#!/usr/bin/env python3
"""Check sensors and LOS through the documented CLI only."""
import argparse
from collections import Counter
import hashlib
import json
import subprocess
from sensors_support import ROOT,OUTPUT,ENV
from sensors_feature_cases import BUILDERS


def scalar(v):
    if v in ('True','False'): return v=='True'
    try: return int(v)
    except ValueError:
        try: return float(v)
        except ValueError: return v


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',help='Feature stem or case label prefix')
    args=parser.parse_args();OUTPUT.mkdir(parents=True,exist_ok=True)
    contract=json.loads((ROOT/'qa/sensors-los-contract.json').read_text());cases=[]
    for stem,builder in BUILDERS.items():
        if args.only and not args.only.startswith(stem): continue
        feature=ROOT/f'features/sensors_los/{stem}.feature';ir=OUTPUT/f'{stem}.json'
        parsed=subprocess.run(['gherkin-parser',str(feature),'./'+str(ir.relative_to(ROOT))],cwd=ROOT,env=ENV,capture_output=True,text=True,timeout=60)
        assert parsed.returncode==0,parsed.stderr
        data=json.loads(ir.read_text())
        signature=dict(background=data.get('background'),scenarios=[dict(name=s['name'],steps=s['steps'],columns=list(s['examples'][0])) for s in data['scenarios']])
        assert signature==contract[stem],f'{stem}: specification changed; update matching QA fixtures'
        for n,scenario in enumerate(data['scenarios'],1):
            for index,row in enumerate(scenario['examples'],1):
                label=f'{stem}/{n:02}-{index:02}'
                if args.only and not label.startswith(args.only): continue
                c=builder(n,{k:scalar(v) for k,v in row.items()});c.label=label
                c.assertions='\n'.join(s['text'] for s in scenario['steps'])+'\n'+json.dumps(row,sort_keys=True)
                cases.append(c)
    try:
        from sensors_supplemental import cases as supplements
    except ModuleNotFoundError as error:
        if error.name!='sensors_supplemental': raise
    else: cases.extend(c for c in supplements() if not args.only or c.label.startswith(args.only))
    reports=[]
    for c in cases:
        report=c.execute();reports.append(report)
        if report['failure']: print('FAIL',c.label,report['failure'],flush=True)
        elif len(reports)%20==0: print(f'{len(reports)} workflows checked',flush=True)
    if not reports: raise ValueError('no QA cases selected')
    summary=dict(workflows=len(reports),totals=dict(Counter(r['status'] for r in reports)),by_feature={stem:dict(Counter(r['status'] for r in reports if r['label'].startswith(stem+'/'))) for stem in BUILDERS},
                 diagnostic=sum(r['diagnostic'] for r in reports),failures=[r for r in reports if r['failure']],blocked=[r for r in reports if r['blocked']])
    summary['hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sorted((ROOT/'qa').glob('sensors*')),*sorted((ROOT/'features/sensors_los').glob('*.feature'))] if p.is_file()}
    (OUTPUT/('reproduction.json' if args.only else 'summary.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('hashes','failures','blocked')},indent=2))
    return int(bool(summary['failures']))


if __name__=='__main__': raise SystemExit(main())
