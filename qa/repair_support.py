"""Independent JSON/subprocess QA support; no project implementation imports."""
from copy import deepcopy
from pathlib import Path
import hashlib,json,math,os,re,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'tmp/qa-repair-economy'
MANIFEST=ROOT/'specs/repair-economy/acceptance-manifest.json'
ARMOR=547;INTERNAL=546;ELECTRIC=545;HEATSINK=403;ACTUATOR=548

def op(operation,**kw):return dict(op=operation,**kw)
def cmd(name,args='',unit='u',**kw):return op('command',unit=unit,name=name,args=args,**kw)
def inspect():return op('inspect')
def advance(seconds):return op('advance',seconds=seconds)
def repair(kind,**kw):return op('repair',kind=kind,**kw)
def diag(kind,unit='u',**kw):return op('repair_diagnose',kind=kind,unit=unit,**kw)
def section(loc,unit='u',**kw):return op('section',unit=unit,value=dict(index=loc,**kw))
def setslot(u,loc,pos=0,**kw):
    slots=u['sections'][loc].setdefault('slots',[])
    found=next((s for s in slots if s['index']==pos),None)
    if found is None:found=dict(index=pos);slots.append(found)
    found.update(kw);return found

def actor(ident=200,location=10,**kw):
    r=dict(id=ident,name='Technician'+str(ident),tech=True,location=location,connected=True,values={'Build':5,'Reflexes':5,'Intuition':5,'Learn':5,'Technician-Battlemech':2,'Technician-Aerospace':2,'Technician-Mechanic':2,'Technician-Weapons':2})
    r.update(kw);return r

def unit(name='u',ident=10,kind='MECH',**kw):
    r=dict(name=name,id=ident,character=200,**{'class':kind},movement='FLY' if kind in ('AERO','DS','SPHEROID_DS') else 'VTOL' if kind=='VTOL' else 'TRACK' if kind=='VEH_GROUND' else 'BIPED',at=[3,3,0],started=False,measured_mass=51200,repair=dict(stall=True),core=dict(max_speed=60,vis_mod=50,cargo_inventory=[],fuel=1000,fuel_orig=1000),sections=[dict(index=i,armor=10,armor_orig=10,internal=10,internal_orig=10,rear=5 if i in (2,3,4) and kind=='MECH' else 0,rear_orig=5 if i in (2,3,4) and kind=='MECH' else 0) for i in range(8)])
    r.update(kw)
    limit=6 if kind in ('AERO','DS','SPHEROID_DS','VTOL') else 5 if kind=='VEH_GROUND' else 8
    for sec in r['sections'][limit:]:sec.update(armor=0,armor_orig=0,internal=0,internal_orig=0,rear=0,rear_orig=0)
    return r

def stocks(*rows):return ','.join(f'[{p},{b},{n}]' for p,b,n in rows)
def doc(u=None,actions=None,stock='',**kw):
    r=dict(map=dict(id=1000,size=[12,12]),config=dict(periodic_updates=False),units=[u or unit()],characters=[actor()],repair_economy=dict(objects=[dict(id=1000,ECONPARTS=stock)]),random=dict(streams={'tech_rolls':[12]*30,'tech_d6':[6]*30,'repair_percent':[44]*30,'pilot_rolls':[12]*20,'sensor.random':[1]*100,'sensor.detect':[1]*100,'sensor.perception_xp':[1]*100,'damage_entry':[7]*100,'critical_rolls':[7]*50,'tow_rolls':[12]*100,'fall_directions':[1]*50,'fall_pilot_rolls':[12]*50}),actions=actions or [inspect()])
    r.update(kw);return r

def rows(stem,outline):
    feature=next(f for f in json.loads(MANIFEST.read_text())['features'] if Path(f['path']).stem==stem)
    assert hashlib.sha256((ROOT/feature['path']).read_bytes()).hexdigest()==feature['sha256']
    for i,row in enumerate(feature['scenarios'][outline-1]['examples'],1):yield f'{stem}/{outline:02}-{i:02}',row

def at(data,key):
    for p in key.split('.'):data=data[int(p)] if isinstance(data,list) else data[p]
    return data

class Case:
    def __init__(self,name,document):self.name,self.doc,self.checks=name,document,[];self.storage_origin=None;self.prepare=None;self.cli='tools.repair_economy'
    def expect(self,path,value,mode='equal'):self.checks.append(dict(path=path,value=value,mode=mode));return self
    def final(self,**kw):
        for k,v in kw.items():self.expect('state.units.u.'+k,v)
        return self
    def result(self,i=0,**kw):
        for k,v in kw.items():self.expect(f'results.{i}.'+k,v)
        return self
    def run(self):
        folder=OUTPUT/self.name;folder.mkdir(parents=True,exist_ok=True)
        d=deepcopy(self.doc)
        for field,directory in [('pilots','characters'),('construction','templates'),('repair_economy','economy')]:
            p=(OUTPUT/self.storage_origin/directory) if self.storage_origin else folder/directory
            if not self.storage_origin and p.exists():shutil.rmtree(p)

            if field!='repair_economy' or self.cli=='tools.repair_economy':d.setdefault(field,{})['root']=str(p)
        d['file_root']=str(folder/'maps')
        if self.prepare:self.prepare(d,folder)
        (folder/'input.json').write_text(json.dumps(d,indent=2)+'\n');(folder/'checks.json').write_text(json.dumps(self.checks,indent=2)+'\n')
        p=subprocess.run([sys.executable,'-m',self.cli,'--input',str(folder/'input.json')],cwd=ROOT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp')),capture_output=True,text=True,timeout=90)
        (folder/'stdout.json').write_text(p.stdout);(folder/'stderr.txt').write_text(p.stderr);(folder/'exit-code.txt').write_text(str(p.returncode))
        errors=[];checks=[]
        if p.returncode:errors.append('CLI exit: '+p.stderr)
        try:
            out=json.loads(p.stdout)
            negative={int(c['path'].split('.')[1]) for c in self.checks if c['path'].startswith('results.') and ((c['value'] is False and c['path'].endswith(('.ok','.accepted'))) or (c['path'].endswith('.error') and c['value'] is not None))}
            for i,r in enumerate(out['results']):
                if isinstance(r,dict) and (r.get('ok') is False or r.get('accepted') is False or r.get('error') is not None) and i not in negative:errors.append(f'Unexpected refusal {i}: {r}')
            for c in self.checks:
                try:
                    a=at(out,c['path']);v=c['value'];m=c['mode']
                    passed=(a==v if m=='equal' else [json.loads(line) for line in a.splitlines()]==v if m=='json_lines' else [[int(z) if j in (0,2,4) else z for j,z in enumerate(row.split('|'))] for row in a.split(',') if row]==v if m=='machine_rows' else a!=at(out,v) if m=='different_from' else a==at(out,v) if m=='same_as' else v in a if m=='contains' else v not in a if m=='not_contains' else len(a)==v if m=='length' else a>v if m=='greater' else a<v if m=='less' else bool(a&v) if m=='bit' else not a&v if m=='not_bit' else math.isclose(a,v,abs_tol=1e-4,rel_tol=0) if m=='close' else any(all(r.get(k)==x for k,x in v.items()) for r in a) if m=='has' else sum(r['name']==v[0] for r in a)==v[1] if m=='draw_count' else False)
                    checks.append(dict(**c,actual=a,passed=passed))
                    if not passed:errors.append(f"{c['path']}: {a!r} {m} {v!r}")
                except (KeyError,IndexError,TypeError) as error:errors.append(f'{c}: {error}')
        except ValueError as error:errors.append(str(error))
        result=dict(case=self.name,passed=not errors,assertions=checks,failures=errors)
        (folder/'assertions.json').write_text(json.dumps(result,indent=2)+'\n');return result

def drawcheck(c,name,values):
    c.expect('draws',[name,len(values)],'draw_count')
    for value in set(values):
        bounds=(2,12) if name=='tech_rolls' else (1,6) if name=='tech_d6' else None
        c.expect('draws',dict(name=name,value=value,**(dict(low=bounds[0],high=bounds[1]) if bounds else {})),'has')
    return c
