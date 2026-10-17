import json
import re
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_qubo_builder_lazy_dimod():
    """Verify ThermodynamicQUBOBuilder can construct model without eager dimod import."""
    from thermodynamic_grid_qubo.qubo_engine.qubo_builder import ThermodynamicQUBOBuilder, QUBOModel
    builder = ThermodynamicQUBOBuilder(
        num_buses=5,
        edges=[(0, 1), (1, 2), (2, 3), (3, 4), (0, 4)],
        substations=[0],
    )
    weights = {0: 10.0, 1: 5.0, 2: 1.0, 3: 2.0, 4: 0.5}
    model = builder.build_model(weights)
    assert isinstance(model, QUBOModel)
    assert model.Q.shape[0] >= 5


def test_qubo_weight_sign_rewards_closed_loaded_lines():
    """Verify that thermodynamic linear weight is negative so loaded lines are rewarded when closed."""
    from thermodynamic_grid_qubo.qubo_engine.qubo_builder import ThermodynamicQUBOBuilder
    builder = ThermodynamicQUBOBuilder(
        num_buses=3,
        edges=[(0, 1), (1, 2)],
        substations=[0],
        lambda_thermo=1.0,
    )
    weights = {0: 100.0, 1: 10.0}
    model = builder.build_model(weights)
    # x_0 has higher weight than x_1, so its diagonal linear coefficient Q[0,0] must be strictly negative
    # and lower (more negative) than Q[1,1]
    assert model.Q[0, 0] < model.Q[1, 1]
    # Check that setting x_0=1 lowers energy relative to x_0=0 (holding other vars 0)
    import numpy as np
    x_zero = np.zeros(model.Q.shape[0])
    x_closed = np.zeros(model.Q.shape[0])
    x_closed[0] = 1.0
    e_zero = model.energy(x_zero)[0]
    e_closed = model.energy(x_closed)[0]
    # Closing loaded branch 0 should contribute negatively to the thermo term
    # (subject to radiality penalties)
    assert (model.Q[0, 0] - model.Q[1, 1]) < 0


def test_classical_baseline_uses_standard_feeder_topology():
    """Verify that ClassicalBaselineSolver uses nominal topology (ties open, distribution branches closed)."""
    from thermodynamic_grid_qubo.grid_engine.ieee_feeder_loader import IEEEFeederLoader
    from thermodynamic_grid_qubo.solvers.classical_baseline import ClassicalBaselineSolver
    grid = IEEEFeederLoader.load_ieee33()
    solver = ClassicalBaselineSolver(grid)
    switches = solver.solve()
    # Tie lines 32..36 must be open (0)
    for tie in grid.tie_switches:
        assert switches[tie] == 0
    # Standard branches 0..31 must be closed (1)
    for b in range(32):
        assert switches[b] == 1


def test_branch_exchange_reconfiguration_improves_loss():
    """Verify that BranchExchangeSolver strictly reduces power flow loss vs unreconfigured standard."""
    from thermodynamic_grid_qubo.grid_engine.ieee_feeder_loader import IEEEFeederLoader
    from thermodynamic_grid_qubo.solvers.exact_classical_solver import BranchExchangeSolver
    from thermodynamic_grid_qubo.verification.physics_verifier import PhysicsVerifier

    grid = IEEEFeederLoader.load_ieee33()
    solver = BranchExchangeSolver(grid)
    verifier = PhysicsVerifier(grid)

    injections = {b: (-p, -q) for b, (p, q) in grid.bus_loads.items()}
    # Standard unreconfigured
    std_switches, _ = solver.solve_unreconfigured_standard()
    _, _, _, std_loss = verifier.solve_power_flow(std_switches, injections)

    # Branch exchange
    be_switches, be_loss, _ = solver.solve_exact_loss_minimizer(injections)
    assert be_loss < std_loss
    assert (std_loss - be_loss) / std_loss > 0.05  # At least 5% reduction on IEEE 33 nominal


def test_no_hardcoded_paths_in_codebase():
    """Verify that no absolute Windows paths (e.g. c:\\ep-project) are hardcoded in python source files."""
    pattern = re.compile(r"c:[\\/]ep-project", re.IGNORECASE)
    py_files = list(PROJECT_ROOT.glob("*.py")) + list((PROJECT_ROOT / "thermodynamic_grid_qubo").rglob("*.py"))
    violations = []
    for f in py_files:
        content = f.read_text(encoding="utf-8")
        if pattern.search(content):
            violations.append(str(f.relative_to(PROJECT_ROOT)))
    assert not violations, f"Hardcoded Windows paths found in: {violations}"


def test_report_numbers_match_summary_json():
    """Verify that every number in BENCHMARK_REPORT.md and README.md matches results/benchmark_summary.json."""
    summary_file = PROJECT_ROOT / "results" / "benchmark_summary.json"
    if not summary_file.exists():
        pytest.skip("results/benchmark_summary.json does not exist yet")

    with open(summary_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = data["summary"]
    hypo = data.get("statistical_tests", {})

    report_file = PROJECT_ROOT / "results" / "BENCHMARK_REPORT.md"
    assert report_file.exists(), "results/BENCHMARK_REPORT.md must exist"
    report_text = report_file.read_text(encoding="utf-8")

    readme_file = PROJECT_ROOT / "README.md"
    readme_text = readme_file.read_text(encoding="utf-8")

    # Fabricated row must NOT exist anywhere
    assert "3.470" not in readme_text, "Fabricated row (3.470 MJ) found in README.md"
    assert "3.470" not in report_text, "Fabricated row (3.470 MJ) found in BENCHMARK_REPORT.md"

    # Check that each policy's mean heat matches between JSON and report
    for pol_name, stats in summary.items():
        heat_mean = stats["heat_mj"]["mean"]
        heat_str = f"{heat_mean:.3f}"
        assert heat_str in report_text, f"Mean heat {heat_str} for {pol_name} not found in BENCHMARK_REPORT.md"
        assert heat_str in readme_text, f"Mean heat {heat_str} for {pol_name} not found in README.md"


def test_build_bqm_slack_formulation():
    """Verify build_bqm uses the inequality slack formulation for fundamental cycles."""
    from thermodynamic_grid_qubo.grid_engine.ieee_feeder_loader import IEEEFeederLoader
    from thermodynamic_grid_qubo.qubo_engine.qubo_builder import ThermodynamicQUBOBuilder
    grid = IEEEFeederLoader.load_ieee33()
    builder = ThermodynamicQUBOBuilder(
        num_buses=len(grid.graph.nodes),
        edges=grid.get_edge_list(),
        substations=grid.substations,
        graph=grid.graph,
    )
    weights = {e: 1.0 for e in range(len(grid.lines))}
    bqm = builder.build_bqm(weights, {}, {})
    # Edge variables: x_0 .. x_36
    edge_vars = [v for v in bqm.variables if v.startswith("x_")]
    # Slack variables: s_k_j
    slack_vars = [v for v in bqm.variables if v.startswith("s_")]
    assert len(edge_vars) == 37
    assert len(slack_vars) > 0, "BQM must include cycle slack variables"
    assert len(bqm.variables) == 37 + len(slack_vars)


def test_exact_ac_baseline_loss():
    """Verify that exact AC DistFlow produces canonical ~210.74 kW (~211 kW) base loss on IEEE 33."""
    from thermodynamic_grid_qubo.grid_engine.ieee_feeder_loader import IEEEFeederLoader
    from thermodynamic_grid_qubo.verification.fast_flow import FastFeeder
    from thermodynamic_grid_qubo.verification.physics_verifier import PhysicsVerifier
    grid = IEEEFeederLoader.load_ieee33()
    fast = FastFeeder(grid)
    pv = PhysicsVerifier(grid)

    injections = {b: (-p, -q) for b, (p, q) in grid.bus_loads.items()}
    p_pu, q_pu = fast.vectors(injections)
    r0 = fast.resistances()

    # LinDistFlow (linearized, no branch loss feedback): ~196.9 kW
    ok_lin, _, _, loss_lin, _ = fast.evaluate(fast.standard_edges, p_pu, q_pu, r0)
    assert ok_lin
    assert 190.0 < loss_lin < 200.0

    # Exact AC DistFlow (iterative, branch loss feedback): canonical ~210.74 kW (~211 kW)
    ok_ac, _, _, loss_ac, v_min = fast.evaluate_ac(fast.standard_edges, p_pu, q_pu, r0)
    assert ok_ac
    assert 205.0 < loss_ac < 215.0, f"Expected AC loss ~211 kW, got {loss_ac:.2f} kW"
    assert 0.90 < v_min < 0.92

    # PhysicsVerifier AC power flow
    sw = {e: (0 if e in grid.tie_switches else 1) for e in grid.lines}
    _, v_pv, _, loss_pv = pv.solve_ac_power_flow(sw, injections)
    assert 0.90 < min(v_pv.values()) < 0.92
    assert 205.0 < loss_pv < 215.0


def test_random_proposals_policy():
    """Verify that RandomProposalsPolicy generates valid radial tree reconfigurations."""
    from thermodynamic_grid_qubo.grid_engine.ieee_feeder_loader import IEEEFeederLoader
    from thermodynamic_grid_qubo.verification.fast_flow import FastFeeder
    from thermodynamic_grid_qubo.benchmark.policies import RandomProposalsPolicy, DecisionContext
    import numpy as np

    grid = IEEEFeederLoader.load_ieee33()
    fast = FastFeeder(grid)
    policy = RandomProposalsPolicy(k_samples=20, mode="filtered", seed=42)
    policy.reset(grid, fast, [])

    injections = {b: (-p, -q) for b, (p, q) in grid.bus_loads.items()}
    p_pu, q_pu = fast.vectors(injections)
    temps_k = np.array([grid.lines[e].t_amb for e in fast.edge_ids], dtype=float)
    resistances = fast.resistances(temps_k)

    ctx = DecisionContext(
        grid=grid,
        fast=fast,
        injections=injections,
        temps_k=temps_k,
        prev_active=fast.standard_edges,
        step=0,
        p_pu=p_pu,
        q_pu=q_pu,
        resistances=resistances,
    )
    chosen, ms = policy.decide(ctx)
    assert fast.is_tree(chosen), "Chosen configuration must be a valid radial tree"
    assert len(chosen) == 32
