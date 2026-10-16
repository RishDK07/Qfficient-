<div align="center">

# ⚡ Qfficient: Thermodynamic-Mapped QUBO for Dynamic Microgrid Distribution
### *Next-Generation Distribution Network Reconfiguration via Non-Equilibrium Thermodynamics & Quantum Annealing*

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Quantum](https://img.shields.io/badge/Quantum-D--Wave%20%2F%20OpenJij-4A154B?style=for-the-badge&logo=quantum&logoColor=white)](https://www.dwavesys.com/)
[![Framework](https://img.shields.io/badge/Streamlit-App-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-Passing%20(6%2F6)-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](tests/)

<p align="center">
  <b>Dynamic Power Routing</b> • <b>Entropy Minimization</b> • <b>Exergy Preservation</b> • <b>Thermal Runaway Suppression</b>
</p>

</div>

---

## 📌 Executive Summary & Problem Context

Modern electrical distribution microgrids are experiencing rapid penetration of intermittent **Distributed Energy Resources (DERs)**, such as rooftop solar PV arrays, wind turbines, community battery storage (BESS), and ultra-fast electric vehicle (EV) charging depots.

* **The Classical Breakdown**: Traditional distribution network reconfiguration (DNR) relies on static shortest-path algorithms or Mixed-Integer Non-Linear Programming (MINLP). These classical methods assume fixed conductor resistances ($R_0$) and take seconds to minutes to converge—failing to respond during steep, transient renewable surges ($di/dt$ and $dP/dt$).
* **Thermal Runaway**: Real conductors heat up quadratically ($P = I^2 R$). High line temperatures trigger a positive thermal feedback loop where conductor resistance rises non-linearly, escalating thermal degradation and permanently destroying available electrical work (exergy).
* **The Qfficient Innovation**: We reframe dynamic network reconfiguration strictly as an **entropy-generation minimization problem grounded in non-equilibrium thermodynamics**, compiling dynamic conductor temperatures and physical line flows directly into the **Ising spin glass Hamiltonian** of a quantum annealer.

---

## 🏆 Proven Experimental Outcomes (IEEE 33-Bus Benchmark)

Under synchronized transient conditions (a sudden 75% solar PV drop combined with an 800 kW multi-vehicle fast charging depot pulse load), **Qfficient** demonstrated dramatic improvements over the standard minimum-resistance baseline:

| Evaluation Metric | Classical Baseline (Static $R_0$) | Qfficient (Thermodynamic QUBO) | Measured Improvement | Target |
| :--- | :---: | :---: | :---: | :---: |
| **Total Joule Heat Dissipation** | **$4.479\text{ MJ}$** | **$3.470\text{ MJ}$** | **$-22.54\%$ Heat Saved** | $\ge 5.0\%$ Reduction |
| **Cumulative Entropy Generation ($S_{\text{gen}}$)** | $14.968\text{ kJ/K}$ | $11.608\text{ kJ/K}$ | **$-22.45\%$ Entropy Reduction** | $p < 0.01$ |
| **Destroyed Exergy Capacity ($E_x$)** | $4.463\text{ MJ}$ | $3.461\text{ MJ}$ | **$+1.002\text{ MJ}$ Exergy Preserved** | Maximize |
| **Peak Feeder Conductor Temp** | $28.5^\circ\text{C}$ | $27.3^\circ\text{C}$ | **$-1.2^\circ\text{C}$ Hotspot Drop** | Relieve Hotspots |
| **ANSI C84.1 Voltage Violations** | $40\text{ steps}$ | $29\text{ steps}$ | **$27.5\%$ Violation Drop** | Maintain $0.95 - 1.05\text{ p.u.}$ |
| **Solver Convergence Latency** | $0.85\text{ ms}$ | Real-time SQA | **Sub-second Reconfiguration** | Low latency |

---

## 🔬 Core Physics Foundations

### 1. Non-Equilibrium Entropy Generation in Distribution Feeders
In an electrical distribution grid with branch set $E$, the transport of electric current through resistive conductors is an irreversible thermodynamic process. At conductor temperature $T_e(t)$, local entropy generation rate $\dot{S}_{\text{gen},e}(t)$ is:

$$\dot{S}_{\text{gen},e}(t) = \frac{\dot{Q}_e(t)}{T_e(t)} = \frac{3 \cdot I_e(t)^2 \cdot R_e(T_e(t))}{T_e(t)} \quad \left[\frac{\text{W}}{\text{K}}\right]$$

### 2. The Gouy-Stodola Theorem
The Gouy-Stodola theorem establishes that the rate of usable electrical exergy destroyed is strictly proportional to the thermodynamic entropy generated:

$$E_{x,\text{destroyed}} = T_0 \cdot \int_0^{\Delta t} \sum_{e \in E} \dot{S}_{\text{gen},e}(t) \, dt$$

Where $T_0$ is ambient temperature ($298.15\text{ K}$). Minimizing entropy generation directly preserves grid delivery capacity.

### 3. Conductor Transient Heat Balance Equation
Conductor thermal dynamics are integrated at every step using the differential heat balance:

$$C_{\text{th},e} \frac{dT_e(t)}{dt} = 3 \cdot I_e(t)^2 \cdot R_e(T_e(t)) - \frac{T_e(t) - T_{\text{amb}}}{\theta_{\text{th},e}}$$

Conductor resistance updates non-linearly: $R_e(T_e) = R_{0,e} \cdot [1 + \alpha \cdot (T_e - T_0)]$, where $\alpha \approx 0.00393\text{ K}^{-1}$.

---

## ⚛️ Thermodynamic QUBO & Ising Formulation

### Decision Variables
For each switchable line $e \in E$, binary decision variable $x_e \in \{0, 1\}$ denotes:
* $x_e = 1 \implies$ Switch closed (branch energized)
* $x_e = 0 \implies$ Switch open (branch de-energized/isolated)

### Master Hamiltonian
The unconstrained objective function submitted to the quantum annealer is:

$$H(x) = \lambda_{\text{thermo}} H_{\text{thermo}}(x) + \lambda_{\text{cycle}} H_{\text{cycle}}(x) + \lambda_{\text{rad}} H_{\text{rad}}(x) + \lambda_{\text{cap}} H_{\text{cap}}(x) + \lambda_{\text{sw}} H_{\text{sw}}(x)$$

1. **Thermodynamic Dissipation**: $H_{\text{thermo}}(x) = \sum_{e \in E} w_e \cdot x_e$, where $w_e = \frac{3 \cdot I_e^2 \cdot R_e(T_e)}{T_e}$
2. **Fundamental Cycle-Breaking**: For each fundamental loop $C_k$, enforce exactly one open switch:
   $$H_{\text{cycle}}(x) = \sum_{k} \left(\sum_{e \in C_k} x_e - (|C_k| - 1)\right)^2$$
3. **Radiality / Spanning Tree**: Enforce $|V| - N_{\text{sub}}$ active branches ($32$ for IEEE 33-bus):
   $$H_{\text{rad}}(x) = \left(\sum_{e \in E} x_e - (|V| - N_{\text{sub}})\right)^2$$
4. **Thermal Ampacity Limit**: Heavily penalize branches approaching or exceeding rated current $I_{\max,e}$.
5. **Breaker Switching Fatigue**: Penalize toggling switch states between consecutive time steps.

### Mapping to Transverse Ising Spin Glass
Using algebraic transformation $x_i = \frac{s_i + 1}{2}$, where $s_i \in \{-1, +1\}$:

$$H_{\text{Ising}}(s) = \sum_{i} h_i s_i + \sum_{i < j} J_{ij} s_i s_j + \text{Offset}$$

* $h_i$: Local magnetic field bias applied to physical qubit $i$
* $J_{ij}$: Magnetic coupling interaction between physical qubits $i$ and $j$

---

## 📊 Visual Diagnostics & Microgrid Topology

### 1. 12-Component Smart Microgrid Topology
The platform features an integrated topology visualizer displaying active feeder paths (solid green) vs. standing open candidate tie lines (dashed gray) with real-time loss and power flow badges:

<p align="center">
  <img src="optimized_microgrid.png" alt="12-Component Microgrid Topology" width="850">
</p>

### 2. Publication-Quality Transient Dynamics (IEEE 33-Bus Feeder)
<p align="center">
  <img src="thermodynamic_qubo_results.png" alt="Transient Dynamics Comparison" width="850">
</p>

---

## 💻 Interactive Review Portal (Streamlit Dashboard)

Qfficient includes a full-featured presentation dashboard for live demonstrations, evaluators, and project reviews:

```bash
# Launch the interactive review portal
streamlit run app.py
```
* **Local Web Interface**: `http://localhost:8501`
* **Features**:
  * Live sliders for solar irradiance drops ($0 - 90\%$) and EV charging bursts ($0 - 1200\text{ kW}$).
  * Dynamic toggling between Simulated Quantum Annealing (SQA), D-Wave Neal, and Classical Baseline.
  * Real-time metric cards and animated network topology diagrams.

---

## 🚀 Quickstart & Installation

### 1. Clone & Set Up Virtual Environment
```bash
git clone https://github.com/RishDK07/Qfficient-.git
cd Qfficient-

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Experiments & Visualizations
```bash
# Run full scientific simulation (IEEE 33-bus transient benchmark)
python main_experiment.py

# Generate 12-component microgrid topology diagram
python visualize_microgrid.py

# Run automated test suite (6 unit & physics verification tests)
pytest tests/
```

### 4. 1-Click Launchers
* **Windows**: Double-click `run_dashboard.bat`
* **Linux/macOS**: Run `./run_dashboard.sh`
* **Docker**: Run `docker compose up -d`

---

## 🌐 Deploy to Streamlit Community Cloud (Free & 1-Click)

1. Fork or push this repository to your GitHub account.
2. Sign in to **[share.streamlit.io](https://share.streamlit.io)**.
3. Select your repository, set the entry file to `app.py`, and click **Deploy**.
4. You receive an instant public HTTPS URL to present from any device!

---

## 📁 Repository Architecture

```
Qfficient-/
├── requirements.txt                 # Pinned dependencies
├── pyproject.toml                   # Package installation metadata
├── Dockerfile                       # Multi-stage production container
├── docker-compose.yml               # Container orchestration
├── run_dashboard.bat                # Windows 1-click launcher
├── run_dashboard.sh                 # Linux/macOS 1-click launcher
├── app.py                           # Streamlit review portal & interactive dashboard
├── main_experiment.py               # Complete scientific benchmark & figure generator
├── visualize_microgrid.py           # 12-component microgrid diagram generator
├── optimized_microgrid.png          # High-resolution routing diagram
├── thermodynamic_qubo_results.png   # 300 DPI 4-panel transient analysis plot
├── tests/
│   └── test_qubo_grid.py            # Pytest test suite (6 passed tests)
└── thermodynamic_grid_qubo/
    ├── grid_engine/                 # Thermal dynamics, IEEE 33-bus netlists, DER simulator
    ├── qubo_engine/                 # Entropy calculator, BQM compiler, penalty tuner
    ├── solvers/                     # OpenJij SQA, D-Wave QPU runner, classical baseline
    └── verification/                # LinDistFlow power flow, metrics, topology visualizer
```

---

## 🤝 Hardware Quantum Access (D-Wave Advantage QPU)

To submit QUBO matrices directly to physical D-Wave Advantage QPUs in the cloud:
```bash
export DWAVE_API_TOKEN="YOUR_LEAP_API_TOKEN"
python main_experiment.py
```
*(If no token is present, the framework automatically uses local high-performance Simulated Quantum Annealing via OpenJij).*

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