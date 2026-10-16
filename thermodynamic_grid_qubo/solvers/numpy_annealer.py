"""Pure NumPy simulated annealing engine for QUBO optimization.

Requires zero external quantum dependencies (dimod, OpenJij, D-Wave).
Provides reproducible, fast simulated annealing with Metropolis-Hastings spin flips,
along with an optional adapter for OpenJij SASampler / SQASampler when installed.
"""
import time
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


class NumpyAnnealer:
    """Dependency-free Simulated Annealer using vectorized Metropolis-Hastings updates."""

    def __init__(
        self,
        sweeps: int = 400,
        beta_min: float = 0.05,
        beta_max: float = 30.0,
        seed: int = 42,
    ):
        self.sweeps = sweeps
        self.beta_min = beta_min
        self.beta_max = beta_max
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def sample(
        self,
        qubo_matrix: np.ndarray,
        num_reads: int = 100,
        offset: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray, float]:
        """Perform simulated annealing on QUBO matrix Q (min x^T Q x + offset).

        Args:
            qubo_matrix: (N, N) matrix representing quadratic program
            num_reads: number of independent annealing runs
            offset: scalar offset added to energy

        Returns:
            X: (num_reads, N) binary solution vectors sorted by energy
            E: (num_reads,) array of solution energies
            elapsed_ms: execution time in milliseconds
        """
        t0 = time.perf_counter()
        N = qubo_matrix.shape[0]

        # Symmetrize Q for fast single-spin flip delta-E calculations
        # For x in {0, 1}^N: x^T Q x = sum_i Q_ii x_i + sum_{i < j} (Q_ij + Q_ji) x_i x_j
        diag = np.diag(qubo_matrix).copy()
        # Symmetric off-diagonal: M_ij = (Q_ij + Q_ji) / 2
        M = (qubo_matrix + qubo_matrix.T) / 2.0
        np.fill_diagonal(M, 0.0)

        # Geometric beta schedule (inverse temperature: 1 / (k_B * T))
        betas = np.geomspace(self.beta_min, self.beta_max, self.sweeps)

        # Initialize random binary states for all reads (R, N)
        X = self.rng.integers(0, 2, size=(num_reads, N)).astype(float)

        # Local fields for all reads simultaneously: H = diag + 2 * X @ M  (R, N)
        H = diag + 2.0 * (X @ M)

        # Run simulated annealing across all reads simultaneously
        for beta in betas:
            order = self.rng.permutation(N)
            for i in order:
                x_i = X[:, i]  # (R,)
                h_i = H[:, i]  # (R,)

                # Delta E for flipping spin i: if x_i == 0 -> h_i; if x_i == 1 -> -h_i
                delta_E = np.where(x_i == 0.0, h_i, -h_i)

                # Acceptance probability: exp(-beta * delta_E)
                # Accepted if delta_E <= 0 or random < exp(-beta * delta_E)
                accept = (delta_E <= 0.0) | (self.rng.random(num_reads) < np.exp(-beta * np.clip(delta_E, -50.0, 50.0)))

                if np.any(accept):
                    # For accepted reads, flip x_i
                    delta_x = np.where(accept, 1.0 - 2.0 * x_i, 0.0)
                    X[:, i] += delta_x

                    # Rank-1 update to local fields across all reads:
                    # delta_H = 2 * delta_x[:, None] * M[i, :][None, :]
                    H += 2.0 * np.outer(delta_x, M[i, :])

        X_out = X.astype(np.int8)

        # Compute energies: E = diag(X Q X^T) + offset
        # Vectorized energy evaluation
        E = np.einsum("ri,ij,rj->r", X.astype(float), qubo_matrix, X.astype(float)) + offset

        # Sort solutions by ascending energy
        sort_idx = np.argsort(E)
        X_out = X_out[sort_idx]
        E = E[sort_idx]

        elapsed_ms = (time.perf_counter() - t0) * 1e3
        return X_out, E, elapsed_ms


class OpenJijSampler:
    """Optional adapter with the same interface as NumpyAnnealer, backed by OpenJij SASampler / SQASampler."""

    def __init__(
        self,
        use_sqa: bool = False,
        seed: int = 42,
        trotter: int = 16,
        num_sweeps: int = 300,
    ):
        self.use_sqa = use_sqa
        self.seed = seed
        self.trotter = trotter
        self.num_sweeps = num_sweeps

    def sample(
        self,
        qubo_matrix: np.ndarray,
        num_reads: int = 100,
        offset: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray, float]:
        import dimod
        try:
            import openjij as oj
        except ImportError:
            # Fallback to NumpyAnnealer if openjij is not installed
            fallback = NumpyAnnealer(sweeps=self.num_sweeps, seed=self.seed)
            return fallback.sample(qubo_matrix, num_reads=num_reads, offset=offset)

        t0 = time.perf_counter()
        N = qubo_matrix.shape[0]
        # Build dictionary QUBO for dimod
        qubo_dict = {}
        for i in range(N):
            for j in range(i, N):
                val = float(qubo_matrix[i, j])
                if i != j and qubo_matrix[j, i] != 0.0:
                    val += float(qubo_matrix[j, i])
                if abs(val) > 1e-12:
                    qubo_dict[(i, j)] = val

        bqm = dimod.BinaryQuadraticModel.from_qubo(qubo_dict, offset=offset)

        if self.use_sqa:
            sampler = oj.SQASampler(trotter=self.trotter, num_sweeps=self.num_sweeps, seed=self.seed)
        else:
            sampler = oj.SASampler(num_sweeps=self.num_sweeps, seed=self.seed)

        response = sampler.sample(bqm, num_reads=num_reads)
        samples = []
        energies = []
        for sample, energy in response.data(fields=["sample", "energy"]):
            vec = np.array([sample[i] for i in range(N)], dtype=np.int8)
            samples.append(vec)
            energies.append(float(energy))

        X = np.array(samples)
        E = np.array(energies)
        sort_idx = np.argsort(E)
        X = X[sort_idx]
        E = E[sort_idx]

        elapsed_ms = (time.perf_counter() - t0) * 1e3
        return X, E, elapsed_ms
