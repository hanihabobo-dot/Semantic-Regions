import json
from collections import Counter

data = json.load(open('/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels/tools/swarm_2026-08-22/D_secondary_sweep_results.json'))
c = Counter(r.get('config', {}).get('goal') for r in data if 'error' not in r)
print('secondary goal breakdown:', c)

# incidents by goal, and self-shadow vs cross-shadow split
self_shadow = 0
cross_shadow = 0
by_goal_incidents = Counter()
by_goal_places = Counter()
for r in data:
    if 'error' in r:
        continue
    g = r.get('config', {}).get('goal')
    by_goal_places[g] += r.get('total_place_actions', 0)
    for inc in r.get('incidents', []):
        by_goal_incidents[g] += 1
        obj = inc['placed_obj']
        for sid in inc['reblocked_shadows']:
            if obj in sid:
                self_shadow += 1
            else:
                cross_shadow += 1
print('self-shadow-name reblocks:', self_shadow, ' cross-object reblocks:', cross_shadow)
print('incidents by goal:', dict(by_goal_incidents))
print('places by goal:', dict(by_goal_places))

print()
# same breakdown for primary corpus for comparison
data2 = json.load(open('/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels/tools/swarm_2026-08-22/D_primary_sweep_results.json'))
self_shadow2 = 0
cross_shadow2 = 0
for r in data2:
    if 'error' in r:
        continue
    for inc in r.get('incidents', []):
        obj = inc['placed_obj']
        for sid in inc['reblocked_shadows']:
            if obj in sid:
                self_shadow2 += 1
            else:
                cross_shadow2 += 1
print('PRIMARY self-shadow-name reblocks:', self_shadow2, ' cross-object reblocks:', cross_shadow2)
