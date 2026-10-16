"""Independent public CLI checks for the historical fighter task."""
import aerospace_support as base
from aerospace_support import *
from aerospace_workflows import finite
OUTPUT=ROOT/'tmp/qa-six-location-aerofighters'
base.OUTPUT=OUTPUT
NAMES=('Nose','Left Wing','Right Wing','Fuselage','Cockpit','Engine')
ARMOR=(24,15,15,30,16,20)
CATALOG=ROOT/'btmux-mechs'

class Case(base.Case):
    def run(self):
        result=super().run()
        try:
            output=json.loads((OUTPUT/self.name/'stdout.json').read_text())
            negatives={int(c['path'].split('.')[1]) for c in self.checks if c['path'].startswith('results.') and c['value'] is False}
            for i,row in enumerate(output['results']):
                if isinstance(row,dict) and (row.get('ok') is False or row.get('accepted') is False) and i not in negatives:
                    result['failures'].append(f'Unexpected command refusal {i}: {row}')
        except (ValueError,KeyError):pass
        for reference,contents in self.doc.get('construction',{}).get('files',{}).items():
            if reference not in ('CHP-W5','DS.Union','Cavalry','WVR-6R'):continue
            copied=OUTPUT/self.name/'templates'/reference
            valid=copied.read_bytes()==contents.encode('ascii')==(CATALOG/reference).read_bytes()
            result['assertions'].append(dict(path='original-bytes.'+reference,passed=valid))
            if not valid:result['failures'].append('Original template bytes changed: '+reference)
        result['passed']=not result['failures']
        (OUTPUT/self.name/'assertions.json').write_text(json.dumps(result,indent=2)+'\n')
        return result

def rows(stem,outline):
    manifest=json.loads((ROOT/'specs/six-location-aerofighters-acceptance-manifest.json').read_text())
    feature=next(f for f in manifest['features'] if f['path'].endswith('/'+stem+'.feature'))
    assert hashlib.sha256((ROOT/feature['path']).read_bytes()).hexdigest()==feature['sha256']
    scenario=feature['scenarios'][outline-1]
    for i,row in enumerate(scenario['examples'],1):yield f'{stem}/{outline:02}-{i:02}',dict(row)

def fighter(**kw):
    u=craft(at=[10,10,10],piloting=0,num_sinks=25,sections=[dict(index=i,armor=ARMOR[i] if i<6 else 0,armor_orig=ARMOR[i] if i<6 else 0,internal=10 if i<6 else 0,internal_orig=10 if i<6 else 0,rear=0,rear_orig=0) for i in range(8)])
    for key,value in kw.items():
        if key in ('core','aerospace'):u[key].update(value)
        else:u[key]=value
    return u

def session(u=None,actions=None,**kw):
    d=document(u or fighter(),actions,random=dict(streams=finite()))
    d['random']['streams'].update(critical_rolls=[7]*100,critical_slot=[0]*100,crittable_chance=[22]*100,fighter_weapon_choice=[0]*100,missile_pre_roll=[1]*100,missile_cluster=[12]*100,tc_location=[3]*100,aim_rolls=[7]*100)
    d.update(kw);return d

def dd(kind,unit='u',**kw):return op('diagnose',unit=unit,kind=kind,options=kw)
def damage(section,amount,unit='u',**kw):return dd('damage',unit,section=section,amount=amount,**kw)
def edit(name,args='',**kw):return op('editor',editor='e',name=name,args=args,**kw)
def slot(loc,index,**kw):return op('section',unit='u',value=dict(index=loc,slots=[dict(index=index,**kw)]))
def load(reference='CHP-W5',actions=None,**kw):
    d=session(craft(at=[50,50,0]),[op('template',unit='u',kind='load',reference=reference),*(actions or [])],**kw)
    d['maps'][0].update(size=[100,100],mapvis=60,maxvis=100,light=2)
    d['construction']=dict(files={reference:(CATALOG/reference).read_bytes().decode('ascii')})
    d['editors']=[dict(name='e',id=70,target='u')]
    return d

def drawcheck(c,name,values,low=None,high=None):
    c.expect('draws',[name,len(values)],'draw_count')
    for value in set(values):
        check=dict(name=name,value=value)
        if low is not None:check['low']=low
        if high is not None:check['high']=high
        c.expect('draws',check,'has_record')
    return c
