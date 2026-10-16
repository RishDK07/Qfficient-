import os
import time
import dimod
from typing import Dict, Tuple, Any

class DWaveQPURunner:
    """
    Submits Thermodynamic QUBO instances to D-Wave Advantage QPU or Leap Hybrid Sampler
    using the D-Wave Ocean SDK, with automatic local simulated annealing fallback.
    """
    def __init__(self, token: str = None, use_cloud: bool = False):
        self.token = token or os.environ.get("DWAVE_API_TOKEN", "")
        self.use_cloud = use_cloud and bool(self.token)

    def solve(
        self,
        bqm: dimod.BinaryQuadraticModel,
        num_reads: int = 500
    ) -> Tuple[Dict[int, int], float, float, str]:
        """
        Executes sampling on D-Wave Advantage QPU (if credentials available)
        or high-performance local simulated annealing fallback.
        """
        start_time = time.perf_counter()
        solver_name = "Local Neal Sampler"

        if self.use_cloud:
            try:
                from dwave.system import LeapHybridSampler
                sampler = LeapHybridSampler(token=self.token)
                response = sampler.sample(bqm)
                solver_name = "D-Wave Leap Hybrid QPU"
            except Exception as e:
                import neal
                sampler = neal.SimulatedAnnealingSampler()
                response = sampler.sample(bqm, num_reads=num_reads)
                solver_name = f"Local Fallback ({str(e)[:30]})"
        else:
            import neal
            sampler = neal.SimulatedAnnealingSampler()
            response = sampler.sample(bqm, num_reads=num_reads)
            solver_name = "D-Wave Neal (Simulated Annealing)"

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        best_record = response.first
        raw_sample = best_record.sample
        best_energy = float(best_record.energy)

        parsed_sample = {}
        for var_name, val in raw_sample.items():
            if var_name.startswith("x_"):
                edge_idx = int(var_name.split("_")[1])
                parsed_sample[edge_idx] = int(val)

        return parsed_sample, best_energy, elapsed_ms, solver_name
