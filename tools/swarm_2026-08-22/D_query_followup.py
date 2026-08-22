import json
data = json.load(open('/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels/tools/swarm_2026-08-22/D_primary_sweep_results.json'))
seed0_holding = [r for r in data if r.get('config', {}).get('seed') == '0' and r.get('config', {}).get('goal') == 'holding']
print('seed=0 holding runs total:', len(seed0_holding))
for r in seed0_holding:
    print(' ', r['run_id'], 'incidents=', len(r.get('incidents', [])), 'outcome=', r.get('final_outcome'), 'places=', r.get('total_place_actions'))
print()
regd = [r for r in data if r.get('regime') == 'D(current,0.15-gate)']
print('regime D strict runs:', len(regd))
tot_places = sum(r.get('total_place_actions', 0) for r in regd)
tot_inc = sum(len(r.get('incidents', [])) for r in regd)
print('  total place actions:', tot_places, 'total incidents:', tot_inc)
for r in regd:
    print('  ', r['run_id'], r.get('config', {}).get('goal'), r.get('config', {}).get('seed'), 'places=', r.get('total_place_actions'), 'incidents=', len(r.get('incidents', [])), 'outcome=', r.get('final_outcome'))
print()
print('total primary place actions (all 154 runs):', sum(r.get('total_place_actions', 0) for r in data if 'error' not in r))
print('goal breakdown:')
from collections import Counter
c = Counter(r.get('config', {}).get('goal') for r in data if 'error' not in r)
print(c)
