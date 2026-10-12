import json

with open("reports/candidate_task_inventory.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for u in data["user_tasks"]:
    if u["user_task_id"] in ["user_task_4", "user_task_7", "user_task_8", "user_task_12", "user_task_35"]:
        print("=" * 80)
        print(f"Task: {u['user_task_id']}")
        print(f"Prompt: {u['prompt']}")
        print("GT calls:")
        for c in u["ground_truth_calls"]:
            print(f"  {c['function']}({c['args']})")
        print(f"Injection candidates: {u['injection_candidates']}")
