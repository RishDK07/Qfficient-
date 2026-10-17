import os
import sys
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def create_document():
    doc = Document()
    
    # Page Setup: Normal 1-inch margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Styles Setup
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = RGBColor(0x22, 0x22, 0x22)
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(6)

    # Title
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(18)
    title_p.paragraph_format.space_after = Pt(4)
    run_icon = title_p.add_run("⚡ ")
    run_icon.font.size = Pt(26)
    run_title = title_p.add_run("Qfficient: System Manual & Technical Reference")
    run_title.font.name = 'Calibri'
    run_title.font.size = Pt(26)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(0x00, 0x33, 0x66)

    # Subtitle
    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(14)
    run_sub = sub_p.add_run("Thermodynamic-Mapped QUBO for Dynamic Microgrid Distribution\nNext-Generation Power Routing via Non-Equilibrium Thermodynamics & Quantum Annealing")
    run_sub.font.size = Pt(13)
    run_sub.font.italic = True
    run_sub.font.color.rgb = RGBColor(0x44, 0x66, 0x88)

    # Horizontal Rule
    p_hr = doc.add_paragraph()
    p_hr_border = parse_xml(f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="12" w:space="1" w:color="003366"/></w:pBdr>')
    p_hr._p.get_or_add_pPr().append(p_hr_border)
    p_hr.paragraph_format.space_after = Pt(14)

    def add_h1(text):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(18)
        h.paragraph_format.space_after = Pt(6)
        h.paragraph_format.keep_with_next = True
        run = h.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(16)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x00, 0x33, 0x66)
        return h

    def add_h2(text):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(12)
        h.paragraph_format.space_after = Pt(4)
        h.paragraph_format.keep_with_next = True
        run = h.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(13)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x00, 0x55, 0x99)
        return h

    def add_callout(text, prefix="NOTE: ", fill="F0F4F8", border_color="005599"):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        set_cell_background(cell, fill)
        set_cell_margins(cell, top=140, bottom=140, left=200, right=200)
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(f'<w:tcBorders {nsdecls("w")}><w:left w:val="single" w:sz="24" w:color="{border_color}"/><w:top w:val="none"/><w:right w:val="none"/><w:bottom w:val="none"/></w:tcBorders>')
        tcPr.append(borders)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        r_pre = p.add_run(prefix)
        r_pre.bold = True
        r_pre.font.color.rgb = RGBColor(0x00, 0x33, 0x66)
        r_txt = p.add_run(text)
        r_txt.font.size = Pt(10.5)
        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    def add_code_block(code_text):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        set_cell_background(cell, "F7F8FA")
        set_cell_margins(cell, top=120, bottom=120, left=180, right=180)
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(f'<w:tcBorders {nsdecls("w")}><w:left w:val="single" w:sz="12" w:color="D0D5DD"/><w:top w:val="single" w:sz="6" w:color="E4E7EC"/><w:right w:val="single" w:sz="6" w:color="E4E7EC"/><w:bottom w:val="single" w:sz="6" w:color="E4E7EC"/></w:tcBorders>')
        tcPr.append(borders)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.05
        run = p.add_run(code_text)
        run.font.name = 'Consolas'
        run.font.size = Pt(9.5)
        run.font.color.rgb = RGBColor(0x22, 0x22, 0x22)
        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # Section 1
    add_h1("1. Executive Summary & Problem Context")
    doc.add_paragraph(
        "Modern electrical distribution microgrids are experiencing rapid deployment of intermittent Distributed Energy Resources (DERs)—such as rooftop solar PV arrays, wind turbines, community battery storage (BESS), and ultra-fast electric vehicle (EV) charging depots.\n\n"
        "• The Classical Breakdown: Traditional distribution network reconfiguration (DNR) relies on static shortest-path algorithms or Mixed-Integer Non-Linear Programming (MINLP). These classical methods assume fixed conductor resistances (R0) and take seconds to minutes to converge—failing to respond during steep, transient renewable surges (di/dt and dP/dt).\n"
        "• Thermal Runaway: Real conductors heat up quadratically (P = 3 I² R). High line temperatures trigger a positive thermal feedback loop where conductor resistance rises non-linearly, escalating thermal degradation and permanently destroying available electrical work (exergy).\n"
        "• The Qfficient Innovation: We reframe dynamic network reconfiguration strictly as an entropy-generation minimization problem grounded in non-equilibrium thermodynamics, compiling dynamic conductor temperatures and physical line flows directly into the Ising spin glass Hamiltonian of a quantum annealer."
    )

    add_callout(
        "Gouy-Stodola Theorem: The rate of usable electrical exergy destroyed is strictly proportional to the thermodynamic entropy generated: Ex_destroyed = T0 · ∫ ∑ S_gen(t) dt. Minimizing entropy generation directly maximizes delivered grid capacity.",
        prefix="PHYSICS PRINCIPLE: ",
        fill="EBF3FA",
        border_color="005599"
    )

    # Section 2
    add_h1("2. Comprehensive Technology Stack Breakdown")
    tech_table_data = [
        ("Layer / Subsystem", "Technologies & Libraries", "Version", "Role in Qfficient"),
        ("Language & Runtime", "Python (CPython)", "3.10 / 3.11", "Core execution environment, asynchronous task handling, and typing."),
        ("Scientific Computing", "NumPy, SciPy", ">=1.26, >=1.11", "Vectorized branch current solver, matrix QUBO evaluation, paired t-tests."),
        ("Graph & Network Theory", "NetworkX", ">=3.0", "Feeder graph topology, fundamental cycle detection, and spanning tree checks."),
        ("Data Handling", "Pandas", ">=2.0.0", "Telemetry logging, injection profile management, and tabular exports."),
        ("Quantum Formulation", "dimod", ">=0.12.0", "Binary Quadratic Models (BQM), QUBO-to-Ising mapping (x = (s+1)/2)."),
        ("Quantum Annealing", "OpenJij", ">=0.12.0", "Simulated Quantum Annealing (SQA) engine with transverse field sweeps."),
        ("Classical Annealing", "dwave-neal", ">=0.6.0", "Classical simulated annealing benchmark sampler."),
        ("Hardware QPU Access", "dwave-samplers / Ocean", ">=1.8.0", "Leap API token integration for physical D-Wave Advantage QPUs."),
        ("Power Flow Engine", "LinDistFlow (FastFeeder)", "Internal", "Linearized AC distribution power flow calculating currents, losses, and voltages."),
        ("Thermal Physics", "Differential Heat Balance", "Internal", "C_th dT/dt = 3 I² R - ΔT/θ_th with non-linear temperature coefficient α."),
        ("Interactive GUI", "Streamlit", ">=1.35.0", "Full presentation dashboard with interactive sliders and real-time report cards."),
        ("Data Visualization", "Matplotlib", ">=3.8.0", "300-DPI publication plots, 4-panel transient dynamics, topology schematics."),
        ("CLI Formatting", "tabulate", ">=0.10.0", "Formatted ASCII/Unicode terminal tables for simulation summaries."),
        ("Testing & Verification", "pytest", ">=8.0.0", "17 unit & physics verification tests enforcing radiality and math integrity."),
        ("Containerization", "Docker & Compose", "Production", "Multi-stage slim container based on python:3.11-slim with health monitoring.")
    ]

    tbl = doc.add_table(rows=len(tech_table_data), cols=4)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for r_idx, row in enumerate(tech_table_data):
        for c_idx, val in enumerate(row):
            cell = tbl.cell(r_idx, c_idx)
            cell.text = val
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.05
            p.paragraph_format.space_after = Pt(2)
            set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            if r_idx == 0:
                set_cell_background(cell, "003366")
                p.runs[0].font.bold = True
                p.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                p.runs[0].font.size = Pt(10)
            else:
                set_cell_background(cell, "F9FAFB" if r_idx % 2 == 1 else "FFFFFF")
                p.runs[0].font.size = Pt(9.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # Section 3
    add_h1("3. Core Mathematical & Thermodynamic Formulations")
    doc.add_paragraph(
        "1. Entropy Generation Rate:\n"
        "   S_gen,e(t) = Q_dot_e(t) / T_e(t) = [3 · I_e(t)² · R_e(T_e(t))] / T_e(t)  [W/K]\n\n"
        "2. Exergy Destruction (Gouy-Stodola):\n"
        "   Ex,destroyed = T0 · ∫ ∑ S_gen,e(t) dt   (where T0 = 298.15 K)\n\n"
        "3. Conductor Transient Heat Balance Equation:\n"
        "   C_th,e · (dT_e/dt) = 3 · I_e(t)² · R_e(T_e(t)) - [T_e(t) - T_amb] / θ_th,e\n"
        "   R_e(T_e) = R0,e · [1 + α · (T_e - T0)], where α ≈ 0.00393 K⁻¹ (copper/aluminum)\n\n"
        "4. Master Thermodynamic QUBO Hamiltonian submitted to Annealer:\n"
        "   H(x) = λ_thermo · H_thermo(x) + λ_cycle · H_cycle(x) + λ_rad · H_rad(x) + λ_cap · H_cap(x) + λ_sw · H_sw(x)\n\n"
        "   - H_thermo = ∑ w_e x_e, where w_e = (3 I_e² R_e) / T_e\n"
        "   - H_cycle = ∑_k (∑_{e ∈ C_k} x_e - (|C_k| - 1))²  (Cycle-breaking penalty)\n"
        "   - H_rad = (∑ x_e - (|V| - N_sub))²  (Spanning tree radiality)\n"
        "   - H_cap = Heavily penalizes branches exceeding thermal ampacity I_max\n"
        "   - H_sw = Penalizes excessive breaker toggling between consecutive steps"
    )

    # Section 4: Repository Blueprint
    add_h1("4. Repository Structure & Codebase Blueprint")
    add_code_block(
        "qfficient/\n"
        "├── app.py                             # Interactive Streamlit Web Portal & Report Card UI\n"
        "├── main_experiment.py                 # Primary simulation & 4-panel transient dynamics figure generator\n"
        "├── run_benchmark.py                   # Multi-scenario statistical benchmark & ablation suite\n"
        "├── run_custom_grid.py                 # Scalable custom microgrid runner (10 to 100 components)\n"
        "├── run_custom_40.py                   # Preset runner for 40-component microgrid\n"
        "├── run_custom_60.py                   # Preset runner for 60-component microgrid\n"
        "├── visualize_microgrid.py             # 12-component microgrid topology diagram generator\n"
        "├── run_dashboard.bat                  # 1-Click launcher for Windows\n"
        "├── run_dashboard.sh                   # 1-Click launcher for Linux/macOS\n"
        "├── pyproject.toml                     # Package metadata & console entrypoints\n"
        "├── requirements.txt                   # Pinned dependency requirements\n"
        "├── Dockerfile                         # Production container specification (Python 3.11-slim)\n"
        "├── docker-compose.yml                 # Multi-container service orchestrator\n"
        "├── README.md                          # Executive project documentation & research outcomes\n"
        "├── MANUAL.md                          # Markdown operations manual\n"
        "├── results/                           # Benchmark reports, telemetry JSON, and distribution plots\n"
        "├── tests/                             # Pytest test suite (17 passed tests)\n"
        "└── thermodynamic_grid_qubo/           # Core library package\n"
        "    ├── pipeline.py                    # Unified optimization pipeline & config dataclasses\n"
        "    ├── grid_engine/                   # Power grid topologies and thermal dynamics\n"
        "    ├── qubo_engine/                   # QUBO and Ising Hamiltonian compilation\n"
        "    ├── solvers/                       # Optimization backends (SQA, Neal, NumPy, Oracle)\n"
        "    └── verification/                  # LinDistFlow solver, metrics, and visualizer"
    )

    # Section 5: CLI Operations Manual
    add_h1("5. Complete CLI Command Reference & User Operations Manual")

    add_h2("5.1 Interactive Web Dashboard (Streamlit)")
    doc.add_paragraph("Launch the interactive review portal with live parameter sliders and report cards:")
    add_code_block(
        "# Direct Streamlit execution:\n"
        "streamlit run app.py\n\n"
        "# Or using the virtual environment directly:\n"
        ".venv\\Scripts\\python.exe -m streamlit run app.py\n\n"
        "# 1-Click launchers:\n"
        "run_dashboard.bat    # Windows\n"
        "./run_dashboard.sh   # Linux/macOS"
    )

    add_h2("5.2 Main Scientific Experiment (IEEE 33-Bus Transient)")
    doc.add_paragraph("Executes the synchronized transient benchmark (75% solar drop + 800 kW EV charging pulse) and generates 'thermodynamic_qubo_results.png':")
    add_code_block(
        "# Direct python execution:\n"
        "python main_experiment.py\n\n"
        "# Or via registered console entrypoint:\n"
        "thermo-qubo-sim"
    )

    add_h2("5.3 Scalable Custom Microgrid Runner (10 to 100 Buses)")
    doc.add_paragraph("Simulates arbitrary custom microgrid topologies generated via graph algorithms:")
    add_code_block(
        "# Basic usage (default 60 components, 6 ties, 15 steps):\n"
        "python run_custom_grid.py\n\n"
        "# 40 components with 4 tie lines:\n"
        "python run_custom_grid.py --components 40 --ties 4\n\n"
        "# 80 components with 8 tie switches over 20 time steps:\n"
        "python run_custom_grid.py --components 80 --ties 8 --steps 20\n\n"
        "# 100 components using Exact Oracle solver:\n"
        "python run_custom_grid.py --components 100 --ties 8 --solver exact_oracle\n\n"
        "# Using the vectorized NumPy annealer:\n"
        "python run_custom_grid.py --components 50 --ties 5 --solver numpy_annealer\n\n"
        "# Ready-made benchmark presets:\n"
        "python run_custom_40.py\n"
        "python run_custom_60.py"
    )

    add_h2("5.4 Multi-Scenario Benchmark & Policy Ablation Suite")
    doc.add_paragraph("Runs multi-scenario statistical ablation studies with Student's t-test verification:")
    add_code_block(
        "# Run benchmark with 5 scenarios:\n"
        "python run_benchmark.py --n 5\n\n"
        "# Comprehensive benchmark with 20 scenarios saved to custom directory:\n"
        "python run_benchmark.py --n 20 --output-dir results"
    )

    add_h2("5.5 Microgrid Topology Visualizer")
    doc.add_paragraph("Generates high-resolution schematic diagrams highlighting active paths vs. open switches:")
    add_code_block(
        "python visualize_microgrid.py\n"
        "# Or via console entrypoint:\n"
        "thermo-qubo-gui"
    )

    add_h2("5.6 Automated Test Suite Execution (pytest)")
    doc.add_paragraph("Executes 17 comprehensive unit, physical verification, and schema validation tests:")
    add_code_block(
        "# Run all tests:\n"
        ".venv\\Scripts\\python.exe -m pytest\n\n"
        "# Verbose output:\n"
        ".venv\\Scripts\\python.exe -m pytest -v\n\n"
        "# Run specific test modules:\n"
        ".venv\\Scripts\\python.exe -m pytest tests/test_custom_grid.py\n"
        ".venv\\Scripts\\python.exe -m pytest tests/test_fast_flow.py\n"
        ".venv\\Scripts\\python.exe -m pytest tests/test_pipeline.py\n"
        ".venv\\Scripts\\python.exe -m pytest tests/test_qubo_grid.py"
    )

    # Section 6: Solvers & Results
    add_h1("6. Solver Matrix & Performance Comparison")
    solver_data = [
        ("Solver Identifier", "Algorithm Description", "Loss Reduction", "Voltage Compliant", "Latency"),
        ("exact_dynamic_oracle", "Global loss-minimizing dynamic branch-exchange", "+28.37%", "Yes (100%)", "38.98 ms"),
        ("static_loss_optimal", "Optimal static spanning tree configuration", "+27.87%", "Yes (100%)", "0.00 ms"),
        ("sqa (OpenJij)", "Simulated Quantum Annealing (Transverse Ising)", "Dynamic", "Yes (100%)", "~330 ms"),
        ("numpy_annealer", "Vectorized local-search simulated annealing", "Dynamic", "Yes (100%)", "~15 ms"),
        ("dwave_qpu_runner", "Physical D-Wave Advantage QPU (Leap Cloud)", "Dynamic", "Yes (100%)", "Cloud"),
        ("standard_static", "Unreconfigured textbook baseline (tie lines open)", "0.00%", "Baseline", "0.00 ms")
    ]
    tbl_s = doc.add_table(rows=len(solver_data), cols=5)
    tbl_s.alignment = WD_TABLE_ALIGNMENT.CENTER
    for r_idx, row in enumerate(solver_data):
        for c_idx, val in enumerate(row):
            cell = tbl_s.cell(r_idx, c_idx)
            cell.text = val
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.05
            p.paragraph_format.space_after = Pt(2)
            set_cell_margins(cell, top=70, bottom=70, left=90, right=90)
            if r_idx == 0:
                set_cell_background(cell, "003366")
                p.runs[0].font.bold = True
                p.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                p.runs[0].font.size = Pt(10)
            else:
                set_cell_background(cell, "F9FAFB" if r_idx % 2 == 1 else "FFFFFF")
                p.runs[0].font.size = Pt(9.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # Section 7: Programmatic API
    add_h1("7. Programmatic Python API & Extensibility")
    doc.add_paragraph("You can integrate Qfficient directly into external scripts or Jupyter notebooks:")
    add_code_block(
        "from thermodynamic_grid_qubo.pipeline import OptimizationConfig, run_optimization\n\n"
        "# 1. Configure the scenario\n"
        "config = OptimizationConfig(\n"
        "    grid='custom',\n"
        "    solver='exact_oracle',\n"
        "    solar_drop_pct=75.0,\n"
        "    ev_surge_kw=800.0,\n"
        "    ambient_c=25.0,\n"
        "    time_steps=20,\n"
        "    custom_n_components=50,\n"
        "    custom_n_ties=5,\n"
        ")\n\n"
        "# 2. Run optimization\n"
        "results = run_optimization(config)\n\n"
        "# 3. Access physics telemetry\n"
        "b_heat = sum(results['baseline']['heat_mj'])\n"
        "q_heat = sum(results['qubo']['heat_mj'])\n"
        "pct_saved = ((b_heat - q_heat) / b_heat) * 100.0\n"
        "print(f'Joule Heat Reduction: {pct_saved:+.2f}%')\n"
        "print(f'Voltage Compliant: {results[\"checks\"][\"voltage_all_steps\"]}')"
    )

    # Section 8: Visual Diagrams Embedding
    add_h1("8. Embedded Visual Diagrams & Schematics")
    base_dir = Path(__file__).resolve().parent
    microgrid_img = base_dir / "optimized_microgrid.png"
    if microgrid_img.exists():
        doc.add_paragraph("Figure 1: 12-Component Smart Microgrid Dynamic Reconfiguration Routing Diagram:")
        doc.add_picture(str(microgrid_img), width=Inches(6.2))
        p_cap = doc.add_paragraph("Figure 1. Active energized feeder paths (solid green) vs. standing open candidate tie lines (dashed gray).")
        p_cap.runs[0].font.size = Pt(9.5)
        p_cap.runs[0].font.italic = True
        doc.add_paragraph().paragraph_format.space_after = Pt(8)

    transient_img = base_dir / "thermodynamic_qubo_results.png"
    if transient_img.exists():
        doc.add_paragraph("Figure 2: Transient Dynamics & Loss Reduction on IEEE 33-Bus Benchmark:")
        doc.add_picture(str(transient_img), width=Inches(6.2))
        p_cap2 = doc.add_paragraph("Figure 2. 4-Panel publication transient analysis: (A) Active power loss, (B) Cumulative Joule heat dissipation, (C) Entropy generation rate, and (D) Peak feeder conductor temperature.")
        p_cap2.runs[0].font.size = Pt(9.5)
        p_cap2.runs[0].font.italic = True

    # Save Document
    out_file = base_dir / "QFFICIENT_SYSTEM_MANUAL.docx"
    doc.save(str(out_file))
    print(f"Successfully generated Word Document at: {out_file.resolve()}")

if __name__ == "__main__":
    create_document()
