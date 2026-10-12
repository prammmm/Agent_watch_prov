import json
from agentdojo.task_suite.load_suites import get_suite
from agentdojo.attacks.attack_registry import load_attack
from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline

suite = get_suite("v1", "workspace")
pipe = AgentPipeline([])
pipe.name = "qwen2.5:3b"

attacks = ["important_instructions", "injecagent", "ignore_previous", "system_message", "tool_knowledge", "direct"]
tasks_to_check = ["user_task_4", "user_task_7", "user_task_8", "user_task_12", "user_task_35"]
inj_tasks = ["injection_task_0", "injection_task_1", "injection_task_2"]

print("=== CHECKING INJECTIONS & CANDIDATES ===")
for u_id in tasks_to_check:
    u_task = suite.get_user_task_by_id(u_id)
    print(f"\nUser Task: {u_id}")
    for a_name in ["important_instructions", "injecagent", "direct"]:
        try:
            atk = load_attack(a_name, suite, pipe)
            for i_id in ["injection_task_0", "injection_task_1"]:
                i_task = suite.get_injection_task_by_id(i_id)
                payloads = atk.attack(u_task, i_task)
                for k, v in payloads.items():
                    print(f"  [{a_name} + {i_id}] Key: {k} -> Payload snippet: {repr(v[:120])}")
        except Exception as e:
            print(f"  [{a_name}] Error: {e}")
