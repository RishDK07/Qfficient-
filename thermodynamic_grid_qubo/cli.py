"""
Command Line Interface (CLI) and Automation Engine for Thermodynamic QUBO Grid Reconfiguration.

Provides a rich terminal interface, automated CSV data exports, publication-grade
figure generation, and comprehensive markdown/LaTeX reports.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

import tempfile

# Configure headless matplotlib and writable cache directory
mpl_cache = Path(tempfile.gettempdir()) / "mpl_cache"
mpl_cache.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from thermodynamic_grid_qubo.pipeline import (
    OptimizationConfig,
    run_optimization,
    GRID_CHOICES,
    SOLVER_CHOICES,
)
from thermodynamic_grid_qubo.grid_engine.custom_grid_generator import generate_custom_grid


# ---------------------------------------------------------------------------
# ANSI Terminal Colors & Styling Helpers
# ---------------------------------------------------------------------------
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright Foreground
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Backgrounds
    BG_DARK = "\033[40m"
    BG_BLUE = "\033[44m"
    BG_CYAN = "\033[46m"


def box_table(title: str, headers: List[str], rows: List[List[str]], alignments: Optional[List[str]] = None) -> str:
    """Renders a Unicode box-drawing table with ANSI highlights."""
    if not alignments:
        alignments = ["left"] + ["right"] * (len(headers) - 1)
        
    # Strip ANSI escape codes to measure true string width
    def strip_ansi(s: str) -> str:
        import re
        return re.sub(r"\033\[[0-9;]*m", "", s)

    col_widths = [len(strip_ansi(h)) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(strip_ansi(cell)))

    # Add padding
    col_widths = [w + 2 for w in col_widths]
    total_w = sum(col_widths) + len(col_widths) + 1

    lines = []
    # Title bar
    lines.append(f"{Style.CYAN}┌" + "─" * (total_w - 2) + f"┐{Style.RESET}")
    title_text = f" {title} "
    lines.append(f"{Style.CYAN}│{Style.RESET}{Style.BOLD}{Style.BRIGHT_WHITE}{title_text.center(total_w - 2)}{Style.RESET}{Style.CYAN}│{Style.RESET}")
    lines.append(f"{Style.CYAN}├" + "┬".join("─" * w for w in col_widths) + f"┤{Style.RESET}")

    # Header row
    hdr_cells = []
    for h, w, align in zip(headers, col_widths, alignments):
        raw_len = len(strip_ansi(h))
        pad = w - raw_len
        if align == "right":
            cell = " " * (pad - 1) + f"{Style.BOLD}{Style.BRIGHT_CYAN}{h}{Style.RESET}" + " "
        elif align == "center":
            left_pad = pad // 2
            right_pad = pad - left_pad
            cell = " " * left_pad + f"{Style.BOLD}{Style.BRIGHT_CYAN}{h}{Style.RESET}" + " " * right_pad
        else:
            cell = " " + f"{Style.BOLD}{Style.BRIGHT_CYAN}{h}{Style.RESET}" + " " * (pad - 1)
        hdr_cells.append(cell)
    lines.append(f"{Style.CYAN}│{Style.RESET}" + f"{Style.CYAN}│{Style.RESET}".join(hdr_cells) + f"{Style.CYAN}│{Style.RESET}")
    lines.append(f"{Style.CYAN}├" + "┼".join("─" * w for w in col_widths) + f"┤{Style.RESET}")

    # Data rows
    for r_idx, row in enumerate(rows):
        cells = []
        for cell_val, w, align in zip(row, col_widths, alignments):
            raw_len = len(strip_ansi(cell_val))
            pad = w - raw_len
            if align == "right":
                c = " " * (pad - 1) + cell_val + " "
            elif align == "center":
                left_pad = pad // 2
                right_pad = pad - left_pad
                c = " " * left_pad + cell_val + " " * right_pad
            else:
                c = " " + cell_val + " " * (pad - 1)
            cells.append(c)
        lines.append(f"{Style.CYAN}│{Style.RESET}" + f"{Style.CYAN}│{Style.RESET}".join(cells) + f"{Style.CYAN}│{Style.RESET}")

    lines.append(f"{Style.CYAN}└" + "┴".join("─" * w for w in col_widths) + f"┘{Style.RESET}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Exporters: CSV, Markdown Reports, and Publication Figures
# ---------------------------------------------------------------------------
def export_csv_data(result: Dict[str, Any], output_dir: Path) -> Dict[str, Path]:
    """Exports structured simulation datasets to CSV format."""
    csv_dir = output_dir / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)
    
    run_id = result["run_id"]
    time_s = result["time_s"]
    grid = result["grid"]
    edges = grid["edges"]
    edge_labels = [e["label"] for e in edges]
    
    # 1. Switching Schedule CSV
    sched_path = csv_dir / f"run_{run_id}_switching_schedule.csv"
    with open(sched_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", "step", "baseline_loss_kw", "qubo_loss_kw", "loss_delta_kw", "loss_reduction_pct", "closed_switches", "energized_ties"])
        nTies = grid["n_ties"]
        nEdges = len(edges)
        for t_idx, t in enumerate(time_s):
            b_loss = result["baseline"]["loss_kw"][t_idx]
            q_loss = result["qubo"]["loss_kw"][t_idx]
            delta = b_loss - q_loss
            pct = (delta / b_loss * 100.0) if b_loss > 0 else 0.0
            sw = result["qubo"]["switches"][t_idx]
            closed_labels = [edge_labels[i] for i, s in enumerate(sw) if s == 1]
            energized_ties = [edge_labels[i] for i, s in enumerate(sw) if s == 1 and i >= (nEdges - nTies)]
            writer.writerow([
                f"{t:.2f}",
                t_idx,
                f"{b_loss:.4f}",
                f"{q_loss:.4f}",
                f"{delta:.4f}",
                f"{pct:.2f}%",
                ";".join(closed_labels),
                ";".join(energized_ties) if energized_ties else "None"
            ])

    # 2. Thermal & Feeder Telemetry CSV
    thermal_path = csv_dir / f"run_{run_id}_thermal_telemetry.csv"
    with open(thermal_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", "step", "edge_id", "edge_label", "u_bus", "v_bus", "status", "current_a", "i_max_a", "loading_pct", "temp_c", "loss_kw"])
        for t_idx, t in enumerate(time_s):
            sw = result["qubo"]["switches"][t_idx]
            cur = result["qubo"]["currents"][t_idx]
            temps = result["qubo"]["temps"][t_idx]
            ll = result["qubo"]["line_loss_kw"][t_idx] if "line_loss_kw" in result["qubo"] else {}
            for e_idx, edge in enumerate(edges):
                status = "CLOSED" if sw[e_idx] == 1 else "OPEN"
                i_val = cur[e_idx] if e_idx < len(cur) else 0.0
                t_val = temps[e_idx] if e_idx < len(temps) else 25.0
                i_max = edge["i_max"]
                load_pct = (i_val / i_max * 100.0) if i_max > 0 else 0.0
                l_kw = ll.get(edge["id"], 0.0) if isinstance(ll, dict) else 0.0
                writer.writerow([
                    f"{t:.2f}", t_idx, edge["id"], edge["label"], edge["u"], edge["v"],
                    status, f"{i_val:.2f}", f"{i_max:.1f}", f"{load_pct:.1f}%", f"{t_val:.2f}", f"{l_kw:.4f}"
                ])

    # 3. Overall KPI Summary CSV
    kpi_path = csv_dir / f"run_{run_id}_kpi_summary.csv"
    with open(kpi_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "baseline_value", "qubo_value", "delta_value", "delta_percent"])
        sumry = result["summary"]
        b = sumry["baseline"]
        q = sumry["qubo"]
        writer.writerow(["total_heat_dissipation_mj", f"{b['total_heat_mj']:.6f}", f"{q['total_heat_mj']:.6f}", f"{b['total_heat_mj'] - q['total_heat_mj']:.6f}", f"{sumry['heat_reduction_pct']:.2f}%"])
        writer.writerow(["entropy_generation_jk", f"{b['total_entropy_jk']:.4f}", f"{q['total_entropy_jk']:.4f}", f"{b['total_entropy_jk'] - q['total_entropy_jk']:.4f}", f"{sumry['entropy_reduction_pct']:.2f}%"])
        writer.writerow(["exergy_destroyed_mj", f"{b['exergy_destroyed_mj']:.6f}", f"{q['exergy_destroyed_mj']:.6f}", f"{sumry['exergy_saved_mj']:.6f}", "N/A"])
        writer.writerow(["peak_temperature_c", f"{b['peak_temp_c']:.2f}", f"{q['peak_temp_c']:.2f}", f"{sumry['peak_temp_reduction_c']:.2f}", "N/A"])
        writer.writerow(["voltage_violations", b["voltage_violations"], q["voltage_violations"], 0, "0.0%"])
        writer.writerow(["avg_solver_latency_ms", f"{b['avg_latency_ms']:.2f}", f"{q['avg_latency_ms']:.2f}", f"{q['avg_latency_ms'] - b['avg_latency_ms']:.2f}", "N/A"])

    return {"schedule": sched_path, "thermal": thermal_path, "kpi": kpi_path}


def export_markdown_report(result: Dict[str, Any], output_dir: Path) -> Path:
    """Generates an academic and engineering report in GitHub-flavored Markdown."""
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    run_id = result["run_id"]
    grid = result["grid"]
    sumry = result["summary"]
    b = sumry["baseline"]
    q = sumry["qubo"]
    n_buses = grid["n_buses"]
    
    report_path = reports_dir / f"run_{run_id}_{n_buses}_components_report.md"

    heat_saved_kj = (b['total_heat_mj'] - q['total_heat_mj']) * 1000.0
    entropy_red_jk = b['total_entropy_jk'] - q['total_entropy_jk']
    exergy_saved_kj = sumry['exergy_saved_mj'] * 1000.0
    status_heat = 'Optimal' if sumry['heat_reduction_pct'] >= 0 else 'Nominal'
    status_entropy = 'Reduced' if sumry['entropy_reduction_pct'] >= 0 else 'Nominal'
    tree_status = 'PASSED (All trees connected with N-1 active branches)' if result['checks']['radial_all_steps'] else 'FAILED'
    
    status_temp = "Thermal Relief" if sumry['peak_temp_reduction_c'] >= 0 else "Temperature Rise"
    v_viol_b = b.get('voltage_violations', 0)
    v_viol_q = q.get('voltage_violations', 0)
    status_volt = "100% Compliant" if v_viol_q == 0 else f"{v_viol_q} Violations"
    b_volt_str = "100% Compliant" if v_viol_b == 0 else f"{v_viol_b} Violations"
    delta_volt_str = "0 Violations" if v_viol_q == 0 else f"{v_viol_q - v_viol_b:+d} Violations"
    volt_security = "Strict Security" if v_viol_q == 0 else "Non-Compliant"
    latency_feasible = "Real-time Feasible" if q['avg_latency_ms'] < 1000.0 else "Batch Mode"
    latency_target = "< 1.0s" if q['avg_latency_ms'] < 1000.0 else "> 1.0s"

    duration_s = result["time_s"][-1] if result["time_s"] else 0.0
    reconfigs = result['checks']['reconfigurations']
    if reconfigs > 0:
        telemetry_narrative = f"Over the {duration_s:.0f}-second simulation horizon, the solver dynamically executed {reconfigs} switch operations, transferring power flows across parallel tie lines."
    else:
        telemetry_narrative = f"Over the {duration_s:.0f}-second simulation horizon, the solver maintained the baseline radial topology with 0 switch operations."

    md_content = f"""# Thermodynamic QUBO Grid Optimization Report

**Run Identifier:** `{run_id}`  
**Network Architecture:** {grid['title']}  
**Dimension:** {grid['n_buses']} Buses | {grid['n_lines']} Total Lines | {grid['n_ties']} Tie Switches  
**QUBO Variables:** {grid['n_qubo_vars']} Binary Decision Variables | {grid['n_couplings']} Couplers  
**Solver Engine:** {result['solver_label']}  
**Execution Timestamp:** {time.strftime('%Y-%m-%d %H:%M:%S')}  

---

## 1. Executive Summary

This report evaluates the thermodynamic loss minimization of a **{n_buses}-bus radial distribution grid** subject to time-varying photovoltaic generation and concentrated electric vehicle charging surges. The distribution topology was evaluated to minimize non-equilibrium Joule heat dissipation $\\dot{{Q}} = \\sum 3 I_e^2 R_e$ while evaluating radiality, Kirchhoff's current/voltage laws, and ANSI C84.1 voltage tolerances.

### Key Performance Indicators (KPIs)
* **Total Joule Heat Saved:** `{sumry['heat_reduction_pct']:+.2f}%` ({heat_saved_kj:.2f} kJ)
* **Entropy Generation Reduction:** `{sumry['entropy_reduction_pct']:+.2f}%` ({entropy_red_jk:.2f} J/K)
* **Exergy Preserved:** `{exergy_saved_kj:.2f} kJ` of available electrical work
* **ANSI C84.1 Voltage Violations:** `{v_viol_q} violations` across all time steps (0.95 <= V_pu <= 1.05)
* **Mean Solver Dispatch Latency:** `{q['avg_latency_ms']:.1f} ms` per reconfiguration cycle

---

## 2. Technical & Thermodynamic Benchmark

| Dimension | Baseline Radial Grid | Thermodynamic QUBO | Optimization Delta | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Total Joule Dissipation** | `{b['total_heat_mj']:.4f} MJ` | `{q['total_heat_mj']:.4f} MJ` | `{sumry['heat_reduction_pct']:+.2f}%` | {status_heat} |
| **Thermodynamic Entropy (S_gen)** | `{b['total_entropy_jk']:.2f} J/K` | `{q['total_entropy_jk']:.2f} J/K` | `{sumry['entropy_reduction_pct']:+.2f}%` | {status_entropy} |
| **Exergy Destruction (B_dest)** | `{b['exergy_destroyed_mj']:.4f} MJ` | `{q['exergy_destroyed_mj']:.4f} MJ` | `+{exergy_saved_kj:.2f} kJ preserved` | Preserved |
| **Peak Conductor Temp** | `{b['peak_temp_c']:.2f} °C` | `{q['peak_temp_c']:.2f} °C` | `ΔT = {sumry['peak_temp_reduction_c']:+.2f} °C` | {status_temp} |
| **ANSI C84.1 Voltage Security** | `{b_volt_str}` | `{status_volt}` | `{delta_volt_str}` | {volt_security} |
| **Mean Solver Latency** | `{b['avg_latency_ms']:.2f} ms` | `{q['avg_latency_ms']:.1f} ms` | {latency_feasible} | {latency_target} |

---

## 3. Dynamic Reconfiguration Telemetry

{telemetry_narrative}

* **Total Breaker Switch Operations:** `{reconfigs}` operations
* **Active Radial Tree Constraint Check:** `{tree_status}`
* **Branch Overload Occurrences:** `{result['checks']['overload_line_steps_qubo']}` overloads (Baseline: `{result['checks']['overload_line_steps_base']}`)

---

## 4. Engineering Takeaway

By formulating the feeder reconfiguration problem with thermodynamic penalty bounds, the system seeks to prevent localized conductor heating and Joule losses without violating graph radiality. Conductor thermal dissipation is tracked, preserving useful exergy and maintaining grid stability during peak EV and solar transient events.
"""
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    return report_path


def export_publication_figures(result: Dict[str, Any], output_dir: Path) -> Dict[str, Path]:
    """Renders 300 DPI publication-grade vector plots."""
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    
    run_id = result["run_id"]
    time_s = result["time_s"]
    grid = result["grid"]
    
    # 1. Transient Power Loss & Dissipation Comparison
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True, dpi=300)
    fig.patch.set_facecolor("#ffffff")

    b_loss = result["baseline"]["loss_kw"]
    q_loss = result["qubo"]["loss_kw"]
    loss_saved = np.array(b_loss) - np.array(q_loss)

    ax1.plot(time_s, b_loss, color="#e11d48", linestyle="--", linewidth=1.8, label="Baseline Radial Grid", marker="o", markersize=3)
    ax1.plot(time_s, q_loss, color="#059669", linewidth=2.2, label="Thermodynamic QUBO Reconfiguration", marker="s", markersize=3)
    ax1.set_ylabel("Active Power Loss (kW)", fontsize=11, fontweight="bold")
    ax1.set_title(f"Dynamic Power Loss & Joule Heat Minimization ({grid['title']})", fontsize=12, fontweight="bold")
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="upper right", frameon=True)

    ax2.bar(time_s, loss_saved, width=1.4, color=["#10b981" if v >= 0 else "#f59e0b" for v in loss_saved], alpha=0.85, label="Net Power Saved (kW)")
    ax2.axhline(0, color="#64748b", linewidth=0.8)
    ax2.set_xlabel("Simulation Time (seconds)", fontsize=11, fontweight="bold")
    ax2.set_ylabel("Power Saved ΔP (kW)", fontsize=11, fontweight="bold")
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="upper right", frameon=True)

    plt.tight_layout()
    trans_path = fig_dir / f"run_{run_id}_power_loss_transient.png"
    plt.savefig(trans_path, dpi=300)
    plt.close()

    # 2. Network Topology Plot
    fig, ax = plt.subplots(figsize=(11, 8), dpi=300)
    fig.patch.set_facecolor("#ffffff")
    
    pos = grid.get("positions", {})
    roles = grid.get("node_roles", {})
    edges = grid.get("edges", [])
    switches = result["qubo"]["switches"][0]
    nTies = grid["n_ties"]
    nEdges = len(edges)

    role_colors = {
        "substation": "#9333ea",
        "solar": "#f59e0b",
        "wind": "#06b6d4",
        "battery": "#10b981",
        "ev": "#3b82f6",
        "load": "#64748b"
    }

    # Draw edges
    for idx, e in enumerate(edges):
        p1 = pos.get(str(e["u"]))
        p2 = pos.get(str(e["v"]))
        if not p1 or not p2:
            continue
        is_tie = idx >= (nEdges - nTies)
        is_closed = switches[idx] == 1
        
        if is_closed:
            if is_tie:
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color="#10b981", linewidth=2.8, linestyle="-", zorder=2, label="Active Tie Switch" if idx == (nEdges - nTies) else "")
            else:
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color="#0284c7", linewidth=1.6, linestyle="-", zorder=1)
        else:
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color="#cbd5e1", linewidth=1.0, linestyle=":", zorder=0, label="Open Switch" if idx == 0 else "")

    # Draw nodes
    for k, (x, y) in pos.items():
        r = roles.get(k, "load")
        c = role_colors.get(r, "#64748b")
        size = 180 if r == "substation" else (120 if r in ["solar", "wind", "battery", "ev"] else 60)
        ax.scatter(x, y, s=size, color=c, edgecolor="#1e293b", linewidth=1.2, zorder=3)
        ax.annotate(k, (x, y), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=7, fontweight="bold", color="#334155")

    ax.set_title(f"Network Reconfiguration Topology: {grid['title']}", fontsize=12, fontweight="bold")
    ax.axis("off")
    plt.tight_layout()
    topo_path = fig_dir / f"run_{run_id}_network_topology.png"
    plt.savefig(topo_path, dpi=300)
    plt.close()

    return {"transient": trans_path, "topology": topo_path}


# ---------------------------------------------------------------------------
# Terminal Display Functions
# ---------------------------------------------------------------------------
def print_terminal_results(result: Dict[str, Any], output_paths: Optional[Dict[str, Any]] = None):
    """Prints formatted executive summaries directly to terminal stdout."""
    grid = result["grid"]
    sumry = result["summary"]
    b = sumry["baseline"]
    q = sumry["qubo"]
    
    # 1. Header Banner
    banner = f"""
{Style.BOLD}{Style.BRIGHT_CYAN}========================================================================================={Style.RESET}
{Style.BOLD}{Style.BRIGHT_WHITE}   THERMODYNAMIC QUBO POWER DISTRIBUTION RECONFIGURATION ENGINE{Style.RESET}
{Style.CYAN}   Joule Dissipation Minimization | Entropy Generation Reduction | SQA Annealing{Style.RESET}
{Style.BOLD}{Style.BRIGHT_CYAN}========================================================================================={Style.RESET}
"""
    print(banner)

    # 2. Grid Architecture Table
    qubo_desc = (
        f"{grid['n_qubo_vars']} Binary Decision Variables | {grid['n_couplings']} Couplers | {grid['n_cycles']} Cycles"
        if grid['n_qubo_vars'] > 0
        else "Classical Power-Flow Search / Branch Exchange"
    )
    dim_rows = [
        [f"{Style.BOLD}Grid Model{Style.RESET}", grid["title"]],
        [f"{Style.BOLD}Network Dimensions{Style.RESET}", f"{grid['n_buses']} Buses | {grid['n_lines']} Total Branches | {grid['n_ties']} Available Tie Switches"],
        [f"{Style.BOLD}QUBO Formulation{Style.RESET}", qubo_desc],
        [f"{Style.BOLD}Optimization Engine{Style.RESET}", f"{result['solver_label']}"],
        [f"{Style.BOLD}Radiality Integrity{Style.RESET}", f"{Style.BRIGHT_GREEN}STRICTLY RADIAL (All {len(result['time_s'])} steps connected, 0 cycles){Style.RESET}" if result['checks']['radial_all_steps'] else f"{Style.BRIGHT_RED}VIOLATION DETECTED{Style.RESET}"],
        [f"{Style.BOLD}Breaker Operations{Style.RESET}", f"{result['checks']['reconfigurations']} dynamic switch operations executed"],
        [f"{Style.BOLD}Total Wallclock Runtime{Style.RESET}", f"{result['runtime_s']:.2f} seconds"]
    ]
    print(box_table("1. NETWORK SPECIFICATION & FORMULATION", ["Parameter", "Specification Details"], dim_rows, ["left", "left"]))
    print()

    # 3. Technical & Thermodynamic Benchmark Table
    heat_color = Style.BRIGHT_GREEN if sumry['heat_reduction_pct'] >= 0 else Style.BRIGHT_YELLOW
    heat_sign = "+" if sumry['heat_reduction_pct'] >= 0 else ""

    temp_delta = sumry['peak_temp_reduction_c']
    temp_status = f"{Style.BRIGHT_GREEN}Thermal Relief ({temp_delta:+.2f} °C){Style.RESET}" if temp_delta >= 0 else f"{Style.YELLOW}Conductor Heated ({temp_delta:+.2f} °C){Style.RESET}"

    v_viol_b = b.get('voltage_violations', 0)
    v_viol_q = q.get('voltage_violations', 0)
    b_v_str = f"100% Compliant (0 Viols)" if v_viol_b == 0 else f"{v_viol_b} Viols"
    q_v_str = f"100% Compliant (0 Viols)" if v_viol_q == 0 else f"{v_viol_q} Viols"
    v_delta_color = Style.BRIGHT_GREEN if v_viol_q <= v_viol_b else Style.BRIGHT_RED
    v_delta_str = f"{v_delta_color}{v_viol_q - v_viol_b:+d} Viols{Style.RESET}" if v_viol_q != v_viol_b else f"{Style.BRIGHT_GREEN}Baseline Preserved{Style.RESET}"

    lat_str = f"{Style.BRIGHT_CYAN}Real-Time Feasible (< 1.0s){Style.RESET}" if q['avg_latency_ms'] < 1000.0 else f"{Style.YELLOW}Batch Feasible ({q['avg_latency_ms']/1000:.1f}s){Style.RESET}"

    bench_rows = [
        [
            f"{Style.BOLD}Total Joule Heat Dissipation{Style.RESET}",
            f"{b['total_heat_mj']:.4f} MJ",
            f"{q['total_heat_mj']:.4f} MJ",
            f"{heat_color}{heat_sign}{sumry['heat_reduction_pct']:.2f}% ({- (q['total_heat_mj'] - b['total_heat_mj'])*1000:.2f} kJ saved){Style.RESET}"
        ],
        [
            f"{Style.BOLD}Thermodynamic Entropy (S_gen){Style.RESET}",
            f"{b['total_entropy_jk']:.2f} J/K",
            f"{q['total_entropy_jk']:.2f} J/K",
            f"{heat_color}{heat_sign}{sumry['entropy_reduction_pct']:.2f}% ({- (q['total_entropy_jk'] - b['total_entropy_jk']):.2f} J/K){Style.RESET}"
        ],
        [
            f"{Style.BOLD}Exergy Destroyed (B_dest){Style.RESET}",
            f"{b['exergy_destroyed_mj']:.4f} MJ",
            f"{q['exergy_destroyed_mj']:.4f} MJ",
            f"{Style.BRIGHT_GREEN}+{sumry['exergy_saved_mj']*1000:.2f} kJ work preserved{Style.RESET}"
        ],
        [
            f"{Style.BOLD}Peak Conductor Temperature{Style.RESET}",
            f"{b['peak_temp_c']:.2f} °C",
            f"{q['peak_temp_c']:.2f} °C",
            f"{temp_status}"
        ],
        [
            f"{Style.BOLD}ANSI C84.1 Voltage Security{Style.RESET}",
            f"{b_v_str}",
            f"{q_v_str}",
            f"{v_delta_str}"
        ],
        [
            f"{Style.BOLD}Mean Solver Dispatch Latency{Style.RESET}",
            f"{b['avg_latency_ms']:.2f} ms",
            f"{q['avg_latency_ms']:.1f} ms",
            f"{lat_str}"
        ],
    ]
    print(box_table("2. THERMODYNAMIC & OPERATIONAL BENCHMARK", ["Metric Dimension", "Baseline Radial", "Thermodynamic QUBO", "Optimization Delta"], bench_rows, ["left", "right", "right", "right"]))
    print()

    # 4. Switching Event Schedule (Sample Steps)
    sched_rows = []
    edges = grid["edges"]
    nTies = grid["n_ties"]
    nEdges = len(edges)
    edge_labels = [e["label"] for e in edges]

    for t_idx in [0, len(result["time_s"])//4, len(result["time_s"])//2, 3*len(result["time_s"])//4, len(result["time_s"])-1]:
        t_val = result["time_s"][t_idx]
        b_loss = result["baseline"]["loss_kw"][t_idx]
        q_loss = result["qubo"]["loss_kw"][t_idx]
        delta_loss = b_loss - q_loss
        pct = (delta_loss / b_loss * 100.0) if b_loss > 0 else 0.0
        sw = result["qubo"]["switches"][t_idx]
        energized_ties = [edge_labels[i] for i, s in enumerate(sw) if s == 1 and i >= (nEdges - nTies)]
        ties_str = ", ".join(energized_ties) if energized_ties else "None (Base Radial)"
        
        sched_rows.append([
            f"Step {t_idx+1:02d} (t={t_val:.1f}s)",
            f"{b_loss:.3f} kW",
            f"{q_loss:.3f} kW",
            f"{Style.BRIGHT_GREEN if delta_loss >= 0 else Style.YELLOW}{delta_loss:+.3f} kW ({pct:+.1f}%){Style.RESET}",
            f"{Style.BRIGHT_CYAN}{ties_str}{Style.RESET}"
        ])

    print(box_table("3. SWITCHING TELEMETRY (DYNAMIC TIME PROFILE SAMPLES)", ["Simulation Step", "Base Loss", "QUBO Loss", "Loss Delta", "Active Energized Ties"], sched_rows, ["left", "right", "right", "right", "left"]))
    print()

    # 5. Export Artifacts Summary
    if output_paths:
        print(f"{Style.BOLD}{Style.BRIGHT_WHITE}4. GENERATED EXPORT ARTIFACTS:{Style.RESET}")
        if "csv" in output_paths:
            for k, p in output_paths["csv"].items():
                print(f"   {Style.GREEN}● CSV Dataset:{Style.RESET}      {p.as_uri()}")
        if "report" in output_paths:
            print(f"   {Style.CYAN}● Markdown Report:{Style.RESET}  {output_paths['report'].as_uri()}")
        if "figures" in output_paths:
            for k, p in output_paths["figures"].items():
                print(f"   {Style.MAGENTA}● Publication Plot:{Style.RESET} {p.as_uri()}")
        print()


# ---------------------------------------------------------------------------
# CLI Command Entrypoint
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Thermodynamic QUBO Grid Reconfiguration CLI & Batch Execution Suite"
    )
    parser.add_argument("--components", "-n", type=int, default=60, help="Number of buses/components (default: 60)")
    parser.add_argument("--grid", "-g", type=str, default="custom", choices=list(GRID_CHOICES.keys()), help="Grid architecture")
    parser.add_argument("--solver", "-s", type=str, default="sqa", choices=list(SOLVER_CHOICES.keys()), help="Annealing solver")
    parser.add_argument("--solar", type=int, default=None, help="Number of solar generation nodes")
    parser.add_argument("--wind", type=int, default=None, help="Number of wind turbine nodes")
    parser.add_argument("--battery", type=int, default=None, help="Number of battery storage nodes")
    parser.add_argument("--ev", type=int, default=None, help="Number of EV charging depot nodes")
    parser.add_argument("--ties", "-k", type=int, default=None, help="Number of available tie lines")
    parser.add_argument("--steps", "-t", type=int, default=20, help="Number of simulation time steps (default: 20)")
    parser.add_argument("--reads", "-r", type=int, default=40, help="Number of annealer reads (default: 40)")
    parser.add_argument("--sweep", action="store_true", help="Run parametric scaling sweep across sizes [20, 40, 60, 80, 100]")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactively enter microgrid components")
    parser.add_argument("--no-csv", action="store_true", help="Disable CSV dataset export")
    parser.add_argument("--no-report", action="store_true", help="Disable Markdown report export")
    parser.add_argument("--no-figures", action="store_true", help="Disable publication figure export")
    default_results = str(Path(__file__).resolve().parent.parent / "results")
    parser.add_argument("--output-dir", "-o", type=str, default=default_results, help="Directory for exported outputs")

    args = parser.parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Interactive input for custom grid components if requested or if run without args in interactive TTY
    if (args.interactive or (len(sys.argv) == 1 and sys.stdin.isatty())) and not args.sweep:
        print(f"\n{Style.BOLD}{Style.BRIGHT_CYAN}⚡ Custom Microgrid Optimizer (10 to 100 Components){Style.RESET}")
        try:
            raw = input(f"Enter number of components (10 to 100) [default {args.components}]: ").strip()
            if raw:
                args.components = int(raw)
        except (ValueError, EOFError, KeyboardInterrupt):
            pass

    if args.grid == "custom":
        if not (10 <= args.components <= 100):
            print(f"{Style.BRIGHT_RED}Error: Custom grid component count must be between 10 and 100 (got {args.components}).{Style.RESET}")
            sys.exit(1)

    # -----------------------------------------------------------------------
    # Parametric Sweep Mode
    # -----------------------------------------------------------------------
    if args.sweep:
        print(f"\n{Style.BOLD}{Style.BRIGHT_CYAN}=== RUNNING PARAMETRIC SCALING SWEEP ==={Style.RESET}")
        sizes = [20, 40, 60, 80, 100]
        sweep_rows = []
        benchmark_csv_path = out_dir / "csv" / "parametric_scaling_benchmark.csv"
        benchmark_csv_path.parent.mkdir(parents=True, exist_ok=True)
        
        sweep_data = []
        for n in sizes:
            sys.stdout.write(f"  Optimizing {n}-component grid... ")
            sys.stdout.flush()
            t0 = time.perf_counter()
            cfg = OptimizationConfig(
                grid="custom",
                solver=args.solver,
                time_steps=args.steps,
                num_reads=args.reads,
                custom_n_components=n
            )
            res = run_optimization(cfg)
            elapsed = time.perf_counter() - t0
            sumry = res["summary"]
            heat_pct = sumry["heat_reduction_pct"]
            reconfigs = res["checks"]["reconfigurations"]
            qubo_lat = sumry["qubo"]["avg_latency_ms"]
            radial = "PASS" if res["checks"]["radial_all_steps"] else "FAIL"

            sweep_rows.append([
                f"{n} Buses",
                f"{res['grid']['n_ties']} Ties",
                f"{heat_pct:+.2f}%",
                f"{sumry['entropy_reduction_pct']:+.2f}%",
                f"{reconfigs} Ops",
                f"{qubo_lat:.1f} ms",
                f"{radial}",
                f"{elapsed:.2f}s"
            ])
            sweep_data.append([n, res['grid']['n_ties'], heat_pct, sumry['entropy_reduction_pct'], reconfigs, qubo_lat, radial, elapsed])
            print(f"{Style.GREEN}Done! ({elapsed:.1f}s, {heat_pct:+.2f}% heat saved){Style.RESET}")

        # Save sweep CSV
        with open(benchmark_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["n_buses", "n_ties", "heat_reduction_pct", "entropy_reduction_pct", "switch_operations", "qubo_latency_ms", "radiality_status", "runtime_s"])
            for row in sweep_data:
                writer.writerow(row)

        print()
        print(box_table("PARAMETRIC SCALING BENCHMARK RESULTS", ["Network Size", "Tie Lines", "Heat Saved", "Entropy Red.", "Switch Ops", "SQA Latency", "Radiality", "Wallclock"], sweep_rows))
        print(f"\n{Style.GREEN}● Scaling Benchmark CSV saved to:{Style.RESET} {benchmark_csv_path.as_uri()}\n")
        return

    # -----------------------------------------------------------------------
    # Single Run Mode
    # -----------------------------------------------------------------------
    print(f"\n{Style.CYAN}Initializing simulation for {args.components}-component network...{Style.RESET}")
    
    cfg = OptimizationConfig(
        grid=args.grid,
        solver=args.solver,
        time_steps=args.steps,
        num_reads=args.reads,
        custom_n_components=args.components,
        custom_n_solar=args.solar,
        custom_n_wind=args.wind,
        custom_n_battery=args.battery,
        custom_n_ev=args.ev,
        custom_n_ties=args.ties
    )

    t_start = time.perf_counter()
    result = run_optimization(cfg)
    total_time = time.perf_counter() - t_start

    # Export outputs
    output_paths = {}
    if not args.no_csv:
        output_paths["csv"] = export_csv_data(result, out_dir)
    if not args.no_report:
        output_paths["report"] = export_markdown_report(result, out_dir)
    if not args.no_figures:
        output_paths["figures"] = export_publication_figures(result, out_dir)

    # Print terminal display
    print_terminal_results(result, output_paths)


if __name__ == "__main__":
    main()
