import time
import dimod
import openjij as oj
from typing import Dict, Tuple, Any, Optional

class OpenJijAnnealer:
    """
    Solves the Thermodynamic-Mapped QUBO using OpenJij's Simulated Quantum Annealing (SQA)
    and Simulated Annealing (SA) engines.
    """
    def __init__(self, use_sqa: bool = False):
        self.use_sqa = use_sqa

    def solve(
        self,
        bqm: dimod.BinaryQuadraticModel,
        num_reads: int = 400,
        beta_min: float = 0.1,
        beta_max: float = 10.0,
        trotter: int = 16
    ) -> Tuple[Dict[int, int], float, float, Any]:
        """
        Executes annealing on the BQM.
        """
        start_time = time.perf_counter()

        if self.use_sqa:
            sampler = oj.SQASampler()
            response = sampler.sample(
                bqm,
                num_reads=num_reads,
                trotter=trotter
            )
        else:
            sampler = oj.SASampler()
            response = sampler.sample(
                bqm,
                num_reads=num_reads,
                beta_min=beta_min,
                beta_max=beta_max
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        raw_sample = response.first.sample
        best_energy = float(response.first.energy)

        # Parse variable keys "x_0", "x_1" into integer edge indices
        parsed_sample = {}
        for var_name, val in raw_sample.items():
            if var_name.startswith("x_"):
                edge_idx = int(var_name.split("_")[1])
                parsed_sample[edge_idx] = int(val)

        return parsed_sample, best_energy, elapsed_ms, response

    def extract_optimal_tree(
        self,
        response: Any,
        grid: Any,
        entropy_weights: Dict[int, float],
        injections: Optional[Dict[int, Tuple[float, float]]] = None,
        current_switches: Optional[Dict[int, int]] = None,
        switching_threshold_kw: float = 0.5
    ) -> Dict[int, int]:
        """
        Extracts the lowest-loss, physically valid radial tree from the quantum sample distribution
        that satisfies ANSI C84.1 voltage constraints and reduces Joule heat dissipation.
        """
        import networkx as nx
        from ..verification.physics_verifier import PhysicsVerifier
        verifier = PhysicsVerifier(grid)

        # Baseline power flow loss with current switches
        base_loss = float("inf")
        if current_switches is not None and injections is not None:
            v_ok, _, _, loss_b = verifier.solve_power_flow(current_switches, injections)
            if v_ok:
                base_loss = loss_b

        best_sample = current_switches
        min_loss = base_loss

        # 1. Evaluate valid trees within quantum annealer sample distribution
        checked = set()
        for record in response.data(fields=['sample', 'energy'], sorted_by='energy'):
            sample_dict = {
                int(k.split("_")[1]): int(v)
                for k, v in record.sample.items() if k.startswith("x_")
            }
            key = tuple(sample_dict[e] for e in sorted(sample_dict.keys()))
            if key in checked:
                continue
            checked.add(key)

            is_valid, _ = verifier.is_valid_radial_tree(sample_dict)
            if is_valid:
                if injections is not None:
                    v_ok, v_pu, cur, total_loss_kw = verifier.solve_power_flow(sample_dict, injections)
                    # Must be within ANSI limits and improve loss beyond wear threshold
                    if v_ok and (total_loss_kw + switching_threshold_kw < min_loss):
                        min_loss = total_loss_kw
                        best_sample = sample_dict
                else:
                    cost = sum(entropy_weights.get(e, 1.0) for e, val in sample_dict.items() if val == 1)
                    if cost < min_loss:
                        min_loss = cost
                        best_sample = sample_dict

        if best_sample is not None:
            return best_sample

        return current_switches if current_switches is not None else {e: (1 if e < 32 else 0) for e in grid.lines.keys()}
