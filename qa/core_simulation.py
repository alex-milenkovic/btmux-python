#!/usr/bin/env python3
"""Independent public-CLI Core QA. No production or acceptance imports.

Each case writes input, stdout, stderr, exit status, and individual assertions.
Run --only FAMILY or a case ID. Acceptance is a separate command/obligation.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tmp/qa-core-simulation'
CASES = []


def D(kind, *args, **kw):
    return dict(op='diagnose', kind=kind, args=list(args), **kw)


def C(name, *args, **kw):
    return dict(op='command', name=name, args=list(args), **kw)


def A(seconds): return dict(op='advance', seconds=seconds)
def I(): return dict(op='inspect')
def K(name, **kw): return dict(op='clock', name=name, **kw)
def S(callback, delay=1, data=0, **kw):
    return dict(op='schedule', callback=callback, delay=delay, data=data, **kw)


def check(path, expected=None, **kw):
    return dict(path=path, expected=expected, **kw)


def case(family, name, actions, checks, *, units=None, mode='diagnostic', error=None, repeat=False, checker=None, **fixture):
    document = dict(actions=actions, **fixture)
    if units is not None: document['units'] = units
    CASES.append(dict(id=family+'/'+name, family=family, mode=mode, input=document,
                      checks=checks, error=error,repeat=repeat,checker=checker))


def examples(family, outline):
    """Read current example values; unknown/missing outlines fail, never skip."""
    rows, current, headers = [], 0, None
    for line in (ROOT / 'features/core_simulation' / (family+'.feature')).read_text().splitlines():
        if line.strip().startswith('Scenario Outline:'):
            current += 1
            headers = None
        elif current == outline and line.strip().startswith('|'):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if headers is None: headers = cells
            else:
                if len(cells) != len(headers): raise ValueError('invalid example row')
                rows.append(dict(zip(headers, cells)))
    if not rows: raise ValueError(f'missing outline {family}/{outline}')
    return rows


def get(value, path):
    for key in path.split('.') if path else []:
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def verify(data, spec):
    if spec.get('shared_source'):
        words=json.loads(subprocess.check_output([str(OUT/'mt-oracle'),'5489'],text=True))
        cursor=0;histogram=[0]*11;errors=[]
        def number(low,high):
            nonlocal cursor
            bits=(high-low).bit_length()
            if not bits:return 0
            while True:
                value=words[cursor]>>(32-bits);cursor+=1
                if value<=high-low:return low+value
        for row in data['draws']:
            before=cursor
            if (row['low'],row['high'])==(2,12):
                expected=number(1,6)+number(1,6);histogram[expected-2]+=1
            else:expected=number(row['low'],row['high'])
            if (expected,cursor-before)!=(row['value'],row['raw_words']):errors.append(dict(draw=row,expected=expected,raw_words=cursor-before))
        state=data['state']['random']
        generator=json.loads(subprocess.check_output([str(OUT/'mt-oracle'),'state',str(cursor)],text=True))
        return dict(shared_source=True,consumers=len(data['draws']),words=cursor,errors=errors,
                    passed=not errors and state['words_consumed']==cursor and state['histogram']==histogram and state['total_rolls']==sum(histogram) and state['generator']==generator)
    actual = get(data, spec['path'])
    if 'where' in spec:
        actual = [r for r in actual if all(r.get(k) == v for k,v in spec['where'].items())]
    if 'project' in spec: actual = [get(r, spec['project']) for r in actual]
    if 'omit' in spec: actual = {k:v for k,v in actual.items() if k not in spec['omit']}
    if spec.get('length'): actual = len(actual)
    if spec.get('sum'): actual = sum(actual)
    if 'mask' in spec: actual &= spec['mask']
    if 'count_text' in spec: actual = sum(spec['count_text'] in row for row in actual)
    if spec.get('leading_integer'): actual=int(actual.split()[0])
    expected = get(data, spec['same_as']) if 'same_as' in spec else spec['expected']
    if 'omit' in spec: expected = {k:v for k,v in expected.items() if k not in spec['omit']}
    if 'contains' in spec: passed = spec['contains'] in actual
    elif 'tolerance' in spec: passed = abs(actual-expected) <= spec['tolerance']
    elif spec.get('positive'): passed = actual > 0
    else: passed = actual == expected
    return dict(**spec, actual=actual, passed=passed)


def run(item):
    path = OUT / item['id']
    path.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(item['input'], sort_keys=True, indent=2)+'\n'
    (path/'input.json').write_text(raw)
    cmd = [sys.executable, '-m', 'tools.core_simulation', '--input', str(path/'input.json')]
    process = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=60,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT), TMPDIR=str(ROOT/'tmp')))
    (path/'stdout.json').write_text(process.stdout)
    (path/'stderr.txt').write_text(process.stderr)
    (path/'exit-code.txt').write_text(str(process.returncode)+'\n')
    result = dict(id=item['id'], family=item['family'], mode=item['mode'], command=cmd,
                  fixture_sha256=hashlib.sha256(raw.encode()).hexdigest(), exit=process.returncode,
                  stdout_sha256=hashlib.sha256(process.stdout.encode()).hexdigest())
    try:
        if item['error'] is not None:
            result['assertions'] = [dict(passed=process.returncode != 0 and not process.stdout.strip()
                and item['error'].lower() in process.stderr.lower(), expected_error=item['error'], actual=process.stderr)]
        else:
            if process.returncode != 0: raise AssertionError(process.stderr)
            data = json.loads(process.stdout)
            result['assertions'] = [verify(data, s) for s in item['checks']]
            if item.get('checker'):
                item['checker'](data)
                result['assertions'].append(dict(passed=True,reviewed_consumer_assertions=True))
            if not result['assertions']: raise AssertionError('case has no assertions')
        if item.get('repeat'):
            repeated = subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=60,
                env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT),TMPDIR=str(ROOT/'tmp')))
            result['assertions'].append(dict(passed=(process.returncode,process.stdout,process.stderr)==(repeated.returncode,repeated.stdout,repeated.stderr),repeat_fresh_input=True))
        result['status'] = 'pass' if all(a['passed'] for a in result['assertions']) else 'fail'
        if result['status']=='pass' and item['mode']=='blocked': result['status']='blocked'
    except (AssertionError, KeyError, IndexError, TypeError, ValueError) as exc:
        result.update(status='fail', error=str(exc))
    (path/'assertions.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result['status'].upper(), item['id'], flush=True)
    if result['status']=='fail': print(json.dumps(result.get('error', [a for a in result.get('assertions',[]) if not a['passed']]))[:2000], flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',help='Family or case substring; comma-separated selections are allowed')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--workers',type=int,choices=(1,2,3,4),default=4)
    args = parser.parse_args()
    from core_qa_events import build as events
    from core_qa_random import build as randoms
    from core_qa_numeric import build as numeric
    from core_qa_inventory import build as inventory
    from core_qa_workflows import build as workflows
    from core_qa_branches import build as branches
    from core_qa_consumers import build as consumers
    from core_qa_lifecycle_extra import build as extra
    events(); randoms(); numeric(); inventory(); workflows(); branches()
    consumers(); extra()
    from core_qa_geometry_extra import build as geometry_extra
    geometry_extra()
    from core_qa_repair_extra import build as repair_extra
    repair_extra()
    from core_qa_inventory_extra import build as inventory_extra
    inventory_extra()
    from core_qa_final_boundaries import build as final_boundaries
    final_boundaries()
    expected_examples=set()
    for feature in (ROOT/'features/core_simulation').glob('*.feature'):
        outlines=sum(line.strip().startswith('Scenario Outline:') for line in feature.read_text().splitlines())
        for outline in range(1,outlines+1):
            expected_examples.update(f'{feature.stem}/example-{outline:02d}-{i}' for i,_ in enumerate(examples(feature.stem,outline)))
    actual_examples={c['id'] for c in CASES if '/example-' in c['id']}
    if actual_examples != expected_examples:raise ValueError('example coverage mismatch: '+str(actual_examples^expected_examples))
    if not args.only or args.only in ('randomness','geometry','integration') or 'c-oracle' in args.only or 'shared' in args.only:
        from core_qa_oracles import build as oracles
        oracles()
    if not args.only or args.only=='bv' or 'c-oracle' in args.only:
        from core_qa_bv_oracle import build as bv_oracles
        bv_oracles()
        from core_qa_legacy_oracle import build as legacy_oracles
        legacy_oracles()
    if not args.only or args.only=='cost' or 'c-oracle-cost' in args.only:
        from core_qa_cost_oracle import build as cost_oracles
        cost_oracles()
    if not args.only or args.only in ('parts','repair') or 'material' in args.only or 'c-oracle' in args.only:
        from core_qa_parts_oracle import build as parts_oracles
        parts_oracles()
    selections = args.only.split(',') if args.only else []
    selected = [c for c in CASES if not selections or any(c['family']==v or v in c['id'] for v in selections)]
    if not selected: parser.error('unknown family or case')
    if len({c['id'] for c in CASES}) != len(CASES): raise ValueError('duplicate case IDs')
    if len({c['id'].casefold() for c in CASES}) != len(CASES): raise ValueError('case-insensitive output path collision')
    if args.list:
        for c in selected: print(c['id'])
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(run,selected))
    summary = dict(cases=results, counts=dict(Counter(r['status'] for r in results)),
                   unique_inputs=len({r['fixture_sha256'] for r in results}), families={})
    for family in sorted({r['family'] for r in results}):
        summary['families'][family] = dict(Counter(r['mode']+'/'+r['status'] for r in results if r['family']==family))
    label = (args.only or 'all').replace('/','-')
    if len(label)>100: label='selection-'+hashlib.sha256(label.encode()).hexdigest()[:12]
    dest = OUT / ('summary-'+label+'.json')
    dest.write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary['counts']))
    return int(summary['counts'].get('fail',0)>0)


# Support the adjacent, QA-only catalogue modules when executed as a script.
sys.modules['core_simulation_qa'] = sys.modules[__name__]
if __name__ == '__main__': raise SystemExit(main())
