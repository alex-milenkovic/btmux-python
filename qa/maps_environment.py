#!/usr/bin/env python3
"""Independent Maps QA through the documented process CLI; stdlib only.

Inputs and expected values originate in the reviewed C and QA contract. No
production or acceptance module is imported. Raw process evidence stays in tmp.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tmp/qa-maps-operational'
CASES=[]
def D(kind,*args,**kw): return dict(op='map_diagnose',kind=kind,args=list(args),**kw)
def M(name,*args,**kw): return dict(op='map_command',name=name,args=list(args),**kw)
def C(name,*args,**kw): return dict(op='command',name=name,args=list(args),**kw)
def A(seconds): return dict(op='advance',seconds=seconds)
def I(): return dict(op='inspect')
def F(kind,file='record',**kw): return dict(op='map_file',kind=kind,file=file,**kw)
def V(**values): return dict(op='map_value',values=values)
def check(path,expected=None,**kw): return dict(path=path,expected=expected,**kw)
def case(family,name,actions,checks,*,mode='diagnostic',error=None,checker=None,followup=None,write_limit=None,**fixture):
    document=dict(map={'size':[9,9]},units=[],config={'periodic_updates':False,'lock_tick':0},random={'seed':5489})
    document.update(deepcopy(fixture));document['actions']=actions
    if 'maps' in fixture:document.pop('map',None)
    CASES.append(dict(id=family+'/'+name,family=family,mode=mode,input=document,checks=checks,error=error,checker=checker,followup=followup,write_limit=write_limit))
def declare_finite_draws():
    # Fixed input values from the accepted source-MT seeded exploratory traces.
    # Only random inputs are retained; no expected state is inserted in fixtures.
    values=json.loads((ROOT/'qa/maps-qa-finite.json').read_text())
    for item in CASES:
        if item['id'] in values:
            item['input'].setdefault('random',{}).setdefault('streams',{}).update(values[item['id']])

def examples(family,outline):
    rows=[];current=0;header=None
    for line in (ROOT/'features/maps_environment'/f'{family}.feature').read_text().splitlines():
        if line.strip().startswith('Scenario Outline:'):current+=1;header=None
        elif current==outline and line.strip().startswith('|'):
            cells=[c.strip() for c in line.strip().strip('|').split('|')]
            if header is None:header=cells
            else:
                if len(cells)!=len(header):raise ValueError('invalid example')
                rows.append(dict(zip(header,cells)))
    if not rows:raise ValueError(f'missing example {family}/{outline}')
    return rows
def get(data,path):
    for key in path.split('.') if path else []:data=data[int(key)] if isinstance(data,list) else data[key]
    return data
def verify(data,spec):
    value=get(data,spec['path'])
    if 'where' in spec:value=[r for r in value if all(r.get(k)==v for k,v in spec['where'].items())]
    if 'project' in spec:value=[get(r,spec['project']) for r in value]
    if spec.get('length'):value=len(value)
    if 'mask' in spec:value &= spec['mask']
    expected=get(data,spec['same_as']) if 'same_as' in spec else spec['expected']
    if 'contains' in spec:passed=spec['contains'] in value
    elif 'not_equal' in spec:passed=value!=spec['not_equal']
    elif 'tolerance' in spec:passed=abs(value-expected)<=spec['tolerance']
    else:passed=value==expected
    return dict(**spec,actual=value,passed=passed)
def invoke(document,path,label='',write_limit=None):
    raw=json.dumps(document,sort_keys=True,indent=2)+'\n'
    (path/(label+'input.json')).write_text(raw)
    cmd=[sys.executable,'-m','tools.maps_environment','--input',str(path/(label+'input.json'))]
    if write_limit is not None:
        cmd=[sys.executable,'-c','import resource,runpy; resource.setrlimit(resource.RLIMIT_FSIZE,('+str(write_limit)+','+str(write_limit)+')); runpy.run_module("tools.maps_environment",run_name="__main__")','--input',str(path/(label+'input.json'))]
    process=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=90,
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT),TMPDIR=str(ROOT/'tmp')))
    (path/(label+'stdout.json')).write_text(process.stdout)
    (path/(label+'stderr.txt')).write_text(process.stderr)
    (path/(label+'exit-code.txt')).write_text(str(process.returncode)+'\n')
    return process,cmd,hashlib.sha256(raw.encode()).hexdigest()
def run(item):
    path=OUT/item['id'];path.mkdir(parents=True,exist_ok=True)
    doc=deepcopy(item['input']);doc['file_root']=str(path/'files')
    result={k:item[k] for k in ('id','family','mode')}
    result['logical_input_sha256']=hashlib.sha256(json.dumps(item['input'],sort_keys=True).encode()).hexdigest()
    try:
        p,cmd,digest=invoke(doc,path,write_limit=item['write_limit']);result.update(command=cmd,fixture_sha256=digest,exit=p.returncode)
        if item['error'] is not None:
            result['assertions']=[dict(passed=p.returncode!=0 and not p.stdout.strip() and item['error'].lower() in p.stderr.lower(),expected_error=item['error'],actual=p.stderr)]
        else:
            if p.returncode:raise AssertionError(p.stderr)
            data=json.loads(p.stdout)
            supplied=doc.get('random',{}).get('streams',{})
            used=Counter(r['name'] for r in data['draws'])
            result['finite_streams']={name:dict(supplied=len(values),used=used[name],unused=values[used[name]:]) for name,values in supplied.items()}
            result['assertions']=[verify(data,c) for c in item['checks']]
            if item['checker']:
                item['checker'](data,path)
                result['assertions'].append(dict(passed=True,independent_extra_assertions=True))
            if item['followup']:
                next_doc,next_checks=item['followup'](data,path)
                next_doc['file_root']=doc['file_root']
                p2,cmd2,_=invoke(next_doc,path,'fresh-')
                if p2.returncode:raise AssertionError(p2.stderr)
                result['fresh_command']=cmd2
                result['assertions'] += [dict(verify(json.loads(p2.stdout),c),fresh_process=True) for c in next_checks]
            if not result['assertions']:raise AssertionError('no assertions')
        result['status']='pass' if all(a['passed'] for a in result['assertions']) else 'fail'
        if result['status']=='pass' and item['mode']=='blocked':result['status']='blocked'
    except Exception as e:result.update(status='fail',error=f'{type(e).__name__}: {e}')
    (path/'assertions.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'].upper(),item['id'],flush=True)
    if result['status']=='fail':print(json.dumps(result.get('error',[a for a in result.get('assertions',[]) if not a['passed']]))[:2500],flush=True)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only');parser.add_argument('--workers',type=int,choices=(1,2,3,4),default=4)
    parser.add_argument('--list',action='store_true')
    args=parser.parse_args()
    for name in ('storage','weather','files','objects','buildings','workflows','extra','lifecycle','consumers','operations'):
        target=ROOT/'qa'/f'maps_qa_{name}.py'
        if target.exists():importlib.import_module(f'maps_qa_{name}').build()
    declare_finite_draws()
    all_ids=[c['id'] for c in CASES]
    if len(set(i.casefold() for i in all_ids))!=len(all_ids):raise ValueError('duplicate output identity')
    if not args.only:
        expected=set()
        for feature in (ROOT/'features/maps_environment').glob('*.feature'):
            for outline in range(1,1+sum(l.strip().startswith('Scenario Outline:') for l in feature.read_text().splitlines())):
                expected.update(f'{feature.stem}/example-{outline:02d}-{i}' for i,_ in enumerate(examples(feature.stem,outline)))
        actual={i for i in all_ids if '/example-' in i}
        if expected!=actual:raise ValueError('incomplete example coverage: '+str(sorted(expected^actual)))
    selections=args.only.split(',') if args.only else []
    chosen=[c for c in CASES if not selections or any(s in c['id'] for s in selections)]
    if not chosen:parser.error('no matching cases')
    if args.list:
        for c in chosen:print(c['id'])
        return 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:results=list(pool.map(run,chosen))
    summary=dict(cases=results,counts=dict(Counter(r['status'] for r in results)),unique_inputs=len({r['logical_input_sha256'] for r in results}))
    label=(args.only or 'all').replace('/','-')
    if len(label)>100:label=hashlib.sha256(label.encode()).hexdigest()[:16]
    (OUT/f'summary-{label}.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary['counts']))
    return int(summary['counts'].get('fail',0)>0)

sys.modules['maps_environment_qa']=sys.modules[__name__]
if __name__=='__main__':raise SystemExit(main())
