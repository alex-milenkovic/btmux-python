"""Independent subprocess QA: fixtures and assertions never import engine APIs."""
from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'tmp/qa-damage-criticals'
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT/'tmp'))
LOC = dict(LARM=0,RARM=1,LTORSO=2,RTORSO=3,CTORSO=4,LLEG=5,RLEG=6,HEAD=7,
           LSIDE=0,RSIDE=1,FSIDE=2,BSIDE=3,TURRET=4,ROTOR=5,COCKPIT=6)
WEAP = dict(energy='IS.MediumLaser',ballistic='IS.AC/5',autocannon='IS.AC/5',missile='IS.LRM-5',flamer='IS.Flamer',PCOMBAT='PC.Rifle')
TEMP = dict(NONE=0,JAMMED=1,SHORTED=2,DUD=3,EMPTY=4,DESTROYED=5,AMMOJAM=6,AMMOCRITJAMMED=7)
FLAGS = {'moderate':1,'focus':2,'crystal':4,'barrel':8,'ballistic-feed':16,'ranging':32,'missile-feed':64}
CATEGORY = dict(energy=0,autocannon=6,ballistic=6,missile=12,flamer=18,computer=24,radio=30)

def num(x): return float(x) if '.' in str(x) else int(x)
def yes(x): return x == 'True'
def side(x): return {'LEFT':'LEFTSIDE','RIGHT':'RIGHTSIDE'}.get(x,x)
def sec(i,armor=100,internal=100,rear=20,**kw):
    return dict(index=i,armor=armor,armor_orig=armor,internal=internal,internal_orig=internal,rear=rear,rear_orig=rear,**kw)
def special(name,index=0,**kw): return dict(index=index,special=name,**kw)
def diag(kind,unit='u',**options): return dict(op='diagnose',unit=unit,kind=kind,options=options)
def cmd(name,*args,unit='u'):
    return dict(op='command',unit=unit,name=name,args=list(args))
def advance(n): return dict(op='advance',seconds=n)
def inspect(): return dict(op='inspect')
def configure(**values): return dict(op='configure',values=values)
def state(out,name='u',index=None): return (out['state'] if index is None else out['results'][index])['units'][name]
def sl(out,section=4,slot=0,index=None): return state(out,index=index)['sections'][section]['slots'][slot]
def eq(a,b):
    if isinstance(b,float): assert abs(a-b)<1e-5,(a,b)
    else: assert a==b,(a,b)
def checks(*pairs):
    for actual,expected in pairs: eq(actual,expected)
def flag(value,mask): return bool(value&mask)
def count_draw(out,name): return sum(d['name']==name for d in out['draws'])
def events(s,kind): return [e['deadline'] for e in s['events'] if e['kind']==kind]
def notices(s,text): return sum(text in m for m in s['messages'])
def destroyed_slots(out,section): return [i for i,s in enumerate(state(out)['sections'][section]['slots']) if s['firemode']&1]

def document(kind='MECH',periodic=False):
    kind={'airborne-VTOL':'VTOL','landed-VTOL':'VTOL'}.get(kind,kind)
    return dict(config={'periodic_updates':periodic},map={'size':[20,80]},
        units=[dict(name='u',**{'class':kind},at=[2,2,0],facing=180),dict(name='enemy',team=2,at=[2,3,0],movement='NONE')],
        random={'seed':0,'streams':{'damage_entry':[7]*100,'critical_rolls':[7]*100,'critical_slot':[0]*100,'pilot_rolls':[12]*100}},actions=[])
def section(d,i,**values):
    rows=d['units'][0].setdefault('sections',[])
    row=next((s for s in rows if s['index']==i),None)
    if row is None: row=sec(i);rows.append(row)
    row.update(values);return row

def mount(d,kind='energy',section_index=4,critical=0,brand=0,metadata=None,rounds=None):
    name=WEAP.get(kind,kind)
    record=dict(name=name,section=section_index,critical=critical,brand=brand)
    if metadata: record['metadata']=metadata
    d['units'][0].setdefault('weapons',[]).append(record)
    if rounds is not None:
        section(d,2).setdefault('slots',[]).append(dict(index=8,ammo=name,data=rounds))
    return name

def fire_setup(d,kind='energy',brand=0,metadata=None,rounds=None,distance=1):
    name=mount(d,kind,brand=brand,metadata=metadata,rounds=rounds)
    d['units'][1]['at']=[2,2+distance,0]
    d['units'][1]['sections']=[sec(i) for i in range(8)]
    d['random']['streams'].update(attack_rolls=[12]*20,hit_location_rolls=[7]*100)
    d['config']['periodic_updates']=True
    d['actions'] += [advance(10),cmd('target','01')]
    return name

@dataclass
class Case:
    document: object
    check: object
    label: str = ''
    invalid: bool = False
    blocked: str = ''
    note: str = ''
    def execute(self):
        folder=OUTPUT/self.label;folder.mkdir(parents=True,exist_ok=True)
        raw=self.document if isinstance(self.document,str) else json.dumps(self.document,indent=2)+'\n'
        (folder/'input.json').write_text(raw)
        result=subprocess.run([sys.executable,'-m','tools.damage_criticals','--input',str(folder/'input.json')],cwd=ROOT,env=ENV,capture_output=True,text=True,timeout=60)
        (folder/'stdout.json').write_text(result.stdout);(folder/'stderr.txt').write_text(result.stderr)
        (folder/'exit-code.txt').write_text(str(result.returncode)+'\n')
        error=None
        try:
            if self.invalid:
                assert result.returncode!=0,'invalid input accepted'
                assert result.stderr.strip(),'missing diagnostic'
                assert not result.stdout.strip(),'success emitted for invalid input'
                out={}
            else:
                eq(result.returncode,0);eq(result.stderr,'');out=json.loads(result.stdout)
            self.check(out)
        except Exception as failure: error=f'{type(failure).__name__}: {failure}'
        mode='normal' if isinstance(self.document,dict) and any(isinstance(a,dict) and a.get('op')=='command' for a in self.document.get('actions',[])) else 'diagnostic'
        report=dict(label=self.label,status='failed' if error else 'blocked' if self.blocked else 'passed',mode=mode,error=error,blocked=self.blocked,note=self.note)
        (folder/'assertions.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
