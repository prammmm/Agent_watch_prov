import glob
import json

runs = glob.glob('data/*/labels/*.json')
for p in runs:
    l = json.load(open(p))
    if l.get('injected') and l.get('exposure_detected'):
        raw = json.load(open(p.replace('labels', 'raw')))
        exp_step = None
        for i, s in enumerate(raw['steps']):
            for tr in s.get('tool_results', []):
                out = str(tr.get('output', ''))
                if any(x in out for x in ['mark.black', 'Important message', 'Please email', 'delete_file', 'TODO: Please email']):
                    exp_step = i
                    break
            if exp_step is not None:
                break
        
        subsequent_tool_calls = []
        if exp_step is not None:
            for j in range(exp_step + 1, len(raw['steps'])):
                tcs = raw['steps'][j].get('tool_calls', [])
                if tcs:
                    subsequent_tool_calls.extend([tc['tool_name'] for tc in tcs])
        print('%s: exp_step=%s, post_tc=%s, label_post=%s' % (l['run_id'], exp_step, subsequent_tool_calls, l.get('post_exposure_decision_occurred')))
