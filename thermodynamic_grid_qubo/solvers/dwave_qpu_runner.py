"""
D-Wave QPU Runner & Hardware Sampler Interface.

Provides:
1. DWaveQPUSampler: Directly interfaces with physical D-Wave Advantage QPU
   (Advantage_system4.1 / Advantage_system6.x) via EmbeddingComposite(DWaveSampler()),
   conforming to the same (X, E, ms) interface as NumpyAnnealer.
2. Explicit Chain Diagnostics: Tracks physical qubits embedded, max chain length,
   chain break fraction, and actual QPU access time.
3. Strict Honest Logging: Never falls back silently to classical simulation without
   explicit error or diagnostics tagging ('fallback=true').
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


class DWaveQPUSampler:
    """
    Physical D-Wave Advantage QPU Sampler with explicit minor embedding diagnostics.
    Conforms to the standard sampler interface: sample(qubo_matrix, num_reads, offset).
    """

    def __init__(
        self,
        token: Optional[str] = None,
        solver: Optional[str] = None,
        chain_strength: Optional[float] = None,
        annealing_time: float = 20.0,
        allow_fallback: bool = False,
    ):
        self.token = token or os.environ.get("DWAVE_API_TOKEN", "")
        self.solver = solver
        self.chain_strength = chain_strength
        self.annealing_time = annealing_time
        self.allow_fallback = allow_fallback
        self.last_diagnostics: Dict[str, Any] = {}

    def sample(
        self,
        qubo_matrix: np.ndarray,
        num_reads: int = 100,
        offset: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray, float]:
        """
        Submits QUBO matrix to physical D-Wave Advantage QPU.
        Returns:
            X: sorted binary samples matrix (num_reads x N)
            E: sorted energies array (num_reads)
            elapsed_ms: wall-clock latency (ms)
        """
        import dimod

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

        if not self.token:
            if not self.allow_fallback:
                raise RuntimeError(
                    "DWAVE_API_TOKEN not configured. To test physical hardware, provide a valid "
                    "D-Wave Leap API token or set allow_fallback=True for simulated execution."
                )
            # Explicit fallback mode
            import neal
            sampler = neal.SimulatedAnnealingSampler()
            response = sampler.sample(bqm, num_reads=num_reads, seed=42)
            self.last_diagnostics = {
                "hardware": "simulated_fallback",
                "fallback": True,
                "qubits_used": 0,
                "max_chain_length": 0,
                "chain_break_fraction": 0.0,
                "qpu_access_time_us": 0,
            }
        else:
            try:
                from dwave.system import DWaveSampler, EmbeddingComposite

                qpu_kwargs = {"token": self.token}
                if self.solver:
                    qpu_kwargs["solver"] = self.solver
                qpu_sampler = DWaveSampler(**qpu_kwargs)
                sampler = EmbeddingComposite(qpu_sampler)

                # Calibrate chain strength if not explicitly set
                cs = self.chain_strength
                if cs is None:
                    # Standard scaled heuristic: 1.5 * max |coupling|
                    max_coupling = max(abs(v) for v in qubo_dict.values()) if qubo_dict else 1.0
                    cs = float(1.5 * max_coupling)

                sample_kwargs = {
                    "num_reads": num_reads,
                    "chain_strength": cs,
                    "annealing_time": self.annealing_time,
                }
                response = sampler.sample(bqm, **sample_kwargs)

                # Extract hardware embedding and timing telemetry
                embedding = response.info.get("embedding_context", {}).get("embedding", {})
                qubits_used = sum(len(chain) for chain in embedding.values()) if embedding else 0
                max_chain = max((len(chain) for chain in embedding.values()), default=0)

                timing = response.info.get("timing", {})
                qpu_access_us = timing.get("qpu_access_time", 0)

                chain_breaks = []
                for record in response.data(fields=["chain_break_fraction"]):
                    if hasattr(record, "chain_break_fraction"):
                        chain_breaks.append(record.chain_break_fraction)

                mean_cbf = float(np.mean(chain_breaks)) if chain_breaks else 0.0

                self.last_diagnostics = {
                    "hardware": "dwave_advantage_qpu",
                    "solver_name": qpu_sampler.solver.name,
                    "fallback": False,
                    "qubits_used": qubits_used,
                    "max_chain_length": max_chain,
                    "chain_break_fraction": mean_cbf,
                    "chain_strength": cs,
                    "annealing_time_us": self.annealing_time,
                    "qpu_access_time_us": qpu_access_us,
                }
            except Exception as e:
                if not self.allow_fallback:
                    raise RuntimeError(f"D-Wave QPU execution failed: {e}") from e

                import neal
                sampler = neal.SimulatedAnnealingSampler()
                response = sampler.sample(bqm, num_reads=num_reads, seed=42)
                self.last_diagnostics = {
                    "hardware": "simulated_fallback",
                    "fallback": True,
                    "error": str(e),
                    "qubits_used": 0,
                    "max_chain_length": 0,
                    "chain_break_fraction": 0.0,
                    "qpu_access_time_us": 0,
                }

        samples = []
        energies = []
        for sample, energy in response.data(fields=["sample", "energy"]):
            vec = np.array([sample.get(i, 0) for i in range(N)], dtype=np.int8)
            samples.append(vec)
            energies.append(float(energy))

        X = np.array(samples)
        E = np.array(energies)
        sort_idx = np.argsort(E)
        X = X[sort_idx]
        E = E[sort_idx]

        elapsed_ms = (time.perf_counter() - t0) * 1e3
        return X, E, elapsed_ms


# Backwards compatibility wrapper
class DWaveQPURunner:
    """Legacy interface maintained for backwards compatibility."""

    def __init__(self, token: Optional[str] = None, use_cloud: bool = False):
        self.sampler = DWaveQPUSampler(token=token, allow_fallback=(not use_cloud))

    def solve(
        self,
        bqm: Any,
        num_reads: int = 500,
    ) -> Tuple[Dict[int, int], float, float, str]:
        t0 = time.perf_counter()
        Q, offset = bqm.to_qubo()
        var_list = list(bqm.variables)
        vmap = {v: i for i, v in enumerate(var_list)}
        N = len(var_list)
        q_mat = np.zeros((N, N), dtype=float)
        for (u, v), val in Q.items():
            q_mat[vmap[u], vmap[v]] = val

        X, E, ms = self.sampler.sample(q_mat, num_reads=num_reads, offset=offset)
        best_sample = {var_list[i]: int(X[0, i]) for i in range(N)}
        solver_name = self.sampler.last_diagnostics.get("hardware", "dwave_qpu")

        parsed_sample = {}
        for var_name, val in best_sample.items():
            if str(var_name).startswith("x_"):
                edge_idx = int(str(var_name).split("_")[1])
                parsed_sample[edge_idx] = int(val)

        return parsed_sample, float(E[0]), ms, solver_name
