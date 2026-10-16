"""Standalone runner for large-scale custom microgrids (10 to 100 components).

Usage:
    python run_custom_grid.py --components 60
    python run_custom_grid.py --components 80 --ties 8
    python run_custom_grid.py --components 100 --solver exact_oracle
"""
import argparse
import time
from pathlib import Path

from thermodynamic_grid_qubo.grid_engine.custom_grid_generator import generate_custom_grid
from thermodynamic_grid_qubo.pipeline import OptimizationConfig, run_optimization
from thermodynamic_grid_qubo.verification import report_card as rc


def main():
    parser = argparse.ArgumentParser(description="Run optimization on custom 10-100 component microgrids.")
    parser.add_argument("--components", type=int, default=60, help="Total components/buses (10 to 100)")
    parser.add_argument("--ties", type=int, default=6, help="Normally open tie lines")
    parser.add_argument("--solver", type=str, default="exact_oracle",
                        choices=["exact_oracle", "numpy_annealer", "classical"],
                        help="Solver engine to use")
    parser.add_argument("--steps", type=int, default=15, help="Time steps to simulate")
    parser.add_argument("--save-diagram", action="store_true", default=True, help="Save PNG topology diagram")
    args = parser.parse_args()

    n = args.components
    if not (10 <= n <= 100):
        print(f"Error: Components must be between 10 and 100 (got {n})")
        return

    print(f"\n=======================================================")
    print(f" Generating Custom {n}-Component Microgrid with {args.ties} Tie Lines")
    print(f"=======================================================")

    t0 = time.time()
    # Generate custom grid
    grid = generate_custom_grid(
        n_components=n,
        n_solar=max(2, n // 15),
        n_wind=max(2, n // 20),
        n_battery=max(2, n // 20),
        n_ev=max(2, n // 20),
        n_ties=args.ties,
        seed=42,
    )

    print(f"Grid created in {(time.time() - t0)*1000:.1f} ms:")
    print(f" - Buses / Components: {len(grid.graph.nodes)} (1 Substation, {len(grid.der_nodes)} DER nodes)")
    print(f" - Candidate Lines: {len(grid.lines)} ({n-1} distribution branches + {args.ties} tie switches)")

    cfg = OptimizationConfig(
        grid="custom",
        solver=args.solver,
        time_steps=args.steps,
        custom_n_components=n,
        custom_n_ties=args.ties,
        custom_grid=grid,
    )

    print(f"\nRunning Optimization with '{args.solver}' over {args.steps} time steps...")
    result = run_optimization(cfg, progress_cb=lambda i, tot, msg: print(f" [{i}/{tot}] {msg}", end="\r"))
    print("\nOptimization completed!")

    # Summary metrics
    b_heat = sum(result["baseline"]["heat_mj"])
    q_heat = sum(result["qubo"]["heat_mj"])
    pct_red = ((b_heat - q_heat) / b_heat) * 100.0 if b_heat > 0 else 0.0

    print("\n---------------- Performance Summary ----------------")
    print(f" Baseline Joule Heat Dissipation:   {b_heat:.3f} MJ")
    print(f" Reconfigured Heat Dissipation:     {q_heat:.3f} MJ")
    print(f" Heat Reduction Achieved:           {pct_red:+.2f}%")
    print(f" Peak Baseline Loss:                {max(result['baseline']['loss_kw']):.2f} kW")
    print(f" Peak Reconfigured Loss:            {max(result['qubo']['loss_kw']):.2f} kW")
    print(f" Min Voltage (Baseline):            {min(result['baseline']['min_v']):.4f} pu")
    print(f" Voltage Violations (<0.95 pu):     {'None (All Compliant)' if result['checks'].get('voltage_all_steps') else 'Present'}")
    import numpy as np
    mean_lat = float(np.mean(result["qubo"]["latency_ms"])) if result["qubo"]["latency_ms"] else 0.0
    print(f" Average Decision Latency:          {mean_lat:.2f} ms")

    if args.save_diagram:
        fig = rc.render_network_figure(result, step=0)
        out_file = f"custom_microgrid_{n}.png"
        fig.savefig(out_file, dpi=200, bbox_inches="tight")
        print(f"\nSaved {n}-component topology diagram to: {Path(out_file).resolve()}")


if __name__ == "__main__":
    main()
