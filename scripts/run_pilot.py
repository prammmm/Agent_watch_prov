"""CLI and orchestration runner for the Phase 1 Pilot Experiment.

Handles:
- Backend pre-flight checks and diagnostics (without secret leakage)
- Pilot execution across 5 attacked pairs and 5 benign comparison runs
- Preservation of raw execution records and decoupled ground-truth labels
- Generation of the reproducible run manifest
"""

import os
import sys
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentwatch.benchmark.pilot_harness import check_backend_credentials, run_single_pilot_trajectory
from agentwatch.traces.schema import RawExecutionRecord, GroundTruthLabelRecord


PILOT_TASKS = [
    {"user": "user_task_0", "injection": "injection_task_0"},
    {"user": "user_task_1", "injection": "injection_task_1"},
    {"user": "user_task_2", "injection": "injection_task_2"},
    {"user": "user_task_3", "injection": "injection_task_3"},
    {"user": "user_task_4", "injection": "injection_task_4"},
]


def run_phase1_pilot(output_base_dir: str = "data/pilot_runs") -> Dict[str, Any]:
    """Execute the Phase 1 pilot evaluation suite."""
    base_path = Path(output_base_dir)
    raw_dir = base_path / "raw"
    labels_dir = base_path / "labels"
    manifests_dir = base_path / "manifests"

    raw_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    creds = check_backend_credentials()
    print("=== AgentWatch Phase 1 Pilot Pre-Flight ===")
    print("Backends detected:")
    for k, v in creds.items():
        print(f"  {k}: {'[READY]' if v else '[NOT AVAILABLE]'}")

    if not creds.get("LOCAL_OLLAMA") and not any([creds.get("OPENAI_API_KEY"), creds.get("ANTHROPIC_API_KEY"), creds.get("GEMINI_API_KEY")]):
        print("\n[DIAGNOSTIC BLOCKER]: No model backend is available.")
        return {
            "status": "BLOCKED_BY_BACKEND",
            "message": "Neither local Ollama nor cloud API keys are available.",
            "completed_runs": 0,
            "manifest_file": None,
        }

    # Prioritize zero-cost local Ollama inference
    if creds.get("LOCAL_OLLAMA"):
        import openai
        from agentdojo.agent_pipeline.llms.openai_llm import OpenAILLM
        model_name = "qwen2.5:3b"
        client = openai.OpenAI(base_url="http://127.0.0.1:11434/v1", api_key="ollama")
        llm = OpenAILLM(client, model_name)
        backend_type = "local_ollama"
    else:
        from agentdojo.agent_pipeline.llms.openai_llm import OpenAILLM
        model_name = "gpt-4o-mini-2024-07-18"
        llm = OpenAILLM(model_name)
        backend_type = "cloud_openai"

    manifest = {
        "pilot_id": f"phase1-pilot-{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "benchmark_version": "v1",
        "suite_name": "workspace",
        "attack_name": "important_instructions",
        "model_name": model_name,
        "runs": [],
    }

    print(f"\nStarting Pilot Executions on {model_name}...")
    # Execute 5 benign runs followed by 5 attacked runs
    for idx, pair in enumerate(PILOT_TASKS):
        u_id = pair["user"]
        i_id = pair["injection"]

        # 1. Benign Run
        benign_run_id = f"run-benign-{u_id}-{uuid.uuid4().hex[:6]}"
        print(f"[{len(manifest['runs'])+1}/10] Running Benign: {u_id}...")
        raw_b, lbl_b, gp_count_b = run_single_pilot_trajectory(
            suite_name="workspace",
            benchmark_version="v1",
            user_task_id=u_id,
            injection_task_id=None,
            attack_name=None,
            model_name=model_name,
            run_id=benign_run_id,
            llm_element=llm,
        )

        with open(raw_dir / f"{benign_run_id}.json", "w", encoding="utf-8") as f:
            f.write(raw_b.model_dump_json(indent=2))
        with open(labels_dir / f"{benign_run_id}.json", "w", encoding="utf-8") as f:
            f.write(lbl_b.model_dump_json(indent=2))

        manifest["runs"].append({
            "run_id": benign_run_id,
            "type": "benign",
            "user_task_id": u_id,
            "injection_task_id": None,
            "utility_success": lbl_b.utility_success,
            "security_success": None,
            "gate_points": gp_count_b,
        })

        # 2. Attacked Run
        attack_run_id = f"run-attack-{u_id}-{i_id}-{uuid.uuid4().hex[:6]}"
        print(f"[{len(manifest['runs'])+1}/10] Running Attacked: {u_id} + {i_id}...")
        raw_a, lbl_a, gp_count_a = run_single_pilot_trajectory(
            suite_name="workspace",
            benchmark_version="v1",
            user_task_id=u_id,
            injection_task_id=i_id,
            attack_name="important_instructions",
            model_name=model_name,
            run_id=attack_run_id,
            llm_element=llm,
        )

        with open(raw_dir / f"{attack_run_id}.json", "w", encoding="utf-8") as f:
            f.write(raw_a.model_dump_json(indent=2))
        with open(labels_dir / f"{attack_run_id}.json", "w", encoding="utf-8") as f:
            f.write(lbl_a.model_dump_json(indent=2))

        manifest["runs"].append({
            "run_id": attack_run_id,
            "type": "attacked",
            "user_task_id": u_id,
            "injection_task_id": i_id,
            "utility_success": lbl_a.utility_success,
            "security_success": lbl_a.security_success,
            "gate_points": gp_count_a,
            "exposure_detected": lbl_a.exposure_detected,
            "first_harmful_step": lbl_a.first_harmful_step,
        })

    manifest_file = manifests_dir / f"{manifest['pilot_id']}.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nPilot Completed Successfully. Manifest saved to {manifest_file}")
    return {
        "status": "COMPLETED",
        "completed_runs": len(manifest["runs"]),
        "manifest_file": str(manifest_file),
    }


if __name__ == "__main__":
    result = run_phase1_pilot()
    print(json.dumps(result, indent=2))
