"""Build Verified Candidate Task and Attack Inventory for Phase 5B.

Systematically inspects AgentDojo v1 Workspace user tasks and injection tasks.
Verifies:
1. Ground truth definitions for user tasks and injection tasks.
2. Injection candidates and payload delivery mechanisms.
3. Harmful ground-truth function calls.
4. Feasibility of multi-step tool sequences and post-exposure opportunities.
5. Saves machine-readable inventory to reports/candidate_task_inventory.json.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from agentdojo.task_suite.load_suites import get_suite
from agentdojo.attacks.attack_registry import load_attack
from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline
from agentdojo.functions_runtime import FunctionCall


def inspect_all_injection_tasks(suite) -> Dict[str, Any]:
    env = suite.load_and_inject_default_environment({})
    inj_info = {}
    for inj_id, inj_task in suite.injection_tasks.items():
        try:
            gt_calls = inj_task.ground_truth(env)
            gt_repr = [
                {"function": c.function, "args": c.args}
                for c in gt_calls
            ]
        except Exception as e:
            gt_repr = [{"error": str(e)}]

        inj_info[inj_id] = {
            "injection_task_id": inj_id,
            "goal": getattr(inj_task, "GOAL", getattr(inj_task, "PROMPT", str(inj_task))),
            "ground_truth_calls": gt_repr,
        }
    return inj_info


def inspect_candidate_user_tasks(suite, candidate_user_ids: List[str]) -> List[Dict[str, Any]]:
    pipe = AgentPipeline([])
    pipe.name = "local-qwen2.5:3b"
    atk = load_attack("important_instructions", suite, pipe)
    env = suite.load_and_inject_default_environment({})

    supported_attacks = [
        "important_instructions",
        "injecagent",
        "system_message",
        "ignore_previous",
        "tool_knowledge",
        "direct",
    ]

    inventory = []

    for u_id in candidate_user_ids:
        if u_id not in suite.user_tasks:
            continue
        u_task = suite.user_tasks[u_id]
        try:
            u_gt_calls = [
                {"function": c.function, "args": c.args}
                for c in u_task.ground_truth(env)
            ]
        except Exception as e:
            u_gt_calls = [{"error": str(e)}]

        # Injection candidates for this user task
        candidates = atk.get_injection_candidates(u_task)

        # For each injection task, check pairing validity
        pairing_details = []
        for i_id, i_task in suite.injection_tasks.items():
            try:
                payloads = atk.attack(u_task, i_task)
                has_payload = len(payloads) > 0
                payload_keys = list(payloads.keys())
            except Exception as e:
                has_payload = False
                payload_keys = []

            try:
                i_gt_calls = [
                    {"function": c.function, "args": c.args}
                    for c in i_task.ground_truth(env)
                ]
            except Exception as e:
                i_gt_calls = [{"error": str(e)}]

            # Determine whether post-exposure decision point is theoretically possible
            # That requires user task to make a read tool call that retrieves the payload,
            # followed by either the user task's second tool call OR the attacker's tool call.
            post_exposure_possible = has_payload and len(u_gt_calls) >= 2

            pairing_details.append({
                "injection_task_id": i_id,
                "has_payload": has_payload,
                "payload_keys": payload_keys,
                "harmful_ground_truth_calls": i_gt_calls,
                "post_exposure_theoretically_possible": post_exposure_possible,
            })

        inventory.append({
            "user_task_id": u_id,
            "prompt": getattr(u_task, "PROMPT", ""),
            "ground_truth_calls": u_gt_calls,
            "injection_candidates": candidates,
            "supported_attack_strategies": supported_attacks,
            "pairings": pairing_details,
        })

    return inventory


def main():
    suite = get_suite("v1", "workspace")
    inj_info = inspect_all_injection_tasks(suite)
    print("--- Injection Tasks in workspace v1 ---")
    for k, v in inj_info.items():
        print(f"[{k}] Goal: {v['goal']}")
        print(f"  GT Calls: {v['ground_truth_calls']}")

    candidate_user_ids = [
        "user_task_0",
        "user_task_1",
        "user_task_2",
        "user_task_3",
        "user_task_4",
        "user_task_5",
        "user_task_6",
        "user_task_7",
        "user_task_8",
        "user_task_9",
        "user_task_10",
        "user_task_11",
        "user_task_12",
        "user_task_35",
    ]

    user_inventory = inspect_candidate_user_tasks(suite, candidate_user_ids)

    out_file = Path("reports/candidate_task_inventory.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    full_data = {
        "injection_tasks": inj_info,
        "user_tasks": user_inventory,
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(full_data, f, indent=2)

    print(f"\nInventory saved to {out_file}")


if __name__ == "__main__":
    main()
