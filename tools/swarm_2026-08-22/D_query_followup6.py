import json
data = json.load(open('/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels/tools/swarm_2026-08-22/D_primary_sweep_results.json'))

all_inc = [(r, inc) for r in data if 'error' not in r for inc in r.get('incidents', [])]
print("total incidents:", len(all_inc))
succ = sum(1 for r, inc in all_inc if inc['run_final_outcome'] == 'SUCCESS')
fail_ended_by_this = sum(1 for r, inc in all_inc if inc['episode_ended_by_this'])
fail_not_ended_by_this = sum(1 for r, inc in all_inc
                              if inc['run_final_outcome'] != 'SUCCESS' and not inc['episode_ended_by_this'])
print("  incident's run ultimately SUCCESS:", succ)
print("  incident's run FAILED and this incident is the terminal one (no later plan restart):", fail_ended_by_this)
print("  incident's run FAILED but NOT the terminal cause (later replanning happened / another incident is terminal):", fail_not_ended_by_this)

print()
regd_inc = [(r, inc) for r, inc in all_inc if r['regime'] == 'D(current,0.15-gate)']
print("regime D incidents:", len(regd_inc))
for r, inc in regd_inc:
    print(f"  {r['run_id']} ended_by_this={inc['episode_ended_by_this']} outcome={inc['run_final_outcome'][:50]}")

print()
regabc_places = sum(r.get('total_place_actions',0) for r in data if 'error' not in r and r['regime']=='A/B/C(pre-fix or first-impl)')
regabc_inc = sum(len(r.get('incidents',[])) for r in data if 'error' not in r and r['regime']=='A/B/C(pre-fix or first-impl)')
regd_places = sum(r.get('total_place_actions',0) for r in data if 'error' not in r and r['regime']=='D(current,0.15-gate)')
regd_inc_n = sum(len(r.get('incidents',[])) for r in data if 'error' not in r and r['regime']=='D(current,0.15-gate)')
print(f"regime A/B/C: {regabc_inc}/{regabc_places} = {100*regabc_inc/regabc_places:.1f}% of placements immediately reblocked")
print(f"regime D:     {regd_inc_n}/{regd_places} = {100*regd_inc_n/regd_places:.1f}% of placements immediately reblocked")
