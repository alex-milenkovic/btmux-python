#!/usr/bin/env python3
"""Check heat and per-tick behavior through subprocess UI and feature files."""
import argparse
from collections import Counter
import hashlib
import json
import subprocess
import sys
from heat_support import ROOT, OUTPUT
from heat_feature_cases import BUILDERS
from heat_supplemental import cases as supplements
from heat_audit_cases import cases as audit_cases


def scalar(value):
    if value in ('True','False'):return value=='True'
    try:return int(value)
    except ValueError:
        try:return float(value)
        except ValueError:return value


def feature_cases():
    contract=json.loads((ROOT/'qa/heat-updates-contract.json').read_text())
    for stem,builder in BUILDERS.items():
        feature=ROOT/f'features/heat_updates/{stem}.feature'
        ir=OUTPUT/f'{stem}.json'
        parsed=subprocess.run(['gherkin-parser',str(feature),'./'+str(ir.relative_to(ROOT))],
                              cwd=ROOT,capture_output=True,text=True,timeout=30)
        assert parsed.returncode==0,parsed.stderr
        data=json.loads(ir.read_text())
        signature=dict(background=data['background'],scenarios=[dict(name=s['name'],steps=s['steps'],
                       columns=list(s['examples'][0])) for s in data['scenarios']])
        assert signature==contract[stem], f'{stem}: unknown/changed steps; update QA procedures and driver'
        for n,scenario in enumerate(data['scenarios'],1):
            for index,row in enumerate(scenario['examples'],1):
                assert set(row)==set(signature['scenarios'][n-1]['columns'])
                c=builder(n,{k:scalar(v) for k,v in row.items()})
                c.label=f'{stem}/{n:02}-{index:02}'
                yield c


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',help='case label prefix for reproducing a failure')
    args=parser.parse_args()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    cases=list(feature_cases())
    cases.extend(supplements())
    cases.extend(audit_cases())
    reports=[]
    for c in cases:
        if args.only and not c.label.startswith(args.only):continue
        report=c.execute();reports.append(report)
        if report['failure']:print('FAIL',c.label,report['failure'],flush=True)
        elif len(reports)%25==0:print(f'{len(reports)} workflows checked',flush=True)
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [ROOT/'docs/heat-updates-cli.md',*sorted((ROOT/'features/heat_updates').glob('*.feature')),
                      *sorted((ROOT/'qa').glob('heat*'))] if p.is_file()}
    summary=dict(workflows=len(reports),passed=sum(r['failure'] is None for r in reports),
                 by_feature=dict(Counter(r['label'].split('/')[0] for r in reports)),
                 integrated=sum(r['integrated'] for r in reports),
                 diagnostic=sum(not r['integrated'] for r in reports),
                 failures=[dict(label=r['label'],failure=r['failure']) for r in reports if r['failure']],
                 hashes=hashes)
    (OUTPUT/('summary.json' if not args.only else 'reproduction.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='hashes'},indent=2))
    return int(bool(summary['failures']))


if __name__=='__main__':raise SystemExit(main())
