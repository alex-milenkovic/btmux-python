"""Procedure 13: shared-stock command journeys and preserved original fighters."""
from qa.repair_persistence import Journey
from qa.repair_towing import tow_doc
from qa.repair_cargo import hangar
from qa.repair_access_time import gun,source
from qa.repair_support import *

def damage(loc,amount):return op('diagnose',unit='u',kind='damage',options=dict(section=loc,amount=amount))
def original():
    u=unit(kind='AERO',at=[50,50,0]);d=doc(u,stock=stocks((ARMOR,0,5)))
    d['map'].update(size=[100,100],mapvis=60,maxvis=100,light=2)
    d['characters'][0]['values'].update({'Piloting-Aerospace':8,'Gunnery-Laser':8,'Gunnery-Missile':8})
    d['construction']=dict(files={'CHP-W5':(ROOT/'btmux-mechs/CHP-W5').read_bytes().decode('ascii')})
    d['editors']=[dict(name='e',id=70,target='u')]
    d['actions']=[op('template',unit='u',kind='load',reference='CHP-W5'),op('personnel',unit='u',kind='attach',player=200)]
    d['random']['streams'].update(fuel_check=[1]*800,failure_generic_chance=[5000]*100,failure_weapon_chance=[1]*100,visibility_change=[1]*800,**{'sensor.random':[1]*1000,'sensor.detect':[1]*1000,'sensor.perception_xp':[1]*1000},character_d6=[6]*100,hit_location_rolls=[7]*600,crittable_chance=[22]*100,critical_slot=[0]*100,fighter_weapon_choice=[0]*100,fire_duration=[120]*100,fire_rolls=[2]*100,attack_rolls=[12]*50,map_contact_id=list(range(26))*20)
    return d

def original_checks(c,prefix='state.units.u'):
    for key,value in dict(si=0,real_mass=90,max_speed=86,fuel=750,real_num_sinks=25).items():c.expect(prefix+'.'+key,value)
    for loc,armor in enumerate([24,15,15,30,16,20,0,0]):
        for key,value in dict(armor=armor,armor_orig=armor,internal=10 if loc<6 else 0,internal_orig=10 if loc<6 else 0).items():c.expect(f'{prefix}.sections.{loc}.{key}',value)
    c.expect(prefix+'.weapons',11,'length');return c

class OriginalJourney:
    name='workflows/01-09'
    def run(self):
        d=original();d['actions'] +=[inspect(),damage('Nose',5),cmd('fixarmor','N'),inspect(),advance(899),inspect(),advance(1),inspect(),op('template',unit='u',kind='save',reference='Repaired-CHP',clock=0),op('template',unit='u',kind='read',reference='Repaired-CHP')]
        first=Case(self.name+'/before',d).result(ok=True).result(4,ok=True).expect('results.5.units.u.sections.0.armor',19).expect('results.7.units.u.sections.0.armor',23).expect('results.9.units.u.sections.0.armor',24).expect('state.economy.objects.1000.ECONPARTS','').expect('state.repair_jobs',[])
        original_checks(first);a=first.run();phases=[a]
        if a['passed']:
            out=json.loads((OUTPUT/first.name/'stdout.json').read_text());saved=out['results'][-1]['text'];later=original();later['construction']['files']={'Repaired-CHP':saved};later['actions'][0]['reference']='Repaired-CHP'
            child=original_checks(Case(self.name+'/after',later).result(ok=True));phases.append(child.run())
            original_bytes=(ROOT/'btmux-mechs/CHP-W5').read_bytes();copied=(OUTPUT/first.name/'templates/CHP-W5').read_bytes();same=original_bytes==copied
            phases.append(dict(case=self.name+'/provenance',passed=same,assertions=[dict(source_sha256=hashlib.sha256(original_bytes).hexdigest(),copied_sha256=hashlib.sha256(copied).hexdigest(),passed=same)],failures=[] if same else ['Original template bytes changed']))
        r=dict(case=self.name,passed=all(x['passed'] for x in phases),assertions=[a for p in phases for a in p['assertions']],failures=[f for p in phases for f in p['failures']],phases=phases)
        (OUTPUT/self.name/'assertions.json').write_text(json.dumps(r,indent=2)+'\n');return r

class InventoryJourney:
    name='workflows/01-07'
    def run(self):
        d=doc(characters=[actor(location=1000)],actions=[cmd('Raddstuff','HeatSink 3'),diag('add_time',actor=200,minutes=10),inspect()]);d['repair_economy']['objects'].append(dict(id=200,TECHTIME='1600'));d['actions'].insert(0,op('clock',name='skip_seconds',seconds=1000))
        first=Case(self.name+'/before',d).result(1,ok=True).expect('state.economy.objects.1000.ECONPARTS',stocks((HEATSINK,0,3))).expect('state.economy.objects.200.TECHTIME','2200');a=first.run();phases=[a]
        if a['passed']:
            later=doc(characters=[],actions=[inspect(),cmd('Raddstuff','HeatSink 2'),cmd('Rremovestuff','HeatSink 1'),cmd('manifest')]);later['repair_economy']['objects']=[];later['actions'].insert(0,op('clock',name='skip_seconds',seconds=1000))
            second=Case(self.name+'/after',later);second.storage_origin=first.name
            second.expect('results.1.economy.objects.1000.ECONPARTS',stocks((HEATSINK,0,3))).expect('state.economy.objects.1000.ECONPARTS',stocks((HEATSINK,0,4))).expect('state.economy.objects.200.TECHTIME','2200').expect('state.characters.200.location',1000);phases.append(second.run())
        r=dict(case=self.name,passed=all(x['passed'] for x in phases),assertions=[a for p in phases for a in p['assertions']],failures=[f for p in phases for f in p['failures']],phases=phases)
        (OUTPUT/self.name/'assertions.json').write_text(json.dumps(r,indent=2)+'\n');return r

def workflows():
    # Sequential internal and armor callbacks consume the same room inventory.
    u=unit();u['sections'][4].update(internal=8,armor=7)
    d=doc(u,stock=stocks((INTERNAL,0,2),(ARMOR,0,3)),actions=[cmd('fixinternal','CT'),advance(1079),inspect(),advance(1),cmd('fixarmor','CT'),advance(539),inspect(),advance(1),repair('actor',actor=200,values={'location':1000}),cmd('manifest')])
    yield Case('workflows/01-01',d).result(ok=True).expect('results.2.units.u.sections.4.internal',9).expect('results.6.units.u.sections.4.armor',9).expect('state.units.u.sections.4.internal',10).expect('state.units.u.sections.4.armor',10).expect('state.economy.objects.1000.ECONPARTS','').expect('state.repair_jobs',[])
    u=unit();gun(u,fire_mode=1)
    d=doc(u,characters=[actor(location=1000)],actions=[cmd('Raddstuff','IS.SRM-6 1'),repair('actor',actor=200,values={'location':10}),cmd('replacegun','0'),cmd('repairs'),advance(7199),inspect(),advance(1),inspect()])
    yield Case('workflows/01-02',d).result(ok=True).result(2,ok=True).expect('results.5.units.u.sections.4.slots.2.firemode',1).expect('state.units.u.sections.4.slots.2.firemode',0).expect('state.units.u.sections.4.slots.3.firemode',0).expect('state.economy.objects.1000.ECONPARTS','').expect('state.repair_jobs',[])
    u=unit();setslot(u,4,2,ammo='IS.SRM-6',data=15)
    d=doc(u,actions=[cmd('unload','CT 3'),advance(600),inspect(),cmd('reload','CT 3'),advance(599),inspect(),advance(1),inspect()])
    yield Case('workflows/01-03',d).result(ok=True).expect('results.2.economy.objects.1000.ECONPARTS',stocks((517,0,1))).expect('results.2.units.u.sections.4.slots.2.data',0).expect('results.5.units.u.sections.4.slots.2.data',0).expect('state.units.u.sections.4.slots.2.data',15).expect('state.economy.objects.1000.ECONPARTS','').expect('state.repair_jobs',[])
    d=hangar();u=d['units'][0];u['started']=False;u['profile']='sparse';setslot(u,0,4,type=HEATSINK);d['repair_economy']['objects'][0]['ECONPARTS']=''
    d['actions']=[cmd('removepart','LA 5'),advance(2399),inspect(),advance(1),inspect(),cmd('removesection','LA'),advance(7199),inspect(),advance(1),inspect(),cmd('startup'),advance(30),cmd('loadcargo','HeatSink 1'),inspect()]
    yield Case('workflows/01-04',d).result(ok=True).expect('results.2.economy.objects.1000.ECONPARTS','').expect('results.4.economy.objects.1000.ECONPARTS',stocks((HEATSINK,0,1))).expect('results.7.units.u.sections.0.internal',10).expect('results.9.units.u.sections.0.internal',0).expect('state.economy.objects.10.ECONPARTS',stocks((HEATSINK,0,1))).expect('state.economy.objects.1000.ECONPARTS',stocks((INTERNAL,0,10),(ARMOR,0,10),(ELECTRIC,0,5)))
    yield Journey('workflows/01-05','armor');yield Journey('workflows/01-06','fake');yield InventoryJourney()
    d=tow_doc();d['map']['size']=[50,50];d['units'][0]['at']=[25,25,0];d['units'][1]['at']=[25,25,0]
    d['actions']=[cmd('pickup','01'),cmd('speed','30'),advance(60),inspect(),cmd('dropoff'),inspect(),advance(60),inspect()]
    c=Case('workflows/01-08',d).result(ok=True).expect('results.3.units.u.at.1',25,'less').expect('results.3.units.v.at','results.3.units.u.at','same_as').expect('state.units.v.at','results.5.units.v.at','same_as').expect('state.units.u.at.1', 'results.3.units.u.at.1','same_as')
    # Continued tower movement is compared separately from stationary released cargo.
    c.checks.pop();c.expect('state.units.u.at','results.3.units.u.at','different_from').expect('state.units.u.at.1',25,'less').expect('state.units.u.repair.carrying',-1).expect('state.units.v.status',0x4000,'not_bit');yield c
    yield OriginalJourney()
    d=original();d['actions'] +=[op('configure',unit='u',values={'started':True}),op('aero_configure',unit='u',values={'landed':False,'z':10,'fz':640,'speed':40,'vertical_speed':5,'fuel':0}),damage('Engine',20),diag('fixable'),op('aero_diagnose',unit='u',kind='control'),cmd('weaponstatus'),inspect(),advance(2),inspect(),advance(1),inspect()]
    c=Case('workflows/01-10',d).result(ok=True).expect('results.5',True).expect('results.8.units.u.speed',0).expect('results.8.units.u.vertical_speed',0).expect('results.10.units.u.at.2',10).expect('state.units.u.at.2',8).final(si=0,max_speed=0,fallen=True,destroyed=False).expect('state.units.u.sections.5.armor',0).expect('state.events',dict(kind='FALL',deadline=6,data2=-2),'has').expect('state.units.u.weapons.9.usable',True);yield c
    d=tow_doc();d['units'][1].update({'class':'MW','tonnage':1,'measured_mass':1024});d['actions']=[inspect(),cmd('pickup','01'),inspect()]
    yield Case('workflows/01-11',d).result(1,ok=True).expect('state.characters.201.location',10).expect('state.characters.201.categories.health','results.0.characters.201.categories.health','same_as').expect('state.units.u.repair.carrying',-1)
    u=unit(profile='sparse',sections=[],num_sinks=10,tonnage=50);u['core'].update(max_speed=0,engine_rating=0)
    d=doc(u,actions=[cmd('cost'),repair('configure_object',values={'id':10,'ECONPARTS':''}),cmd('cost')])
    yield Case('workflows/01-12',d).expect('results.2','results.0','same_as').expect('results.0.result.value',705000).expect('state.economy.objects.10.ECONPARTS','')
