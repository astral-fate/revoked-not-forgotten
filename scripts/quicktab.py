import json,collections,sys
R=[json.loads(l) for l in open(sys.argv[1]+'/trials.jsonl')]
agg=collections.defaultdict(collections.Counter)
for r in R:
    c=agg[(r['model'].split('/')[-1].split(':')[-1][:14],r['condition'])]; c['n']+=1
    for k in ['fact_residue','instr_residue','field_correct','redelegated','escalated','task_success','w_carried_fact','w_carried_instr','refund_ok']: c[k]+=int(r[k])
print(f"{'model':14} {'cond':15} n  factR instR corr refund redel esc succ | W:fact W:instr")
for (m,c),v in sorted(agg.items()):
    print(f"{m:14} {c:15} {v['n']:2} {v['fact_residue']:5} {v['instr_residue']:5} {v['field_correct']:4} {v['refund_ok']:6} {v['redelegated']:5} {v['escalated']:3} {v['task_success']:4} | {v['w_carried_fact']} {v['w_carried_instr']}")
