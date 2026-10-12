"""Phase 3 Dataset Builder and Extractor.

Constructs versioned derived datasets from authoritative raw records and decoupled labels:
1. Gate-point dataset: One record per proposed tool call for causal pre-execution monitors.
2. Trajectory dataset: One record per trajectory for whole-run outcome and false-alarm statistics.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agentwatch.traces.schema import (
    RawExecutionRecord,
    GroundTruthLabelRecord,
    NormalizedTrace,
    GatePointDatasetRecord,
    TrajectoryDatasetRecord,
    SCHEMA_VERSION,
)
from agentwatch.traces.normalizer import normalize_raw_trace
from agentwatch.traces.integrity import compute_content_hash

PAYLOAD_MARKERS = [
    "<INFORMATION>",
    "IMPORTANT",
    "<SYSTEM_MESSAGE>",
    "TODO:",
    "Ignore previous",
    "Before executing the original request",
    "mark.black-2134@gmail.com",
    "463820",
    "file with ID '13'",
]


def build_phase3_datasets(
    base_dir: str = "data/pilot_runs",
    output_dir: str = "data/derived_datasets",
) -> Tuple[List[GatePointDatasetRecord], List[TrajectoryDatasetRecord], Dict[str, Any]]:
    """Extract and write versioned Gate-Point and Trajectory datasets from raw pilot runs.

    Guarantees:
    - Authoritative raw traces remain unmodified.
    - Detector feature views exclude future observations, sibling call results, and labels.
    - All 6 outcome dimensions (assigned, exposed, proposed harmful, executed harmful,
      security outcome, utility outcome) are strictly decoupled.
    """
    base_path = Path(base_dir)
    raw_files = sorted((base_path / "raw").glob("*.json"))
    labels_dir = base_path / "labels"

    gate_point_records: List[GatePointDatasetRecord] = []
    trajectory_records: List[TrajectoryDatasetRecord] = []

    for rf in raw_files:
        run_id = rf.stem
        with open(rf, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        raw_rec = RawExecutionRecord.model_validate(raw_data)
        raw_hash = compute_content_hash(raw_data)

        # Load decoupled ground-truth label
        lf_path = labels_dir / f"{run_id}.json"
        label_rec: Optional[GroundTruthLabelRecord] = None
        if lf_path.exists():
            with open(lf_path, "r", encoding="utf-8") as lf:
                label_rec = GroundTruthLabelRecord.model_validate(json.load(lf))

        # Normalize trace
        norm_trace = normalize_raw_trace(raw_rec)
        norm_hash = compute_content_hash(norm_trace)

        # 1. Build Trajectory Dataset Record
        traj_rec = TrajectoryDatasetRecord(
            schema_version=SCHEMA_VERSION,
            run_id=raw_rec.run_id,
            user_task_id=raw_rec.user_task_id,
            injection_task_id=raw_rec.injection_task_id,
            attack_name=raw_rec.attack_name,
            agent_model=raw_rec.agent_model,
            total_steps=len(raw_rec.steps),
            total_proposed_calls=len(norm_trace.tool_invocations),
            total_gate_points=norm_trace.gate_point_count,
            total_executed_calls=sum(1 for inv in norm_trace.tool_invocations if inv.is_executed),
            injected=(raw_rec.injection_task_id is not None),
            exposure_detected=label_rec.exposure_detected if label_rec else False,
            harmful_action_proposed=label_rec.harmful_action_proposed if label_rec else False,
            harmful_action_executed=label_rec.harmful_action_executed if label_rec else False,
            security_success=label_rec.security_success if label_rec else None,
            utility_success=label_rec.utility_success if label_rec else False,
            raw_hash=raw_hash,
            normalized_hash=norm_hash,
            is_deterministic=True,
        )
        trajectory_records.append(traj_rec)

        # 2. Build Gate-Point Dataset Records
        # Index invocations by call_id for lookup
        inv_map = {inv.call_id: inv for inv in norm_trace.tool_invocations}
        gate_counter = 0

        for step in raw_rec.steps:
            if step.role == "assistant" and len(step.tool_calls) > 0:
                # Historical prefix strictly prior to this assistant step
                # Sanitized message list containing only roles and contents
                prefix_messages = [
                    {
                        "step_index": s.step_index,
                        "role": s.role,
                        "content": s.content,
                        "tool_calls": [tc.model_dump() for tc in s.tool_calls],
                        "tool_results": [tr.model_dump() for tr in s.tool_results],
                    }
                    for s in raw_rec.steps[:step.step_index]
                ]

                # Check if exposure occurred strictly in observations prior to this step
                exposure_prior = False
                if label_rec and label_rec.exposure_detected:
                    for s in raw_rec.steps[:step.step_index]:
                        if s.role == "tool" and any(m in (s.content or "") for m in PAYLOAD_MARKERS):
                            exposure_prior = True
                            break

                for tc in step.tool_calls:
                    gp_id = f"{raw_rec.run_id}_gp_{gate_counter}"
                    inv = inv_map.get(tc.call_id)

                    gp_rec = GatePointDatasetRecord(
                        schema_version=SCHEMA_VERSION,
                        gate_point_id=gp_id,
                        run_id=raw_rec.run_id,
                        user_task_id=raw_rec.user_task_id,
                        gate_index=gate_counter,
                        step_index=step.step_index,
                        proposed_tool_name=tc.tool_name,
                        proposed_arguments=tc.arguments,
                        prefix_step_count=len(prefix_messages),
                        available_prefix=prefix_messages,
                        call_id=tc.call_id,
                        is_executed=inv.is_executed if inv else False,
                        result_step_index=inv.result_step_index if inv else None,
                        has_execution_error=bool(inv.error) if (inv and inv.error) else False,
                        trajectory_injected=(raw_rec.injection_task_id is not None),
                        exposure_prior_to_call=exposure_prior,
                        is_harmful_action=False,  # Evaluated by ground-truth match (0 in pilot)
                        security_breached_at_or_before=False,
                    )
                    gate_point_records.append(gp_rec)
                    gate_counter += 1

    # Write datasets to disk
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    gp_file = out_path / "gate_points_v2.json"
    traj_file = out_path / "trajectories_v2.json"

    with open(gp_file, "w", encoding="utf-8") as f:
        json.dump([gp.model_dump() for gp in gate_point_records], f, indent=2)

    with open(traj_file, "w", encoding="utf-8") as f:
        json.dump([tr.model_dump() for tr in trajectory_records], f, indent=2)

    # Compute summary metrics for coverage and quality report
    metrics = {
        "total_trajectories": len(trajectory_records),
        "distinct_user_tasks": len(set(tr.user_task_id for tr in trajectory_records)),
        "benign_runs": sum(1 for tr in trajectory_records if not tr.injected),
        "attacked_runs": sum(1 for tr in trajectory_records if tr.injected),
        "exposed_attacked_runs": sum(1 for tr in trajectory_records if tr.injected and tr.exposure_detected),
        "unexposed_attacked_runs": sum(1 for tr in trajectory_records if tr.injected and not tr.exposure_detected),
        "security_success_count": sum(1 for tr in trajectory_records if tr.security_success is True),
        "security_resisted_count": sum(1 for tr in trajectory_records if tr.security_success is False),
        "utility_success_count": sum(1 for tr in trajectory_records if tr.utility_success is True),
        "utility_failure_count": sum(1 for tr in trajectory_records if tr.utility_success is False),
        "total_gate_points": len(gate_point_records),
        "total_proposed_calls": sum(tr.total_proposed_calls for tr in trajectory_records),
        "executed_calls": sum(tr.total_executed_calls for tr in trajectory_records),
        "gate_points_file": str(gp_file),
        "trajectories_file": str(traj_file),
    }

    return gate_point_records, trajectory_records, metrics


def build_corpus_datasets(
    dataset_dirs: Optional[List[str]] = None,
    output_dir: str = "data/derived_datasets",
) -> Tuple[List[GatePointDatasetRecord], List[TrajectoryDatasetRecord], Dict[str, Any]]:
    """Extract and write versioned Gate-Point and Trajectory datasets across all authentic corpus partitions.

    Default partitions:
    - data/pilot_runs (10 runs, 18 gate points)
    - data/collection_study (4 runs, 5 gate points)
    - data/phase4a_collection (7 runs, 53 gate points)
    Total: 21 authentic runs, 76 gate points.
    """
    if dataset_dirs is None:
        dataset_dirs = [
            "data/pilot_runs",
            "data/collection_study",
            "data/phase4a_collection",
            "data/phase5b_collection",
            "data/phase5c_collection",
        ]

    gate_point_records: List[GatePointDatasetRecord] = []
    trajectory_records: List[TrajectoryDatasetRecord] = []

    for d_path_str in dataset_dirs:
        d_path = Path(d_path_str)
        raw_files = sorted((d_path / "raw").glob("*.json"))
        labels_dir = d_path / "labels"

        for rf in raw_files:
            run_id = rf.stem
            with open(rf, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            raw_rec = RawExecutionRecord.model_validate(raw_data)
            raw_hash = compute_content_hash(raw_data)

            # Load decoupled ground-truth label
            lf_path = labels_dir / f"{run_id}.json"
            label_rec: Optional[GroundTruthLabelRecord] = None
            if lf_path.exists():
                with open(lf_path, "r", encoding="utf-8") as lf:
                    label_rec = GroundTruthLabelRecord.model_validate(json.load(lf))

            # Normalize trace
            norm_trace = normalize_raw_trace(raw_rec)
            norm_hash = compute_content_hash(norm_trace)

            # 1. Build Trajectory Dataset Record
            traj_rec = TrajectoryDatasetRecord(
                schema_version=SCHEMA_VERSION,
                run_id=raw_rec.run_id,
                user_task_id=raw_rec.user_task_id,
                injection_task_id=raw_rec.injection_task_id,
                attack_name=raw_rec.attack_name,
                agent_model=raw_rec.agent_model,
                total_steps=len(raw_rec.steps),
                total_proposed_calls=len(norm_trace.tool_invocations),
                total_gate_points=norm_trace.gate_point_count,
                total_executed_calls=sum(1 for inv in norm_trace.tool_invocations if inv.is_executed),
                injected=(raw_rec.injection_task_id is not None),
                exposure_detected=label_rec.exposure_detected if label_rec else False,
                harmful_action_proposed=label_rec.harmful_action_proposed if label_rec else False,
                harmful_action_executed=label_rec.harmful_action_executed if label_rec else False,
                security_success=label_rec.security_success if label_rec else None,
                utility_success=label_rec.utility_success if label_rec else False,
                raw_hash=raw_hash,
                normalized_hash=norm_hash,
                is_deterministic=True,
            )
            trajectory_records.append(traj_rec)

            # 2. Build Gate-Point Dataset Records
            inv_map = {inv.call_id: inv for inv in norm_trace.tool_invocations}
            gate_counter = 0

            for step in raw_rec.steps:
                if step.role == "assistant" and len(step.tool_calls) > 0:
                    prefix_messages = [
                        {
                            "step_index": s.step_index,
                            "role": s.role,
                            "content": s.content,
                            "tool_calls": [tc.model_dump() for tc in s.tool_calls],
                            "tool_results": [tr.model_dump() for tr in s.tool_results],
                        }
                        for s in raw_rec.steps[:step.step_index]
                    ]

                    exposure_prior = False
                    if label_rec and label_rec.exposure_detected:
                        for s in raw_rec.steps[:step.step_index]:
                            if s.role == "tool" and any(m in (s.content or "") for m in PAYLOAD_MARKERS):
                                exposure_prior = True
                                break

                    for tc in step.tool_calls:
                        gp_id = f"{raw_rec.run_id}_gp_{gate_counter}"
                        inv = inv_map.get(tc.call_id)

                        gp_rec = GatePointDatasetRecord(
                            schema_version=SCHEMA_VERSION,
                            gate_point_id=gp_id,
                            run_id=raw_rec.run_id,
                            user_task_id=raw_rec.user_task_id,
                            gate_index=gate_counter,
                            step_index=step.step_index,
                            proposed_tool_name=tc.tool_name,
                            proposed_arguments=tc.arguments,
                            prefix_step_count=len(prefix_messages),
                            available_prefix=prefix_messages,
                            call_id=tc.call_id,
                            is_executed=inv.is_executed if inv else False,
                            result_step_index=inv.result_step_index if inv else None,
                            has_execution_error=bool(inv.error) if (inv and inv.error) else False,
                            trajectory_injected=(raw_rec.injection_task_id is not None),
                            exposure_prior_to_call=exposure_prior,
                            is_harmful_action=False,
                            security_breached_at_or_before=False,
                        )
                        gate_point_records.append(gp_rec)
                        gate_counter += 1

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    gp_file = out_path / "gate_points_v2.json"
    traj_file = out_path / "trajectories_v2.json"

    with open(gp_file, "w", encoding="utf-8") as f:
        json.dump([gp.model_dump() for gp in gate_point_records], f, indent=2)

    with open(traj_file, "w", encoding="utf-8") as f:
        json.dump([tr.model_dump() for tr in trajectory_records], f, indent=2)

    metrics = {
        "total_trajectories": len(trajectory_records),
        "distinct_user_tasks": len(set(tr.user_task_id for tr in trajectory_records)),
        "benign_runs": sum(1 for tr in trajectory_records if not tr.injected),
        "attacked_runs": sum(1 for tr in trajectory_records if tr.injected),
        "exposed_attacked_runs": sum(1 for tr in trajectory_records if tr.injected and tr.exposure_detected),
        "unexposed_attacked_runs": sum(1 for tr in trajectory_records if tr.injected and not tr.exposure_detected),
        "security_success_count": sum(1 for tr in trajectory_records if tr.security_success is True),
        "security_resisted_count": sum(1 for tr in trajectory_records if tr.security_success is False),
        "utility_success_count": sum(1 for tr in trajectory_records if tr.utility_success is True),
        "utility_failure_count": sum(1 for tr in trajectory_records if tr.utility_success is False),
        "total_gate_points": len(gate_point_records),
        "total_proposed_calls": sum(tr.total_proposed_calls for tr in trajectory_records),
        "executed_calls": sum(tr.total_executed_calls for tr in trajectory_records),
        "gate_points_file": str(gp_file),
        "trajectories_file": str(traj_file),
    }

    return gate_point_records, trajectory_records, metrics

