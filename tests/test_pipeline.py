import networkx as nx
import pytest

from thermodynamic_grid_qubo.grid_engine.ieee_feeder_loader import DistributionGrid
from thermodynamic_grid_qubo.pipeline import (
    MAX_BUSES, GridSizeError, OptimizationConfig, load_12_component_microgrid,
    run_optimization, validate_grid_size,
)
from thermodynamic_grid_qubo.verification import report_card as rc


@pytest.fixture(scope="module")
def result():
    return run_optimization(OptimizationConfig(grid="microgrid12", solver="neal", num_reads=100, time_steps=12))


def test_12_component_grid_matches_diagram_table():
    grid = load_12_component_microgrid()
    assert len(grid.graph.nodes) == 12 and len(grid.lines) == 16
    validate_grid_size(grid)


def test_every_step_is_a_valid_radial_tree(result):
    g = result["grid"]
    assert result["checks"]["radial_all_steps"]
    for sw in result["qubo"]["switches"]:
        tree = nx.Graph([(e["u"], e["v"]) for e, on in zip(g["edges"], sw) if on])
        assert nx.is_tree(tree) and tree.number_of_nodes() == g["n_buses"]


def test_result_has_everything_the_report_card_needs(result):
    grade = rc.grade_results(result)
    assert grade["overall"] in "ABCD" and len(grade["checks"]) == 8
    assert "Optimization Report Card" in rc.header_html(result, grade)
    fig = rc.render_network_figure(result)
    assert len(rc.fig_to_png(fig)) > 1000
    assert len(rc.line_rows(result, 0)) == result["grid"]["n_lines"]


def test_classical_mode_reports_no_improvement():
    r = run_optimization(OptimizationConfig(solver="classical", time_steps=6))
    assert abs(r["summary"]["heat_reduction_pct"]) < 1e-9
    assert rc.grade_results(r)["checks"][0]["status"] == "INFO"


def test_oversized_grid_is_rejected():
    g = DistributionGrid("big")
    g.add_bus(1, is_substation=True)
    for b in range(2, MAX_BUSES + 3):
        g.add_bus(b, 10, 5)
        g.add_branch(b - 2, b - 1, b, 0.3, 0.2)
    with pytest.raises(GridSizeError):
        validate_grid_size(g)
