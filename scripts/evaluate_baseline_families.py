"""Phase 5A Baseline Comparison and Feasibility Evaluation CLI.

Executes:
1. Reconciles authentic features from data/derived_datasets/features_v1.json (76 gate points).
2. Evaluates 5 transparent baseline families across all 7 benign trajectories (9 gate points):
   - Structural-Only Baseline
   - Provenance-Only Baseline (0.8)
   - Provenance-Only Baseline (0.5)
   - Combined Disjunctive (OR)
   - Combined Conjunctive (AND)
   - No-Alert Reference
3. Generates auditable diagnostic and feasibility reports:
   - reports/baseline_comparison.json
   - reports/benign_alarm_diagnostics.json
   - reports/feature_redundancy_report.json
   - reports/feasibility_assessment.json
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from agentwatch.features.schema import FeatureRecord
from agentwatch.features.baselines import (
    BaselineConfig,
    BaselineMode,
    get_standard_baseline_configs,
    evaluate_trajectory_baseline,
)
from agentwatch.features.diagnostics import (
    diagnose_benign_alarms,
    audit_feature_redundancy,
    profile_post_exposure_gate_points,
    generate_feasibility_assessment,
)


def main():
    print("=================================================================")
    print("      AGENTWATCH PHASE 5A: BASELINE SEPARATION & FEASIBILITY     ")
    print("=================================================================")

    # 1. Load authentic feature records
    features_path = Path("data/derived_datasets/features_v1.json")
    if not features_path.exists():
        raise FileNotFoundError(f"Missing feature dataset: {features_path}")

    with open(features_path, "r", encoding="utf-8") as f:
        raw_feats = json.load(f)

    feature_records = [FeatureRecord.model_validate(rf) for rf in raw_feats]
    print(f"Loaded {len(feature_records)} authentic gate points from {features_path}")
    assert len(feature_records) == 76, f"Expected 76 gate points, found {len(feature_records)}"

    # 2. Identify the 7 authentic benign trajectories
    datasets = ["data/pilot_runs", "data/collection_study", "data/phase4a_collection"]
    benign_run_ids: List[str] = []
    for d in datasets:
        for rf in Path(d).glob("raw/*.json"):
            with open(rf, "r", encoding="utf-8") as raw_f:
                raw_data = json.load(raw_f)
            if raw_data.get("injection_task_id") is None:
                benign_run_ids.append(raw_data["run_id"])

    benign_run_ids = sorted(list(set(benign_run_ids)))
    print(f"Identified {len(benign_run_ids)} authentic benign trajectories:")
    for b_id in benign_run_ids:
        print(f"  - {b_id}")
    assert len(benign_run_ids) == 7, f"Expected 7 benign trajectories, found {len(benign_run_ids)}"

    benign_features = [r for r in feature_records if r.run_id in set(benign_run_ids)]
    print(f"Total benign gate points: {len(benign_features)} (across 6 tool-bearing runs, 1 zero-call run)")
    assert len(benign_features) == 9, f"Expected 9 benign gate points, found {len(benign_features)}"

    # 3. Evaluate Baseline Families
    print("\n-----------------------------------------------------------------")
    print("            EVALUATING TRANSPARENT BASELINE FAMILIES             ")
    print("-----------------------------------------------------------------")
    configs = get_standard_baseline_configs()
    reports_map: Dict[str, Any] = {}

    table_header = "{:<32} {:<12} {:<16} {:<14} {:<12}".format(
        "Baseline Configuration", "Mode", "Traj FAR (7)", "Tool FAR (6)", "GP FAR (9)"
    )
    print(table_header)
    print("-" * 88)

    for cfg in configs:
        report = evaluate_trajectory_baseline(
            feature_records=benign_features,
            all_benign_run_ids=benign_run_ids,
            config=cfg,
        )
        reports_map[cfg.config_id] = report.model_dump()

        row = "{:<32} {:<12} {:<16} {:<14} {:<12}".format(
            cfg.config_id,
            cfg.mode.value[:10],
            f"{report.trajectory_alarm_count}/7 ({report.trajectory_level_alarm_rate*100:.1f}%)",
            f"{report.trajectory_alarm_count}/6 ({report.tool_bearing_trajectory_level_alarm_rate*100:.1f}%)",
            f"{report.gate_point_alarm_count}/9 ({report.gate_point_level_alarm_fraction*100:.1f}%)",
        )
        print(row)

    # Export Baseline Comparison Report
    comp_path = Path("reports/baseline_comparison.json")
    comp_path.parent.mkdir(parents=True, exist_ok=True)
    with open(comp_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "baseline_evaluations": reports_map,
                "dataset_provenance": "data/derived_datasets/features_v1.json",
                "benign_trajectories_count": len(benign_run_ids),
                "benign_gate_points_count": len(benign_features),
            },
            f,
            indent=2,
        )
    print(f"\nSaved baseline comparison report: {comp_path}")

    # 4. Diagnose Benign False Alarms
    print("\n-----------------------------------------------------------------")
    print("             DIAGNOSING BENIGN FALSE-ALARM INCIDENTS             ")
    print("-----------------------------------------------------------------")
    diagnoses = diagnose_benign_alarms(feature_records)
    print(f"Diagnosed {len(diagnoses)} benign alarm gate points:")
    for d in diagnoses:
        print(f"  Gate Point: {d.gate_point_id} ({d.proposed_tool_name})")
        print(f"    Unexpected Keys:      {d.unexpected_keys}")
        print(f"    Official Parameters:  {d.official_declared_properties}")
        print(f"    Validation Issue:     {d.is_tool_validation_issue}")
        print(f"    Security Compromise:  {d.is_security_compromise}")

    diag_path = Path("reports/benign_alarm_diagnostics.json")
    with open(diag_path, "w", encoding="utf-8") as f:
        json.dump([d.model_dump() for d in diagnoses], f, indent=2)
    print(f"Saved benign alarm diagnostics: {diag_path}")

    # 5. Feature Redundancy and Quality Audit
    print("\n-----------------------------------------------------------------")
    print("               FEATURE QUALITY & REDUNDANCY AUDIT                ")
    print("-----------------------------------------------------------------")
    redundancy_audit = audit_feature_redundancy(feature_records)
    print(f"Total Features Audited:    {redundancy_audit.total_features}")
    print(f"Constant Features:         {len(redundancy_audit.constant_features)} {redundancy_audit.constant_features}")
    print(f"Near-Constant Features:    {len(redundancy_audit.near_constant_features)} {redundancy_audit.near_constant_features}")
    print(f"Identical Feature Pairs:   {len(redundancy_audit.identical_feature_pairs)}")
    for p in redundancy_audit.identical_feature_pairs:
        print(f"  - {p[0]} == {p[1]}")
    print(f"Highly Correlated Pairs:   {len(redundancy_audit.highly_correlated_pairs)}")
    for p in redundancy_audit.highly_correlated_pairs:
        print(f"  - {p[0]} vs {p[1]} (r = {p[2]})")

    red_path = Path("reports/feature_redundancy_report.json")
    with open(red_path, "w", encoding="utf-8") as f:
        json.dump(redundancy_audit.model_dump(), f, indent=2)
    print(f"Saved feature redundancy report: {red_path}")

    # 6. Post-Exposure Coverage Profiling
    print("\n-----------------------------------------------------------------")
    print("             POST-EXPOSURE GATE POINT COVERAGE PROFILE           ")
    print("-----------------------------------------------------------------")
    post_exp_profiles = profile_post_exposure_gate_points(feature_records)
    print(f"Profiled {len(post_exp_profiles)} post-exposure gate points (user_task_4):")
    for prof in post_exp_profiles:
        print(f"  GP {prof['gate_index']} ({prof['proposed_tool_name']}):")
        print(f"    Lexical Overlap Fraction: {prof['argument_token_overlap_fraction']}")
        print(f"    Completely Conformant:    {prof['is_completely_schema_conformant']}")
        print(f"    Insight:                  {prof['insight']}")

    # 7. Generate Feasibility Assessment
    print("\n-----------------------------------------------------------------")
    print("                 PHASE 5A FEASIBILITY VERDICT                    ")
    print("-----------------------------------------------------------------")
    feasibility = generate_feasibility_assessment()
    print(f"Engineering Pipeline Validated:         {feasibility.engineering_pipeline_validated}")
    print(f"Exploratory Rule Comparison Completed:  {feasibility.exploratory_rule_comparison_completed}")
    print(f"Positive-Class Evaluation Blocked:      {feasibility.positive_class_evaluation_blocked}")
    print(f"Research Hypothesis Validated:          {not feasibility.research_hypothesis_not_yet_validated}")

    feas_path = Path("reports/feasibility_assessment.json")
    with open(feas_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "verdict_report": feasibility.model_dump(),
                "post_exposure_profiles": post_exp_profiles,
            },
            f,
            indent=2,
        )
    print(f"\nSaved feasibility assessment report: {feas_path}")

    print("\n=================================================================")
    print("             PHASE 5A BASELINE EVALUATION COMPLETE               ")
    print("=================================================================")


if __name__ == "__main__":
    main()
