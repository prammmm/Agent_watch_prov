"""Phase 5D Canonical Multi-Model Feature Extraction.

Extracts the standard 25 provenance and structural features across all 139 authentic
gate points from the 43 canonical trajectories across both models (qwen2.5:3b and llama3.2:3b).

Guarantees:
- Strict causal isolation: feature extractor receives strictly causal pre-execution feature views.
- No ground truth labels, future observations, or runtime outcomes enter the feature vector.
- Comprehensive sidecar metadata preserving run_id, model, partition, task, and temporal exposure.
- Exports versioned outputs without overwriting historical datasets:
  - data/derived_datasets/features_multimodel_v2.json
  - data/derived_datasets/features_multimodel_v2.csv
  - data/derived_datasets/features_multimodel_v2_sidecar.json
  - reports/phase5d_feature_extraction_summary.json
"""

import csv
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
            "is_constant": bool(np.std(arr) == 0.0),
            "missing_count": 0,
        }

    return stats


def extract_multimodel_corpus_features(
    output_dir: str = "data/derived_datasets",
    summary_report_path: str = "reports/phase5d_feature_extraction_summary.json",
) -> Dict[str, Any]:
    print("=== Extracting Multi-Model Canonical Corpus Features (Phase 5D) ===")

    # 1. Load canonical corpus across all 5 partitions
    dataset_dirs = [
        "data/pilot_runs",
        "data/collection_study",
        "data/phase4a_collection",
        "data/phase5b_collection",
        "data/phase5c_collection",
    ]
    gp_records, traj_records, corpus_metrics = build_corpus_datasets(dataset_dirs=dataset_dirs)

    print(f"Loaded {len(traj_records)} trajectories and {len(gp_records)} gate points.")

    # 2. Extract 25 features for each gate point using GatePointFeatureExtractor
    extractor = GatePointFeatureExtractor()
    extracted_features: List[FeatureRecord] = []
    sidecar_metadata: List[Dict[str, Any]] = []

    # Map trajectory run_id to model and partition
    traj_map = {t.run_id: t for t in traj_records}

    for gp in gp_records:
        fview = gp.get_feature_view()
        feat_rec = extractor.extract_from_feature_view(fview, call_id=gp.call_id)
        extracted_features.append(feat_rec)

        # Build sidecar metadata (decoupled from feature vector)
        t_info = traj_map.get(gp.run_id)
        sidecar_metadata.append({
            "gate_point_id": gp.gate_point_id,
            "run_id": gp.run_id,
            "call_id": gp.call_id,
            "proposed_tool_name": gp.proposed_tool_name,
            "user_task_id": gp.user_task_id,
            "gate_index": gp.gate_index,
            "step_index": gp.step_index,
            "agent_model": t_info.agent_model if t_info else "unknown",
            "is_attacked": gp.trajectory_injected,
            "exposure_prior_to_call": gp.exposure_prior_to_call,
            "is_executed": gp.is_executed,
            "has_execution_error": gp.has_execution_error,
        })

    # 3. Export versioned datasets
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    json_file = out_path / "features_multimodel_v2.json"
    csv_file = out_path / "features_multimodel_v2.csv"
    sidecar_file = out_path / "features_multimodel_v2_sidecar.json"
    traj_file = out_path / "trajectories_multimodel_v2.json"

    export_features_to_json(extracted_features, str(json_file))
    export_features_to_csv(extracted_features, str(csv_file))

    with open(sidecar_file, "w", encoding="utf-8") as f:
        json.dump(sidecar_metadata, f, indent=2)

    with open(traj_file, "w", encoding="utf-8") as f:
        json.dump([t.model_dump() for t in traj_records], f, indent=2)

    print(f"Exported {len(extracted_features)} feature records to {json_file} and {csv_file}")
    print(f"Exported sidecar metadata to {sidecar_file}")

    # 4. Feature statistics
    stats = compute_feature_statistics(extracted_features)
    constant_features = [k for k, v in stats.items() if v["is_constant"]]

    # Model breakdowns
    models = sorted(list({m["agent_model"] for m in sidecar_metadata}))
    model_stats = {}
    for m in models:
        m_gps = [f for f, s in zip(extracted_features, sidecar_metadata) if s["agent_model"] == m]
        model_stats[m] = {
            "gate_point_count": len(m_gps),
            "completely_schema_conformant_fraction": round(
                float(np.mean([1.0 if f.is_completely_schema_conformant else 0.0 for f in m_gps])), 4
            ),
            "mean_token_overlap_fraction": round(
                float(np.mean([f.argument_token_overlap_fraction for f in m_gps])), 4
            ),
        }

    summary = {
        "dataset_name": "features_multimodel_v2",
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_count": 25,
        "total_trajectories": len(traj_records),
        "total_gate_points": len(gp_records),
        "total_extracted_records": len(extracted_features),
        "extraction_failures": 0,
        "model_breakdown": model_stats,
        "constant_features": constant_features,
        "constant_feature_count": len(constant_features),
        "feature_statistics": stats,
        "export_paths": {
            "json": str(json_file),
            "csv": str(csv_file),
            "sidecar": str(sidecar_file),
        },
    }

    report_path = Path(summary_report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Feature extraction summary report written to {report_path}")
    return summary


if __name__ == "__main__":
    extract_multimodel_corpus_features()
