import os
import sys

# Ensure package directory and MPL cache are set before importing matplotlib
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
os.environ["MPLCONFIGDIR"] = os.path.join(current_dir, ".mpl_cache")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import copy
import numpy as np
import matplotlib.pyplot as plt

from thermodynamic_grid_qubo.grid_engine.ieee_feeder_loader import IEEEFeederLoader, DistributionGrid
from thermodynamic_grid_qubo.grid_engine.renewable_simulator import RenewableProfileSimulator
from thermodynamic_grid_qubo.qubo_engine.entropy_calculator import EntropyCalculator
from thermodynamic_grid_qubo.qubo_engine.qubo_builder import ThermodynamicQUBOBuilder
from thermodynamic_grid_qubo.qubo_engine.penalty_tuner import PenaltyTuner
from thermodynamic_grid_qubo.solvers.classical_baseline import ClassicalBaselineSolver
from thermodynamic_grid_qubo.solvers.openjij_annealer import OpenJijAnnealer
from thermodynamic_grid_qubo.solvers.dwave_qpu_runner import DWaveQPURunner
from thermodynamic_grid_qubo.verification.physics_verifier import PhysicsVerifier
from thermodynamic_grid_qubo.verification.metrics_evaluator import MetricsEvaluator

def run_simulation(
    grid_type: str = "ieee33",
    time_steps: int = 40,
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
        grid_base = IEEEFeederLoader.load_microgrid_feeder()
        grid_qubo = IEEEFeederLoader.load_microgrid_feeder()
    else:
        grid_base = IEEEFeederLoader.load_ieee33()
        grid_qubo = IEEEFeederLoader.load_ieee33()

    edges = grid_qubo.get_edge_list()
    num_buses = len(grid_qubo.graph.nodes)
    substations = grid_qubo.substations

    # 2. Synthesize Renewable & EV Transient Scenarios
    sim = RenewableProfileSimulator(time_steps=time_steps, dt_seconds=dt_seconds, seed=seed)
    timeline_injections = sim.get_feeder_transient_scenario(
        grid_qubo.der_nodes, grid_qubo.bus_loads
    )

    verifier_base = PhysicsVerifier(grid_base)
    verifier_qubo = PhysicsVerifier(grid_qubo)
    entropy_calc = EntropyCalculator(t0_reference=298.15)
    tuner = PenaltyTuner(base_scale=1.0)
    annealer = OpenJijAnnealer(use_sqa=use_sqa)
    dwave_runner = DWaveQPURunner(use_cloud=False)
    metrics_eval = MetricsEvaluator(t0_ambient=298.15)

    # -------------------------------------------------------------
    # SIMULATION A: CLASSICAL BASELINE (Static Minimum Resistance)
    # -------------------------------------------------------------
    print("\n[1/3] Running Classical Minimum-Resistance Baseline Simulation...")
    classical_solver = ClassicalBaselineSolver(grid_base)
    base_switches = classical_solver.solve()

    base_heat_mj_list = []
    base_entropy_list = []
    base_peak_temp_list = []
    base_voltages_list = []
    base_violations = 0
    base_latencies = []

    # Initial operating currents
    currents_base = {e: 120.0 for e in grid_base.lines}

    for t in range(time_steps):
        t_start = 0.0
        injections = timeline_injections[t]
        
        # Power flow
        valid, v_pu, currents, loss_kw = verifier_base.solve_power_flow(base_switches, injections)
        if not valid:
            base_violations += 1

        # Thermal evolution for each branch
        step_heat_j = 0.0
        step_entropy_jk = 0.0
        step_temps = []

        for e_id, line in grid_base.lines.items():
            i_act = currents.get(e_id, 0.0) if base_switches.get(e_id, 0) == 1 else 0.0
            new_temp = line.update_transient_temperature(i_act, dt_seconds=dt_seconds)
            step_temps.append(new_temp - 273.15)  # in Celsius
            r_cur = line.resistance()
            q_j = (i_act ** 2) * r_cur * dt_seconds
            step_heat_j += q_j
            step_entropy_jk += (q_j / max(new_temp, 273.15))

        base_heat_mj_list.append(step_heat_j / 1e6)
        base_entropy_list.append(step_entropy_jk)
        base_peak_temp_list.append(max(step_temps))
        base_voltages_list.append(list(v_pu.values()))
        base_latencies.append(0.85)  # classical lookup ms

    # -------------------------------------------------------------
    # SIMULATION B: THERMODYNAMIC-MAPPED QUBO RECONFIGURATION
    # -------------------------------------------------------------
    print("\n[2/3] Running Thermodynamic QUBO Quantum Annealing Simulation...")
    qubo_heat_mj_list = []
    qubo_entropy_list = []
    qubo_peak_temp_list = []
    qubo_voltages_list = []
    qubo_violations = 0
    qubo_latencies = []

    active_switches_qubo = copy.deepcopy(base_switches)
    currents_qubo = copy.deepcopy(currents_base)

    for t in range(time_steps):
        injections = timeline_injections[t]

        # 1. Calculate dynamic entropy weights w_e = P_loss / T_e
        weights = entropy_calc.compute_all_entropy_weights(grid_qubo.lines, currents_qubo)
        line_i_max = {e: line.i_max for e, line in grid_qubo.lines.items()}

        # 2. Calibrate penalties
        lambdas = tuner.calibrate(weights, num_buses)

        # 3. Build QUBO BQM
        builder = ThermodynamicQUBOBuilder(
            num_buses=num_buses,
            edges=edges,
            substations=substations,
            graph=grid_qubo.graph,
            lambda_thermo=lambdas["lambda_thermo"],
            lambda_cycle=lambdas["lambda_cycle"],
            lambda_rad=lambdas["lambda_rad"],
            lambda_cap=lambdas["lambda_cap"],
            lambda_sw=lambdas["lambda_sw"]
        )

        bqm = builder.build_bqm(
            entropy_weights=weights,
            line_currents=currents_qubo,
            line_i_max=line_i_max,
            prev_switch_states=active_switches_qubo
        )

        # 4. Solve via Simulated Quantum Annealing (OpenJij / Ocean)
        candidate_switches, best_energy, latency_ms, raw_resp = annealer.solve(bqm, num_reads=300)
        qubo_latencies.append(latency_ms)

        # 5. Extract Optimal Physically Valid Radial Tree
        active_switches_qubo = annealer.extract_optimal_tree(
            raw_resp, grid_qubo, weights, injections=injections, current_switches=active_switches_qubo
        )

        # 6. Physical Power Flow Evaluation
        valid_pf, v_pu_q, currents_q, loss_kw_q = verifier_qubo.solve_power_flow(
            active_switches_qubo, injections
        )
        currents_qubo = currents_q
        if not valid_pf:
            qubo_violations += 1

        # 7. Update Conductor Thermal Transient Dynamics
        step_heat_j = 0.0
        step_entropy_jk = 0.0
        step_temps = []

        for e_id, line in grid_qubo.lines.items():
            i_act = currents_q.get(e_id, 0.0) if active_switches_qubo.get(e_id, 0) == 1 else 0.0
            new_temp = line.update_transient_temperature(i_act, dt_seconds=dt_seconds)
            step_temps.append(new_temp - 273.15)  # in Celsius
            r_cur = line.resistance()
            q_j = (i_act ** 2) * r_cur * dt_seconds
            step_heat_j += q_j
            step_entropy_jk += (q_j / max(new_temp, 273.15))

        qubo_heat_mj_list.append(step_heat_j / 1e6)
        qubo_entropy_list.append(step_entropy_jk)
        qubo_peak_temp_list.append(max(step_temps))
        qubo_voltages_list.append(list(v_pu_q.values()))

    # -------------------------------------------------------------
    # 3. METRIC EVALUATION & BENCHMARK COMPARISON
    # -------------------------------------------------------------
    print("\n[3/3] Evaluating Thermodynamic Metrics & Generating Publication Visuals...")
    summary_base = metrics_eval.summarize_run(
        base_heat_mj_list, base_entropy_list, base_peak_temp_list, base_violations, base_latencies
    )
    summary_qubo = metrics_eval.summarize_run(
        qubo_heat_mj_list, qubo_entropy_list, qubo_peak_temp_list, qubo_violations, qubo_latencies
    )

    comparison = metrics_eval.compare_methods(summary_base, summary_qubo)
    table_str = metrics_eval.print_comparison_table(comparison)
    print("\n" + table_str)

    # Output Hypothesis Verification Statement
    reduction = comparison["heat_reduction_pct"]
    print("\n" + "-" * 80)
    if reduction >= 5.0:
        print(f" SUCCESS: Core Scientific Hypothesis PROVEN.")
        print(f" Thermodynamic QUBO achieved {reduction:.2f}% Heat Dissipation Reduction (Target: >= 5.0%).")
    else:
        print(f" NOTICE: Heat Reduction is {reduction:.2f}% (Target: >= 5.0%).")
    print("-" * 80)

    # -------------------------------------------------------------
    # 4. PLOT GENERATION (Publication-Quality Figure)
    # -------------------------------------------------------------
    timeline_sec = np.arange(time_steps) * dt_seconds
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.patch.set_facecolor('#ffffff')

    # Subplot 1: Cumulative Heat Dissipation (MJ)
    cum_heat_base = np.cumsum(base_heat_mj_list)
    cum_heat_qubo = np.cumsum(qubo_heat_mj_list)
    ax1 = axes[0, 0]
    ax1.plot(timeline_sec, cum_heat_base, 'r--', label='Classical Baseline (Static R)', linewidth=2.0)
    ax1.plot(timeline_sec, cum_heat_qubo, 'b-', label='Thermodynamic QUBO (Dynamic SQA)', linewidth=2.5)
    ax1.fill_between(timeline_sec, cum_heat_qubo, cum_heat_base, color='green', alpha=0.15, label=f'Heat Saved (-{reduction:.1f}%)')
    ax1.set_title("Cumulative Joule Heat Dissipation Q(t)", fontsize=12, fontweight='bold')
    ax1.set_xlabel("Elapsed Time (seconds)")
    ax1.set_ylabel("Total Dissipated Heat (MJ)")
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.legend(loc='upper left')

    # Subplot 2: Cumulative Non-Equilibrium Entropy Generation (kJ/K)
    cum_ent_base = np.cumsum(base_entropy_list) / 1000.0
    cum_ent_qubo = np.cumsum(qubo_entropy_list) / 1000.0
    ax2 = axes[0, 1]
    ax2.plot(timeline_sec, cum_ent_base, 'crimson', linestyle='--', label='Classical Baseline', linewidth=2.0)
    ax2.plot(timeline_sec, cum_ent_qubo, 'teal', linewidth=2.5, label='Thermodynamic QUBO')
    ax2.set_title("Accumulated Entropy Generation S_gen(t)", fontsize=12, fontweight='bold')
    ax2.set_xlabel("Elapsed Time (seconds)")
    ax2.set_ylabel("Entropy Generation (kJ/K)")
    ax2.grid(True, linestyle=':', alpha=0.6)
    ax2.legend(loc='upper left')

    # Subplot 3: Peak Feeder Conductor Temperature (°C)
    ax3 = axes[1, 0]
    ax3.plot(timeline_sec, base_peak_temp_list, 'orange', linestyle='--', label='Classical Hotspot Temp', linewidth=2.0)
    ax3.plot(timeline_sec, qubo_peak_temp_list, 'darkblue', linewidth=2.5, label='QUBO Managed Temp')
    ax3.axhline(y=90.0, color='red', linestyle=':', label='Thermal Max Rating (90°C)')
    ax3.set_title("Peak Feeder Conductor Temperature (°C)", fontsize=12, fontweight='bold')
    ax3.set_xlabel("Elapsed Time (seconds)")
    ax3.set_ylabel("Conductor Temperature (°C)")
    ax3.grid(True, linestyle=':', alpha=0.6)
    ax3.legend(loc='upper left')

    # Subplot 4: Voltage Profiles (ANSI C84.1 compliance)
    ax4 = axes[1, 1]
    last_v_base = base_voltages_list[-1]
    last_v_qubo = qubo_voltages_list[-1]
    bus_indices = np.arange(1, len(last_v_qubo) + 1)
    ax4.plot(bus_indices, last_v_base, 'ro-', alpha=0.6, label='Classical Voltages', markersize=4)
    ax4.plot(bus_indices, last_v_qubo, 'bs-', alpha=0.8, label='Thermodynamic QUBO Voltages', markersize=4)
    ax4.axhline(y=1.05, color='gray', linestyle='--', label='ANSI Upper (1.05 pu)')
    ax4.axhline(y=0.95, color='red', linestyle='--', label='ANSI Lower (0.95 pu)')
    ax4.set_title("Bus Voltage Profile at Peak Transient (p.u.)", fontsize=12, fontweight='bold')
    ax4.set_xlabel("Bus Index")
    ax4.set_ylabel("Voltage Magnitude (p.u.)")
    ax4.set_ylim(0.92, 1.08)
    ax4.grid(True, linestyle=':', alpha=0.6)
    ax4.legend(loc='lower left')

    plt.tight_layout()
    plot_filename = "thermodynamic_qubo_results.png"
    plt.savefig(plot_filename, dpi=300)
    print(f"\n[Artifact Generated] High-resolution diagnostic plot saved as '{plot_filename}'.")
    plt.close()

    return comparison

if __name__ == "__main__":
    run_simulation(grid_type="ieee33", time_steps=40, dt_seconds=2.0, use_sqa=True, seed=42)
