# Real-World Scenario Input Profiles & Dataset Documentation

## Overview

The Qfficient simulation framework benchmarks dynamic distribution network reconfiguration policies across stochastic load profiles, solar photovoltaic generation curves, wind fluctuations, and high-power electric vehicle (EV) fleet charging surges.

This document details the mathematical formulations, empirical distributions, parameter sources, and licensing for all dynamic profile inputs.

---

## 1. Primary Test Feeder Networks

### 1.1 IEEE 33-Bus Radial Distribution Test Feeder
* **Base Parameters:** $V_{\text{base}} = 12.66\text{ kV}$, $S_{\text{base}} = 10\text{ MVA}$, $Z_{\text{base}} = 16.0276\ \Omega$.
* **Topology:** 33 buses, 32 sectionalizing lines (normally closed, branches 0..31), 5 tie-switches (normally open, branches 32..36).
* **Reference:** M. E. Baran and F. F. Wu, *"Network reconfiguration in distribution systems for loss reduction and load balancing,"* IEEE Transactions on Power Delivery, vol. 4, no. 2, pp. 1401–1407, Apr. 1989.
* **Literature Benchmark:** 
  * Total base load: $3,715\text{ kW}$, $2,300\text{ kVAR}$.
  * Base radial active power loss: $202.68\text{ kW}$ (AC power flow) / $196.93\text{ kW}$ (LinDistFlow).
  * Valid radial spanning tree count: exactly $50,751$ configurations.
  * Baran-Wu exact optimal tie-switches: $\{s_7, s_9, s_{14}, s_{32}, s_{37}\}$ (0-indexed branch IDs: `[6, 8, 13, 31, 36]`).

### 1.2 IEEE 69-Bus Distribution Feeder
* **Base Parameters:** $V_{\text{base}} = 12.66\text{ kV}$, $S_{\text{base}} = 10\text{ MVA}$, $Z_{\text{base}} = 16.0276\ \Omega$.
* **Topology:** 69 buses, 68 sectionalizing branches (normally closed, lines 0..67), 5 tie-switches (normally open, lines 68..72).
* **Reference:** M. E. Baran and F. F. Wu, *"Optimal capacitor placement on radial distribution systems,"* IEEE Transactions on Power Delivery, vol. 4, no. 1, pp. 725–734, Jan. 1989.
* **Tie-Lines:** D. Das, *"Optimal placement of capacitors in radial distribution system using a Fuzzy-GA method,"* IJEPES, 2008 / Savic & Walters, 1989.
  * Open tie switches: $(11-43, 13-21, 15-46, 50-59, 27-65)$.
* **Literature Benchmark:**
  * Total base load: $3,802.10\text{ kW}$, $2,694.70\text{ kVAR}$.
  * Base radial active power loss: $224.99\text{ kW}$ (AC) / $209.00\text{ kW}$ (LinDistFlow).
  * Literature optimal open switches: Branches $\{14, 57, 61, 69, 70\}$ (0-indexed: `[13, 56, 60, 68, 69]`), reducing AC losses to $99.62\text{ kW}$ ($-52.91\%$).

---

## 2. Dynamic Scenario Generation Methodology

Scenarios are instantiated via `Scenario.sample(seed, time_steps, dt_seconds, randomize=True)` with reproducible Mersenne Twister / PCG64 random state seeding.

### 2.1 Diurnal Base Load Variation
For each bus $i$ with base demand $(P_{\text{base}, i}, Q_{\text{base}, i})$:
$$P_i(t) = P_{\text{base}, i} \cdot s_{\text{load}} \left[ 1.0 + 0.05 \sin\left(\frac{2\pi t}{T}\right) + \epsilon_{\text{load}} \right]$$
where $s_{\text{load}} \sim \mathcal{U}(0.85, 1.15)$ scales system-wide loading, and $\epsilon_{\text{load}} \sim \mathcal{N}(0, 0.015^2)$ injects realistic feeder demand jitter.

### 2.2 Solar Photovoltaic (PV) Generation & Cloud Attenuation
Solar generation is hosted at buses 14 and 25 (rated $450\text{ kW}$ peak each) and bus 8 ($250\text{ kW}$ peak):
$$P_{\text{PV}}(t) = P_{\text{rated}} \cdot f_{\text{PV}}(t)$$
During a cloud passage event spanning $t \in [t_{\text{cloud, start}}, t_{\text{cloud, end}}]$:
$$f_{\text{PV}}(t) = \max\left(0.05,\ 1.0 - c_{\text{depth}} \sin\left(\pi \frac{t - t_{\text{cloud, start}}}{t_{\text{cloud, end}} - t_{\text{cloud, start}}}\right)\right)$$
where $c_{\text{depth}} \sim \mathcal{U}(0.35, 0.85)$ models severe irradiance drops. Outside cloud windows, irradiance experiences high-frequency turbulence: $f_{\text{PV}}(t) = 1.0 + 0.05 \cdot \mathcal{N}(0, 1)$.

### 2.3 Wind Generation Fluctuations
Wind generation is located at the lateral terminals (buses 18 and 33, rated $400\text{ kW}$ each):
$$P_{\text{wind}}(t) = \max\left(0.20,\ 0.85 + 0.30 \sin\left(\frac{4\pi t}{T}\right) + 0.10 \cdot \mathcal{N}(0, 1)\right) \cdot P_{\text{rated}}$$

### 2.4 High-Power EV Fleet Depot Surges
High-power commercial fast-charging depots are positioned at buses 22 and 31:
During peak arrival windows $t \in [t_{\text{ev, start}}, t_{\text{ev, end}}]$:
$$P_{\text{EV}}(t) = P_{\text{surge}} \sin\left(\pi \frac{t - t_{\text{ev, start}}}{t_{\text{ev, end}} - t_{\text{ev, start}}}\right)$$
where $P_{\text{surge}} \sim \mathcal{U}(350, 850)\text{ kW}$ (with stress-test surges reaching up to $1,400\text{ kW}$).

---

## 3. Data Licensing & Reproducibility

* **IEEE Distribution Benchmark Data:** Derived from publicly released IEEE Power & Energy Society (PES) Distribution System Analysis Subcommittee benchmark cases and MATPOWER (`case33bw.m`, `case69.m`), licensed under standard BSD-3-Clause / Public Domain educational exemptions.
* **Deterministic Seeding:** Pre-registered seeds `seed=1000..1029` (Phase 2), `seed=2000..2004` (AC Cross-Validation), `seed=3000..3014` (IEEE 69 Feeder), and `seed=5000..5099` (Phase 3 $n=100$ confirmation) ensure exact bit-for-bit replication across operating systems.
