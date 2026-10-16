"""
Custom Microgrid Generator for user-specified topologies.

Generates physically valid, connected, radial distribution microgrids with:
- Configurable component count (10 to 100 buses)
- User-specified mix of DER nodes (Solar PV, Wind, Battery BESS, EV Fast Charging)
- User-specified number of normally open tie lines (switches)
- Exactly 1 substation (slack bus at Bus 1)
- Guaranteed connected spanning tree in base configuration (N - 1 active lines)
- Realistic physical line parameters (R, X, ampacity, thermal mass, thermal resistance)
- Aesthetic 2D coordinates for network diagram visualization
"""
from __future__ import annotations

import networkx as nx
import numpy as np
from typing import Dict, List, Optional, Tuple

from .ieee_feeder_loader import DistributionGrid


def generate_custom_grid(
    n_components: int = 30,
    n_solar: int = 3,
    n_wind: int = 2,
    n_battery: int = 2,
    n_ev: int = 2,
    n_ties: int = 5,
    seed: int = 42,
    v_base_kv: float = 12.66,
    s_base_mva: float = 10.0,
) -> DistributionGrid:
    """
    Constructs a valid reconfigurable distribution microgrid.

    Parameters:
        n_components: Total number of buses (nodes), including 1 substation (slack bus).
        n_solar: Number of Solar PV generation nodes.
        n_wind: Number of Wind turbine nodes.
        n_battery: Number of Battery Energy Storage System (BESS) nodes.
        n_ev: Number of EV fast charging depot nodes.
        n_ties: Number of normally open tie-line switches.
        seed: Random seed for deterministic, reproducible generation.
        v_base_kv: Nominal line-to-line voltage base (kV).
        s_base_mva: System three-phase MVA base.

    Returns:
        DistributionGrid with fully initialized buses, branches, tie switches, DER allocations,
        and aesthetic 2D visual layout coordinates.
    """
    if n_components < 4:
        raise ValueError(f"Custom grid must have at least 4 components (got {n_components}).")

    rng = np.random.default_rng(seed)
    grid = DistributionGrid(
        f"Custom_Microgrid_{n_components}",
        v_base_kv=v_base_kv,
        s_base_mva=s_base_mva,
    )

    # 1. Bus 1 is always the Substation (slack bus)
    grid.add_bus(1, p_kw=0.0, q_kvar=0.0, is_substation=True)
    positions: Dict[int, Tuple[float, float]] = {1: (0.0, 0.0)}

    # 2. Assign DER node roles to buses 2..N
    available_buses = list(range(2, n_components + 1))
    rng.shuffle(available_buses)

    der_requests = [
        ("pv", max(0, int(n_solar))),
        ("wind", max(0, int(n_wind))),
        ("bess", max(0, int(n_battery))),
        ("ev", max(0, int(n_ev))),
    ]
    der_assignment: Dict[int, str] = {}
    idx = 0
    for der_type, count in der_requests:
        for _ in range(count):
            if idx < len(available_buses):
                der_assignment[available_buses[idx]] = der_type
                idx += 1

    # 3. Add load buses with realistic demand profiles
    # Loads scaled moderately so long feeders maintain voltage within ANSI range
    for b in range(2, n_components + 1):
        der = der_assignment.get(b)
        if der == "ev":
            p = float(rng.uniform(60.0, 110.0))
            q = float(rng.uniform(20.0, 45.0))
        elif der in ("pv", "wind"):
            p = float(rng.uniform(15.0, 30.0))
            q = float(rng.uniform(5.0, 12.0))
        elif der == "bess":
            p = float(rng.uniform(20.0, 40.0))
            q = float(rng.uniform(5.0, 15.0))
        else:
            p = float(rng.uniform(25.0, 55.0))
            q = float(rng.uniform(10.0, 22.0))
        grid.add_bus(b, p_kw=p, q_kvar=q, is_substation=False)

    for b, der in der_assignment.items():
        grid.der_nodes[b] = der

    # 4. Construct tree topology with main trunk + laterals
    # Main trunk length scales with feeder size
    n_trunk = max(3, min(8, n_components // 4))
    trunk = list(range(1, n_trunk + 1))
    edge_idx = 0

    # Main trunk lines along the central horizontal spine
    for i in range(1, n_trunk):
        u, v = trunk[i - 1], trunk[i]
        r = float(rng.uniform(0.10, 0.16))
        x = r * 0.5
        grid.add_branch(edge_idx, u, v, r_ohm=r, x_ohm=x, i_max=450.0, is_tie=False)
        positions[v] = (float(i * 1.8), 0.0)
        edge_idx += 1

    # Laterals branching north (+y) and south (-y) from trunk nodes
    curr_bus = n_trunk + 1
    trunk_attachments = trunk[1:]
    side = 1
    lateral_ends: List[int] = []

    while curr_bus <= n_components:
        t_node = trunk_attachments[(curr_bus - n_trunk - 1) % len(trunk_attachments)]
        tx, ty = positions[t_node]
        side = -side if (curr_bus % 2 == 0) else side
        lat_len = min(int(rng.integers(2, 5)), n_components - curr_bus + 1)
        prev_node = t_node

        for step in range(lat_len):
            b = curr_bus
            r = float(rng.uniform(0.18, 0.32))
            x = r * 0.5
            grid.add_branch(edge_idx, prev_node, b, r_ohm=r, x_ohm=x, i_max=350.0, is_tie=False)
            x_coord = tx + (step + 1) * 0.35 + float(rng.uniform(-0.1, 0.1))
            y_coord = ty + side * (step + 1) * 1.4 + float(rng.uniform(-0.15, 0.15))
            positions[b] = (x_coord, y_coord)
            edge_idx += 1
            prev_node = b
            curr_bus += 1
        lateral_ends.append(prev_node)

    # 5. Add tie lines (normally open switches) forming loops across distinct laterals/trunk
    tie_count = 0
    attempts = 0
    max_ties = min(n_ties, max(1, (n_components * (n_components - 1)) // 2 - (n_components - 1)))
    nodes_pool = list(range(2, n_components + 1))

    while tie_count < max_ties and attempts < 400:
        attempts += 1
        # Prefer connecting lateral endpoints for meaningful reconfiguration loops
        if lateral_ends and len(lateral_ends) >= 2 and rng.random() < 0.7:
            u = int(rng.choice(lateral_ends))
            v = int(rng.choice(nodes_pool))
        else:
            u = int(rng.choice(nodes_pool))
            v = int(rng.choice(nodes_pool))

        if u != v and not grid.graph.has_edge(u, v):
            dist = nx.shortest_path_length(grid.graph, u, v)
            if dist >= 3:
                r_tie = float(rng.uniform(0.25, 0.50))
                x_tie = r_tie * 0.5
                grid.add_branch(edge_idx, u, v, r_ohm=r_tie, x_ohm=x_tie, i_max=350.0, is_tie=True)
                edge_idx += 1
                tie_count += 1

    # Store layout positions directly on grid for rendering
    grid.layout_positions = positions
    return grid
