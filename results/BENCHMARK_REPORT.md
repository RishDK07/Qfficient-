# Research-Grade Benchmark & Ablation Study

**Testbed**: IEEE 33-Bus Radial Distribution Network (33 Buses, 37 Branches)  
**Scenarios**: 30 independent randomized renewable/load fluctuation profiles  
**Time Horizon**: 12 steps ($dt = 300.0\text{ s}$) per scenario  
**Evaluation Standard**: ANSI C84.1 ($V \in [0.95, 1.05]\text{ pu}$), 3-Phase Joule Heat ($3 I^2 R$)

## 1. Summary Comparison Table

| Policy | Heat (MJ) [Mean ± Std] | Heat Red. vs Std (%) | p-value (t-test) | Peak Temp (°C) | Volt Violations (steps) | Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `standard_static` | 368.805 ± 87.578 | Baseline | — | 47.3°C | 7.4 | 0.00 ms |
| `branch_exchange` | 292.359 ± 69.195 | +20.73% | 5.4526e-20 | 44.6°C | 3.4 | 78.10 ms |
| `static_loss_optimal` | 265.718 ± 61.197 | +27.95% | 3.5128e-19 | 38.7°C | 3.3 | 0.00 ms |
| `loss_optimal_candidate_search` | 261.623 ± 61.079 | +29.06% | 1.2204e-19 | 38.9°C | 3.0 | 62.99 ms |
| `random_trees_raw` | 842.111 ± 259.067 | -128.34% | 6.3234e-14 | 56.7°C | 10.3 | 0.05 ms |
| `random_trees_filtered` | 292.410 ± 72.627 | +20.71% | 2.9566e-22 | 39.7°C | 3.2 | 12.55 ms |
| `qubo_mesh_current_raw` | 409.083 ± 107.876 | -10.92% | 2.3864e-04 | 43.7°C | 6.6 | 241.38 ms |
| `qubo_mesh_current_filtered` | 355.396 ± 88.464 | +3.64% | 0.0194 | 42.7°C | 5.7 | 250.02 ms |

## 2. Key Scientific Findings & Claim Reconciliation

1. **Classical Baseline and Branch Exchange**:
   - The standard baseline is the textbook IEEE 33 nominal configuration (tie lines 32..36 open).
   - Classical branch exchange (`branch_exchange`) provides a strong, physically valid reconfiguration benchmark, achieving **+20.73% loss reduction** ($p = 5.45e-20$).
   - The theoretical optimum across pre-filtered candidate topologies (`loss_optimal_candidate_search`) achieves **+29.06% loss reduction** ($p = 1.22e-19$).

2. **Thermodynamic QUBO Performance**:
   - By correctly setting the linear Hamiltonian weights ($-w_e x_e$), loaded lines stay closed, and tie-switches at minimal mesh current points are broken.
   - Filtered QUBO (`qubo_mesh_current_filtered`) achieves **+3.64% loss reduction** ($p = 1.94e-02$).
   - Raw QUBO (`qubo_mesh_current_raw`) achieves **-10.92% loss reduction** ($p = 2.39e-04$) without post-hoc power-flow re-ranking.

3. **Methodological Rigor**:
   - All metrics above are computed dynamically from 30 independent randomized scenarios with a 5.0-minute decision interval.
   - All reported figures are saved directly to `benchmark_summary.json` with zero hard-coded status strings.
