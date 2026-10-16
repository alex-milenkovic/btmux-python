"""Independent combat UI fixtures; this module imports no project APIs."""
from dataclasses import dataclass
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import os
import subprocess
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'tmp/qa-combat-resolution'
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp'))
def eq(actual,expected):
    if isinstance(expected,float):assert abs(actual-expected)<1e-5,(actual,expected)
    else:assert actual==expected,(actual,expected)
def checks(*pairs):
    for a,b in pairs:eq(a,b)
def cmd(name,*args,unit='u'):return dict(op='command',unit=unit,name=name,args=list(args))
def diag(kind,unit='u',**options):return dict(op='diagnose',unit=unit,kind=kind,options=options)
def inspect():return dict(op='inspect')
def advance(n):return dict(op='advance',seconds=n)
def configure(unit='u',**values):return dict(op='configure',unit=unit,values=values)
def sec(i,armor=200,internal=200,rear=200,**kw):
    return dict(index=i,armor=armor,armor_orig=armor,internal=internal,internal_orig=internal,rear=rear,rear_orig=rear,**kw)
def section(d,i,unit=0,**kw):
    rows=d['units'][unit].setdefault('sections',[])
    row=next((r for r in rows if r['index']==i),None)
    if row is None:row=sec(i);rows.append(row)
    row.update(kw);return row
def slot(d,loc,index=0,unit=0,**kw):
    rows=section(d,loc,unit).setdefault('slots',[])
    row=next((r for r in rows if r['index']==index),None)
    if row is None:row=dict(index=index);rows.append(row)
    row.update(kw);return row
def fixture(periodic=True):
    return dict(map={'size':[12,12]},config={'periodic_updates':periodic,'glancing_blows':0},
      units=[dict(name='u',at=[3,3,0],sections=[sec(i) for i in range(8)]),
             dict(name='v',at=[3,2,0],team=2,facing=180,sections=[sec(i) for i in range(8)])],
      random={'seed':0,'streams':{'damage_entry':[7]*200,'pilot_rolls':[12]*100,
        'hit_location_rolls':[7]*100,'physical_location':[3]*100,'critical_rolls':[7]*100}},actions=[])
def mount(d,name='IS.MediumLaser',unit=0,loc=4,index=0,ammo=None,fire=0,mode=0,**metadata):
    record=dict(name=name,section=loc,critical=index,brand=0,fire_mode=fire,ammo_mode=mode)
    if metadata:record['metadata']=metadata
    d['units'][unit].setdefault('weapons',[]).append(record)
    if ammo is not None:d['units'][unit].setdefault('ammo',[]).append(dict(weapon=name,rounds=ammo,section=2,critical=10,ammo_mode=mode))
    return record
def snapshot(out,index=None):return out['state'] if index is None else out['results'][index]
def state(out,name='u',index=None):return snapshot(out,index)['units'][name]
def rounds(out,name='u',index=None):
    return sum(s['data'] for section in state(out,name,index)['sections'] for s in section['slots'] if 193<=s['type']<385)
def armor(out,name='v',index=None):return sum(s['armor']+s['rear'] for s in state(out,name,index)['sections'])
def loss(out,name='v',baseline=3200):return baseline-armor(out,name)
def draws(out,name):return [d['value'] for d in out['draws'] if d['name']==name]
def events(out,name='u',kind=None,index=None):return [e for e in state(out,name,index)['events'] if kind is None or e['kind']==kind]
def ws(out,index=0,name='u'):return state(out,name)['weapons'][index]
def rawslot(out,loc=4,index=0,name='u'):return state(out,name)['sections'][loc]['slots'][index]

@dataclass
class Case:
    document:object
    check:object
    label:str=''
    mode:str='diagnostic'
    blocked:str=''
    invalid:bool=False
    repeat:bool=False
    note:str=''
    def execute(self):
        folder=OUTPUT/self.label;folder.mkdir(parents=True,exist_ok=True)
        raw=self.document if isinstance(self.document,str) else json.dumps(self.document,indent=2)+'\n'
        (folder/'input.json').write_text(raw)
        error=None
        try:
            result=subprocess.run([sys.executable,'-m','tools.combat_resolution','--input',str(folder/'input.json')],cwd=ROOT,env=ENV,capture_output=True,text=True,timeout=60)
            for file,value in [('stdout.json',result.stdout),('stderr.txt',result.stderr),('exit-code.txt',str(result.returncode)+'\n')]:
                (folder/file).write_text(value)
            if self.invalid:
                assert result.returncode!=0,'invalid input accepted'
                assert result.stderr.strip(),'missing error diagnostic'
                eq(result.stdout,'');out={}
            else:
                eq(result.returncode,0);eq(result.stderr,'');out=json.loads(result.stdout)
            self.check(out)
            if self.repeat:
                again=subprocess.run([sys.executable,'-m','tools.combat_resolution','--input',str(folder/'input.json')],cwd=ROOT,env=ENV,capture_output=True,text=True,timeout=60)
                checks((again.returncode,result.returncode),(again.stdout,result.stdout),(again.stderr,result.stderr))
        except Exception:error=traceback.format_exc()
        mode=self.mode
        if isinstance(self.document,dict):
            config=self.document.get('config',{})
            actions=self.document.get('actions',[])
            ordinary=(isinstance(config,dict) and config.get('periodic_updates') is not False and
                isinstance(actions,list) and all(isinstance(a,dict) and a.get('op') in ('command','advance','inspect') for a in actions))
            if not ordinary:mode='diagnostic'
        report=dict(label=self.label,status='failed' if error else 'blocked' if self.blocked else 'passed',mode=mode,blocked=self.blocked,error=error,note=self.note,input_sha256=hashlib.sha256(raw.encode()).hexdigest())
        (folder/'assertions.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
