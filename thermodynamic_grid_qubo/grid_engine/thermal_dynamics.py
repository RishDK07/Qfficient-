import numpy as np

class ThermodynamicLineModel:
    """
    Models transient temperature rise, dynamic electrical resistance, and
    non-equilibrium thermodynamic entropy generation rate for overhead and
    underground electrical distribution conductors under dynamic current loading.
    
    Governing differential equation:
        C_th * (dT/dt) = I^2 * R(T) - (T - T_amb) / theta_th
    """
    def __init__(
        self,
        edge_id: int,
        u: int,
        v: int,
        r0: float = 0.2,
        x0: float = 0.1,
        alpha: float = 0.00393,
        c_th: float = 250000.0,
        theta_th: float = 0.003,
        t_amb: float = 298.15,
        i_max: float = 400.0,
        length_km: float = 1.0,
    ):
        self.edge_id = edge_id
        self.u = u
        self.v = v
        self.r0 = r0 * length_km            # Nominal resistance at reference temp (Ohms)
        self.x0 = x0 * length_km            # Reactance (Ohms)
        self.alpha = alpha                  # Temperature coefficient of resistance (1/K)
        self.c_th = c_th * length_km        # Conductor heat capacity (J/K)
        self.theta_th = theta_th / max(length_km, 1e-4) # Thermal resistance to ambient (K/W)
        self.t_amb = t_amb                  # Ambient environmental temperature (Kelvin, 25°C = 298.15K)
        self.temp = t_amb                   # Operating conductor temperature (Kelvin)
        self.i_max = i_max                  # Max thermal ampacity rating (Amperes)
        self.total_joule_heat_joules = 0.0  # Cumulative heat energy dissipated (Joules)
        self.total_entropy_gen = 0.0        # Cumulative entropy generation (J/K)

    def resistance(self) -> float:
        """Dynamic temperature-dependent electrical resistance R(T)."""
        return self.r0 * (1.0 + self.alpha * (self.temp - self.t_amb))

    def update_transient_temperature(self, current_amps: float, dt_seconds: float = 1.0) -> float:
        """
        Integrates the thermal transient differential equation:
            C_th * dT/dt = I^2 * R(T) - (T - T_amb) / theta_th
        """
        r = self.resistance()
        q_joule = (current_amps ** 2) * r
        q_dissipated = (self.temp - self.t_amb) / self.theta_th
        
        # Conductor temperature rate of change
        dT = ((q_joule - q_dissipated) / self.c_th) * dt_seconds
        self.temp += dT
        
        # Accumulate metrics
        self.total_joule_heat_joules += q_joule * dt_seconds
        s_dot = q_joule / max(self.temp, 273.15)
        self.total_entropy_gen += s_dot * dt_seconds
        
        return self.temp

    def entropy_generation_rate(self, current_amps: float) -> float:
        """
        Calculates local instantaneous entropy generation rate:
            S_dot = (I^2 * R(T)) / T  (Watts/Kelvin)
        """
        r = self.resistance()
        p_loss = (current_amps ** 2) * r
        return p_loss / max(self.temp, 273.15)

    def power_loss(self, current_amps: float) -> float:
        """Instantaneous Ohmic power loss P_loss = I^2 * R(T) (Watts)."""
        return (current_amps ** 2) * self.resistance()

    def is_thermal_overloaded(self, current_amps: float) -> bool:
        """Checks if line current exceeds max ampacity or operating temperature limit (e.g. 90°C = 363.15 K)."""
        return (current_amps > self.i_max) or (self.temp > 363.15)

    def reset_thermal_state(self):
        """Resets conductor temperature back to ambient."""
        self.temp = self.t_amb
        self.total_joule_heat_joules = 0.0
        self.total_entropy_gen = 0.0
