"""Independent Construction QA: stdlib subprocesses, source/spec oracles only."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,os,subprocess,sys,shutil
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tmp/qa-construction'
CROOT=ROOT/'btmux/btmux/btech/src/btech'

def E(name,args='',**kw):return dict(op='editor',name=name,args=args,**kw)
def T(kind,reference='',**kw):return dict(op='template',kind=kind,reference=reference,**kw)
def C(name,args='',unit='u'):return dict(op='command',name=name,args=args,unit=unit)
def R(unit='u'):return dict(op='construction_readout',unit=unit)
def I():return dict(op='inspect')
def A(seconds):return dict(op='advance',seconds=seconds)
def D(kind,*args):return dict(op='construction_diagnose',kind=kind,args=list(args))
def cat(kind,**kw):return dict(op='catalog',kind=kind,**kw)
def examples(family,outline):
    rows=[];current=0;header=None
    for lineno,line in enumerate((ROOT/'features/construction_templates'/f'{family}.feature').read_text().splitlines(),1):
        if line.strip().startswith('Scenario Outline:'):current+=1;header=None
        elif current==outline and line.strip().startswith('|'):
            cells=[c.strip() for c in line.strip().strip('|').split('|')]
            if header is None:header=cells
            else:rows.append((lineno,dict(zip(header,cells))))
    assert rows,(family,outline)
    return rows

def field(name,value):return f'{name} {{ {value} }}\n'
SECTIONS=['Left_Arm','Right_Arm','Left_Torso','Right_Torso','Center_Torso','Left_Leg','Right_Leg','Head']
INTS=[8,8,12,12,16,12,12,3]

def modern(reference='QA50',unit='Mech',move='Biped',weapon='IS.AC/5',ammo=20,fire='-',ammomode='-',rear=False):
    text=''.join(field(k,v) for k,v in [('Name','QA independent chassis'),('Reference',reference),('Type',unit),('Move_Type',move),('Tons',50),('Max_Speed','64.50'),('Heat_Sinks',10),('Computer',2),('Radio',3),('Tac_Range',20),('LRS_Range',40),('Scan_Range',20),('Radio_Range',100)])
    names=SECTIONS if unit=='Mech' else ['Left_Side','Right_Side','Front_Side','Aft_Side','Turret']
    for i,name in enumerate(names):
        text+=name+'\n'+field('Armor',24)+field('Internals',INTS[i] if unit=='Mech' else 5)
        if unit=='Mech':
            defaults={}
            if i in (0,1,5,6):defaults=dict(enumerate(['ShoulderOrHip','UpperActuator','LowerActuator','HandOrFootActuator'],1))
            if i==4:defaults={j:('Gyro' if 4<=j<=7 else 'Engine') for j in range(1,11)}
            if i==7:defaults={1:'LifeSupport',2:'Sensors',3:'Cockpit',5:'Sensors',6:'LifeSupport'}
            for j,part in defaults.items():text+=field(f'CRIT_{j}',f'{part} - - 3')
        if i==2:text+=field('CRIT_1-4' if unit=='Mech' else 'CRIT_1',f'{weapon} - {fire} 3')
        if i==3:text+=field('CRIT_1',f'Ammo_{weapon} {ammo} {ammomode} -')
        if i==0:text+=field('CRIT_5' if unit=='Mech' else 'CRIT_2','IS.MediumLaser - - 3')
    return text

def legacy(specials=0,radio=80,cls=0,move=0,triples=None):
    s=f'50 20 40 20 10 64.50 0.00 {specials}\n'
    for loc in range(8):
        s+=f'{20+loc} {INTS[loc]} {loc} 4\n'
        for pos in range(12):s+=' '.join(map(str,(triples or {}).get((loc,pos),(0,0,0))))+'\n'
    s+=f'{cls} {move}\n'
    if radio is not None:s+=str(radio)+'\n'
    return s

def firing():return [dict(op='construction_pilot',actor={'gunnery':4,'piloting':5,'health':{'build':5,'bruise':0,'lethal':0}}),C('startup'),A(40),C('lock','01'),A(1),C('fire','1 01'),I(),A(40),I()]

def document(actions,files=None,units=None,ordinary=False,**kw):
    d=dict(construction={'files':files or {}},units=units if units is not None else [{'name':'u','at':[3,3,0]}],editors=[{'name':'e','id':1,'target':'u'}],map={'size':[9,9]},config={'periodic_updates':ordinary,'lock_tick':0},random={'seed':5489},actions=actions)
    if ordinary:d['random']={'streams':{'visibility_change':[0]*400,'failure_generic_chance':[5000]*200,'attack_rolls':[12]*10,'failure_weapon_chance':[1]*10,'hit_location_rolls':[7]*50,'damage_entry':[7]*50,'tow_rolls':[12]*20,'missile_pre_roll':[6]*60,'missile_cluster':[12]*20}}
    d.update(kw);return d

class Audit:
    def __init__(self):self.rows=[];self.current=None
    def run(self,name,doc,mode='diagnostic',root=None):
        path=OUT/name;path.mkdir(parents=True,exist_ok=True)
        # Fresh case-owned file roots; cross-process reloads pass an explicit root.
        for directory in ([path/'templates'] if root is None else [])+[path/'maps']:
            if directory.exists():shutil.rmtree(directory)
        doc=deepcopy(doc);doc.setdefault('construction',{})['root']=str(root or path/'templates');doc['file_root']=str(path/'maps')
        raw=json.dumps(doc,indent=2,sort_keys=True)+'\n';(path/'input.json').write_text(raw)
        p=subprocess.run([sys.executable,'-m','tools.construction_templates','--input',str(path/'input.json')],cwd=ROOT,capture_output=True,text=True,timeout=90,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT),TMPDIR=str(ROOT/'tmp')))
        (path/'stdout.json').write_text(p.stdout);(path/'stderr.txt').write_text(p.stderr)
        self.current={'id':name,'mode':mode,'input':str(path.relative_to(ROOT)/'input.json'),'sha256':hashlib.sha256(raw.encode()).hexdigest(),'exit':p.returncode,'assertions':[]}
        self.rows.append(self.current)
        if p.returncode:raise AssertionError((name,p.returncode,p.stderr))
        return json.loads(p.stdout)
    def eq(self,label,actual,expected):
        self.current['assertions'].append(dict(label=label,actual=actual,expected=expected,passed=actual==expected))
    def save(self):
        result={'cases':len(self.rows),'assertions':sum(len(r['assertions']) for r in self.rows),'failures':sum(bool(r['exit']) for r in self.rows)+sum(not c['passed'] for r in self.rows for c in r['assertions']),'results':self.rows}
        (OUT/'results.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='results'},flush=True)
        return result
