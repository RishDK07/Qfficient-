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
