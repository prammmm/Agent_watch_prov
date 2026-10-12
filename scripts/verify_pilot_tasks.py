"""Verification script for AgentDojo v1 Workspace Pilot Task Pairs.

Validates that user_task_0 to 4 and injection_task_0 to 4 have complete
ground truth definitions, valid candidate injection points, and generated payloads.
"""

from agentdojo.task_suite.load_suites import get_suite
from agentdojo.attacks.attack_registry import load_attack
from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline

def verify_pilot_pairs():
    suite = get_suite("v1", "workspace")
    pipe = AgentPipeline([])
    pipe.name = "gpt-4o-mini-2024-07-18"
    atk = load_attack("important_instructions", suite, pipe)
    env = suite.load_and_inject_default_environment({})

    print("--- Pilot Task Ground-Truth & Attack Verification ---")
    for i in range(5):
        u_id = f"user_task_{i}"
        i_id = f"injection_task_{i}"
        u_task = suite.get_user_task_by_id(u_id)
        i_task = suite.get_injection_task_by_id(i_id)

        u_calls = [c.function for c in u_task.ground_truth(env)]
        i_calls = [c.function for c in i_task.ground_truth(env)]

        candidates = atk.get_injection_candidates(u_task)
        payloads = atk.attack(u_task, i_task)

        print(f"[{i+1}/5] Pair: {u_id} <-> {i_id}")
        print(f"  User Prompt: {u_task.PROMPT}")
        print(f"  User Ground Truth Calls: {u_calls}")
        print(f"  Injection Ground Truth Calls: {i_calls}")
        print(f"  Candidate Injection Keys: {candidates}")
        print(f"  Payload Count: {len(payloads)}")
        print(f"  Payload Key Sample: {list(payloads.keys())[0]}")
        print()

if __name__ == "__main__":
    verify_pilot_pairs()
