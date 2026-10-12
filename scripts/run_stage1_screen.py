"""Stage 1: Benign Capability Screen Script.

Tests a diverse subset of valid AgentDojo v1 workspace user tasks
under benign conditions to measure utility success, tool-call validity,
and execution errors before attempting attack combinations.
"""

import uuid
import openai
from agentdojo.agent_pipeline.llms.openai_llm import OpenAILLM
from agentwatch.benchmark.pilot_harness import run_single_pilot_trajectory

BENIGN_CANDIDATE_TASKS = [
    "user_task_0",   # Single-step calendar search (previously passed)
    "user_task_1",   # Single-step day calendar count (previously passed)
    "user_task_5",   # Time calculation before lunch (single-day calendar query)
    "user_task_10",  # Appointments today query (single-day calendar query)
]


def run_stage1_screen():
    client = openai.OpenAI(base_url="http://127.0.0.1:11434/v1", api_key="ollama")
    llm = OpenAILLM(client, "qwen2.5:3b")

    print("=== Stage 1: Benign Capability Screen ===")
    results = []
    for u_id in BENIGN_CANDIDATE_TASKS:
        run_id = f"screen-benign-{u_id}-{uuid.uuid4().hex[:6]}"
        print(f"Executing benign screen on {u_id}...")
        raw, lbl, gp_count = run_single_pilot_trajectory(
            suite_name="workspace",
            benchmark_version="v1",
            user_task_id=u_id,
            injection_task_id=None,
            attack_name=None,
            model_name="qwen2.5:3b",
            run_id=run_id,
            llm_element=llm,
        )
        results.append({
            "user_task_id": u_id,
            "utility_success": lbl.utility_success,
            "gate_points": gp_count,
            "steps": len(raw.steps),
        })
        print(f"  Result: utility={lbl.utility_success}, gate_points={gp_count}, steps={len(raw.steps)}")

    print("\nSummary of Stage 1 Screen:")
    for r in results:
        print(f"  {r['user_task_id']}: Utility={'PASS' if r['utility_success'] else 'FAIL'}, GatePoints={r['gate_points']}")


if __name__ == "__main__":
    run_stage1_screen()
