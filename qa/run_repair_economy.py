"""Execute every independent UI example and procedure supplement, four workers."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from collections import Counter
from qa.repair_support import *
from qa.repair_access_time import access,time_cases
from qa.repair_parts import parts
from qa.repair_ammo import ammo
from qa.repair_structure import structure
from qa.repair_scrap import scrap
from qa.repair_inventory import inventory
from qa.repair_events import events
from qa.repair_persistence import persistence
from qa.repair_economy_cases import economy
from qa.repair_cargo import cargo
from qa.repair_towing import towing
from qa.repair_workflows import workflows
from qa.repair_supplements import supplements

def cases():
    return [c for factory in (access,time_cases,parts,ammo,structure,scrap,inventory,events,persistence,economy,cargo,towing,workflows,supplements) for c in factory()]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workers',type=int,choices=[4],default=4);parser.add_argument('--prefix',default='');parser.add_argument('--retry-failed',action='store_true');a=parser.parse_args()
    all_cases=cases();manifest=json.loads(MANIFEST.read_text());expected={f'{Path(f["path"]).stem}/{i:02}-{j:02}' for f in manifest['features'] for i,s in enumerate(f['scenarios'],1) for j,_ in enumerate(s['examples'],1)}
    names=[c.name for c in all_cases];assert len(names)==len(set(names));assert len(expected)==433;assert expected.issubset(names),sorted(expected-set(names))
    previous=json.loads((OUTPUT/'summary.json').read_text()) if a.retry_failed else None
    failed={r['case'] for r in previous['results'] if not r['passed']} if previous else None
    selected=[c for c in all_cases if c.name.startswith(a.prefix) and (failed is None or c.name in failed)];results=[]
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures={pool.submit(c.run):c.name for c in selected}
        for future in as_completed(futures):
            name=futures[future]
            try:r=future.result()
            except Exception as e:r=dict(case=name,passed=False,assertions=[],failures=[repr(e)])
            results.append(r)
            if not r['passed']:print(name,[str(f)[:350] for f in r['failures']],flush=True)
            if len(results)%20==0:print(f'{len(results)}/{len(selected)} completed; {sum(not x["passed"] for x in results)} failed',flush=True)
    if previous:
        assert not a.prefix and set(names)=={r['case'] for r in previous['results']}
        (OUTPUT/'before-retry-summary.json').write_text(json.dumps(previous,indent=2)+'\n')
        for row in previous['results']:
            if row['case'] not in failed:
                actual=json.loads((OUTPUT/row['case']/'assertions.json').read_text());assert actual['passed'];results.append(actual)
    count=lambda good:dict(sorted(Counter(r['case'].split('/')[0] for r in results if r['case'] in expected and r['passed']==good).items()))
    summary=dict(passed=all(r['passed'] for r in results),examples_passed=count(True),examples_failed=count(False),total=len(results),assertions=sum(len(r['assertions']) for r in results),supplements=sum(r['case'] not in expected for r in results),results=[dict(case=r['case'],passed=r['passed'],assertions=len(r['assertions']),failures=r['failures']) for r in sorted(results,key=lambda x:x['case'])])
    OUTPUT.mkdir(parents=True,exist_ok=True);(OUTPUT/('summary.json' if not a.prefix else 'filtered-summary.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2),flush=True);return 0 if summary['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
