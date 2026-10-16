import math
from typing import Dict, List, Tuple, Optional
from ..grid_engine.thermal_dynamics import ThermodynamicLineModel

class EntropyCalculator:
    """
    Evaluates branch non-equilibrium entropy generation rates, Gouy-Stodola exergy destruction,
    and closed-state current estimation for unenergized candidate tie lines.
    
    Theoretical Formulation (3-phase balanced):
        I_line = S_VA / (sqrt(3) * V)
        P_loss,3phi = 3 * I_line^2 * R_e(T_e)
        S_dot_gen,e = P_loss,3phi / T_e = (3 * I_line^2 * R_e(T_e)) / T_e   [Watts / Kelvin]
        E_x,destroyed = T_0 * S_gen                                          [Joules]
    """
    def __init__(self, t0_reference: float = 298.15):
        self.t0 = t0_reference

    def compute_branch_entropy_rate(self, line: ThermodynamicLineModel, current_amps: float) -> float:
        """Computes instantaneous 3-phase S_dot for a branch in Watts/Kelvin."""
        r = line.resistance()
        # 3-phase active power loss: 3 * I^2 * R
        p_loss_3phi = 3.0 * (current_amps ** 2) * r
        return p_loss_3phi / max(line.temp, 273.15)

    def estimate_closed_branch_currents(
        self,
        lines: Dict[int, ThermodynamicLineModel],
        active_currents: Dict[int, float],
        bus_voltages_pu: Dict[int, float],
        v_base_v: float = 12660.0
    ) -> Dict[int, float]:
        """
        Estimates the anticipated current for every line if closed:
        - For active lines: uses actual current.
        - For open tie lines: uses physical potential drop ΔV across open terminal buses
          divided by estimated loop impedance Z_loop.
        """
        estimated_currents = {}
        for edge_id, line in lines.items():
            act_i = active_currents.get(edge_id, 0.0)
            if act_i > 1.0:
                estimated_currents[edge_id] = act_i
            else:
                # Open tie line: estimate closed current from open-circuit voltage differential
                v_u = bus_voltages_pu.get(line.u, 1.0)
                v_v = bus_voltages_pu.get(line.v, 1.0)
                delta_v_volts = abs(v_u - v_v) * v_base_v
                # Loop impedance (line impedance + upstream network approximation)
                r_line = line.resistance()
                z_loop = math.sqrt(r_line ** 2 + line.x0 ** 2) + 1.5
                # Symmetrical component circulating current in 3-phase: ΔV / (sqrt(3) * Z)
                i_est = delta_v_volts / (math.sqrt(3.0) * max(z_loop, 0.5))
                # Bound to reasonable physical feeder current range
                estimated_currents[edge_id] = max(min(i_est, line.i_max), 25.0)

        return estimated_currents

    def compute_all_entropy_weights(
        self,
        lines: Dict[int, ThermodynamicLineModel],
        anticipated_currents: Dict[int, float]
    ) -> Dict[int, float]:
        """
        Calculates branch weights w_e = S_dot_e using anticipated closed currents.
        These weights form the linear coefficients of the Thermodynamic Objective H_thermo(x).
        """
        weights = {}
        for edge_id, line in lines.items():
            current = anticipated_currents.get(edge_id, 30.0)
            weights[edge_id] = self.compute_branch_entropy_rate(line, current)
        return weights

    def compute_exergy_destruction(self, entropy_joules_per_k: float) -> float:
        """Gouy-Stodola Theorem: Exergy Destroyed = T_0 * S_gen."""
        return self.t0 * entropy_joules_per_k


def mesh_branch_currents(
    grid,
    injections: Dict[int, Tuple[float, float]],
    temps_k: Optional[Dict[int, float]] = None,
) -> Dict[int, float]:
    """Estimated current (Amps) every candidate line would carry with ALL switches closed (meshed network).

    Solves the complex nodal equations of the fully meshed feeder with constant-power loads linearized at 1.0 pu.
    Unlike last-step currents, this gives non-zero, physically grounded currents for open tie lines as well
    (Merlin-Back heuristic relaxation).
    """
    import numpy as np

    buses = sorted(grid.graph.nodes)
    idx = {b: i for i, b in enumerate(buses)}
    n = len(buses)
    root = idx[grid.substations[0]]

    Y = np.zeros((n, n), dtype=complex)
    ys = {}

    for e, line in grid.lines.items():
        t = line.temp if temps_k is None else temps_k.get(e, line.temp)
        r = line.r0 * (1.0 + line.alpha * (t - line.t_amb))
        z = complex(r, line.x0) / grid.z_base_ohm
        y = 1.0 / z
        ys[e] = y
        a, b = idx[line.u], idx[line.v]
        Y[a, a] += y
        Y[b, b] += y
        Y[a, b] -= y
        Y[b, a] -= y

    # Injections: P + jQ in pu (load is negative injection)
    s_pu = np.zeros(n, dtype=complex)
    for b, (p_kw, q_kvar) in injections.items():
        if b in idx:
            s_pu[idx[b]] = complex(p_kw, q_kvar) * 1e3 / (grid.s_base_mva * 1e6)

    # Nodal current injection: I_inj = conj(S / V) ~ conj(S) for V ~ 1.0
    i_inj = np.conj(s_pu)

    # Substation bus voltage is fixed at 1.0 + j0.0 pu (slack bus)
    keep = [i for i in range(n) if i != root]
    Y_red = Y[np.ix_(keep, keep)]
    rhs = i_inj[keep] - Y[keep, root] * 1.0

    try:
        v_red = np.linalg.solve(Y_red, rhs)
    except np.linalg.LinAlgError:
        v_red = np.ones(len(keep), dtype=complex)

    v = np.ones(n, dtype=complex)
    v[keep] = v_red

    # Branch currents in Amperes: I_ij = |V_i - V_j| / |z_ij| * I_base
    i_base_amps = (grid.s_base_mva * 1e6) / (np.sqrt(3.0) * grid.v_base_kv * 1e3)
    currents = {}
    for e, line in grid.lines.items():
        a, b = idx[line.u], idx[line.v]
        delta_v_pu = abs(v[a] - v[b])
        i_pu = delta_v_pu * abs(ys[e])
        currents[e] = float(i_pu * i_base_amps)

    return currents
