"""Independent HUD UI QA: only stdlib and subprocess access to the product."""
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tmp/qa-hud-status/current-card'


def action(op, **values):
    return dict(op=op, **values)


def command(name, args='', unit='u'):
    return action('command', unit=unit, name=name, args=args.split() if isinstance(args, str) else args)


def hud(text, session='pilot', **values):
    return action('hudinfo', session=session, text=text, **values)


def unit(name='u', ident=10, **values):
    return dict(dict(name=name, id=ident, contact_id='AA' if name == 'u' else 'TT', at=[5,5,0]), **values)


def document(units=None, actions=None):
    return dict(map=dict(id=1000, size=[100,100]), units=units or [unit()],
                config=dict(periodic_updates=False), sessions=[dict(name='pilot',unit='u')],
                random=dict(seed=123,streams={'attack_rolls':[7]*30,'attack_dice':[6,5,1]*30,
                    'sensor.detect':[1]*100,'sensor.random':[1]*100,'sensor.perception_xp':[1]*100,'map_contact_id':[0,0,0,1,0,2]*10,'failure_weapon_chance':[1]*30,'fire_spread':[2]*20,'smoke_duration':[90]*40,'hit_location_rolls':[7]*30,'damage_entry':[7]*30,'mine_discovery':[9]*20,'perception_rolls':[12]*20,'visibility_change':[0]*100,'failure_generic_chance':[1]*100}),
                actions=actions or [])


def examples(stem):
    path=ROOT/'features/hud_status'/f'{stem}.feature'
    parsed=json.loads((ROOT/'tmp/acceptance'/f'hud_status-{stem}.json').read_text())
    for number, scenario in enumerate(parsed['scenarios'],1):
        for index,row in enumerate(scenario.get('examples') or [{}],1):
            yield f'{stem}/{number:02}-{index:02}', number, row, dict(
                feature=path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                scenario=scenario['name'], example=index, row=row)


def get(data,path):
    path,*column=path.split('|')
    if path:
        head,*tail=path.split('.')
        if head=='*':
            data=[get(item,'.'.join(tail)) for item in data]
        else:
            data=get(data[int(head)] if isinstance(data,list) else data[head],'.'.join(tail))
    return data.split(',')[int(column[0])] if column else data


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


@lru_cache(maxsize=1)
def driver_hashes():
    return {path.name:hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT/'qa').glob('hud_displays*.py')) if path.name!='hud_displays_audit.py'}


@lru_cache(maxsize=1)
def production_hashes():
    return {path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
            for directory in ('core','entities','physics','systems','tools','data')
            for path in sorted((ROOT/directory).rglob('*.py'))}


class Case:
    def __init__(self,name,doc,meta=None):
        self.name,self.doc,self.meta,self.checks=name,doc,meta or {},[]

    def expect(self,path,value,mode='equal'):
        self.checks.append(dict(path=path,expected=value,mode=mode));return self

    def run(self):
        folder=OUT/self.name;folder.mkdir(parents=True,exist_ok=True)
        store=folder/'store'
        if store.exists():shutil.rmtree(store)
        doc=deepcopy(self.doc);checks=deepcopy(self.checks)
        prefix=[dict(op='cache',unit=row['viewer'],target=row['target'],flags=row['flags']) for row in doc.get('diagnostic_cache',[])]
        if prefix:
            doc['actions']=prefix+doc['actions']
            for check in checks:
                check['path']=re.sub(r'^results\.(\d+)',lambda m:'results.'+str(int(m[1])+len(prefix)),check['path'])
                if check['mode'] in ('same','changed'):check['expected']=re.sub(r'^results\.(\d+)',lambda m:'results.'+str(int(m[1])+len(prefix)),check['expected'])
        doc.setdefault('hud_display',{})['root']=str(store)
        (folder/'input.json').write_text(json.dumps(doc,indent=2)+'\n')
        (folder/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
        response=subprocess.run([sys.executable,'-m','tools.hud_status','--input',str(folder/'input.json')],
            cwd=ROOT,capture_output=True,text=True,timeout=90,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp')))
        for name,value in [('stdout.json',response.stdout),('stderr.txt',response.stderr),('exit-code.txt',str(response.returncode))]:
            (folder/name).write_text(value)
        results=[];errors=[]
        if response.returncode:errors.append('CLI exit '+str(response.returncode)+': '+response.stderr)
        if self.meta.get('stdin_parity'):
            if store.exists():shutil.rmtree(store)
            alternate=subprocess.run([sys.executable,'-m','tools.hud_status'],input=(folder/'input.json').read_text(),
                cwd=ROOT,capture_output=True,text=True,timeout=90,
                env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp')))
            for name,value in [('stdin-stdout.json',alternate.stdout),('stdin-stderr.txt',alternate.stderr),('stdin-exit-code.txt',str(alternate.returncode))]:(folder/name).write_text(value)
            if alternate.returncode!=response.returncode or alternate.stdout!=response.stdout or alternate.stderr!=response.stderr:errors.append('stdin/input invocation mismatch')
        try:
            output=json.loads(response.stdout)
            for index,result in enumerate(output['results']):
                if isinstance(result,dict) and (result.get('error_kind')=='invalid-input' or result.get('error')):errors.append(f'action {index} invalid input: '+str(result.get('error')))
            if len(output['results'])!=len(doc['actions']):errors.append('action/result count mismatch')
            for index,result in enumerate(output['results']):
                if not isinstance(result,dict) or 'records' not in result:continue
                records=result['records'];wire=result.get('wire','')
                if records and all(r.get('class') is not None for r in records):
                    frames=wire.split('\r\n')
                    if frames[-1]!='' or len(frames)!=len(records)+1:errors.append(f'HUD {index}: invalid CRLF framing')
                    for frame,record in zip(frames,records):
                        suffix=':'+record['class']+':'+record['type']+'# '+record['payload']
                        if not frame.startswith('#HUD:') or not frame.endswith(suffix):errors.append(f'HUD {index}: record/wire mismatch')
                    if any(r['type']=='E' for r in records) and any(r['type']=='D' for r in records):errors.append(f'HUD {index}: Done after refusal')
                    if any(r['type'] in ('L','S') for r in records) and [r['type'] for r in records].count('D')!=1:errors.append(f'HUD {index}: missing/duplicate Done')
            for check in checks:
                try:
                    actual=get(output,check['path']);expected=check['expected'];mode=check['mode']
                    passed=(actual==expected if mode=='equal' else expected in actual if mode=='contains' else
                            expected not in actual if mode=='excludes' else len(actual)==expected if mode=='length' else
                            actual.split(',')==list(map(str,expected)) if mode=='csv' else
                            actual==get(output,expected) if mode=='same' else
                            actual!=get(output,expected) if mode=='changed' else
                            any(all(item.get(k)==v for k,v in expected.items()) for item in actual) if mode=='has_fields' else
                            sum(expected['text'] in str(item) for item in actual)==expected['count'] if mode=='count_contains' else
                            re.search(expected,actual) is not None if mode=='regex' else
                            all(token not in json.dumps(actual) for token in expected) if mode=='no_leak' else False)
                    results.append(dict(**check,actual=actual,passed=passed))
                    if not passed:errors.append(f"{check['path']}: {str(actual)[:200]} {mode} {str(expected)[:200]}")
                except (KeyError,IndexError,TypeError,AttributeError) as error:
                    results.append(dict(**check,passed=False,error=str(error)));errors.append(str(check)+': '+str(error))
        except (ValueError,KeyError) as error:errors.append(str(error))
        meta=dict(self.meta,fixture_sha256=digest(self.doc),oracle_sha256=digest(self.checks),driver_sha256=driver_hashes(),production_sha256=digest(production_hashes()))
        if prefix:meta['seeded_los_cache']=True
        if any(a['op']=='display_diagnostic' for a in doc['actions']):meta['diagnostic']=True
        result=dict(case=self.name,meta=meta,passed=not errors,assertions=results,errors=errors)
        (folder/'assertions.json').write_text(json.dumps(result,indent=2)+'\n')
        return result


def formed(form):
    names={'biped':('MECH','BIPED'),'quad':('MECH','QUAD'),'vehicle':('VEH_GROUND','TRACK'),
        'turreted-vehicle':('VEH_GROUND','TRACK'),'VTOL':('VTOL','VTOL'),'AERO':('AERO','FLY'),
        'DS':('DS','FLY'),'SPHEROID_DS':('SPHEROID_DS','FLY'),'MW':('MW','BIPED'),
        'BSUIT':('BSUIT','BIPED'),'NAVAL-HULL':('VEH_NAVAL','HULL'),
        'NAVAL-FOIL':('VEH_NAVAL','FOIL'),'NAVAL-SUB':('VEH_NAVAL','SUB'),'INSTALLATION':('MECH','NONE')}
    if form.startswith(('MECH-','VEHICLE-')):
        kind,move=form.split('-');return dict(zip(('class','movement'),('VEH_GROUND' if kind=='VEHICLE' else kind,move)))
    return dict(zip(('class','movement'),names[form]))


def record(case,index,cls,kind,payload,key='test'):
    case.expect(f'results.{index}.records.0',dict(type=kind,payload=payload,**{'class':cls}))
    return case.expect(f'results.{index}.wire',f'#HUD:{key or "???"}:{cls}:{kind}# {payload}\r\n')
