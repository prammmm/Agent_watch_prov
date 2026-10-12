"""Analyze Phase 6A Execution Results."""

import json
from pathlib import Path

sum_path = Path("D:/Agent_watch_prov/data/phase6a_collection/manifests/phase6a_execution_summary.json")
with open(sum_path, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total runs executed: {data['total_executed']}")
print(f"Total wall-clock time: {data['total_time_seconds']}s")

models = {}
task_stats = {}

for r in data["runs"]:
    m = r["agent_model"]
    u = r["user_task_id"]
    cond = r["condition"]
    rep = r["repetition"]

    if m not in models:
        models[m] = {
            "total": 0, "benign": 0, "attacked": 0,
            "benign_util": 0, "attacked_util": 0,
            "exposed": 0, "harmful_prop": 0, "harmful_exec": 0, "sec_succ": 0,
            "tasks": {}
        }
    models[m]["total"] += 1

    if u not in models[m]["tasks"]:
        models[m]["tasks"][u] = {"benign_util": 0, "attacked_util": 0, "exposed": 0, "harmful_prop": 0, "harmful_exec": 0, "sec_succ": 0}

    if cond == "benign":
        models[m]["benign"] += 1
        if r["utility_success"]:
            models[m]["benign_util"] += 1
            models[m]["tasks"][u]["benign_util"] += 1
    else:
        models[m]["attacked"] += 1
        if r["utility_success"]:
            models[m]["attacked_util"] += 1
            models[m]["tasks"][u]["attacked_util"] += 1
        if r["exposure_detected"]:
            models[m]["exposed"] += 1
            models[m]["tasks"][u]["exposed"] += 1
        if r["harmful_action_proposed"]:
            models[m]["harmful_prop"] += 1
            models[m]["tasks"][u]["harmful_prop"] += 1
        if r["harmful_action_executed"]:
            models[m]["harmful_exec"] += 1
            models[m]["tasks"][u]["harmful_exec"] += 1
        if r["security_success"]:
            models[m]["sec_succ"] += 1
            models[m]["tasks"][u]["sec_succ"] += 1

for m, s in models.items():
    print(f"\n=======================================================")
    print(f"Model: {m}")
    print(f"   Total Runs: {s['total']}")
    print(f"   Benign Utility Success: {s['benign_util']}/{s['benign']} ({s['benign_util']/s['benign']*100:.1f}%)")
    print(f"   Attacked Utility Success: {s['attacked_util']}/{s['attacked']} ({s['attacked_util']/s['attacked']*100:.1f}%)")
    print(f"   Attacked Payload Exposed: {s['exposed']}/{s['attacked']} ({s['exposed']/s['attacked']*100:.1f}%)")
    print(f"   Harmful Actions Proposed: {s['harmful_prop']}/{s['attacked']} ({s['harmful_prop']/s['attacked']*100:.1f}%)")
    print(f"   Harmful Actions Executed: {s['harmful_exec']}/{s['attacked']} ({s['harmful_exec']/s['attacked']*100:.1f}%)")
    print(f"   Benchmark Security Success (Breach): {s['sec_succ']}/{s['attacked']} ({s['sec_succ']/s['attacked']*100:.1f}%)")
    print(f"   Task Breakdown:")
    for t_id, t_data in s["tasks"].items():
        print(f"      {t_id}: benign_util={t_data['benign_util']}/2, attacked_util={t_data['attacked_util']}/2, exposed={t_data['exposed']}/2, harmful={t_data['harmful_prop']}/2, sec_succ={t_data['sec_succ']}/2")
