# Thermodynamic QUBO Grid Optimization Report

**Run Identifier:** `b25f3ff1`  
**Network Architecture:** Custom Microgrid (60 Buses, 7 Ties)  
**Dimension:** 60 Buses | 66 Total Lines | 7 Tie Switches  
**QUBO Variables:** 66 Binary Spins | 2145 Quadratic Couplers  
**Solver Engine:** OpenJij Simulated Quantum Annealing (SQA)  
**Execution Timestamp:** 2026-10-17 03:58:08  

---

## 1. Executive Summary

This report evaluates the thermodynamic loss minimization of a **60-bus radial distribution grid** subject to time-varying photovoltaic generation and concentrated electric vehicle charging surges. Using Quantum-Inspired Annealing (Simulated Quantum Annealing / SQA), the distribution topology was dynamically reconfigured via tie switches to minimize non-equilibrium Joule heat dissipation $\dot{Q} = \sum I_e^2 R_e$ while strictly satisfying radiality, Kirchhoff's current/voltage laws, and ANSI C84.1 voltage tolerances.

### Key Performance Indicators (KPIs)
* **Total Joule Heat Saved:** `+7.29%` (11.57 kJ)
* **Entropy Generation Reduction:** `+7.29%` (38.80 J/K)
* **Exergy Preserved:** `11.57 kJ` of available electrical work
* **ANSI C84.1 Voltage Violations:** `0 violations` across all time steps (0.95 <= V_pu <= 1.05)
* **Mean Solver Dispatch Latency:** `819.1 ms` per reconfiguration cycle

---

## 2. Technical & Thermodynamic Benchmark

| Dimension | Baseline Radial Grid | Thermodynamic QUBO | Optimization Delta | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Total Joule Dissipation** | `0.1587 MJ` | `0.1471 MJ` | `+7.29%` | Optimal |
| **Thermodynamic Entropy (S_gen)** | `532.21 J/K` | `493.40 J/K` | `+7.29%` | Reduced |
| **Exergy Destruction (B_dest)** | `0.1587 MJ` | `0.1471 MJ` | `+11.57 kJ preserved` | Preserved |
| **Peak Conductor Temp** | `25.16 °C` | `25.16 °C` | `ΔT = +0.00 °C` | Thermal Safe |
| **ANSI C84.1 Voltage Security** | `100% Compliant` | `100% Compliant` | `0 Violations` | Strict Security |
| **Mean Solver Latency** | `0.67 ms` | `819.1 ms` | Real-time Feasible | < 1.0s |

---

## 3. Dynamic Reconfiguration Telemetry

Over the 40-second simulation horizon, the quantum annealer transferred power flows from overloaded radial trunks to parallel tie lines.

* **Total Breaker Switch Operations:** `16` operations
* **Active Radial Tree Constraint Check:** `PASSED (All trees connected with N-1 active branches)`
* **Branch Overload Occurrences:** `0` overloads (Baseline: `0`)

---

## 4. Engineering Takeaway

By formulating the feeder reconfiguration problem in QUBO space with thermodynamic penalty bounds, the system prevents localized conductor heating and Joule losses without violating graph radiality. Conductor thermal dissipation is reduced, preserving useful exergy and maintaining grid stability during peak EV and solar transient events.
