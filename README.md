<div align="center">

# ⚡ Qfficient: Thermodynamic-Mapped QUBO for Dynamic Microgrid Distribution
### *Next-Generation Distribution Network Reconfiguration via Non-Equilibrium Thermodynamics, Fast LinDistFlow, and Quantum Annealing*

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Quantum](https://img.shields.io/badge/Quantum-D--Wave%20%7C%20OpenJij%20%7C%20Neal-4A154B?style=for-the-badge&logo=quantum&logoColor=white)](https://www.dwavesys.com/)
[![Framework](https://img.shields.io/badge/Streamlit-2.0%20App-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-Passing%20(37%2F37)-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](tests/)
[![Grid Scale](https://img.shields.io/badge/Grid%20Scale-10%20to%20100%20Components-orange?style=for-the-badge&logo=target&logoColor=white)](#-custom-microgrid-generator-10-to-100-components)

<p align="center">
  <b>Dynamic Power Routing</b> • <b>Entropy Minimization</b> • <b>Exergy Preservation</b> • <b>Thermal Runaway Suppression</b> • <b>10–100 Component Scalability</b>
</p>

</div>

---

## 📌 Table of Contents
1. [Executive Summary & Problem Context](#-executive-summary--problem-context)
2. [Complete Technical Stack & Operational User Manual](#-complete-technical-stack--operational-user-manual)
3. [Proven Experimental Outcomes & Claim Reconciliation](#-proven-experimental-outcomes--claim-reconciliation)
4. [Core Physics & Non-Equilibrium Thermodynamics](#-core-physics--non-equilibrium-thermodynamics)
5. [Thermodynamic QUBO & Ising Formulation](#-thermodynamic-qubo--ising-formulation)
6. [Custom Microgrid Generator (10 to 100 Components)](#-custom-microgrid-generator-10-to-100-components)
7. [Multi-Solver Architecture & Scalable Quantum Annealing](#-multi-solver-architecture--scalable-quantum-annealing)
8. [Visual Diagnostics & Network Topologies](#-visual-diagnostics--network-topologies)
9. [Interactive Review Portal (Streamlit 2.0 Web Dashboard)](#-interactive-review-portal-streamlit-20-web-dashboard)
10. [Quickstart & CLI Commands](#-quickstart--cli-commands)
11. [Repository Architecture](#-repository-architecture)
12. [License & Citation](#-license--citation)

---

## 📌 Executive Summary & Problem Context

Modern electrical distribution microgrids are experiencing rapid, high-density penetration of intermittent **Distributed Energy Resources (DERs)**, including rooftop and commercial solar PV, wind turbines, community Battery Energy Storage Systems (BESS), and high-power Electric Vehicle (EV) fast-charging depots.

### The Engineering Challenge
* **The Classical Reconfiguration Bottleneck**: Traditional Distribution Network Reconfiguration (DNR) relies on static shortest-path heuristics or Mixed-Integer Non-Linear Programming (MINLP). These solvers assume fixed conductor resistances ($R_0$) and take seconds to minutes to converge—making real-time topological adaptation during steep transient ramps ($di/dt$ and $dP/dt$) physically impossible.
* **Thermal Runaway & Resistance Feedback**: Electric current generates heat quadratically ($P = 3 I^2 R$). As heavy feeder lines heat up under demand surges, conductor resistance rises non-linearly ($R(T) = R_0 [1 + \alpha(T - T_0)]$). This positive feedback loop amplifies voltage sag, triggers line ampacity overloads, and permanently destroys available electrical work (exergy).
* **The Qfficient Solution**: We reframe dynamic network reconfiguration strictly as an **entropy-generation minimization problem grounded in non-equilibrium thermodynamics**. Dynamic conductor temperatures, transient power injections, and topological radiality constraints are compiled into an Ising spin glass Hamiltonian solved on quantum annealers, simulated quantum annealing (SQA), or exact loss-minimizing classical oracles in milliseconds.

---

## 📖 Complete Technical Stack & Operational User Manual

For a comprehensive, end-to-end technical reference with step-by-step CLI walkthroughs, programmatic Python APIs, technology stack breakdowns, and diagnostic troubleshooting:

* 📄 **Markdown User Manual**: See [`MANUAL.md`](MANUAL.md) for complete file-by-file blueprints, solver parameter guides, and Docker orchestration details.
* 📑 **Formatted Word Manual**: Download [`QFFICIENT_SYSTEM_MANUAL.docx`](QFFICIENT_SYSTEM_MANUAL.docx) (generated via `python generate_docx_manual.py`) for formatted printing, stakeholder submission, and formal project presentation.

---

## 🏆 Proven Experimental Outcomes & Claim Reconciliation

### 1. IEEE 33-Bus Benchmark (Rigorous Research-Grade Evaluation)
Evaluated across **30 independent randomized renewable/load fluctuation profiles** over 12 time steps ($dt = 300.0\text{ s}$) using IEEE 33-Bus benchmark parameters ($V_{\text{base}} = 12.66\text{ kV}$, $S_{\text{base}} = 10\text{ MVA}$, ANSI C84.1 voltage band $[0.95, 1.05]\text{ p.u.}$):

| Policy / Algorithm | Total Joule Heat (MJ) [Mean ± Std] | Heat Reduction vs Std. Baseline (%) | $p$-value ($t$-test) | Peak Conductor Temp (°C) | Voltage Violations (steps) | Decision Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Standard Static Baseline (IEEE 33 Default)** | $368.805 \pm 87.578$ | *Reference* | — | $47.3^\circ\text{C}$ | $7.4$ | $0.00\text{ ms}$ |
| **Classical Branch Exchange (Baran-Wu)** | $292.359 \pm 69.195$ | **+20.73%** | 5.45e-20 | $44.6^\circ\text{C}$ | $3.4$ | $55.22\text{ ms}$ |
| **Static Loss-Optimal (Best Single Tree)** | $265.718 \pm 61.197$ | **+27.95%** | 3.51e-19 | $38.7^\circ\text{C}$ | $3.3$ | $0.00\text{ ms}$ |
| **Candidate Loss-Optimal Search (Top Trees)** | $261.623 \pm 61.079$ | **+29.06%** | 1.22e-19 | $38.9^\circ\text{C}$ | $3.0$ | $45.71\text{ ms}$ |
| **Random Switch Proposals (Raw)** | $627.089 \pm 214.974$ | -70.03% | 2.21e-09 | $47.7^\circ\text{C}$ | $8.4$ | $1.06\text{ ms}$ |
| **Random Switch Proposals (Filtered Control)** | $276.148 \pm 65.391$ | **+25.12%** | 5.54e-20 | $38.6^\circ\text{C}$ | $2.5$ | $14.29\text{ ms}$ |
| **Random Spanning Trees (Raw)** | $842.111 \pm 259.067$ | -128.34% | 6.32e-14 | $56.7^\circ\text{C}$ | $10.3$ | $0.04\text{ ms}$ |
| **Random Spanning Trees (Filtered)** | $292.410 \pm 72.627$ | **+20.71%** | 2.96e-22 | $39.7^\circ\text{C}$ | $3.2$ | $9.20\text{ ms}$ |
| **Thermodynamic QUBO (Raw Ground State)** | $409.083 \pm 107.876$ | -10.92% | 2.39e-04 | $43.7^\circ\text{C}$ | $6.6$ | $135.71\text{ ms}$ |
| **Thermodynamic QUBO (Power-Flow Filtered)** | $355.396 \pm 88.464$ | **+3.64%** | 0.0194 | $42.7^\circ\text{C}$ | $5.7$ | $142.08\text{ ms}$ |

### 2. Scientific Claim Reconciliation & Empirical Findings
* **True ~211 kW Baseline & AC Recalibration**: Under standard nominal load without transients, linearized LinDistFlow yields **196.93 kW**, while exact non-linear AC DistFlow (Baran & Wu, 1989) yields **210.74 kW (~211 kW)** due to coupled branch $I^2 R$ loss feedback ($K_{\text{AC/LinDistFlow}} = 1.0701$). All baseline figures represent the standard unreconfigured textbook radial network (tie lines 32..36 open).
* **Classical Branch Exchange & Theoretical Optimum**: Relative to the standard baseline, classical loop branch exchange achieves **+20.73% loss reduction**, while dynamic candidate tree search achieves **+29.06% loss reduction**.
* **Random-Proposals Control vs. QUBO Guidance**: The `random_proposals_filtered` control generates 50 random switch proposals and applies the exact same Kruskal thermal repair and power-flow filter, achieving **+25.12% loss reduction**. Comparing filtered QUBO (**+3.64%**) against random proposals isolates the extent to which the quantum Hamiltonian guides the search versus the post-processing filter.
* **Thermodynamic QUBO Sign Physics**: With the corrected negative linear mapping ($-w_e x_e$), loaded backbone lines are prioritized to stay closed while loop tie-lines with minimum mesh currents are broken. Raw unconstrained QUBO ground states achieve **-10.92% loss reduction** without post-hoc power-flow re-ranking.
* **Realistic Problem Hardness & Quantum Advantage Boundaries**: On the 33-bus testbed (37 binary variables, 5 tie switches), there exist only 50,751 valid radial trees, which an exhaustive classical LinDistFlow oracle evaluates in under 40 ms. Therefore, **no quantum advantage exists or is claimed on the 33-bus system**. Meaningful quantum advantage requires large-scale meshed distribution networks ($>100$ buses, $\ge 15\text{--}20$ tie switches, where tree cardinality exceeds $10^{15}$ and exhaustive classical enumeration becomes NP-hard). The custom grid generator (`run_custom_grid.py`) supports scaling experiments up to 100 components.
* **Sampler Backends & Benchmark Execution**: The headline numbers reported above use the dependency-free `numpy-sa` simulated annealer (vectorized Metropolis-Hastings on CPU, 100 sweeps, 50 reads) ensuring exact reproducibility without external proprietary dependencies. Multi-sampler evaluations across `dwave-neal`, `openjij` classical SA, and `openjij` SQA (path-integral Monte Carlo, Trotter=16) are detailed in [`results/BENCHMARK.md`](results/BENCHMARK.md) and [`results/sampler_comparison.png`](results/sampler_comparison.png).

---

## 🔬 Core Physics & Non-Equilibrium Thermodynamics

```
                                  SUNLIGHT / WIND
                                        │
                                        ▼
    ┌────────────────────────────────────────────────────────────────────────┐
    │                       DISTRIBUTION FEEDER LINE                          │
    │                                                                        │
    │   Electric Current I_e(t) ──► Non-Linear Joule Dissipation:            │
    │                               Q̇_e(t) = 3 · I_e(t)² · R_e(T_e)         │
    │                                        │                               │
    │                                        ▼                               │
    │   Thermal Balance:           dT_e/dt = (Q̇_e - Q̇_loss) / C_th           │
    │                                        │                               │
    │                                        ▼                               │
    │   Resistance Feedback:       R_e(T) = R_0 · [1 + α · (T_e - T_0)]     │
    │                                        │                               │
    │                                        ▼                               │
    │   Entropy Generation:        Ṡ_gen,e(t) = Q̇_e(t) / T_e(t)              │
    │                                        │                               │
    │                                        ▼                               │
    │   Gouy-Stodola Exergy Loss:  E_x,dest = T_0 · ∫ Ṡ_gen dt               │
    └────────────────────────────────────────────────────────────────────────┘
                                        │
                         THERMODYNAMIC QUBO MINIMIZATION
                                        │
                                        ▼
                  Optimized Reconfigured Feeder Topology
```

### 1. Non-Equilibrium Entropy Generation Rate
Electric current transport through resistive conductors produces irreversible entropy. For a three-phase branch $e \in E$ at temperature $T_e(t)$:

$$\dot{S}_{\text{gen},e}(t) = \frac{\dot{Q}_e(t)}{T_e(t)} = \frac{3 \cdot I_e(t)^2 \cdot R_e(T_e(t))}{T_e(t)} \quad \left[\frac{\text{W}}{\text{K}}\right]$$

### 2. The Gouy-Stodola Theorem
The rate of usable electrical work capability (exergy) destroyed is directly proportional to entropy generation:

$$E_{x,\text{destroyed}} = T_0 \cdot \int_0^{\Delta t} \sum_{e \in E} \dot{S}_{\text{gen},e}(t) \, dt$$

Where $T_0$ is ambient reference temperature ($298.15\text{ K}$). Minimizing entropy generation directly maximizes delivered useful exergy to loads.

### 3. Conductor Transient Differential Heat Balance
Conductor temperature transients are simulated at each time step using first-order lumped capacitance dynamics:

$$C_{\text{th},e} \frac{dT_e(t)}{dt} = 3 \cdot I_e(t)^2 \cdot R_e(T_e(t)) - \frac{T_e(t) - T_{\text{amb}}}{\theta_{\text{th},e}}$$

Conductor resistance updates non-linearly with temperature:

$$R_e(T_e) = R_{0,e} \cdot \left[1 + \alpha \cdot (T_e - T_0)\right]$$

Where $\alpha \approx 0.00393\text{ K}^{-1}$ for aluminum/copper conductors.

---

## ⚛️ Thermodynamic QUBO & Ising Formulation

### Decision Variables
For each candidate distribution line and tie switch $e \in E$, binary decision variable $x_e \in \{0, 1\}$ represents:
* $x_e = 1$: Switch closed (branch energized)
* $x_e = 0$: Switch open (branch isolated)

### Master Objective Hamiltonian
The composite Hamiltonian submitted to the quantum annealing core is:

$$H(x) = \lambda_{\text{thermo}} H_{\text{thermo}}(x) + \lambda_{\text{cycle}} H_{\text{cycle}}(x) + \lambda_{\text{rad}} H_{\text{rad}}(x) + \lambda_{\text{cap}} H_{\text{cap}}(x) + \lambda_{\text{sw}} H_{\text{sw}}(x)$$

1. **Thermodynamic Dissipation**:
   $$H_{\text{thermo}}(x) = \sum_{e \in E} w_e \cdot x_e \quad \text{where } w_e = \frac{3 \cdot I_e^2 \cdot R_e(T_e)}{T_e}$$
2. **Fundamental Loop Breaking**: For each fundamental cycle $C_k$ in the co-tree, enforce exactly one open branch:
   $$H_{\text{cycle}}(x) = \sum_{k} \left(\sum_{e \in C_k} x_e - (|C_k| - 1)\right)^2$$
3. **Radial Spanning Tree**: Enforce exactly $N - 1$ active lines ($|V| - 1$ branches for 1 substation):
   $$H_{\text{rad}}(x) = \left(\sum_{e \in E} x_e - (|V| - 1)\right)^2$$
4. **Thermal Ampacity Protection**:
   $$H_{\text{cap}}(x) = \sum_{e \in E} \max\left(0, \frac{I_e - I_{\max,e}}{I_{\max,e}}\right)^2 \cdot x_e$$
5. **Switching Wear Fatigue**: Penalize toggling switch states between consecutive time intervals $t-1$ and $t$:
   $$H_{\text{sw}}(x) = \sum_{e \in E} |x_e^{(t)} - x_e^{(t-1)}|$$

### Mapping to Transverse Ising Spin Glass
Using change of variables $x_i = \frac{s_i + 1}{2}$ where spin $s_i \in \{-1, +1\}$:

$$H_{\text{Ising}}(s) = \sum_{i} h_i s_i + \sum_{i < j} J_{ij} s_i s_j + \text{Offset}$$

* $h_i$: Local magnetic field bias applied to physical qubit $i$
* $J_{ij}$: Inter-qubit coupling strength between physical qubits $i$ and $j$

---

## 🌐 Custom Microgrid Generator (10 to 100 Components)

The platform includes a procedural generator (`generate_custom_grid`) enabling simulation of arbitrary microgrid architectures from **10 to 100 components**:

* **Physical Grid Topologies**: Guaranteed connected spanning tree with central high-capacity trunk spine and branching lateral feeders.
* **Configurable DER Mix**:
  * Solar PV generation buses ($P_{\text{gen}} \in [15, 30]\text{ kW}$)
  * Wind turbine generation buses ($P_{\text{gen}} \in [20, 45]\text{ kW}$)
  * Battery Energy Storage System (BESS) nodes ($P_{\text{cap}} \in [20, 50]\text{ kW}$)
  * Electric Vehicle (EV) fast-charging depot nodes ($P_{\text{load}} \in [60, 110]\text{ kW}$)
* **Configurable Tie Lines**: User-specified count of normally open tie switches (1 to 15) creating realistic reconfiguration loop paths.
* **Aesthetic 2D Layout Coordinates**: Automatically generates spatial coordinates for high-resolution topology visualization.

```bash
# Generate and optimize an 80-component microgrid with 8 tie switches
python run_custom_grid.py --components 80 --ties 8 --solver exact_oracle
```

---

## 🧩 Multi-Solver Architecture & Scalable Quantum Annealing

Qfficient provides a unified solver interface through `thermodynamic_grid_qubo.pipeline`:

```
                           ┌──────────────────────────┐
                           │   OptimizationConfig     │
                           └─────────────┬────────────┘
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
      ┌─────────────────────────┐                 ┌─────────────────────────┐
      │     Quantum Solvers     │                 │    Classical Solvers    │
      ├─────────────────────────┤                 ├─────────────────────────┤
      │ • D-Wave Advantage QPU  │                 │ • Exact Dynamic Oracle  │
      │ • OpenJij SQA (Ensemble)│                 │ • NumPy Vectorized SA   │
      │ • D-Wave Neal (SA)      │                 │ • Static Baseline       │
      └─────────────────────────┘                 └─────────────────────────┘
```

### Scalable Quantum Annealing for Large Grids ($N \ge 30$)
As grid sizes expand to 40, 60, and 100 components, raw spin-flip sampling suffers from combinatorial fragmentation. We introduced a **hybrid quantum-ensemble extraction engine**:
1. **Raw Quantum Sampling**: Executes SQA / Neal across configured anneal reads.
2. **Kruskal-Guided Energy Repair**: Repaired candidate spanning trees formed by Kruskal's MST biased by low-energy spins.
3. **Marginal Spin Ensemble MST**: Computes edge marginal probabilities across all quantum samples and extracts the maximum-probability spanning tree.
4. **Annealer-Guided Loop Exchange**: Identifies high-probability tie switches and generates minimal branch-exchange candidates.
5. **Physics Screening**: Evaluates candidate trees with fast LinDistFlow to guarantee voltage compliance and minimum Joule dissipation.

---

## 📊 Visual Diagnostics & Network Topologies

### 1. 33-Component IEEE Benchmark Topology
Active lines (green) vs. open tie switches (dashed gray) with node voltage and line temperature heatmaps:
<p align="center">
  <img src="optimized_microgrid.png" alt="33-Component Microgrid Topology" width="850">
</p>

### 2. Custom 60-Component & 100-Component Microgrid Topologies
<p align="center">
  <img src="custom_microgrid_60.png" alt="60-Component Microgrid Topology" width="420">
  <img src="custom_microgrid_100.png" alt="100-Component Microgrid Topology" width="420">
</p>

### 3. Dynamic Transient Analysis (40-Component & 60-Component Systems)
<p align="center">
  <img src="custom_40_transient.png" alt="40-Component Transient Analysis" width="420">
  <img src="custom_60_transient.png" alt="60-Component Transient Analysis" width="420">
</p>

---

## 💻 Interactive Review Portal (Streamlit 2.0 Web Dashboard)

Launch the full interactive GUI for presentations, demonstrations, and design reviews:

```bash
streamlit run app.py
```
* **Local Web Address**: `http://localhost:8501`

### Key Interactive Features
1. **Architecture Selector**: Choose between standard IEEE 33-Bus, 12-component test feeder, or **Custom Microgrid**.
2. **Custom Grid Controls**: Sliders for total components (10 to 100 buses), tie switches (1 to 15), and DER allocation (Solar PV, Wind, Battery BESS, EV depots).
3. **Transient Stress Injections**: Adjust solar PV cloud drop ($0 - 90\%$) and EV charging pulse surges ($0 - 1200\text{ kW}$).
4. **Executive Performance Table**: Direct comparison of Joule heat dissipation, entropy generation, exergy preserved, peak conductor temperature, and breaker switch counts.
5. **Interactive Topology Canvas**: Scrub through simulation time steps to inspect switch actions, active routes, and thermal states.
6. **Line-by-Line Operating State Table**: Detailed breakdown of line current, resistance, loading %, and temperature at any selected second.

---

## 🚀 Quickstart & CLI Commands

### 1. Environment Setup
```bash
git clone https://github.com/RishDK07/Qfficient-.git
cd Qfficient-

# Create virtual environment
python -m venv .venv
# Activate on Windows:
.venv\Scripts\activate
# Activate on Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Commands

| Task | Command | Description |
| :--- | :--- | :--- |
| **Unified CLI Suite** | `python run.py -n 60` | Full CLI & automated export suite (CSV, figures, reports) |
| **Parametric Sweep** | `python run.py --sweep` | Multi-scale scaling sweep across sizes [20, 40, 60, 80, 100] |
| **Phase 3 Validation** | `python run_phase3_validation.py` | Full validation suite: pandapower AC cross-val, IEEE 69-bus, N=100, EV stress |
| **Phase 2 Ablations** | `python run_phase2_ablations.py` | QUBO formulation ablations, quadratic surrogate, and hybrid policies |
| **Sampler Comparison** | `python run_sampler_comparison.py` | Multi-sampler benchmarks: NumPy SA, OpenJij SQA, and D-Wave Neal |
| **Launch Dashboard** | `streamlit run app.py` | Full interactive review portal & custom grid designer |
| **Standalone Web Suite**| Open `dashboard.html` | Self-contained single-page executive web app with SVG topology |
| **Build HTML Dashboard**| `python build_dashboard_html.py` | Compiles simulation telemetry into `dashboard.html` |
| **Run Benchmark** | `python run_benchmark.py` | 100-scenario statistical evaluation with LaTeX tables |
| **Custom 60-Bus Grid** | `python run_custom_grid.py --components 60 --ties 6` | Generates 60-component microgrid and runs optimization |
| **Custom 40-Bus Script** | `python run_custom_40.py` | Evaluates 40-component microgrid with transient plots |
| **Custom 60-Bus Script** | `python run_custom_60.py` | Evaluates 60-component microgrid with transient plots |
| **IEEE 33-Bus Visualizer**| `python visualize_microgrid.py` | Generates high-res `optimized_microgrid.png` |
| **Run Test Suite** | `pytest tests/` | Runs all 37 unit, AC power flow, IEEE 69-bus, and report integrity tests |

### 3. One-Click Launchers
* **Windows**: Double-click `run_dashboard.bat`
* **Linux / macOS**: Execute `./run_dashboard.sh`
* **Docker**: Execute `docker compose up -d`

---

## 📁 Repository Architecture

```
Qfficient-/
├── run.py                                             # Unified CLI entry point & scaling sweep runner
├── run_phase3_validation.py                           # Phase 3 comprehensive validation suite (pandapower, IEEE 69)
├── MANUAL.md                                          # Complete technical stack specification & user manual
├── QFFICIENT_SYSTEM_MANUAL.docx                       # Comprehensive formatted Word technical manual
├── generate_docx_manual.py                            # Automated generator for the Word technical manual
├── dashboard.html                                     # Self-contained executive single-page presentation suite
├── build_dashboard_html.py                            # Compiler for the executive presentation dashboard
├── dashboard_data.json                                # Pre-generated multi-grid simulation telemetry
├── app.py                                             # Streamlit 2.0 interactive review portal & custom designer
├── main_experiment.py                                 # Scientific benchmark runner & figure generator
├── run_benchmark.py                                   # 100-scenario research-grade benchmark suite
├── run_custom_grid.py                                 # Standalone runner for custom 10-100 component microgrids
├── run_custom_40.py                                   # 40-component custom microgrid evaluation script
├── run_custom_60.py                                   # 60-component custom microgrid evaluation script
├── visualize_microgrid.py                             # IEEE 33-bus high-res topology visualizer
├── Dockerfile                                         # Multi-stage production container definition
├── docker-compose.yml                                 # Container orchestration
├── run_dashboard.bat                                  # Windows 1-click launcher
├── run_dashboard.sh                                   # Linux/macOS 1-click launcher
├── pyproject.toml                                     # Package installation metadata & entry points
├── requirements.txt                                   # Pinned production dependencies
│
├── results/                                           # Benchmark datasets & analytical summaries
│   ├── BENCHMARK_REPORT.md                            # Comprehensive statistical report & claim reconciliation
│   ├── benchmark_distribution.png                     # Loss distribution across policies
│   ├── benchmark_raw.json                             # Raw scenario execution telemetry
│   ├── benchmark_summary.json                         # Mean, std, and p-value summary table
│   ├── phase2_ablations.json                          # Phase 2 QUBO formulation & penalty ablation data
│   ├── phase3_validation.json                         # Phase 3 full validation (AC cross-val, IEEE 69, N=100)
│   ├── sampler_comparison.json                        # Multi-sampler (SA, SQA, Neal) comparison telemetry
│   ├── sampler_comparison.png                         # Multi-sampler comparative performance figure
│   └── sensitivity_curves.png                         # Phase 3 parametric sensitivity curves figure
│
├── tests/                                             # Automated test suite (37 passed tests)
│   ├── test_custom_grid.py                            # Custom 30, 60, 100 component topology & pipeline tests
│   ├── test_fast_flow.py                              # LinDistFlow accuracy & voltage tests
│   ├── test_pandapower_and_ieee69.py                  # Pandapower AC cross-validation & IEEE 69-bus tests
│   ├── test_pipeline.py                               # Pipeline config & multi-solver tests
│   ├── test_qubo_grid.py                              # Physics verifier, thermal dynamics, and QUBO tests
│   └── test_report_integrity.py                       # Automated verification of report cards & HTML exports
│
└── thermodynamic_grid_qubo/                           # Core Python Package
    ├── __init__.py                                    # Package root
    ├── cli.py                                         # Rich CLI & batch execution engine with CSV/report exports
    ├── pipeline.py                                    # Unified optimization pipeline & config
    ├── grid_engine/                                   # Distribution grid netlists & DER dynamics
    │   ├── __init__.py                                # Grid engine exports
    │   ├── custom_grid_generator.py                   # Procedural 10-100 component microgrid generator
    │   ├── ieee_feeder_loader.py                      # IEEE 33-bus and 12-component netlists
    │   ├── renewable_simulator.py                     # Solar drop & EV pulse transient simulators
    │   └── thermal_dynamics.py                        # Conductor lumped capacitance heat balance
    ├── qubo_engine/                                   # QUBO compilation & Ising mapping
    │   ├── __init__.py                                # QUBO engine exports
    │   ├── entropy_calculator.py                      # Joule dissipation & entropy generation weights
    │   ├── penalty_tuner.py                           # Dynamic Lagrange multiplier scaling
    │   └── qubo_builder.py                            # Master Hamiltonian & cycle constraints
    ├── solvers/                                       # Multi-solver execution backends
    │   ├── __init__.py                                # Solver exports
    │   ├── ablation_suite.py                          # Multi-policy ablation benchmarking suite
    │   ├── classical_baseline.py                      # Static baseline power flow evaluator
    │   ├── dwave_qpu_runner.py                        # Hardware D-Wave Advantage QPU interface
    │   ├── exact_classical_solver.py                  # Exact loss-minimizing classical oracle
    │   ├── numpy_annealer.py                          # Vectorized NumPy simulated annealer
    │   └── openjij_annealer.py                        # OpenJij SQA with ensemble MST loop exchange
    └── verification/                                  # Physics checks & visual reporting
        ├── __init__.py                                # Verification exports
        ├── fast_flow.py                               # Vectorized LinDistFlow power flow engine
        ├── ieee33_trees.npy                           # Precomputed IEEE 33-bus spanning tree database
        ├── metrics_evaluator.py                       # Exergy, entropy, and heat metric calculations
        ├── microgrid_visualizer.py                    # Network graph rendering & node positioning
        ├── physics_verifier.py                        # ANSI C84.1 voltage & thermal compliance checks
        └── report_card.py                             # Formal engineering grading & KPI report cards
```

---

## 🤝 Hardware Quantum Access (D-Wave Advantage QPU)

To submit QUBO Hamiltonians directly to cloud-based physical D-Wave Advantage QPUs:
```bash
export DWAVE_API_TOKEN="YOUR_LEAP_API_TOKEN"
python main_experiment.py
```
*(If no token is present, the framework automatically uses local high-performance Simulated Quantum Annealing via OpenJij or the exact classical oracle).*

---

## 📜 License & Citation

Distributed under the Apache 2.0 License. See `LICENSE` for details.

If you use **Qfficient** in academic research or industrial projects, please cite:
```bibtex
@article{qfficient2026,
  title={Thermodynamic-Mapped QUBO Formulation for Dynamic Microgrid Power Distribution},
  author={RishDK07 and Contributors},
  journal={GitHub Repository},
  url={https://github.com/RishDK07/Qfficient-},
  year={2026}
}
```