import networkx as nx
from typing import Dict, List, Tuple
from ..grid_engine.ieee_feeder_loader import DistributionGrid

class ClassicalBaselineSolver:
    """
    Classical Grid Routing Baseline:
    Implements the standard textbook radial feeder configuration (normally closed distribution
    branches, normally open tie switches).
    """
    def __init__(self, grid: DistributionGrid):
        self.grid = grid

    def solve(self) -> Dict[int, int]:
        """
        Computes the standard textbook radial distribution configuration.
        Returns a dictionary mapping edge_id -> 0 (open tie line) or 1 (closed feeder branch).
        """
        if hasattr(self.grid, "tie_switches") and self.grid.tie_switches:
            return {e: (0 if e in self.grid.tie_switches else 1) for e in self.grid.lines}
        
        n_tree = len(self.grid.graph.nodes) - len(self.grid.substations)
        return {e: (1 if i < n_tree else 0) for i, e in enumerate(self.grid.lines)}

