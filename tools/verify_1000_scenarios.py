"""Mega-Scale 1,000-Iteration Statistical Rigor & Monte Carlo Verification Suite.

Executes 1,000 randomized Monte Carlo scenario evaluations across the full suite
of distribution network reconfiguration policies on IEEE 33-bus benchmark parameters:
  - Standard Static Baseline
  - Classical Branch Exchange (Baran-Wu / Civanlar)
  - Random Trees Filtered Control
  - Pairwise Quadratic Loss Surrogate QUBO (Filtered)
  - Hybrid QUBO + Branch Exchange

Calculates:
  - High-confidence statistical distributions (Mean, Std, 95% Confidence Intervals, IQR)
  - Paired Wilcoxon signed-rank tests across 1,000 scenarios
  - Voltage violation counts and ANSI C84.1 compliance rates
  - Feasibility and stability metrics
  - Outputs results to results/monte_carlo_1000_results.json
"""
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Any
import numpy as np
from scipy import stats

# Set MPL cache directory
if "MPLCONFIGDIR" not in os.environ:
    mpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mpl_cache")
    os.environ["MPLCONFIGDIR"] = os.path.abspath(mpl_dir)
    os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from thermodynamic_grid_qubo.grid_engine.ieee_feeder_loader import IEEEFeederLoader
from thermodynamic_grid_qubo.verification.fast_flow import FastFeeder
from thermodynamic_grid_qubo.benchmark.policies import (
    StandardStaticPolicy,
    BranchExchangePolicy,
    RandomTreePolicy,
    QUBOQuadraticSurrogatePolicy,
    HybridBranchExchangePolicy,
)
from thermodynamic_grid_qubo.benchmark.simulate import Scenario, simulate


def run_1000_scenario_verification(
    num_scenarios: int = 1000,
    time_steps: int = 2,
    dt_seconds: float = 300.0,
    output_dir: str = "results",
) -> Dict[str, Any]:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    grid = IEEEFeederLoader.load_ieee33()
    fast = FastFeeder(grid)

    print(f"=== Starting 1,000-Iteration Monte Carlo Verification Suite ===")
    print(f"Feeder: IEEE 33-Bus | Scenarios: {num_scenarios} | Steps/Scenario: {time_steps} | dt: {dt_seconds}s")
    print(f"Total operating state evaluations: {num_scenarios * time_steps:,} time-steps\n")

    policies = [
        StandardStaticPolicy(),
        BranchExchangePolicy(max_iterations=3),
        RandomTreePolicy(k_samples=25, mode="filtered", seed=777),
        QUBOQuadraticSurrogatePolicy(num_reads=15, sweeps=40, selection="filtered", seed=777),
        HybridBranchExchangePolicy(max_iterations=2, seed=777),
    ]

    p_names = [p.name for p in policies]
    heat_results: Dict[str, List[float]] = {name: [] for name in p_names}
    vmin_results: Dict[str, List[float]] = {name: [] for name in p_names}
    violations_results: Dict[str, List[int]] = {name: [] for name in p_names}
    latencies_results: Dict[str, List[float]] = {name: [] for name in p_names}

    t0_suite = time.time()

    for s_idx in range(num_scenarios):
        seed = 10000 + s_idx
        sc = Scenario.sample(seed=seed, time_steps=time_steps, dt_seconds=dt_seconds, randomize=True)

        for p in policies:
            res = simulate(p, sc, grid=grid)
            heat_results[p.name].append(res["heat_mj"])
            vmin_results[p.name].append(res["min_voltage_pu"])
            violations_results[p.name].append(res["voltage_violation_steps"])
            latencies_results[p.name].append(res["mean_decision_ms"])

        if (s_idx + 1) % 25 == 0 or (s_idx + 1) == num_scenarios:
            elapsed = time.time() - t0_suite
            rate = (s_idx + 1) / elapsed
            remaining = (num_scenarios - (s_idx + 1)) / rate if rate > 0 else 0
            print(f"  [Progress {s_idx + 1:4d}/{num_scenarios}] Elapsed: {elapsed:5.1f}s | Rate: {rate:4.1f} sc/s | Est. Remaining: {remaining:4.1f}s", flush=True)

    total_time_s = time.time() - t0_suite
    print(f"\n1,000 Scenarios completed in {total_time_s:.2f} s ({total_time_s / 60:.2f} min).", flush=True)

    base_heat = np.array(heat_results["standard_static"])
    rand_heat = np.array(heat_results["random_trees_filtered"])

    summary_stats: Dict[str, Any] = {}

    for name in p_names:
        h = np.array(heat_results[name])
        vm = np.array(vmin_results[name])
        viol = np.array(violations_results[name])
        lat = np.array(latencies_results[name])

        mean_h = float(np.mean(h))
        std_h = float(np.std(h, ddof=1))
        median_h = float(np.median(h))
        q25_h = float(np.percentile(h, 25))
        q75_h = float(np.percentile(h, 75))

        # 95% Confidence Interval for mean heat
        ci95 = float(1.96 * std_h / np.sqrt(num_scenarios))

        # Heat reduction vs baseline
        reduction_pct = float((np.mean(base_heat) - mean_h) / np.mean(base_heat) * 100.0)

        # Wilcoxon signed-rank test vs random_trees_filtered
        try:
            _, p_vs_rand = stats.wilcoxon(h - rand_heat)
        except Exception:
            p_vs_rand = 1.0

        # Wilcoxon vs baseline
        try:
            _, p_vs_base = stats.wilcoxon(h - base_heat)
        except Exception:
            p_vs_base = 1.0

        total_viol_steps = int(np.sum(viol))
        compliance_pct = float((1.0 - (total_viol_steps / (num_scenarios * time_steps))) * 100.0)

        summary_stats[name] = {
            "mean_heat_mj": mean_h,
            "std_heat_mj": std_h,
            "ci95_heat_mj": ci95,
            "median_heat_mj": median_h,
            "iqr_heat_mj": float(q75_h - q25_h),
            "reduction_pct": reduction_pct,
            "mean_vmin_pu": float(np.mean(vm)),
            "min_vmin_pu": float(np.min(vm)),
            "compliance_pct": compliance_pct,
            "total_violation_steps": total_viol_steps,
            "mean_latency_ms": float(np.mean(lat)),
            "p_vs_random": float(p_vs_rand),
            "p_vs_baseline": float(p_vs_base),
        }

    print("\n" + "=" * 95)
    print(f"1,000-SCENARIO MONTE CARLO STATISTICAL LEDGER (N={num_scenarios:,})")
    print("=" * 95)
    header = f"{'Policy':34s} | {'Mean Heat ± 95% CI (MJ)':24s} | {'Red. (%)':9s} | {'Min V (pu)':10s} | {'Compliance':10s} | {'p vs Rand':11s}"
    print(header)
    print("-" * 95)
    for name, s in summary_stats.items():
        ci_str = f"{s['mean_heat_mj']:.2f} ± {s['ci95_heat_mj']:.2f}"
        p_str = f"{s['p_vs_random']:.2e}" if not np.isnan(s['p_vs_random']) else "—"
        print(f"{name:34s} | {ci_str:24s} | {s['reduction_pct']:+7.2f}% | {s['mean_vmin_pu']:10.4f} | {s['compliance_pct']:9.1f}% | {p_str:11s}")
    print("=" * 95)

    # Plot 1000-Scenario Loss Distributions
    fig, ax = plt.subplots(figsize=(10, 5))
    plot_data = [heat_results[name] for name in p_names]
    bp = ax.boxplot(plot_data, tick_labels=[n.replace("_", "\n") for n in p_names], patch_artist=True)
    colors = ["#7f7f7f", "#2ca02c", "#1f77b4", "#ff7f0e", "#9467bd"]
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_ylabel("Total Joule Heat Dissipation (MJ)", fontsize=11)
    ax.set_title(f"Empirical Loss Distribution Across {num_scenarios:,} Randomized Scenarios (IEEE 33-Bus)", fontsize=12)
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    dist_file = out_path / "monte_carlo_1000_distribution.png"
    plt.savefig(dist_file, dpi=200)
    plt.close()
    print(f"Saved distribution plot to: {dist_file}")

    full_output = {
        "metadata": {
            "num_scenarios": num_scenarios,
            "time_steps_per_scenario": time_steps,
            "dt_seconds": dt_seconds,
            "total_operating_states_evaluated": num_scenarios * time_steps,
            "total_runtime_seconds": total_time_s,
        },
        "summary": summary_stats,
    }

    out_json = out_path / "monte_carlo_1000_results.json"
    with open(out_json, "w") as f:
        json.dump(full_output, f, indent=2)
    print(f"Saved 1,000-scenario results to: {out_json}")

    return full_output


if __name__ == "__main__":
    run_1000_scenario_verification()
