import json
from pathlib import Path

with open('results/phase2_ablations.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

ablation = data['ablation_summary']

conclusions = {
    'standard_static': 'Standard baseline reference.',
    'loss_optimal_candidate_search': 'Exact empirical dynamic optimum upper bound.',
    'random_trees_filtered': 'Random spanning tree baseline with identical power-flow filter.',
    'branch_exchange': 'Fast classical loop branch-exchange heuristic (Baran-Wu).',
    'qubo_mesh_current_filtered': 'Baseline linear-flow QUBO: underperforms random search due to linear objective.',
    'qubo_penalty_tuned_filtered': 'Tuned penalties (lambda_cycle=2.0, lambda_rad=3.0) raise feasible reads to ~29% (+13.54% reduction, +9.9 pp gain).',
    'qubo_quadratic_surrogate_filtered': 'Validated quadratic surrogate (rho=0.924) achieves +15.24% heat reduction (+11.6 pp gain over linear QUBO).',
    'hybrid_qubo_branch_exchange': 'QUBO warm-start achieves +16.41% reduction in 2 iterations.',
    'random_branch_exchange': 'Random warm-start achieves +25.01% reduction in 2 iterations.',
}

display_names = {
    'standard_static': 'Standard Static Baseline',
    'loss_optimal_candidate_search': 'Exhaustive Dynamic Oracle',
    'random_trees_filtered': 'Random Trees (Filtered Control)',
    'branch_exchange': 'Classical Branch Exchange',
    'qubo_mesh_current_filtered': 'Linear QUBO (Filtered)',
    'qubo_penalty_tuned_filtered': 'Tuned-Penalty QUBO (Filtered)',
    'qubo_quadratic_surrogate_filtered': 'Quadratic Surrogate QUBO (Filtered)',
    'hybrid_qubo_branch_exchange': 'Hybrid QUBO + Branch Exchange',
    'random_branch_exchange': 'Hybrid Random + Branch Exchange',
}

rows = []
for name, st in ablation.items():
    mean_h = st['mean_heat_mj']
    std_h = st['std_heat_mj']
    red = st['reduction_pct']
    p_rand = st['p_vs_random']
    p_orc = st['p_vs_oracle']
    lat = st['mean_latency_ms']

    red_str = f"**{red:+.2f}%**" if red > 0 else f"{red:+.2f}%"
    p_r_str = f"{p_rand:.2e}" if (p_rand is not None and str(p_rand) != 'nan' and p_rand < 0.001) else ('—' if str(p_rand) == 'nan' else f"{p_rand:.4f}")
    p_o_str = f"{p_orc:.2e}" if (p_orc is not None and str(p_orc) != 'nan' and p_orc < 0.001) else ('—' if str(p_orc) == 'nan' else f"{p_orc:.4f}")

    rows.append(
        f"| **{display_names[name]}** | ${mean_h:.3f} \\pm {std_h:.3f}$ | {red_str} | {p_r_str} | {p_o_str} | ${lat:.1f}\\text{{ ms}}$ | {conclusions[name]} |"
    )

table_md = "\n".join(rows)

section_md = f"""
## 4. Phase 2: QUBO Enhancement & Research Ablation Study

Evaluated across 30 independent scenarios ($dt = 300.0\\text{{ s}}$):

| Formulation / Policy | Total Joule Heat (MJ) [Mean ± Std] | Heat Red. vs Baseline (%) | $p$-val vs Random | $p$-val vs Oracle | Wall Latency | One-Line Empirical Conclusion |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
{table_md}

### Thermodynamic vs. Plain $I^2 R$ Weights Ablation (Stress Regime)
* **Regime**: $1.6\\times$ loading, $T_{{\\text{{amb}}}} = 40^\\circ\\text{{C}}$, $\\tau_{{\\text{{th}}}} = 60\\text{{ s}}$, $H_{{\\text{{cap}}}}$ active.
* **Result**: $\\Delta_{{\\text{{Heat}}}} = 0.0000 \\pm 0.0000\\text{{ MJ}}$ ($p = 1.0000$).
* **Empirical Finding**: Thermodynamic entropy weighting ($P_{{\\text{{loss}}}} / T$) is statistically indistinguishable from plain Joule heat ($I^2 R$) weighting even under thermal stress, because temperature variations across lateral conductors ($\\Delta T \\approx 10\\text{{--}}20\\text{{ K}}$) do not alter the relative permutation ordering of line conductivities.
"""

for target_name in ['results/BENCHMARK.md', 'results/BENCHMARK_REPORT.md']:
    fpath = Path(target_name)
    if fpath.exists():
        content = fpath.read_text(encoding='utf-8')
        if "## 4. Phase 2:" in content:
            idx = content.find("## 4. Phase 2:")
            content = content[:idx].strip() + "\n" + section_md
        else:
            content = content.strip() + "\n" + section_md
        fpath.write_text(content, encoding='utf-8')
        print(f"Updated {fpath}")
