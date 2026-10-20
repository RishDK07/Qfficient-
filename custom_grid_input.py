"""Interactive Custom Microgrid Runner (10 to 100 Components).

Allows entering ANY number of microgrid components (buses) from 10 to 100,
runs thermodynamic QUBO / branch-exchange optimization, and provides
the full physical and thermodynamic report card with diagrams.

Usage:
    python custom_grid_input.py             # Prompts interactively
    python custom_grid_input.py 45          # Direct positional argument
    python custom_grid_input.py -n 75       # Flag argument
    python custom_grid_input.py -n 100 --solver exact_oracle
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from thermodynamic_grid_qubo.grid_engine.custom_grid_generator import generate_custom_grid
from thermodynamic_grid_qubo.pipeline import (
    MAX_BUSES,
    OptimizationConfig,
    SOLVER_CHOICES,
    run_optimization,
)
from thermodynamic_grid_qubo.verification import report_card as rc


def prompt_component_count(default: int = 60) -> int:
    """Interactively prompts the user to enter any number of components from 10 to 100."""
    print("=" * 70)
    print(" ⚡ THERMODYNAMIC MICROGRID CUSTOM COMPONENT RUNNER (10 - 100)")
    print("=" * 70)
    while True:
        try:
            val_str = input(f"Enter number of components (10 to 100) [default {default}]: ").strip()
            if not val_str:
                return default
            val = int(val_str)
            if 10 <= val <= MAX_BUSES:
                return val
            print(f"⚠️  Out of bounds: Please enter an integer between 10 and {MAX_BUSES} (received {val}).")
        except ValueError:
            print("⚠️  Invalid input: Please enter a valid integer (e.g., 25, 42, 60, 100).")
        except (KeyboardInterrupt, EOFError):
            print("\nAborted by user.")
            sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Enter any number of components (10 to 100) and optimize custom microgrid."
    )
    parser.add_argument(
        "pos_components",
        nargs="?",
        type=int,
        default=None,
        help="Number of components/buses (10 to 100) as positional argument",
    )
    parser.add_argument(
        "--components",
        "-n",
        type=int,
        default=None,
        help="Number of components/buses (10 to 100)",
    )
    parser.add_argument(
        "--ties",
        "-k",
        type=int,
        default=None,
        help="Number of normally open tie switches (default: auto)",
    )
    parser.add_argument(
        "--solver",
        "-s",
        type=str,
        default="exact_oracle",
        choices=list(SOLVER_CHOICES.keys()),
        help="Optimization engine to use (default: exact_oracle)",
    )
    parser.add_argument(
        "--steps",
        "-t",
        type=int,
        default=15,
        help="Number of transient simulation steps (default: 15)",
    )
    parser.add_argument(
        "--reads",
        "-r",
        type=int,
        default=100,
        help="Number of annealer reads (default: 100)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible grid topology and transients",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Open generated diagram images in the default system viewer",
    )
    args = parser.parse_args()

    # Determine component count: flag > positional > interactive prompt
    n = args.components if args.components is not None else args.pos_components
    if n is None:
        if sys.stdin.isatty():
            n = prompt_component_count(default=60)
        else:
            n = 60
    elif not (10 <= n <= MAX_BUSES):
        print(f"Error: Component count must be between 10 and {MAX_BUSES} (received {n}).")
        sys.exit(1)

    ties = args.ties if args.ties is not None else max(2, min(14, int(round(n * 0.12))))

    print(f"\n[+] Building custom microgrid with {n} components and {ties} candidate tie switches...")
    t0 = time.perf_counter()
    grid = generate_custom_grid(
        n_components=n,
        n_solar=max(2, n // 15),
        n_wind=max(2, n // 20),
        n_battery=max(2, n // 20),
        n_ev=max(2, n // 20),
        n_ties=ties,
        seed=args.seed,
    )
    gen_time_ms = (time.perf_counter() - t0) * 1000.0

    print(f"    Grid generated in {gen_time_ms:.1f} ms:")
    print(f"    - Nodes: {len(grid.graph.nodes)} (1 Substation slack bus, {len(grid.der_nodes)} DER buses)")
    print(f"    - Lines: {len(grid.lines)} ({n - 1} base branches + {ties} tie switches)")

    cfg = OptimizationConfig(
        grid="custom",
        solver=args.solver,
        time_steps=args.steps,
        num_reads=args.reads,
        custom_n_components=n,
        custom_n_ties=ties,
        custom_grid=grid,
        seed=args.seed,
    )

    print(f"\n[+] Executing {args.solver} optimization over {args.steps} transient time steps...")
    result = run_optimization(
        cfg, progress_cb=lambda i, tot, msg: print(f"    Step [{i}/{tot}] {msg}", end="\r")
    )
    print("\n[+] Optimization run completed!")

    grade = rc.grade_results(result)
    g = result["grid"]
    s = result["summary"]
    b, q = s["baseline"], s["qubo"]
    chk = result["checks"]

    print("\n" + "=" * 78)
    print(f" OPTIMIZATION RESULTS: {n}-COMPONENT CUSTOM MICROGRID")
    print("=" * 78)
    print(f" Executive Grade:        Grade {grade['overall']} ({grade['headline']})")
    print(f" Total Components:       {n} buses (1 Substation, {len(grid.der_nodes)} DER resources)")
    print(f" Candidate Line Pool:    {g['n_lines']} lines ({n - 1} distribution branches + {ties} tie switches)")
    print(f" Active Tree Lines:      {n - 1} lines energized (Strictly Radial Tree: N - 1)")
    print(f" Radiality Verification: {'100% PASS (All time steps radial and fully connected)' if chk['radial_all_steps'] else 'FAIL'}")
    print(f" Dynamic Breaker Ops:    {chk['reconfigurations']} switch operations executed")
    print(f" Solver Latency:         {q['avg_latency_ms']:.2f} ms/step")
    print(f" Total Wallclock Time:   {result['runtime_s']:.2f} seconds")
    print("-" * 78)
    print(" PHYSICAL & THERMODYNAMIC PERFORMANCE METRICS:")
    print(f"  ● Joule Heat Dissipated: {rc.fmt_energy_mj(b['total_heat_mj'])} -> {rc.fmt_energy_mj(q['total_heat_mj'])} ({s['heat_reduction_pct']:+.2f}%)")
    print(f"  ● Energy Saved:          {(b['total_heat_mj'] - q['total_heat_mj']) * 1000:+.2f} kJ preserved")
    print(f"  ● Entropy Generation:    {b['total_entropy_jk'] / 1000:.3f} -> {q['total_entropy_jk'] / 1000:.3f} kJ/K ({s['entropy_reduction_pct']:+.2f}%)")
    print(f"  ● Exergy Preserved:      {s['exergy_saved_mj'] * 1000:+.2f} kJ (Gouy-Stodola: T0 * Delta_S)")
    print(f"  ● Peak Conductor Temp:   {b['peak_temp_c']:.2f} °C -> {q['peak_temp_c']:.2f} °C (Thermal relief: {-s['peak_temp_reduction_c']:+.2f} °C)")
    print(f"  ● Feeder Min Voltage:    {min(result['baseline']['min_v']):.4f} pu -> {min(result['qubo']['min_v']):.4f} pu (ANSI 0.95-1.05 pu)")
    viol_c = q.get("voltage_violations", 0)
    print(f"  ● Voltage Compliance:    {'100% ANSI Compliant (0 violations)' if viol_c == 0 else f'{viol_c} steps non-compliant'}")
    print(f"  ● Line Overloads:        Baseline: {chk['overload_line_steps_base']} steps | Reconfigured: {chk['overload_line_steps_qubo']} steps")
    print("-" * 78)

    # Save visual topology and transient plots
    topo_file = Path(f"custom_microgrid_{n}.png")
    fig_net = rc.render_network_figure(result)
    fig_net.savefig(topo_file, dpi=200, bbox_inches="tight")
    print(f"[+] Saved network topology diagram to: {topo_file.resolve()}")

    trans_file = Path(f"custom_microgrid_{n}_transient.png")
    fig_tr = rc.render_transient_figure(result)
    fig_tr.savefig(trans_file, dpi=200, bbox_inches="tight")
    print(f"[+] Saved transient performance charts to: {trans_file.resolve()}")
    print("=" * 78 + "\n")

    # Automatically open or offer to open images
    should_open = args.show
    if not should_open and sys.stdin.isatty():
        try:
            ans = input("Would you like to open the generated diagrams now? [y/N]: ").strip().lower()
            should_open = ans in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            pass

    if should_open:
        try:
            import os
            if sys.platform.startswith("win"):
                os.startfile(str(topo_file.resolve()))
                os.startfile(str(trans_file.resolve()))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", str(topo_file.resolve())])
                subprocess.Popen(["open", str(trans_file.resolve())])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(topo_file.resolve())])
                subprocess.Popen(["xdg-open", str(trans_file.resolve())])
            print("[+] Opened diagrams in default image viewer.")
        except Exception as exc:
            print(f"[-] Could not launch image viewer: {exc}")


if __name__ == "__main__":
    main()
