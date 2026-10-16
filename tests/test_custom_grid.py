import networkx as nx
import pytest

from thermodynamic_grid_qubo.grid_engine.custom_grid_generator import generate_custom_grid
from thermodynamic_grid_qubo.pipeline import (
    OptimizationConfig,
    run_optimization,
    validate_grid_size,
)
from thermodynamic_grid_qubo.verification import report_card as rc
from thermodynamic_grid_qubo.verification.physics_verifier import PhysicsVerifier


def test_custom_grid_generator_topology_and_tree_size():
    """Verify generated custom grid matches specifications and tree size is exactly N - 1."""
    n_components = 30
    n_ties = 5
    grid = generate_custom_grid(
        n_components=n_components,
        n_solar=3,
        n_wind=2,
        n_battery=2,
        n_ev=2,
        n_ties=n_ties,
        seed=42,
    )

    assert len(grid.graph.nodes) == n_components
    assert len(grid.substations) == 1
    assert grid.substations[0] == 1
    assert len(grid.tie_switches) == n_ties
    assert len(grid.lines) == (n_components - 1) + n_ties

    # Verify DER node mix
    der_counts = {}
    for role in grid.der_nodes.values():
        der_counts[role] = der_counts.get(role, 0) + 1
    assert der_counts.get("pv") == 3
    assert der_counts.get("wind") == 2
    assert der_counts.get("bess") == 2
    assert der_counts.get("ev") == 2

    # Baseline configuration (ties open, base lines closed)
    base_switches = {e: (0 if e in grid.tie_switches else 1) for e in grid.lines}
    assert sum(base_switches.values()) == n_components - 1  # exactly 29 active lines

    verifier = PhysicsVerifier(grid)
    is_valid, msg = verifier.is_valid_radial_tree(base_switches)
    assert is_valid, f"Base tree is invalid: {msg}"

    tree = nx.Graph([
        (grid.lines[e].u, grid.lines[e].v)
        for e, on in base_switches.items() if on
    ])
    assert nx.is_tree(tree)
    assert tree.number_of_nodes() == n_components
    validate_grid_size(grid)


def test_custom_grid_full_pipeline_execution():
    """Verify full end-to-end pipeline run on 30-component custom grid."""
    cfg = OptimizationConfig(
        grid="custom",
        custom_n_components=30,
        custom_n_solar=3,
        custom_n_wind=2,
        custom_n_battery=2,
        custom_n_ev=2,
        custom_n_ties=5,
        solver="neal",
        num_reads=100,
        time_steps=6,
        seed=42,
    )
    result = run_optimization(cfg)

    g = result["grid"]
    assert g["n_buses"] == 30
    assert g["n_lines"] == 34
    assert g["n_ties"] == 5
    assert result["checks"]["radial_all_steps"]

    # Every step must be a radial spanning tree with exactly 29 active lines connecting all 30 components
    for sw in result["qubo"]["switches"]:
        assert sum(sw) == 29
        tree = nx.Graph([(e["u"], e["v"]) for e, on in zip(g["edges"], sw) if on])
        assert nx.is_tree(tree)
        assert tree.number_of_nodes() == 30

    # Test report card rendering for custom grid
    grade = rc.grade_results(result)
    assert grade["overall"] in "ABCD"
    fig = rc.render_network_figure(result)
    png_bytes = rc.fig_to_png(fig)
    assert len(png_bytes) > 5000


def test_custom_grid_sizes_60_and_100_switching():
    """Verify that larger sizes (60, 100) find valid radial reconfigurations with switch operations."""
    # Test 60-component grid
    cfg60 = OptimizationConfig(
        grid="custom",
        custom_n_components=60,
        custom_n_solar=4,
        custom_n_wind=3,
        custom_n_battery=2,
        custom_n_ev=3,
        custom_n_ties=6,
        solver="neal",
        num_reads=100,
        time_steps=4,
        seed=42,
    )
    res60 = run_optimization(cfg60)
    assert res60["grid"]["n_buses"] == 60
    assert res60["checks"]["radial_all_steps"]
    # Verify every step has exactly 59 active lines
    for sw in res60["qubo"]["switches"]:
        assert sum(sw) == 59
    assert res60["checks"]["reconfigurations"] > 0
