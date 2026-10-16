import os
from pathlib import Path
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ["MPLCONFIGDIR"] = os.path.join(current_dir, ".mpl_cache")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import matplotlib.pyplot as plt
from thermodynamic_grid_qubo.pipeline import run_optimization, OptimizationConfig
from thermodynamic_grid_qubo.verification import report_card as rc

def main():
    cfg = OptimizationConfig(
        grid="custom",
        custom_n_components=60,
        custom_n_solar=5,
        custom_n_wind=4,
        custom_n_battery=3,
        custom_n_ev=4,
        custom_n_ties=6,
        solver="neal",
        num_reads=200,
        time_steps=20,
        dt_seconds=2.0,
        seed=42
    )

    print("Starting 60-component Custom Grid optimization...")
    result = run_optimization(cfg, progress_cb=lambda i, n, msg: print(f"[{i}/{n}] {msg}") if i % 5 == 0 or i == n else None)

    grade = rc.grade_results(result)
    g = result["grid"]
    s = result["summary"]
    b, q = s["baseline"], s["qubo"]
    chk = result["checks"]

    print("\n" + "=" * 75)
    print("OPTIMIZATION REPORT CARD: 60-COMPONENT CUSTOM MICROGRID")
    print("=" * 75)
    print(f"Overall Grade:        {grade['overall']}")
    print(f"Headline:             {grade['headline']}")
    print(f"Components (Buses):   {g['n_buses']}")
    print(f"Candidate Lines:      {g['n_lines']} ({g['n_buses'] - 1} base branches + {g['n_ties']} tie switches)")
    peak_active = sum(result["qubo"]["switches"][result["peak_step"]])
    print(f"Active Lines/Tree:    {peak_active} lines (Radial Spanning Tree: exactly N - 1 = {g['n_buses'] - 1})")
    print(f"All Steps Radial:     {chk['radial_all_steps']}")
    print(f"Switch Operations:    {chk['reconfigurations']}")
    print(f"Solver Latency:       {q['avg_latency_ms']:.1f} ms/step")
    print(f"Runtime:              {result['runtime_s']:.2f} s")
    print("-" * 75)
    print("KEY PERFORMANCE INDICATORS (KPIs):")
    print(f"  - Joule Heat:       {rc.fmt_energy_mj(b['total_heat_mj'])} -> {rc.fmt_energy_mj(q['total_heat_mj'])} ({s['heat_reduction_pct']:+.2f}%)")
    print(f"  - Entropy Gen:      {b['total_entropy_jk']/1000:.3f} -> {q['total_entropy_jk']/1000:.3f} kJ/K ({s['entropy_reduction_pct']:+.2f}%)")
    print(f"  - Exergy Preserved: {s['exergy_saved_mj']*1000:+.1f} kJ (Gouy-Stodola: T0 * Delta_S)")
    print(f"  - Peak Temp:        {b['peak_temp_c']:.1f} °C -> {q['peak_temp_c']:.1f} °C (Delta: {-s['peak_temp_reduction_c']:+.2f} °C)")
    print(f"  - Min Voltage:      {min(result['baseline']['min_v']):.4f} p.u. -> {min(result['qubo']['min_v']):.4f} p.u. (ANSI C84.1 band: 0.95 - 1.05)")
    print(f"  - Overloaded Lines: Baseline {chk['overload_line_steps_base']} | QUBO {chk['overload_line_steps_qubo']}")
    print("-" * 75)
    print("VERIFICATION CHECKLIST:")
    for c in grade["checks"]:
        print(f"  [{c['status']:4s}] {c['label']:32s}: {c['value']} | Target: {c['target']}")
    print("=" * 75)

    # Render and save figures
    fig_net = rc.render_network_figure(result)
    net_path = Path("custom_60_network.png")
    fig_net.savefig(net_path, dpi=200, bbox_inches="tight")
    plt.close(fig_net)
    print(f"\nNetwork diagram saved to: {net_path.resolve()} ({net_path.stat().st_size} bytes)")

    fig_tr = rc.render_transient_figure(result)
    tr_path = Path("custom_60_transient.png")
    fig_tr.savefig(tr_path, dpi=200, bbox_inches="tight")
    plt.close(fig_tr)
    print(f"Transient charts saved to: {tr_path.resolve()} ({tr_path.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
