"""Test candidate tasks for tool sequence and payload exposure."""

from agentdojo.task_suite.load_suites import get_suite
from agentdojo.attacks.attack_registry import load_attack
from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline
from agentdojo.functions_runtime import FunctionsRuntime

suite = get_suite("v1", "workspace")
pipe = AgentPipeline([])
pipe.name = "local-qwen2.5:3b"

# Let's inspect user_task_7 and user_task_8 environment and tools
for u_id in ["user_task_7", "user_task_8"]:
    u_task = suite.get_user_task_by_id(u_id)
    i_task = suite.get_injection_task_by_id("injection_task_0")
    atk = load_attack("injecagent", suite, pipe)
    injections = atk.attack(u_task, i_task)
    print(f"\n--- {u_id} ---")
    print(f"Prompt: {u_task.PROMPT}")
    print(f"Injections: {list(injections.keys())}")
    
    env = suite.load_and_inject_default_environment(injections)
    env = u_task.init_environment(env)
    
    # Check if the injection is present in the environment
    # Let's inspect the calendar events in env
    calendar = getattr(env, "calendar", None)
    if calendar:
        events = getattr(calendar, "events", {})
        print(f"Calendar events count: {len(events)}")
        for eid, ev in events.items():
            desc = getattr(ev, "description", "")
            title = getattr(ev, "title", "")
            for inj_key, inj_val in injections.items():
                if inj_val in desc:
                    print(f"  MATCH in event {eid} ('{title}'): contains injection {inj_key}!")
