"""Live consequences and repeated lifecycle boundary checks."""
from damage_support import *

def cases():
    # All enhanced severity breakpoints, including pre-existing damaged slots.
    for kind in ('energy','missile','autocannon','IS.Thumper','unsupported'):
        for damaged in (0,1,3):
            for roll in range(2,13):
                d=document();mount(d,'energy' if kind=='unsupported' else kind,metadata={'crits':6,**({'weapon_type':4} if kind=='unsupported' else {})});section(d,4,slots=[dict(index=i,firemode=8,weap_damage_flags=1) for i in range(1,damaged+1)])
                d['actions']=[diag('enhanced',roll=roll)]
                severity=roll+damaged+1;destroy=damaged==3 or severity>=10
                if kind=='unsupported':destroy=True
                flags=0 if severity<=3 or destroy else 1 if severity<=5 else (2 if kind=='energy' else 32 if kind=='missile' else 8) if severity<=7 else (4 if kind=='energy' else 64 if kind=='missile' else 16)
                yield Case(d,lambda o,flags=flags,destroy=destroy:checks((flag(sl(o)['firemode'],1),destroy),(sl(o)['weap_damage_flags'],flags)),label=f'enhanced-supp-severity-{kind}-{damaged}-{roll}')
    for kind,roll,field,expected in [('energy',4,'bth',1),('energy',6,'damage',1),('energy',8,'heat',1),('autocannon',6,'bth',1),('missile',6,'bth',1)]:
        for distance in (3,4):
            d=document();fire_setup(d,kind,rounds=20 if kind!='energy' else None,metadata={'crits':6,'damage':10,'heat':5,'range_short':3},distance=distance)
            d['actions'] += [diag('enhanced',roll=roll),diag('weapon-modifiers',range_bracket=int(distance>3)),cmd('fire',0)]
            def check(o,field=field,distance=distance,kind=kind):
                modifier=0 if kind=='autocannon' or kind=='missile' and distance==3 else 1
                eq(o['results'][-2][field],modifier)
                attack=o['results'][-1]['attack'];eq(attack['shot_aborted'],False)
                if field=='bth':eq(attack['critical_bth'],modifier)
                if kind=='energy':checks((attack['damage_dealt'],9 if field=='damage' else 10),(state(o)['weap_heat'],6 if field=='heat' else 5))
            yield Case(d,check,label=f'enhanced-supp-induced-live-{kind}-{roll}-{distance}')
    for kind,category,outcome,temp,delay in [('energy',0,5,2,20),('autocannon',6,3,1,20),('autocannon',6,2,3,50),('missile',12,5,2,20)]:
        d=document();fire_setup(d,kind,rounds=10 if kind!='energy' else None)
        d['random']['streams'].update(failure_weapon_recycle=[20],failure_dud_recycle=[20])
        d['actions'] += [diag('failure',category=category,outcome=outcome),advance(delay-1),cmd('fire',0),inspect(),advance(1),cmd('fire',0)]
        def check(o,temp=temp):checks((o['results'][-4]['ok'],False),(sl(o,index=len(o['results'])-3)['temp_failure'],temp),(o['results'][-1]['ok'],True))
        yield Case(d,check,label=f'recovery-supp-fire-retry-{kind}-{outcome}')
    for kind,outcome,expected in [('energy',1,17),('energy',2,14),('energy',3,11),('missile',2,1),('missile',3,2),('missile',4,5)]:
        d=document();fire_setup(d,kind,brand=1,rounds=10 if kind=='missile' else None,metadata={'damage':20})
        d['random']['streams'].update(failure_weapon_chance=[9],failure_reliability=[100],failure_outcome=[outcome],missile_cluster=[12],cluster_rolls=[12])
        d['actions'].append(cmd('fire',0))
        def check(o,expected=expected,kind=kind):
            attack=o['results'][-1]['attack'];eq(attack['damage_dealt'],expected)
            if kind=='missile':eq(sl(o,2,8)['data'],9)
        yield Case(d,check,label=f'failures-supp-live-percent-{kind}-{outcome}')
    for exhausted in (False,True):
        d=document();fire_setup(d,'IS.NarcBeacon',rounds=10)
        d['units'][1]['sections'][4]['internal']=0 if exhausted else 100
        d['units'][1]['sections'][0]['internal']=0
        d['random']['streams']['hit_location_rolls']=[10]
        if exhausted:d['units'][1]['sections'][2]['internal']=0
        d['actions'].append(cmd('fire',0))
        def check(o,exhausted=exhausted):eq([i for i,s in enumerate(state(o,'enemy')['sections']) if s['specials']&1],[] if exhausted else [2])
        yield Case(d,check,label=f'locations-supp-narc-attach-{exhausted}')
    for elapsed in (30,31):
        for roll in (8,9):
            for started in (False,True):
                d=document();u=d['units'][0];u.update(started=started,engine_heat=10);section(d,4,armor=0);section(d,2,slots=[special('ENGINE')])
                d['random']['streams'].update(stackpole_rolls=[roll],hit_location_rolls=[7]*100,physical_location=[1]*100)
                d['actions']=[advance(5),diag('damage',amount=1,section=4,attacker='enemy'),advance(elapsed),diag('destroy-parts',section=2,attacker='enemy')]
                boom=elapsed==30 and roll==9 and started
                def check(o,boom=boom):eq(notices(state(o),'releasing the fusion reaction'),int(boom))
                yield Case(d,check,label=f'destruction-supp-stackpole-{elapsed}-{roll}-{started}',blocked='B1: reactor ejection cannot create a persistent character.' if boom else '')

_base=cases
def cases():
    yield from _base()
    for disabled in (False,True):
        d=document();section(d,2,slots=[special('HEAT_SINK')]);d['units'][0]['num_sinks']=10
        d['actions']=[diag('destroy-parts',section=2,disable=disabled),inspect(),diag('destroy-parts',section=2),inspect(),diag('destroy-parts',section=2)]
        def check(o,disabled=disabled):checks((sl(o,2,index=1)['firemode'],2 if disabled else 1),(state(o)['sink_capacity'],9),(state(o,index=3)['sink_capacity'],9))
        yield Case(d,check,label=f'destruction-supp-disable-then-destroy-{disabled}')
    for dead in (False,True):
        d=document();d['units'][0].update(target=2,in_character=dead);section(d,7,slots=[special('COCKPIT')]);d['actions']=[cmd('speed',20),diag('slot',section=7,attacker='enemy'),diag('slot',section=7,attacker='enemy')]
        yield Case(d,lambda o:checks((state(o)['target'],-1),(state(o)['pilot_present'],False),(events(state(o),'MOVE'),[])),label=f'destruction-supp-cockpit-cleanup-{dead}')
    for original in (0,10):
        d=document();section(d,2,armor=5,armor_orig=original);mount(d,'autocannon',metadata={'damage':10});d['actions']=[diag('damage',section=2,amount=1,weapon=WEAP['autocannon'],ammo_mode=0x2000,attacker='enemy')]
        yield Case(d,lambda o:eq(state(o)['sections'][2]['armor'],4),label=f'armor-supp-ap-original-{original}')
    for roll,salvage in [(5,False),(6,False),(6,True)]:
        d=document();d['units'][0].update(towed_unit='enemy',measured_mass=51200,specials=0x1000 if salvage else 0);d['units'][1]['measured_mass']=51200
        d['random']['streams']['tow_rolls']=[roll];d['actions']=[diag('damage',section=2,amount=1,rear=True,attacker='enemy')]
        yield Case(d,lambda o,roll=roll,salvage=salvage:eq(state(o)['relationships']['towed_unit'] is None,roll==5 and not salvage),label=f'transfer-supp-rear-tow-{roll}-{salvage}')
    d=document();d['units'][0]['status']=0x48002000;section(d,2,armor=1);d['actions']=[diag('damage',section=2,amount=2,attacker='enemy')]
    yield Case(d,lambda o:checks((flag(state(o)['sections'][2]['config'],4),True),(count_draw(o,'breach_rolls'),0)),label='transfer-supp-internal-vacuum-breach')
    for name,bit in [('BEAGLE_PROBE',0x800),('BLOODHOUND_PROBE',0x800),('LIGHT_BAP',0x8000)]:
        d=document();d['units'][0].update(specials=bit,specials2=bit);section(d,4,slots=[special(name)]);d['actions']=[diag('slot')]
        yield Case(d,lambda o,name=name,bit=bit:checks((sl(o)['firemode'],1),(state(o)['specials2' if name=='BLOODHOUND_PROBE' else 'specials']&bit,0)),label=f'components-supp-live-probe-{name}')
    for count in (1,2,12,13):
        d=document();section(d,4,slots=[special('LIFE_SUPPORT',i) for i in range(12)]);d['actions']=[diag('critical',count=count),diag('critical',count=1)]
        yield Case(d,lambda o,count=count:eq(len(destroyed_slots(o,4)),min(12,count+1)),label=f'dispatch-supp-candidate-exhaustion-{count}')
    for condition in (0,1,2,4,8):
        d=document(periodic=True);mount(d);section(d,4,slots=[dict(index=0,firemode=condition,temp_failure=5,data=1)]);d['actions']=[advance(1)]
        yield Case(d,lambda o,condition=condition:eq(sl(o)['temp_failure'],5 if condition in (1,2,4) else 0),label=f'recovery-supp-recycler-condition-{condition}')
    for mass in (25600,76800):
        d=document();d['units'][0].update(measured_mass=mass,max_speed=64.5,template_max_speed=64.5,speed=-100,desired_speed=-100)
        d['actions']=[diag('normalize'),inspect(),diag('normalize')]
        yield Case(d,lambda o:checks((state(o)['max_speed'],state(o,index=1)['max_speed']),(state(o)['speed'],state(o,index=1)['speed']),(abs(state(o)['speed'])<=state(o)['max_speed'],True)),label=f'mobility-supp-cargo-idempotence-{mass}')
