import numpy as np
from typing import Dict

class PenaltyTuner:
    """
    Calibrates Lagrange multipliers (λ_thermo, λ_cycle, λ_rad, λ_cap, λ_sw)
    to maintain constraint feasibility while preventing objective suppression.
    """
    def __init__(self, base_scale: float = 1.0):
        self.base_scale = base_scale

    def calibrate(self, entropy_weights: Dict[int, float], num_buses: int) -> Dict[str, float]:
        """Calculates optimal Lagrange multipliers for given feeder and operating state."""
        weights = list(entropy_weights.values())
        max_w = max(weights) if weights else 1.0
        avg_w = float(np.mean(weights)) if weights else 0.5
        
        lambda_thermo = 1.0 * self.base_scale
        lambda_cycle = max(15.0 * max_w, 25.0) * self.base_scale
        lambda_rad = max(20.0 * max_w, 30.0) * self.base_scale
        lambda_cap = max(10.0 * max_w, 15.0) * self.base_scale
        lambda_sw = max(0.2 * avg_w, 0.5) * self.base_scale

        return {
            "lambda_thermo": lambda_thermo,
            "lambda_cycle": lambda_cycle,
            "lambda_rad": lambda_rad,
            "lambda_cap": lambda_cap,
            "lambda_sw": lambda_sw,
        }
