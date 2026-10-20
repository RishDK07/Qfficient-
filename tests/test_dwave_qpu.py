import pytest
import numpy as np
from thermodynamic_grid_qubo.solvers.dwave_qpu_runner import DWaveQPUSampler

def test_dwave_qpu_sampler_raises_without_token():
    """Verify that DWaveQPUSampler refuses silent fallback when allow_fallback=False."""
    sampler = DWaveQPUSampler(token="", allow_fallback=False)
    Q = np.array([[1.0, -2.0], [0.0, 1.0]])
    with pytest.raises(RuntimeError, match="DWAVE_API_TOKEN not configured"):
        sampler.sample(Q, num_reads=10)

def test_dwave_qpu_sampler_explicit_fallback():
    """Verify that DWaveQPUSampler tags diagnostics accurately when allow_fallback=True."""
    sampler = DWaveQPUSampler(token="", allow_fallback=True)
    Q = np.array([[1.0, -2.0], [0.0, 1.0]])
    X, E, ms = sampler.sample(Q, num_reads=20)
    assert X.shape == (20, 2)
    assert len(E) == 20
    assert ms > 0.0
    diag = sampler.last_diagnostics
    assert diag["fallback"] is True
    assert diag["hardware"] == "simulated_fallback"
