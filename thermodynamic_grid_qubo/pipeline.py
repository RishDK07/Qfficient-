"""
End-to-end backend pipeline for Qfficient.

`run_optimization(config)` runs the classical baseline and the thermodynamic QUBO
optimizer over a transient scenario and returns ONE plain-dict result that the
front end (report card) renders. Nothing in the result is hard-coded: topology,
line flows, losses and metrics all come from the solver / power-flow runs.
"""
from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, List, Optional

import networkx as nx
import numpy as np

from .grid_engine.ieee_feeder_loader import DistributionGrid, IEEEFeederLoader
from .grid_engine.custom_grid_generator import generate_custom_grid
from .grid_engine.renewable_simulator import RenewableProfileSimulator
from .qubo_engine.entropy_calculator import EntropyCalculator
from .qubo_engine.penalty_tuner import PenaltyTuner
from .qubo_engine.qubo_builder import ThermodynamicQUBOBuilder
from .solvers.classical_baseline import ClassicalBaselineSolver
from .solvers.exact_classical_solver import ExactClassicalSolver
from .solvers.numpy_annealer import NumpyAnnealer
from .solvers.openjij_annealer import OpenJijAnnealer
from .verification.metrics_evaluator import MetricsEvaluator
from .verification.microgrid_visualizer import SAMPLE_LINES, SAMPLE_NODES
from .verification.physics_verifier import PhysicsVerifier

# ---------------------------------------------------------------------------
# Input limits
# ---------------------------------------------------------------------------
# One binary variable per branch, and the radiality term couples EVERY pair of
# branches, so the QUBO has M*(M-1)/2 couplings (M = number of branches).
# These caps keep an interactive run (40 annealing steps) in the seconds range.
MAX_BUSES = 100       # components (buses / nodes)
MAX_BRANCHES = 150    # candidate lines incl. tie switches  -> ~11k couplings

GRID_CHOICES = {
    "ieee33": "IEEE 33-Bus Radial Feeder",
    "microgrid12": "12-Component Smart Microgrid",
    "custom": "Custom User-Defined Microgrid",
}
SOLVER_CHOICES = {
    "exact_oracle": "Exact Loss-Minimizing Reconfiguration (Baran-Wu Optimum)",
    "numpy_annealer": "NumPy Vectorized Annealer (Native, Fast)",
    "sqa": "OpenJij Simulated Quantum Annealing (SQA)",
    "neal": "D-Wave Neal (Simulated Annealing)",
    "classical": "Classical Minimum-Resistance Baseline",
}


class GridSizeError(ValueError):
    """Raised when a grid exceeds the supported component / branch limits."""


@dataclass
class OptimizationConfig:
    grid: str = "microgrid12"      # key of GRID_CHOICES
    solver: str = "sqa"            # key of SOLVER_CHOICES
    solar_drop_pct: float = 75.0   # 0-90
    ev_surge_kw: float = 700.0     # 0-1200
    ambient_c: float = 25.0
    num_reads: int = 400
    time_steps: int = 40
    dt_seconds: float = 2.0
    seed: int = 42
    # Custom Grid Parameters
    custom_n_components: int = 30
    custom_n_solar: int = 3
    custom_n_wind: int = 2
    custom_n_battery: int = 2
    custom_n_ev: int = 2
    custom_n_ties: int = 5
    custom_grid: Optional[DistributionGrid] = None


def validate_grid_size(grid: DistributionGrid) -> None:
    n_buses, n_lines = len(grid.graph.nodes), len(grid.lines)
    if n_buses > MAX_BUSES:
        raise GridSizeError(f"{n_buses} components supplied; the limit is {MAX_BUSES}.")
    if n_lines > MAX_BRANCHES:
        raise GridSizeError(f"{n_lines} candidate lines supplied; the limit is {MAX_BRANCHES}.")
    if not grid.substations:
        raise GridSizeError("At least one substation (slack bus) is required.")
    if len(grid.substations) > 1:
        raise GridSizeError("Only a single substation is supported by the power-flow solver.")
    if not nx.is_connected(grid.graph):
        raise GridSizeError("The candidate network must be connected.")


# ---------------------------------------------------------------------------
# Grid builders
# ---------------------------------------------------------------------------
def load_12_component_microgrid() -> DistributionGrid:
    """
    Builds the 12-component microgrid from the SAME node/line table that the
    topology diagram uses, so the solver and the picture can never disagree.
    Impedances are derived from each line's reference loss figure.
    """
    names = list(SAMPLE_NODES)
    ids = {n: i + 1 for i, n in enumerate(names)}
    grid = DistributionGrid("Microgrid_12_Component", v_base_kv=12.66, s_base_mva=5.0)

    base_loads = {  # kW, kVAR
        "EV Depot": (60, 20), "Hospital": (180, 90), "Data Center": (220, 100),
        "Residential": (150, 60), "Heavy Industry": (320, 150),
    }
    for n in names:
        p, q = base_loads.get(n, (0, 0))
        grid.add_bus(ids[n], p_kw=p, q_kvar=q, is_substation=(n == "Substation"))

    for idx, (_lid, a, b, loss_kw, _flow) in enumerate(SAMPLE_LINES):
        r = 0.25 + 0.35 * loss_kw
        grid.add_branch(idx, ids[a], ids[b], r_ohm=r, x_ohm=0.5 * r, i_max=300.0)

    grid.der_nodes = {
        ids["Solar Farm"]: "pv", ids["Wind Park"]: "wind",
        ids["Battery BESS"]: "bess", ids["EV Depot"]: "ev",
    }
    return grid


def _grid_meta(choice: str, grid: DistributionGrid) -> Dict[str, Any]:
    """Display metadata: labels, roles, coordinates, line names."""
    roles = {b: "load" for b in grid.graph.nodes}
    for b in grid.substations:
        roles[b] = "substation"
    for b, kind in grid.der_nodes.items():
        roles[b] = kind

    if choice == "microgrid12":
        names = list(SAMPLE_NODES)
        node_labels = {i + 1: n for i, n in enumerate(names)}
        positions = {i + 1: SAMPLE_NODES[n] for i, n in enumerate(names)}
        line_labels = {i: row[0] for i, row in enumerate(SAMPLE_LINES)}
    elif choice == "custom":
        node_labels = {}
        for b in grid.graph.nodes:
            if b in grid.substations:
                node_labels[b] = f"Substation (B{b})"
            elif b in grid.der_nodes:
                kind = grid.der_nodes[b].upper()
                der_names = {"PV": "Solar", "WIND": "Wind", "BESS": "Battery", "EV": "EV Depot"}
                node_labels[b] = f"{der_names.get(kind, kind)} (B{b})"
            else:
                node_labels[b] = f"Bus {b}"

        pos = getattr(grid, "layout_positions", None)
        if not pos or len(pos) != len(grid.graph.nodes):
            pos = nx.kamada_kawai_layout(grid.graph)
        positions = {b: (float(x), float(y)) for b, (x, y) in pos.items()}

        line_labels = {}
        tie_counter = 1
        for e, line in grid.lines.items():
            if grid.graph[line.u][line.v].get("is_tie", False):
                line_labels[e] = f"T{tie_counter}"
                tie_counter += 1
            else:
                line_labels[e] = f"L{e + 1}"
    else:
        node_labels = {b: str(b) for b in grid.graph.nodes}
        pos = nx.kamada_kawai_layout(grid.graph)
        positions = {b: (float(x), float(y)) for b, (x, y) in pos.items()}
        line_labels = {}
        for e, line in grid.lines.items():
            line_labels[e] = f"T{e - 31}" if grid.graph[line.u][line.v]["is_tie"] else f"L{e + 1}"

    return {
        "node_labels": node_labels,
        "node_roles": roles,
        "positions": {int(k): [float(v[0]), float(v[1])] for k, v in positions.items()},
        "line_labels": line_labels,
    }


# ---------------------------------------------------------------------------
# Scenario with user-controlled transients
# ---------------------------------------------------------------------------
class ParametricScenario(RenewableProfileSimulator):
    """Same scenario generator as the benchmark, but solar drop / EV surge are inputs."""

    def __init__(self, *args, solar_drop_pct: float, ev_surge_kw: float, **kwargs):
        super().__init__(*args, **kwargs)
        self.solar_drop_pct = float(solar_drop_pct)
        self.ev_surge_kw = float(ev_surge_kw)

    def generate_pv_profile(self, base_cap_kw: float = 450.0) -> np.ndarray:
        n = self.time_steps
        t = np.linspace(0, 1, n)
        profile = base_cap_kw * np.maximum(np.sin(np.pi * t), 0.2)
        start, end = int(n * 0.3), int(n * 0.6)
        residual = 1.0 - self.solar_drop_pct / 100.0
        amp = 0.1 * min(self.solar_drop_pct / 75.0, 1.0)
        cloud = np.clip(residual + amp * np.sin(np.linspace(0, 2 * np.pi, end - start)), 0.0, None)
        profile[start:end] *= cloud
        noise = self.rng.normal(0, 0.03 * base_cap_kw, n)
        return np.maximum(profile + noise, 0.0)

    def generate_ev_charging_profile(self, peak_kw: float = 650.0) -> np.ndarray:
        n = self.time_steps
        profile = np.ones(n) * 50.0
        profile[int(n * 0.2): int(n * 0.55)] = max(self.ev_surge_kw, 50.0)
        ripple = self.rng.normal(0, 15.0, n)
        return np.maximum(profile + ripple, 10.0)


# ---------------------------------------------------------------------------
# Solver dispatch
# ---------------------------------------------------------------------------
def _anneal(solver: str, annealer: OpenJijAnnealer, bqm, num_reads: int):
    """Returns (energy, latency_ms, response) for sqa / neal / numpy_annealer."""
    if solver == "sqa":
        _s, energy, ms, resp = annealer.solve(bqm, num_reads=num_reads)
        return energy, ms, resp
    elif solver == "numpy_annealer":
        import dimod
        t0 = time.perf_counter()
        Q, offset = bqm.to_qubo()
        var_list = list(bqm.variables)
        vmap = {v: i for i, v in enumerate(var_list)}
        N = len(var_list)
        q_mat = np.zeros((N, N), dtype=float)
        for (u, v), val in Q.items():
            q_mat[vmap[u], vmap[v]] = val
        X, E, sample_ms = NumpyAnnealer(sweeps=80).sample(q_mat, num_reads=num_reads, offset=offset)
        samples = [{var_list[i]: int(X[r, i]) for i in range(N)} for r in range(len(X))]
        resp = dimod.SampleSet.from_samples(samples, vartype=dimod.BINARY, energy=E)
        return float(E[0]), sample_ms, resp
    import neal
    t0 = time.perf_counter()
    resp = neal.SimulatedAnnealingSampler().sample(bqm, num_reads=num_reads)
    return float(resp.first.energy), (time.perf_counter() - t0) * 1000.0, resp


def estimate_runtime_s(cfg: OptimizationConfig, n_lines: int) -> float:
    """Rough wall-clock estimate (seconds) for the UI."""
    per_read_var_ms = {"sqa": 0.42, "neal": 0.035, "numpy_annealer": 0.005, "exact_oracle": 0.0, "classical": 0.0}.get(cfg.solver, 0.02)
    return cfg.time_steps * (cfg.num_reads * n_lines * per_read_var_ms / 1000.0 + 0.05)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def run_optimization(
    cfg: OptimizationConfig,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, Any]:
    if cfg.grid not in GRID_CHOICES:
        raise ValueError(f"Unknown grid '{cfg.grid}'.")
    if cfg.solver not in SOLVER_CHOICES:
        raise ValueError(f"Unknown solver '{cfg.solver}'.")

    started = time.perf_counter()
    notify = progress_cb or (lambda i, n, m: None)
    T, dt = cfg.time_steps, cfg.dt_seconds

    if cfg.grid == "custom":
        if cfg.custom_grid is not None:
            grid_base = copy.deepcopy(cfg.custom_grid)
            grid_qubo = copy.deepcopy(cfg.custom_grid)
        else:
            def _build_custom():
                return generate_custom_grid(
                    n_components=cfg.custom_n_components,
                    n_solar=cfg.custom_n_solar,
                    n_wind=cfg.custom_n_wind,
                    n_battery=cfg.custom_n_battery,
                    n_ev=cfg.custom_n_ev,
                    n_ties=cfg.custom_n_ties,
                    seed=cfg.seed,
                )
            grid_base, grid_qubo = _build_custom(), _build_custom()
    else:
        loader = load_12_component_microgrid if cfg.grid == "microgrid12" else IEEEFeederLoader.load_ieee33
        grid_base, grid_qubo = loader(), loader()
    validate_grid_size(grid_qubo)

    t_amb_k = cfg.ambient_c + 273.15
    for g in (grid_base, grid_qubo):
        for line in g.lines.values():
            line.t_amb = t_amb_k
            line.temp = t_amb_k

    meta = _grid_meta(cfg.grid, grid_qubo)
    edges = grid_qubo.get_edge_list()
    edge_ids = sorted(grid_qubo.lines)
    num_buses = len(grid_qubo.graph.nodes)

    scenario = ParametricScenario(
        time_steps=T, dt_seconds=dt, seed=cfg.seed,
        solar_drop_pct=cfg.solar_drop_pct, ev_surge_kw=cfg.ev_surge_kw,
    ).get_feeder_transient_scenario(grid_qubo.der_nodes, grid_qubo.bus_loads)

    verifier_base, verifier_qubo = PhysicsVerifier(grid_base), PhysicsVerifier(grid_qubo)
    entropy_calc, tuner = EntropyCalculator(t0_reference=298.15), PenaltyTuner()
    annealer = OpenJijAnnealer(use_sqa=(cfg.solver == "sqa"))
    evaluator = MetricsEvaluator(t0_ambient=298.15)

    def thermal_step(grid, switches, currents):
        heat_j = ent = 0.0
        temps, loss_kw = [], []
        for e in edge_ids:
            line = grid.lines[e]
            i_act = currents.get(e, 0.0) if switches.get(e, 0) == 1 else 0.0
            loss_kw.append(3.0 * i_act ** 2 * line.resistance() / 1000.0)  # 3-phase, as in power flow
            temp = line.update_transient_temperature(i_act, dt_seconds=dt)
            temps.append(temp - 273.15)
            q_j = (i_act ** 2) * line.resistance() * dt   # same convention as main_experiment.py
            heat_j += q_j
            ent += q_j / max(temp, 273.15)
        return heat_j / 1e6, ent, temps, loss_kw

    def overloaded(grid, switches, currents) -> int:
        return sum(1 for e in edge_ids
                   if switches.get(e, 0) == 1 and currents.get(e, 0.0) > grid.lines[e].i_max)

    # ---- A. classical baseline (static minimum resistance) ------------------
    notify(0, T * 2, "Running classical baseline…")
    t0 = time.perf_counter()
    base_switches = ClassicalBaselineSolver(grid_base).solve()
    base_latency_ms = (time.perf_counter() - t0) * 1000.0   # measured, not a constant

    B = {k: [] for k in ("heat_mj", "entropy", "peak_temp", "min_v", "loss_kw", "currents", "temps", "line_loss_kw")}
    base_viol = base_over = 0
    for t in range(T):
        ok, v_pu, cur, loss = verifier_base.solve_power_flow(base_switches, scenario[t])
        base_viol += 0 if ok else 1
        base_over += overloaded(grid_base, base_switches, cur)
        heat, ent, temps, ll = thermal_step(grid_base, base_switches, cur)
        B["heat_mj"].append(heat); B["entropy"].append(ent)
        B["peak_temp"].append(max(temps)); B["min_v"].append(min(v_pu.values()))
        B["loss_kw"].append(loss); B["temps"].append(temps); B["line_loss_kw"].append(ll)
        B["currents"].append([cur.get(e, 0.0) for e in edge_ids])
        notify(t + 1, T * 2, f"Baseline step {t + 1}/{T}")

    # ---- B. thermodynamic QUBO ---------------------------------------------
    Q = {k: [] for k in ("heat_mj", "entropy", "peak_temp", "min_v", "loss_kw", "currents", "temps",
                         "line_loss_kw", "switches", "toggles", "latency_ms", "energy")}
    qubo_viol = qubo_over = 0
    active = copy.deepcopy(base_switches)
    currents_q = {e: 120.0 for e in grid_qubo.lines}
    n_vars = n_couplings = n_cycles = 0

    for t in range(T):
        prev = dict(active)
        if cfg.solver == "exact_oracle":
            t0 = time.perf_counter()
            exact_solver = ExactClassicalSolver(grid_qubo)
            active, best_loss, _ = exact_solver.solve_exact_loss_minimizer(scenario[t])
            ms = (time.perf_counter() - t0) * 1000.0
            energy = best_loss
        elif cfg.solver != "classical":
            weights = entropy_calc.compute_all_entropy_weights(grid_qubo.lines, currents_q)
            lam = tuner.calibrate(weights, num_buses)
            builder = ThermodynamicQUBOBuilder(
                num_buses=num_buses, edges=edges, substations=grid_qubo.substations,
                graph=grid_qubo.graph, lambda_thermo=lam["lambda_thermo"], lambda_cycle=lam["lambda_cycle"],
                lambda_rad=lam["lambda_rad"], lambda_cap=lam["lambda_cap"], lambda_sw=lam["lambda_sw"],
            )
            bqm = builder.build_bqm(weights, currents_q, {e: l.i_max for e, l in grid_qubo.lines.items()}, active)
            if t == 0:
                n_vars, n_couplings, n_cycles = len(bqm.variables), len(bqm.quadratic), len(builder.cycle_edge_ids)
            energy, ms, resp = _anneal(cfg.solver, annealer, bqm, cfg.num_reads)
            active = annealer.extract_optimal_tree(resp, grid_qubo, weights, injections=scenario[t], current_switches=active)
        else:
            energy, ms = 0.0, base_latency_ms

        ok, v_pu, cur, loss = verifier_qubo.solve_power_flow(active, scenario[t])
        currents_q = cur
        qubo_viol += 0 if ok else 1
        qubo_over += overloaded(grid_qubo, active, cur)
        heat, ent, temps, ll = thermal_step(grid_qubo, active, cur)
        Q["heat_mj"].append(heat); Q["entropy"].append(ent)
        Q["peak_temp"].append(max(temps)); Q["min_v"].append(min(v_pu.values()))
        Q["loss_kw"].append(loss); Q["temps"].append(temps); Q["line_loss_kw"].append(ll)
        Q["currents"].append([cur.get(e, 0.0) for e in edge_ids])
        Q["switches"].append([int(active.get(e, 0)) for e in edge_ids])
        Q["toggles"].append(sum(1 for e in edge_ids if active.get(e, 0) != prev.get(e, 0)) if t else 0)
        Q["latency_ms"].append(ms); Q["energy"].append(energy)
        notify(T + t + 1, T * 2, f"Optimizing step {t + 1}/{T}")

    # ---- C. metrics & hard checks ------------------------------------------
    s_base = evaluator.summarize_run(B["heat_mj"], B["entropy"], B["peak_temp"], base_viol, [base_latency_ms] * T)
    s_qubo = evaluator.summarize_run(Q["heat_mj"], Q["entropy"], Q["peak_temp"], qubo_viol, Q["latency_ms"])
    comparison = evaluator.compare_methods(s_base, s_qubo)

    radial_ok = all(verifier_qubo.is_valid_radial_tree({e: s for e, s in zip(edge_ids, sw)})[0]
                    for sw in Q["switches"])
    peak_step = int(np.argmax(B["loss_kw"]))

    return {
        "run_id": uuid.uuid4().hex[:8],
        "config": asdict(cfg),
        "grid": {
            "name": grid_qubo.name,
            "title": (f"Custom Microgrid ({num_buses} Buses, {len(grid_qubo.tie_switches)} Ties)"
                      if cfg.grid == "custom" else GRID_CHOICES[cfg.grid]),
            "n_buses": num_buses,
            "n_lines": len(edge_ids),
            "n_ties": len(grid_qubo.tie_switches),
            "n_qubo_vars": n_vars,
            "n_couplings": n_couplings,
            "n_cycles": n_cycles,
            "edges": [{"id": e, "u": grid_qubo.lines[e].u, "v": grid_qubo.lines[e].v,
                       "i_max": grid_qubo.lines[e].i_max, "label": meta["line_labels"].get(e, f"L{e + 1}")}
                      for e in edge_ids],
            **meta,
        },
        "solver_label": SOLVER_CHOICES[cfg.solver],
        "time_s": [t * dt for t in range(T)],
        "peak_step": peak_step,
        "baseline": {**B, "switches": [int(base_switches.get(e, 0)) for e in edge_ids],
                     "latency_ms": base_latency_ms},
        "qubo": Q,
        "summary": comparison,
        "checks": {
            "radial_all_steps": bool(radial_ok),
            "overload_line_steps_base": int(base_over),
            "overload_line_steps_qubo": int(qubo_over),
            "reconfigurations": int(sum(Q["toggles"])),
        },
        "runtime_s": time.perf_counter() - started,
    }
