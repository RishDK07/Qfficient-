import json
import os
import sys
from pathlib import Path

# Ensure local cache for Matplotlib & Streamlit
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
os.environ["MPLCONFIGDIR"] = os.path.join(current_dir, ".mpl_cache")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from thermodynamic_grid_qubo.pipeline import (
    GRID_CHOICES, MAX_BRANCHES, MAX_BUSES, SOLVER_CHOICES,
    GridSizeError, OptimizationConfig, estimate_runtime_s, run_optimization,
)
from thermodynamic_grid_qubo.verification import report_card as rc


def _w(fn):
    """Full-width kwarg that works on both old and new Streamlit releases."""
    import inspect
    return {"width": "stretch"} if "width" in inspect.signature(fn).parameters else {"use_container_width": True}


st.set_page_config(
    page_title="Thermodynamic QUBO Microgrid Optimizer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("⚡ Thermodynamic-Mapped QUBO for Dynamic Microgrid Power Distribution")
st.markdown(
    "**Next-generation microgrid reconfiguration via non-equilibrium thermodynamics & quantum annealing (Ising / QUBO)**  \n"
    "*Set the inputs, run the optimizer, and read the result as a report card.*"
)

# ---------------------------------------------------------------------------
# Sidebar: inputs
# ---------------------------------------------------------------------------
GRID_SIZES = {"microgrid12": (12, 16), "ieee33": (33, 37)}   # (components, candidate lines)

with st.sidebar:
    st.header("🎛️ Simulation & Grid Inputs")
    grid_key = st.selectbox("Select Microgrid Architecture", list(GRID_CHOICES),
                            format_func=GRID_CHOICES.get, index=0)
    n_comp, n_lines = GRID_SIZES[grid_key]
    st.caption(f"{n_comp} components · {n_lines} candidate lines "
               f"(supported limit: {MAX_BUSES} components / {MAX_BRANCHES} lines)")

    st.subheader("☀️ Renewable & Demand Transients")
    solar_drop = st.slider("Solar PV Cloud Drop (%)", 0, 90, 75, 5)
    ev_spike = st.slider("EV Charging Depot Surge (kW)", 0, 1200, 700, 50)
    t_ambient = st.slider("Ambient Temperature (°C)", 10, 45, 25, 1)

    st.subheader("⚛️ Quantum Annealing Solver")
    solver_key = st.selectbox("Solver Engine", list(SOLVER_CHOICES), format_func=SOLVER_CHOICES.get, index=0)
    num_reads = st.slider("Quantum Reads / Annealing Shots", 100, 1000, 200, 100,
                          disabled=(solver_key == "classical"))

    cfg = OptimizationConfig(grid=grid_key, solver=solver_key, solar_drop_pct=solar_drop,
                             ev_surge_kw=ev_spike, ambient_c=t_ambient, num_reads=num_reads)
    st.caption(f"⏱️ Estimated run time ≈ {max(estimate_runtime_s(cfg, n_lines), 0.5):.0f} s "
               f"({cfg.time_steps} steps × {cfg.dt_seconds:.0f} s window)")
    run_btn = st.button("🚀 Run Thermodynamic Optimization", type="primary", **_w(st.button))

# ---------------------------------------------------------------------------
# Backend run -> session state (the report only appears once the backend is done)
# ---------------------------------------------------------------------------
if run_btn:
    bar = st.progress(0.0, text="Starting…")
    try:
        result = run_optimization(cfg, progress_cb=lambda i, n, msg: bar.progress(min(i / n, 1.0), text=msg))
        st.session_state["result"] = result
    except GridSizeError as exc:
        st.session_state.pop("result", None)
        st.error(f"Input rejected: {exc}")
    except Exception as exc:  # surface backend failures instead of showing a stale report
        st.session_state.pop("result", None)
        st.error(f"The optimizer failed: {exc}")
    finally:
        bar.empty()

result = st.session_state.get("result")

tab_report, tab_benchmark, tab_limits, tab_theory = st.tabs(
    ["📋 Report Card", "📊 Multi-Scenario Benchmark & Ablations", "📏 Input Limits & Scalability", "📐 Theoretical Physics & Datasets"]
)

# ---------------------------------------------------------------------------
# Tab 1: report card
# ---------------------------------------------------------------------------
with tab_report:
    if result is None:
        st.info("Choose your inputs in the sidebar and press **Run Thermodynamic Optimization**. "
                "The report card appears here as soon as the backend finishes.")
        ref_img = Path(current_dir) / "thermodynamic_qubo_results.png"
        if ref_img.exists():
            with st.expander("Reference benchmark image (static, from the README run — IEEE 33-bus)"):
                st.image(str(ref_img), **_w(st.image))
    else:
        grade = rc.grade_results(result)
        st.markdown(rc.header_html(result, grade), unsafe_allow_html=True)
        st.markdown(rc.kpi_cards_html(result, grade), unsafe_allow_html=True)

        # ---- network diagram --------------------------------------------------
        st.subheader("🗺️ Optimized network topology")
        times = result["time_s"]
        step = st.select_slider(
            "Inspect the network at time (s)", options=list(range(len(times))),
            value=result["peak_step"], format_func=lambda i: f"{times[i]:.0f} s",
            key=f"step_{result['run_id']}",
            help="Defaults to the moment of peak stress (highest baseline loss). Drag to watch the QUBO re-route the grid.",
        )
        fig_net = rc.render_network_figure(result, step)
        st.pyplot(fig_net, **_w(st.pyplot))
        net_png = rc.fig_to_png(fig_net)
        plt.close(fig_net)

        with st.expander("Line-by-line table for this moment"):
            st.dataframe(pd.DataFrame(rc.line_rows(result, step)), hide_index=True, **_w(st.dataframe))

        # ---- transient charts -------------------------------------------------
        st.subheader("📈 Transient behaviour")
        fig_tr = rc.render_transient_figure(result)
        st.pyplot(fig_tr, **_w(st.pyplot))
        plt.close(fig_tr)

        # ---- checklist --------------------------------------------------------
        st.subheader("✅ Verification checklist")
        st.markdown(rc.checklist_html(grade), unsafe_allow_html=True)
        with st.expander("How the overall grade is decided"):
            st.markdown(
                "- **A** – every check passes.\n"
                "- **B** – no failures, at least one warning (e.g. voltage still outside the band on some steps, or slow solver).\n"
                "- **C** – at least one failed check.\n"
                "- **D** – heat is *worse* than the baseline, the topology is not radial, or a line exceeds its ampacity."
            )

        # ---- run details & downloads -----------------------------------------
        g = result["grid"]
        st.caption(
            f"QUBO size: {g['n_qubo_vars']} binary variables · {g['n_couplings']} couplings · "
            f"{g['n_cycles']} independent loops · seed {result['config']['seed']} · run {result['run_id']}"
        )
        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇️ Report (JSON)", json.dumps(result, indent=2), f"qfficient_report_{result['run_id']}.json",
                           "application/json", **_w(st.download_button))
        timeline = pd.DataFrame({
            "time_s": result["time_s"],
            "baseline_heat_MJ": result["baseline"]["heat_mj"], "qubo_heat_MJ": result["qubo"]["heat_mj"],
            "baseline_entropy_JperK": result["baseline"]["entropy"], "qubo_entropy_JperK": result["qubo"]["entropy"],
            "baseline_peak_temp_C": result["baseline"]["peak_temp"], "qubo_peak_temp_C": result["qubo"]["peak_temp"],
            "baseline_min_voltage_pu": result["baseline"]["min_v"], "qubo_min_voltage_pu": result["qubo"]["min_v"],
            "qubo_switch_operations": result["qubo"]["toggles"], "qubo_latency_ms": result["qubo"]["latency_ms"],
        })
        d2.download_button("⬇️ Timeline (CSV)", timeline.to_csv(index=False), f"qfficient_timeline_{result['run_id']}.csv",
                           "text/csv", **_w(st.download_button))
        d3.download_button("⬇️ Network diagram (PNG)", net_png, f"qfficient_network_{result['run_id']}.png",
                           "image/png", **_w(st.download_button))

# ---------------------------------------------------------------------------
# Tab 2: Multi-Scenario Benchmark & Ablations
# ---------------------------------------------------------------------------
with tab_benchmark:
    st.subheader("📊 Rigorous Multi-Scenario Benchmark & Ablation Study")
    st.markdown(
        "Direct comparison across independent renewable/EV scenarios on the **IEEE 33-Bus benchmark**, "
        "measuring real 3-phase Joule heat dissipation ($3 I^2 R$), decision latency, and statistical significance."
    )

    bench_sum_file = Path(current_dir) / "results" / "benchmark_summary.json"
    bench_chart_file = Path(current_dir) / "results" / "benchmark_distribution.png"

    if bench_chart_file.exists():
        st.image(str(bench_chart_file), caption="Heat Dissipation (MJ) and Decision Latency (ms) across independent scenarios", **_w(st.image))

    if bench_sum_file.exists():
        with open(bench_sum_file) as f:
            bench_data = json.load(f)

        summary_dict = bench_data.get("summary", {})
        tests_dict = bench_data.get("statistical_tests", {})

        rows = []
        for policy, data in summary_dict.items():
            h = data["heat_mj"]
            t = data["peak_temp_c"]
            v = data["voltage_violation_steps"]
            lat = data["mean_decision_ms"]

            if policy == "standard_static":
                pct_str = "Baseline"
                p_str = "—"
            else:
                test = tests_dict.get(policy, {})
                red = test.get("percent_loss_reduction", 0.0)
                p_val = test.get("p_value_paired_t", 1.0)
                pct_str = f"{red:+.2f}%"
                p_str = f"{p_val:.3e}" if p_val < 0.001 else f"{p_val:.4f}"

            rows.append({
                "Policy Engine": policy,
                "Joule Heat (MJ)": f"{h['mean']:.3f} ± {h['std']:.3f}",
                "Loss Reduction vs Baseline": pct_str,
                "p-value (paired t-test)": p_str,
                "Peak Conductor Temp": f"{t['mean']:.1f} °C",
                "Voltage Violations (steps)": f"{v['mean']:.1f}",
                "Decision Latency": f"{lat['mean']:.2f} ms",
            })

        st.dataframe(pd.DataFrame(rows), hide_index=True, **_w(st.dataframe))

    st.markdown("""
    ### 🔬 Scientific Attribution & Reconciliation of the 22.27% Claim
    * **Standard Baseline vs Strawman Baseline**: The standard textbook IEEE 33-bus baseline experiences **~4.98 MJ** of heat dissipation under these profiles. Comparing against this true baseline reveals that **exact dynamic reconfiguration yields -28.37% loss reduction** ($p = 2.15 \\times 10^{-8}$).
    * **Role of Power-Flow Selection**: When 50 random radial spanning trees are sampled and evaluated via LinDistFlow (`random_trees_filtered`), they achieve **-20.06% loss reduction** ($p = 4.37 \\times 10^{-7}$). This proves that evaluating candidate trees through a power-flow selector is effective, and the previous 22.27% figure was an artifact of the power-flow filter and strawman baseline.
    * **Raw QUBO Formulation**: The raw Hamiltonian lowest-energy state (`qubo_mesh_current_raw`) produces valid radial trees, but because linear objective weights do not capture the non-linear AC/LinDistFlow network effects, exact classical or hybrid power-flow-guided selection is necessary for optimal performance.
    """)

# ---------------------------------------------------------------------------
# Tab 3: limits
# ---------------------------------------------------------------------------
with tab_limits:
    st.subheader("How many components can the program take?")
    st.markdown(
        f"""
The optimizer uses **one binary variable per candidate line** (not per component). Its radiality constraint couples
**every pair of lines**, so the QUBO has about `M·(M−1)/2` couplings for `M` lines, and anneal time grows quickly with `M`.

| Limit | Value | Where it comes from |
| :-- | :-- | :-- |
| **Max components (buses/nodes)** | **{MAX_BUSES}** | `MAX_BUSES` in `pipeline.py`, enforced by `validate_grid_size()` |
| **Max candidate lines (incl. ties)** | **{MAX_BRANCHES}** | `MAX_BRANCHES` in `pipeline.py` |
| Substations | exactly **1** | Power flow roots the tree at `substations[0]` |
| Network | must be **connected** | Otherwise no spanning tree exists |

Measured with a synthetic ring-and-tie feeder on one CPU core (100 reads, one anneal):

| Components | Lines (variables) | Couplings | Anneal time |
| --: | --: | --: | --: |
| 12 | 14 | 91 | 0.05 s |
| 33 | 42 | 861 | 0.18 s |
| 60 | 78 | 3,003 | 0.43 s |
| 100 | 132 | 8,646 | 1.0 s |
| 150 | 198 | 19,503 | 2.4 s |
| 200 | 265 | 34,980 | 4.1 s |

Those are classical simulated-annealing times; **OpenJij SQA is roughly 10× slower** per read, and a full run repeats the
anneal at every time step. The caps above keep a run in the range of minutes rather than hours. Raise them in `pipeline.py` if you need more.
"""
    )

# ---------------------------------------------------------------------------
# Tab 3: theory
# ---------------------------------------------------------------------------
with tab_theory:
    st.subheader("Theoretical Foundations & Complete Dataset Inventory")
    st.markdown(r"""
    ### 1. Mathematical Grounding
    * **Joule Heating Rate**: $\dot{Q}_e(t) = 3 \cdot I_e(t)^2 \cdot R_e(T_e(t))$
    * **Conductor Transient Heat Balance**: $C_{\text{th}} \frac{dT}{dt} = \dot{Q}_{\text{in}} - \frac{T - T_{\text{amb}}}{\theta_{\text{th}}}$
    * **Non-Equilibrium Entropy Rate**: $\dot{S}_{\text{gen},e}(t) = \frac{\dot{Q}_e(t)}{T_e(t)} = \frac{P_{\text{loss},e}}{T_e(t)}$
    * **Gouy-Stodola Exergy Destruction**: $E_{x,\text{destroyed}} = T_0 \cdot S_{\text{gen}}$
    * **Quantum Transverse Ising Model**: $H_{\text{Ising}}(s) = \sum_i h_i s_i + \sum_{i < j} J_{ij} s_i s_j + \text{Offset}$ where $x_i = \frac{s_i + 1}{2}$

    ### 2. Dataset & Physical Parameters Used
    | Parameter / Dataset | Physical Value | Engineering Significance |
    | :--- | :--- | :--- |
    | **Benchmark Grid** | IEEE 33-Bus Distribution Feeder | 33 buses, 32 branches, 5 tie lines ($V_{\text{base}} = 12.66\text{ kV}$, $S_{\text{base}} = 10\text{ MVA}$) |
    | **Smart Microgrid** | 12-Component Reconfigurable Testbed | Substation, Solar, Wind, BESS, EV Depot, Hospital, Data Center, Industry |
    | **Conductor Heat Capacity ($C_{\text{th}}$)** | $2.5 \times 10^5\text{ J/K}$ per km | Realistic ACSR overhead distribution conductor thermal mass |
    | **Thermal Resistance ($\theta_{\text{th}}$)** | $0.003\text{ K/W}$ per km | Convective and radiative cooling to ambient surroundings |
    | **Resistance Temp Coeff ($\alpha$)** | $0.00393\text{ K}^{-1}$ | Linearized thermal runaway coefficient for aluminum/copper lines |
    | **Solar PV Profile** | $450\text{ kW}$ baseline | Cloud dip between $t = 24\text{s}$ and $48\text{s}$, depth set by the sidebar slider |
    | **Fast EV Charging Depot** | surge set by the sidebar slider | Multi-vehicle high-current DC fast-charging pulse load |
    """)

st.sidebar.markdown("---")
st.sidebar.caption("⚡ Thermodynamic QUBO Distribution Engine | Antigravity Project")
