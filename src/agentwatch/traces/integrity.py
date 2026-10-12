"""Data Integrity Verification Utilities for AgentWatch.

Provides cryptographic hashing, run consistency validation, and schema verification
for raw traces, normalized traces, labels, and run manifests.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agentwatch.traces.schema import (
    RawExecutionRecord,
    GroundTruthLabelRecord,
    NormalizedTrace,
    SCHEMA_VERSION,
)
from agentwatch.traces.normalizer import normalize_raw_trace


def compute_content_hash(data: Any) -> str:
    """Compute a deterministic SHA-256 hash of a dictionary or Pydantic model dump."""
    if hasattr(data, "model_dump"):
        dumped = data.model_dump()
    elif isinstance(data, dict):
        dumped = data
    else:
        dumped = json.loads(str(data))
    
    serialized = json.dumps(dumped, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class IntegrityCheckResult:
    """Detailed outcome of an integrity validation pass."""
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.is_valid: bool = True
        self.errors: List[str] = []
        self.raw_hash: Optional[str] = None
        self.normalized_hash: Optional[str] = None
        self.label_hash: Optional[str] = None

    def add_error(self, msg: str) -> None:
        self.is_valid = False
        self.errors.append(msg)


def verify_run_integrity(
    raw_path: Path,
    label_path: Optional[Path] = None,
) -> IntegrityCheckResult:
    """Verify data integrity, schema compliance, and causal linkages for a single run."""
    run_id = raw_path.stem
    result = IntegrityCheckResult(run_id)

    # 1. Inspect and validate raw record
    if not raw_path.exists():
        result.add_error(f"Raw trace file missing: {raw_path}")
        return result

    try:
        with open(raw_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        raw_rec = RawExecutionRecord.model_validate(raw_data)
        result.raw_hash = compute_content_hash(raw_data)
    except Exception as e:
        result.add_error(f"Failed to parse RawExecutionRecord: {str(e)}")
        return result

    if raw_rec.run_id != run_id:
        result.add_error(f"Run ID mismatch: file stem {run_id} != record.run_id {raw_rec.run_id}")

    # 2. Reconstruct normalized trace
    try:
        norm_trace = normalize_raw_trace(raw_rec)
        result.normalized_hash = compute_content_hash(norm_trace)
    except Exception as e:
        result.add_error(f"Failed to rebuild NormalizedTrace: {str(e)}")
        return result

    # Check that tool call count matches invocations
    total_raw_calls = sum(len(s.tool_calls) for s in raw_rec.steps if s.role == "assistant")
    if len(norm_trace.tool_invocations) != total_raw_calls:
        result.add_error(
            f"Invocation count mismatch: raw calls {total_raw_calls} != normalized {len(norm_trace.tool_invocations)}"
        )

    # Check causal linkage: each executed invocation must point to a result step strictly AFTER the call step
    for inv in norm_trace.tool_invocations:
        if inv.is_executed and inv.result_step_index is not None:
            if inv.result_step_index <= inv.call_step_index:
                result.add_error(
                    f"Causal violation in invocation {inv.call_id}: "
                    f"result_step {inv.result_step_index} <= call_step {inv.call_step_index}"
                )

    # 3. Inspect label record if provided
    if label_path is not None:
        if not label_path.exists():
            result.add_error(f"Label file missing: {label_path}")
        else:
            try:
                with open(label_path, "r", encoding="utf-8") as lf:
                    label_data = json.load(lf)
                label_rec = GroundTruthLabelRecord.model_validate(label_data)
                result.label_hash = compute_content_hash(label_data)

                if label_rec.run_id != raw_rec.run_id:
                    result.add_error(
                        f"Label run_id mismatch: label {label_rec.run_id} != raw {raw_rec.run_id}"
                    )

                # Verify consistency between raw trace and label metadata
                is_attacked = raw_rec.injection_task_id is not None
                if label_rec.injected != is_attacked:
                    result.add_error(
                        f"Label injection mismatch: label.injected={label_rec.injected} but raw has injection={raw_rec.injection_task_id}"
                    )
            except Exception as e:
                result.add_error(f"Failed to parse GroundTruthLabelRecord: {str(e)}")

    return result


def audit_pilot_directory(
    base_dir: str = "data/pilot_runs",
) -> Tuple[bool, List[IntegrityCheckResult]]:
    """Run comprehensive integrity audit over all runs in data/pilot_runs."""
    base_path = Path(base_dir)
    raw_files = sorted((base_path / "raw").glob("*.json"))
    labels_dir = base_path / "labels"

    all_valid = True
    results: List[IntegrityCheckResult] = []

    for rf in raw_files:
        lf = labels_dir / rf.name
        res = verify_run_integrity(rf, lf if lf.exists() else None)
        if not res.is_valid:
            all_valid = False
        results.append(res)

    return all_valid, results
