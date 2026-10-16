import os
import sys

# Ensure package directory and MPL cache are set before importing matplotlib
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
os.environ["MPLCONFIGDIR"] = os.path.join(current_dir, ".mpl_cache")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import time
import copy
import numpy as np
import matplotlib.pyplot as plt
from tabulate import tabulate

from thermodynamic_grid_qubo.grid_engine.ieee_feeder_loader import IEEEFeederLoader, DistributionGrid
from thermodynamic_grid_qubo.grid_engine.renewable_simulator import RenewableProfileSimulator
from thermodynamic_grid_qubo.qubo_engine.entropy_calculator import EntropyCalculator
from thermodynamic_grid_qubo.qubo_engine.qubo_builder import ThermodynamicQUBOBuilder
from thermodynamic_grid_qubo.qubo_engine.penalty_tuner import PenaltyTuner
from thermodynamic_grid_qubo.solvers.exact_classical_solver import ExactClassicalSolver
from thermodynamic_grid_qubo.solvers.openjij_annealer import OpenJijAnnealer
from thermodynamic_grid_qubo.solvers.dwave_qpu_runner import DWaveQPURunner
from thermodynamic_grid_qubo.verification.physics_verifier import PhysicsVerifier

def run_simulation(
    grid_type: str = "ieee33",
    time_steps: int = 30,
    dt_seconds: float = 2.0,
    use_sqa: bool = True,
    seed: int = 42
):
    print("=" * 80)
    print("THERMODYNAMIC-MAPPED QUBO POWER DISTRIBUTION RECONFIGURATION ENGINE")
    print(f"Target Feeder: {grid_type.upper()} | Observation Window: {time_steps * dt_seconds}s | SQA: {use_sqa}")
    print("=" * 80)

    # 1. Load Grid Benchmark
    if grid_type == "microgrid":
        grid_std = IEEEFeederLoader.load_microgrid_feeder()
        grid_exact = IEEEFeederLoader.load_microgrid_feeder()
        grid_qubo = IEEEFeederLoader.load_microgrid_feeder()
    else:
        grid_std = IEEEFeederLoader.load_ieee33()
        grid_exact = IEEEFeederLoader.load_ieee33()
        grid_qubo = IEEEFeederLoader.load_ieee33()

    edges = grid_qubo.get_edge_list()
    num_buses = len(grid_qubo.graph.nodes)
    substations = grid_qubo.substations

    # 2. Synthesize Renewable & EV Transient Scenarios
    sim = RenewableProfileSimulator(time_steps=time_steps, dt_seconds=dt_seconds, seed=seed)
    timeline_injections = sim.get_feeder_transient_scenario(
        grid_qubo.der_nodes, grid_qubo.bus_loads
    )

    verifier_std = PhysicsVerifier(grid_std)
    verifier_exact = PhysicsVerifier(grid_exact)
    verifier_qubo = PhysicsVerifier(grid_qubo)
    
    exact_solver = ExactClassicalSolver(grid_exact)
    entropy_calc = EntropyCalculator(t0_reference=298.15)
    tuner = PenaltyTuner(base_scale=1.0)
    annealer = OpenJijAnnealer(use_sqa=use_sqa)

    # -------------------------------------------------------------
    # SIMULATION 1: STANDARD UNRECONFIGURED BASELINE
    # -------------------------------------------------------------
    print("\n[1/3] Running Standard Unreconfigured Feeder Baseline...")
    std_switches, _ = exact_solver.solve_unreconfigured_standard()

    std_heat_mj_list = []
    std_entropy_list = []
    std_peak_temp_list = []
    std_voltages_list = []
    std_latencies = []

    for t in range(time_steps):
        t_start = time.perf_counter()
        injections = timeline_injections[t]
        valid, v_pu, currents, loss_kw = verifier_std.solve_power_flow(std_switches, injections)
        lat_ms = (time.perf_counter() - t_start) * 1000.0
        std_latencies.append(lat_ms)

        step_heat_j = 0.0
        step_entropy_jk = 0.0
        step_temps = []

        for e_id, line in grid_std.lines.items():
            i_act = currents.get(e_id, 0.0) if std_switches.get(e_id, 0) == 1 else 0.0
            new_temp = line.update_transient_temperature(i_act, dt_seconds=dt_seconds)
            step_temps.append(new_temp - 273.15)
            # 3-phase Joule heat
            q_3phi = 3.0 * (i_act ** 2) * line.resistance() * dt_seconds
            step_heat_j += q_3phi
            step_entropy_jk += (q_3phi / max(new_temp, 273.15))

        std_heat_mj_list.append(step_heat_j / 1e6)
        std_entropy_list.append(step_entropy_jk)
        std_peak_temp_list.append(max(step_temps))
        std_voltages_list.append(list(v_pu.values()))

    # -------------------------------------------------------------
    # SIMULATION 2: EXACT CLASSICAL LOSS-MINIMIZING RECONFIGURATION
    # -------------------------------------------------------------
    print("\n[2/3] Running Exact Classical Loss-Minimizing Reconfiguration...")
    exact_heat_mj_list = []
    exact_entropy_list = []
    exact_peak_temp_list = []
    exact_voltages_list = []
    exact_latencies = []

    for t in range(time_steps):
        injections = timeline_injections[t]
        exact_sw, exact_loss, lat_ms = exact_solver.solve_exact_loss_minimizer(injections)
        exact_latencies.append(lat_ms)

        valid, v_pu, currents, loss_kw = verifier_exact.solve_power_flow(exact_sw, injections)

        step_heat_j = 0.0
        step_entropy_jk = 0.0
        step_temps = []

        for e_id, line in grid_exact.lines.items():
            i_act = currents.get(e_id, 0.0) if exact_sw.get(e_id, 0) == 1 else 0.0
            new_temp = line.update_transient_temperature(i_act, dt_seconds=dt_seconds)
            step_temps.append(new_temp - 273.15)
            q_3phi = 3.0 * (i_act ** 2) * line.resistance() * dt_seconds
            step_heat_j += q_3phi
            step_entropy_jk += (q_3phi / max(new_temp, 273.15))

        exact_heat_mj_list.append(step_heat_j / 1e6)
        exact_entropy_list.append(step_entropy_jk)
        exact_peak_temp_list.append(max(step_temps))
        exact_voltages_list.append(list(v_pu.values()))

    # -------------------------------------------------------------
    # SIMULATION 3: THERMODYNAMIC-MAPPED QUBO (Raw SQA Hamiltonian Energy)
    # -------------------------------------------------------------
    print("\n[3/3] Running Thermodynamic QUBO (Raw SQA Ground State)...")
    qubo_heat_mj_list = []
    qubo_entropy_list = []
    qubo_peak_temp_list = []
    qubo_voltages_list = []
    qubo_latencies = []

    active_switches_qubo = copy.deepcopy(std_switches)
    currents_qubo = {e: 100.0 for e in grid_qubo.lines}
    voltages_qubo = {b: 1.0 for b in grid_qubo.graph.nodes}

    for t in range(time_steps):
        t_start = time.perf_counter()
        injections = timeline_injections[t]

        # 1. Estimate closed-state current for all lines (including open ties)
        est_currents = entropy_calc.estimate_closed_branch_currents(
            grid_qubo.lines, currents_qubo, voltages_qubo, grid_qubo.v_base_v
        )

        # 2. Compute non-equilibrium entropy weights: w_e = (3 * I_est^2 * R) / T_e
        weights = entropy_calc.compute_all_entropy_weights(grid_qubo.lines, est_currents)
        line_i_max = {e: line.i_max for e, line in grid_qubo.lines.items()}

        # 3. Calibrate Lagrange multipliers
        lambdas = tuner.calibrate(weights, num_buses)

        # 4. Build QUBO BQM with cycle loop-breaking
        builder = ThermodynamicQUBOBuilder(
            num_buses=num_buses,
            edges=edges,
            substations=substations,
            graph=grid_qubo.graph,
            lambda_thermo=lambdas["lambda_thermo"],
            lambda_cycle=lambdas["lambda_cycle"],
            lambda_rad=lambdas["lambda_rad"],
            lambda_cap=lambdas["lambda_cap"],
            lambda_sw=0.0
        )

        bqm = builder.build_bqm(
            entropy_weights=weights,
            line_currents=est_currents,
            line_i_max=line_i_max,
            prev_switch_states=active_switches_qubo
        )

        # 5. Solve via Simulated Quantum Annealing
        _, best_energy, _, raw_resp = annealer.solve(bqm, num_reads=300)

        # 6. Rank STRICTLY by raw QUBO Hamiltonian energy (zero external power flow filtering!)
        active_switches_qubo, raw_energy = annealer.extract_raw_qubo_tree(raw_resp, grid_qubo)
        lat_ms = (time.perf_counter() - t_start) * 1000.0
        qubo_latencies.append(lat_ms)

        # 7. Evaluate physical power flow for this ground state
        valid_pf, v_pu_q, cur_q, loss_kw_q = verifier_qubo.solve_power_flow(
            active_switches_qubo, injections
        )
        currents_qubo = cur_q
        voltages_qubo = v_pu_q

        # 8. Update Conductor Thermal Transient Dynamics
        step_heat_j = 0.0
        step_entropy_jk = 0.0
        step_temps = []

        for e_id, line in grid_qubo.lines.items():
            i_act = cur_q.get(e_id, 0.0) if active_switches_qubo.get(e_id, 0) == 1 else 0.0
            new_temp = line.update_transient_temperature(i_act, dt_seconds=dt_seconds)
            step_temps.append(new_temp - 273.15)
            q_3phi = 3.0 * (i_act ** 2) * line.resistance() * dt_seconds
            step_heat_j += q_3phi
            step_entropy_jk += (q_3phi / max(new_temp, 273.15))

        qubo_heat_mj_list.append(step_heat_j / 1e6)
        qubo_entropy_list.append(step_entropy_jk)
        qubo_peak_temp_list.append(max(step_temps))
        qubo_voltages_list.append(list(v_pu_q.values()))

    # -------------------------------------------------------------
    # 4. BENCHMARK SUMMARY & COMPARISON TABLE
    # -------------------------------------------------------------
    total_std_heat = float(np.sum(std_heat_mj_list))
    total_exact_heat = float(np.sum(exact_heat_mj_list))
    total_qubo_heat = float(np.sum(qubo_heat_mj_list))

    total_std_ent = float(np.sum(std_entropy_list))
    total_exact_ent = float(np.sum(exact_entropy_list))
    total_qubo_ent = float(np.sum(qubo_entropy_list))

    exact_red = ((total_std_heat - total_exact_heat) / total_std_heat) * 100.0
    qubo_red = ((total_std_heat - total_qubo_heat) / total_std_heat) * 100.0

    table_data = [
        ["Configuration / Method", "Total Heat (MJ)", "Loss Reduction vs Standard", "Total Entropy (kJ/K)", "Peak Temp (°C)", "Mean Latency (ms)"],
        [
            "Standard Unreconfigured",
            f"{total_std_heat:.3f} MJ",
            "0.00% (Baseline)",
            f"{total_std_ent/1000.0:.3f} kJ/K",
            f"{max(std_peak_temp_list):.1f} °C",
            f"{np.mean(std_latencies):.2f} ms"
        ],
        [
            "Exact Classical Loss Minimizer",
            f"{total_exact_heat:.3f} MJ",
            f"-{exact_red:.2f}%",
            f"{total_exact_ent/1000.0:.3f} kJ/K",
            f"{max(exact_peak_temp_list):.1f} °C",
            f"{np.mean(exact_latencies):.2f} ms"
        ],
        [
            "Thermodynamic QUBO (Raw SQA)",
            f"{total_qubo_heat:.3f} MJ",
            f"-{qubo_red:.2f}%",
            f"{total_qubo_ent/1000.0:.3f} kJ/K",
            f"{max(qubo_peak_temp_list):.1f} °C",
            f"{np.mean(qubo_latencies):.2f} ms"
        ]
    ]

    print("\n" + tabulate(table_data, headers="firstrow", tablefmt="fancy_grid"))

    # -------------------------------------------------------------
    # 5. PUBLICATION PLOTS (Tri-Comparison)
    # -------------------------------------------------------------
    timeline_sec = np.arange(time_steps) * dt_seconds
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.patch.set_facecolor('#ffffff')

    # Subplot 1: Cumulative Heat Dissipation (MJ)
    ax1 = axes[0, 0]
    ax1.plot(timeline_sec, np.cumsum(std_heat_mj_list), 'r:', label='Standard Unreconfigured', linewidth=2.0)
    ax1.plot(timeline_sec, np.cumsum(exact_heat_mj_list), 'm-.', label=f'Exact Classical (-{exact_red:.1f}%)', linewidth=2.2)
    ax1.plot(timeline_sec, np.cumsum(qubo_heat_mj_list), 'b-', label=f'Thermodynamic QUBO (-{qubo_red:.1f}%)', linewidth=2.5)
    ax1.set_title("Cumulative Joule Heat Dissipation Q(t)", fontsize=12, fontweight='bold')
    ax1.set_xlabel("Elapsed Time (seconds)")
    ax1.set_ylabel("Total Dissipated Heat (MJ)")
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.legend(loc='upper left')

    # Subplot 2: Cumulative Entropy Generation (kJ/K)
    ax2 = axes[0, 1]
    ax2.plot(timeline_sec, np.cumsum(std_entropy_list) / 1000.0, 'r:', label='Standard Unreconfigured', linewidth=2.0)
    ax2.plot(timeline_sec, np.cumsum(exact_entropy_list) / 1000.0, 'm-.', label='Exact Classical', linewidth=2.2)
    ax2.plot(timeline_sec, np.cumsum(qubo_entropy_list) / 1000.0, 'b-', label='Thermodynamic QUBO', linewidth=2.5)
    ax2.set_title("Accumulated Entropy Generation S_gen(t)", fontsize=12, fontweight='bold')
    ax2.set_xlabel("Elapsed Time (seconds)")
    ax2.set_ylabel("Entropy Generation (kJ/K)")
    ax2.grid(True, linestyle=':', alpha=0.6)
    ax2.legend(loc='upper left')

    # Subplot 3: Peak Feeder Conductor Temperature (°C)
    ax3 = axes[1, 0]
    ax3.plot(timeline_sec, std_peak_temp_list, 'orange', linestyle=':', label='Standard Hotspot Temp', linewidth=2.0)
    ax3.plot(timeline_sec, exact_peak_temp_list, 'purple', linestyle='-.', label='Exact Classical Temp', linewidth=2.0)
    ax3.plot(timeline_sec, qubo_peak_temp_list, 'darkblue', linewidth=2.2, label='QUBO Managed Temp')
    ax3.set_title("Peak Feeder Conductor Temperature (°C)", fontsize=12, fontweight='bold')
    ax3.set_xlabel("Elapsed Time (seconds)")
    ax3.set_ylabel("Conductor Temperature (°C)")
    ax3.grid(True, linestyle=':', alpha=0.6)
    ax3.legend(loc='upper left')

    # Subplot 4: Bus Voltage Profiles
    ax4 = axes[1, 1]
    buses = np.arange(1, len(std_voltages_list[-1]) + 1)
    ax4.plot(buses, std_voltages_list[-1], 'ro:', alpha=0.6, label='Standard Voltages', markersize=3)
    ax4.plot(buses, exact_voltages_list[-1], 'm^-.', alpha=0.7, label='Exact Classical', markersize=3)
    ax4.plot(buses, qubo_voltages_list[-1], 'bs-', alpha=0.8, label='Thermodynamic QUBO', markersize=3)
    ax4.axhline(y=0.95, color='red', linestyle='--', label='ANSI Lower (0.95 pu)')
    ax4.axhline(y=1.05, color='gray', linestyle='--', label='ANSI Upper (1.05 pu)')
    ax4.set_title("Bus Voltage Profile at Peak Transient (p.u.)", fontsize=12, fontweight='bold')
    ax4.set_xlabel("Bus Index")
    ax4.set_ylabel("Voltage Magnitude (p.u.)")
    ax4.grid(True, linestyle=':', alpha=0.6)
    ax4.legend(loc='lower left')

    plt.tight_layout()
    plot_file = "thermodynamic_qubo_results.png"
    plt.savefig(plot_file, dpi=300)
    plt.close()
    print(f"\n[Visual Generated] Saved updated publication plot to '{plot_file}'.")

if __name__ == "__main__":
    run_simulation(grid_type="ieee33", time_steps=30, dt_seconds=2.0, use_sqa=True, seed=42)
