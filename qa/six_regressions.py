"""Additional explicit procedure controls through public commands/diagnostics."""
from six_support import *
from six_workflows import original
from six_weapons import pair

def extras():
    d=pair();d['units'][1]['facing']=0;d['random']['streams']['hit_location_rolls']=[5]
    d['actions']=[cmd('fire','0 BB')]
    yield Case('procedures/back-roll5-real-hit',d).result(accepted=True).expect('results.0.attack.location',2).expect('results.0.attack.is_rear',True).expect('state.units.target.sections.2.armor',15).expect('state.units.target.sections.3.armor',25)
    u=fighter(weapons=[dict(name='IS.MediumLaser',section=0)])
    yield Case('procedures/physical-weapon-critical',session(u,[dd('slot',section=0,slot=0)],random=dict(streams={**finite(),'enhanced_rolls':[12]}))).expect('state.units.u.sections.0.slots.0.firemode',1).expect('state.units.u.weapons.0.usable',False)
    u=fighter();u['sections'][0]['slots']=[dict(index=0,ammo='IS.SRM-2',data=1)];u['sections'][0]['armor']=3
    yield Case('procedures/physical-ammo-critical',session(u,[dd('slot',section=0,slot=0,attacker='u')])).expect('state.units.u.sections.0.slots.0.firemode',1).expect('state.units.u.sections.0.armor',0).expect('state.units.u.sections.3.armor',29)
    # An original Mech still applies excess through internals and transfers to
    # its side torso, and its physical head laser recycles and fires again.
    d=original('WVR-6R');d['units'].append(craft(kind='MECH',name='target',id=20,contact_id='BB',team=2,at=[50,47,0]))
    d['config']['periodic_updates']=True;d['random']['streams']['visibility_change']=[40]*100
    d['actions'] += [cmd('startup'),advance(40),cmd('lock','BB'),cmd('fire','2 BB'),inspect(),advance(40),inspect(),cmd('fire','2 BB'),damage(0,30),inspect()]
    c=Case('workflows/01-06/WVR-6R-combat',d).result(ok=True).result(6,accepted=True).result(10,accepted=True)
    c.expect('results.7.units.u.sections.7.slots.3.data',40).expect('results.9.units.u.sections.7.slots.3.data',0).final(shots_fired=2)
    c.expect('state.units.u.sections.0.armor',0).expect('state.units.u.sections.0.internal',0).expect('state.units.u.sections.2.armor',15).expect('state.units.u.sections.2.internal',13)
    yield c

    d=original('WVR-6R');d['units'][0]['in_character']=True;d['actions'].append(damage(7,1))
    yield Case('procedures/shared-Mech-head-injury',d).final(pilot_hits=1,destroyed=False).expect('state.characters.110.categories.health','10,0')
