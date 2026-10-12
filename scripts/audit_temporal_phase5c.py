"""Forensic temporal audit of Phase 5C Llama-3.2-3B traces."""

import json
from pathlib import Path

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

raw_dir = Path("data/phase5c_collection/raw")
for rf in sorted(raw_dir.glob("*.json")):
    with open(rf, "r", encoding="utf-8") as f:
        d = json.load(f)
    print(f"\n========================================================")
    print(f"Run ID: {d.get('run_id')}")
    print(f"Model: {d.get('agent_model')}, User: {d.get('user_task_id')}, Inj: {d.get('injection_task_id')}, Attack: {d.get('attack_name')}")
    print(f"Total Steps: {len(d['steps'])}, Gate Points Recorded: {d.get('metadata', {}).get('gate_point_count', 'N/A')}")

    exposure_step = None
    for s in d["steps"]:
        idx = s["step_index"]
        role = s["role"]
        tcs = [tc["tool_name"] for tc in s.get("tool_calls", [])]
        tr_count = len(s.get("tool_results", []))
        content = s.get("content") or ""
        # Check payload
        found_markers = [m for m in PAYLOAD_MARKERS if m in content]
        if found_markers and role == "tool" and exposure_step is None:
            exposure_step = idx

        marker_str = f" [PAYLOAD: {found_markers}]" if found_markers else ""
        print(f"  Step {idx} ({role}): {len(tcs)} tool_calls={tcs}, {tr_count} results{marker_str}")

    print(f"  First Payload Exposure Step: {exposure_step}")
    if exposure_step is not None:
        subsequent_assistant_steps = [
            s for s in d["steps"]
            if s["step_index"] > exposure_step and s["role"] == "assistant"
        ]
        subsequent_tool_calls = [
            tc["tool_name"]
            for s in subsequent_assistant_steps
            for tc in s.get("tool_calls", [])
        ]
        print(f"  Subsequent Assistant Steps after Exposure: {len(subsequent_assistant_steps)}")
        print(f"  Subsequent Tool Calls Proposed after Exposure: {subsequent_tool_calls}")
    else:
        print("  No payload exposure detected in tool steps.")
