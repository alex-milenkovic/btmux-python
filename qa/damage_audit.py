"""Additional damage, ammunition and input-boundary assertions."""
from damage_support import *

def cases():
    for first in (0,3):
        d=document('GROUND');mount(d,'autocannon',critical=first);d['random']['streams']['vehicle_weapon_weight']=[10]
        d['actions']=[diag('main-weapon-destroy')]
        yield Case(d,lambda o,first=first:eq(flag(sl(o,4,first)['firemode'],1),first==3),label=f'vehicle_effects-audit-main-order-{first}')
    for rounds in (0,2):
        d=document();mount(d,'missile',rounds=rounds,metadata={'crits':6});section(d,4,slots=[dict(index=0,firemode=0x40)])
        d['random']['streams']['enhanced_rolls']=[2];d['actions']=[diag('slot',attacker='enemy')]
        yield Case(d,lambda o,rounds=rounds:checks((state(o)['sections'][4]['internal'],95 if rounds else 100),(flag(sl(o)['firemode'],1),bool(rounds))),label=f'components-audit-hotload-{rounds}')
    for recycling,matching in [(False,True),(True,False),(True,True)]:
        d=document();mount(d,'autocannon',rounds=2);section(d,4,slots=[dict(index=0,ammomode=0x8000,data=20 if recycling else 0)]);section(d,2)['slots'][0]['ammomode']=0x8000 if matching else 0
        d['random']['streams']['enhanced_rolls']=[2];d['actions']=[diag('slot',attacker='enemy')]
        boom=recycling and matching
        yield Case(d,lambda o,boom=boom:checks((state(o)['sections'][4]['internal'],95 if boom else 100),(flag(sl(o)['firemode'],1),boom)),label=f'components-audit-incendiary-{recycling}-{matching}')
    for unit_class in ('MECH','BSUIT','GROUND'):
        d=document(unit_class);mount(d,'IS.GaussRifle');section(d,4);d['actions']=[diag('slot',attacker='enemy')]
        yield Case(d,lambda o,unit_class=unit_class:checks((state(o)['sections'][4]['internal'],80),(state(o)['pilot_hits'],0 if unit_class=='BSUIT' else 2),(state(o,'enemy')['damage_inflicted'],20)),label=f'components-audit-gauss-{unit_class}')
    d=document();mount(d,'IS.Anti-MissileSystem');d['units'][0].update(status=0x2800,specials=4);d['random']['streams']['enhanced_rolls']=[2];d['actions']=[diag('slot')]
    yield Case(d,lambda o:checks((state(o)['status']&0x800,0),(state(o)['specials']&4,0)),label='components-audit-ams-shutdown')
    d=document();mount(d,'autocannon',rounds=10,metadata={'special':0x400000});d['actions']=[diag('slot',section=2,slot=8,attacker='enemy')]
    yield Case(d,lambda o:checks((sl(o,2,8)['data'],10),(state(o)['sections'][2]['internal'],100)),label='components-audit-noboom')
    for condition,expected in [(0,-3),(1,-2),(2,-2)]:
        d=document();mount(d,section_index=0);mount(d,section_index=1);section(d,1,slots=[dict(index=0,data=20,firemode=condition)])
        d['actions']=[diag('weapon-count',section=1),diag('weapon-type',section=1,ordinal=1)]
        yield Case(d,lambda o,expected=expected:eq(o['results'],[1,expected]),label=f'commands-audit-nonfunctional-ordinal-{condition}')
    d=document('VTOL');d['units'][0].update(desired_speed=60,max_speed=64.5)
    d['actions']=[diag('effect',name='tail_rotor_damaged'),inspect(),cmd('speed','run'),diag('effect',name='tail_rotor_damaged')]
    yield Case(d,lambda o:checks((o['results'][2]['ok'],False),(state(o)['desired_speed'],state(o,index=1)['desired_speed'])),label='vehicle_effects-audit-tail-rotor-repeat')
    for feed,weapon,mode in [(8,'autocannon','armorpiercing'),(8,'missile','artemis')]:
        d=document();mount(d,weapon,metadata={'crits':6});d['actions']=[diag('enhanced',roll=feed),cmd('ammo',0,mode)]
        yield Case(d,lambda o:checks((o['results'][1]['success'],False),(o['results'][1]['messages'],["That weapon's ammo feed mechanism is damaged!"])),label=f'enhanced-audit-induced-feed-{weapon}')

_behavior_cases=cases
def cases():
    yield from _behavior_cases()
    for field,values in [('aim',(-1,9,1.5,True)),('aim_type',(-1,99,True)),('measured_mass',(-1,True))]:
        for value in values:
            d=document();d['units'][0][field]=value;d['actions']=[inspect()]
            yield Case(d,lambda o:None,invalid=True,label=f'commands-audit-invalid-{field}-{value}')
