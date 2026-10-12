"""Phase 4B Gate Point Feature Extractor.

Coordinates provenance and structural feature extraction on a causal pre-execution feature view:
Causal Feature View -> Provenance Features + Structural Features -> Validated Feature Record.

Guarantees:
- Enforces strict input validation: rejects feature views containing ground-truth labels
  or post-hoc outcome annotations.
- Deterministic extraction: same input produces identical feature values.
- Export to JSON and CSV formats.
"""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agentwatch.features.schema import (
    FeatureRecord,
    FEATURE_SCHEMA_VERSION,
    FEATURE_DATA_DICTIONARY,
)
from agentwatch.features.provenance import extract_provenance_features
from agentwatch.features.structural import extract_structural_features
from agentwatch.features.registry import ToolSchemaRegistry, get_default_registry


PROHIBITED_LABEL_KEYS = {
    "trajectory_injected",
    "exposure_prior_to_call",
    "is_harmful_action",
    "security_breached_at_or_before",
    "is_executed",
    "result_step_index",
    "has_execution_error",
    "security_success",
    "utility_success",
    "harmful_action_proposed",
    "harmful_action_executed",
    "attack_name",
    "injection_technique",
    "injection_task_id",
}


class GatePointFeatureExtractor:
    """Extracts validated pre-execution features from causal gate-point feature views."""

    def __init__(self, registry: Optional[ToolSchemaRegistry] = None):
        self.registry = registry or get_default_registry()

    def extract_from_feature_view(
        self,
        feature_view: Dict[str, Any],
        call_id: Optional[str] = None,
    ) -> FeatureRecord:
        """Extract features from a causal pre-execution feature view dictionary.

        Raises:
            ValueError: If prohibited post-hoc label fields are detected in the input.
        """
        # 1. Enforce strict causal isolation: reject post-hoc label leakage
        leaked_keys = PROHIBITED_LABEL_KEYS.intersection(feature_view.keys())
        if leaked_keys:
            raise ValueError(
                f"Causal isolation violation: Prohibited post-hoc label fields detected in feature view: {sorted(list(leaked_keys))}"
            )

        # 2. Extract required metadata references
        gate_point_id = str(feature_view.get("gate_point_id", "unknown_gp"))
        run_id = str(feature_view.get("run_id", "unknown_run"))
        user_task_id = str(feature_view.get("user_task_id", "unknown_task"))
        gate_index = int(feature_view.get("gate_index", 0))
        step_index = int(feature_view.get("step_index", 0))
        resolved_call_id = str(call_id or feature_view.get("call_id", f"call_{gate_point_id}"))
        proposed_tool_name = str(feature_view.get("proposed_tool_name", ""))
        proposed_arguments = feature_view.get("proposed_arguments", {})
        if not isinstance(proposed_arguments, dict):
            proposed_arguments = {}

        available_prefix = feature_view.get("available_prefix", [])
        if not isinstance(available_prefix, list):
            available_prefix = []

        # 3. Extract Provenance Features (11 features)
        prov_feats = extract_provenance_features(
            proposed_arguments=proposed_arguments,
            available_prefix=available_prefix,
        )

        # 4. Extract Structural Features (14 features)
        struct_feats = extract_structural_features(
            proposed_tool_name=proposed_tool_name,
            proposed_arguments=proposed_arguments,
            call_id=resolved_call_id,
            registry=self.registry,
        )

        # 5. Assemble and return validated FeatureRecord
        return FeatureRecord(
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            gate_point_id=gate_point_id,
            run_id=run_id,
            user_task_id=user_task_id,
            gate_index=gate_index,
            step_index=step_index,
            call_id=resolved_call_id,
            proposed_tool_name=proposed_tool_name,
            **prov_feats,
            **struct_feats,
        )

    def extract_from_record(self, gate_point_record: Any) -> FeatureRecord:
        """Extract features from a GatePointDatasetRecord using its get_feature_view()."""
        feature_view = gate_point_record.get_feature_view()
        call_id = getattr(gate_point_record, "call_id", None)
        return self.extract_from_feature_view(feature_view, call_id=call_id)

    def extract_batch(self, gate_point_records: List[Any]) -> List[FeatureRecord]:
        """Extract features for a batch of GatePointDatasetRecords."""
        return [self.extract_from_record(gp) for gp in gate_point_records]


def export_features_to_json(feature_records: List[FeatureRecord], output_path: Union[str, Path]) -> None:
    """Save feature records to formatted JSON file."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump([rec.model_dump() for rec in feature_records], f, indent=2)


def export_features_to_csv(feature_records: List[FeatureRecord], output_path: Union[str, Path]) -> None:
    """Save feature records to tabular CSV file with deterministic column order."""
    if not feature_records:
        return
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    # Deterministic header: Metadata columns first, then 25 features in alphabetical order
    meta_cols = [
        "feature_schema_version",
        "gate_point_id",
        "run_id",
        "user_task_id",
        "gate_index",
        "step_index",
        "call_id",
        "proposed_tool_name",
    ]
    feature_cols = sorted(list(FEATURE_DATA_DICTIONARY.keys()))
    fieldnames = meta_cols + feature_cols

    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in feature_records:
            d = rec.model_dump()
            writer.writerow({k: d.get(k) for k in fieldnames})
