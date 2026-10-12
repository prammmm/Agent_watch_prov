"""Detailed verification of pilot task pairs and security outcomes."""

from agentdojo.task_suite.load_suites import get_suite
from agentdojo.attacks.attack_registry import load_attack
from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline

def print_pair_details():
    suite = get_suite("v1", "workspace")
    pipe = AgentPipeline([])
    pipe.name = "gpt-4o-mini-2024-07-18"
    atk = load_attack("important_instructions", suite, pipe)
    env = suite.load_and_inject_default_environment({})

    for i in range(5):
        u_id = f"user_task_{i}"
        i_id = f"injection_task_{i}"
        u_task = suite.get_user_task_by_id(u_id)
        i_task = suite.get_injection_task_by_id(i_id)
        candidates = atk.get_injection_candidates(u_task)
        payloads = atk.attack(u_task, i_task)

        print(f"============================================================")
        print(f"PAIR {i}: {u_id} <---> {i_id}")
        print(f"User Goal: {u_task.PROMPT}")
        print(f"Injection Goal: {i_task.GOAL}")
        print(f"Injection Candidates in Environment: {candidates}")
        print(f"Ground Truth Expected Calls (User): {[c.function for c in u_task.ground_truth(env)]}")
        print(f"Ground Truth Expected Calls (Attacker): {[c.function for c in i_task.ground_truth(env)]}")
        print(f"Sample Payload:")
        first_payload = list(payloads.values())[0]
        print(first_payload.strip())
        print()

if __name__ == "__main__":
    print_pair_details()
