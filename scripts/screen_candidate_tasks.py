"""Screen Candidate Multi-Tool Tasks under Benign Execution.

Tests candidate tasks from workspace v1 with local qwen2.5:3b to determine:
1. Whether the local model emits valid tool calls
2. Whether multiple tool interactions occur
3. Whether benign utility succeeds
"""

import openai
from agentdojo.agent_pipeline.llms.openai_llm import OpenAILLM
from agentwatch.benchmark.pilot_harness import run_single_pilot_trajectory

CANDIDATES = [
    "user_task_6",
    "user_task_7",
    "user_task_8",
    "user_task_9",
    "user_task_35",
]

def screen_candidates():
    client = openai.OpenAI(base_url="http://127.0.0.1:11434/v1", api_key="ollama")
    llm = OpenAILLM(client, "qwen2.5:3b")

    print("=== Screening Candidate Tasks (Benign Mode) ===")
    results = []
    for u_id in CANDIDATES:
        print(f"\nScreening {u_id}...")
        raw, lbl, gp_count = run_single_pilot_trajectory(
            suite_name="workspace",
            benchmark_version="v1",
            user_task_id=u_id,
            injection_task_id=None,
            attack_name=None,
            model_name="qwen2.5:3b",
            run_id=f"screen-{u_id}",
            llm_element=llm,
        )
        tools = [tc.tool_name for s in raw.steps for tc in s.tool_calls]
        res = {
            "user_task_id": u_id,
            "utility_success": lbl.utility_success,
            "gate_points": gp_count,
            "tools_called": tools,
            "steps": len(raw.steps),
        }
        results.append(res)
        print(f"  Result: utility={lbl.utility_success}, gate_points={gp_count}, tools={tools}")

    return results

if __name__ == "__main__":
    screen_candidates()
