import networkx as nx
from typing import Dict, List, Tuple
from ..grid_engine.ieee_feeder_loader import DistributionGrid

class ClassicalBaselineSolver:
    """
    Classical Grid Routing Baseline:
    Implements standard Minimum-Ohmic / Minimum-Resistance spanning tree configuration.
    Critically, this classical algorithm assumes STATIC nominal resistance (R_0), completely
    ignoring dynamic conductor temperatures, thermal runaway, and thermodynamic entropy.
    """
    def __init__(self, grid: DistributionGrid):
        self.grid = grid

    def solve(self) -> Dict[int, int]:
        """
        Computes the classical minimum resistance radial configuration.
        Returns a dictionary mapping edge_id -> 0 (open) or 1 (closed).
        """
        # Create weighted graph using nominal resistance r0 only
        g = nx.Graph()
        for edge_id, line in self.grid.lines.items():
            g.add_edge(line.u, line.v, weight=line.r0, edge_id=edge_id)

        # Minimum Spanning Tree based on static Ohmic resistance
        mst_edges = nx.minimum_spanning_edges(g, algorithm="kruskal", data=True)
        active_edge_ids = set()
        for u, v, data in mst_edges:
            active_edge_ids.add(data["edge_id"])

        # Formulate full switch state vector
        switch_states = {}
        for edge_id in self.grid.lines.keys():
            switch_states[edge_id] = 1 if edge_id in active_edge_ids else 0

        return switch_states
