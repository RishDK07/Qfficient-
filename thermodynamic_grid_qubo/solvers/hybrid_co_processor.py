"""
Symbiotic Hybrid Quantum-Classical Co-Processor (Option B).

Combines:
1. Thermodynamic QUBO mapping with negative meshed-flow linear weights.
2. Quantum / SQA global multi-loop combinatorial candidate generation.
3. Fast cycle-basis matroid projection (Kruskal Union-Find) guaranteeing 100% radiality.
4. Classical multi-basin tournament ranking and local branch-exchange polishing.

This architecture solves the fundamental scaling challenge for large distribution
networks (where tree cardinality tau(G) reaches 10^12 - 10^15):
- Pure classical 1-opt branch exchange gets trapped in local minima.
- Pure quantum annealing suffers from analog noise and non-local I^2*R flow rerouting.
- The symbiotic hybrid co-processor uses quantum tunneling to discover promising global basins,
  matroid repair to guarantee physical topology, and classical DistFlow to polish the local minimum.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np

from ..grid_engine.ieee_feeder_loader import DistributionGrid
from ..verification.physics_verifier import PhysicsVerifier
from ..solvers.exact_classical_solver import ExactClassicalSolver
from ..solvers.numpy_annealer import NumpyAnnealer
from ..solvers.openjij_annealer import OpenJijAnnealer
from ..qubo_engine.entropy_calculator import mesh_branch_currents
from ..qubo_engine.qubo_builder import ThermodynamicQUBOBuilder
from ..qubo_engine.penalty_tuner import PenaltyTuner


class HybridCoProcessor:
    """
    Option B: Symbiotic Hybrid Quantum-Classical Optimization Engine.
    """

    def __init__(
        self,
        grid: DistributionGrid,
        num_reads: int = 100,
        sweeps: int = 120,
        top_basins: int = 3,
        polish_iterations: int = 5,
        use_sqa: bool = False,
        seed: int = 42,
    ):
        self.grid = grid
        self.num_reads = num_reads
        self.sweeps = sweeps
        self.top_basins = top_basins
        self.polish_iterations = polish_iterations
        self.use_sqa = use_sqa
        self.seed = seed

        self.verifier = PhysicsVerifier(grid)
        self.exact_solver = ExactClassicalSolver(grid)
        self.tuner = PenaltyTuner()

        self.edge_ids = sorted(grid.lines.keys())
        self.num_buses = len(grid.graph.nodes)
        self.edges = grid.get_edge_list()

        if use_sqa:
            self.annealer = OpenJijAnnealer(use_sqa=True)
        else:
            self.annealer = NumpyAnnealer(sweeps=sweeps, seed=seed)

    def _build_qubo_model(
        self,
        injections: Dict[int, Tuple[float, float]],
        temps_dict: Optional[Dict[int, float]] = None,
        prev_switches: Optional[Dict[int, int]] = None,
    ) -> Tuple[Any, Dict[int, float]]:
        """Builds calibrated Thermodynamic QUBO matrix with mesh currents."""
        if temps_dict is None:
            temps_dict = {e: self.grid.lines[e].temp for e in self.edge_ids}

        i_mesh = mesh_branch_currents(self.grid, injections, temps_dict)
        entropy_weights = {
            e: 3.0 * (i_mesh.get(e, 30.0) ** 2) * self.grid.lines[e].resistance() / max(temps_dict.get(e, 298.15), 273.15)
            for e in self.edge_ids
        }

        lambdas = self.tuner.calibrate(entropy_weights, self.num_buses)

        builder = ThermodynamicQUBOBuilder(
            num_buses=self.num_buses,
            edges=self.edges,
            substations=self.grid.substations,
            graph=self.grid.graph,
            lambda_thermo=lambdas["lambda_thermo"],
            lambda_cycle=lambdas["lambda_cycle"],
            lambda_rad=lambdas["lambda_rad"],
            lambda_cap=lambdas["lambda_cap"],
            lambda_sw=lambdas["lambda_sw"],
        )

        line_currents = {i: i_mesh.get(e, 30.0) for i, e in enumerate(self.edge_ids)}
        line_imax = {i: self.grid.lines[e].i_max for i, e in enumerate(self.edge_ids)}
        prev_map = {i: prev_switches.get(e, 1) for i, e in enumerate(self.edge_ids)} if prev_switches else None

        qubo_model = builder.build_model(
            entropy_weights={i: entropy_weights[e] for i, e in enumerate(self.edge_ids)},
            line_currents=line_currents,
            line_i_max=line_imax,
            prev_switch_states=prev_map,
        )
        return qubo_model, entropy_weights

    def _matroid_repair_to_tree(
        self,
        sample_bits: np.ndarray,
        entropy_weights: Dict[int, float],
    ) -> Dict[int, int]:
        """
        Fast Kruskal Matroid Projection (O(M alpha(N))).
        Prioritizes bits selected by quantum annealing, tie-breaking by high entropy weight.
        Guarantees 100% radiality, connectivity, and zero cycles.
        """
        active_indices = set(np.nonzero(sample_bits)[0])
        m = len(self.edge_ids)

        all_e = list(range(m))
        all_e.sort(key=lambda idx: (0 if idx in active_indices else 1, -entropy_weights[self.edge_ids[idx]]))

        uf = nx.utils.UnionFind()
        chosen_edges = set()

        for idx in all_e:
            e_id = self.edge_ids[idx]
            u, v = self.grid.lines[e_id].u, self.grid.lines[e_id].v
            if uf[u] != uf[v]:
                uf.union(u, v)
                chosen_edges.add(e_id)
                if len(chosen_edges) == self.num_buses - 1:
                    break

        return {e: (1 if e in chosen_edges else 0) for e in self.edge_ids}

    def solve(
        self,
        injections: Dict[int, Tuple[float, float]],
        temps_dict: Optional[Dict[int, float]] = None,
        prev_switches: Optional[Dict[int, int]] = None,
    ) -> Tuple[Dict[int, int], float, float, Dict[str, Any]]:
        """
        Executes the Option B Hybrid Quantum-Classical optimization cycle.

        Returns:
            best_switches: Dict[int, int]
            best_loss_kw: float
            elapsed_ms: float
            diagnostics: Dict[str, Any]
        """
        t0 = time.perf_counter()

        # Step 1: Classical baseline seed (guarantees monotonic improvement)
        if prev_switches is not None:
            baseline_seed = dict(prev_switches)
        else:
            baseline_seed, _ = self.exact_solver.solve_unreconfigured_standard()

        # Step 2: Build QUBO and execute global multi-loop quantum sampling
        qubo_model, entropy_weights = self._build_qubo_model(injections, temps_dict, prev_switches)
        t_sample_start = time.perf_counter()

        if self.use_sqa:
            # OpenJij SQA path
            import dimod
            bqm = dimod.BinaryQuadraticModel.from_qubo(qubo_model.Q, offset=qubo_model.offset)
            _, _, sample_ms, resp = self.annealer.solve(bqm, num_reads=self.num_reads)
            samples_matrix = np.array([
                [record.sample.get(f"x_{i}", 0) for i in range(len(self.edge_ids))]
                for record in resp.record
            ])
        else:
            # Vectorized NumPy Annealer path
            samples_matrix, energies, sample_ms = self.annealer.sample(
                qubo_model.Q, num_reads=self.num_reads, offset=qubo_model.offset
            )

        # Step 3: Candidate Reservoir Generation & Matroid Feasibility Projection
        candidate_trees: List[Dict[int, int]] = []
        seen_keys: Set[Tuple[int, ...]] = set()

        def register_candidate(sw_dict: Dict[int, int]):
            key = tuple(sw_dict[e] for e in self.edge_ids)
            if key not in seen_keys:
                seen_keys.add(key)
                is_valid, _ = self.verifier.is_valid_radial_tree(sw_dict)
                if is_valid:
                    candidate_trees.append(sw_dict)

        # Always include baseline seed in the tournament
        register_candidate(baseline_seed)

        # Project top quantum samples
        m = len(self.edge_ids)
        num_candidates_to_project = min(40, len(samples_matrix))
        for r in range(num_candidates_to_project):
            repaired = self._matroid_repair_to_tree(samples_matrix[r, :m], entropy_weights)
            register_candidate(repaired)

        # Step 4: Rapid Physical Screening via LinDistFlow
        scored_candidates: List[Tuple[float, Dict[int, int]]] = []
        for cand in candidate_trees:
            _, v_pu, _, loss_c = self.verifier.solve_power_flow(cand, injections)
            if v_pu is not None and len(v_pu) > 0:
                scored_candidates.append((loss_c, cand))

        scored_candidates.sort(key=lambda x: x[0])

        # Step 5: Symbiotic Multi-Basin Classical Polish
        # Polish top distinct candidate basins using local branch exchange
        best_loss = 1e9
        best_switches = baseline_seed
        polished_count = 0

        basins_to_polish = scored_candidates[: self.top_basins]
        for rank, (cand_loss, cand_sw) in enumerate(basins_to_polish):
            polished_sw, polished_loss, _ = self.exact_solver.solve_exact_loss_minimizer(
                injections,
                max_iterations=self.polish_iterations,
                initial_switches=cand_sw,
            )
            polished_count += 1
            if polished_loss < best_loss:
                best_loss = polished_loss
                best_switches = polished_sw

        total_ms = (time.perf_counter() - t0) * 1000.0

        diagnostics = {
            "total_candidates_generated": len(candidate_trees),
            "feasible_candidates_screened": len(scored_candidates),
            "basins_polished": polished_count,
            "quantum_sample_ms": sample_ms,
            "total_ms": total_ms,
            "best_loss_kw": best_loss,
        }

        return best_switches, best_loss, total_ms, diagnostics
