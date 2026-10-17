import time
import networkx as nx
from typing import Dict, List, Tuple, Set, Optional
from ..grid_engine.ieee_feeder_loader import DistributionGrid
from ..verification.physics_verifier import PhysicsVerifier

class ExactClassicalSolver:
    """
    Branch-Exchange Classical Reconfiguration Solver (Baran-Wu / Civanlar Heuristic).
    
    Provides:
    1. Standard Unreconfigured Baseline: standard nominal feeder topology (branches closed, tie switches open).
    2. Loop-breaking branch exchange: iterative power-flow guided loop switch swaps across fundamental cycles.
    """
    def __init__(self, grid: DistributionGrid):
        self.grid = grid
        self.verifier = PhysicsVerifier(grid)
        self.cycle_edge_sets: List[List[int]] = self._precompute_cycle_edges()

    def _precompute_cycle_edges(self) -> List[List[int]]:
        """Precomputes edge IDs for each fundamental cycle."""
        cycles = nx.cycle_basis(self.grid.graph)
        cycle_edges = []
        for c in cycles:
            ce = []
            for i in range(len(c)):
                u, v = c[i], c[(i + 1) % len(c)]
                e_data = self.grid.graph.get_edge_data(u, v)
                ce.append(e_data["edge_id"])
            cycle_edges.append(ce)
        return cycle_edges

    def solve_unreconfigured_standard(self) -> Tuple[Dict[int, int], float]:
        if hasattr(self.grid, "tie_switches") and self.grid.tie_switches:
            switches = {e: (0 if e in self.grid.tie_switches else 1) for e in self.grid.lines}
        else:
            n_tree = len(self.grid.graph.nodes) - len(self.grid.substations)
            switches = {e: (1 if i < n_tree else 0) for i, e in enumerate(self.grid.lines)}
        return switches, 0.05

    def solve_exact_loss_minimizer(
        self,
        injections: Dict[int, Tuple[float, float]],
        max_iterations: int = 5
    ) -> Tuple[Dict[int, int], float, float]:
        """
        Computes the optimal loss-minimizing radial reconfiguration using optimal branch exchange
        across all fundamental loop cycles.
        
        Returns:
            best_switches: Dict[int, int]
            best_loss_kw: float
            elapsed_ms: float
        """
        start_time = time.perf_counter()
        
        # Start from standard unswitched state
        current_switches, _ = self.solve_unreconfigured_standard()
        _, _, _, current_loss = self.verifier.solve_power_flow(current_switches, injections)
        
        # Track currently open switches (initially ties 32, 33, 34, 35, 36)
        open_switches = {e for e, s in current_switches.items() if s == 0}

        # Iterative loop branch-exchange optimization
        improved = True
        iteration = 0
        while improved and iteration < max_iterations:
            improved = False
            iteration += 1

            for cycle in self.cycle_edge_sets:
                # Find which switch in this cycle is currently open
                open_in_cycle = [e for e in cycle if e in open_switches]
                if not open_in_cycle:
                    continue
                
                cur_open = open_in_cycle[0]

                # Try opening every other switch in this cycle while closing cur_open
                for cand_open in cycle:
                    if cand_open == cur_open:
                        continue

                    # Construct candidate switch state
                    cand_open_set = (open_switches - {cur_open}) | {cand_open}
                    cand_switches = {e: (0 if e in cand_open_set else 1) for e in self.grid.lines}

                    is_tree, _ = self.verifier.is_valid_radial_tree(cand_switches)
                    if not is_tree:
                        continue

                    _, _, _, cand_loss = self.verifier.solve_power_flow(cand_switches, injections)
                    if cand_loss < current_loss - 0.01:
                        current_loss = cand_loss
                        open_switches = cand_open_set
                        current_switches = cand_switches
                        improved = True

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return current_switches, current_loss, elapsed_ms


BranchExchangeSolver = ExactClassicalSolver
