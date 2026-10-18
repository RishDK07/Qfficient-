"""Reconfiguration policies for benchmark and ablation evaluation."""
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple, Any
import time
import numpy as np

from ..grid_engine.ieee_feeder_loader import DistributionGrid
from ..verification.fast_flow import FastFeeder
from ..qubo_engine.qubo_builder import ThermodynamicQUBOBuilder, QUBOModel
from ..qubo_engine.entropy_calculator import mesh_branch_currents, EntropyCalculator
from ..solvers.numpy_annealer import NumpyAnnealer


@dataclass
class DecisionContext:
    grid: DistributionGrid
    fast: FastFeeder
    injections: Dict[int, Tuple[float, float]]
    temps_k: np.ndarray
    prev_active: Tuple[int, ...]
    step: int
    p_pu: np.ndarray
    q_pu: np.ndarray
    resistances: np.ndarray


class Policy:
    name: str = "base_policy"

    def reset(self, grid: DistributionGrid, fast: FastFeeder, timeline: List[Dict[int, Tuple[float, float]]]):
        pass

    def decide(self, ctx: DecisionContext) -> Tuple[Tuple[int, ...], float]:
        """Returns (active_edges_tuple, decision_latency_ms)."""
        raise NotImplementedError


class StandardStaticPolicy(Policy):
    """Textbook IEEE 33-bus baseline: branches 0..31 closed, 5 tie lines open (no reconfiguration)."""
    name = "standard_static"

    def reset(self, grid, fast, timeline):
        self.standard = tuple(range(fast.n - 1))

    def decide(self, ctx: DecisionContext) -> Tuple[Tuple[int, ...], float]:
        t0 = time.perf_counter()
        active = self.standard
        latency_ms = (time.perf_counter() - t0) * 1e3
        return active, latency_ms


class StaticLossOptimalPolicy(Policy):
    """Optimal single static topology: the best single tree chosen offline under mean load."""
    name = "static_loss_optimal"

    def __init__(self, candidate_trees: Optional[List[Tuple[int, ...]]] = None):
        self.candidate_trees = candidate_trees
        self.best_tree: Optional[Tuple[int, ...]] = None

    def reset(self, grid, fast, timeline):
        trees = self.candidate_trees or fast.enumerate_radial_configs()
        # Compute mean loads
        mean_inj = {}
        for b in grid.graph.nodes:
            p_mean = float(np.mean([inj.get(b, (0.0, 0.0))[0] for inj in timeline]))
            q_mean = float(np.mean([inj.get(b, (0.0, 0.0))[1] for inj in timeline]))
            mean_inj[b] = (p_mean, q_mean)

        p_pu, q_pu = fast.vectors(mean_inj)
        r0 = fast.resistances()

        best_loss = 1e12
        best_t = tuple(range(fast.n - 1))
        for t in trees:
            ok, _, _, loss_kw, _ = fast.evaluate(t, p_pu, q_pu, r0)
            if ok and loss_kw < best_loss:
                best_loss = loss_kw
                best_t = t
        self.best_tree = best_t

    def decide(self, ctx: DecisionContext) -> Tuple[Tuple[int, ...], float]:
        t0 = time.perf_counter()
        active = self.best_tree or ctx.fast.standard_edges
        latency_ms = (time.perf_counter() - t0) * 1e3
        return active, latency_ms


class BranchExchangePolicy(Policy):
    """Classical loop-breaking branch exchange reconfiguration (Baran-Wu / Civanlar)."""
    name = "branch_exchange"

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.solver = None

    def reset(self, grid, fast, timeline):
        from ..solvers.exact_classical_solver import BranchExchangeSolver
        self.solver = BranchExchangeSolver(grid)

    def decide(self, ctx: DecisionContext) -> Tuple[Tuple[int, ...], float]:
        t0 = time.perf_counter()
        switches, _, _ = self.solver.solve_exact_loss_minimizer(ctx.injections, max_iterations=self.max_iterations)
        active = tuple(sorted([e for e, s in switches.items() if s == 1]))
        latency_ms = (time.perf_counter() - t0) * 1e3
        return active, latency_ms


class LossOptimalCandidateSearchPolicy(Policy):
    """Dynamic candidate tree search over top loss-ranked radial configurations."""
    name = "loss_optimal_candidate_search"

    def __init__(self, candidate_trees: Optional[List[Tuple[int, ...]]] = None, pool_size: int = 400):
        self.candidate_trees = candidate_trees
        self.pool_size = pool_size
        self.active_pool: List[Tuple[int, ...]] = []

    def reset(self, grid, fast, timeline):
        if self.active_pool and len(self.active_pool) >= self.pool_size:
            return
        trees = self.candidate_trees or fast.enumerate_radial_configs()
        # Pre-filter to top pool based on mean load to make per-step solve ultra-fast
        mean_inj = {b: (float(np.mean([inj.get(b, (0.0, 0.0))[0] for inj in timeline])),
                        float(np.mean([inj.get(b, (0.0, 0.0))[1] for inj in timeline])))
                    for b in grid.graph.nodes}
        p_pu, q_pu = fast.vectors(mean_inj)
        r0 = fast.resistances()

        scored = []
        for t in trees:
            ok, _, _, loss, _ = fast.evaluate(t, p_pu, q_pu, r0)
            if ok:
                scored.append((loss, t))
        scored.sort(key=lambda x: x[0])
        self.active_pool = [t for _, t in scored[: self.pool_size]]

    def decide(self, ctx: DecisionContext) -> Tuple[Tuple[int, ...], float]:
        t0 = time.perf_counter()
        best_loss = 1e12
        best_t = ctx.prev_active

        for t in self.active_pool:
            ok, _, _, loss, _ = ctx.fast.evaluate(t, ctx.p_pu, ctx.q_pu, ctx.resistances)
            if ok and loss < best_loss:
                best_loss = loss
                best_t = t

        latency_ms = (time.perf_counter() - t0) * 1e3
        return best_t, latency_ms


# Backwards compatibility alias
ExactDynamicOraclePolicy = LossOptimalCandidateSearchPolicy


class RandomTreePolicy(Policy):
    """Ablation: generates K random spanning trees.
    In 'raw' mode, picks a random tree.
    In 'filtered' mode, picks the tree with minimum power-flow loss among the K candidates.
    """

    def __init__(self, k_samples: int = 100, mode: str = "filtered", seed: int = 42):
        self.k_samples = k_samples
        self.mode = mode
        self.name = f"random_trees_{mode}"
        self.rng = np.random.default_rng(seed)
        self.all_trees: List[Tuple[int, ...]] = []

    def reset(self, grid, fast, timeline):
        self.all_trees = fast.enumerate_radial_configs()

    def decide(self, ctx: DecisionContext) -> Tuple[Tuple[int, ...], float]:
        t0 = time.perf_counter()
        indices = self.rng.choice(len(self.all_trees), size=min(self.k_samples, len(self.all_trees)), replace=False)
        candidates = [self.all_trees[i] for i in indices]

        if self.mode == "raw":
            chosen = candidates[0]
        else:
            # Filtered: evaluate power flow on all K candidate trees
            best_loss = 1e12
            chosen = candidates[0]
            for t in candidates:
                ok, _, _, loss, _ = ctx.fast.evaluate(t, ctx.p_pu, ctx.q_pu, ctx.resistances)
                if ok and loss < best_loss:
                    best_loss = loss
                    chosen = t

        latency_ms = (time.perf_counter() - t0) * 1e3
        return chosen, latency_ms


class UnionFind:
    __slots__ = ('parent', 'rank')

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, i: int) -> int:
        root = i
        while root != self.parent[root]:
            root = self.parent[root]
        curr = i
        while curr != root:
            nxt = self.parent[curr]
            self.parent[curr] = root
            curr = nxt
        return root

    def union(self, i: int, j: int) -> bool:
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i == root_j:
            return False
        if self.rank[root_i] < self.rank[root_j]:
            self.parent[root_i] = root_j
        elif self.rank[root_i] > self.rank[root_j]:
            self.parent[root_j] = root_i
        else:
            self.parent[root_j] = root_i
            self.rank[root_i] += 1
        return True


class RandomProposalsPolicy(Policy):
    """Random Proposals Control (Ablation Baseline):
    Generates K random switch proposals in the configuration space, and applies
    the exact same repair and power-flow filtering as the QUBO policy.
    This establishes a rigorous control: does the quantum Hamiltonian guide the search,
    or does the post-processing filter/repair heuristic do all the work?
    """

    def __init__(self, k_samples: int = 50, mode: str = "filtered", seed: int = 42):
        self.k_samples = k_samples
        self.mode = mode
        self.name = f"random_proposals_{mode}"
        self.rng = np.random.default_rng(seed)

    def reset(self, grid, fast, timeline):
        pass

    def _repair_to_tree(self, active_edges: Set[int], fast: FastFeeder, weights: Dict[int, float]) -> Tuple[int, ...]:
        if fast.is_tree(tuple(active_edges)):
            return tuple(sorted(active_edges))

        all_edges = list(range(fast.m))
        all_edges.sort(key=lambda e: (0 if e in active_edges else 1, -weights.get(e, 0.0)))

        uf = UnionFind(fast.n)
        chosen = []
        for e in all_edges:
            u, v = fast.eu[e], fast.ev[e]
            if uf.union(u, v):
                chosen.append(e)
                if len(chosen) == fast.n - 1:
                    break
        return tuple(sorted(chosen))

    def decide(self, ctx: DecisionContext) -> Tuple[Tuple[int, ...], float]:
        t0 = time.perf_counter()
        target_edges = ctx.fast.n - 1

        temps_dict = {e: ctx.temps_k[i] for i, e in enumerate(ctx.fast.edge_ids)}
        i_mesh = mesh_branch_currents(ctx.grid, ctx.injections, temps_dict)
        weights = {}
        for i, e in enumerate(ctx.fast.edge_ids):
            i_val = i_mesh.get(e, 30.0)
            p_loss = 3.0 * (i_val ** 2) * ctx.resistances[i]
            weights[i] = p_loss / max(ctx.temps_k[i], 273.15)

        proposals = []
        for _ in range(self.k_samples):
            sample_edges = set(self.rng.choice(ctx.fast.m, size=target_edges, replace=False))
            proposals.append(sample_edges)

        if self.mode == "raw":
            chosen = self._repair_to_tree(proposals[0], ctx.fast, weights)
        else:
            candidate_trees = [self._repair_to_tree(p, ctx.fast, weights) for p in proposals]
            best_loss = 1e12
            chosen = candidate_trees[0]
            for t in candidate_trees:
                ok, _, _, loss, _ = ctx.fast.evaluate(t, ctx.p_pu, ctx.q_pu, ctx.resistances)
                if ok and loss < best_loss:
                    best_loss = loss
                    chosen = t

        latency_ms = (time.perf_counter() - t0) * 1e3
        return chosen, latency_ms


class QUBOPolicy(Policy):
    """Thermodynamic QUBO Policy with Simulated Annealing.
    Modes:
      - selection: 'raw' (pure Hamiltonian eigenvalue ranking) vs 'filtered' (power flow loss filter)
      - weights: 'mesh_current' vs 'flow_preserving'
    """

    def __init__(
        self,
        sampler: Optional[Any] = None,
        num_reads: int = 50,
        sweeps: int = 100,
        selection: str = "raw",
        weight_mode: str = "mesh_current",
        seed: int = 42,
    ):
        self.sampler = sampler or NumpyAnnealer(sweeps=sweeps, seed=seed)
        self.num_reads = num_reads
        self.sweeps = sweeps
        self.seed = seed
        self.selection = selection
        self.weight_mode = weight_mode
        self.name = f"qubo_{weight_mode}_{selection}"
        self.builder: Optional[ThermodynamicQUBOBuilder] = None
        self.calculator = EntropyCalculator()
        self.all_trees: List[Tuple[int, ...]] = []
        self.feasible_fractions: List[float] = []

    def reset(self, grid, fast, timeline):
        self.feasible_fractions = []
        edges = [(grid.lines[e].u, grid.lines[e].v) for e in fast.edge_ids]
        self.builder = ThermodynamicQUBOBuilder(
            num_buses=fast.n,
            edges=edges,
            substations=grid.substations,
            graph=grid.graph,
            lambda_thermo=1.0,
            lambda_cycle=4.0,
            lambda_rad=4.0,
            lambda_cap=5.0,
            lambda_sw=0.2,
        )

    def _repair_to_tree(self, active_edges: Set[int], fast: FastFeeder, weights: Dict[int, float]) -> Tuple[int, ...]:
        """Greedy repair if raw sample is not connected tree: sort by weight and keep acyclic edges."""
        if fast.is_tree(tuple(active_edges)):
            return tuple(sorted(active_edges))

        # Build maximum-conductivity/weight spanning tree guided by the QUBO sample
        # Prioritize edges in active_edges, tie-break by higher weight (keeping loaded lines closed)
        all_edges = list(range(fast.m))
        all_edges.sort(key=lambda e: (0 if e in active_edges else 1, -weights.get(e, 0.0)))

        uf = UnionFind(fast.n)
        chosen = []
        for e in all_edges:
            u, v = fast.eu[e], fast.ev[e]
            if uf.union(u, v):
                chosen.append(e)
                if len(chosen) == fast.n - 1:
                    break
        return tuple(sorted(chosen))

    def decide(self, ctx: DecisionContext) -> Tuple[Tuple[int, ...], float]:
        t0 = time.perf_counter()
        # Compute mesh currents for non-zero weights on all lines
        temps_dict = {e: ctx.temps_k[i] for i, e in enumerate(ctx.fast.edge_ids)}
        i_mesh = mesh_branch_currents(ctx.grid, ctx.injections, temps_dict)

        weights = {}
        for i, e in enumerate(ctx.fast.edge_ids):
            line = ctx.grid.lines[e]
            i_val = i_mesh.get(e, 30.0)
            if self.weight_mode == "flow_preserving":
                # Weight prioritizing high-loss branches
                weights[i] = (i_val ** 2) * ctx.resistances[i] / max(ctx.temps_k[i], 273.15)
            else:
                # Standard thermodynamic entropy rate
                p_loss = 3.0 * (i_val ** 2) * ctx.resistances[i]
                weights[i] = p_loss / max(ctx.temps_k[i], 273.15)

        prev_map = {i: (1 if i in ctx.prev_active else 0) for i in range(ctx.fast.m)}
        qubo_model = self.builder.build_model(
            entropy_weights=weights,
            line_currents={i: i_mesh.get(e, 30.0) for i, e in enumerate(ctx.fast.edge_ids)},
            line_i_max={i: ctx.grid.lines[e].i_max for i, e in enumerate(ctx.fast.edge_ids)},
            prev_switch_states=prev_map,
        )

        X, E, sample_ms = self.sampler.sample(qubo_model.Q, num_reads=self.num_reads, offset=qubo_model.offset)

        # Track feasible read fraction
        is_tree_flags = [ctx.fast.is_tree(tuple(np.nonzero(X[r, :ctx.fast.m])[0])) for r in range(len(X))]
        self.feasible_fractions.append(float(np.mean(is_tree_flags)))

        if self.selection == "raw":
            # Rank STRICTLY by raw lowest QUBO Hamiltonian energy
            best_sample = X[0, :ctx.fast.m]
            active_set = set(np.nonzero(best_sample)[0])
            if ctx.fast.is_tree(tuple(active_set)):
                chosen = tuple(sorted(active_set))
            else:
                # Repair minimal discrepancy to form valid radial tree
                chosen = self._repair_to_tree(active_set, ctx.fast, weights)
        else:
            # Filtered mode: check feasible trees among reads and rank by power flow loss
            valid_trees = []
            for r in range(len(X)):
                act = tuple(sorted(np.nonzero(X[r, :ctx.fast.m])[0]))
                if ctx.fast.is_tree(act):
                    valid_trees.append(act)

            if valid_trees:
                best_loss = 1e12
                chosen = valid_trees[0]
                for t in valid_trees:
                    ok, _, _, loss, _ = ctx.fast.evaluate(t, ctx.p_pu, ctx.q_pu, ctx.resistances)
                    if ok and loss < best_loss:
                        best_loss = loss
                        chosen = t
            else:
                # Fallback to repairing top sample
                act_set = set(np.nonzero(X[0, :ctx.fast.m])[0])
                chosen = self._repair_to_tree(act_set, ctx.fast, weights)

        latency_ms = (time.perf_counter() - t0) * 1e3
        return chosen, latency_ms


class QUBOPenaltyTunedPolicy(QUBOPolicy):
    """QUBO Policy with empirically tuned constraint penalties (lambda_cycle=2.0, lambda_rad=3.0)
    and per-scenario weight normalization.
    """

    def __init__(
        self,
        sampler: Optional[Any] = None,
        num_reads: int = 50,
        sweeps: int = 300,
        selection: str = "filtered",
        seed: int = 42,
    ):
        super().__init__(sampler=sampler, num_reads=num_reads, sweeps=sweeps, selection=selection, seed=seed)
        self.name = f"qubo_penalty_tuned_{selection}"

    def reset(self, grid, fast, timeline):
        self.feasible_fractions = []
        edges = [(grid.lines[e].u, grid.lines[e].v) for e in fast.edge_ids]
        # Use empirically tuned penalties from parameter sweep
        self.builder = ThermodynamicQUBOBuilder(
            num_buses=fast.n,
            edges=edges,
            substations=grid.substations,
            graph=grid.graph,
            lambda_thermo=1.0,
            lambda_cycle=2.0,
            lambda_rad=3.0,
            lambda_cap=4.0,
            lambda_sw=0.2,
        )


class QUBOQuadraticSurrogatePolicy(Policy):
    """QUBO Policy utilizing a Pairwise Quadratic Loss Surrogate (Spearman rho > 0.92).
    Captures coupled flow accumulation along shared paths to the substation.
    """

    def __init__(
        self,
        sampler: Optional[Any] = None,
        num_reads: int = 50,
        sweeps: int = 300,
        selection: str = "filtered",
        seed: int = 42,
    ):
        self.sampler = sampler or NumpyAnnealer(sweeps=sweeps, seed=seed)
        self.num_reads = num_reads
        self.sweeps = sweeps
        self.selection = selection
        self.seed = seed
        self.name = f"qubo_quadratic_surrogate_{selection}"
        self.builder: Optional[ThermodynamicQUBOBuilder] = None
        self.feasible_fractions: List[float] = []
        self.cycle_pairs: List[Tuple[int, int]] = []
        self.w_surrogate: Optional[np.ndarray] = None

    def reset(self, grid, fast, timeline):
        self.feasible_fractions = []
        edges = [(grid.lines[e].u, grid.lines[e].v) for e in fast.edge_ids]
        self.builder = ThermodynamicQUBOBuilder(
            num_buses=fast.n,
            edges=edges,
            substations=grid.substations,
            graph=grid.graph,
            lambda_thermo=1.0,
            lambda_cycle=2.0,
            lambda_rad=3.0,
        )

        # Precompute cycle pairs
        cycle_pairs = []
        for ce in self.builder.cycle_edge_ids:
            for i in range(len(ce)):
                for j in range(i + 1, len(ce)):
                    cycle_pairs.append((min(ce[i], ce[j]), max(ce[i], ce[j])))
        self.cycle_pairs = sorted(list(set(cycle_pairs)))

        # Calibrate surrogate weights on sample trees
        trees = fast.enumerate_radial_configs()
        rng = np.random.default_rng(self.seed)
        indices = rng.choice(len(trees), size=min(1000, len(trees)), replace=False)
        sample_trees = [trees[i] for i in indices]

        mean_inj = {b: (float(np.mean([inj.get(b, (0.0, 0.0))[0] for inj in timeline])),
                        float(np.mean([inj.get(b, (0.0, 0.0))[1] for inj in timeline])))
                    for b in grid.graph.nodes}
        p_pu, q_pu = fast.vectors(mean_inj)
        r0 = fast.resistances()

        y = []
        X_rows = []
        for t in sample_trees:
            ok, _, _, loss, _ = fast.evaluate(t, p_pu, q_pu, r0)
            y.append(loss)
            vec = np.zeros(fast.m)
            for e in t:
                vec[e] = 1.0
            X_rows.append(vec)

        y = np.array(y)
        X_mat = np.array(X_rows)

        quad_feats = [np.ones((len(X_mat), 1)), X_mat]
        for a, b in self.cycle_pairs:
            quad_feats.append((X_mat[:, a] * X_mat[:, b])[:, None])
        X_q = np.hstack(quad_feats)

        alpha = 10.0
        self.w_surrogate = np.linalg.solve(X_q.T @ X_q + alpha * np.eye(X_q.shape[1]), X_q.T @ y)

    def _repair_to_tree(self, active_edges: Set[int], fast: FastFeeder, weights: Dict[int, float]) -> Tuple[int, ...]:
        if fast.is_tree(tuple(active_edges)):
            return tuple(sorted(active_edges))

        all_edges = list(range(fast.m))
        all_edges.sort(key=lambda e: (0 if e in active_edges else 1, -weights.get(e, 0.0)))

        uf = UnionFind(fast.n)
        chosen = []
        for e in all_edges:
            u, v = fast.eu[e], fast.ev[e]
            if uf.union(u, v):
                chosen.append(e)
                if len(chosen) == fast.n - 1:
                    break
        return tuple(sorted(chosen))

    def decide(self, ctx: DecisionContext) -> Tuple[Tuple[int, ...], float]:
        t0 = time.perf_counter()
        temps_dict = {e: ctx.temps_k[i] for i, e in enumerate(ctx.fast.edge_ids)}
        i_mesh = mesh_branch_currents(ctx.grid, ctx.injections, temps_dict)
        weights = {i: 3.0 * (i_mesh.get(e, 30.0) ** 2) * ctx.resistances[i] for i, e in enumerate(ctx.fast.edge_ids)}

        model = self.builder.build_model(weights)
        Q = model.Q.copy()
        offset = model.offset

        # Incorporate quadratic surrogate loss couplings into Q
        if self.w_surrogate is not None:
            w_full = self.w_surrogate
            w_scale = 1.0 / (np.max(np.abs(w_full[1:])) + 1e-6)
            for e in range(ctx.fast.m):
                Q[e, e] += w_full[1 + e] * w_scale

            pair_idx = 1 + ctx.fast.m
            for a, b in self.cycle_pairs:
                val = w_full[pair_idx] * w_scale
                Q[a, b] += val
                pair_idx += 1

        X, E, sample_ms = self.sampler.sample(Q, num_reads=self.num_reads, offset=offset)

        is_tree_flags = [ctx.fast.is_tree(tuple(np.nonzero(X[r, :ctx.fast.m])[0])) for r in range(len(X))]
        self.feasible_fractions.append(float(np.mean(is_tree_flags)))

        if self.selection == "raw":
            best_sample = X[0, :ctx.fast.m]
            active_set = set(np.nonzero(best_sample)[0])
            chosen = self._repair_to_tree(active_set, ctx.fast, weights)
        else:
            valid_trees = []
            for r in range(len(X)):
                act = tuple(sorted(np.nonzero(X[r, :ctx.fast.m])[0]))
                if ctx.fast.is_tree(act):
                    valid_trees.append(act)

            if valid_trees:
                best_loss = 1e12
                chosen = valid_trees[0]
                for t in valid_trees:
                    ok, _, _, loss, _ = ctx.fast.evaluate(t, ctx.p_pu, ctx.q_pu, ctx.resistances)
                    if ok and loss < best_loss:
                        best_loss = loss
                        chosen = t
            else:
                act_set = set(np.nonzero(X[0, :ctx.fast.m])[0])
                chosen = self._repair_to_tree(act_set, ctx.fast, weights)

        latency_ms = (time.perf_counter() - t0) * 1e3
        return chosen, latency_ms


class HybridBranchExchangePolicy(Policy):
    """Hybrid Refinement: Uses QUBO proposal as the starting point for branch-exchange local search.
    Ablated against branch-exchange started from random trees.
    """
    name = "hybrid_qubo_branch_exchange"

    def __init__(self, max_iterations: int = 2, seed: int = 42):
        self.max_iterations = max_iterations
        self.seed = seed
        self.qubo_policy = QUBOPolicy(num_reads=50, sweeps=100, selection="filtered", seed=seed)
        self.solver = None

    def reset(self, grid, fast, timeline):
        from ..solvers.exact_classical_solver import BranchExchangeSolver
        self.qubo_policy.reset(grid, fast, timeline)
        self.solver = BranchExchangeSolver(grid)

    def decide(self, ctx: DecisionContext) -> Tuple[Tuple[int, ...], float]:
        t0 = time.perf_counter()
        # 1. QUBO Proposal
        qubo_tree, _ = self.qubo_policy.decide(ctx)

        # 2. Convert to switches dict
        init_switches = {e: (1 if e in qubo_tree else 0) for e in range(ctx.fast.m)}

        # 3. Branch Exchange local refinement
        refined_switches, _, _ = self.solver.solve_exact_loss_minimizer(
            ctx.injections,
            max_iterations=self.max_iterations,
            initial_switches=init_switches,
        )
        active = tuple(sorted([e for e, s in refined_switches.items() if s == 1]))
        latency_ms = (time.perf_counter() - t0) * 1e3
        return active, latency_ms


class RandomBranchExchangePolicy(Policy):
    """Ablation Baseline: Uses random tree proposal as the starting point for branch-exchange local search.
    Directly isolates whether the QUBO provides a superior warm start.
    """
    name = "random_branch_exchange"

    def __init__(self, max_iterations: int = 2, seed: int = 42):
        self.max_iterations = max_iterations
        self.seed = seed
        self.random_policy = RandomTreePolicy(k_samples=50, mode="filtered", seed=seed)
        self.solver = None

    def reset(self, grid, fast, timeline):
        from ..solvers.exact_classical_solver import BranchExchangeSolver
        self.random_policy.reset(grid, fast, timeline)
        self.solver = BranchExchangeSolver(grid)

    def decide(self, ctx: DecisionContext) -> Tuple[Tuple[int, ...], float]:
        t0 = time.perf_counter()
        # 1. Random Tree Proposal
        rand_tree, _ = self.random_policy.decide(ctx)

        # 2. Convert to switches dict
        init_switches = {e: (1 if e in rand_tree else 0) for e in range(ctx.fast.m)}

        # 3. Branch Exchange local refinement
        refined_switches, _, _ = self.solver.solve_exact_loss_minimizer(
            ctx.injections,
            max_iterations=self.max_iterations,
            initial_switches=init_switches,
        )
        active = tuple(sorted([e for e, s in refined_switches.items() if s == 1]))
        latency_ms = (time.perf_counter() - t0) * 1e3
        return active, latency_ms
