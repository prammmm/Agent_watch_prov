import json

with open("reports/candidate_task_inventory.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"{'User Task':<14} | {'GT Calls':<45} | {'Inj Candidates':<15} | {'Pairs with payload':<18}")
print("-" * 100)
for u in data["user_tasks"]:
    u_id = u["user_task_id"]
    gt_fns = [c.get("function") for c in u["ground_truth_calls"]]
    gt_str = ", ".join(gt_fns) if gt_fns else "None"
    inj_cand = len(u["injection_candidates"])
    valid_pairs = sum(1 for p in u["pairings"] if p["has_payload"])
    print(f"{u_id:<14} | {gt_str[:45]:<45} | {inj_cand:<15} | {valid_pairs:<18}")
