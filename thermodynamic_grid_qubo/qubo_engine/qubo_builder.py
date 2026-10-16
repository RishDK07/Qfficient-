import dimod
import networkx as nx
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Sequence
import numpy as np


def bounded_binary_coeffs(upper_bound: int) -> List[int]:
    """Generates binary expansion coefficients covering {0, 1, ..., upper_bound}."""
    coeffs = []
    power = 1
    rem = upper_bound
    while rem > 0:
        val = min(power, rem)
        coeffs.append(val)
        rem -= val
        power *= 2
    return coeffs


@dataclass
class QUBOModel:
    names: List[str]
    Q: np.ndarray
    offset: float = 0.0
    n_edges: int = 37

    def energy(self, X: np.ndarray) -> np.ndarray:
        X = np.atleast_2d(X).astype(float)
        return np.einsum("ri,ij,rj->r", X, self.Q, X) + self.offset

    def to_bqm(self):
        qubo_dict = {}
        N = self.Q.shape[0]
        for i in range(N):
            for j in range(i, N):
                val = float(self.Q[i, j])
                if i != j and self.Q[j, i] != 0.0:
                    val += float(self.Q[j, i])
                if abs(val) > 1e-12:
                    qubo_dict[(self.names[i], self.names[j])] = val
        return dimod.BinaryQuadraticModel.from_qubo(qubo_dict, offset=self.offset)


class ThermodynamicQUBOBuilder:
    """
    Constructs the Thermodynamic-Mapped Quadratic Unconstrained Binary Optimization (QUBO)
    matrix and dimod BinaryQuadraticModel (BQM) for dynamic microgrid power distribution.
    
    Master Hamiltonian:
        H(x) = λ_thermo * H_thermo(x) 
             + λ_cycle * H_cycle(x) 
             + λ_rad * H_radiality(x) 
             + λ_cap * H_capacity(x) 
             + λ_sw * H_switching(x)
    """
    def __init__(
        self,
        num_buses: int,
        edges: List[Tuple[int, int]],
        substations: List[int],
        graph: Optional[nx.Graph] = None,
        lambda_thermo: float = 1.0,
        lambda_cycle: float = 25.0,
        lambda_rad: float = 30.0,
        lambda_cap: float = 10.0,
        lambda_sw: float = 1.0,
    ):
        self.num_buses = num_buses
        self.edges = edges  # List of (u, v) for edge_id = 0 .. M-1
        self.num_edges = len(edges)
        self.substations = substations
        self.graph = graph
        
        self.l_thermo = lambda_thermo
        self.l_cycle = lambda_cycle
        self.l_rad = lambda_rad
        self.l_cap = lambda_cap
        self.l_sw = lambda_sw

        # Precompute fundamental cycle edges if graph is provided
        self.cycle_edge_ids: List[List[int]] = []
        if self.graph is not None:
            cycles = nx.cycle_basis(self.graph)
            for c in cycles:
                ce = []
                for i in range(len(c)):
                    u, v = c[i], c[(i + 1) % len(c)]
                    e_data = self.graph.get_edge_data(u, v)
                    if e_data and "edge_id" in e_data:
                        ce.append(e_data["edge_id"])
                    else:
                        # Lookup in edges list
                        for idx, (eu, ev) in enumerate(self.edges):
                            if (eu == u and ev == v) or (eu == v and ev == u):
                                ce.append(idx)
                                break
                self.cycle_edge_ids.append(ce)

    def build_bqm(
        self,
        entropy_weights: Dict[int, float],
        line_currents: Dict[int, float],
        line_i_max: Dict[int, float],
        prev_switch_states: Optional[Dict[int, int]] = None,
    ) -> dimod.BinaryQuadraticModel:
        """
        Formulates the complete unconstrained BQM using dimod.
        Variables: x_0, x_1, ..., x_{M-1} in {0, 1}
        """
        bqm = dimod.BinaryQuadraticModel(vartype=dimod.BINARY)
        
        # Initialize all binary switch variables
        for e in range(self.num_edges):
            bqm.add_variable(f"x_{e}", 0.0)

        # ------------------------------------------------------------------
        # Term 1: Thermodynamic Entropy Dissipation Objective H_thermo(x)
        # H_thermo(x) = Sum_{e} w_e * x_e, where w_e = P_loss,e / T_e
        # ------------------------------------------------------------------
        for e in range(self.num_edges):
            w = entropy_weights.get(e, 0.0)
            bqm.add_variable(f"x_{e}", self.l_thermo * w)

        # ------------------------------------------------------------------
        # Term 2: Fundamental Cycle Breaking Constraints H_cycle(x)
        # Each fundamental loop k must have exactly |C_k| - 1 active branches:
        # (Sum_{e in C_k} x_e - (|C_k| - 1))^2
        # = Sum_{e} (1 - 2*target)*x_e + 2 * Sum_{a < b} x_a * x_b + target^2
        # ------------------------------------------------------------------
        for ce in self.cycle_edge_ids:
            target = len(ce) - 1
            lin_coeff = self.l_cycle * (1.0 - 2.0 * float(target))
            for e_idx in ce:
                bqm.add_variable(f"x_{e_idx}", lin_coeff)

            quad_coeff = 2.0 * self.l_cycle
            for a in range(len(ce)):
                for b in range(a + 1, len(ce)):
                    bqm.add_interaction(f"x_{ce[a]}", f"x_{ce[b]}", quad_coeff)
            
            bqm.offset += self.l_cycle * (float(target) ** 2)

        # ------------------------------------------------------------------
        # Term 3: Radiality / Tree Topology Constraint H_radiality(x)
        # Total active lines across feeder must equal |V| - N_sub
        # (Sum_{e} x_e - (|V| - N_sub))^2
        # ------------------------------------------------------------------
        target_branches = self.num_buses - len(self.substations)
        lin_rad = self.l_rad * (1.0 - 2.0 * float(target_branches))
        for e in range(self.num_edges):
            bqm.add_variable(f"x_{e}", lin_rad)

        quad_rad = 2.0 * self.l_rad
        for a in range(self.num_edges):
            for b in range(a + 1, self.num_edges):
                bqm.add_interaction(f"x_{a}", f"x_{b}", quad_rad)

        bqm.offset += self.l_rad * (float(target_branches) ** 2)

        # ------------------------------------------------------------------
        # Term 4: Thermal Ampacity & Capacity Limit Constraint H_capacity(x)
        # Penalizes activating any line that exceeds safe thermal ampacity
        # ------------------------------------------------------------------
        for e in range(self.num_edges):
            i_val = line_currents.get(e, 0.0)
            i_max = line_i_max.get(e, 350.0)
            if i_val > i_max:
                overload_ratio = (i_val - i_max) / i_max
                penalty = self.l_cap * (1.0 + 5.0 * (overload_ratio ** 2))
                bqm.add_variable(f"x_{e}", penalty)

        # ------------------------------------------------------------------
        # Term 5: Circuit Breaker Switching Wear Penalty H_switching(x)
        # H_switching = Sum [ x_e (1 - x_prev) + (1 - x_e) x_prev ]
        #             = Sum [ (1 - 2*x_prev) * x_e + x_prev ]
        # ------------------------------------------------------------------
        if prev_switch_states is not None:
            for e, prev_state in prev_switch_states.items():
                coeff = self.l_sw * (1.0 - 2.0 * float(prev_state))
                bqm.add_variable(f"x_{e}", coeff)
                bqm.offset += self.l_sw * float(prev_state)

        return bqm

    def build_model(
        self,
        entropy_weights: Dict[int, float],
        line_currents: Optional[Dict[int, float]] = None,
        line_i_max: Optional[Dict[int, float]] = None,
        prev_switch_states: Optional[Dict[int, int]] = None,
    ) -> QUBOModel:
        """Constructs QUBOModel with binary decision variables and cycle slack variables."""
        var_names = [f"x_{e}" for e in range(self.num_edges)]

        cycle_slacks: List[List[Tuple[str, int]]] = []
        for k, ce in enumerate(self.cycle_edge_ids):
            max_slack = max(len(ce) - 2, 1)
            coeffs = bounded_binary_coeffs(max_slack)
            slacks = []
            for j, c in enumerate(coeffs):
                s_name = f"s_{k}_{j}"
                slacks.append((s_name, c))
                var_names.append(s_name)
            cycle_slacks.append(slacks)

        N = len(var_names)
        Q = np.zeros((N, N), dtype=float)
        offset = 0.0
        vidx = {name: i for i, name in enumerate(var_names)}

        w_max = max(max(entropy_weights.values()) if entropy_weights else 1.0, 1e-6)
        for e in range(self.num_edges):
            w = entropy_weights.get(e, 0.0) / w_max
            idx = vidx[f"x_{e}"]
            Q[idx, idx] += self.l_thermo * w

        for ce, slacks in zip(self.cycle_edge_ids, cycle_slacks):
            target = float(len(ce) - 1)
            terms = [(vidx[f"x_{e}"], 1.0) for e in ce] + [(vidx[s_name], float(c)) for s_name, c in slacks]
            offset += self.l_cycle * (target ** 2)

            for i, a_i in terms:
                Q[i, i] += self.l_cycle * (a_i ** 2 - 2.0 * target * a_i)

            for a in range(len(terms)):
                i, a_i = terms[a]
                for b in range(a + 1, len(terms)):
                    j, a_j = terms[b]
                    idx1, idx2 = min(i, j), max(i, j)
                    Q[idx1, idx2] += self.l_cycle * 2.0 * a_i * a_j

        target_edges = float(self.num_buses - len(self.substations))
        offset += self.l_rad * (target_edges ** 2)

        for e in range(self.num_edges):
            i = vidx[f"x_{e}"]
            Q[i, i] += self.l_rad * (1.0 - 2.0 * target_edges)

        for a in range(self.num_edges):
            for b in range(a + 1, self.num_edges):
                Q[a, b] += self.l_rad * 2.0

        if line_currents and line_i_max:
            for e in range(self.num_edges):
                i_val = line_currents.get(e, 0.0)
                i_max = line_i_max.get(e, 350.0)
                if i_val > i_max:
                    over = (i_val - i_max) / i_max
                    idx = vidx[f"x_{e}"]
                    Q[idx, idx] += self.l_cap * (1.0 + 5.0 * (over ** 2))

        if prev_switch_states:
            for e, prev in prev_switch_states.items():
                if e < self.num_edges:
                    idx = vidx[f"x_{e}"]
                    Q[idx, idx] += self.l_sw * (1.0 - 2.0 * float(prev))
                    offset += self.l_sw * float(prev)

        return QUBOModel(names=var_names, Q=Q, offset=offset, n_edges=self.num_edges)

    def to_ising(self, bqm: dimod.BinaryQuadraticModel) -> Tuple[Dict[str, float], Dict[Tuple[str, str], float], float]:
        """Converts QUBO Binary Quadratic Model into Ising Hamiltonian."""
        return bqm.to_ising()
