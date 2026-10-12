import json
import glob
from pathlib import Path

files = sorted(glob.glob("data/pilot_runs/raw/*.json"))
print(f"Total raw files: {len(files)}")
for p in files:
    with open(p, "r", encoding="utf-8") as f:
        d = json.load(f)
    run_id = d.get("run_id")
    u_id = d.get("user_task_id")
    inj_id = d.get("injection_task_id")
    steps = d.get("steps", [])
    gp_count = d.get("metadata", {}).get("gate_point_count")
    
    # Load label
    lbl_path = Path("data/pilot_runs/labels") / f"{run_id}.json"
    lbl_data = {}
    if lbl_path.exists():
        with open(lbl_path, "r", encoding="utf-8") as lf:
            lbl_data = json.load(lf)

    total_tc = sum(len(s.get("tool_calls", [])) for s in steps)
    total_tr = sum(len(s.get("tool_results", [])) for s in steps)
    
    print(f"\nRun: {run_id}")
    print(f"  User: {u_id} | Inj: {inj_id} | Steps: {len(steps)} | GatePoints: {gp_count}")
    print(f"  ToolCalls: {total_tc} | ToolResults: {total_tr}")
    print(f"  Utility: {lbl_data.get('utility_success')} | Security: {lbl_data.get('security_success')} | Exposed: {lbl_data.get('exposure_detected')}")
    for idx, s in enumerate(steps):
        tc_names = [tc.get("tool_name") for tc in s.get("tool_calls", [])]
        tr_call_ids = [tr.get("call_id") for tr in s.get("tool_results", [])]
        content_preview = (s.get("content") or "").replace("\n", " ")[:60]
        print(f"    Step {s.get('step_index')}: role={s.get('role')} | content='{content_preview}' | tcs={tc_names} | trs={tr_call_ids}")
