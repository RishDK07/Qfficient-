"""Pandapower AC Power Flow Cross-Validation against LinDistFlow.

Validates active power losses and minimum bus voltage between the fast
vectorized LinDistFlow formulation and the non-linear full AC power flow (Newton-Raphson)
computed via pandapower.
"""
from typing import Dict, List, Tuple, Sequence, Optional
import numpy as np
import pandapower as pp
import pandapower.networks as nw

from ..grid_engine.ieee_feeder_loader import DistributionGrid, IEEEFeederLoader
from .fast_flow import FastFeeder


class PandapowerVerifier:
    """Cross-validates LinDistFlow results against Pandapower full AC power flow."""

    def __init__(self, grid: Optional[DistributionGrid] = None):
        if grid is None:
            grid = IEEEFeederLoader.load_ieee33()
        self.grid = grid
        self.fast = FastFeeder(grid)
        self.net = self._build_pandapower_network()

    def _build_pandapower_network(self) -> pp.pandapowerNet:
        """Construct matching pandapower network from DistributionGrid."""
        net = pp.create_empty_network(f_hz=50.0, sn_mva=self.grid.s_base_mva)

        # Bus mapping: grid bus_id -> pp bus index
        self.bus_map = {}
        for b in sorted(self.grid.graph.nodes):
            is_sub = (b in self.grid.substations)
            vn_kv = self.grid.v_base_kv
            pp_b = pp.create_bus(net, vn_kv=vn_kv, name=f"Bus_{b}", zone=None)
            self.bus_map[b] = pp_b
            if is_sub:
                pp.create_ext_grid(net, bus=pp_b, vm_pu=1.0, va_degree=0.0)

        # Add lines
        self.line_map = {}
        tie_set = set(self.grid.tie_switches)
        for edge_id, model in sorted(self.grid.lines.items()):
            from_b = self.bus_map[model.u]
            to_b = self.bus_map[model.v]
            pp_l = pp.create_line_from_parameters(
                net,
                from_bus=from_b,
                to_bus=to_b,
                length_km=1.0,
                r_ohm_per_km=model.r0,
                x_ohm_per_km=model.x0,
                c_nf_per_km=0.0,
                max_i_ka=model.i_max / 1000.0,
                name=f"Line_{edge_id}",
                in_service=(edge_id not in tie_set),
            )
            self.line_map[edge_id] = pp_l

        # Create load placeholders for all load buses
        self.load_map = {}
        for b, (p, q) in self.grid.bus_loads.items():
            if b not in self.grid.substations:
                pp_b = self.bus_map[b]
                pp_load = pp.create_load(net, bus=pp_b, p_mw=p / 1000.0, q_mvar=q / 1000.0, name=f"Load_{b}")
                self.load_map[b] = pp_load

        return net

    def update_injections(self, injections: Dict[int, Tuple[float, float]]):
        """Update bus net injections in pandapower network.
        injections: Dict[bus, (P_kW, Q_kVAR)] where negative means load demand.
        """
        for b, pp_load in self.load_map.items():
            inj = injections.get(b, (0.0, 0.0))
            # If inj is negative, demand is positive
            p_dem_mw = -inj[0] / 1000.0 if inj[0] < 0 else 0.0
            q_dem_mvar = -inj[1] / 1000.0 if inj[1] < 0 else 0.0
            self.net.load.loc[pp_load, "p_mw"] = p_dem_mw
            self.net.load.loc[pp_load, "q_mvar"] = q_dem_mvar

    def set_topology(self, active_edges: Sequence[int]):
        """Update switch status in pandapower network."""
        active_set = set(active_edges)
        for edge_id, pp_l in self.line_map.items():
            self.net.line.loc[pp_l, "in_service"] = (edge_id in active_set)

    def solve_ac(self) -> Tuple[bool, float, float]:
        """Runs full AC power flow using Newton-Raphson.

        Returns:
            converged: bool
            loss_kw: total active power loss across all branches in kW
            v_min: minimum bus voltage magnitude in pu
        """
        try:
            pp.runpp(self.net, algorithm="nr", numba=False, max_iteration=30, tolerance_mva=1e-5)
            loss_kw = float(self.net.res_line.pl_mw.sum() * 1000.0)
            v_min = float(self.net.res_bus.vm_pu.min())
            return True, loss_kw, v_min
        except Exception:
            return False, 1e9, 0.0

    def cross_validate(
        self,
        active_edges: Sequence[int],
        injections: Dict[int, Tuple[float, float]],
        temps_k: Optional[np.ndarray] = None,
    ) -> Dict[str, float]:
        """Compares LinDistFlow and full AC power flow on the specified topology and injections.

        Returns:
            Dict containing lindistflow_loss_kw, ac_loss_kw, loss_error_pct,
            lindistflow_vmin, ac_vmin, vmin_diff_pu, converged.
        """
        p_pu, q_pu = self.fast.vectors(injections)
        resistances = self.fast.resistances(temps_k)
        ld_valid, _, _, ld_loss, ld_vmin = self.fast.evaluate(active_edges, p_pu, q_pu, resistances)

        self.update_injections(injections)
        self.set_topology(active_edges)
        ac_converged, ac_loss, ac_vmin = self.solve_ac()

        loss_err_pct = abs(ld_loss - ac_loss) / ac_loss * 100.0 if ac_converged and ac_loss > 0 else 0.0
        vmin_diff = abs(ld_vmin - ac_vmin) if ac_converged else 0.0

        return {
            "lindistflow_loss_kw": ld_loss,
            "ac_loss_kw": ac_loss,
            "loss_error_pct": loss_err_pct,
            "lindistflow_vmin": ld_vmin,
            "ac_vmin": ac_vmin,
            "vmin_diff_pu": vmin_diff,
            "ac_converged": float(ac_converged),
            "lindistflow_valid": float(ld_valid),
        }
