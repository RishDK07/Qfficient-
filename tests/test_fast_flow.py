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


def test_radial_configuration_count_matches_literature():
    """Verify that IEEE 33-bus topology yields exactly 50,751 valid radial spanning trees."""
    grid = IEEEFeederLoader.load_ieee33()
    fast = FastFeeder(grid)
    trees = fast.enumerate_radial_configs()
    assert len(trees) == 50751, f"Expected 50751 spanning trees, got {len(trees)}"


def test_fast_flow_matches_reference_verifier():
    """Verify LinDistFlow results match PhysicsVerifier reference on standard IEEE 33."""
    from thermodynamic_grid_qubo.verification.physics_verifier import PhysicsVerifier
    grid = IEEEFeederLoader.load_ieee33()
    fast = FastFeeder(grid)
    verifier = PhysicsVerifier(grid)

    injections = {k: (-v[0], -v[1]) for k, v in grid.bus_loads.items()}
    p_pu, q_pu = fast.vectors(injections)
    resistances = fast.resistances()

    valid, v_pu, currents, loss_kw, v_min = fast.evaluate(fast.standard_edges, p_pu, q_pu, resistances)
    sw = {e: (0 if e in grid.tie_switches else 1) for e in grid.lines}
    _, v_ref, _, loss_ref = verifier.solve_power_flow(sw, injections)

    assert valid is True
    assert abs(loss_kw - loss_ref) < 1.0  # Loss within 1 kW
    assert abs(v_min - min(v_ref.values())) < 0.01  # Min voltage within 0.01 pu


def test_exhaustive_optimum_opens_the_published_switches():
    """Verify exact classical optimum opens published branches: 7-8, 9-10, 14-15, 32-33, 25-29."""
    grid = IEEEFeederLoader.load_ieee33()
    fast = FastFeeder(grid)
    trees = fast.enumerate_radial_configs()

    injections = {b: (-p, -q) for b, (p, q) in grid.bus_loads.items()}
    p_pu, q_pu = fast.vectors(injections)
    r0 = fast.resistances()

    best_loss = 1e9
    best_tree = None
    for t in trees:
        ok, _, _, loss, _ = fast.evaluate(t, p_pu, q_pu, r0)
        if ok and loss < best_loss:
            best_loss = loss
            best_tree = t

    assert best_tree is not None
    open_edges = [e for e in range(fast.m) if e not in best_tree]
    open_pairs = sorted([(grid.lines[e].u, grid.lines[e].v) for e in open_edges])

    expected_pairs = sorted([(7, 8), (9, 10), (14, 15), (32, 33), (25, 29)])
    assert open_pairs == expected_pairs, f"Expected {expected_pairs}, got {open_pairs}"


def test_numpy_annealer_matches_brute_force_on_small_qubo():
    """Verify NumpyAnnealer matches exact brute-force search on a small 10-variable QUBO."""
    import itertools
    np.random.seed(123)
    n_vars = 8
    A = np.random.randn(n_vars, n_vars)
    Q = (A + A.T) / 2.0

    # Brute force
    best_bf_e = 1e9
    best_bf_x = None
    for bits in itertools.product([0, 1], repeat=n_vars):
        x = np.array(bits, dtype=float)
        e = float(x @ Q @ x)
        if e < best_bf_e:
            best_bf_e = e
            best_bf_x = x

    annealer = NumpyAnnealer(sweeps=200, seed=42)
    X, E, _ = annealer.sample(Q, num_reads=50)

    assert abs(E[0] - best_bf_e) < 1e-5
    assert np.allclose(X[0], best_bf_x)
