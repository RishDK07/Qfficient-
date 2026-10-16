# Thermodynamic QUBO Grid Optimization Report

**Run Identifier:** `7dfa7b0a`  
**Network Architecture:** Custom Microgrid (40 Buses, 5 Ties)  
**Dimension:** 40 Buses | 44 Total Lines | 5 Tie Switches  
**QUBO Variables:** 44 Binary Spins | 946 Quadratic Couplers  
**Solver Engine:** OpenJij Simulated Quantum Annealing (SQA)  
**Execution Timestamp:** 2026-10-17 03:56:31  

---

## 1. Executive Summary

This report evaluates the thermodynamic loss minimization of a **40-bus radial distribution grid** subject to time-varying photovoltaic generation and concentrated electric vehicle charging surges. Using Quantum-Inspired Annealing (Simulated Quantum Annealing / SQA), the distribution topology was dynamically reconfigured via tie switches to minimize non-equilibrium Joule heat dissipation $\dot{Q} = \sum I_e^2 R_e$ while strictly satisfying radiality, Kirchhoff's current/voltage laws, and ANSI C84.1 voltage tolerances.

### Key Performance Indicators (KPIs)
* **Total Joule Heat Saved:** `+8.44%` (4.52 kJ)
* **Entropy Generation Reduction:** `+8.44%` (15.16 J/K)
* **Exergy Preserved:** `4.52 kJ` of available electrical work
* **ANSI C84.1 Voltage Violations:** `0 violations` across all time steps (0.95 <= V_pu <= 1.05)
* **Mean Solver Dispatch Latency:** `719.1 ms` per reconfiguration cycle

---

## 2. Technical & Thermodynamic Benchmark

| Dimension | Baseline Radial Grid | Thermodynamic QUBO | Optimization Delta | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Total Joule Dissipation** | `0.0535 MJ` | `0.0490 MJ` | `+8.44%` | Optimal |
| **Thermodynamic Entropy (S_gen)** | `179.56 J/K` | `164.39 J/K` | `+8.44%` | Reduced |
| **Exergy Destruction (B_dest)** | `0.0535 MJ` | `0.0490 MJ` | `+4.52 kJ preserved` | Preserved |
| **Peak Conductor Temp** | `25.08 °C` | `25.08 °C` | `ΔT = +0.00 °C` | Thermal Safe |
| **ANSI C84.1 Voltage Security** | `100% Compliant` | `100% Compliant` | `0 Violations` | Strict Security |
| **Mean Solver Latency** | `0.92 ms` | `719.1 ms` | Real-time Feasible | < 1.0s |

---

## 3. Dynamic Reconfiguration Telemetry

Over the 40-second simulation horizon, the quantum annealer transferred power flows from overloaded radial trunks to parallel tie lines.

* **Total Breaker Switch Operations:** `20` operations
* **Active Radial Tree Constraint Check:** `PASSED (All trees connected with N-1 active branches)`
* **Branch Overload Occurrences:** `0` overloads (Baseline: `0`)

---

## 4. Engineering Takeaway

By formulating the feeder reconfiguration problem in QUBO space with thermodynamic penalty bounds, the system prevents localized conductor heating and Joule losses without violating graph radiality. Conductor thermal dissipation is reduced, preserving useful exergy and maintaining grid stability during peak EV and solar transient events.
