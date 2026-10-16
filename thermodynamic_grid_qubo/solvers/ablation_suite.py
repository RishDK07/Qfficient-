import time
import random
import numpy as np
import scipy.stats as stats
import networkx as nx
from typing import Dict, List, Tuple, Any

from ..grid_engine.ieee_feeder_loader import IEEEFeederLoader, DistributionGrid
from ..grid_engine.renewable_simulator import RenewableProfileSimulator
from ..qubo_engine.entropy_calculator import EntropyCalculator
from ..qubo_engine.qubo_builder import ThermodynamicQUBOBuilder
from ..qubo_engine.penalty_tuner import PenaltyTuner
from ..solvers.exact_classical_solver import ExactClassicalSolver
from ..solvers.openjij_annealer import OpenJijAnnealer
from ..verification.physics_verifier import PhysicsVerifier

class AblationBenchmarkSuite:
    """
    Comprehensive Rigorous Scientific Benchmark & Ablation Suite.
    
    Ablations evaluated:
    1. Standard_Unreconfigured: Base unswitched IEEE 33-bus feeder.
    2. Random_Spanning_Tree: Random valid radial tree (null control).
    3. Exact_Classical_Min: Global loss-minimizing classical branch exchange.
    4. Classical_SA_Ohmic: Simulated Annealing with static Ohmic weights (I^2 * R_0).
    5. Thermodynamic_SA_RawEnergy: Simulated Annealing with Thermodynamic weights,
       ranked strictly by raw QUBO Hamiltonian energy.
    6. Thermodynamic_SQA_RawEnergy: Simulated Quantum Annealing with Thermodynamic weights,
       ranked strictly by raw QUBO Hamiltonian energy.
       
    Measures:
    - Real wall-clock latency (ms) for every method.
    - Total Joule heat dissipation (MJ) and power loss (kW).
    - Cumulative thermodynamic entropy (kJ/K).
    - Statistical significance (paired t-test and Wilcoxon p-values across multiple seeds).
    """
    def __init__(self, num_scenarios: int = 20, time_steps: int = 30, dt_seconds: float = 2.0):
        self.num_scenarios = num_scenarios
        self.time_steps = time_steps
        self.dt_seconds = dt_seconds

    def generate_random_valid_tree(self, grid: DistributionGrid, rng: random.Random) -> Dict[int, int]:
        """Generates a random valid radial spanning tree on the grid graph."""
        verifier = PhysicsVerifier(grid)
        edges = list(grid.lines.keys())
        # Shuffle edge weights and find MST
        for _ in range(500):
            g = nx.Graph()
            for e, line in grid.lines.items():
                g.add_edge(line.u, line.v, weight=rng.random(), edge_id=e)
            mst = nx.minimum_spanning_tree(g, weight="weight")
            chosen = {data["edge_id"] for _, _, data in mst.edges(data=True)}
            sw = {e: (1 if e in chosen else 0) for e in edges}
            if verifier.is_valid_radial_tree(sw)[0]:
                return sw
        # Fallback to standard
        return {e: (1 if e < 32 else 0) for e in edges}

    def run_benchmark(self) -> Dict[str, Any]:
        grid = IEEEFeederLoader.load_ieee33()
        verifier = PhysicsVerifier(grid)
        exact_solver = ExactClassicalSolver(grid)
        entropy_calc = EntropyCalculator(t0_reference=298.15)
        tuner = PenaltyTuner(base_scale=1.0)
        sa_annealer = OpenJijAnnealer(use_sqa=False)
        sqa_annealer = OpenJijAnnealer(use_sqa=True)

        edges = grid.get_edge_list()
        num_buses = len(grid.graph.nodes)
        substations = grid.substations

        methods = [
            "Standard_Unreconfigured",
            "Random_Spanning_Tree",
            "Exact_Classical_Min",
            "Classical_SA_Ohmic",
            "Thermodynamic_SA_RawEnergy",
            "Thermodynamic_SQA_RawEnergy"
        ]

        # Results storage: method -> list of metrics across scenarios
        scenario_heat_mj = {m: [] for m in methods}
        scenario_entropy_jk = {m: [] for m in methods}
        scenario_latency_ms = {m: [] for m in methods}
        scenario_peak_temp_c = {m: [] for m in methods}

        print(f"\nExecuting Rigorous Ablation Benchmark across {self.num_scenarios} Scenarios/Seeds...")
        print("-" * 75)

        for s_idx in range(self.num_scenarios):
            seed = 100 + s_idx
            rng = random.Random(seed)
            sim = RenewableProfileSimulator(time_steps=self.time_steps, dt_seconds=self.dt_seconds, seed=seed)
            timeline_injections = sim.get_feeder_transient_scenario(grid.der_nodes, grid.bus_loads)

            # Evaluate each method over the timeline
            for m in methods:
                # Reset conductor temperatures for fair identical starting thermal state
                grid.reset_all_thermal_states()
                total_heat_j = 0.0
                total_entropy_jk = 0.0
                latencies = []
                step_temps = []

                # Active switch states for this method
                switches, _ = exact_solver.solve_unreconfigured_standard()
                currents = {e: 100.0 for e in grid.lines}
                voltages = {b: 1.0 for b in grid.graph.nodes}

                for t in range(self.time_steps):
                    injections = timeline_injections[t]

                    t_start = time.perf_counter()

                    if m == "Standard_Unreconfigured":
                        switches, _ = exact_solver.solve_unreconfigured_standard()
                        latency = (time.perf_counter() - t_start) * 1000.0

                    elif m == "Random_Spanning_Tree":
                        switches = self.generate_random_valid_tree(grid, rng)
                        latency = (time.perf_counter() - t_start) * 1000.0

                    elif m == "Exact_Classical_Min":
                        switches, _, latency = exact_solver.solve_exact_loss_minimizer(injections)

                    elif m == "Classical_SA_Ohmic":
                        # Static Ohmic weights w_e = 3 * I_act^2 * R_0
                        ohmic_weights = {e: 3.0 * (currents.get(e, 30.0) ** 2) * line.r0 for e, line in grid.lines.items()}
                        lambdas = tuner.calibrate(ohmic_weights, num_buses)
                        builder = ThermodynamicQUBOBuilder(
                            num_buses, edges, substations, graph=grid.graph,
                            lambda_thermo=lambdas["lambda_thermo"], lambda_cycle=lambdas["lambda_cycle"],
                            lambda_rad=lambdas["lambda_rad"], lambda_cap=lambdas["lambda_cap"], lambda_sw=0.0
                        )
                        bqm = builder.build_bqm(ohmic_weights, currents, {e: line.i_max for e, line in grid.lines.items()})
                        _, _, _, resp = sa_annealer.solve(bqm, num_reads=250)
                        switches, _ = sa_annealer.extract_raw_qubo_tree(resp, grid)
                        latency = (time.perf_counter() - t_start) * 1000.0

                    elif m == "Thermodynamic_SA_RawEnergy":
                        # Closed-state current estimation
                        est_currents = entropy_calc.estimate_closed_branch_currents(
                            grid.lines, currents, voltages, grid.v_base_v
                        )
                        weights = entropy_calc.compute_all_entropy_weights(grid.lines, est_currents)
                        lambdas = tuner.calibrate(weights, num_buses)
                        builder = ThermodynamicQUBOBuilder(
                            num_buses, edges, substations, graph=grid.graph,
                            lambda_thermo=lambdas["lambda_thermo"], lambda_cycle=lambdas["lambda_cycle"],
                            lambda_rad=lambdas["lambda_rad"], lambda_cap=lambdas["lambda_cap"], lambda_sw=0.0
                        )
                        bqm = builder.build_bqm(weights, est_currents, {e: line.i_max for e, line in grid.lines.items()})
                        _, _, _, resp = sa_annealer.solve(bqm, num_reads=250)
                        # Rank strictly by raw QUBO energy
                        switches, _ = sa_annealer.extract_raw_qubo_tree(resp, grid)
                        latency = (time.perf_counter() - t_start) * 1000.0

                    elif m == "Thermodynamic_SQA_RawEnergy":
                        # SQA with closed-state current estimation and raw energy ranking
                        est_currents = entropy_calc.estimate_closed_branch_currents(
                            grid.lines, currents, voltages, grid.v_base_v
                        )
                        weights = entropy_calc.compute_all_entropy_weights(grid.lines, est_currents)
                        lambdas = tuner.calibrate(weights, num_buses)
                        builder = ThermodynamicQUBOBuilder(
                            num_buses, edges, substations, graph=grid.graph,
                            lambda_thermo=lambdas["lambda_thermo"], lambda_cycle=lambdas["lambda_cycle"],
                            lambda_rad=lambdas["lambda_rad"], lambda_cap=lambdas["lambda_cap"], lambda_sw=0.0
                        )
                        bqm = builder.build_bqm(weights, est_currents, {e: line.i_max for e, line in grid.lines.items()})
                        _, _, _, resp = sqa_annealer.solve(bqm, num_reads=250)
                        # Rank strictly by raw QUBO energy
                        switches, _ = sqa_annealer.extract_raw_qubo_tree(resp, grid)
                        latency = (time.perf_counter() - t_start) * 1000.0

                    latencies.append(latency)

                    # Solve physical power flow
                    v_ok, v_pu, cur_a, loss_kw = verifier.solve_power_flow(switches, injections)
                    currents = cur_a
                    voltages = v_pu

                    # Integrate conductor thermal dynamics per phase: C_th dT/dt = I^2 R - ΔT/θ
                    # Total 3-phase heat dissipated: 3 * I^2 * R * dt
                    for e_id, line in grid.lines.items():
                        i_act = cur_a.get(e_id, 0.0) if switches.get(e_id, 0) == 1 else 0.0
                        new_temp = line.update_transient_temperature(i_act, dt_seconds=self.dt_seconds)
                        step_temps.append(new_temp - 273.15)
                        # 3-phase heat
                        q_3phi = 3.0 * (i_act ** 2) * line.resistance() * self.dt_seconds
                        total_heat_j += q_3phi
                        total_entropy_jk += (q_3phi / max(new_temp, 273.15))

                scenario_heat_mj[m].append(total_heat_j / 1e6)
                scenario_entropy_jk[m].append(total_entropy_jk)
                scenario_latency_ms[m].append(float(np.mean(latencies)))
                scenario_peak_temp_c[m].append(float(np.max(step_temps)))

            print(f"Scenario {s_idx + 1:02d}/{self.num_scenarios}: "
                  f"Std={scenario_heat_mj['Standard_Unreconfigured'][-1]:.3f} MJ | "
                  f"Exact={scenario_heat_mj['Exact_Classical_Min'][-1]:.3f} MJ | "
                  f"SQA={scenario_heat_mj['Thermodynamic_SQA_RawEnergy'][-1]:.3f} MJ")

        # Statistical Calculations & p-values
        summary = {}
        base_heats = np.array(scenario_heat_mj["Standard_Unreconfigured"])
        exact_heats = np.array(scenario_heat_mj["Exact_Classical_Min"])

        for m in methods:
            heats = np.array(scenario_heat_mj[m])
            entropies = np.array(scenario_entropy_jk[m])
            lats = np.array(scenario_latency_ms[m])
            temps = np.array(scenario_peak_temp_c[m])

            # Paired t-test vs Standard Unreconfigured
            if m != "Standard_Unreconfigured":
                t_stat, p_val_ttest = stats.ttest_rel(heats, base_heats)
                try:
                    w_stat, p_val_wilcox = stats.wilcoxon(heats - base_heats)
                except Exception:
                    p_val_wilcox = p_val_ttest
                mean_red_pct = float(np.mean((base_heats - heats) / base_heats * 100.0))
            else:
                p_val_ttest = 1.0
                p_val_wilcox = 1.0
                mean_red_pct = 0.0

            summary[m] = {
                "mean_heat_mj": float(np.mean(heats)),
                "std_heat_mj": float(np.std(heats)),
                "mean_reduction_pct": mean_red_pct,
                "mean_entropy_jk": float(np.mean(entropies)),
                "mean_peak_temp_c": float(np.mean(temps)),
                "mean_latency_ms": float(np.mean(lats)),
                "p_value_ttest": float(p_val_ttest),
                "p_value_wilcoxon": float(p_val_wilcox),
            }

        return {
            "summary": summary,
            "raw_heat_mj": scenario_heat_mj,
            "raw_latency_ms": scenario_latency_ms
        }
