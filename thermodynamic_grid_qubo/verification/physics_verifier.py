import math
import numpy as np
import networkx as nx
from typing import Dict, Tuple, List, Set
from ..grid_engine.ieee_feeder_loader import DistributionGrid

class PhysicsVerifier:
    """
    AC/DC Distribution Power Flow and Physical Feasibility Validator.
    
    Implements:
    1. Graph topology & radiality validation (connectivity, cycle detection).
    2. Backward-Forward Sweep / LinDistFlow for radial distribution microgrids.
    3. Bus voltage magnitude calculation in per-unit (ANSI C84.1 limits: 0.95 - 1.05 p.u.).
    4. Exact branch current calculation (Amperes) and thermal loss determination.
    """
    def __init__(self, grid: DistributionGrid):
        self.grid = grid

    def is_valid_radial_tree(self, switch_states: Dict[int, int]) -> Tuple[bool, str]:
        """Validates if the active switches form a connected radial spanning tree rooted at substation."""
        g = nx.Graph()
        for b in self.grid.graph.nodes:
            g.add_node(b)

        active_edges = 0
        for edge_id, is_active in switch_states.items():
            if is_active == 1:
                line = self.grid.lines[edge_id]
                g.add_edge(line.u, line.v)
                active_edges += 1

        num_buses = len(g.nodes)
        substation = self.grid.substations[0]

        # Check connectivity
        if not nx.is_connected(g):
            num_components = nx.number_connected_components(g)
            return False, f"Disconnected network ({num_components} components)."

        # Check cycle-free tree
        if active_edges != (num_buses - 1):
            return False, f"Non-tree topology: {active_edges} active lines for {num_buses} buses."

        return True, "Valid Radial Tree"

    def solve_power_flow(
        self,
        switch_states: Dict[int, int],
        bus_injections: Dict[int, Tuple[float, float]],
        v_slack_pu: float = 1.00
    ) -> Tuple[bool, Dict[int, float], Dict[int, float], float]:
        """
        Solves LinDistFlow for the active radial network.
        
        Args:
            switch_states: Dict[edge_id -> 0 or 1]
            bus_injections: Dict[bus_id -> (P_net_kW, Q_net_kVAR)]
            v_slack_pu: Slack bus voltage in per-unit (default 1.00)
            
        Returns:
            is_feasible: bool (within ANSI C84.1 voltage tolerances [0.95, 1.05])
            bus_voltages: Dict[bus_id -> voltage in p.u.]
            branch_currents: Dict[edge_id -> current in Amperes]
            total_system_loss_kw: float (active power loss across network in kW)
        """
        # Build directed graph from substation outwards
        g = nx.Graph()
        for b in self.grid.graph.nodes:
            g.add_node(b)

        active_edge_map = {}
        for edge_id, is_active in switch_states.items():
            if is_active == 1:
                line = self.grid.lines[edge_id]
                g.add_edge(line.u, line.v, edge_id=edge_id, line=line)
                active_edge_map[edge_id] = line

        sub = self.grid.substations[0]
        if not nx.is_connected(g) or (len(active_edge_map) != len(g.nodes) - 1):
            # Fallback approximate for invalid graph
            return False, {b: 0.90 for b in g.nodes}, {e: 0.0 for e in self.grid.lines}, 9999.0

        # Create oriented BFS tree from substation
        tree = nx.bfs_tree(g, source=sub)
        
        # 1. Backward Sweep: Aggregate downstream power flows
        # Branch power flow: P_branch = Sum downstream P_load - Sum downstream P_gen
        branch_p_kw = {}
        branch_q_kvar = {}
        branch_currents_a = {e: 0.0 for e in self.grid.lines}

        # Traverse in reverse topological order (leaves to root)
        nodes_ordered = list(nx.topological_sort(tree))
        nodes_reversed = list(reversed(nodes_ordered))

        bus_accum_p = {}
        bus_accum_q = {}
        for node in nodes_reversed:
            p_inj, q_inj = bus_injections.get(node, (0.0, 0.0))
            # Power demanded at this node (load is negative injection)
            p_flow = -p_inj
            q_flow = -q_inj
            
            # Add child branches
            for child in tree.successors(node):
                # find branch connecting node -> child
                edge_data = g.get_edge_data(node, child)
                e_id = edge_data["edge_id"]
                p_flow += branch_p_kw.get(e_id, 0.0)
                q_flow += branch_q_kvar.get(e_id, 0.0)

            # Store for incident parent edge
            parent = list(tree.predecessors(node))
            if parent:
                parent_node = parent[0]
                edge_data = g.get_edge_data(parent_node, node)
                e_id = edge_data["edge_id"]
                branch_p_kw[e_id] = p_flow
                branch_q_kvar[e_id] = q_flow

        # 2. Forward Sweep: Voltage Drops using LinDistFlow
        # v_j^2 = v_i^2 - 2*(r*P + x*Q) / V_base^2
        v_sq = {sub: v_slack_pu ** 2}
        v_pu = {sub: v_slack_pu}

        total_loss_kw = 0.0

        for node in nodes_ordered:
            v_i_sq = v_sq[node]
            v_i = math.sqrt(max(v_i_sq, 0.5))
            
            for child in tree.successors(node):
                edge_data = g.get_edge_data(node, child)
                e_id = edge_data["edge_id"]
                line = edge_data["line"]

                p_f_kw = branch_p_kw.get(e_id, 0.0)
                q_f_kvar = branch_q_kvar.get(e_id, 0.0)

                # Convert to per-unit power on base
                p_pu = (p_f_kw * 1e3) / (self.grid.s_base_mva * 1e6)
                q_pu = (q_f_kvar * 1e3) / (self.grid.s_base_mva * 1e6)
                r_pu = line.resistance() / self.grid.z_base_ohm
                x_pu = line.x0 / self.grid.z_base_ohm

                # LinDistFlow voltage drop: v_j^2 = v_i^2 - 2*(r*P + x*Q)
                delta_v_sq = 2.0 * (r_pu * p_pu + x_pu * q_pu)
                v_j_sq = max(v_i_sq - delta_v_sq, 0.64)  # clip minimum to 0.8 pu
                v_sq[child] = v_j_sq
                v_j = math.sqrt(v_j_sq)
                v_pu[child] = v_j

                # Branch Current (Amperes): S = sqrt(3)*V*I => I = S / (sqrt(3)*V)
                s_va = math.sqrt((p_f_kw * 1e3) ** 2 + (q_f_kvar * 1e3) ** 2)
                v_actual_v = v_j * self.grid.v_base_v
                i_a = s_va / (math.sqrt(3.0) * max(v_actual_v, 1.0))
                branch_currents_a[e_id] = i_a

                # 3-phase Ohmic power loss in kW: 3 * I^2 * R(T)
                loss_w = 3.0 * (i_a ** 2) * line.resistance()
                total_loss_kw += (loss_w / 1000.0)

        # Check ANSI C84.1 voltage compliance: [0.95, 1.05]
        min_v = min(v_pu.values())
        max_v = max(v_pu.values())
        voltage_compliant = (min_v >= 0.95) and (max_v <= 1.05)

        return voltage_compliant, v_pu, branch_currents_a, total_loss_kw

    def solve_ac_power_flow(
        self,
        switch_states: Dict[int, int],
        bus_injections: Dict[int, Tuple[float, float]],
        v_slack_pu: float = 1.00,
        max_iter: int = 20,
        tol: float = 1e-5,
    ) -> Tuple[bool, Dict[int, float], Dict[int, float], float]:
        """
        Solves exact non-linear AC DistFlow equations (Baran & Wu, 1989) with branch loss feedback.
        Yields canonical ~210.74 kW (~211 kW) base loss on nominal IEEE 33 network.
        """
        g = nx.Graph()
        for b in self.grid.graph.nodes:
            g.add_node(b)

        active_edge_map = {}
        for edge_id, is_active in switch_states.items():
            if is_active == 1:
                line = self.grid.lines[edge_id]
                g.add_edge(line.u, line.v, edge_id=edge_id, line=line)
                active_edge_map[edge_id] = line

        sub = self.grid.substations[0]
        if not nx.is_connected(g) or (len(active_edge_map) != len(g.nodes) - 1):
            return False, {b: 0.90 for b in g.nodes}, {e: 0.0 for e in self.grid.lines}, 9999.0

        tree = nx.bfs_tree(g, source=sub)
        nodes_ordered = list(nx.topological_sort(tree))
        nodes_reversed = list(reversed(nodes_ordered))

        v_sq = {b: (v_slack_pu ** 2) for b in g.nodes}
        branch_p_kw = {}
        branch_q_kvar = {}
        branch_loss_p = {e: 0.0 for e in self.grid.lines}
        branch_loss_q = {e: 0.0 for e in self.grid.lines}

        for _ in range(max_iter):
            branch_p_kw.clear()
            branch_q_kvar.clear()
            for node in nodes_reversed:
                p_inj, q_inj = bus_injections.get(node, (0.0, 0.0))
                p_flow = -p_inj
                q_flow = -q_inj

                for child in tree.successors(node):
                    edge_data = g.get_edge_data(node, child)
                    e_id = edge_data["edge_id"]
                    p_flow += branch_p_kw.get(e_id, 0.0) + branch_loss_p.get(e_id, 0.0)
                    q_flow += branch_q_kvar.get(e_id, 0.0) + branch_loss_q.get(e_id, 0.0)

                parent = list(tree.predecessors(node))
                if parent:
                    p_node = parent[0]
                    edge_data = g.get_edge_data(p_node, node)
                    e_id = edge_data["edge_id"]
                    line = edge_data["line"]
                    branch_p_kw[e_id] = p_flow
                    branch_q_kvar[e_id] = q_flow

                    # Compute branch loss
                    v_p_sq = max(v_sq[p_node], 0.25)
                    s_sq_va = ((p_flow * 1e3) ** 2 + (q_flow * 1e3) ** 2)
                    v_act_sq = v_p_sq * (self.grid.v_base_v ** 2)
                    i_sq = s_sq_va / (3.0 * max(v_act_sq, 1.0))
                    r_ohm = line.resistance()
                    x_ohm = line.x0
                    branch_loss_p[e_id] = (3.0 * i_sq * r_ohm) / 1000.0
                    branch_loss_q[e_id] = (3.0 * i_sq * x_ohm) / 1000.0

            # Forward sweep
            v_sq_prev = dict(v_sq)
            for node in nodes_ordered:
                v_i_sq = v_sq[node]
                for child in tree.successors(node):
                    edge_data = g.get_edge_data(node, child)
                    e_id = edge_data["edge_id"]
                    line = edge_data["line"]
                    p_f_kw = branch_p_kw.get(e_id, 0.0)
                    q_f_kvar = branch_q_kvar.get(e_id, 0.0)
                    p_pu = (p_f_kw * 1e3) / (self.grid.s_base_mva * 1e6)
                    q_pu = (q_f_kvar * 1e3) / (self.grid.s_base_mva * 1e6)
                    r_pu = line.resistance() / self.grid.z_base_ohm
                    x_pu = line.x0 / self.grid.z_base_ohm
                    i_sq_pu = (p_pu ** 2 + q_pu ** 2) / max(v_i_sq, 0.1)

                    drop = 2.0 * (r_pu * p_pu + x_pu * q_pu) - (r_pu ** 2 + x_pu ** 2) * i_sq_pu
                    v_sq[child] = max(v_i_sq - drop, 0.50)

            diff = max(abs(v_sq[b] - v_sq_prev[b]) for b in g.nodes)
            if diff < tol:
                break

        v_pu = {b: math.sqrt(v_sq[b]) for b in g.nodes}
        branch_currents_a = {e: 0.0 for e in self.grid.lines}
        total_loss_kw = sum(branch_loss_p.values())

        for edge_id in active_edge_map:
            line = self.grid.lines[edge_id]
            r = line.resistance()
            if r > 1e-6:
                branch_currents_a[edge_id] = math.sqrt(max(0.0, (branch_loss_p[edge_id] * 1000.0) / (3.0 * r)))

        min_v = min(v_pu.values())
        max_v = max(v_pu.values())
        voltage_compliant = (min_v >= 0.95) and (max_v <= 1.05)
        return voltage_compliant, v_pu, branch_currents_a, total_loss_kw
