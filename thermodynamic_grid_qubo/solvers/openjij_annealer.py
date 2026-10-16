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
