"""Original design flight, actual combat, bombing and shared-owner preservation."""
from six_support import *
from six_layout import original_checks,RoundTrip

def person(ident=110,location=10):
    return dict(id=ident,name='Pilot'+str(ident),location=location,connected=True,values={'Build':5,'Reflexes':4,'Intuition':3,'Learn':2,'Charisma':1,'Piloting-Aerospace':6,'Piloting-Spacecraft':6,'Piloting-Biped':6,'Piloting-VTOL':6,'Gunnery-Laser':7,'Gunnery-Missile':7})

def original(reference='CHP-W5'):
    d=load(reference);d['config']['periodic_updates']=True;d['characters']=[person()];d['actions'] += [inspect(),op('personnel',unit='u',kind='attach',player=110)]
    return d

def launch_actions(unit='u'):
    return [cmd('startup',unit=unit),advance(30),cmd('speed','60',unit=unit),advance(10),cmd('takeoff',unit=unit),advance(10),inspect(),advance(1),inspect()]

def ordinary_flight():
    d=original();d['actions'] += launch_actions()+[cmd('heading','90'),cmd('thrust','40'),cmd('climb','0'),cmd('dive','0'),advance(6),inspect(),cmd('checklz'),cmd('land'),inspect()]
    c=Case('workflows/01-02',d).result(ok=True).expect('results.1.units.u.si',0).expect('results.1.units.u.destroyed',False).expect('results.9.units.u.aerospace.landed',True).expect('results.11.units.u.aerospace.landed',False)
    c.expect('results.11.units.u.at',[50,49,1]).expect('results.17.units.u.at',[51,49,0])
    c.expect('results.17.units.u.fuel',729,'less').expect('results.17.units.u.start_fx',0,'greater').expect('results.17.units.u.fx',14151,'greater')
    c.final(**{'aerospace.landed':True,'at.2':0,'fz':0,'start_fx':0,'start_fy':0,'start_fz':0,'speed':0,'vertical_speed':0,'si':0,'template_ref':'CHP-W5'})
    yield c

def combat_originals():
    d=original();d['units'][0]['at']=[50,54,0]
    d['units'].append(craft(name='target',id=20,contact_id='BB',team=2,at=[50,46,0],facing=180))
    d['characters'].append(person(120,20))
    d['actions'] += [op('template',unit='target',kind='load',reference='CHP-W5'),op('personnel',unit='target',kind='attach',player=120),cmd('startup'),cmd('startup',unit='target'),advance(30),cmd('heading','180',unit='target'),cmd('speed','60'),cmd('speed','60',unit='target'),advance(10),cmd('takeoff'),cmd('takeoff',unit='target'),advance(11),cmd('climb','0'),cmd('climb','0',unit='target'),inspect(),cmd('lock','BB'),cmd('fire','0 BB'),inspect(),cmd('fire','2 BB'),inspect(),cmd('fire','4 BB'),inspect(),op('template',unit='u',kind='save',reference='combat-copy',clock=0),op('template',unit='u',kind='read',reference='combat-copy')]
    d['random']['streams'].update(hit_location_rolls=[7,3,3,3,7,7,7,7,7,7],crittable_chance=[22,6],fighter_weapon_choice=[0]*20)
    c=RoundTrip('workflows/01-03','none');c.doc=d
    c.expect('results.17.units.u.aerospace.landed',False).expect('results.17.units.target.aerospace.landed',False)
    for i in (19,21,23):c.expect(f'results.{i}.accepted',True).expect(f'results.{i}.attack.hit',True)
    c.final(shots_fired=3).expect('state.units.u.sections.3.slots.0.data',7).expect('state.units.u.sections.3.slots.4.data',14).expect('state.units.u.weap_heat',0,'greater')
    c.final(weap_heat=12)
    for i,armor in ((20,19),(22,4),(24,0)):c.expect(f'results.{i}.units.target.sections.0.armor',armor)
    c.expect('state.units.target.sections.3.armor',22).expect('results.22.units.target.sections.0.slots.0.firemode',1).expect('results.22.units.target.sections.0.slots.1.firemode',0)
    for mount,cooldown in ((0,40),(2,50),(4,30)):
        c.expect(f'state.units.u.weapons.{mount}.critical',mount).expect(f'state.units.u.weapons.{mount}.section',0).expect(f'state.units.u.weapons.{mount}.recycle',cooldown)
    for i,amount in ((19,5),(21,15),(23,12)):c.expect(f'results.{i}.attack.damage_dealt',amount)
    yield c

def damage_originals():
    d=original();d['actions'] += [damage('Left_Wing',20),inspect(),damage('Left_Wing',5),inspect(),damage('Cockpit',1),inspect()]
    c=Case('workflows/01-04',d).result(ok=True).expect('results.4.units.u.sections.1.armor',0).expect('results.4.units.u.sections.3.armor',30).expect('results.6.units.u.sections.3.armor',25).final(pilot_hits=1,destroyed=False).expect('state.units.u.sections.4.armor',15)
    yield c

def bombing_original():
    d=original();d['actions'] += [edit('addbomb','Bomb_10_Standard F 12')]+launch_actions()+[advance(5),cmd('bomb','list'),cmd('bomb','aim'),cmd('bomb','drop 1'),inspect(),advance(3),inspect(),advance(1),inspect()]
    # A stationary recipient beneath the normal vertical ascent, outside taxi path.
    target=fighter(name='target',id=20,team=2,at=[50,49,0]);d['units'].append(target)
    c=Case('workflows/01-05',d).result(ok=True).result(3,ok=True)
    c.expect('results.14.rows',1,'length').result(15,ok=True).result(16,ok=True,scheduled=True)
    c.expect('results.17.units.u.sections.3.slots.11.type',0).expect('results.17.units.u.carried_cargo',0)
    c.expect('results.12.units.u.carried_cargo',1020).expect('results.16.due',60)
    c.expect('results.17.events',dict(kind='ARTILLERY_HIT',deadline=60,bomb=dict(map=1000,x=50,y=49,index=2)),'has_record')
    c.expect('results.19.events',['ARTILLERY_HIT',1],'event_count').expect('results.21.events',['ARTILLERY_HIT',0],'event_count')
    c.expect('results.19.units.target.sections.3.armor',30).expect('results.21.units.target.sections.3.armor',0).expect('results.19.units.target.destroyed',False).expect('results.21.units.target.destroyed',True)
    yield c

def regressions():
    for ref in ('DS.Union','Cavalry'):
        d=original(ref);d['actions'] += [cmd('startup'),advance(30),cmd('takeoff'),advance(301 if ref=='DS.Union' else 1)]
        d['actions'] += [cmd('vertical','0') if ref=='Cavalry' else cmd('climb','90'),cmd('land')]
        c=Case('workflows/01-06/'+ref,d).result(ok=True).final(template_ref=ref,**{'aerospace.landed':True})
        yield c
    from aerospace_workflows import template_workflows,workflows
    for old in template_workflows():
        if old.name=='procedures/catalog-MECH-bay':
            c=Case('workflows/01-06/WVR-6R-bay',old.doc);c.checks=old.checks;yield c
    for old in workflows():
        if old.name in ('workflows/01-09','workflows/01-10','workflows/01-11'):
            c=Case('workflows/01-06/'+old.name.rsplit('/',1)[1],old.doc);c.checks=old.checks;yield c

def additional():
    from six_weapons import pair
    d=pair();d['units'][1]['started']=False
    d['actions']=[cmd('lock','BB'),cmd('aim','Cockpit'),cmd('fire','0 BB')]
    d['random']['streams']['hit_location_rolls']=[7]*10
    yield Case('procedures/aimed-cockpit-hit',d).result(accepted=True).result(1,accepted=True).result(2,accepted=True).expect('results.2.attack.hit',True).expect('results.2.attack.location',4).expect('state.units.target.sections.4.armor',11).expect('state.units.target.pilot_hits',1)
    d=session(fighter(character=110,in_character=True),[damage(4,1)],characters=[person()])
    yield Case('procedures/IC-cockpit-injury',d).final(destroyed=False,pilot_hits=1).expect('state.characters.110.alive',True).expect('state.characters.110.location',10).expect('state.characters.110.categories.health','10,0')
    old=next(combat_originals());d=old.doc;d['actions'] += [cmd('brief','C 0'),cmd('contacts')]
    yield Case('procedures/original-contacts',d).result(28,ok=True).text('results.28.message','Movement: FLY').expect('results.28.contacts',1,'length')

def workflows():
    yield RoundTrip('workflows/01-01','none')
    yield from ordinary_flight();yield from combat_originals();yield from damage_originals();yield from bombing_original();yield from regressions();yield from additional()
