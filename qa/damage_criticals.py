#!/usr/bin/env python3
"""Execute the independent damage CLI procedures; --only accepts feature or case."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import re
import subprocess
from damage_support import ROOT, OUTPUT, ENV
import damage_feature_cases as feature_cases
from damage_supplemental import all_cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only')
    parser.add_argument('--workers',type=int,choices=[1,2,3,4],default=4)
    args=parser.parse_args()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    reports=[];examples=Counter()
    for feature in sorted((ROOT/'features/damage_criticals').glob('*.feature')):
        stem=feature.stem
        if args.only and args.only!=stem and not args.only.startswith(stem+'-'):continue
        ir_path=OUTPUT/(stem+'.json')
        subprocess.run(['gherkin-parser',str(feature),'./'+str(ir_path.relative_to(ROOT))],cwd=ROOT,env=ENV,check=True,capture_output=True,text=True)
        ir=json.loads(ir_path.read_text())
        builder=getattr(feature_cases,stem)
        feature_work=[]
        for scenario in ir['scenarios']:
            n=int(re.search(r' (\d+) - ',scenario['name'])[1])
            for row,p in enumerate(scenario.get('examples') or [{}],1):
                label=f'{stem}-{n:02d}-{row:02d}'
                if args.only and args.only!=stem and not label.startswith(args.only):continue
                examples[stem]+=1
                cases=builder(n,p)
                if not cases:raise ValueError(f'No execution for {label}')
                for i,case in enumerate(cases,1):
                    case.label=label+(f'-{i:02d}' if len(cases)>1 else '')
                    case.note=scenario['name']+'; '+json.dumps(p)+'; '+case.note
                    feature_work.append(case)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for report in pool.map(lambda case:case.execute(),feature_work):
                reports.append(report)
                if report['status']=='failed':print(report,flush=True)
        print(stem,dict(Counter(r['status'] for r in reports if r['label'].startswith(stem+'-'))),flush=True)
    extra=[case for case in all_cases() if not args.only or args.only==case.label.split('-')[0] or case.label.startswith(args.only)]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for index,report in enumerate(pool.map(lambda case:case.execute(),extra),1):
            reports.append(report)
            if report['status']!='passed':print(report,flush=True)
            if index%50==0:print(f'Supplemental progress: {index}/{len(extra)}',flush=True)
    summary=dict(examples=dict(examples),counts=dict(Counter(r['status'] for r in reports)),modes=dict(Counter(r['mode'] for r in reports)),reports=reports)
    (OUTPUT/('summary-'+(args.only or 'all')+'.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='reports'}),flush=True)
    return int(any(r['status']=='failed' for r in reports))

if __name__=='__main__':raise SystemExit(main())
