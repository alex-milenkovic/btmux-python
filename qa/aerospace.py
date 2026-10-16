"""Run aerospace assertions through fresh public CLI processes."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from aerospace_support import Case,OUTPUT,ROOT
from aerospace_flight import controls,landing,launches,takeoff_examples,zones,fuel_and_updates,motion,control_effects
from aerospace_bombing import payload,ballistics,impacts,terrain,forests
from aerospace_bays import bay_configuration,entry_gates,callbacks,exits
from aerospace_turrets import lifecycle,delegates,contexts,supplemental_turrets
from aerospace_workflows import bridge_cases,captured_impacts,exhaust_consumers,workflows,template_workflows,friday_workflows,remaining_transfers,preservation_boundaries,aircraft_services,spheroid_descent,exhaust_observer

FACTORIES=(controls,landing,launches,takeoff_examples,zones,fuel_and_updates,motion,
           control_effects,payload,ballistics,impacts,terrain,forests,bay_configuration,
           entry_gates,callbacks,exits,lifecycle,delegates,contexts,bridge_cases,
           captured_impacts,exhaust_consumers,workflows,template_workflows,
           supplemental_turrets,friday_workflows,remaining_transfers,preservation_boundaries,
           aircraft_services,spheroid_descent,exhaust_observer)


def all_cases():
    cases=[case for factory in FACTORIES for case in factory()]
    names=[case.name for case in cases]
    assert len(names)==len(set(names)), 'Duplicate QA case identity'
    manifest=json.loads((ROOT/'specs/aerospace-acceptance-manifest.json').read_text())
    approved={f'{Path(f["feature"]).stem}/{i:02}-{j:02}' for f in manifest['features']
              for i,s in enumerate(f['scenarios'],1) for j,_ in enumerate(s['examples'],1)}
    assert approved=={name for name in names if not name.startswith('procedures/')}, 'QA/approved-example correspondence changed'
    return cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',default='')
    parser.add_argument('--workers',type=int,default=4,choices=range(1,5))
    parser.add_argument('--replay',type=Path,help='Replay saved case/input/checks JSONL')
    parser.add_argument('--export',type=Path,help='Write reproducible inputs/checks JSONL and exit')
    args=parser.parse_args()
    if args.replay:
        cases=[]
        for line in args.replay.read_text().splitlines():
            row=json.loads(line);case=Case(row['case'],row['input']);case.checks=row['checks'];cases.append(case)
    else:
        cases=all_cases()
    cases=[case for case in cases if case.name.startswith(args.only)]
    if not cases:parser.error('No matching QA cases')
    if args.export:
        args.export.parent.mkdir(parents=True,exist_ok=True)
        args.export.write_text(''.join(json.dumps(dict(case=c.name,input=c.doc,checks=c.checks),separators=(',',':'))+'\n' for c in cases))
        print(f'Exported {len(cases)} replays');return 0
    results=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for index,result in enumerate(pool.map(lambda case:case.run(),cases),1):
            results.append(result)
            if not result['passed']:print('FAIL',result['case'],*result['failures'],sep='\n',flush=True)
            if index%10==0:print(f'{index}/{len(cases)} cases, {sum(not r["passed"] for r in results)} failed',flush=True)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    summary=dict(total=len(results),passed=sum(r['passed'] for r in results),failed=[r for r in results if not r['passed']],cases=[dict(case=r['case'],passed=r['passed'],assertions=len(r['assertions'])) for r in results])
    (OUTPUT/('summary-'+(args.only.replace('/','-') or 'all')+'.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(f'{summary["passed"]}/{summary["total"]} passed',flush=True)
    return bool(summary['failed'])


if __name__=='__main__':raise SystemExit(main())
