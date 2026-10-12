import json
from agentdojo.benchmark import get_suite
from agentdojo.agent_pipeline import AgentPipeline
from agentdojo.attacks import load_attack

suite = get_suite("v1", "workspace")
dummy_pipe = AgentPipeline([])
dummy_pipe.name = "local-qwen2.5:3b"
attack = load_attack("important_instructions", suite, dummy_pipe)

runs = [
    ("run-attack-user_task_0-injection_task_0-79f6f2", "user_task_0", "injection_task_0"),
    ("run-attack-user_task_1-injection_task_1-c5d7f1", "user_task_1", "injection_task_1"),
    ("run-attack-user_task_2-injection_task_2-c07980", "user_task_2", "injection_task_2"),
    ("run-attack-user_task_3-injection_task_3-c8fccf", "user_task_3", "injection_task_3"),
    ("run-attack-user_task_4-injection_task_4-2b9398", "user_task_4", "injection_task_4"),
]

for r_id, u_id, i_id in runs:
    u_task = suite.get_user_task_by_id(u_id)
    i_task = suite.get_injection_task_by_id(i_id)
    injections = attack.attack(u_task, i_task)
    with open(f"data/pilot_runs/raw/{r_id}.json", "r", encoding="utf-8") as f:
        trace = json.load(f)
    print(f"\n=== Run {r_id} ===")
    exposed = False
    for s in trace.get("steps", []):
        if s.get("role") == "tool":
            content = s.get("content") or ""
            for k, payload in injections.items():
                lines = [l.strip() for l in payload.splitlines() if len(l.strip()) > 15]
                for l in lines[:3]:
                    if l in content:
                        print(f"  [EXPOSED] Step {s.get('step_index')}: matched key '{k}' line '{l[:40]}'")
                        exposed = True
                        break
    if not exposed:
        print("  [NOT EXPOSED] Agent did not observe injection payload in any tool observation")
