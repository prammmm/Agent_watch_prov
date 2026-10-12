"""Trace Normalizer and Pipeline Parser.

Reconstructs structured NormalizedTrace objects from raw execution records,
linking proposed tool calls with their observations while strictly preserving
pre-execution causal separation.
"""

from typing import Dict, List, Optional
from agentwatch.traces.schema import (
    RawExecutionRecord,
    RawStep,
    RawToolCall,
    RawToolResult,
    NormalizedTrace,
    LinkedToolInvocation,
    SCHEMA_VERSION,
)


def normalize_raw_trace(raw_record: RawExecutionRecord) -> NormalizedTrace:
    """Project an immutable RawExecutionRecord into a NormalizedTrace.

    Pairs each proposed RawToolCall with its corresponding RawToolResult by call_id,
    handling missing results, duplicate call_ids (via FIFO queue matching),
    execution errors, and empty tool rounds.
    """
    # 1. Index all tool results by call_id -> list of (result, step_index) in FIFO order
    results_map: Dict[str, List[tuple[RawToolResult, int]]] = {}
    for step in raw_record.steps:
        if step.role == "tool":
            for tr in step.tool_results:
                cid = tr.call_id or ""
                if cid not in results_map:
                    results_map[cid] = []
                results_map[cid].append((tr, step.step_index))

    # 2. Iterate through assistant steps and link proposed calls
    invocations: List[LinkedToolInvocation] = []
    for step in raw_record.steps:
        if step.role == "assistant":
            for tc in step.tool_calls:
                cid = tc.call_id or ""
                # Pop from FIFO queue if available
                if cid in results_map and len(results_map[cid]) > 0:
                    tr, res_step_idx = results_map[cid].pop(0)
                    invocations.append(
                        LinkedToolInvocation(
                            call_id=cid,
                            tool_name=tc.tool_name,
                            arguments=tc.arguments,
                            call_step_index=step.step_index,
                            result_step_index=res_step_idx,
                            output=tr.output,
                            error=tr.error,
                            is_executed=True,
                        )
                    )
                else:
                    # Tool call was proposed but no matching execution result was observed
                    invocations.append(
                        LinkedToolInvocation(
                            call_id=cid,
                            tool_name=tc.tool_name,
                            arguments=tc.arguments,
                            call_step_index=step.step_index,
                            result_step_index=None,
                            output=None,
                            error=None,
                            is_executed=False,
                        )
                    )

    gp_count = raw_record.metadata.get("gate_point_count", len(invocations))

    return NormalizedTrace(
        schema_version=SCHEMA_VERSION,
        run_id=raw_record.run_id,
        user_task_id=raw_record.user_task_id,
        injection_task_id=raw_record.injection_task_id,
        attack_name=raw_record.attack_name,
        agent_model=raw_record.agent_model,
        total_steps=len(raw_record.steps),
        tool_invocations=invocations,
        gate_point_count=gp_count,
        is_cleanly_terminated=True,
    )
