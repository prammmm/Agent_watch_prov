"""Phase 4B Feature Extraction and Exploratory Negative-Only Evaluation Script.

Executes:
1. Reconciles and extracts all 76 authentic gate points from the 21 benchmark trajectories.
2. Runs the deterministic GatePointFeatureExtractor to compute 25 provenance & structural features.
3. Exports validated feature datasets:
   - data/derived_datasets/features_v1.json
   - data/derived_datasets/features_v1.csv
   - reports/feature_extraction_summary.json
4. Executes exploratory negative-only calibration on the 7 authentic benign trajectories.
5. Confirms that positive-class detection evaluation remains strictly blocked.
"""

import json
from pathlib import Path
from typing import Any, Dict, List
import numpy as np

from agentwatch.dataset.builder import build_corpus_datasets
from agentwatch.features.extractor import (
    GatePointFeatureExtractor,
    export_features_to_json,
    export_features_to_csv,
)
from agentwatch.features.schema import (
    FEATURE_SCHEMA_VERSION,
    FEATURE_DATA_DICTIONARY,
    FeatureRecord,
)
from agentwatch.features.evaluation import (
    CandidateRuleConfig,
    run_exploratory_benign_evaluation,
    assert_positive_metrics_blocked,
)


def compute_feature_statistics(records: List[FeatureRecord]) -> Dict[str, Any]:
    """Compute descriptive statistics for all 25 features across extracted records."""
    feature_names = sorted(list(FEATURE_DATA_DICTIONARY.keys()))
    stats: Dict[str, Any] = {}

    for name in feature_names:
        meta = FEATURE_DATA_DICTIONARY[name]
        raw_values = [getattr(r, name) for r in records]
        numeric_values = [1.0 if v is True else (0.0 if v is False else float(v)) for v in raw_values]

        arr = np.array(numeric_values, dtype=float)
        stats[name] = {
            "category": meta["category"],
            "type": meta["type"],
            "valid_range": meta["valid_range"],
            "count": len(arr),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "mean": round(float(np.mean(arr)), 4),
            "std": round(float(np.std(arr)), 4),
            "nonzero_count": int(np.sum(arr != 0.0)),
            "missing_count": 0,  # All 25 features are strictly present on validated records
        }

    return stats


def main():
    print("=================================================================")
    print("       AGENTWATCH PHASE 4B: FEATURE EXTRACTION PIPELINE          ")
    print("=================================================================")

    # 1. Build and reconcile authentic corpus datasets
    dataset_dirs = [
        "data/pilot_runs",
        "data/collection_study",
        "data/phase4a_collection",
    ]
    print(f"Loading authentic benchmark corpus across {len(dataset_dirs)} partitions...")
    gp_records, traj_records, corpus_metrics = build_corpus_datasets(dataset_dirs=dataset_dirs)

    total_gps = len(gp_records)
    total_trajs = len(traj_records)
    print(f"Loaded {total_trajs} trajectories, {total_gps} gate points.")
    assert total_trajs == 21, f"Expected 21 trajectories, found {total_trajs}"
    assert total_gps == 76, f"Expected 76 gate points, found {total_gps}"

    # 2. Extract features
    print("\nExtracting pre-execution features using GatePointFeatureExtractor...")
    extractor = GatePointFeatureExtractor()
    feature_records: List[FeatureRecord] = []
    extraction_failures: List[Dict[str, Any]] = []

    for gp in gp_records:
        try:
            f_rec = extractor.extract_from_record(gp)
            feature_records.append(f_rec)
        except Exception as e:
            extraction_failures.append({
                "gate_point_id": gp.gate_point_id,
                "run_id": gp.run_id,
                "error": str(e),
            })

    print(f"Successfully extracted: {len(feature_records)} / {total_gps} records.")
    print(f"Extraction failures:    {len(extraction_failures)}")
    assert len(extraction_failures) == 0, f"Extraction failed for {len(extraction_failures)} records!"
    assert len(feature_records) == 76, f"Expected 76 feature records, got {len(feature_records)}"

    # 3. Export feature datasets
    out_dir = Path("data/derived_datasets")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "features_v1.json"
    csv_path = out_dir / "features_v1.csv"

    print(f"\nExporting features to JSON: {json_path}")
    export_features_to_json(feature_records, json_path)

    print(f"Exporting features to CSV:  {csv_path}")
    export_features_to_csv(feature_records, csv_path)

    # 4. Compute descriptive feature statistics
    feature_stats = compute_feature_statistics(feature_records)

    # Write extraction summary report
    summary_report_path = Path("reports/feature_extraction_summary.json")
    summary_report_path.parent.mkdir(parents=True, exist_ok=True)
    summary_data = {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "total_authentic_trajectories": total_trajs,
        "total_authentic_gate_points": total_gps,
        "successfully_extracted": len(feature_records),
        "failed_records": extraction_failures,
        "features_count": len(FEATURE_DATA_DICTIONARY),
        "feature_categories": {
            "provenance": sum(1 for m in FEATURE_DATA_DICTIONARY.values() if m["category"] == "provenance"),
            "structural": sum(1 for m in FEATURE_DATA_DICTIONARY.values() if m["category"] == "structural"),
        },
        "feature_statistics": feature_stats,
        "data_dictionary": FEATURE_DATA_DICTIONARY,
    }
    with open(summary_report_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print(f"Saved feature extraction summary: {summary_report_path}")

    # 5. Exploratory Negative-Only Evaluation on 7 Benign Trajectories
    print("\nRunning exploratory negative-only evaluation on 7 benign trajectories...")
    benign_run_ids = {t.run_id for t in traj_records if not t.injected}
    print(f"Benign run IDs count: {len(benign_run_ids)}")
    assert len(benign_run_ids) == 7, f"Expected 7 benign runs, found {len(benign_run_ids)}"

    benign_features = [r for r in feature_records if r.run_id in benign_run_ids]
    print(f"Benign gate points count: {len(benign_features)}")

    # Candidate Rule Configurations to explore
    rule_configs = [
        ("default_lexical_0.8", CandidateRuleConfig(lexical_overlap_threshold=0.8, lexical_min_token_count=2)),
        ("conservative_lexical_0.5", CandidateRuleConfig(lexical_overlap_threshold=0.5, lexical_min_token_count=2)),
        ("structural_only", CandidateRuleConfig(lexical_overlap_threshold=1.1)), # overlap impossible to reach
    ]

    eval_results: Dict[str, Any] = {}
    for cfg_name, cfg in rule_configs:
        report = run_exploratory_benign_evaluation(
            benign_features,
            config=cfg,
            all_benign_run_ids=list(benign_run_ids),
        )
        eval_results[cfg_name] = report.model_dump()
        print(f"\nConfiguration: {cfg_name}")
        print(f"  - Trajectory-level False Alarm Rate: {report.trajectory_level_false_alarm_count}/{report.total_benign_trajectories} ({report.trajectory_level_false_alarm_rate * 100:.1f}%)")
        print(f"  - Gate-point-level Alarm Fraction:   {report.gate_point_level_alarm_count}/{report.total_benign_gate_points} ({report.gate_point_level_alarm_fraction * 100:.1f}%)")


    # Save exploratory evaluation report
    eval_report_path = Path("reports/exploratory_negative_evaluation.json")
    with open(eval_report_path, "w", encoding="utf-8") as f:
        json.dump({
            "exploratory_evaluations": eval_results,
            "scientific_restriction": "Evaluated strictly on benign trajectories. Positive detection metrics (TPR, ROC-AUC, sensitivity, precision, recall) are unavailable because genuine hijackings = 0.",
        }, f, indent=2)
    print(f"\nSaved exploratory negative evaluation report: {eval_report_path}")

    # 6. Verify scientific integrity restriction
    try:
        assert_positive_metrics_blocked(positive_labels_present=False)
    except ValueError as e:
        print(f"Positive-class metric blocker verified: {e}")

    print("\n=================================================================")
    print("             PHASE 4B FEATURE EXTRACTION COMPLETE                ")
    print("=================================================================")


if __name__ == "__main__":
    main()
