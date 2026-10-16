"""Independent aerospace CLI replay support. Standard library only."""
from copy import deepcopy
import json
import hashlib
import math
import os
from pathlib import Path
import struct
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'tmp/qa-aerospace'

def f32(value): return struct.unpack('f',struct.pack('f',value))[0]
def op(operation,**kw): return dict(op=operation,**kw)
def cmd(name,args='',unit='u',**kw): return op('command',unit=unit,name=name,args=args,**kw)
def diag(kind,unit='u',**kw): return op('aero_diagnose',unit=unit,kind=kind,**kw)
def configure(**kw): return op('aero_configure',unit='u',values=kw)
def advance(seconds): return op('advance',seconds=seconds)
def inspect(): return op('inspect')
def core(**kw): return op('core',unit='u',values=kw)
def path(data,key):
    for part in key.split('.'):
        data=data[int(part)] if isinstance(data,list) else data[part]
    return data

def craft(kind='AERO',**values):
    result=dict(name='u',id=10,**{'class':kind},movement='VTOL' if kind=='VTOL' else 'BIPED' if kind in ('MECH','MW') else 'FLY',at=[10,10,1],core=dict(max_speed=60,fuel=1000,fuel_orig=1000,mechskills='',vis_mod=50,cargo_inventory=[]),aerospace=dict(landed=False))
    for key,value in values.items():
        if key in ('core','aerospace'):result[key].update(value)
        else:result[key]=value
    return result

def document(unit=None,actions=None,**values):
    result=dict(config=dict(periodic_updates=False,nofusion_vtol_fuel=False),maps=[dict(name='field',id=1000,size=[30,30])],units=[unit or craft()],actions=actions or [inspect()],random=dict(streams={}))
    result.update(values)
    return result

class Case:
    def __init__(self,name,doc):self.name,self.doc,self.checks=name,doc,[]
    def expect(self,key,value,mode='equal'):
        self.checks.append(dict(path=key,value=value,mode=mode));return self
    def final(self,**values):
        for key,value in values.items():self.expect('state.units.u.'+key,value)
        return self
    def result(self,index=0,**values):
        for key,value in values.items():self.expect(f'results.{index}.'+key,value)
        return self
    def text(self,key,fragment):return self.expect(key,fragment,'contains')
    def run(self):
        folder=OUTPUT/self.name;folder.mkdir(parents=True,exist_ok=True)
        for name in ('characters','templates','maps'):
            local=folder/name
            if local.exists():shutil.rmtree(local)
        doc=deepcopy(self.doc)
        doc.setdefault('pilots',{})['root']=str(folder/'characters')
        doc.setdefault('construction',{})['root']=str(folder/'templates')
        doc['file_root']=str(folder/'maps')
        request=folder/'input.json';request.write_text(json.dumps(doc,indent=2)+'\n')
        (folder/'expected.json').write_text(json.dumps(self.checks,indent=2)+'\n')
        proc=subprocess.run([sys.executable,'-m','tools.aerospace','--input',str(request)],cwd=ROOT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp')),capture_output=True,text=True,timeout=60)
        (folder/'stdout.json').write_text(proc.stdout);(folder/'stderr.txt').write_text(proc.stderr);(folder/'exit-code.txt').write_text(str(proc.returncode)+'\n')
        failures=[];observations=[]
        if proc.returncode:failures.append('CLI exit: '+proc.stderr)
        try:
            data=json.loads(proc.stdout)
            # An expected ordinary refusal is legal; unexpected adapter errors aren't.
            expected_errors={int(c['path'].split('.')[1]) for c in self.checks if c['path'].startswith('results.') and (c['path'].endswith('.error') or c['path'].endswith('.ok') and c['value'] is False)}
            for index,row in enumerate(data['results']):
                if isinstance(row,dict) and 'error' in row and index not in expected_errors:failures.append(f'unexpected action error {index}: {row}')
            for check in self.checks:
                try:
                    actual=path(data,check['path']);value=check['value'];mode=check['mode']
                    valid=(actual==value if mode=='equal' else math.isclose(actual,value,abs_tol=1e-4,rel_tol=0) if mode=='close' else value in actual if mode=='contains' else value not in actual if mode=='excludes' else len(actual)==value if mode=='length' else bool(actual & value) if mode=='bit_set' else actual<value if mode=='less' else actual>value if mode=='greater' else sum(e['kind']==value[0] for e in actual)==value[1] if mode=='event_count' else sum(e['name']==value[0] for e in actual)==value[1] if mode=='draw_count' else any(all(e.get(k)==v for k,v in value.items()) for e in actual) if mode=='has_record' else any(isinstance(e,str) and e.endswith(value) for e in actual) if mode=='text_suffix' else not any(isinstance(e,str) and e.endswith(value) for e in actual) if mode=='no_text_suffix' else False)
                    observations.append(dict(**check,actual=actual,passed=valid))
                    if not valid:failures.append(f"{check['path']}: {actual!r} {mode} {value!r}")
                except (KeyError,IndexError,TypeError) as error:failures.append(f'{check}: {error}')
        except ValueError as error:failures.append(str(error))
        summary=dict(case=self.name,passed=not failures,assertions=observations,failures=failures)
        (folder/'assertions.json').write_text(json.dumps(summary,indent=2)+'\n')
        return summary

def feature_rows(stem,outline):
    manifest=json.loads((ROOT/'specs/aerospace-acceptance-manifest.json').read_text())
    feature=next(f for f in manifest['features'] if f['feature']==f'features/aerospace/{stem}.feature')
    assert hashlib.sha256((ROOT/feature['feature']).read_bytes()).hexdigest()==feature['sha256'], 'Feature changed: update QA procedures and manifest correspondence'
    scenario=feature['scenarios'][outline-1]
    for number,row in enumerate(scenario['examples'],1):yield f'{stem}/{outline:02}-{number:02}',dict(zip(scenario['columns'],row))
