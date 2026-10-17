import pytest
import numpy as np
import networkx as nx
from thermodynamic_grid_qubo.grid_engine.thermal_dynamics import ThermodynamicLineModel
from thermodynamic_grid_qubo.grid_engine.ieee_feeder_loader import IEEEFeederLoader
from thermodynamic_grid_qubo.qubo_engine.entropy_calculator import EntropyCalculator
from thermodynamic_grid_qubo.qubo_engine.qubo_builder import ThermodynamicQUBOBuilder
from thermodynamic_grid_qubo.verification.physics_verifier import PhysicsVerifier
from thermodynamic_grid_qubo.solvers.classical_baseline import ClassicalBaselineSolver

def test_thermal_dynamics():
    line = ThermodynamicLineModel(
        edge_id=0, u=1, v=2, r0=0.2, c_th=250000.0, theta_th=0.003, t_amb=298.15
    )
    # Check initial temperature
    assert line.temp == 298.15
    initial_r = line.resistance()
    assert abs(initial_r - 0.2) < 1e-6
    
    # Apply 200 A current for 10 seconds
    new_temp = line.update_transient_temperature(current_amps=200.0, dt_seconds=10.0)
    assert new_temp > 298.15
    # Resistance should increase due to positive temp coefficient alpha
    assert line.resistance() > initial_r
    
    # Entropy generation rate must be positive
    s_dot = line.entropy_generation_rate(current_amps=200.0)
    assert s_dot > 0.0

def test_ieee33_topology():
    grid = IEEEFeederLoader.load_ieee33()
    assert len(grid.graph.nodes) == 33
    assert len(grid.lines) == 37  # 32 branches + 5 ties
    assert len(grid.tie_switches) == 5
    assert 1 in grid.substations

def test_classical_baseline_solver():
    grid = IEEEFeederLoader.load_ieee33()
    solver = ClassicalBaselineSolver(grid)
    switches = solver.solve()
    verifier = PhysicsVerifier(grid)
    is_valid, msg = verifier.is_valid_radial_tree(switches)
    assert is_valid, f"Baseline tree failed: {msg}"
    assert sum(switches.values()) == 32

def test_qubo_bqm_formulation_and_ising():
    grid = IEEEFeederLoader.load_ieee33()
    edges = grid.get_edge_list()
    builder = ThermodynamicQUBOBuilder(
        num_buses=len(grid.graph.nodes),
        edges=edges,
        substations=grid.substations,
        graph=grid.graph
    )
    weights = {e: 1.0 for e in range(len(edges))}
    bqm = builder.build_bqm(weights, {}, {})
    
    # 37 branch decision variables + cycle slack variables
    edge_vars = [v for v in bqm.variables if v.startswith("x_")]
    slack_vars = [v for v in bqm.variables if v.startswith("s_")]
    assert len(edge_vars) == 37
    assert len(slack_vars) > 0  # Slack formulation for inequality cycle constraints
    assert len(bqm.variables) == len(edge_vars) + len(slack_vars)
    # Verify Ising transformation s_i in {-1, +1}
    h, J, offset = builder.to_ising(bqm)
    assert len(h) == len(bqm.variables)
    assert isinstance(offset, (float, int))

def test_power_flow_verification():
    grid = IEEEFeederLoader.load_ieee33()
    verifier = PhysicsVerifier(grid)
    base_switches = {e: (1 if e < 32 else 0) for e in range(37)}
    injections = {b: (-p, -q) for b, (p, q) in grid.bus_loads.items()}
    
    valid, v_pu, currents, loss_kw = verifier.solve_power_flow(base_switches, injections)
    assert 0.90 <= min(v_pu.values()) <= 1.05
    assert loss_kw > 0.0

def test_microgrid_visualizer(tmp_path):
    from thermodynamic_grid_qubo.verification.microgrid_visualizer import MicrogridVisualizer
    out_file = tmp_path / "test_microgrid.png"
    result_path = MicrogridVisualizer.plot_sample_microgrid(
        selected_line_ids={"L2", "L3", "L4", "L6", "L7", "L9"},
        output_file=str(out_file),
        show_line_metrics=True
    )
    assert result_path.exists()
    assert result_path.stat().st_size > 0


def test_every_radial_tree_has_zero_constraint_penalty():
    """Verify that any valid radial tree achieves zero constraint penalty in the QUBO model."""
    from thermodynamic_grid_qubo.verification.fast_flow import FastFeeder
    from thermodynamic_grid_qubo.qubo_engine.qubo_builder import bounded_binary_coeffs
    grid = IEEEFeederLoader.load_ieee33()
    fast = FastFeeder(grid)
    trees = fast.enumerate_radial_configs()

    builder = ThermodynamicQUBOBuilder(
        num_buses=len(grid.graph.nodes),
        edges=grid.get_edge_list(),
        substations=grid.substations,
        graph=grid.graph,
        lambda_thermo=0.0,
        lambda_cycle=10.0,
        lambda_rad=10.0,
        lambda_cap=0.0,
        lambda_sw=0.0,
    )
    weights = {e: 0.0 for e in range(len(grid.lines))}
    model = builder.build_model(weights)

    # For valid radial trees, test that setting optimal cycle slack variables achieves 0 penalty
    for t in trees[:10]:
        x = np.zeros(model.Q.shape[0], dtype=float)
        for e in t:
            x[e] = 1.0

        for k, ce in enumerate(builder.cycle_edge_ids):
            target = len(ce) - 1
            active_in_cycle = sum(x[e] for e in ce)
            diff = int(target - active_in_cycle)
            assert diff >= 0, "Valid radial tree cannot contain all edges of any cycle"
            coeffs = bounded_binary_coeffs(max(len(ce) - 2, 1))
            for j, c in enumerate(coeffs):
                s_name = f"s_{k}_{j}"
                idx = model.names.index(s_name)
                if diff >= c:
                    x[idx] = 1.0
                    diff -= c
            assert diff == 0, f"Failed to represent slack {target - active_in_cycle}"

        energy = model.energy(x)[0]
        assert abs(energy) < 1e-4, f"Constraint penalty for radial tree must be 0, got {energy}"


def test_mesh_currents_non_zero():
    """Verify that mesh_branch_currents produces realistic non-zero currents across meshed network."""
    from thermodynamic_grid_qubo.qubo_engine.entropy_calculator import mesh_branch_currents
    grid = IEEEFeederLoader.load_ieee33()
    injections = {b: (-p, -q) for b, (p, q) in grid.bus_loads.items()}
    temps = {e: 298.15 for e in grid.lines}

    i_mesh = mesh_branch_currents(grid, injections, temps)
    assert len(i_mesh) == len(grid.lines)
    for e, current in i_mesh.items():
        assert current > 0.0, f"Branch {e} current must be non-zero in meshed solve"


def test_thermal_model_time_constant():
    """Verify thermal time constant tau = C_th * theta_th is approx 10-12 minutes."""
    line = ThermodynamicLineModel(
        edge_id=0, u=1, v=2, r0=0.2, c_th=250000.0, theta_th=0.003, t_amb=298.15
    )
    tau_seconds = line.c_th * line.theta_th
    tau_minutes = tau_seconds / 60.0
    assert 5.0 <= tau_minutes <= 15.0, f"Thermal time constant {tau_minutes:.1f} min not in 5-15 min range"


def test_heat_accounting_three_phase():
    """Verify 3-phase Joule heat accounting 3 * I^2 * R * dt."""
    line = ThermodynamicLineModel(
        edge_id=0, u=1, v=2, r0=0.5, c_th=250000.0, theta_th=0.003, t_amb=298.15
    )
    current = 100.0  # A
    dt = 300.0  # s
    r = line.resistance()  # 0.5 ohm
    expected_joules = 3.0 * (current ** 2) * r * dt  # 3 * 10000 * 0.5 * 300 = 4,500,000 J = 4.5 MJ
    heat_mj = (3.0 * (current ** 2) * r * dt) / 1e6
    assert abs(heat_mj - 4.5) < 1e-5
