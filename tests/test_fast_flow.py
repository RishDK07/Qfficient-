"""Unit tests for FastFeeder LinDistFlow and NumpyAnnealer."""
import numpy as np
import pytest

from thermodynamic_grid_qubo.grid_engine.ieee_feeder_loader import IEEEFeederLoader
from thermodynamic_grid_qubo.verification.fast_flow import FastFeeder
from thermodynamic_grid_qubo.solvers.numpy_annealer import NumpyAnnealer


def test_fast_feeder_standard_ieee33():
    grid = IEEEFeederLoader.load_ieee33()
    fast = FastFeeder(grid)

    injections = {k: (-v[0], -v[1]) for k, v in grid.bus_loads.items()}
    p_pu, q_pu = fast.vectors(injections)
    resistances = fast.resistances()

    valid, v_pu, currents, loss_kw, v_min = fast.evaluate(fast.standard_edges, p_pu, q_pu, resistances)

    assert valid is True
    # IEEE 33 standard power flow loss is ~196.9 kW
    assert 195.0 < loss_kw < 205.0
    # Minimum voltage is at bus 18 with ~0.9071 pu
    assert 0.90 < v_min < 0.915
    assert len(currents) == fast.m
    assert len(v_pu) == fast.n


def test_fast_feeder_tree_checker():
    grid = IEEEFeederLoader.load_ieee33()
    fast = FastFeeder(grid)

    # Standard configuration is a tree
    assert fast.is_tree(fast.standard_edges) is True

    # 31 edges (not enough) is not a tree
    assert fast.is_tree(fast.standard_edges[:31]) is False

    # Disconnected edges
    assert fast.is_tree((0, 1, 2)) is False


def test_numpy_annealer_unconstrained():
    # Min x_0^2 + x_1^2 - 2 x_0 - 2 x_1 (Optimum is x_0=1, x_1=1 with energy -2)
    Q = np.array([
        [-1.0, 0.0],
        [0.0, -1.0]
    ])
    annealer = NumpyAnnealer(sweeps=100, seed=42)
    X, E, latency_ms = annealer.sample(Q, num_reads=20)

    assert latency_ms > 0
    assert np.all(X[0] == [1, 1])
    assert E[0] == pytest.approx(-2.0)
