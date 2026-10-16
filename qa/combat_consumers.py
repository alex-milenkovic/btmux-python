"""Cross-system combat consumers exercised at the documented user boundary."""
from combat_support import *

def cases():
    # Keep existing Damage success checks for the affected shared consumers.
    import damage_lifecycle
    for old in damage_lifecycle.cases():
        if not old.label.startswith(('failures-supp-live-percent','destruction-supp-stackpole')):continue
        d=deepcopy(old.document)
        for action in d['actions']:
            if action.get('name')=='target':action['name']='lock'
        yield Case(d,old.check,label=('impacts-' if old.label.startswith('failures') else 'integration-')+old.label,mode='normal' if old.label.startswith('failures') else 'diagnostic',blocked=old.blocked,note=old.note)
    for name in ('IS.LR_DFM-20','CL.ATM-12'):
        d=fixture(False);mount(d,'IS.LRM-20',crits=1,source_name=name);d['actions']=[diag('artillery-launch',weapon=0,x=3,y=1)]
        yield Case(d,lambda o:eq(any('shoots a missile' in m for m in state(o,'v')['messages']),True),label='artillery-raw-arrow-index-'+name)
    for duration in (90,150):
        d=fixture(False);mount(d,'IS.Sniper',mode=32|16,crits=1);d['random']['streams']['smoke_duration']=[duration,duration];d['actions']=[diag('artillery-launch',weapon=0,x=4,y=4),advance(10),advance(5),diag('artillery-launch',weapon=0,x=4,y=4),advance(10),advance(duration-1),inspect(),advance(1)]
        yield Case(d,lambda o:checks((len(o['results'][-2]['map']['decorations']),1),(o['state']['map']['decorations'],[]),(len(draws(o,'smoke_duration')),2)),label=f'artillery-smoke-replacement-duration-{duration}')
    d=fixture(False);mount(d,'IS.Sniper',mode=16,damage=10,crits=1);d['actions']=[diag('artillery-launch',weapon=0,x=4,y=4),diag('artillery-launch',weapon=0,x=4,y=4),advance(10)]
    yield Case(d,lambda o:eq([m['strength'] for m in o['state']['map']['mines']],[10]),label='artillery-duplicate-center-mines')
    for requirement in (0,1):
        for underground in (False,True):
            for blocked in (False,True):
                d=fixture(False);mount(d,'IS.LRM-5',ammo=10,range_min=0,crits=1);d['config']['idf_requires_spotter']=requirement;d['map']['flags']=16 if underground else 0
                d['units'][1]['at']=[3,1,0];d['units'][0]['target']=2
                if blocked:d['map']['hexes']=[dict(at=[3,2],terrain='BUILDING',elevation=9)]
                d['random']['streams'].update(attack_rolls=[12],missile_pre_roll=[3]*3,missile_cluster=[12]);d['actions']=[cmd('fire','0')]
                allowed=not blocked or not requirement and not underground
                yield Case(d,lambda o,allowed=allowed:checks((o['results'][0]['accepted'],allowed),(len(draws(o,'attack_rolls')),int(allowed)),(rounds(o),10-int(allowed))),label=f'firing-IDF-require{requirement}-underground{underground}-blocked{blocked}',mode='normal')
    for control in (0,1):
        d=fixture(False);d['units'][0].update(**{'class':'AERO'},unusable_arcs=control);mount(d,loc=0,crits=1);d['random']['streams']['attack_rolls']=[12];d['actions']=[cmd('fire','0')]
        yield Case(d,lambda o,control=control:checks((o['results'][0]['accepted'],not control),(loss(o),0 if control else 5)),label=f'firing-aero-assigned-control-{control}',mode='normal')
    for actor in ('MECH','AERO'):
        d=fixture(False);mount(d);d['units'][0]['class']=actor;d['units'][1].update(**{'class':'AERO'},speed=32.25,vertical_speed=43);d['actions']=[diag('combat-bth',weapon=0,target='v')]
        yield Case(d,lambda o,actor=actor:eq(o['results'][0]['target_move'],0 if actor=='AERO' else 2),label='bth-aero-vector-'+actor)
    for jumping in (False,True):
        d=fixture(False);mount(d);d['units'][1].update(**{'class':'BA'},swarm_target='host');d['units'].append(dict(name='host',at=[3,2,0],speed=64.5,jump_mp=3,status=8|64 if jumping else 8));d['actions']=[diag('combat-bth',weapon=0,target='v')]
        yield Case(d,lambda o,jumping=jumping:eq(o['results'][0]['target_move'],1 if jumping else 2),label=f'bth-swarm-host-speed-jumping{jumping}')
    for name,category,outcome,spent,temp in [('IS.MediumLaser',0,5,0,2),('IS.AC/5',6,3,1,1),('IS.AC/5',6,2,1,3),('IS.StreakSRM-6',12,5,0,2)]:
        d=fixture(False);m=mount(d,name,ammo=10 if category else None,crits=1,fire=64 if category==12 else 0);m['brand']=1
        d['random']['streams'].update(attack_rolls=[2],failure_weapon_chance=[9],failure_reliability=[100],failure_outcome=[outcome],failure_weapon_recycle=[20],failure_dud_recycle=[20]);d['actions']=[cmd('fire','0')]
        yield Case(d,lambda o,category=category,spent=spent,temp=temp:checks((rawslot(o)['temp_failure'],temp),(rounds(o),10-spent if category else 0),(state(o)['weap_heat'],0.0)),label=f'impacts-brand-before-risky-{category}-{outcome}',mode='normal')
    for mass,modifier in [(35,2),(36,1),(55,1),(56,0),(75,0),(76,-1)]:
        for passed in (False,True):
            d=fixture(False);d['units'][0].update(tonnage=mass,speed=1,piloting=5);mount(d,'IS.HeavyGaussRifle',ammo=10,crits=1);rolled=5+modifier-(not passed)
            d['random']['streams'].update(attack_rolls=[12],pilot_rolls=[rolled]+[12]*20);d['actions']=[cmd('fire','0')]
            yield Case(d,lambda o,passed=passed:checks((state(o)['fallen'],not passed),(rounds(o),9)),label=f'impacts-gauss-recoil-mass{mass}-pass{passed}',mode='normal')
    for transferred in (False,True):
        d=fixture(False);mount(d,'IS.PlasmaRifle',damage=10,crits=1);d['random']['streams'].update(hit_location_rolls=[10],plasma_heat=[4,5]);
        if transferred:section(d,0,unit=1,armor=0,internal=1)
        d['actions']=[diag('combat-attack',weapon=0,target='v',roll=12)]
        yield Case(d,lambda o,transferred=transferred:checks((draws(o,'plasma_heat'),[4,5] if transferred else [4]),(state(o,'v')['weap_heat'],9.0 if transferred else 4.0)),label=f'impacts-plasma-transfer-draw-{transferred}')
    for terrain in ('ICE','BRIDGE'):
        for rolled in (5,6):
            d=fixture(False);mount(d,damage=5);d['map']['hexes']=[dict(at=[4,4],terrain=terrain,elevation=1)];d['random']['streams'].update(surface_draws=[rolled],terrain_rolls=[7,6,12]);d['actions']=[cmd('lock','4','4','H'),diag('terrain-hit',weapon=0,x=4,y=4)]
            yield Case(d,lambda o,terrain=terrain,rolled=rolled:checks((next(h['terrain'] for h in o['state']['map']['hexes'] if h['at']==[4,4]),'~' if rolled==5 else '/' if terrain=='BRIDGE' else '-'),(draws(o,'surface_draws'),[rolled])),label=f'terrain-live-hex-{terrain}-{rolled}')
    for water in (False,True):
        d=fixture();d['units'][1]['at']=[8,8,0];d['map']['mines']=[dict(x=3,y=3,type='Inferno',strength=12)]
        if water:d['map']['hexes']=[dict(at=[3,2],terrain='WATER',elevation=-2)]
        d['actions']=[cmd('prone'),inspect()]+([cmd('stand'),advance(12),cmd('speed','64.5'),advance(20)] if water else [advance(1),inspect(),advance(5)])
        def check(o,water=water):
            eq(bool(state(o,index=1)['crit_status']&4194304),True)
            eq(bool(state(o)['crit_status']&4194304),not water)
            if not water:eq(state(o)['minus_heat'],4.0)
        yield Case(d,check,label=f'integration-inferno-mine-heat-water{water}',mode='normal')
    for name in ('masc','scharge'):
        for other in (False,True):
            for sprint in (False,True):
                d=fixture(False);u=d['units'][0];u.update(specials=16,specials2=64,status=8|(33554432 if name=='masc' else 1048576) if other else 8,status2=65536 if sprint else 0)
                needed=2+(int(other) if name=='scharge' else 0)+2*int(sprint);d['random']['streams']['booster_rolls']=[12];d['actions']=[diag('combat-callback',name='booster',data=name)]
                yield Case(d,lambda o,name=name,other=other,needed=needed:checks((state(o)['masc_counter'],1),(any(f'BTH {needed+1}' in m and f'Roll: {12-int(other)}' in m for m in state(o)['messages']),True)),label=f'boosters-status-words-{name}-other{other}-sprint{sprint}')
    for name in ('masc','scharge'):
        d=fixture(False);d['units'][0].update(specials=16,specials2=64,pilot_wizard=True);d['random']['streams'].update(booster_rolls=[2],booster_wizard=[3]);d['actions']=[cmd(name),advance(1)]
        yield Case(d,lambda o:checks((draws(o,'booster_rolls'),[2]),(draws(o,'booster_wizard'),[3]),(state(o)['specials']&16,16),(state(o)['specials2']&64,64)),label='boosters-pilot-wizard-'+name,mode='normal')
