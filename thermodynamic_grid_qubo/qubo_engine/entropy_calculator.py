import math
from typing import Dict, List, Tuple
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
