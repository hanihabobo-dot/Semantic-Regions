import json
data = json.load(open('/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels/tools/swarm_2026-08-22/D_primary_sweep_results.json'))

print("=== ALL incidents where reblocked shadow == oracle_shadow (target's true hiding place) ===")
n=0
for r in data:
    if 'error' in r:
        continue
    for inc in r.get('incidents', []):
        if inc['target_true_hiding_place']:
            n+=1
            print(f"{n}. run={r['run_id']} regime={r['regime']} seed={r['config'].get('seed')} "
                  f"placed={inc['placed_obj']}@{inc['placed_boxel']} line={inc['line']} "
                  f"reblocks={inc['reblocked_shadows']} ended={inc['episode_ended_by_this']} "
                  f"outcome={inc['run_final_outcome'][:70]}")

print()
print("=== Specifically the orange@free_005 -> shadow_of_red_object signature (seed 0) ===")
n2 = 0
for r in data:
    if 'error' in r:
        continue
    if r['config'].get('seed') != '0':
        continue
    for inc in r.get('incidents', []):
        if inc['placed_obj'] == 'orange_object' and inc['placed_boxel'] == 'free_005' and 'shadow_of_red_object' in inc['reblocked_shadows']:
            n2 += 1
            print(f"{n2}. run={r['run_id']} run_time={r['run_time_hhmmss']} regime={r['regime']} "
                  f"line={inc['line']} ended={inc['episode_ended_by_this']} outcome={inc['run_final_outcome'][:70]}")

print()
print(f"Total incidents (all seeds/goals) where reblock hit the oracle shadow: {n}")
print(f"Total orange@free_005->shadow_of_red_object signature occurrences: {n2}")

print()
print("=== all seed=0 holding runs total count (any regime), for denominator ===")
seed0 = [r for r in data if r.get('config',{}).get('seed')=='0' and r.get('config',{}).get('goal')=='holding' and 'error' not in r]
print("total seed=0 holding runs:", len(seed0))
