"""Screen user_task_12 benign execution with local qwen2.5:3b."""

import openai
from agentdojo.agent_pipeline.llms.openai_llm import OpenAILLM
from agentwatch.benchmark.pilot_harness import run_single_pilot_trajectory

client = openai.OpenAI(base_url="http://127.0.0.1:11434/v1", api_key="ollama")
llm = OpenAILLM(client, "qwen2.5:3b")

print("--- Testing user_task_12 (Benign) ---")
raw, lbl, gp_count = run_single_pilot_trajectory(
    suite_name="workspace",
    benchmark_version="v1",
    user_task_id="user_task_12",
    injection_task_id=None,
    attack_name=None,
    model_name="qwen2.5:3b",
    run_id="screen-user_task_12",
    llm_element=llm,
)

tools = [tc.tool_name for s in raw.steps for tc in s.tool_calls]
print(f"Result: utility={lbl.utility_success}, gate_points={gp_count}")
print(f"Tools called: {tools}")
for s in raw.steps:
    if s.tool_calls:
        for tc in s.tool_calls:
            print(f"  Step {s.step_index}: {tc.tool_name} with {tc.arguments}")
