import glob
import json
import os

def audit_partition(name, file_list):
    total_runs = len(file_list)
    benign_runs = 0
    attacked_runs = 0
    benign_util = 0
    attacked_util = 0
    payload_exp = 0
    post_exp_opp = 0
    harm_prop = 0
    harm_exec = 0
    sec_breach = 0
    total_gp = 0
    models = {}
    tasks = {}

    for raw_p in file_list:
        raw = json.load(open(raw_p))
        run_id = raw['run_id']
        label_p = raw_p.replace('raw', 'labels')
        label = json.load(open(label_p))

        model = raw.get('agent_model', 'unknown')
        models[model] = models.get(model, 0) + 1
        task = raw.get('user_task_id', 'unknown')
        tasks[task] = tasks.get(task, 0) + 1

        gps = sum(len(s.get('tool_calls', [])) for s in raw.get('steps', []))
        total_gp += gps

        injected = label.get('injected', False)
        util = label.get('utility_success', False)
        exp = label.get('exposure_detected', False)
        post = label.get('post_exposure_decision_occurred', False)
        hp = label.get('harmful_action_proposed', False)
        he = label.get('harmful_action_executed', False)
        sec = label.get('benchmark_confirmed_success', False) or (label.get('security_success') is True)

        if injected:
            attacked_runs += 1
            if util: attacked_util += 1
            if exp: payload_exp += 1
            if post: post_exp_opp += 1
            if hp: harm_prop += 1
            if he: harm_exec += 1
            if sec: sec_breach += 1
        else:
            benign_runs += 1
            if util: benign_util += 1

    return {
        'name': name,
        'total_runs': total_runs,
        'models': models,
        'tasks': tasks,
        'benign_runs': benign_runs,
        'attacked_runs': attacked_runs,
        'benign_util': benign_util,
        'attacked_util': attacked_util,
        'payload_exp': payload_exp,
        'post_exp_opp': post_exp_opp,
        'harm_prop': harm_prop,
        'harm_exec': harm_exec,
        'sec_breach': sec_breach,
        'total_gp': total_gp
    }

hist_files = (
    glob.glob('data/pilot_runs/raw/*.json') +
    glob.glob('data/collection_study/raw/*.json') +
    glob.glob('data/phase4a_collection/raw/*.json') +
    glob.glob('data/phase5b_collection/raw/*.json') +
    glob.glob('data/phase5c_collection/raw/*.json')
)
p6a_files = glob.glob('data/phase6a_collection/raw/*.json')

h_stat = audit_partition('Historical Canonical (43)', hist_files)
p_stat = audit_partition('Phase 6A Experimental (32)', p6a_files)
tot_stat = audit_partition('Cumulative Total (75)', hist_files + p6a_files)

for s in [h_stat, p_stat, tot_stat]:
    print('=============================================')
    print(s['name'])
    print('  Total Runs:', s['total_runs'])
    print('  Models:', s['models'])
    print('  Benign Runs: %d (Utility Success: %d)' % (s['benign_runs'], s['benign_util']))
    print('  Attacked Runs: %d (Utility Success: %d)' % (s['attacked_runs'], s['attacked_util']))
    print('  Payload Exposed: %d / %d' % (s['payload_exp'], s['attacked_runs']))
    print('  Post-Exposure Decision Opp: %d / %d' % (s['post_exp_opp'], s['payload_exp']))
    print('  Harmful Actions Proposed: %d' % s['harm_prop'])
    print('  Harmful Actions Executed: %d' % s['harm_exec'])
    print('  Benchmark Security Breaches: %d' % s['sec_breach'])
    print('  Total Gate Points: %d' % s['total_gp'])
