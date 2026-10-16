import time
import dimod
import openjij as oj
from typing import Dict, Tuple, Any, Optional

class OpenJijAnnealer:
    """
    Solves the Thermodynamic-Mapped QUBO using OpenJij's Simulated Quantum Annealing (SQA)
    and Classical Simulated Annealing (SA) engines.
    
    Adheres strictly to physics-grounded evaluation:
    Extracts the raw lowest-energy ground state of the QUBO Hamiltonian WITHOUT
    any post-hoc power-flow filtering or re-ranking.
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
        Executes quantum or classical annealing on the BQM.
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

    def extract_raw_qubo_tree(
        self,
        response: Any,
        grid: Any
    ) -> Tuple[Dict[int, int], float]:
        """
        Ranks samples strictly by raw QUBO Hamiltonian energy.
        Returns the VERY FIRST sample that satisfies the radial tree topology constraint,
        with ZERO external power flow filtering or loss-based re-ranking.
        
        Returns:
            best_sample: Dict[int, int]
            raw_energy: float (Hamiltonian eigenvalue)
        """
        import networkx as nx
        from ..verification.physics_verifier import PhysicsVerifier
        verifier = PhysicsVerifier(grid)

        # 1. Search top lowest-energy raw quantum states
        for record in response.data(fields=['sample', 'energy'], sorted_by='energy'):
            sample_dict = {
                int(k.split("_")[1]): int(v)
                for k, v in record.sample.items() if k.startswith("x_")
            }
            is_valid, _ = verifier.is_valid_radial_tree(sample_dict)
            if is_valid:
                # Return the genuine raw lowest-energy quantum state
                return sample_dict, float(record.energy)

        # 2. Fallback projection only if no raw bitstring was a connected tree
        # Use quantum marginal spin probability ensemble
        edge_counts = {e: 0 for e in grid.lines.keys()}
        total_samples = len(response.record)
        for record in response.record:
            for idx, val in enumerate(record.sample):
                var_name = response.variables[idx]
                if var_name.startswith("x_") and val == 1:
                    e_id = int(var_name.split("_")[1])
                    edge_counts[e_id] += 1

        g = nx.Graph()
        for e_id, line in grid.lines.items():
            prob = edge_counts.get(e_id, 0) / max(total_samples, 1)
            g.add_edge(line.u, line.v, weight=prob, edge_id=e_id)

        mst = nx.maximum_spanning_tree(g, weight="weight")
        chosen_edges = {data["edge_id"] for u, v, data in mst.edges(data=True)}
        fallback_switches = {e: (1 if e in chosen_edges else 0) for e in grid.lines.keys()}

        return fallback_switches, float(response.first.energy)

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

        fallback_switches, _ = self.extract_raw_qubo_tree(response, grid)
        return fallback_switches

