"""Original design loading, editor boundaries and two-process serialization."""
from six_support import *

PARTS=[[2,2,51,51,48]+[0]*7,[3,0,3]+[0]*9,[3,0,3]+[0]*9,[243,243,243,243,240]+[0]*7,[398,399,400,399,398]+[0]*7,[1,1]+[0]*10]
# Runtime ammo encoding is193+weapon index; indices50/47 for LRM15/SRM6.
MOUNTS=[(0,i,n) for i,n in enumerate(['IS.MediumLaser']*2+['IS.LRM-15']*2+['IS.SRM-6'])]+[(i,j,'IS.LargeLaser') for i in (1,2) for j in (0,2)]+[(5,j,'IS.SmallLaser') for j in (0,1)]

def original_checks(c,prefix='state.units.u',rear=False):
    c.expect(prefix+'.si',0).expect(prefix+'.destroyed',False).expect(prefix+'.real_mass',90).expect(prefix+'.max_speed',86).expect(prefix+'.fuel',750).expect(prefix+'.real_num_sinks',25)
    for loc in range(8):
        for key in ('internal','internal_orig'):c.expect(f'{prefix}.sections.{loc}.{key}',10 if loc<6 else 0)
        for key in ('armor','armor_orig'):c.expect(f'{prefix}.sections.{loc}.{key}',ARMOR[loc] if loc<6 else 0)
        for j in range(12):
            c.expect(f'{prefix}.sections.{loc}.slots.{j}.type',PARTS[loc][j] if loc<6 else 0)
            c.expect(f'{prefix}.sections.{loc}.slots.{j}.firemode',32 if rear and loc==1 and j==2 else 0)
    for j,(loc,critical,name) in enumerate(MOUNTS):
        for key,value in dict(section=loc,critical=critical,name=name).items():c.expect(f'{prefix}.weapons.{j}.{key}',value)
    c.expect(prefix+'.weapons',11,'length')
    for j,data in enumerate([8,8,8,8,15]):c.expect(f'{prefix}.sections.3.slots.{j}.data',data)
    return c

class RoundTrip(Case):
    def __init__(self,name,modification):
        actions=[]
        if modification=='Nose-current-armor19':actions=[damage('Nose',5)]
        elif modification=='Fuselage-current-armor0':actions=[damage('Fuselage',30)]
        elif modification=='LRM-bin-current-ammo3':actions=[slot(3,0,data=3)]
        elif modification=='wing-slot3-rear-mounted':actions=[edit('addweap','IS.LargeLaser LW 3 R')]
        actions += [op('template',unit='u',kind='save',reference='QA-copy',clock=0),op('template',unit='u',kind='read',reference='QA-copy')]
        super().__init__(name,load(actions=actions));self.modification=modification
        self.result(ok=True)
    def run(self):
        result=super().run()
        if result['passed']:
            output=json.loads((OUTPUT/self.name/'stdout.json').read_text())
            text=output['results'][-1]['text']
            d=load();d['construction']['files']={'QA-copy':text};d['actions'][0]['reference']='QA-copy'
            child=original_checks(Case(self.name+'/reload',d).result(ok=True),rear=self.modification=='wing-slot3-rear-mounted')
            other=child.run();result['assertions']+=other['assertions'];result['failures']+=other['failures'];result['passed']=other['passed']
            (OUTPUT/self.name/'assertions.json').write_text(json.dumps(result,indent=2)+'\n')
        return result

def layout():
    for name,row in rows('layout',1):
        i=int(row['index']);d=load(actions=[edit('displaysection',row['name'])])
        c=Case(name,d).result(ok=True).expect(f'state.units.u.sections.{i}.armor',int(row['armor'])).expect(f'state.units.u.sections.{i}.internal',10).result(1,ok=True)
        c.expect('results.1.result',int(row['slots']),'length')
        yield c
    for name,row in rows('layout',2):yield original_checks(Case(name,load(actions=[op('construction_readout',unit='u'),cmd('weaponstatus')])).result(ok=True))
    for name,row in rows('layout',3):
        c=Case(name,load(actions=[edit('resetcrits')])).result(ok=True).result(1,ok=True)
        i=NAMES.index(row['section'].replace('_',' '));types=([398,399,400,399,398]+[0]*7 if i==4 else [401 if j in (2,10) else 403 for j in range(12)] if i==5 else [0]*12)
        for j,t in enumerate(types):c.expect(f'state.units.u.sections.{i}.slots.{j}.type',t)
        yield c
    for name,row in rows('layout',4):
        action=row['operation']
        if action.startswith('display'):command=edit('displaysection',action.split('-')[1]);ok=True
        elif 'special' in action:command=edit('addspecial','HeatSink C '+('6' if 'slot6' in action else '5'));ok='slot6' not in action
        else:command=edit('addweap','IS.LargeLaser E '+('13' if 'slot13' in action else '12'));ok='slot13' not in action
        c=Case(name,load(actions=[command])).result(ok=True).result(1,ok=ok)
        if 'special' in action:
            c.expect('state.units.u.sections.4.slots.4.type',403 if ok else 398).expect('state.units.u.sections.4.slots.5.type',0)
        elif 'weapon' in action:c.expect('state.units.u.sections.5.slots.11.type',3 if ok else 0)
        yield c
    for name,row in rows('layout',5):yield RoundTrip(name,row['modification'])
    d=load(actions=[inspect(),op('construction_pilot',unit='u',actor=dict(piloting=0,gunnery=2)),cmd('startup'),advance(30),cmd('status'),cmd('critstatus','C'),cmd('weaponstatus')])
    yield Case('procedures/original-readouts',d).result(ok=True).result(5,ok=True).result(6,ok=True).expect('results.1.units.u.pilot_present',False).expect('results.5.unit.type','AERO').expect('results.5.unit.movement','FLY')
