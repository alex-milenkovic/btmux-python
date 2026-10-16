"""Additional ordered consumers required by the independent QA procedure."""
from combat_support import *

def cases():
    for incoming in (1,5,20):
        for enemy in (False,True):
            d=fixture(False);mount(d,'IS.LRM-5',mode=256 if enemy else 128,crits=1);d['units'].append(dict(name='w',at=[3,2,0],team=2,sections=[sec(i) for i in range(8)]))
            d['random']['streams'].update(missile_pre_roll=[3]*6,missile_cluster=[6,6],swarm_rolls=[12])
            d['actions']=[diag('swarm-hit',weapon=0,target='v',bth=7,roll=8,incoming=incoming,enemy_only=enemy,player_roll=12)]
            yield Case(d,lambda o,enemy=enemy:checks((o['results'][0]['swarm_targets'],[2,3 if enemy else 1]),(o['results'][0]['missiles_remaining'],0),(loss(o),3),(loss(o,'w' if enemy else 'u'),2),(draws(o,'swarm_rolls'),[12])),label=f'missiles-chain-incoming{incoming}-enemy{enemy}')
    for limit in ('visited','range','later-miss'):
        d=fixture(False);mount(d,'IS.LRM-20',crits=1,mode=256,range_short=1,range_medium=2,range_long=3 if limit=='range' else 21);d['units'][0]['at']=[3,10,0] if limit=='visited' else [3,3,0]
        for i in range(12 if limit=='visited' else 5):d['units'].append(dict(name='w'+str(i),at=[3,2 if limit=='visited' else i+1,0],team=2,sections=[sec(j) for j in range(8)]))
        d['random']['streams']['swarm_rolls']=[2]*20
        d['actions']=[diag('swarm-hit',weapon=0,target='v',bth=7,roll=2,incoming=1,enemy_only=True)]
        def check(o,limit=limit):
            result=o['results'][0];checks((result['missiles_remaining'],20),(result['damage_dealt'],0),(len(draws(o,'swarm_rolls')),len(result['swarm_targets'])-1))
            if limit=='visited':eq(result['swarm_targets'],list(range(2,13)))
            if limit=='range':assert len(result['swarm_targets'])<7;assert any('fall short' in m for u in o['state']['units'].values() for m in u['messages'])
            if limit=='later-miss':eq(len(result['swarm_targets']),6)
        yield Case(d,check,label='missiles-chain-boundary-'+limit)
    from combat_physical_procedures import fixture as pf
    for arm in ('','L','R','B','bad'):
        d=pf();d['map']['hexes']=[dict(at=[3,3],terrain='LIGHT_FOREST',elevation=0)];d['actions']=[cmd('grabclub',*([arm] if arm else [])),inspect(),cmd('grabclub','-')]
        yield Case(d,lambda o,arm=arm:checks((o['results'][0]['accepted'],arm in ('','L','R')),(state(o,index=1)['sections'][1 if arm=='R' else 0]['specials']&32,32 if arm in ('','L','R') else 0),(sum(s['specials']&32 for s in state(o)['sections']),0)),label='physicals-grab-club-'+(arm or 'default'),mode='normal')
    for held in (0,1):
        for hit in (False,True):
            d=pf(False);section(d,held,specials=32);d['random']['streams']['physical_attack']=[12 if hit else 2];d['actions']=[cmd('club')]
            yield Case(d,lambda o,held=held,hit=hit:checks((loss(o),10 if hit else 0),(state(o)['sections'][0]['recycle'],30),(state(o)['sections'][1]['recycle'],30),(state(o)['sections'][held]['specials']&32,0 if hit else 32)),label=f'physicals-held-club-{held}-hit{hit}',mode='normal')
    for busy in (0,1):
        d=pf(False);section(d,0,specials=32);mount(d,loc=busy,index=4,crits=1);slot(d,busy,4,data=20);d['actions']=[cmd('club')]
        yield Case(d,lambda o:checks((o['results'][0]['accepted'],False),(draws(o,'physical_attack'),[])),label=f'physicals-club-busy-arm-{busy}',mode='normal')
    for arm in ('L','R'):
        for hit in (False,True):
            d=pf(False);d['units'][1].update(**{'class':'BA'},swarm_target='u',at=[3,3,1],real=[1024.0750399750987,935.25,64.5]);d['random']['streams'].update(physical_attack=[12 if hit else 2],pilot_rolls=[12 if hit else 2,12,12],physical_location=[1]*20);d['actions']=[cmd('punch',arm)]
            def check(o,arm=arm,hit=hit):
                eq(o['results'][0]['accepted'],arm=='R')
                if arm=='L':checks((draws(o,'physical_attack'),[]),(loss(o,'u'),0),(loss(o),0))
                elif hit:checks((loss(o),5),(state(o,'v')['relationships']['swarm_target'],None))
                else:checks((loss(o),0),(loss(o,'u'),5))
            yield Case(d,check,label=f'physicals-own-swarmer-{arm}-hit{hit}',mode='normal')
    for reason in ('step','fall','land'):
        for typ in ('Standard','Inferno','Vibra','Command','Trigger'):
            d=fixture();u=d['units'][0];d['units'][1]['at']=[8,8,0];u.update(jump_mp=3,jump_speed=32.25,piloting=0)
            d['map']['mines']=[dict(x=3,y=3 if reason=='fall' else 2,type=typ,strength=4,extra=0)]
            d['actions']=[cmd('prone')] if reason=='fall' else [cmd('jump','0','1'),advance(40)] if reason=='land' else [cmd('speed','64.5'),advance(20)]
            def check(o,typ=typ):
                if typ in ('Standard','Inferno','Vibra'):eq(loss(o,'u'),1 if typ=='Inferno' else 4)
                else:eq(loss(o,'u'),0)
                if typ=='Command':eq(len(o['state']['map']['mines']),1)
                if typ=='Trigger':assert any(not e['applied'] and 'AMINETRIGGER' in e['service'] for e in state(o)['external_effects'])
            yield Case(d,check,label=f'mines-real-{reason}-{typ}',mode='normal',blocked='persistent mine object scripts' if typ=='Trigger' else '')
    for modes,expected in [([262144,262144],None),([0,262144],'red'),([262144,0],'red'),([8192,65536],'red')]:
        d=fixture(False);mount(d,'IS.AC/5',crits=1,ammo_per_ton=40)
        for i,mode in enumerate(modes):slot(d,2,9+i,ammo='IS.AC/5',ammomode=mode,data=5)
        d['actions']=[diag('ammunition-check',weapon=0)]
        yield Case(d,lambda o,expected=expected:eq(o['results'][0]['severity'],expected),label='ammunition-mixed-bin-integer-'+str(modes))
    for cls,terrain,mode,damage in [('MW','CLEAR',16384,20),('MW','LIGHT_FOREST',16384,10),('BA','CLEAR',16384,5),('MECH','CLEAR',16384,2),('MW','CLEAR',32768,7),('BA','CLEAR',32768,5),('MECH','CLEAR',32768,5)]:
        d=fixture(False);mount(d,'IS.AC/5',mode=mode,crits=1);d['units'][1]['class']=cls;d['map']['hexes']=[dict(at=[3,2],terrain=terrain,elevation=0)];d['actions']=[diag('impact-damage',weapon=0,target='v')]
        yield Case(d,lambda o,damage=damage:eq(o['results'][0]['damage'],damage),label=f'impacts-ammo-shaping-{cls}-{terrain}-{mode}')
    for condition in ('on','off','no-internal','jam','no-LOS'):
        d=fixture();u=d['units'][0];u.update(**{'class':'GROUND'},facing=90,turret_facing=45,target=2)
        if condition=='jam':u['tank_crit_status']=2
        if condition=='no-LOS':d['map']['hexes']=[dict(at=[3,2],terrain='BUILDING',elevation=9)]
        d['actions']=[cmd('autoturret')]
        if condition=='off':d['actions'].append(cmd('autoturret'))
        if condition=='no-internal':d['actions'].append(dict(op='section',value=dict(index=4,internal=0)))
        d['actions'].append(advance(2))
        yield Case(d,lambda o,condition=condition:eq(state(o)['turret_facing'],270 if condition in ('on','no-LOS') else 45),label='preferences-autoturret-consumer-'+condition,mode='normal',note='Source turret consumer follows the stored aim point; it has no LOS gate.')
    for distance in (8,20):
        d=fixture();mount(d,range_min=0,range_short=3,range_medium=6,range_long=9);d['map']['size']=[30,30];d['units'][0].update(at=[3,distance+2,0],specials=128,working_c3_masters=1,c3_network=['p']);d['units'].append(dict(name='p',at=[3,3,0],team=0,specials=256));d['random']['streams']['attack_rolls']=[12];d['actions']=[cmd('fire','0')]
        d['random']['streams']['sensor.detect']=[1]*20
        yield Case(d,lambda o,distance=distance:checks((loss(o),5 if distance==8 else 0),(any('Using range data from' in m for m in state(o)['messages']),distance==8)),label=f'integration-C3-range-identity-{distance}',mode='normal')
    d=fixture();d['units'][0]['status']=8|4194304;d['map']['mines']=[dict(x=3,y=2,type='Standard',strength=4)];d['units'][1]['at']=[8,8,0];d['actions']=[cmd('speed','64.5'),advance(20)]
    yield Case(d,lambda o:eq(loss(o,'u'),0),label='integration-safe-environment-mine',mode='normal')
    for critical in (False,True):
        d=fixture(False);d['units'][0].update(at=[3,3,0],facing=180);d['units'][1].update(at=[3,3,0],facing=0)
        d['random']['streams'].update(hit_location_rolls=([2] if critical else [7])+[7]*5,critical_rolls=[2]*20,crittable_chance=[23])
        d['actions']=[diag('blast',x=3,y=3,damage=12,cluster=5,source_real=[1024.0750399750987,935.25])]
        yield Case(d,lambda o,critical=critical:checks((state(o)['sections'][4]['rear'],188),(state(o,'v')['sections'][4]['rear'],188),(len(draws(o,'damage_entry')),6),(len(draws(o,'critical_rolls')),6 if critical else 0)),label=f'blast-cross-unit-persistent-rear-critical-{critical}')
    from combat_physical_procedures import armtech
    for attack in ('punch','axe','kick'):
        for target_cls in ('MECH','GROUND','VTOL'):
            for dz in (-2,-1,0,1,3,4):
                d=pf(False);armtech(d,attack);d['units'][1].update(**{'class':target_cls},at=[3,2,max(dz,0)],real=[1024.0750399750987,935.25,max(dz,0)*64.5]);d['units'][0]['at'][2]=max(-dz,0)
                if target_cls=='VTOL':d['units'][1]['movement']='VTOL'
                d['random']['streams']['physical_attack']=[12];d['actions']=[cmd(attack,'R')]
                accepted=(-1<=dz<=1 and not(attack=='punch' and (dz<0 or target_cls=='GROUND')) and not(attack=='kick' and (dz>0 or dz<0 and target_cls=='GROUND')) and not(attack=='axe' and target_cls=='GROUND' and dz<=0)) if target_cls!='VTOL' else (dz==0 if attack=='kick' else 0<=dz<=3)
                yield Case(d,lambda o,accepted=accepted:checks((o['results'][0]['accepted'],accepted),(len(draws(o,'physical_attack')),int(accepted))),label=f'physicals-Z-eligibility-{attack}-{target_cls}-{dz}',mode='normal')
    d=fixture();mount(d,'IS.RotaryAC/5',ammo=20,crits=1);mount(d,'IS.RotaryAC/5',index=1,crits=1);slot(d,4,temp_failure=6);slot(d,4,1,temp_failure=6);d['random']['streams']['unjam_rolls']=[12];d['actions']=[cmd('unjamammo','0,1'),inspect(),advance(60)]
    yield Case(d,lambda o:checks((len(events(o,kind='UNJAM_AMMO',index=1)),1),(rawslot(o)['temp_failure'],0),(rawslot(o,index=1)['temp_failure'],6),(rounds(o),20)),label='equipment-unjam-unit-wide-multiselector',mode='normal')
    d=fixture(False);mount(d,'IS.CoolantGun',damage=5,crits=1);d['units'][1]['class']='MW';d['actions']=[diag('combat-attack',weapon=0,target='v',roll=12)]
    yield Case(d,lambda o:checks((state(o,'v')['weap_heat'],0.0),(sum(s['internal'] for s in state(o,'v')['sections'])<1600,True)),label='impacts-coolant-MW-damage-consumer')
    for stock in (1,2):
        d=fixture(False);mount(d,'IS.MachineGun',fire=4096,ammo=stock,crits=1);d['random']['streams'].update(gattling_rolls=[6],attack_rolls=[12]);d['actions']=[cmd('fire','0')]
        yield Case(d,lambda o:checks((loss(o),1),(rounds(o),0),(state(o)['weap_heat'],1.0)),label=f'impacts-gattling-minimum-stock-{stock}',mode='normal')
    for inferno in (False,True):
        d=fixture(False);mount(d,'IS.SRM-6' if inferno else 'IS.LRM-20',ammo=10,mode=64 if inferno else 0,crits=1);d['units'][1]['at']=[8,8,0];d['map']['hexes']=[dict(at=[3,1],terrain='HEAVY_FOREST',elevation=0)]
        seq=[7,5,7,5] if inferno else [7,6,6]*4
        d['random']['streams'].update(attack_rolls=[12],missile_pre_roll=[3]*3,missile_cluster=[12],terrain_rolls=seq)
        d['actions']=[cmd('lock','3','1','C'),cmd('fire','0')]
        yield Case(d,lambda o,inferno=inferno,seq=seq:checks((o['results'][1]['accepted'],True),(draws(o,'terrain_rolls'),seq),(rounds(o),9),(len(o['state']['map']['decorations']),int(inferno))),label=f'missiles-real-hex-clusters-inferno{inferno}',mode='normal')
    for decorated in (False,True):
        d=fixture(False);d['units'][0]['at']=[8,8,0];d['units'][1]['at']=[9,9,0];d['map']['hexes']=[dict(at=[3,2],terrain='LIGHT_FOREST',elevation=0,**(dict(overlay='FIRE',duration=20) if decorated else {}))]
        d['actions']=[inspect(),diag('blast',x=3,y=3,damage=12,neighbors=1,neighbor_target_message=None,neighbor_observer_message=None)]
        def check(o,decorated=decorated):
            eq(len(o['state']['map']['decorations']),1)
            if decorated:eq(o['state']['map']['decorations'],o['results'][0]['map']['decorations'])
        yield Case(d,check,label=f'blast-forest-neighbor-existing-fire-{decorated}')
    import damage_lifecycle
    for old in damage_lifecycle.cases():
        if old.label.startswith('locations-supp-narc-attach'):
            d=deepcopy(old.document)
            for action in d['actions']:
                if action.get('name')=='target':action['name']='lock'
            yield Case(d,old.check,label='missiles-'+old.label,mode='normal')
    for percentage,expected in ((25,3),(50,6),(100,12)):
        d=fixture(False);mount(d,range_short=3,range_medium=6,range_long=9);d['actions']=[diag('percentage-failure',weapon='IS.MediumLaser',type='RANGE',percentage=percentage)]
        yield Case(d,lambda o,expected=expected:eq(o['results'][0]['modifier'],expected),label=f'impacts-unreachable-range-failure-arithmetic-{percentage}',note='No selectable RANGE failure row exists in the authoritative failures.h; this verifies only its public arithmetic diagnostic.')
