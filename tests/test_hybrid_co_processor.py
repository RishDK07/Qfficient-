import pytest
import numpy as np
from thermodynamic_grid_qubo.grid_engine.ieee_feeder_loader import IEEEFeederLoader
from thermodynamic_grid_qubo.grid_engine.custom_grid_generator import generate_custom_grid
from thermodynamic_grid_qubo.solvers.hybrid_co_processor import HybridCoProcessor
from thermodynamic_grid_qubo.verification.physics_verifier import PhysicsVerifier

def test_hybrid_co_processor_radiality_ieee33():
    """Verify that Option B HybridCoProcessor produces guaranteed radial spanning trees."""
    grid = IEEEFeederLoader.load_ieee33()
    verifier = PhysicsVerifier(grid)
    injections = {b: grid.bus_loads.get(b, (0.0, 0.0)) for b in grid.graph.nodes}

    coprocessor = HybridCoProcessor(grid=grid, num_reads=40, sweeps=80, top_basins=2, polish_iterations=3, seed=42)
    switches, loss_kw, elapsed_ms, diag = coprocessor.solve(injections)

    is_radial, msg = verifier.is_valid_radial_tree(switches)
    assert is_radial, f"Topology returned by HybridCoProcessor is not radial: {msg}"
    assert sum(switches.values()) == len(grid.graph.nodes) - 1, "Edge count must be exactly N - 1"
    assert loss_kw > 0.0, "Loss must be positive"
    assert elapsed_ms > 0.0, "Latency must be positive"
    assert diag["total_candidates_generated"] >= 1
    assert diag["basins_polished"] >= 1

def test_hybrid_co_processor_monotonic_vs_baseline():
    """Verify that Option B HybridCoProcessor achieves equal or lower loss than the unreconfigured baseline."""
    grid = IEEEFeederLoader.load_ieee33()
    verifier = PhysicsVerifier(grid)
    injections = {b: grid.bus_loads.get(b, (0.0, 0.0)) for b in grid.graph.nodes}

    # Standard baseline
    std_switches = {e: (0 if e in grid.tie_switches else 1) for e in grid.lines}
    _, _, _, base_loss = verifier.solve_power_flow(std_switches, injections)

    coprocessor = HybridCoProcessor(grid=grid, num_reads=50, sweeps=100, top_basins=3, polish_iterations=5, seed=123)
    best_sw, best_loss, _, _ = coprocessor.solve(injections)

    # Hybrid engine must never perform worse than the baseline seed included in its tournament
    assert best_loss <= base_loss + 1e-4, f"Hybrid loss {best_loss:.2f} exceeded baseline loss {base_loss:.2f}"

def test_hybrid_co_processor_custom_40_grid():
    """Verify Option B on multi-tie custom 40-bus microgrid."""
    grid = generate_custom_grid(n_components=40, n_ties=6, seed=42)
    verifier = PhysicsVerifier(grid)
    injections = {b: grid.bus_loads.get(b, (0.0, 0.0)) for b in grid.graph.nodes}

    coprocessor = HybridCoProcessor(grid=grid, num_reads=40, sweeps=80, top_basins=2, polish_iterations=3, seed=42)
    switches, loss_kw, elapsed_ms, diag = coprocessor.solve(injections)

    is_radial, msg = verifier.is_valid_radial_tree(switches)
    assert is_radial, f"Custom 40 grid reconfiguration is not radial: {msg}"
    assert sum(switches.values()) == 39, "Active edges must equal 40 - 1 = 39"
    ok, v_pu, cur, _ = verifier.solve_power_flow(switches, injections)
    assert ok, "Power flow must satisfy ANSI C84.1 voltage bands on custom grid"
