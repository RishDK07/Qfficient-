# Research-Grade Benchmark & Ablation Study

**Testbed**: IEEE 33-Bus Radial Distribution Network (33 Buses, 37 Branches)  
**Scenarios**: 30 independent randomized renewable/load fluctuation profiles  
**Time Horizon**: 12 steps ($dt = 300.0\text{ s}$) per scenario  
**Evaluation Standard**: ANSI C84.1 ($V \in [0.95, 1.05]\text{ pu}$), 3-Phase Joule Heat ($3 I^2 R$)

## 1. Summary Comparison Table

| Policy | Heat (MJ) [Mean ± Std] | Heat Red. vs Std (%) | p-value (t-test) | Peak Temp (°C) | Volt Violations (steps) | Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `standard_static` | 368.805 ± 87.578 | Baseline | — | 47.3°C | 7.4 | 0.00 ms |
| `branch_exchange` | 292.359 ± 69.195 | +20.73% | 5.4526e-20 | 44.6°C | 3.4 | 55.22 ms |
| `static_loss_optimal` | 265.718 ± 61.197 | +27.95% | 3.5128e-19 | 38.7°C | 3.3 | 0.00 ms |
| `loss_optimal_candidate_search` | 261.623 ± 61.079 | +29.06% | 1.2204e-19 | 38.9°C | 3.0 | 45.71 ms |
| `random_proposals_raw` | 627.089 ± 214.974 | -70.03% | 2.2117e-09 | 47.7°C | 8.4 | 1.06 ms |
| `random_proposals_filtered` | 276.148 ± 65.391 | +25.12% | 5.5411e-20 | 38.6°C | 2.5 | 14.29 ms |
| `random_trees_raw` | 842.111 ± 259.067 | -128.34% | 6.3234e-14 | 56.7°C | 10.3 | 0.04 ms |
| `random_trees_filtered` | 292.410 ± 72.627 | +20.71% | 2.9566e-22 | 39.7°C | 3.2 | 9.20 ms |
| `qubo_mesh_current_raw` | 409.083 ± 107.876 | -10.92% | 2.3864e-04 | 43.7°C | 6.6 | 135.71 ms |
| `qubo_mesh_current_filtered` | 355.396 ± 88.464 | +3.64% | 0.0194 | 42.7°C | 5.7 | 142.08 ms |

## 2. Key Scientific Findings & Claim Reconciliation

1. **True ~211 kW Baseline & AC Recalibration**:
   - The textbook IEEE 33 nominal baseline produces **196.93 kW** under linearized LinDistFlow, and **210.74 kW (~211 kW)** under exact non-linear AC DistFlow (Baran & Wu, 1989), reflecting the +7.01% non-linear branch loss feedback ($K_{\text{AC/LinDistFlow}} = 1.0701$).
   - All baseline comparisons evaluate the standard unreconfigured textbook radial network (tie lines 32..36 open).

2. **Classical Branch Exchange & Theoretical Optimum**:
   - Classical branch exchange (`branch_exchange`) provides a fast, physically sound reconfiguration benchmark, achieving **+20.73% loss reduction** ($p = 5.45e-20$).
   - Dynamic candidate tree search across pre-filtered radial configurations (`loss_optimal_candidate_search`) achieves **+29.06% loss reduction** ($p = 1.22e-19$).

3. **Random-Proposals Control vs. QUBO Guidance**:
   - The `random_proposals_filtered` control generates 50 random switch proposals in the configuration space and subjects them to the exact same Kruskal thermal repair and power-flow filter, achieving **+25.12% loss reduction** ($p = 5.54e-20$).
   - Comparing filtered QUBO (**+3.64%**) against random proposals isolates how much guidance comes from the Hamiltonian ground state versus the post-processing filter.

4. **Thermodynamic QUBO Performance**:
   - With the corrected negative linear mapping ($-w_e x_e$), loaded backbone lines are prioritized to stay closed while loop tie-lines with minimum mesh currents are broken.
   - Filtered QUBO (`qubo_mesh_current_filtered`) achieves **+3.64% loss reduction** ($p = 1.94e-02$).
   - Raw QUBO (`qubo_mesh_current_raw`) achieves **-10.92% loss reduction** ($p = 2.39e-04$) without post-hoc power-flow re-ranking.

5. **Realistic Problem Hardness & Quantum Advantage Boundaries**:
   - On the 33-bus testbed (37 binary variables, 5 tie switches), there exist only 50,751 valid radial trees, which an exhaustive classical LinDistFlow oracle evaluates in under 40 ms. Therefore, **no quantum advantage exists or is claimed on the 33-bus system**.
   - Meaningful quantum advantage requires large-scale meshed distribution networks ($>100$ buses, $\ge 15\text{--}20$ tie switches, where tree cardinality exceeds $10^{15}$ and exhaustive classical enumeration becomes NP-hard). The custom grid generator (`run_custom_grid.py`) supports scaling experiments up to 100 components.

6. **Methodological Rigor**:
   - All metrics above are computed dynamically from 30 independent randomized scenarios with a 5.0-minute decision interval.
   - All reported figures are saved directly to `benchmark_summary.json` with zero hard-coded status strings.
