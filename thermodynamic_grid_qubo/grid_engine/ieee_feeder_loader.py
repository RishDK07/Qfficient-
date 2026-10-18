import networkx as nx
from typing import Dict, List, Tuple
from .thermal_dynamics import ThermodynamicLineModel

class DistributionGrid:
    """Represents a switchable distribution grid with thermodynamic line models."""
    def __init__(self, name: str, v_base_kv: float = 12.66, s_base_mva: float = 10.0):
        self.name = name
        self.v_base_kv = v_base_kv
        self.s_base_mva = s_base_mva
        self.v_base_v = v_base_kv * 1000.0
        self.i_base_a = (s_base_mva * 1e6) / (np_sqrt3 := 1.7320508 * self.v_base_v)
        self.z_base_ohm = (self.v_base_v ** 2) / (s_base_mva * 1e6)

        self.graph = nx.Graph()
        self.substations = []
        self.bus_loads: Dict[int, Tuple[float, float]] = {}  # bus_id -> (P_kW, Q_kVAR)
        self.lines: Dict[int, ThermodynamicLineModel] = {}   # edge_id -> ThermodynamicLineModel
        self.tie_switches: List[int] = []                    # list of edge_ids that are tie lines
        self.der_nodes: Dict[int, str] = {}                  # bus_id -> der_type ('pv', 'wind', 'ev', 'bess')

    def add_bus(self, bus_id: int, p_kw: float = 0.0, q_kvar: float = 0.0, is_substation: bool = False):
        self.graph.add_node(bus_id, p_kw=p_kw, q_kvar=q_kvar, is_substation=is_substation)
        self.bus_loads[bus_id] = (p_kw, q_kvar)
        if is_substation and bus_id not in self.substations:
            self.substations.append(bus_id)

    def add_branch(
        self,
        edge_id: int,
        u: int,
        v: int,
        r_ohm: float,
        x_ohm: float,
        i_max: float = 400.0,
        is_tie: bool = False,
        c_th: float = 250000.0,
        theta_th: float = 0.003
    ):
        model = ThermodynamicLineModel(
            edge_id=edge_id,
            u=u,
            v=v,
            r0=r_ohm,
            x0=x_ohm,
            c_th=c_th,
            theta_th=theta_th,
            i_max=i_max
        )
        self.lines[edge_id] = model
        self.graph.add_edge(u, v, edge_id=edge_id, is_tie=is_tie, model=model)
        if is_tie:
            self.tie_switches.append(edge_id)

    def get_edge_list(self) -> List[Tuple[int, int]]:
        """Returns ordered list of (u, v) pairs corresponding to edge_id 0..N-1."""
        return [(self.lines[i].u, self.lines[i].v) for i in sorted(self.lines.keys())]

    def reset_all_thermal_states(self):
        for line in self.lines.values():
            line.reset_thermal_state()


class IEEEFeederLoader:
    """Standard IEEE Distribution Feeder Benchmark Loader."""
    
    @staticmethod
    def load_ieee33() -> DistributionGrid:
        """
        Builds the standard IEEE 33-Bus distribution test system with 5 tie-switches.
        Total: 33 buses, 32 sectionalizing lines (normally closed), 5 tie lines (normally open).
        """
        grid = DistributionGrid("IEEE_33_Bus", v_base_kv=12.66, s_base_mva=10.0)
        
        # Standard IEEE 33-bus line and load data [from_bus, to_bus, r_ohm, x_ohm, P_kW, Q_kVAR]
        raw_branches = [
            (1, 2, 0.0922, 0.0477, 100.0, 60.0),
            (2, 3, 0.4930, 0.2511, 90.0, 40.0),
            (3, 4, 0.3660, 0.1864, 120.0, 80.0),
            (4, 5, 0.3811, 0.1941, 60.0, 30.0),
            (5, 6, 0.8190, 0.7070, 60.0, 20.0),
            (6, 7, 0.1872, 0.6188, 200.0, 100.0),
            (7, 8, 1.7114, 1.2351, 200.0, 100.0),
            (8, 9, 1.0300, 0.7400, 60.0, 20.0),
            (9, 10, 1.0400, 0.7400, 60.0, 20.0),
            (10, 11, 0.1966, 0.0650, 45.0, 30.0),
            (11, 12, 0.3744, 0.1238, 60.0, 35.0),
            (12, 13, 1.4680, 1.1550, 60.0, 35.0),
            (13, 14, 0.5416, 0.7129, 120.0, 80.0),
            (14, 15, 0.5910, 0.5260, 60.0, 10.0),
            (15, 16, 0.7463, 0.5450, 60.0, 20.0),
            (16, 17, 1.2890, 1.7210, 60.0, 20.0),
            (17, 18, 0.7320, 0.5740, 90.0, 40.0),
            (2, 19, 0.1640, 0.1565, 90.0, 40.0),
            (19, 20, 1.5042, 1.3554, 90.0, 40.0),
            (20, 21, 0.4095, 0.4784, 90.0, 40.0),
            (21, 22, 0.7089, 0.9373, 90.0, 40.0),
            (3, 23, 0.4512, 0.3083, 90.0, 50.0),
            (23, 24, 0.8980, 0.7091, 420.0, 200.0),
            (24, 25, 0.8960, 0.7011, 420.0, 200.0),
            (6, 26, 0.2030, 0.1034, 60.0, 25.0),
            (26, 27, 0.2842, 0.1447, 60.0, 25.0),
            (27, 28, 1.0590, 0.9337, 60.0, 20.0),
            (28, 29, 0.8042, 0.7006, 120.0, 70.0),
            (29, 30, 0.5075, 0.2585, 200.0, 600.0),
            (30, 31, 0.9744, 0.9630, 150.0, 70.0),
            (31, 32, 0.3105, 0.3619, 210.0, 100.0),
            (32, 33, 0.3410, 0.5302, 60.0, 40.0)
        ]

        # Tie lines (switches 33-37 in 0-indexed terminology: 32..36)
        raw_tie_lines = [
            (8, 21, 2.0000, 2.0000),   # Tie 1: switch connecting bus 8 to 21
            (9, 15, 2.0000, 2.0000),   # Tie 2: switch connecting bus 9 to 15
            (12, 22, 2.0000, 2.0000),  # Tie 3: switch connecting bus 12 to 22
            (18, 33, 0.5000, 0.5000),  # Tie 4: switch connecting bus 18 to 33
            (25, 29, 0.5000, 0.5000),  # Tie 5: switch connecting bus 25 to 29
        ]

        # Add Substation (Bus 1)
        grid.add_bus(1, p_kw=0.0, q_kvar=0.0, is_substation=True)

        edge_idx = 0
        for from_b, to_b, r, x, p, q in raw_branches:
            if to_b not in grid.bus_loads:
                grid.add_bus(to_b, p_kw=p, q_kvar=q, is_substation=False)
            grid.add_branch(edge_idx, from_b, to_b, r_ohm=r, x_ohm=x, is_tie=False, i_max=350.0)
            edge_idx += 1

        for from_b, to_b, r, x in raw_tie_lines:
            grid.add_branch(edge_idx, from_b, to_b, r_ohm=r, x_ohm=x, is_tie=True, i_max=350.0)
            edge_idx += 1

        # Designate strategic DER injection nodes
        grid.der_nodes[14] = "pv"    # Solar PV Farm on feeder 1
        grid.der_nodes[18] = "wind"  # Wind Turbine at end of lateral
        grid.der_nodes[22] = "ev"    # Fast EV Charging Depot
        grid.der_nodes[32] = "bess"  # Community Battery Storage
        grid.der_nodes[25] = "pv"    # Commercial Rooftop PV Cluster

        return grid

    @staticmethod
    def load_microgrid_feeder() -> DistributionGrid:
        """
        Compact 14-bus reconfigurable microgrid testbed with 16 branches (3 loops)
        ideal for granular quantum state analysis and swift verification.
        """
        grid = DistributionGrid("Microgrid_14_Bus", v_base_kv=12.66, s_base_mva=5.0)
        grid.add_bus(1, p_kw=0.0, q_kvar=0.0, is_substation=True)
        
        # 13 load buses
        loads = {
            2: (120, 60), 3: (180, 90), 4: (100, 50), 5: (150, 70),
            6: (200, 100), 7: (80, 40), 8: (140, 60), 9: (90, 45),
            10: (110, 55), 11: (160, 80), 12: (130, 65), 13: (90, 40), 14: (170, 85)
        }
        for b, (p, q) in loads.items():
            grid.add_bus(b, p_kw=p, q_kvar=q)

        # 13 radial lines + 3 tie switches = 16 branches
        branches = [
            (1, 2, 0.15, 0.08, False),
            (2, 3, 0.22, 0.11, False),
            (3, 4, 0.18, 0.09, False),
            (4, 5, 0.25, 0.12, False),
            (2, 6, 0.30, 0.15, False),
            (6, 7, 0.20, 0.10, False),
            (7, 8, 0.19, 0.09, False),
            (1, 9, 0.24, 0.12, False),
            (9, 10, 0.28, 0.14, False),
            (10, 11, 0.17, 0.08, False),
            (9, 12, 0.21, 0.10, False),
            (12, 13, 0.16, 0.08, False),
            (13, 14, 0.22, 0.11, False),
            # Tie lines (switches)
            (5, 8, 0.35, 0.18, True),
            (8, 11, 0.40, 0.20, True),
            (11, 14, 0.38, 0.19, True),
        ]

        for idx, (u, v, r, x, is_tie) in enumerate(branches):
            grid.add_branch(idx, u, v, r_ohm=r, x_ohm=x, is_tie=is_tie, i_max=300.0)

        grid.der_nodes[5] = "pv"
        grid.der_nodes[8] = "ev"
        grid.der_nodes[14] = "wind"
        grid.der_nodes[11] = "bess"

        return grid

    @staticmethod
    def load_ieee69() -> DistributionGrid:
        """
        Builds the standard IEEE 69-Bus distribution test system with 5 tie-switches.
        Total: 69 buses, 68 sectionalizing lines (normally closed), 5 tie lines (normally open).
        Origin: M. E. Baran and F. F. Wu, 'Optimal capacitor placement on radial distribution systems',
        IEEE Trans. Power Delivery, vol. 4, no. 1, pp. 725-734, Jan 1989.
        Tie switches (69-73): D. Das (2008) / Savic & Walters (1989): (11-43, 13-21, 15-46, 50-59, 27-65).
        """
        from .ieee69_data import RAW_BUSES, RAW_BRANCHES, RAW_TIE_LINES

        grid = DistributionGrid("IEEE_69_Bus", v_base_kv=12.66, s_base_mva=10.0)

        # Bus 1 is the substation slack bus
        for bus_id, p_kw, q_kvar in RAW_BUSES:
            grid.add_bus(bus_id, p_kw=p_kw, q_kvar=q_kvar, is_substation=(bus_id == 1))

        edge_idx = 0
        for from_b, to_b, r, x in RAW_BRANCHES:
            grid.add_branch(edge_idx, from_b, to_b, r_ohm=r, x_ohm=x, is_tie=False, i_max=400.0)
            edge_idx += 1

        for from_b, to_b, r, x in RAW_TIE_LINES:
            grid.add_branch(edge_idx, from_b, to_b, r_ohm=r, x_ohm=x, is_tie=True, i_max=400.0)
            edge_idx += 1

        # Representative DER locations across major laterals
        grid.der_nodes[11] = "pv"
        grid.der_nodes[21] = "ev"
        grid.der_nodes[50] = "pv"
        grid.der_nodes[64] = "bess"

        return grid

