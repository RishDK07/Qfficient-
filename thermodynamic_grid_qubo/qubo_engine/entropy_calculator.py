from typing import Dict
from ..grid_engine.thermal_dynamics import ThermodynamicLineModel

class EntropyCalculator:
    """
    Evaluates branch non-equilibrium entropy generation rates and Gouy-Stodola exergy destruction.
    
    Theoretical Formulation:
        S_dot_gen,e = (I_e^2 * R_e(T_e)) / T_e = P_loss,e / T_e   [Watts / Kelvin]
        E_x,destroyed = T_0 * S_gen                               [Joules]
    """
    def __init__(self, t0_reference: float = 298.15):
        self.t0 = t0_reference

    def compute_branch_entropy_rate(self, line: ThermodynamicLineModel, current_amps: float) -> float:
        """Computes instantaneous S_dot for a branch in Watts/Kelvin."""
        r = line.resistance()
        p_loss = (current_amps ** 2) * r
        return p_loss / max(line.temp, 273.15)

    def compute_all_entropy_weights(
        self,
        lines: Dict[int, ThermodynamicLineModel],
        anticipated_currents: Dict[int, float]
    ) -> Dict[int, float]:
        """
        Calculates branch weights w_e = S_dot_e for all lines.
        These weights form the linear coefficients of the Thermodynamic Objective H_thermo(x).
        """
        weights = {}
        for edge_id, line in lines.items():
            current = anticipated_currents.get(edge_id, 0.0)
            weights[edge_id] = self.compute_branch_entropy_rate(line, current)
        return weights

    def compute_exergy_destruction(self, entropy_joules_per_k: float) -> float:
        """Gouy-Stodola Theorem: Exergy Destroyed = T_0 * S_gen."""
        return self.t0 * entropy_joules_per_k
