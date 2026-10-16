#!/usr/bin/env python3
"""Run independent combat procedures through the documented JSON CLI."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import re
import subprocess
from combat_support import ROOT,OUTPUT,ENV
import combat_examples

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only')
    parser.add_argument('--workers',type=int,choices=[1,2,3,4],default=4)
    args=parser.parse_args()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    cases=[];examples=Counter()
    for feature in sorted((ROOT/'features/combat_resolution').glob('*.feature')):
        stem=feature.stem
        if args.only and args.only!=stem and not args.only.startswith(stem+'-'):continue
        irpath=OUTPUT/(stem+'.json')
        subprocess.run(['gherkin-parser',str(feature),'./'+str(irpath.relative_to(ROOT))],cwd=ROOT,env=ENV,check=True,capture_output=True,text=True)
        ir=json.loads(irpath.read_text())
        for scenario in ir['scenarios']:
            n=int(re.search(r' (\d+) - ',scenario['name'])[1])
            for i,p in enumerate(scenario['examples'],1):
                label=f'{stem}-{n:02d}-{i:02d}'
                if args.only and args.only!=stem and not label.startswith(args.only):continue
                built=getattr(combat_examples,stem)(n,p)
                if not built:raise ValueError('No independent case: '+label)
                examples[stem]+=1
                for j,case in enumerate(built,1):
                    case.label=label+(f'-{j:02d}' if len(built)>1 else '')
                    case.note=scenario['name']+'; '+json.dumps(p)+'; '+case.note
                    cases.append(case)
    if hasattr(combat_examples,'supplemental'):
        cases.extend(c for c in combat_examples.supplemental() if not args.only or c.label.startswith(args.only))
    if not cases:raise ValueError('Selection matched no cases')
    reports=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i,r in enumerate(pool.map(lambda c:c.execute(),cases),1):
            reports.append(r)
            if r['status']!='passed':print(json.dumps(r),flush=True)
            if i%25==0:print(f'UI progress {i}/{len(cases)}',flush=True)
    summary=dict(examples=dict(examples),counts=dict(Counter(r['status'] for r in reports)),modes=dict(Counter(r['mode'] for r in reports)),
       features={stem:dict(Counter(r['status'] for r in reports if r['label'].startswith(stem+'-'))) for stem in sorted({r['label'].split('-')[0] for r in reports})},reports=reports)
    (OUTPUT/('summary-'+(args.only or 'all')+'.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='reports'}),flush=True)
    return int(any(r['status']=='failed' for r in reports))

if __name__=='__main__':raise SystemExit(main())
