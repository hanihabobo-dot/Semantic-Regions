import json
data = json.load(open('/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels/tools/swarm_2026-08-22/D_primary_sweep_results.json'))

# Broader "practically fixed" window: from the first audit-cited live repro
# (15-25-35) to end of day. This is a HYPOTHESIS-level regime boundary
# (dev commits generally trail working-tree smoke tests by minutes-to-an-hour
# per the observed pattern: 15-58-09 already prints F7-diag text even though
# the F7 commit lands at 16:01:03).
CUTOFF = "15:25:35"

broad = [r for r in data if r.get('run_time_hhmmss', '') >= CUTOFF and 'error' not in r]
print('broad post-15:25:35 runs:', len(broad))
tot_places = sum(r.get('total_place_actions', 0) for r in broad)
incidents = [inc for r in broad for inc in r.get('incidents', [])]
print('  total place actions:', tot_places)
print('  total incidents:', len(incidents))
ended = sum(1 for inc in incidents if inc['episode_ended_by_this'])
truehit = sum(1 for inc in incidents if inc['target_true_hiding_place'])
print('  incidents that ended the episode (no further plan restart):', ended)
print('  incidents where reblocked shadow was the true hiding place:', truehit)
for r in broad:
    if r.get('incidents'):
        print('   ', r['run_id'], r.get('config', {}).get('goal'), r.get('config', {}).get('seed'), 'places=', r.get('total_place_actions'), 'outcome=', r.get('final_outcome'))

print()
print('window 12:22:42-12:42:53 (regime B, strict first impl) runs:')
b = [r for r in data if '12:22:42' <= r.get('run_time_hhmmss', '') <= '12:42:53' and 'error' not in r]
for r in b:
    print('  ', r['run_id'], r.get('config', {}).get('goal'), r.get('config', {}).get('seed'), 'places=', r.get('total_place_actions'), 'incidents=', len(r.get('incidents', [])), 'outcome=', r.get('final_outcome'))
