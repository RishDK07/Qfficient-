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
    import sys
    parser = argparse.ArgumentParser(description="Run optimization on custom 10-100 component microgrids.")
    parser.add_argument("--components", "-n", type=int, default=None, help="Total components/buses (10 to 100)")
    parser.add_argument("--ties", "-k", type=int, default=None, help="Normally open tie lines (default: auto)")
    parser.add_argument("--solver", "-s", type=str, default="exact_oracle",
                        choices=["exact_oracle", "numpy_annealer", "classical", "sqa", "neal", "hybrid_co_processor"],
                        help="Solver engine to use")
    parser.add_argument("--steps", "-t", type=int, default=15, help="Time steps to simulate")
    parser.add_argument("--save-diagram", action="store_true", default=True, help="Save PNG topology diagram")
    args = parser.parse_args()

    n = args.components
    if n is None:
        if sys.stdin.isatty():
            print("\n=======================================================")
            print(" ⚡ Custom Microgrid Optimizer: 10 to 100 Components")
            print("=======================================================")
            while True:
                try:
                    val = input("Enter number of components (10 to 100) [default: 60]: ").strip()
                    if not val:
                        n = 60
                        break
                    n = int(val)
                    if 10 <= n <= 100:
                        break
                    print(f"Error: Components must be between 10 and 100 (got {n}). Please try again.")
                except ValueError:
                    print("Error: Please enter a valid integer.")
                except (EOFError, KeyboardInterrupt):
                    return
        else:
            n = 60
    elif not (10 <= n <= 100):
        print(f"Error: Components must be between 10 and 100 (got {n})")
        return

    ties = args.ties if args.ties is not None else max(2, min(14, int(round(n * 0.12))))

    print(f"\n=======================================================")
    print(f" Generating Custom {n}-Component Microgrid with {ties} Tie Lines")
    print(f"=======================================================")

    t0 = time.time()
    # Generate custom grid
    grid = generate_custom_grid(
        n_components=n,
        n_solar=max(2, n // 15),
        n_wind=max(2, n // 20),
        n_battery=max(2, n // 20),
        n_ev=max(2, n // 20),
        n_ties=ties,
        seed=42,
    )

    print(f"Grid created in {(time.time() - t0)*1000:.1f} ms:")
    print(f" - Buses / Components: {len(grid.graph.nodes)} (1 Substation, {len(grid.der_nodes)} DER nodes)")
    print(f" - Candidate Lines: {len(grid.lines)} ({n-1} distribution branches + {ties} tie switches)")

    cfg = OptimizationConfig(
        grid="custom",
        solver=args.solver,
        time_steps=args.steps,
        custom_n_components=n,
        custom_n_ties=ties,
        custom_grid=grid,
    )

    print(f"\nRunning Optimization with '{args.solver}' over {args.steps} time steps...")
    result = run_optimization(cfg, progress_cb=lambda i, tot, msg: print(f" [{i}/{tot}] {msg}", end="\r"))
    print("\nOptimization completed!")

    # Summary metrics
    s_sum = result["summary"]
    b_sum, q_sum = s_sum["baseline"], s_sum["qubo"]
    b_heat = b_sum["total_heat_mj"]
    q_heat = q_sum["total_heat_mj"]
    pct_red = s_sum["heat_reduction_pct"]

    print("\n---------------- Performance Summary ----------------")
    print(f" Components (Buses):                {n} (1 Substation, {len(grid.der_nodes)} DERs)")
    print(f" Candidate Lines:                   {len(grid.lines)} ({n-1} base + {ties} ties)")
    print(f" All Steps Radial Tree:             {'PASS (100% Valid)' if result['checks']['radial_all_steps'] else 'FAIL'}")
    print(f" Switch Operations Executed:        {result['checks']['reconfigurations']} reconfigurations")
    print(f" Baseline Joule Heat Dissipation:   {b_heat:.4f} MJ")
    print(f" Reconfigured Heat Dissipation:     {q_heat:.4f} MJ")
    print(f" Heat Reduction Achieved:           {pct_red:+.2f}% ({(b_heat - q_heat)*1000:+.2f} kJ saved)")
    print(f" Thermodynamic Entropy Reduction:   {s_sum['entropy_reduction_pct']:+.2f}%")
    print(f" Exergy Preserved (Gouy-Stodola):   {s_sum['exergy_saved_mj']*1000:+.2f} kJ")
    print(f" Peak Baseline Loss:                {max(result['baseline']['loss_kw']):.2f} kW")
    print(f" Peak Reconfigured Loss:            {max(result['qubo']['loss_kw']):.2f} kW")
    print(f" Peak Conductor Temperature Delta:  {-s_sum['peak_temp_reduction_c']:+.2f} °C")
    print(f" Min Voltage (Baseline):            {min(result['baseline']['min_v']):.4f} pu")
    print(f" Min Voltage (Reconfigured):        {min(result['qubo']['min_v']):.4f} pu")
    viol_count = q_sum.get("voltage_violations", 0)
    print(f" Voltage Violations (<0.95 pu):     {'None (All Compliant)' if viol_count == 0 else str(viol_count) + ' steps'}")
    print(f" Average Decision Latency:          {q_sum['avg_latency_ms']:.2f} ms")

    if args.save_diagram:
        fig = rc.render_network_figure(result, step=0)
        out_file = f"custom_microgrid_{n}.png"
        fig.savefig(out_file, dpi=200, bbox_inches="tight")
        print(f"\nSaved {n}-component topology diagram to: {Path(out_file).resolve()}")
        fig_tr = rc.render_transient_figure(result)
        out_tr = f"custom_microgrid_{n}_transient.png"
        fig_tr.savefig(out_tr, dpi=200, bbox_inches="tight")
        print(f"Saved {n}-component transient charts to: {Path(out_tr).resolve()}")


if __name__ == "__main__":
    main()
