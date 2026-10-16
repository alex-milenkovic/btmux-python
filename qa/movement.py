#!/usr/bin/env python3
"""Run movement QA exclusively through subprocess user interfaces."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from movement_cases import FACTORIES

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'tmp/qa-movement'
COVERAGE = False


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command):
    if COVERAGE and command[:3] == [sys.executable, '-m', 'tools.movement']:
        command = [sys.executable, '-m', 'coverage', 'run', '--append',
            '--data-file=tmp/quality/.coverage', '--source=core,data,entities,physics,systems,tools,acceptance',
            *command[1:]]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT/'tmp')))
    return {'command':command,'status':result.returncode,'stdout':result.stdout,'stderr':result.stderr}


def observations(response):
    """Derive indexes and totals from public output, without rule calculations."""
    data = deepcopy(response)
    previous = {}
    for result in data['results']:
        result['hexes'] = {','.join(map(str,h['at'])):h for h in result['snapshot']['map']['hexes']}
        result['terrain_counts'] = dict(Counter(h['terrain'] for h in result['hexes'].values()))
        for terrain in ('ICE','WATER'): result['terrain_counts'].setdefault(terrain,0)
        result['damage_by_unit'] = {name:0 for name in result['snapshot']['units']}
        for cluster in result['damage_clusters']: result['damage_by_unit'][cluster['unit']] += cluster['resolved']
        current = result['snapshot']['units'].get('A',{}).get('timers',{})
        result['new_timers'] = sorted(set(current)-set(previous))
        previous = current
    return data


def verify(data, checks):
    for check in checks:
        actual = data
        for key in check['path']: actual = actual[key]
        expected, comparison = check['value'],check['comparison']
        if comparison=='contains': ok=expected in actual
        elif comparison=='absent': ok=expected not in actual
        elif comparison=='greater': ok=actual>expected
        elif comparison=='text': ok=any(expected in item['text'] for item in actual)
        elif comparison=='clusters': ok=[hit['requested'] for hit in actual]==expected
        elif isinstance(expected,float): ok=abs(actual-expected)<1e-6
        else: ok=actual==expected
        if not ok: raise AssertionError(f"{check['path']}: expected {comparison} {expected!r}, got {actual!r}")


def execute(label, workflow, checks, errors, records):
    request = OUTPUT / (label+'.request.json')
    request.parent.mkdir(parents=True,exist_ok=True)
    request.write_text(json.dumps(workflow,indent=2)+'\n')
    record = run([sys.executable,'-m','tools.movement','--script',str(request)])
    record.update(label=label,checks=checks,request=str(request.relative_to(ROOT)),passed=False)
    try:
        if record['status'] or record['stderr']: raise AssertionError(f"CLI exit {record['status']}: {record['stderr']}")
        response=json.loads(record['stdout'])
        if len(response['results']) != len(workflow['actions']): raise AssertionError('action count mismatch')
        verify(observations(response),checks)
        record['passed']=True
    except (AssertionError,KeyError,IndexError,ValueError,TypeError) as error:
        record['error']=str(error);errors.append({'label':label,'error':str(error)})
    (OUTPUT/(label+'.result.json')).write_text(json.dumps(record,indent=2)+'\n')
    records.append({key:record[key] for key in ('label','passed')})


def main():
    global COVERAGE
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=FACTORIES)
    parser.add_argument('--coverage', action='store_true', help='append sequential CLI coverage to tmp/quality/.coverage')
    args=parser.parse_args()
    COVERAGE=args.coverage
    OUTPUT.mkdir(parents=True,exist_ok=True)
    errors,records,counts=[],[],{}
    contract=json.loads((ROOT/'qa/movement-contract.json').read_text())
    for group,factory in FACTORIES.items():
        if args.group and group!=args.group: continue
        feature=ROOT/'features/movement'/f'{group}.feature'
        ir_path=OUTPUT/f'{group}.ir.json'
        parsed=run(['gherkin-parser',str(feature),str(ir_path)])
        if parsed['status']: raise RuntimeError(parsed)
        ir=json.loads(ir_path.read_text())
        shape={'background':ir['background'],'scenarios':[{'name':s['name'],'steps':s['steps']} for s in ir['scenarios']]}
        if shape!=contract[group]: raise AssertionError(f'{group}: fixture steps changed; update the UI procedures and contract')
        count=0
        for index,scenario in enumerate(ir['scenarios']):
            for row_index,row in enumerate(scenario['examples']):
                document,checks=factory(index,row)
                execute(f'{group}/{index+1:02}/{row_index+1:02}',document,checks,errors,records)
                count+=1
        counts[group]=count
        print(f'{group}: {count} rows; cumulative failures {len(errors)}',flush=True)
    if not args.group:
        from movement_extra import cases, errors_suite
        for label,document,checks in cases(): execute('extra/'+label,document,checks,errors,records)
        errors_suite(run,OUTPUT,errors,records)
    report={'passed':not errors,'groups':counts,'checks':records,'errors':errors,
            'procedure_sha256':sha(Path(__file__)),
            'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'tools/movement.py',ROOT/'tools/movement_inputs.py',ROOT/'core/randomness.py',ROOT/'qa/movement.py',ROOT/'qa/movement_cases.py',ROOT/'qa/movement_extra.py']},
            'features':{p.name:sha(p) for p in sorted((ROOT/'features/movement').glob('*.feature'))}}
    (OUTPUT/(f'results-{args.group}.json' if args.group else 'results.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'groups':counts,'errors':errors},indent=2))
    return int(bool(errors))


if __name__=='__main__': raise SystemExit(main())
