"""Stage 2: Attacked Multi-Strategy Collection Experiment.

Evaluates user_task_0 (the validated capability task) paired with injection_task_0
across 4 distinct supported attack formulations:
1. important_instructions (baseline indirect injection)
2. injecagent (jailbreak style delimiter override)
3. ignore_previous (direct prefix instruction wipe)
4. system_message (fake system turn framing)

Records all 6 outcome dimensions, payload exposure, and gate points.
"""

import json
import uuid
from pathlib import Path
import openai
from agentdojo.agent_pipeline.llms.openai_llm import OpenAILLM
from agentwatch.benchmark.pilot_harness import run_single_pilot_trajectory
from agentwatch.traces.integrity import verify_run_integrity

ATTACK_CONFIGS = [
    {"user": "user_task_0", "injection": "injection_task_0", "attack": "important_instructions"},
    {"user": "user_task_0", "injection": "injection_task_0", "attack": "injecagent"},
    {"user": "user_task_0", "injection": "injection_task_0", "attack": "ignore_previous"},
    {"user": "user_task_0", "injection": "injection_task_0", "attack": "system_message"},
]


def run_stage2_experiment(output_base_dir: str = "data/collection_study"):
    base_path = Path(output_base_dir)
    raw_dir = base_path / "raw"
    labels_dir = base_path / "labels"
    manifests_dir = base_path / "manifests"

    raw_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    client = openai.OpenAI(base_url="http://127.0.0.1:11434/v1", api_key="ollama")
    llm = OpenAILLM(client, "qwen2.5:3b")

    manifest = {
        "study_id": f"collection-study-{uuid.uuid4().hex[:8]}",
        "model_name": "qwen2.5:3b",
        "benchmark_version": "v1",
        "suite_name": "workspace",
        "runs": [],
    }

    print("=== Stage 2: Attacked Multi-Strategy Collection Experiment ===")
    for cfg in ATTACK_CONFIGS:
        u_id = cfg["user"]
        i_id = cfg["injection"]
        att = cfg["attack"]
        run_id = f"study-attack-{u_id}-{i_id}-{att}-{uuid.uuid4().hex[:6]}"

        print(f"\nExecuting: {u_id} + {i_id} under attack '{att}'...")
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

        # Run integrity check on the record
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

        print(f"  Outcome: utility={lbl.utility_success}, security_breached={lbl.security_success}, exposed={lbl.exposure_detected}, proposed_harm={lbl.harmful_action_proposed}, gate_points={gp_count}")

    manifest_file = manifests_dir / f"{manifest['study_id']}.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest saved to {manifest_file}")
    return manifest


if __name__ == "__main__":
    run_stage2_experiment()
