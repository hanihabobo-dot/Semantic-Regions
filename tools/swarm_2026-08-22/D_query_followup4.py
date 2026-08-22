import json
data = json.load(open('/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels/tools/swarm_2026-08-22/D_primary_sweep_results.json'))

print("=== Regime D (0.15-gate, current code) incidents, full detail ===")
regd = [r for r in data if r.get('regime') == 'D(current,0.15-gate)']
for r in regd:
    for inc in r.get('incidents', []):
        print(f"run={r['run_id']} goal={r['config'].get('goal')} seed={r['config'].get('seed')}")
        print(f"  line={inc['line']} placed={inc['placed_obj']}@{inc['placed_boxel']}")
        print(f"  reblocked_shadows={inc['reblocked_shadows']} census={inc['census_snapshot']}")
        print(f"  target_true_hiding_place={inc['target_true_hiding_place']} oracle_shadow={inc['oracle_shadow']}")
        print(f"  plan_restarts_after={inc['plan_restarts_after']} placements_after={inc['placements_after']} episode_ended_by_this={inc['episode_ended_by_this']}")
        print(f"  run_final_outcome={inc['run_final_outcome']}")
        print()

print()
print("=== Self-shadow-name reblocks in PRIMARY corpus (obj name substring of shadow id) ===")
for r in data:
    if 'error' in r:
        continue
    for inc in r.get('incidents', []):
        obj = inc['placed_obj']
        for sid in inc['reblocked_shadows']:
            if obj in sid:
                print(f"run={r['run_id']} regime={r['regime']} line={inc['line']} placed={obj} reblocks={sid} target_hit={inc['target_true_hiding_place']} ended={inc['episode_ended_by_this']} outcome={inc['run_final_outcome']}")

print()
print("=== Cited runs: 15-25-35, 15-58-09, 17-14-10 full incident detail ===")
for want in ['run_2026-08-22_15-25-35', 'run_2026-08-22_15-58-09', 'run_2026-08-22_17-14-10']:
    for r in data:
        if r.get('run_id') == want:
            print(f"--- {want} --- regime={r.get('regime')} outcome={r.get('final_outcome')} total_place={r.get('total_place_actions')}")
            print(f"  config={r.get('config')}")
            print(f"  target={r.get('target')} oracle_shadow={r.get('oracle_shadow')}")
            for inc in r.get('incidents', []):
                print("   INC:", json.dumps(inc))
