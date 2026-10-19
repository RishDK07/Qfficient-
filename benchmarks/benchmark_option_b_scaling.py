"""
Benchmark: Option B Symbiotic Hybrid Quantum-Classical Scaling.

Evaluates scaling performance across multiple distribution grid scales:
- 12-Bus Microgrid (3 ties)
- IEEE 33-Bus Feeder (5 ties, 50,751 trees)
- Custom 40-Bus Microgrid (6 ties)
- Custom 60-Bus Microgrid (8 ties)
- Custom 100-Bus Microgrid (12 ties, >10^12 tree search space)

Compares:
1. Standard Nominal Baseline
2. Classical 1-opt Branch Exchange (Baran-Wu / Civanlar)
3. Option B Symbiotic Hybrid Co-Processor (QUBO + Matroid Repair + Multi-Basin Classical Polish)
"""
import os
import json
import time
from pathlib import Path
import numpy as np

# Ensure matplotlib uses local cache on Windows
if "MPLCONFIGDIR" not in os.environ:
    mpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".mpl_cache")
    os.environ["MPLCONFIGDIR"] = os.path.abspath(mpl_dir)
    os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from thermodynamic_grid_qubo.grid_engine.ieee_feeder_loader import IEEEFeederLoader
from thermodynamic_grid_qubo.grid_engine.custom_grid_generator import generate_custom_grid
from thermodynamic_grid_qubo.pipeline import load_12_component_microgrid
from thermodynamic_grid_qubo.verification.physics_verifier import PhysicsVerifier
from thermodynamic_grid_qubo.solvers.exact_classical_solver import ExactClassicalSolver
from thermodynamic_grid_qubo.solvers.hybrid_co_processor import HybridCoProcessor

def run_scaling_benchmark(output_dir: str = "results"):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    test_systems = [
        ("12-Bus Microgrid", load_12_component_microgrid()),
        ("IEEE 33-Bus Feeder", IEEEFeederLoader.load_ieee33()),
        ("Custom 40-Bus (6 ties)", generate_custom_grid(n_components=40, n_ties=6, seed=42)),
        ("Custom 60-Bus (8 ties)", generate_custom_grid(n_components=60, n_ties=8, seed=42)),
        ("Custom 100-Bus (12 ties)", generate_custom_grid(n_components=100, n_ties=12, seed=42)),
    ]

    results_data = []

    print("=" * 80)
    print("OPTION B SYMBIOTIC HYBRID CO-PROCESSOR SCALING BENCHMARK")
    print("=" * 80)

    for name, grid in test_systems:
        n_buses = len(grid.graph.nodes)
        n_lines = len(grid.lines)
        n_ties = len(grid.tie_switches)
        verifier = PhysicsVerifier(grid)
        exact_solver = ExactClassicalSolver(grid)

        # Build realistic injection vectors
        injections = {b: (grid.bus_loads.get(b, (0.0, 0.0))[0], grid.bus_loads.get(b, (0.0, 0.0))[1]) for b in grid.graph.nodes}

        # 1. Standard Nominal Baseline
        t0 = time.perf_counter()
        std_sw, _ = exact_solver.solve_unreconfigured_standard()
        ok_base, v_base, cur_base, loss_base = verifier.solve_power_flow(std_sw, injections)
        lat_base = (time.perf_counter() - t0) * 1000.0

        # 2. Classical 1-opt Branch Exchange
        t0 = time.perf_counter()
        be_sw, loss_be, lat_be = exact_solver.solve_exact_loss_minimizer(injections, max_iterations=8)
        ok_be, v_be, _, _ = verifier.solve_power_flow(be_sw, injections)
        red_be = (loss_base - loss_be) / loss_base * 100.0 if loss_base > 0 else 0.0

        # 3. Option B Hybrid Co-Processor
        coprocessor = HybridCoProcessor(
            grid=grid,
            num_reads=80,
            sweeps=100,
            top_basins=3,
            polish_iterations=5,
            use_sqa=False,
            seed=42,
        )
        t0 = time.perf_counter()
        hybrid_sw, loss_hybrid, lat_hybrid, diag = coprocessor.solve(injections)
        ok_hyb, v_hyb, _, _ = verifier.solve_power_flow(hybrid_sw, injections)
        red_hyb = (loss_base - loss_hybrid) / loss_base * 100.0 if loss_base > 0 else 0.0

        diff_kw = loss_be - loss_hybrid
        pct_improvement_over_be = (loss_be - loss_hybrid) / loss_be * 100.0 if loss_be > 0 else 0.0

        row = {
            "name": name,
            "buses": n_buses,
            "lines": n_lines,
            "ties": n_ties,
            "baseline": {
                "loss_kw": round(float(loss_base), 3),
                "ansi_valid": bool(ok_base),
                "min_v": round(float(min(v_base.values())), 4) if v_base else 1.0,
                "latency_ms": round(float(lat_base), 2),
            },
            "branch_exchange": {
                "loss_kw": round(float(loss_be), 3),
                "reduction_pct": round(float(red_be), 2),
                "ansi_valid": bool(ok_be),
                "min_v": round(float(min(v_be.values())), 4) if v_be else 1.0,
                "latency_ms": round(float(lat_be), 2),
            },
            "option_b_hybrid": {
                "loss_kw": round(float(loss_hybrid), 3),
                "reduction_pct": round(float(red_hyb), 2),
                "improvement_over_be_pct": round(float(pct_improvement_over_be), 2),
                "saved_vs_be_kw": round(float(diff_kw), 3),
                "ansi_valid": bool(ok_hyb),
                "min_v": round(float(min(v_hyb.values())), 4) if v_hyb else 1.0,
                "latency_ms": round(float(lat_hybrid), 2),
                "diagnostics": diag,
            }
        }
        results_data.append(row)

        print(f"\nGrid: {name} (N={n_buses}, M={n_lines}, Ties={n_ties})")
        print(f"  Standard Baseline:         {loss_base:8.2f} kW | Latency: {lat_base:6.1f} ms | Min V: {row['baseline']['min_v']:.4f}")
        print(f"  Classical Branch Exchange: {loss_be:8.2f} kW ({red_be:+6.2f}%) | Latency: {lat_be:6.1f} ms | Min V: {row['branch_exchange']['min_v']:.4f}")
        print(f"  Option B Hybrid Engine:    {loss_hybrid:8.2f} kW ({red_hyb:+6.2f}%) | Latency: {lat_hybrid:6.1f} ms | Min V: {row['option_b_hybrid']['min_v']:.4f}")
        print(f"  --> Delta vs Branch Exch:  {diff_kw:+8.3f} kW ({pct_improvement_over_be:+5.2f}% lower loss)")

    # Save JSON summary
    summary_file = out_path / "option_b_scaling_results.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2)
    print(f"\nSaved scaling benchmark data to: {summary_file}")

    # Generate Comparative Chart
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    x_labels = [r["name"].replace(" (", "\n(") for r in results_data]
    x_indices = np.arange(len(x_labels))
    width = 0.35

    be_reds = [r["branch_exchange"]["reduction_pct"] for r in results_data]
    hyb_reds = [r["option_b_hybrid"]["reduction_pct"] for r in results_data]

    b1 = ax1.bar(x_indices - width/2, be_reds, width, label="Classical Branch Exchange", color="#3b82f6", alpha=0.85)
    b2 = ax1.bar(x_indices + width/2, hyb_reds, width, label="Option B Hybrid Engine", color="#10b981", alpha=0.85)

    ax1.set_ylabel("Power Loss Reduction vs Baseline (%)", fontsize=11)
    ax1.set_title("Loss Reduction Across Network Scales", fontsize=12, fontweight="bold")
    ax1.set_xticks(x_indices)
    ax1.set_xticklabels(x_labels, fontsize=9)
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3, axis="y")

    # Add value annotations
    for rect in b2:
        height = rect.get_height()
        ax1.annotate(f"{height:+.1f}%",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=8, fontweight="bold")

    # Latencies
    be_lats = [r["branch_exchange"]["latency_ms"] for r in results_data]
    hyb_lats = [r["option_b_hybrid"]["latency_ms"] for r in results_data]

    ax2.plot(x_indices, be_lats, marker='o', linewidth=2, color="#3b82f6", label="Classical Branch Exchange")
    ax2.plot(x_indices, hyb_lats, marker='s', linewidth=2, color="#10b981", label="Option B Hybrid Engine")
    ax2.set_yscale("log")
    ax2.set_ylabel("Execution Latency (ms, log-scale)", fontsize=11)
    ax2.set_title("Computational Latency Across Scales", fontsize=12, fontweight="bold")
    ax2.set_xticks(x_indices)
    ax2.set_xticklabels(x_labels, fontsize=9)
    ax2.legend(loc="upper left")
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    chart_path = out_path / "option_b_scaling_comparison.png"
    fig.savefig(chart_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved comparative chart to: {chart_path}")

if __name__ == "__main__":
    run_scaling_benchmark()
