"""Unit tests for Pandapower AC power flow cross-validation and IEEE 69-bus feeder."""
import pytest
import numpy as np

from thermodynamic_grid_qubo.grid_engine.ieee_feeder_loader import IEEEFeederLoader
from thermodynamic_grid_qubo.verification.fast_flow import FastFeeder
from thermodynamic_grid_qubo.verification.pandapower_verifier import PandapowerVerifier


def test_pandapower_ieee33_cross_validation():
    """Verify LinDistFlow vs full AC power flow on IEEE 33 standard and optimal topologies."""
    grid = IEEEFeederLoader.load_ieee33()
    verifier = PandapowerVerifier(grid)
    injections = {k: (-v[0], -v[1]) for k, v in grid.bus_loads.items()}

    # Standard topology
    res_std = verifier.cross_validate(verifier.fast.standard_edges, injections)
    assert res_std["ac_converged"] == 1.0
    assert res_std["lindistflow_valid"] == 1.0
    # AC loss is ~210.99 kW, LinDistFlow is ~196.93 kW (relative error < 8%)
    assert res_std["loss_error_pct"] < 8.0
    # Voltage difference is < 0.01 pu
    assert res_std["vmin_diff_pu"] < 0.01
    assert 0.90 < res_std["ac_vmin"] < 0.92

    # Baran-Wu optimal topology: open switches [6, 8, 13, 31, 36]
    opt_active = sorted(set(range(37)) - {6, 8, 13, 31, 36})
    res_opt = verifier.cross_validate(opt_active, injections)
    assert res_opt["ac_converged"] == 1.0
    assert res_opt["loss_error_pct"] < 5.0
    assert res_opt["vmin_diff_pu"] < 0.005
    # Optimal reduces AC loss to ~139.5 kW and improves voltage to ~0.938 pu
    assert 135.0 < res_opt["ac_loss_kw"] < 145.0
    assert 0.93 < res_opt["ac_vmin"] < 0.95


def test_ieee69_feeder_loader_and_fast_feeder():
    """Verify IEEE 69-bus loader, radial spanning tree properties, and LinDistFlow."""
    grid = IEEEFeederLoader.load_ieee69()
    assert len(grid.graph.nodes) == 69
    assert len(grid.lines) == 73
    assert len(grid.tie_switches) == 5

    fast = FastFeeder(grid)
    assert fast.n == 69
    assert fast.m == 73
    assert fast.is_tree(fast.standard_edges) is True

    injections = {k: (-v[0], -v[1]) for k, v in grid.bus_loads.items()}
    p_pu, q_pu = fast.vectors(injections)
    resistances = fast.resistances()

    valid, v_pu, currents, loss_kw, v_min = fast.evaluate(fast.standard_edges, p_pu, q_pu, resistances)
    assert valid is True
    # Base LinDistFlow loss is ~209 kW and minimum voltage is ~0.913 pu
    assert 200.0 < loss_kw < 215.0
    assert 0.90 < v_min < 0.93


def test_pandapower_ieee69_cross_validation():
    """Verify LinDistFlow vs AC power flow on IEEE 69 standard and optimal topologies."""
    grid = IEEEFeederLoader.load_ieee69()
    verifier = PandapowerVerifier(grid)
    injections = {k: (-v[0], -v[1]) for k, v in grid.bus_loads.items()}

    # Standard topology
    res_std = verifier.cross_validate(verifier.fast.standard_edges, injections)
    assert res_std["ac_converged"] == 1.0
    assert res_std["loss_error_pct"] < 8.0
    assert res_std["vmin_diff_pu"] < 0.01
    assert 220.0 < res_std["ac_loss_kw"] < 230.0

    # Optimal topology: open branches 14, 57, 61, 69, 70 (0-indexed: 13, 56, 60, 68, 69)
    opt_active = sorted(set(range(73)) - {13, 56, 60, 68, 69})
    res_opt = verifier.cross_validate(opt_active, injections)
    assert res_opt["ac_converged"] == 1.0
    assert res_opt["loss_error_pct"] < 5.0
    assert res_opt["vmin_diff_pu"] < 0.005
    # Optimal AC loss drops to ~99.6 kW
    assert 95.0 < res_opt["ac_loss_kw"] < 105.0
    assert 0.93 < res_opt["ac_vmin"] < 0.96
