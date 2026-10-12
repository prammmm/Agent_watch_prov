"""Phase 4A: Post-Exposure Coverage Audit & Authentic Positive-Case Discovery Collection Harness.

Executes a bounded, reproducible, zero-cost collection study testing:
1. Untested native attack strategies (tool_knowledge, direct) on validated user_task_0 + injection_task_0.
2. Multi-tool candidate user_task_6 with matched benign control and multi-strategy attacks.
3. Matched benign controls for each user task.

Guarantees:
- Zero cost ($0.00; local Ollama with qwen2.5:3b).
- Zero synthetic data (all genuine AgentDojo executions).
- Resumable: skips runs that already exist on disk.
- Decoupled ground truth labels and SHA-256 integrity verification.
"""

import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional
import openai

from agentdojo.agent_pipeline.llms.openai_llm import OpenAILLM
from agentwatch.benchmark.pilot_harness import run_single_pilot_trajectory
from agentwatch.traces.integrity import verify_run_integrity

PLANNED_EXPERIMENTS = [
    # 1. Untested attack strategies on user_task_0 + injection_task_0
    {"user": "user_task_0", "injection": None, "attack": None, "desc": "Benign control for user_task_0"},
    {"user": "user_task_0", "injection": "injection_task_0", "attack": "tool_knowledge", "desc": "user_task_0 with tool_knowledge attack"},
    {"user": "user_task_0", "injection": "injection_task_0", "attack": "direct", "desc": "user_task_0 with direct attack"},
    # 2. Multi-tool candidate user_task_6 with matched benign control and multi-strategy attacks
    {"user": "user_task_6", "injection": None, "attack": None, "desc": "Benign control for multi-tool user_task_6"},
    {"user": "user_task_6", "injection": "injection_task_0", "attack": "important_instructions", "desc": "user_task_6 with important_instructions attack"},
    {"user": "user_task_6", "injection": "injection_task_0", "attack": "injecagent", "desc": "user_task_6 with injecagent attack"},
    {"user": "user_task_6", "injection": "injection_task_0", "attack": "system_message", "desc": "user_task_6 with system_message attack"},
]


def run_phase4a_collection(output_base_dir: str = "data/phase4a_collection"):
    base_path = Path(output_base_dir)
    raw_dir = base_path / "raw"
    labels_dir = base_path / "labels"
    manifests_dir = base_path / "manifests"

    raw_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    client = openai.OpenAI(base_url="http://127.0.0.1:11434/v1", api_key="ollama")
    llm = OpenAILLM(client, "qwen2.5:3b")

    study_id = f"phase4a-study-{uuid.uuid4().hex[:8]}"
    manifest = {
        "study_id": study_id,
        "model_name": "qwen2.5:3b",
        "benchmark_version": "v1",
        "suite_name": "workspace",
        "runs": [],
    }

    print(f"=== Starting Phase 4A Collection Study [{study_id}] ===")
    print(f"Total planned runs: {len(PLANNED_EXPERIMENTS)}")

    for idx, exp in enumerate(PLANNED_EXPERIMENTS, 1):
        u_id = exp["user"]
        i_id = exp["injection"]
        att = exp["attack"]
        
        # Deterministic run ID prefix for resumability
        if i_id is None:
            run_prefix = f"p4a-benign-{u_id}"
        else:
            run_prefix = f"p4a-attack-{u_id}-{i_id}-{att}"

        # Check if already completed
        existing_raw = list(raw_dir.glob(f"{run_prefix}-*.json"))
        if existing_raw:
            print(f"[{idx}/{len(PLANNED_EXPERIMENTS)}] Skipping existing run: {existing_raw[0].name}")
            continue

        run_id = f"{run_prefix}-{uuid.uuid4().hex[:6]}"
        print(f"\n[{idx}/{len(PLANNED_EXPERIMENTS)}] Executing: {exp['desc']} (run_id: {run_id})...")

        raw, lbl, gp_count = run_single_pilot_trajectory(
            suite_name="workspace",
            benchmark_version="v1",
            user_task_id=u_id,
            injection_task_id=i_id,
            attack_name=att,
            model_name="qwen2.5:3b",
            run_id=run_id,
            llm_element=llm,
        )

        raw_file = raw_dir / f"{run_id}.json"
        lbl_file = labels_dir / f"{run_id}.json"

        with open(raw_file, "w", encoding="utf-8") as f:
            f.write(raw.model_dump_json(indent=2))
        with open(lbl_file, "w", encoding="utf-8") as f:
            f.write(lbl.model_dump_json(indent=2))

        # Integrity verification
        integ = verify_run_integrity(raw_file, lbl_file)

        run_summary = {
            "run_id": run_id,
            "user_task_id": u_id,
            "injection_task_id": i_id,
            "attack_name": att,
            "utility_success": lbl.utility_success,
            "security_success": lbl.security_success,
            "exposure_detected": lbl.exposure_detected,
            "harmful_action_proposed": lbl.harmful_action_proposed,
            "harmful_action_executed": lbl.harmful_action_executed,
            "gate_points": gp_count,
            "steps": len(raw.steps),
            "integrity_valid": integ.is_valid,
        }
        manifest["runs"].append(run_summary)

        print(f"  Completed: utility={lbl.utility_success}, security_breached={lbl.security_success}, exposed={lbl.exposure_detected}, proposed_harm={lbl.harmful_action_proposed}, gate_points={gp_count}")

    manifest_file = manifests_dir / f"{study_id}.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nPhase 4A collection complete. Manifest saved to: {manifest_file}")
    return manifest


if __name__ == "__main__":
    run_phase4a_collection()
