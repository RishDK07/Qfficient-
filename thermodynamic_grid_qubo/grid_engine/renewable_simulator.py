import numpy as np
from typing import Dict, List, Tuple

class RenewableProfileSimulator:
    """
    Simulates high-penetration renewable microgrid transients:
    1. Solar PV drops (cloud cover shadowing di/dt)
    2. Wind gusts and sudden ramp-downs
    3. Electric Vehicle (EV) high-power pulse charging events
    4. Time-varying demand spikes
    """
    def __init__(self, time_steps: int = 60, dt_seconds: float = 2.0, seed: int = 42):
        self.time_steps = time_steps
        self.dt_seconds = dt_seconds
        self.rng = np.random.default_rng(seed)

    def generate_pv_profile(self, base_cap_kw: float = 500.0) -> np.ndarray:
        """Simulates solar PV with sudden cloud passage transients (up to 75% drop)."""
        t = np.linspace(0, 1, self.time_steps)
        # Baseline diurnal bell curve
        curve = np.sin(np.pi * t)
        profile = base_cap_kw * np.maximum(curve, 0.2)
        
        # Inject cloud shadowing dips between 30% and 60% of timeline
        drop_start = int(self.time_steps * 0.3)
        drop_end = int(self.time_steps * 0.6)
        cloud_factor = 0.25 + 0.1 * np.sin(np.linspace(0, 2 * np.pi, drop_end - drop_start))
        profile[drop_start:drop_end] *= cloud_factor
        
        # High-frequency irradiance noise
        noise = self.rng.normal(0, 0.03 * base_cap_kw, self.time_steps)
        return np.maximum(profile + noise, 0.0)

    def generate_wind_profile(self, base_cap_kw: float = 600.0) -> np.ndarray:
        """Simulates wind turbine output with turbulence and gust ramps."""
        profile = np.ones(self.time_steps) * (0.6 * base_cap_kw)
        # Random walk turbulence
        steps = self.rng.normal(0, 0.05 * base_cap_kw, self.time_steps)
        profile += np.cumsum(steps)
        # Sudden gust between 65% and 85% of timeline
        gust_start = int(self.time_steps * 0.65)
        gust_end = int(self.time_steps * 0.85)
        profile[gust_start:gust_end] += 0.35 * base_cap_kw
        return np.clip(profile, 0.1 * base_cap_kw, 1.2 * base_cap_kw)

    def generate_ev_charging_profile(self, peak_kw: float = 700.0) -> np.ndarray:
        """Simulates multi-vehicle fast charging depot pulse loads (steep di/dt)."""
        profile = np.ones(self.time_steps) * 50.0  # background trickle charge
        # Multi-vehicle simultaneous fast charge session between 20% and 55% of timeline
        charge_start = int(self.time_steps * 0.2)
        charge_end = int(self.time_steps * 0.55)
        # Ramp up
        profile[charge_start:charge_end] = peak_kw
        # Add high-frequency power electronics ripple
        ripple = self.rng.normal(0, 15.0, self.time_steps)
        return np.maximum(profile + ripple, 10.0)

    def get_feeder_transient_scenario(
        self,
        der_nodes: Dict[int, str],
        base_loads: Dict[int, Tuple[float, float]]
    ) -> List[Dict[int, Tuple[float, float]]]:
        """
        Generates net active/reactive power injection for each bus over all time steps:
            P_net = P_gen - P_load
            Q_net = Q_gen - Q_load
        """
        # Synthesize time series for each DER type
        pv_series = self.generate_pv_profile(base_cap_kw=450.0)
        wind_series = self.generate_wind_profile(base_cap_kw=550.0)
        ev_series = self.generate_ev_charging_profile(peak_kw=650.0)
        
        scenario_timeline = []
        for step in range(self.time_steps):
            step_injections = {}
            for bus_id, (base_p, base_q) in base_loads.items():
                p_net = -base_p  # load is negative injection
                q_net = -base_q
                
                # Check DER attached to bus
                if bus_id in der_nodes:
                    der_type = der_nodes[bus_id]
                    if der_type == "pv":
                        p_gen = pv_series[step]
                        p_net += p_gen
                    elif der_type == "wind":
                        p_gen = wind_series[step]
                        p_net += p_gen
                    elif der_type == "ev":
                        p_ev_demand = ev_series[step]
                        p_net -= p_ev_demand  # heavy additional load
                        q_net -= 0.3 * p_ev_demand
                    elif der_type == "bess":
                        # BESS acts as buffer during extreme solar drops
                        if pv_series[step] < 200.0:
                            p_net += 180.0  # discharge support
                        else:
                            p_net -= 80.0   # recharge
                
                step_injections[bus_id] = (p_net, q_net)
            scenario_timeline.append(step_injections)
            
        return scenario_timeline
