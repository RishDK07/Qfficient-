"""
Report-card rendering for a finished Qfficient run.

Everything here consumes the dict returned by `pipeline.run_optimization`
and produces (a) a grade / checklist, (b) HTML cards, (c) matplotlib figures.
"""
from __future__ import annotations

import html
import io
import os
from typing import Any, Dict, List, Optional

if "MPLCONFIGDIR" not in os.environ:
    _d = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".mpl_cache"))
    os.environ["MPLCONFIGDIR"] = _d
    os.makedirs(_d, exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D

HEAT_TARGET_PCT = 5.0          # hypothesis used by MetricsEvaluator
TEMP_LIMIT_C = 90.0            # thermal rating used in main_experiment.py
LATENCY_TARGET_MS = 100.0      # target printed by MetricsEvaluator
ANSI_LOW, ANSI_HIGH = 0.95, 1.05

STATUS_STYLE = {
    "PASS": ("#15803d", "#dcfce7"),
    "WARN": ("#b45309", "#fef3c7"),
    "FAIL": ("#b91c1c", "#fee2e2"),
    "INFO": ("#374151", "#e5e7eb"),
}
GRADE_COLOR = {"A": "#15803d", "B": "#65a30d", "C": "#d97706", "D": "#b91c1c"}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def fmt_energy_mj(mj: float) -> str:
    return f"{mj * 1000:.1f} kJ" if abs(mj) < 0.1 else f"{mj:.3f} MJ"


def fmt_pct(p: float) -> str:
    return f"{p:+.2f}%"


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------
def grade_results(res: Dict[str, Any]) -> Dict[str, Any]:
    s, b, q = res["summary"], res["summary"]["baseline"], res["summary"]["qubo"]
    chk = res["checks"]
    heat = s["heat_reduction_pct"]
    ent = s["entropy_reduction_pct"]
    is_classical = res["config"]["solver"] == "classical"

    def status_for_reduction(pct: float) -> str:
        if is_classical:
            return "INFO"
        return "PASS" if pct >= HEAT_TARGET_PCT else ("WARN" if pct >= 0 else "FAIL")

    if q["voltage_violations"] == 0:
        v_status = "PASS"
    elif q["voltage_violations"] < b["voltage_violations"]:
        v_status = "WARN"          # improved, but not yet compliant
    elif q["voltage_violations"] == b["voltage_violations"]:
        v_status = "WARN"
    else:
        v_status = "FAIL"

    steps = len(res["time_s"])
    checks: List[Dict[str, str]] = [
        {"label": "Joule heat reduction", "status": status_for_reduction(heat),
         "value": f"{fmt_pct(-heat)}", "target": f"≥ {HEAT_TARGET_PCT:.0f}% reduction vs. baseline"},
        {"label": "Entropy generation", "status": status_for_reduction(ent),
         "value": f"{fmt_pct(-ent)}", "target": "Lower than baseline (Gouy–Stodola)"},
        {"label": "Peak conductor temperature",
         "status": "FAIL" if q["peak_temp_c"] >= TEMP_LIMIT_C else ("PASS" if s["peak_temp_reduction_c"] >= 0 else "WARN"),
         "value": f"{q['peak_temp_c']:.1f} °C", "target": f"< {TEMP_LIMIT_C:.0f} °C and not above baseline"},
        {"label": "Voltage compliance (ANSI C84.1)", "status": v_status,
         "value": f"{q['voltage_violations']} of {steps} steps outside band (baseline {b['voltage_violations']})",
         "target": f"{ANSI_LOW}–{ANSI_HIGH} p.u. at every bus"},
        {"label": "Line ampacity", "status": "PASS" if chk["overload_line_steps_qubo"] == 0 else "FAIL",
         "value": f"{chk['overload_line_steps_qubo']} overloaded line-steps (baseline {chk['overload_line_steps_base']})",
         "target": "No line above rated current"},
        {"label": "Radial topology", "status": "PASS" if chk["radial_all_steps"] else "FAIL",
         "value": "Valid spanning tree at every step" if chk["radial_all_steps"] else "Invalid topology produced",
         "target": "Connected, loop-free"},
        {"label": "Switching activity", "status": "INFO",
         "value": f"{chk['reconfigurations']} switch operations over {steps} steps", "target": "Fewer operations = less breaker wear"},
        {"label": "Solver latency", "status": "INFO" if is_classical else ("PASS" if q["avg_latency_ms"] < LATENCY_TARGET_MS else "WARN"),
         "value": f"{q['avg_latency_ms']:.0f} ms per reconfiguration", "target": f"< {LATENCY_TARGET_MS:.0f} ms"},
    ]

    hard_fail = (not is_classical and heat < 0) or not chk["radial_all_steps"] or chk["overload_line_steps_qubo"] > 0
    fails = sum(c["status"] == "FAIL" for c in checks)
    warns = sum(c["status"] == "WARN" for c in checks)
    if hard_fail:
        overall = "D"
    elif fails:
        overall = "C"
    elif warns:
        overall = "B"
    else:
        overall = "A"

    if is_classical:
        headline = "Classical baseline only — no QUBO optimization was applied."
    elif heat >= HEAT_TARGET_PCT:
        headline = f"Target met: {heat:.1f}% less Joule heat and {ent:.1f}% less entropy than the static baseline."
    elif heat >= 0:
        headline = f"Marginal gain: {heat:.1f}% heat reduction is below the {HEAT_TARGET_PCT:.0f}% target."
    else:
        headline = f"Regression: the optimized plan dissipates {abs(heat):.1f}% MORE heat than the baseline."

    return {"overall": overall, "headline": headline, "checks": checks}


# ---------------------------------------------------------------------------
# HTML blocks
# ---------------------------------------------------------------------------
CSS = """<style>
.rc-wrap{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#111827}
.rc-head{display:flex;gap:20px;align-items:center;background:#ffffff;border:1px solid #d1d5db;border-radius:14px;padding:18px 22px;margin-bottom:14px}
.rc-grade{flex:0 0 84px;height:84px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:44px;font-weight:800;color:#fff}
.rc-title{font-size:20px;font-weight:700;margin:0 0 2px 0;color:#111827}
.rc-sub{font-size:13px;color:#4b5563;margin:0}
.rc-headline{font-size:15px;margin:6px 0 0 0;color:#111827;font-weight:600}
.rc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin-bottom:14px}
.rc-card{background:#ffffff;border:1px solid #d1d5db;border-radius:12px;padding:14px 16px}
.rc-lbl{font-size:12px;color:#4b5563;text-transform:uppercase;letter-spacing:.04em}
.rc-val{font-size:26px;font-weight:800;margin:4px 0 2px 0}
.rc-det{font-size:12.5px;color:#4b5563}
.rc-chip{display:inline-block;font-size:11px;font-weight:700;border-radius:999px;padding:2px 9px;margin-left:6px;vertical-align:middle}
.rc-table{width:100%;border-collapse:collapse;background:#ffffff;border:1px solid #d1d5db;border-radius:12px;overflow:hidden;font-size:13.5px}
.rc-table th{background:#f3f4f6;color:#374151;text-align:left;padding:8px 12px;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.rc-table td{padding:9px 12px;border-top:1px solid #e5e7eb;color:#111827}
</style>"""


def _chip(status: str) -> str:
    fg, bg = STATUS_STYLE[status]
    return f'<span class="rc-chip" style="color:{fg};background:{bg}">{status}</span>'


def header_html(res: Dict[str, Any], grade: Dict[str, Any]) -> str:
    g, cfg = res["grid"], res["config"]
    sub = (f'{html.escape(g["title"])} · {g["n_buses"]} components · {g["n_lines"]} candidate lines · '
           f'{html.escape(res["solver_label"])} · solar drop {cfg["solar_drop_pct"]:.0f}% · EV surge {cfg["ev_surge_kw"]:.0f} kW · '
           f'ambient {cfg["ambient_c"]:.0f} °C · computed in {res["runtime_s"]:.1f} s')
    return (CSS + '<div class="rc-wrap"><div class="rc-head">'
            f'<div class="rc-grade" style="background:{GRADE_COLOR[grade["overall"]]}">{grade["overall"]}</div>'
            '<div><p class="rc-title">Optimization Report Card</p>'
            f'<p class="rc-sub">{sub}</p>'
            f'<p class="rc-headline">{html.escape(grade["headline"])}</p></div></div></div>')


def kpi_cards_html(res: Dict[str, Any], grade: Dict[str, Any]) -> str:
    s = res["summary"]
    b, q = s["baseline"], s["qubo"]
    st = {c["label"]: c["status"] for c in grade["checks"]}

    def card(label, value, detail, status):
        color = STATUS_STYLE[status][0]
        return (f'<div class="rc-card"><div class="rc-lbl">{label}{_chip(status)}</div>'
                f'<div class="rc-val" style="color:{color}">{value}</div><div class="rc-det">{detail}</div></div>')

    cards = [
        card("Total Joule heat", fmt_pct(-s["heat_reduction_pct"]),
             f'{fmt_energy_mj(b["total_heat_mj"])} → {fmt_energy_mj(q["total_heat_mj"])}', st["Joule heat reduction"]),
        card("Entropy generation", fmt_pct(-s["entropy_reduction_pct"]),
             f'{b["total_entropy_jk"] / 1000:.3f} → {q["total_entropy_jk"] / 1000:.3f} kJ/K', st["Entropy generation"]),
        card("Exergy preserved", f'{"+" if s["exergy_saved_mj"] >= 0 else "−"}{fmt_energy_mj(abs(s["exergy_saved_mj"]))}',
             "Gouy–Stodola: T₀ · ΔS", "INFO" if s["exergy_saved_mj"] >= 0 else "WARN"),
        card("Peak conductor temp", f'{q["peak_temp_c"]:.1f} °C',
             f'baseline {b["peak_temp_c"]:.1f} °C · Δ {-s["peak_temp_reduction_c"]:+.2f} °C', st["Peak conductor temperature"]),
        card("Voltage violations", f'{q["voltage_violations"]}',
             f'baseline {b["voltage_violations"]} steps · limit {ANSI_LOW}–{ANSI_HIGH} p.u.', st["Voltage compliance (ANSI C84.1)"]),
        card("Solver latency", f'{q["avg_latency_ms"]:.0f} ms',
             f'per reconfiguration · {res["checks"]["reconfigurations"]} switch ops', st["Solver latency"]),
    ]
    return '<div class="rc-wrap"><div class="rc-grid">' + "".join(cards) + "</div></div>"


def checklist_html(grade: Dict[str, Any]) -> str:
    rows = "".join(
        f'<tr><td>{html.escape(c["label"])}</td><td>{_chip(c["status"])}</td>'
        f'<td>{html.escape(c["value"])}</td><td style="color:#4b5563">{html.escape(c["target"])}</td></tr>'
        for c in grade["checks"])
    return ('<div class="rc-wrap"><table class="rc-table"><thead><tr><th>Check</th><th>Result</th>'
            f'<th>Measured</th><th>Target</th></tr></thead><tbody>{rows}</tbody></table></div>')


# ---------------------------------------------------------------------------
# Line table (for st.dataframe)
# ---------------------------------------------------------------------------
def line_rows(res: Dict[str, Any], step: int) -> List[Dict[str, Any]]:
    g, q = res["grid"], res["qubo"]
    base_sw = res["baseline"]["switches"]
    rows = []
    for k, e in enumerate(g["edges"]):
        now, was = q["switches"][step][k], base_sw[k]
        change = ("Closed by QUBO" if now and not was else "Opened by QUBO" if was and not now
                  else "Active" if now else "Standby")
        cur = q["currents"][step][k] if now else 0.0
        rows.append({
            "Line": e["label"],
            "From": g["node_labels"][e["u"]], "To": g["node_labels"][e["v"]],
            "Status": change,
            "Current (A)": round(cur, 1),
            "Loading (%)": round(100 * cur / e["i_max"], 1),
            "Loss (kW)": round(q["line_loss_kw"][step][k], 3) if now else 0.0,
            "Temp (°C)": round(q["temps"][step][k], 2),
        })
    return rows


# ---------------------------------------------------------------------------
# Network diagram — drawn from the solver's actual switch states
# ---------------------------------------------------------------------------
ROLE_STYLE = {
    "substation": ("#1f2937", "s", "Substation"),
    "pv": ("#facc15", "o", "Solar PV"),
    "wind": ("#38bdf8", "o", "Wind"),
    "bess": ("#a78bfa", "o", "Battery (BESS)"),
    "ev": ("#2dd4bf", "o", "EV depot"),
    "load": ("#e8f1ff", "o", "Load / junction"),
}
LOAD_CMAP = LinearSegmentedColormap.from_list("loading", ["#16803c", "#f59e0b", "#dc2626"])


def render_network_figure(res: Dict[str, Any], step: Optional[int] = None) -> plt.Figure:
    g, q = res["grid"], res["qubo"]
    step = res["peak_step"] if step is None else int(step)
    n = g["n_buses"]
    base_sw = res["baseline"]["switches"]

    graph = nx.Graph()
    graph.add_nodes_from(g["node_labels"])
    pos = {int(k): tuple(v) for k, v in g["positions"].items()}
    cats: Dict[str, List] = {"kept": [], "closed": [], "opened": [], "standby": []}
    loading, loss_lbl = {}, {}
    for k, e in enumerate(g["edges"]):
        now, was = q["switches"][step][k], base_sw[k]
        key = (e["u"], e["v"])
        cats["kept" if now and was else "closed" if now else "opened" if was else "standby"].append(key)
        if now:
            loading[key] = min(q["currents"][step][k] / e["i_max"], 1.2)
        loss_lbl[key] = (e["label"], q["line_loss_kw"][step][k] if now else 0.0, bool(now))

    small = n <= 15
    fig, ax = plt.subplots(figsize=(12, 7) if small else (13, 9))
    node_size = 1500 if small else (650 if n <= 40 else 220)
    font = 8.5 if small else (7 if n <= 40 else 5)

    nx.draw_networkx_edges(graph, pos, edgelist=cats["standby"], ax=ax, edge_color="#b8c0cc",
                           width=1.8, style="dashed", alpha=0.85)
    nx.draw_networkx_edges(graph, pos, edgelist=cats["opened"], ax=ax, edge_color="#dc2626",
                           width=2.2, style="dashed")
    for key in cats["kept"] + cats["closed"]:
        base_w = 2.5 + 4.0 * min(loading[key], 1.0)
        color = LOAD_CMAP(min(loading[key], 1.0)) if key in cats["kept"] else "#2563eb"
        nx.draw_networkx_edges(graph, pos, edgelist=[key], ax=ax, edge_color=[color], width=base_w)

    for role, (color, shape, _label) in ROLE_STYLE.items():
        nodes = [b for b, r in g["node_roles"].items() if r == role]
        if nodes:
            nx.draw_networkx_nodes(graph, pos, nodelist=nodes, ax=ax, node_color=color, node_shape=shape,
                                   edgecolors="#234a73", linewidths=1.4, node_size=node_size)
    labels = {int(b): t for b, t in g["node_labels"].items()}
    if small:   # names are long: print them under each node on a white tag
        ys = [p[1] for p in pos.values()]
        off = 0.062 * (max(ys) - min(ys))
        for b, text in labels.items():
            ax.text(pos[b][0], pos[b][1] - off, text, ha="center", va="top", fontsize=font, weight="bold",
                    color="#111827", bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.85})
    else:       # bus numbers fit inside the node; keep them readable on the dark substation square
        light = [b for b, r in g["node_roles"].items() if r == "substation"]
        nx.draw_networkx_labels(graph, pos, labels={b: labels[b] for b in labels if b not in light}, ax=ax,
                                font_size=font, font_weight="bold", font_color="#111827")
        nx.draw_networkx_labels(graph, pos, labels={b: labels[b] for b in light}, ax=ax,
                                font_size=font, font_weight="bold", font_color="#ffffff")

    # Line labels: all of them on small grids, otherwise only the five lossiest active lines
    top5 = set(sorted((k for k, v in loss_lbl.items() if v[2]), key=lambda k: -loss_lbl[k][1])[:5])
    for key, (name, loss, active) in loss_lbl.items():
        if not small and key not in top5:
            continue
        if small and not active:
            text, color = name, "#475569"
        else:
            text, color = (f"{name}\n{loss:.2f} kW" if small else f"{loss:.2f} kW"), "#14532d"
        (x1, y1), (x2, y2) = pos[key[0]], pos[key[1]]
        ax.text((x1 + x2) / 2, (y1 + y2) / 2, text, fontsize=font - 1, color=color, ha="center", va="center",
                bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.85})

    roles_present = {r for r in g["node_roles"].values()}
    handles = [
        Line2D([], [], color="#16803c", lw=4, label="Active (colour = loading)"),
        Line2D([], [], color="#2563eb", lw=4, label="Closed by QUBO (vs. baseline)"),
        Line2D([], [], color="#dc2626", lw=2.2, ls="--", label="Opened by QUBO (vs. baseline)"),
        Line2D([], [], color="#b8c0cc", lw=2, ls="--", label="Standby candidate"),
    ] + [Line2D([], [], marker=ROLE_STYLE[r][1], ls="", markerfacecolor=ROLE_STYLE[r][0], markeredgecolor="#234a73",
                markersize=9, label=ROLE_STYLE[r][2]) for r in ROLE_STYLE if r in roles_present]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=True, fontsize=9)

    sm = ScalarMappable(norm=Normalize(0, 100), cmap=LOAD_CMAP)
    cbar = fig.colorbar(sm, ax=ax, fraction=0.025, pad=0.02, shrink=0.5, anchor=(0.0, 0.1))
    cbar.set_label("Line loading (% of ampacity)", fontsize=9)

    n_active = sum(q["switches"][step])
    n_changed = len(cats["closed"]) + len(cats["opened"])
    t_s = res["time_s"][step]
    tag = "  ·  peak-stress moment" if step == res["peak_step"] else ""
    ax.set_title(f'{g["title"]} — optimized topology at t = {t_s:.0f} s{tag}', fontsize=14, weight="bold")
    ax.text(0.01, 0.01, f"Components: {n}  |  Active lines: {n_active} of {g['n_lines']}  |  "
                        f"Re-routed vs. baseline: {n_changed}", transform=ax.transAxes, fontsize=9.5,
            color="#374151", weight="bold")
    ax.axis("off")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Transient charts
# ---------------------------------------------------------------------------
def render_transient_figure(res: Dict[str, Any]) -> plt.Figure:
    t = np.array(res["time_s"])
    B, Q = res["baseline"], res["qubo"]
    reduction = res["summary"]["heat_reduction_pct"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5))

    ax = axes[0, 0]
    cb, cq = np.cumsum(B["heat_mj"]), np.cumsum(Q["heat_mj"])
    ax.plot(t, cb, "r--", lw=2, label="Classical baseline (static R)")
    ax.plot(t, cq, "b-", lw=2.5, label="Thermodynamic QUBO")
    ax.fill_between(t, cq, cb, where=cb >= cq, color="green", alpha=0.15, label=f"Heat saved ({reduction:.1f}%)")
    ax.set_title("Cumulative Joule heat Q(t)", weight="bold"); ax.set_ylabel("MJ")

    ax = axes[0, 1]
    ax.plot(t, np.cumsum(B["entropy"]) / 1000, color="crimson", ls="--", lw=2, label="Classical baseline")
    ax.plot(t, np.cumsum(Q["entropy"]) / 1000, color="teal", lw=2.5, label="Thermodynamic QUBO")
    ax.set_title("Accumulated entropy generation S_gen(t)", weight="bold"); ax.set_ylabel("kJ/K")

    ax = axes[1, 0]
    ax.plot(t, B["peak_temp"], color="orange", ls="--", lw=2, label="Baseline hotspot")
    ax.plot(t, Q["peak_temp"], color="darkblue", lw=2.5, label="QUBO hotspot")
    ax.set_title("Peak conductor temperature", weight="bold"); ax.set_ylabel("°C")

    ax = axes[1, 1]
    ax.plot(t, B["min_v"], color="crimson", ls="--", lw=2, label="Baseline")
    ax.plot(t, Q["min_v"], color="navy", lw=2.5, label="QUBO")
    ax.axhline(ANSI_LOW, color="red", ls=":", label=f"ANSI lower ({ANSI_LOW} p.u.)")
    ax.set_title("Lowest bus voltage over time", weight="bold"); ax.set_ylabel("p.u.")

    switch_t = [tt for tt, k in zip(t, Q["toggles"]) if k]
    for a in axes.flat:
        a.set_xlabel("Elapsed time (s)")
        a.grid(True, ls=":", alpha=0.6)
        for tt in switch_t:
            a.axvline(tt, color="#9ca3af", lw=0.8, alpha=0.5)
        a.legend(loc="best", fontsize=8.5)
    fig.suptitle("Transient behaviour (grey ticks = steps where the QUBO re-routed the network)", fontsize=11, y=0.995)
    fig.tight_layout()
    return fig


def fig_to_png(fig: plt.Figure, dpi: int = 200) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    return buf.getvalue()
