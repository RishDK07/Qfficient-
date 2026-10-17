# ⚡ Qfficient: Complete Technical Stack & Operational User Manual
### *Thermodynamic-Mapped QUBO for Dynamic Microgrid Distribution*

---

## 📑 Table of Contents
1. [Executive Summary & Problem Statement](#1-executive-summary--problem-statement)
2. [Complete Technology Stack Specification](#2-complete-technology-stack-specification)
3. [Core Physics & Thermodynamic QUBO Formulation](#3-core-physics--thermodynamic-qubo-formulation)
4. [Project Architecture & File-by-File Blueprint](#4-project-architecture--file-by-file-blueprint)
5. [Installation & Environment Configuration](#5-installation--environment-configuration)
6. [Complete CLI Operations & Command Reference](#6-complete-cli-operations--command-reference)
   - [6.1 Interactive Presentation Portal (Streamlit)](#61-interactive-presentation-portal-streamlit)
   - [6.2 Scientific Transient Experiment (IEEE 33-Bus Feeder)](#62-scientific-transient-experiment-ieee-33-bus-feeder)
   - [6.3 Custom Microgrid Scalability Runner (10 to 100 Buses)](#63-custom-microgrid-scalability-runner-10-to-100-buses)
   - [6.4 Multi-Scenario Benchmark & Policy Ablation Suite](#64-multi-scenario-benchmark--policy-ablation-suite)
   - [6.5 Topology & Schematic Visualizer](#65-topology--schematic-visualizer)
   - [6.6 Automated Test Suite Execution (pytest)](#66-automated-test-suite-execution-pytest)
7. [Solver Engines & Policy Comparative Analysis](#7-solver-engines--policy-comparative-analysis)
8. [Docker & Containerized Cloud Deployment](#8-docker--containerized-cloud-deployment)
9. [Programmatic Python API & Automation Guide](#9-programmatic-python-api--automation-guide)
10. [Scientific Metrics Interpretation & Diagnostic Guide](#10-scientific-metrics-interpretation--diagnostic-guide)

---

## 1. Executive Summary & Problem Statement

Modern distribution microgrids are experiencing rapid deployment of intermittent **Distributed Energy Resources (DERs)** (such as rooftop solar PV arrays, wind turbines, and community battery energy storage systems) along with high-concurrency **Electric Vehicle (EV) fast-charging depots**. 

Traditional Distribution Network Reconfiguration (DNR) relies on:
- Static shortest-path algorithms or Mixed-Integer Non-Linear Programming (MINLP).
- Fixed ambient conductor resistance assumptions ($R_0$).
- Convergence times ranging from seconds to minutes, which are unable to track steep sub-second renewable transients ($di/dt$ and $dP/dt$).

### The Thermal Runaway Problem
Conductors heat up quadratically with electric current ($P = 3 I^2 R$). High line temperatures trigger a non-linear resistance rise ($R(T) = R_0 [1 + \alpha (T - T_0)]$). In high-load branches, this forms a positive thermal feedback loop that causes localized thermal hotspots, voltage sag violations below ANSI C84.1 thresholds, and permanent destruction of electrical work capacity (exergy).

### The Qfficient Innovation
**Qfficient** formulates dynamic network reconfiguration as an **entropy-generation minimization problem grounded in non-equilibrium thermodynamics**, compiling dynamic conductor temperatures and physical line flows directly into the **Ising spin glass Hamiltonian** of a quantum annealer.

---

## 2. Complete Technology Stack Specification

| Subsystem | Framework / Technology | Version Requirement | Functional Role in Qfficient |
| :--- | :--- | :--- | :--- |
| **Language Runtime** | **Python (CPython)** | `3.10` / `3.11` | Primary runtime supporting typing, vectorized arithmetic, and multithreading. |
| **Linear Algebra** | **NumPy** | `>=1.26.0` | Vectorized branch current calculations, thermal equations, and matrix QUBO evaluations. |
| **Scientific Computing** | **SciPy** | `>=1.11.0` | Statistical significance testing (paired Student's $t$-tests, $p$-values) and sparse calculations. |
| **Network & Graph Theory** | **NetworkX** | `>=3.0` | Graph representation of electrical feeders, fundamental cycle detection ($C_k$), and spanning trees. |
| **Data Engineering** | **Pandas** | `>=2.0.0` | Time-series telemetry logs, scenario management, and tabular exports. |
| **Quantum Formulation** | **dimod** | `>=0.12.0` | Binary Quadratic Models (BQM), QUBO-to-Ising conversions ($x_i = \frac{s_i+1}{2}$). |
| **Quantum Annealing** | **OpenJij** | `>=0.12.0` | Simulated Quantum Annealing (SQA) engine with transverse magnetic field schedules. |
| **Classical Annealing** | **dwave-neal** | `>=0.6.0` | Simulated classical annealing sampler for algorithm comparison. |
| **Hardware Cloud Access** | **dwave-samplers / Ocean SDK** | `>=1.8.0` | Leap API interface for cloud execution on physical D-Wave Advantage QPUs. |
| **Power Flow Modeling** | **LinDistFlow / FastFeeder** | *Internal Engine* | Linearized AC distribution flow solver calculating branch currents ($I_{ij}$), losses, and voltages ($V_i$). |
| **Thermal Dynamics** | **Differential Conductor Physics** | *Internal Engine* | First-order differential thermal heat balance equations: $C_{\text{th}} \frac{dT}{dt} = 3I^2R - \frac{\Delta T}{\theta}$. |
| **Interactive UI** | **Streamlit** | `>=1.35.0` | Web dashboard with interactive parameter sliders, topology viewer, and real-time report cards. |
| **Visualization** | **Matplotlib** | `>=3.8.0` | 300-DPI publication figures, 4-panel transient dynamics plots, and microgrid network layouts. |
| **CLI Formatting** | **tabulate** | `>=0.10.0` | Formatted terminal output tables for simulation summaries. |
| **Test Automation** | **pytest** | `>=8.0.0` | 23 unit, physics validation, and report integrity tests ensuring radiality, flow sign, and empirical data correspondence. |
| **Containerization** | **Docker & Docker Compose** | Multi-stage | Containerization based on `python:3.11-slim` with healthcheck orchestration. |

---

## 3. Core Physics & Thermodynamic QUBO Formulation

### 3.1 Non-Equilibrium Entropy Generation
For branch set $E$, the transport of electric current through resistive conductors is an irreversible thermodynamic process. At conductor temperature $T_e(t)$, local entropy generation rate $\dot{S}_{\text{gen},e}(t)$ is:

$$\dot{S}_{\text{gen},e}(t) = \frac{\dot{Q}_e(t)}{T_e(t)} = \frac{3 \cdot I_e(t)^2 \cdot R_e(T_e(t))}{T_e(t)} \quad \left[\frac{\text{W}}{\text{K}}\right]$$

### 3.2 The Gouy-Stodola Theorem
The Gouy-Stodola theorem establishes that the rate of usable electrical exergy destroyed is strictly proportional to the thermodynamic entropy generated:

$$E_{x,\text{destroyed}} = T_0 \cdot \int_0^{\Delta t} \sum_{e \in E} \dot{S}_{\text{gen},e}(t) \, dt$$

Where $T_0$ is ambient temperature ($298.15\text{ K}$). Minimizing entropy generation directly maximizes grid delivery capacity.

### 3.3 Conductor Transient Heat Balance
Conductor thermal dynamics are integrated at every step using:

$$C_{\text{th},e} \frac{dT_e(t)}{dt} = 3 \cdot I_e(t)^2 \cdot R_e(T_e(t)) - \frac{T_e(t) - T_{\text{amb}}}{\theta_{\text{th},e}}$$

Where conductor resistance updates non-linearly: $R_e(T_e) = R_{0,e} \cdot [1 + \alpha \cdot (T_e - T_0)]$, with $\alpha \approx 0.00393\text{ K}^{-1}$.

### 3.4 Master Hamiltonian Assembly
For binary switch variables $x_e \in \{0, 1\}$ ($1 = \text{closed}, 0 = \text{open}$):

$$H(x) = -\lambda_{\text{thermo}} H_{\text{thermo}}(x) + \lambda_{\text{cycle}} H_{\text{cycle}}(x) + \lambda_{\text{rad}} H_{\text{rad}}(x) + \lambda_{\text{cap}} H_{\text{cap}}(x) + \lambda_{\text{sw}} H_{\text{sw}}(x)$$

1. **Thermodynamic Objective**: $H_{\text{thermo}}(x) = \sum_{e \in E} w_e x_e$, where $w_e = \frac{3 I_e^2 R_e(T_e)}{T_e}$. In energy minimization $\min H(x)$, the negative linear coefficient $-\lambda_{\text{thermo}} w_e$ prioritizes keeping loaded, low-resistance distribution branches closed ($x_e = 1$) rather than forcing current through high-resistance detours.
2. **Fundamental Cycle-Breaking**: For each independent loop $C_k$, enforce exactly one open switch:
   $$H_{\text{cycle}}(x) = \sum_{k} \left(\sum_{e \in C_k} x_e - (|C_k| - 1)\right)^2$$
3. **Radiality / Spanning Tree Constraint**: Enforce $|V| - N_{\text{sub}}$ active branches:
   $$H_{\text{rad}}(x) = \left(\sum_{e \in E} x_e - (|V| - N_{\text{sub}})\right)^2$$
4. **Thermal Ampacity Limit**: Heavy quadratic penalties when $I_e \to I_{\max,e}$.
5. **Switching Fatigue Penalty**: Penalizes toggling switch states between consecutive time steps.

---

## 4. Project Architecture & File-by-File Blueprint

```
c:/ep-project/
├── app.py                             # Interactive Streamlit Web Portal & Report Card UI
├── main_experiment.py                 # Primary simulation & 4-panel transient dynamics figure generator
├── run_benchmark.py                   # Multi-scenario statistical benchmark & ablation suite
├── run_custom_grid.py                 # Scalable custom microgrid runner (10 to 100 components)
├── run_custom_40.py                   # Preset runner for 40-component microgrid
├── run_custom_60.py                   # Preset runner for 60-component microgrid
├── visualize_microgrid.py             # 12-component microgrid topology diagram generator
├── run_dashboard.bat                  # 1-Click launcher for Windows
├── run_dashboard.sh                   # 1-Click launcher for Linux/macOS
├── pyproject.toml                     # Package installation metadata & console entrypoints
├── requirements.txt                   # Pinned dependency requirements
├── Dockerfile                         # Production container specification (Python 3.11-slim)
├── docker-compose.yml                 # Multi-container service orchestrator
├── README.md                          # Executive project documentation & research outcomes
├── MANUAL.md                          # Comprehensive operations manual & technical guide
├── results/                           # Benchmark reports and telemetry artifacts
│   ├── BENCHMARK_REPORT.md            # Statistical findings, p-values, and claim reconciliation
│   ├── benchmark_distribution.png     # Metric distribution plots across scenarios
│   ├── benchmark_raw.json             # Full step-by-step telemetry data
│   └── benchmark_summary.json         # Mean, standard deviation, and p-value aggregates
├── tests/                             # Pytest test suite (17 passed tests)
│   ├── test_custom_grid.py            # Scalability tests for 10-100 component grids
│   ├── test_fast_flow.py              # LinDistFlow power flow verification tests
│   ├── test_pipeline.py               # End-to-end pipeline & schema integrity tests
│   └── test_qubo_grid.py              # Physics equations & QUBO penalty matrix tests
└── thermodynamic_grid_qubo/           # Core library package
    ├── pipeline.py                    # Unified optimization pipeline & config dataclasses
    ├── grid_engine/                   # Power grid topologies and thermal dynamics
    │   ├── ieee_feeder_loader.py      # IEEE 33-Bus benchmark and 12-component microgrid netlists
    │   ├── custom_grid_generator.py   # Procedural graph generator for 10-100 component microgrids
    │   ├── thermal_dynamics.py        # Differential conductor thermal balance equations
    │   └── renewable_simulator.py     # Solar PV drops, wind ramps, and EV fast-charging surges
    ├── qubo_engine/                   # QUBO and Ising Hamiltonian compilation
    │   ├── qubo_builder.py            # Master Hamiltonian assembly
    │   ├── entropy_calculator.py      # Gouy-Stodola exergy and entropy generation formulas
    │   └── penalty_tuner.py           # Adaptive Lagrangian multiplier tuning
    ├── solvers/                       # Optimization backends
    │   ├── openjij_annealer.py        # OpenJij SQA (Simulated Quantum Annealing)
    │   ├── dwave_qpu_runner.py        # D-Wave Advantage QPU Leap cloud runner
    │   ├── exact_classical_solver.py  # Branch-exchange and dynamic oracle loss minimization
    │   ├── numpy_annealer.py          # High-speed vectorized NumPy annealer
    │   ├── classical_baseline.py      # Unreconfigured / static minimum-resistance baseline
    │   └── ablation_suite.py          # Systematic penalty & solver ablation tests
    └── verification/                  # Power flow and diagnostics
        ├── fast_flow.py               # Vectorized tree LinDistFlow solver
        ├── physics_verifier.py        # Kirchhoff's laws and ANSI C84.1 compliance validation
        ├── metrics_evaluator.py       # Comparative metrics (heat savings, exergy, hotspot reduction)
        ├── microgrid_visualizer.py    # Matplotlib diagram generator for microgrids
        ├── report_card.py             # Formatted visual cards and status checks for UI
        └── ieee33_trees.npy           # Pre-enumerated spanning trees for the IEEE 33-bus feeder
```

---

## 5. Installation & Environment Configuration

### 5.1 Local Virtual Environment
```bash
# Clone the repository
git clone https://github.com/RishDK07/Qfficient-.git
cd Qfficient-

# Create virtual environment
python -m venv .venv

# Activate on Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Activate on Windows (CMD)
.venv\Scripts\activate.bat

# Activate on Linux/macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install in editable mode (registers console CLI tools)
pip install -e .
```

---

## 6. Complete CLI Operations & Command Reference

### 6.1 Interactive Presentation Portal (Streamlit)
Launches the interactive demonstration dashboard at `http://localhost:8501`.

```bash
# Standard launch:
streamlit run app.py

# Using the virtual environment python directly:
.venv\Scripts\python.exe -m streamlit run app.py

# 1-Click Launchers:
run_dashboard.bat     # Windows
./run_dashboard.sh    # Linux/macOS
```

**UI Capabilities**:
- **Grid Models**: IEEE 33-Bus, 12-Component Smart Microgrid, or Custom Grid.
- **Custom Sliders**: 10–100 Buses, 1–15 Tie Lines, customizable Solar/Wind/BESS/EV allocations.
- **Dynamic Stress Injection**: Real-time sliders for Solar Drop (0–90%) and EV Pulse (0–1200 kW).
- **Diagnostics**: Displays live line flows, nodal voltages, Joule heat savings, and network diagrams.

---

### 6.2 Scientific Transient Experiment (IEEE 33-Bus Feeder)
Executes the synchronized transient benchmark (75% solar drop + 800 kW EV charging pulse).

```bash
# Via script:
python main_experiment.py

# Via registered console entrypoint:
thermo-qubo-sim
```

**Outputs Produced**:
- Comprehensive terminal tables comparing Baseline vs. Exact Oracle vs. SQA.
- Generates `thermodynamic_qubo_results.png` (300-DPI publication 4-panel transient analysis).

---

### 6.3 Custom Microgrid Scalability Runner (10 to 100 Buses)
Runs optimization on custom microgrids generated via graph algorithms.

```bash
# Default run (60 components, 6 tie lines, 15 time steps):
python run_custom_grid.py

# 40 components with 4 tie lines:
python run_custom_grid.py --components 40 --ties 4

# 80 components with 8 tie lines over 20 time steps:
python run_custom_grid.py --components 80 --ties 8 --steps 20

# 100 components using Exact Oracle solver:
python run_custom_grid.py --components 100 --ties 8 --solver exact_oracle

# Using the vectorized NumPy annealer:
python run_custom_grid.py --components 50 --ties 5 --solver numpy_annealer

# Ready-made presets:
python run_custom_40.py
python run_custom_60.py
```

**Full Parameter Reference**:

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--components` | `int` | `60` | Number of buses/components (`10` to `100`). |
| `--ties` | `int` | `6` | Normally open candidate tie switches for reconfiguration. |
| `--solver` | `str` | `exact_oracle` | Choice: `exact_oracle`, `numpy_annealer`, `classical`. |
| `--steps` | `int` | `15` | Number of discrete time steps to simulate. |
| `--save-diagram`| `bool`| `True` | Automatically renders and saves `custom_microgrid_<N>.png`. |

---

### 6.4 Multi-Scenario Benchmark & Policy Ablation Suite
Executes a multi-scenario statistical ablation study with Student's $t$-tests and p-value validation.

```bash
# Run 30-scenario statistical benchmark across 8 policies with 5-minute decision intervals:
python run_benchmark.py --n 30 --output-dir results

# Custom scenario batch:
python run_benchmark.py --n 10 --output-dir results
```

**Outputs Created in `results/`**:
- `results/BENCHMARK_REPORT.md`: Comprehensive markdown report generated dynamically from JSON.
- `results/benchmark_summary.json`: Mean, std dev, paired t-tests, and p-value statistical summaries.
- `results/benchmark_raw.json`: Complete raw step-by-step telemetry logs.
- `results/benchmark_distribution.png`: Cumulative energy dissipation distribution chart.

---

### 6.5 Topology & Schematic Visualizer
Generates a dedicated visual schematic of the 12-component microgrid.

```bash
# Via script:
python visualize_microgrid.py

# Via registered console entrypoint:
thermo-qubo-gui
```
- **Output**: Saves `optimized_microgrid.png`.

---

### 6.6 Automated Test Suite Execution (pytest)
Runs 23 unit, physics verification, and scientific integrity tests across 5 modules.

```bash
# Run all tests:
.venv\Scripts\python.exe -m pytest

# Run tests with verbose output:
.venv\Scripts\python.exe -m pytest -v

# Run individual test files:
.venv\Scripts\python.exe -m pytest tests/test_custom_grid.py
.venv\Scripts\python.exe -m pytest tests/test_fast_flow.py
.venv\Scripts\python.exe -m pytest tests/test_pipeline.py
.venv\Scripts\python.exe -m pytest tests/test_qubo_grid.py
.venv\Scripts\python.exe -m pytest tests/test_report_integrity.py
```

---

## 7. Solver Engines & Policy Comparative Analysis

Empirical results from 30 randomized scenarios ($dt = 300\text{ s}$, 12 steps = 1-hour horizon) on the IEEE 33-bus benchmark network:

| Policy / Solver Identifier | Algorithm Description | Dissipation (MJ) | Loss Reduction vs Baseline | ANSI Violations | Mean Latency | Primary Application |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `loss_optimal_candidate_search` | Global candidate tree loss minimization (50k radial trees) | **261.62 ± 60.11** | **+29.06%** ($p = 1.22 \times 10^{-19}$) | 0.00 steps | 41.2 ms | Global theoretical bound. |
| `static_loss_optimal` | Optimal fixed radial configuration (tie switches 7-9, 14-34, 32-33 open) | **265.72 ± 61.20** | **+27.95%** ($p = 3.51 \times 10^{-19}$) | 0.00 steps | 0.00 ms | High-efficiency static planning. |
| `branch_exchange` | Classical Baran-Wu / Civanlar loop branch exchange heuristic | **292.36 ± 69.20** | **+20.73%** ($p = 5.45 \times 10^{-20}$) | 3.40 steps | 1.8 ms | Fast utility baseline. |
| `qubo_filtered` | Thermodynamic QUBO with Kruskal thermal repair heuristic | **355.40 ± 88.46** | **+3.64%** ($p = 0.0194$) | 7.00 steps | 55.4 ms | Near-term hybrid quantum reconfiguration. |
| `standard_static` | Textbook nominal radial topology (tie switches open) | **368.81 ± 87.58** | **0.00%** (Baseline) | 7.43 steps | 0.00 ms | Unreconfigured legacy utility baseline. |
| `qubo_raw` | Thermodynamic QUBO raw binary samples (unrepaired) | **409.08 ± 107.88** | **-10.92%** ($p = 0.0016$) | 11.23 steps | 54.8 ms | Raw Hamiltonian spin formulation. |
| `random_trees_raw` | Random uniform spanning tree selections | **842.12 ± 187.67** | **-128.34%** | 10.37 steps | 0.8 ms | Stochastic null model. |

### D-Wave QPU Hardware Submission
To execute the QUBO on physical quantum hardware:
```bash
# Windows PowerShell:
$env:DWAVE_API_TOKEN="YOUR_LEAP_API_TOKEN"
python main_experiment.py

# Linux/macOS:
export DWAVE_API_TOKEN="YOUR_LEAP_API_TOKEN"
python main_experiment.py
```

---

## 8. Docker & Containerized Cloud Deployment

### Build & Run via Docker CLI:
```bash
# Build the production image:
docker build -t qfficient:latest .

# Run the container mapping port 8501:
docker run -d --name qfficient_app -p 8501:8501 qfficient:latest

# Check container health and logs:
docker ps
docker logs -f qfficient_app

# Stop the container:
docker stop qfficient_app
```

### Run via Docker Compose:
```bash
# Launch in background:
docker compose up -d

# Check service status:
docker compose ps

# Shutdown:
docker compose down
```

---

## 9. Programmatic Python API & Automation Guide

Qfficient can be imported into custom Python applications, automation workflows, or Jupyter notebooks:

```python
from thermodynamic_grid_qubo.pipeline import OptimizationConfig, run_optimization
from thermodynamic_grid_qubo.grid_engine.custom_grid_generator import generate_custom_grid

# 1. Define configuration
config = OptimizationConfig(
    grid="custom",                 # "ieee33", "microgrid12", or "custom"
    solver="exact_oracle",          # "exact_oracle", "sqa", or "numpy_annealer"
    solar_drop_pct=75.0,           # Solar PV transient drop
    ev_surge_kw=800.0,             # EV charging pulse
    ambient_c=25.0,                # Ambient temperature (°C)
    time_steps=20,                 # Observation window steps
    custom_n_components=50,        # Number of buses
    custom_n_ties=5,               # Number of candidate tie lines
)

# 2. Run end-to-end optimization pipeline
results = run_optimization(config)

# 3. Retrieve computed physics metrics
b_heat = sum(results["baseline"]["heat_mj"])
q_heat = sum(results["qubo"]["heat_mj"])
savings = ((b_heat - q_heat) / b_heat) * 100.0

print(f"Baseline Joule Heat:    {b_heat:.3f} MJ")
print(f"Optimized Joule Heat:   {q_heat:.3f} MJ")
print(f"Heat Loss Reduction:    {savings:+.2f}%")
print(f"Voltage Compliant:      {results['checks']['voltage_all_steps']}")
```

---

## 10. Scientific Metrics Interpretation & Diagnostic Guide

1. **Joule Heat Dissipation ($MJ$)**:
   $$\dot{Q} = 3 \cdot \sum_{e \in E_{\text{active}}} I_e^2(t) \cdot R_e(T_e(t)) \cdot \Delta t$$
   Calculates total resistive energy wasted as heat. Lower values indicate improved grid efficiency.

2. **Thermodynamic Entropy Generation ($S_{\text{gen}}$ in $kJ/K$)**:
   $$S_{\text{gen}} = \int \sum_{e} \frac{\dot{Q}_e(t)}{T_e(t)} \, dt$$
   Quantifies thermodynamic irreversibility. Minimizing entropy directly relieves conductor strain.

3. **Exergy Capacity Preserved ($MJ$)**:
   Calculated using the **Gouy-Stodola Theorem** ($E_{x,\text{destroyed}} = T_0 \cdot S_{\text{gen}}$):
   $$\Delta E_x = E_{x,\text{baseline}} - E_{x,\text{reconfigured}}$$
   Represents usable energy delivery capacity saved from thermal dissipation.

4. **ANSI C84.1 Voltage Compliance**:
   $$0.95\text{ p.u.} \le V_{\text{bus}} \le 1.05\text{ p.u.}$$
   Voltages below $0.95\text{ p.u.}$ are classified as undervoltage violations. Qfficient preserves radiality and reduces line impedance drops to eliminate these violations.

5. **Feeder Hotspot Temperature ($^\circ C$)**:
   The peak temperature recorded across any line in the network. Lowering peak feeder temperature prevents insulation degradation and delays thermal expansion sagging.
