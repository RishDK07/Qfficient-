#!/usr/bin/env python3
"""Phase 3 Comprehensive Suite: AC Cross-Validation, IEEE 69-Bus Feeder,
Parametric Sensitivity Curves, Pre-Registered n=100 Confirmation,
and ANSI C84.1 Voltage Support Analysis.
"""
import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Any

# Ensure matplotlib uses local cache on Windows
if "MPLCONFIGDIR" not in os.environ:
    mpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mpl_cache")
    os.environ["MPLCONFIGDIR"] = os.path.abspath(mpl_dir)
    os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from thermodynamic_grid_qubo.grid_engine.ieee_feeder_loader import IEEEFeederLoader
from thermodynamic_grid_qubo.verification.fast_flow import FastFeeder
from thermodynamic_grid_qubo.verification.pandapower_verifier import PandapowerVerifier
from thermodynamic_grid_qubo.benchmark.policies import (
    StandardStaticPolicy,
    BranchExchangePolicy,
    LossOptimalCandidateSearchPolicy,
    RandomTreePolicy,
    QUBOPolicy,
    QUBOQuadraticSurrogatePolicy,
    HybridBranchExchangePolicy,
    RandomBranchExchangePolicy,
)
from thermodynamic_grid_qubo.benchmark.simulate import Scenario, simulate


def run_ac_validation_study(num_scenarios: int = 5, output_dir: Path = Path("results")) -> Dict[str, Any]:
    """Step 3.1: AC Validation with pandapower across 5 scenarios at 3 sample timepoints."""
    print("\n=======================================================")
    print("STEP 3.1: Pandapower Non-Linear AC Power Flow Validation")
    print("=======================================================")
    grid = IEEEFeederLoader.load_ieee33()
    verifier = PandapowerVerifier(grid)
    trees = verifier.fast.enumerate_radial_configs()

    policies = {
        "standard_static": StandardStaticPolicy(),
        "oracle": LossOptimalCandidateSearchPolicy(candidate_trees=trees, pool_size=150),
        "branch_exchange": BranchExchangePolicy(max_iterations=3),
        "qubo_surrogate": QUBOQuadraticSurrogatePolicy(num_reads=40, sweeps=150, selection="filtered", seed=42),
    }

    loss_errors = []
    vmin_errors = []
    comparison_records = []

    for s_idx in range(num_scenarios):
        sc = Scenario.sample(seed=2000 + s_idx, time_steps=6, dt_seconds=300.0, randomize=True)
        # Reset each policy once per scenario
        for policy in policies.values():
            policy.reset(grid, verifier.fast, sc.timeline)

        # Sample 3 time points per scenario: early (step 1), mid (step 3), late (step 5)
        for step in [1, 3, 5]:
            inj = sc.timeline[step]
            for p_name, policy in policies.items():
                p_pu, q_pu = verifier.fast.vectors(inj)
                r0 = verifier.fast.resistances()

                from thermodynamic_grid_qubo.benchmark.policies import DecisionContext
                ctx = DecisionContext(
                    grid=grid,
                    fast=verifier.fast,
                    injections=inj,
                    temps_k=verifier.fast.t_amb,
                    prev_active=verifier.fast.standard_edges,
                    step=step,
                    p_pu=p_pu,
                    q_pu=q_pu,
                    resistances=r0,
                )
                active, _ = policy.decide(ctx)
                res = verifier.cross_validate(active, inj)
                loss_errors.append(res["loss_error_pct"])
                vmin_errors.append(res["vmin_diff_pu"])
                comparison_records.append({
                    "scenario": s_idx,
                    "step": step,
                    "policy": p_name,
                    "ld_loss_kw": res["lindistflow_loss_kw"],
                    "ac_loss_kw": res["ac_loss_kw"],
                    "loss_error_pct": res["loss_error_pct"],
                    "ld_vmin": res["lindistflow_vmin"],
                    "ac_vmin": res["ac_vmin"],
                    "vmin_diff_pu": res["vmin_diff_pu"],
                })

    mean_loss_err = float(np.mean(loss_errors))
    max_loss_err = float(np.max(loss_errors))
    mean_vmin_err = float(np.mean(vmin_errors))
    max_vmin_err = float(np.max(vmin_errors))

    print(f"LinDistFlow vs Full AC Power Flow Validation (N={len(comparison_records)} evaluations):")
    print(f"  Mean Active Loss Error : {mean_loss_err:.2f}% (Max: {max_loss_err:.2f}%)")
    print(f"  Mean Voltage Error     : {mean_vmin_err:.4f} pu (Max: {max_vmin_err:.4f} pu)")

    summary = {
        "num_evaluations": len(comparison_records),
        "mean_loss_error_pct": mean_loss_err,
        "max_loss_error_pct": max_loss_err,
        "mean_vmin_diff_pu": mean_vmin_err,
        "max_vmin_diff_pu": max_vmin_err,
        "records_sample": comparison_records[:8],
    }
    return summary


def run_second_feeder_study(num_scenarios: int = 15, output_dir: Path = Path("results")) -> Dict[str, Any]:
    """Step 3.2: Second Feeder Reconfiguration on IEEE 69-Bus Test Network."""
    print("\n=======================================================")
    print("STEP 3.2: Second Feeder Reconfiguration (IEEE 69-Bus)")
    print("=======================================================")
    grid69 = IEEEFeederLoader.load_ieee69()
    fast69 = FastFeeder(grid69)

    policies = [
        StandardStaticPolicy(),
        BranchExchangePolicy(max_iterations=5),
        RandomBranchExchangePolicy(max_iterations=5, seed=500),
    ]

    results: Dict[str, List[float]] = {p.name: [] for p in policies}
    v_mins: Dict[str, List[float]] = {p.name: [] for p in policies}

    for s_idx in range(num_scenarios):
        seed = 3000 + s_idx
        sc = Scenario.sample(seed=seed, time_steps=12, dt_seconds=300.0, grid=grid69, randomize=True)
        for p in policies:
            res = simulate(p, sc, grid=grid69)
            results[p.name].append(res["heat_mj"])
            v_mins[p.name].append(res["min_voltage_pu"])

    base_heat = np.array(results["standard_static"])
    be_heat = np.array(results["branch_exchange"])
    rand_be_heat = np.array(results["random_branch_exchange"])

    summary = {
        "feeder": "IEEE 69-Bus",
        "num_scenarios": num_scenarios,
        "standard_static_mean_heat_mj": float(np.mean(base_heat)),
        "branch_exchange_mean_heat_mj": float(np.mean(be_heat)),
        "branch_exchange_reduction_pct": float((np.mean(base_heat) - np.mean(be_heat)) / np.mean(base_heat) * 100.0),
        "branch_exchange_min_v_pu": float(np.mean(v_mins["branch_exchange"])),
        "standard_static_min_v_pu": float(np.mean(v_mins["standard_static"])),
        "random_be_mean_heat_mj": float(np.mean(rand_be_heat)),
        "random_be_reduction_pct": float((np.mean(base_heat) - np.mean(rand_be_heat)) / np.mean(base_heat) * 100.0),
    }

    print(f"IEEE 69-Bus Benchmark Results ({num_scenarios} scenarios):")
    print(f"  Standard Static : {summary['standard_static_mean_heat_mj']:.2f} MJ (V_min = {summary['standard_static_min_v_pu']:.4f} pu)")
    print(f"  Branch Exchange : {summary['branch_exchange_mean_heat_mj']:.2f} MJ (-{summary['branch_exchange_reduction_pct']:.2f}%, V_min = {summary['branch_exchange_min_v_pu']:.4f} pu)")
    print(f"  Random + BE     : {summary['random_be_mean_heat_mj']:.2f} MJ (-{summary['random_be_reduction_pct']:.2f}%)")
    return summary


def run_parametric_sensitivity(output_dir: Path = Path("results")) -> Dict[str, Any]:
    """Step 3.3: Parametric Sensitivity Curves over decision interval and thermal tau."""
    print("\n=======================================================")
    print("STEP 3.3: Parametric Sensitivity Analysis")
    print("=======================================================")
    grid = IEEEFeederLoader.load_ieee33()
    intervals = [60.0, 300.0, 900.0]  # 1 min, 5 min, 15 min
    thermal_taus = [60.0, 300.0, 600.0]  # fast, medium, slow

    p_std = StandardStaticPolicy()
    p_be = BranchExchangePolicy(max_iterations=3)

    interval_results = {}
    for dt in intervals:
        heat_std_list = []
        heat_be_list = []
        steps = int(3600.0 / dt)  # 1 hour simulation
        for s_idx in range(5):
            sc = Scenario.sample(seed=4000 + s_idx, time_steps=steps, dt_seconds=dt, randomize=True)
            res_std = simulate(p_std, sc, grid=grid)
            res_be = simulate(p_be, sc, grid=grid)
            heat_std_list.append(res_std["heat_mj"])
            heat_be_list.append(res_be["heat_mj"])

        red_pct = (np.mean(heat_std_list) - np.mean(heat_be_list)) / np.mean(heat_std_list) * 100.0
        interval_results[f"{int(dt)}s"] = {
            "dt_seconds": dt,
            "steps": steps,
            "mean_heat_std_mj": float(np.mean(heat_std_list)),
            "mean_heat_be_mj": float(np.mean(heat_be_list)),
            "reduction_pct": float(red_pct),
        }
        print(f"  Decision Interval {dt:4.0f}s: Base={np.mean(heat_std_list):.2f} MJ, Reconfig={np.mean(heat_be_list):.2f} MJ, Reduction={red_pct:.2f}%")

    # Plot Sensitivity Curve
    fig, ax = plt.subplots(figsize=(6, 4))
    dts = [intervals[0], intervals[1], intervals[2]]
    reds = [interval_results[f"{int(dt)}s"]["reduction_pct"] for dt in dts]
    ax.plot([dt / 60.0 for dt in dts], reds, marker="o", linewidth=2, color="#1f77b4")
    ax.set_xlabel("Reconfiguration Decision Interval (minutes)", fontsize=11)
    ax.set_ylabel("Loss Reduction vs Static (%)", fontsize=11)
    ax.set_title("Reconfiguration Benefit vs Decision Cadence", fontsize=12)
    ax.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plot_file = output_dir / "sensitivity_curves.png"
    plt.savefig(plot_file, dpi=200)
    plt.close()
    print(f"  Saved sensitivity curves to {plot_file}")

    return interval_results


def run_preregistered_n100_confirmation(output_dir: Path = Path("results")) -> Dict[str, Any]:
    """Step 3.4: Pre-registered Confirmation Run on n=100 randomized scenarios."""
    print("\n=======================================================")
    print("STEP 3.4: Pre-Registered n=100 Confirmation Study")
    print("=======================================================")
    grid = IEEEFeederLoader.load_ieee33()
    fast = FastFeeder(grid)
    trees = fast.enumerate_radial_configs()

    policies = [
        StandardStaticPolicy(),
        LossOptimalCandidateSearchPolicy(candidate_trees=trees, pool_size=200),
        BranchExchangePolicy(max_iterations=3),
        RandomTreePolicy(k_samples=50, mode="filtered", seed=888),
        QUBOQuadraticSurrogatePolicy(num_reads=50, sweeps=200, selection="filtered", seed=888),
        HybridBranchExchangePolicy(max_iterations=2, seed=888),
    ]

    p_names = [p.name for p in policies]
    results: Dict[str, List[float]] = {name: [] for name in p_names}
    v_mins: Dict[str, List[float]] = {name: [] for name in p_names}
    latencies: Dict[str, List[float]] = {name: [] for name in p_names}

    t0_all = time.time()
    for s_idx in range(100):
        seed = 5000 + s_idx
        sc = Scenario.sample(seed=seed, time_steps=12, dt_seconds=300.0, randomize=True)
        if (s_idx + 1) % 20 == 0:
            print(f"  Progress: [{s_idx + 1:3d}/100] scenarios evaluated...")

        for p in policies:
            res = simulate(p, sc, grid=grid)
            results[p.name].append(res["heat_mj"])
            v_mins[p.name].append(res["min_voltage_pu"])
            latencies[p.name].append(res["mean_decision_ms"])

    total_time_s = time.time() - t0_all
    print(f"  n=100 evaluation completed in {total_time_s:.1f} s.")

    base_heat = np.array(results["standard_static"])
    rand_heat = np.array(results["random_trees_filtered"])
    oracle_heat = np.array(results["loss_optimal_candidate_search"])

    confirmation_table: Dict[str, Any] = {}
    for name in p_names:
        h_vals = np.array(results[name])
        mean_h = float(np.mean(h_vals))
        std_h = float(np.std(h_vals, ddof=1))
        red_pct = float((np.mean(base_heat) - mean_h) / np.mean(base_heat) * 100.0)

        # Wilcoxon p-value vs random_trees_filtered
        try:
            _, p_vs_rand = stats.wilcoxon(h_vals - rand_heat)
        except Exception:
            p_vs_rand = 1.0

        # Wilcoxon p-value vs oracle
        try:
            _, p_vs_oracle = stats.wilcoxon(h_vals - oracle_heat)
        except Exception:
            p_vs_oracle = 1.0

        confirmation_table[name] = {
            "mean_heat_mj": mean_h,
            "std_heat_mj": std_h,
            "reduction_pct": red_pct,
            "min_v_pu": float(np.mean(v_mins[name])),
            "mean_latency_ms": float(np.mean(latencies[name])),
            "p_vs_random": float(p_vs_rand),
            "p_vs_oracle": float(p_vs_oracle),
        }

    print("\n--- Pre-Registered n=100 Confirmation Results ---")
    for name, m in confirmation_table.items():
        print(f"  {name:32s}: {m['mean_heat_mj']:.2f} ± {m['std_heat_mj']:.2f} MJ (-{m['reduction_pct']:5.2f}%), V_min={m['min_v_pu']:.4f} pu, p_rand={m['p_vs_random']:.2e}")

    return confirmation_table


def run_voltage_support_analysis(output_dir: Path = Path("results")) -> Dict[str, Any]:
    """Step 3.5: Voltage Support vs Loss Minimization Trade-Off Analysis."""
    print("\n=======================================================")
    print("STEP 3.5: Voltage Support & ANSI C84.1 Limit Analysis")
    print("=======================================================")
    grid = IEEEFeederLoader.load_ieee33()
    fast = FastFeeder(grid)

    # Extreme EV surge scenario causing voltage sag under 0.90 pu
    sc_heavy = Scenario.sample(seed=999, time_steps=12, dt_seconds=300.0, ev_surge_kw=1400.0, load_scale=1.35, randomize=False)

    p_std = StandardStaticPolicy()
    p_be = BranchExchangePolicy(max_iterations=5)

    res_std = simulate(p_std, sc_heavy, grid=grid, trace=True)
    res_be = simulate(p_be, sc_heavy, grid=grid, trace=True)

    summary = {
        "extreme_load_scale": 1.35,
        "extreme_ev_surge_kw": 1400.0,
        "standard_static": {
            "heat_mj": res_std["heat_mj"],
            "min_voltage_pu": res_std["min_voltage_pu"],
            "violation_steps": res_std["violation_steps"],
        },
        "branch_exchange": {
            "heat_mj": res_be["heat_mj"],
            "min_voltage_pu": res_be["min_voltage_pu"],
            "violation_steps": res_be["violation_steps"],
            "heat_reduction_pct": (res_std["heat_mj"] - res_be["heat_mj"]) / res_std["heat_mj"] * 100.0,
        },
    }

    print(f"Heavy Load / Severe EV Surge Stress Test:")
    print(f"  Standard Static : V_min = {res_std['min_voltage_pu']:.4f} pu, Violations = {res_std['violation_steps']}/12 steps, Heat = {res_std['heat_mj']:.2f} MJ")
    print(f"  Reconfiguration : V_min = {res_be['min_voltage_pu']:.4f} pu, Violations = {res_be['violation_steps']}/12 steps, Heat = {res_be['heat_mj']:.2f} MJ")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Run Phase 3 Validation Suite")
    parser.add_argument("--out", type=str, default="results", help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    ac_results = run_ac_validation_study(num_scenarios=5, output_dir=out_dir)
    feeder69_results = run_second_feeder_study(num_scenarios=15, output_dir=out_dir)
    sensitivity_results = run_parametric_sensitivity(output_dir=out_dir)
    n100_results = run_preregistered_n100_confirmation(output_dir=out_dir)
    voltage_results = run_voltage_support_analysis(output_dir=out_dir)

    all_phase3_results = {
        "ac_validation": ac_results,
        "ieee69_feeder": feeder69_results,
        "sensitivity": sensitivity_results,
        "n100_confirmation": n100_results,
        "voltage_support": voltage_results,
        "execution_time_seconds": time.time() - t0,
    }

    out_json = out_dir / "phase3_validation.json"
    with open(out_json, "w") as f:
        json.dump(all_phase3_results, f, indent=2)

    print(f"\nPhase 3 Suite Complete! Output written to {out_json}")


if __name__ == "__main__":
    main()
