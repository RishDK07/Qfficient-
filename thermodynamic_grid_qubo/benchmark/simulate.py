"""Dynamic simulation harness for evaluating microgrid reconfiguration policies."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from ..grid_engine.ieee_feeder_loader import DistributionGrid, IEEEFeederLoader
from ..verification.fast_flow import FastFeeder
from .policies import Policy, DecisionContext


@dataclass
class Scenario:
    seed: int
    time_steps: int = 12
    dt_seconds: float = 300.0
    cloud_depth: float = 0.70
    ev_surge_kw: float = 600.0
    load_scale: float = 1.0
    timeline: List[Dict[int, Tuple[float, float]]] = field(default_factory=list)

    @classmethod
    def sample(
        cls,
        seed: int = 42,
        time_steps: int = 12,
        dt_seconds: float = 300.0,
        cloud_depth: Optional[float] = None,
        ev_surge_kw: Optional[float] = None,
        load_scale: Optional[float] = None,
        randomize: bool = True,
    ) -> "Scenario":
        rng = np.random.default_rng(seed)
        grid = IEEEFeederLoader.load_ieee33()

        timeline: List[Dict[int, Tuple[float, float]]] = []

        if randomize:
            c_depth = float(rng.uniform(0.35, 0.85)) if cloud_depth is None else cloud_depth
            ev_surge = float(rng.uniform(350.0, 850.0)) if ev_surge_kw is None else ev_surge_kw
            l_scale = float(rng.uniform(0.85, 1.15)) if load_scale is None else load_scale
            cloud_start = int(time_steps * rng.uniform(0.15, 0.35))
            cloud_end = max(cloud_start + 2, int(time_steps * rng.uniform(0.55, 0.80)))
            ev_start = int(time_steps * rng.uniform(0.25, 0.45))
            ev_end = max(ev_start + 2, int(time_steps * rng.uniform(0.70, 0.95)))
        else:
            c_depth = 0.70 if cloud_depth is None else cloud_depth
            ev_surge = 600.0 if ev_surge_kw is None else ev_surge_kw
            l_scale = 1.0 if load_scale is None else load_scale
            cloud_start = int(time_steps * 0.25)
            cloud_end = int(time_steps * 0.65)
            ev_start = int(time_steps * 0.40)
            ev_end = int(time_steps * 0.85)

        for step in range(time_steps):
            # Slow load variation with subtle noise
            step_load_factor = l_scale * (1.0 + 0.05 * np.sin(2.0 * np.pi * step / time_steps) + rng.normal(0, 0.015))

            # Solar PV generation profile with cloud attenuation
            if cloud_start <= step <= cloud_end:
                dip_phase = (step - cloud_start) / max(cloud_end - cloud_start, 1)
                pv_factor = 1.0 - c_depth * np.sin(np.pi * dip_phase)
            else:
                pv_factor = 1.0 + 0.05 * rng.normal(0, 1.0)
            pv_factor = max(0.05, pv_factor)

            # Wind generation fluctuation
            wind_factor = max(0.2, 0.85 + 0.3 * np.sin(2.0 * np.pi * step / max(time_steps * 0.5, 1)) + 0.1 * rng.normal(0, 1.0))

            # EV depot load surge
            if ev_start <= step <= ev_end:
                ev_factor = np.sin(np.pi * (step - ev_start) / max(ev_end - ev_start, 1))
                ev_add_kw = ev_surge * max(0.0, ev_factor)
            else:
                ev_add_kw = 0.0

            step_injections: Dict[int, Tuple[float, float]] = {}
            for bus_id in grid.graph.nodes:
                p_base, q_base = grid.bus_loads.get(bus_id, (0.0, 0.0))
                # Base load is demand (negative injection)
                p_net = -p_base * step_load_factor
                q_net = -q_base * step_load_factor

                # Distributed Generators
                if bus_id in [14, 25]:  # Solar PV farms
                    p_net += 450.0 * pv_factor
                elif bus_id == 8:       # Secondary Solar
                    p_net += 250.0 * pv_factor
                elif bus_id in [18, 33]: # Wind Turbines
                    p_net += 400.0 * wind_factor
                elif bus_id in [22, 31]: # EV Fast Charging Depots
                    p_net -= ev_add_kw * 0.5

                step_injections[bus_id] = (float(p_net), float(q_net))

            timeline.append(step_injections)

        return cls(
            seed=seed,
            time_steps=time_steps,
            dt_seconds=dt_seconds,
            cloud_depth=c_depth,
            ev_surge_kw=ev_surge,
            load_scale=l_scale,
            timeline=timeline,
        )


def simulate(
    policy: Policy,
    sc: Scenario,
    grid: Optional[DistributionGrid] = None,
    trace: bool = False,
) -> Dict[str, Any]:
    """Executes a simulation scenario under the specified reconfiguration policy."""
    if grid is None:
        grid = IEEEFeederLoader.load_ieee33()

    fast = FastFeeder(grid)
    policy.reset(grid, fast, sc.timeline)

    # Initialize thermal states for all lines (Kelvin)
    temps_k = np.array([grid.lines[e].t_amb for e in fast.edge_ids], dtype=float)
    c_th = np.array([grid.lines[e].c_th for e in fast.edge_ids], dtype=float)
    theta_th = np.array([grid.lines[e].theta_th for e in fast.edge_ids], dtype=float)
    t_amb = np.array([grid.lines[e].t_amb for e in fast.edge_ids], dtype=float)

    total_heat_joules = 0.0
    total_entropy_gen = 0.0
    violation_steps = 0
    min_voltage_pu = 1.0
    switch_ops = 0
    decision_times_ms: List[float] = []

    prev_active = fast.standard_edges

    trace_data = {
        "step": [],
        "heat_kw": [],
        "v_min": [],
        "peak_temp_c": [],
        "switch_ops": [],
        "latency_ms": [],
    }

    for step, injections in enumerate(sc.timeline):
        p_pu, q_pu = fast.vectors(injections)
        resistances = fast.resistances(temps_k)

        ctx = DecisionContext(
            grid=grid,
            fast=fast,
            injections=injections,
            temps_k=temps_k,
            prev_active=prev_active,
            step=step,
            p_pu=p_pu,
            q_pu=q_pu,
            resistances=resistances,
        )

        # Policy decision
        active_edges, decision_ms = policy.decide(ctx)
        decision_times_ms.append(decision_ms)

        # Track switch changes
        diff = len(set(active_edges) - set(prev_active))
        switch_ops += diff
        prev_active = active_edges

        # Power flow evaluation
        ok, v_pu, currents_amps, step_loss_kw, v_min = fast.evaluate(active_edges, p_pu, q_pu, resistances)
        if not ok:
            # Fallback if invalid tree
            active_edges = fast.standard_edges
            ok, v_pu, currents_amps, step_loss_kw, v_min = fast.evaluate(active_edges, p_pu, q_pu, resistances)

        # 3-Phase Joule Heat in step: P_loss * dt = 3 * sum(I^2 * R) * dt
        step_joules = step_loss_kw * 1e3 * sc.dt_seconds
        total_heat_joules += step_joules

        # Entropy generation: sum(P_loss_e / T_e) * dt
        step_entropy = np.sum((fast.n_phases * (currents_amps ** 2) * resistances) / np.maximum(temps_k, 273.15)) * sc.dt_seconds
        total_entropy_gen += step_entropy

        # Conductor thermal ODE (per conductor heat balance):
        # C_th * dT/dt = I^2 * R - (T - T_amb) / theta_th
        q_joule_conductor = (currents_amps ** 2) * resistances
        q_dissipated = (temps_k - t_amb) / theta_th
        dT = ((q_joule_conductor - q_dissipated) / c_th) * sc.dt_seconds
        temps_k += dT

        # Voltage monitoring
        if v_min < 0.95:
            violation_steps += 1
        min_voltage_pu = min(min_voltage_pu, v_min)

        if trace:
            trace_data["step"].append(step)
            trace_data["heat_kw"].append(step_loss_kw)
            trace_data["v_min"].append(v_min)
            trace_data["peak_temp_c"].append(float(np.max(temps_k) - 273.15))
            trace_data["switch_ops"].append(diff)
            trace_data["latency_ms"].append(decision_ms)

    # Exclude head feeder line 0 when measuring lateral temperature relief
    lateral_indices = [i for i in range(fast.m) if i != 0]
    peak_lateral_temp_c = float(np.max(temps_k[lateral_indices]) - 273.15) if lateral_indices else float(np.max(temps_k) - 273.15)

    result = {
        "policy": policy.name,
        "seed": sc.seed,
        "heat_mj": float(total_heat_joules / 1e6),
        "entropy_kj_per_k": float(total_entropy_gen / 1e3),
        "exergy_destroyed_mj": float((298.15 * total_entropy_gen) / 1e6),
        "peak_temp_c": float(np.max(temps_k) - 273.15),
        "peak_temp_excl_head_c": peak_lateral_temp_c,
        "voltage_violation_steps": int(violation_steps),
        "min_voltage_pu": float(min_voltage_pu),
        "switch_operations": int(switch_ops),
        "mean_decision_ms": float(np.mean(decision_times_ms)),
        "max_decision_ms": float(np.max(decision_times_ms)),
        "feasible_read_fraction": float(np.mean(policy.feasible_fractions)) if hasattr(policy, "feasible_fractions") and policy.feasible_fractions else 1.0,
        "total_steps": sc.time_steps,
    }

    if trace:
        result["trace"] = trace_data

    return result
