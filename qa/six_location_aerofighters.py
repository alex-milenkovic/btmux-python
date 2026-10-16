"""Execute all six fighter procedures through fresh public CLI processes."""
import argparse
import gzip
from concurrent.futures import ThreadPoolExecutor
from six_support import *
from six_layout import layout
from six_damage import damages
from six_tables import tables,gates
from six_criticals import direct_effects,deferred,components,missile_cases
from six_weapons import weapons
from six_workflows import workflows
from six_regressions import extras

FACTORIES=(layout,tables,damages,gates,direct_effects,deferred,components,missile_cases,weapons,workflows,extras)

def all_cases():
    cases=[c for factory in FACTORIES for c in factory()]
    names=[c.name for c in cases]
    assert len(names)==len(set(names)), 'Duplicate QA identity'
    manifest=json.loads((ROOT/'specs/six-location-aerofighters-acceptance-manifest.json').read_text())
    approved={f'{Path(f["path"]).stem}/{i:02}-{j:02}' for f in manifest['features'] for i,s in enumerate(f['scenarios'],1) for j,_ in enumerate(s['examples'],1)}
    observed={'/'.join(name.split('/')[:2]) for name in names if not name.startswith('procedures/')}
    assert approved==observed, (approved-observed,observed-approved)
    return cases

def export(cases,destination):
    rows=[]
    for c in cases:
        rows.append(dict(case=c.name,input=c.doc,checks=c.checks))
        child=OUTPUT/c.name/'reload'
        if child.exists():
            rows.append(dict(case=c.name+'/reload',input=json.loads((child/'input.json').read_text()),checks=json.loads((child/'expected.json').read_text())))
    destination.parent.mkdir(parents=True,exist_ok=True)
    payload=''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows)
    if destination.suffix=='.gz':destination.write_bytes(gzip.compress(payload.encode(),mtime=0))
    else:destination.write_text(payload)
    return len(rows)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',default='')
    parser.add_argument('--workers',type=int,default=4,choices=range(1,5))
    parser.add_argument('--replay',type=Path)
    parser.add_argument('--export',type=Path,help='Export inputs/checks after a successful run, including saved-design child processes')
    args=parser.parse_args()
    if args.replay:
        cases=[]
        payload=gzip.decompress(args.replay.read_bytes()).decode() if args.replay.suffix=='.gz' else args.replay.read_text()
        for line in payload.splitlines():
            row=json.loads(line);c=Case(row['case'],row['input']);c.checks=row['checks'];cases.append(c)
    else:cases=all_cases()
    cases=[c for c in cases if c.name.startswith(args.only)]
    if not cases:parser.error('No matching cases')
    results=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i,r in enumerate(pool.map(lambda c:c.run(),cases),1):
            results.append(r)
            if not r['passed']:print('FAIL',r['case'],*r['failures'],sep='\n',flush=True)
            if i%10==0:print(f'{i}/{len(cases)} cases; {sum(not r["passed"] for r in results)} failed',flush=True)
    summary=dict(total=len(results),passed=sum(r['passed'] for r in results),failed=[r for r in results if not r['passed']],cases=[dict(case=r['case'],passed=r['passed'],assertions=len(r['assertions'])) for r in results])
    if args.export and not summary['failed']:summary['replays_exported']=export(cases,args.export)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/('summary-'+(args.only.replace('/','-') or 'all')+'.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(f'{summary["passed"]}/{summary["total"]} passed',flush=True)
    return bool(summary['failed'])

if __name__=='__main__':raise SystemExit(main())
