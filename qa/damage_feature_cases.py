"""Feature-derived inputs and independent observations at the documented CLI."""
from damage_support import *


def armor(n,p):
    d=document(p.get('unit_class','MECH'));u=d['units'][0];rng=d['random']['streams']
    if n==1:
        loc=LOC[p['section']];section(d,loc,armor=20,armor_orig=20,rear=8,rear_orig=8,internal=30,internal_orig=30)
        u['specials']={'standard':0,'hardened':0x20000000,'reinforced-internal':0x8000000,'composite-internal':0x10000000}[p['technology']]
        d['actions']=[diag('damage',section=loc,amount=int(p['damage']),rear=yes(p['rear']),attacker='enemy')]
        def check(o):
            s=state(o)['sections'][loc];checks(*[(s[k],int(p[v])) for k,v in [('armor','front_left'),('rear','rear_left'),('internal','internal_left')]])
    elif n==2:
        u['armor_warnings']=yes(p['enabled']);section(d,2,armor=int(p['before']),armor_orig=40,rear=int(p['before']),rear_orig=40)
        d['actions']=[diag('damage',section=2,amount=1,rear=yes(p['rear']),attacker='enemy')]
        def check(o):
            ns=state(o)['armor_notices'];checks((len(ns),int(p['notices'])),(ns[-1]['severity'] if ns else 'none',p['severity']))
    elif n==3:
        name='IS.'+p['weapon'] if p['weapon']!='other' else WEAP['energy']
        section(d,4,armor=int(p['before']),armor_orig=100,internal=100,slots=[special('LIFE_SUPPORT',i) for i in range(6)])
        rng['critical_rolls']=[7] if int(p['damage'])>int(p['before']) else [int(p['roll']),7,7]
        d['actions']=[diag('damage',section=4,amount=int(p['damage']),weapon=name,ammo_mode=0x2000,attacker='enemy')]
        def check(o): eq(len(destroyed_slots(o,4)),int(p['criticals']))
    elif n==4:
        section(d,4,armor=1,armor_orig=1,slots=[special('LIFE_SUPPORT',i) for i in range(6)])
        rng['critical_rolls']=[int(p['armor_roll']),int(p['internal_roll'])]
        d['actions']=[diag('damage',section=4,amount=2,critical=True,attacker='enemy')]
        def check(o): checks((len(destroyed_slots(o,4)),int(p['criticals'])),(count_draw(o,'critical_rolls'),2))
    else: raise ValueError(n)
    return [Case(d,check)]


def transfer(n,p):
    d=document();u=d['units'][0];rng=d['random']['streams']
    if n in (1,2,4):
        section(d,0,armor=0 if n==2 else 2,armor_orig=2,internal=0 if n==2 else 3,internal_orig=3)
        section(d,2,armor={1:4,2:10,4:20}[n],armor_orig=20,internal=20,internal_orig=20)
        if n==1:
            section(d,0)['config']={'CASE':1,'CASE-II-only':64,'none':0,'Clan':0}[p['containment']]
            u['specials']=32 if p['containment']=='Clan' else 0
        d['actions']=[diag('damage',section=0,amount=int(p['damage']),internal=p.get('path')=='internal',attacker='enemy')]
        def check(o):
            s=state(o);t=s['sections'][2]
            if n==1: checks((s['sections'][0]['internal']==0,yes(p['arm_destroyed'])),(t['armor'],int(p['armor_left'])),(t['internal'],int(p['internal_left'])))
            elif n==2: checks((t['armor'],int(p['armor_left'])),(count_draw(o,'critical_rolls'),0))
            else: checks((s['damage_taken'],int(p['damage'])),(state(o,'enemy')['damage_inflicted'],int(p['damage'])),(s['stagger'],int(p['damage'])))
    elif n==3:
        section(d,2,armor=20,armor_orig=20);u.update(hidden=True,status2=0x10000)
        if yes(p['unit_safe']): u['status']=0x400000
        d['map']['combat_safe']=yes(p['map_safe']);d['units'][1]['status2']=0x800000 if yes(p['hold']) else 0
        d['actions']=[diag('damage',section=2,amount=5,attacker='enemy')]
        def check(o):
            s=state(o);checks((s['sections'][2]['armor'],int(p['armor_left'])),(flag(s['crit_status'],8),yes(p['hidden'])),(flag(s['status2'],0x10000),yes(p['sprinting'])),(notices(state(o,'enemy'),'weapons hold'),int(p['warnings'])),(count_draw(o,'damage_entry'),1))
    elif n==5:
        suit=dict(name='suit',**{'class':'BSUIT'},swarm_target='u',sections=[sec(i,internal=10 if i==0 else 0) for i in range(8)])
        d['units'].append(suit);rng.update(damage_entry=[int(p['roll']),7,7],live_suit=[0]*10)
        d['actions']=[diag('damage',section=LOC[p['section']],amount=3,rear=yes(p['rear']),ignore_swarmers=yes(p['ignore']),attacker='enemy')]
        def check(o): eq(state(o,'suit')['damage_taken']>0,yes(p['absorbed']))
    else: raise ValueError(n)
    return [Case(d,check)]


def locations(n,p):
    d=document();u=d['units'][0];rng=d['random']['streams'];out=[]
    if n in (1,2):
        for roll,expected in enumerate(p['locations'].split(','),2 if n==1 else 1):
            q=document();q['units'][0]['movement']='QUAD' if p.get('chassis')=='quad' else 'BIPED'
            q['actions']=[diag('location',profile='FASA',side=side(p['side']),roll=roll)] if n==1 else [diag('physical-location',attack=p['attack'],side=side(p['side']),roll=roll)]
            def check(o,expected=expected,roll=roll):
                r=o['results'][0];eq(r[0] if n==1 else r,LOC[expected])
                if n==1:eq(r[1],roll==2)
            out.append(Case(q,check,note=f'Independent roll {roll}'))
        return out
    if n==3:
        d['actions']=[diag('swarm-location',roll=int(p['roll']))]
        def check(o): eq(o['results'][0],[LOC[p['location']],yes(p['rear']),True])
    elif n==4:
        u['class']='BSUIT';live=[] if p['members']=='none' else list(map(int,p['members'].split(',')))
        u['sections']=[sec(i,internal=10 if i in live else 0) for i in range(8)];rng.update(suit_choice=[0]*10,empty_suit_location=[0])
        d['actions']=[diag('live-suit'),diag('location',profile='FASA',side='FRONT',roll=7)]
        def check(o): checks((o['results'][0],int(p['helper_location'])),(o['results'][1][0],int(p['table_location'])))
    elif n==5:
        u['class']=p['attacker'];u['at'][2]=int(p['height'])
        if yes(p['swarmed']):u['swarm_target']='enemy'
        if yes(p['cover']):d['units'][1]['status']=0x10|0x8
        rng.update(physical_location=[1],swarm_location=[7],hit_location_rolls=[7])
        d['actions']=[diag('target-location',target='enemy',side='FRONT')]
        def check(o):
            eq(o['results'][0][0],LOC[p['location']])
            expected={'punch':'physical_location','kick':'physical_location','swarm':'swarm_location'}.get(p['table'])
            if expected:eq(count_draw(o,expected),1)
    elif n==6:
        d['units'][1]['class']=p['unit_class'];d['units'][1]['sections']=[sec(LOC[x],internal=0) for x in p['dead'].split(',') if x!='none']
        d['actions']=[diag('narc-location',target='enemy',section=LOC[p['location']],rear=True)]
        def check(o): eq(o['results'][0],[-1 if p['attached']=='none' else LOC[p['attached']],yes(p['rear'])])
    elif n==7:
        d['config']['exile_stun_code']=int(p['mode']);u.update(speed=60,desired_speed=60);rng['physical_location']=[int(p['roll'])]
        d['actions']=[diag('location',side='FRONT',roll=12),advance(int(p['time']))]
        def check(o): checks((o['results'][0][0],LOC[p['location']]),(flag(state(o)['crit_status'],0x40000000),yes(p['stunned'])))
    else: raise ValueError(n)
    return [Case(d,check)]


def vehicle_locations(n,p):
    d=document(p.get('unit_class','GROUND'));u=d['units'][0];rng=d['random']['streams']
    if n==1:
        cases=[]
        for roll,expected in enumerate(p['locations'].split(','),2):
            q=document(p['unit_class']);q['units'][0]['sections']=[sec(i) for i in range(8)];section(q,4,internal=int(p['turret']))
            q['random']['streams']['crittable_chance']=[1]*10
            q['actions']=[diag('location',profile='advanced',side=side(p['side']),roll=roll)]
            def check(o,expected=expected): checks((o['results'][0][0],LOC[expected]),(o['results'][0][1],False))
            cases.append(Case(q,check,note=f'Independent roll {roll}'))
        return cases
    if n==2:
        u.update(movement=p['movement'],specials=0x40000000 if yes(p['proof']) else 0)
        d['config']['vcrit']=int(p['vcrit']);section(d,4,armor=int(p['current']),armor_orig=int(p['original']))
        rng['crittable_chance']=[int(p['draw'])];d['actions']=[diag('crittable',section=4,threshold=60)]
        def check(o):eq(o['results'][0],yes(p['eligible']))
    elif n==3:
        u['tank_crit_status']=4;section(d,4,internal=int(p['current']),internal_orig=10)
        rng.update(dug_in=[int(p['draw'])],crittable_chance=[1]*10,hit_location_rolls=[7]*10)
        d['actions']=[diag('location',profile=p['profile'],side='FRONT',roll=7)]
        def check(o):eq(o['results'][0][0],LOC[p['location']])
    elif n==4:
        u['sections']=[sec(i) for i in range(8)];rng['crittable_chance']=[1]*10
        d['actions']=[diag('location',profile=p['profile'],side=side(p['side']),roll=int(p['roll']))]
        def check(o):eq(o['results'][0][0],int(p['location']))
    else:raise ValueError(n)
    return [Case(d,check)]


def components(n,p):
    d=document();u=d['units'][0];actions=d['actions']
    if n==1:
        u.update(lrs_range=31,tac_range=21,scan_range=11,base_to_hit=4)
        section(d,4,slots=[special('SENSORS',i) for i in range(int(p['hits']))])
        actions += [diag('slot',slot=i) for i in range(int(p['hits']))]
        def check(o):
            s=state(o);checks(*[(s[k],int(p[v])) for k,v in [('lrs_range','lrs'),('tac_range','tac'),('scan_range','scan'),('base_to_hit','bth')]])
    elif n in (2,3):
        u['engine_heat']=int(p.get('before',0));slot=special('ENGINE')
        if n==3:slot.update(brand=3,temp_failure=2,weap_damage_flags=4,data=7,firemode={'functional':0,'broken':4,'disabled':2}[p['condition']])
        section(d,4,slots=[slot]);actions.append(diag('slot'))
        def check(o):
            s=state(o);eq(s['engine_heat'],int(p['after'] if n==2 else p['heat']))
            if n==2:checks((s['destroyed'],yes(p['destroyed'])),(any('reactor' in str(x).lower() for x in s['external_effects']),False))
            else:checks((sl(o)['brand'],3),(sl(o)['temp_failure'],0),(sl(o)['weap_damage_flags'],0),(sl(o)['data'],7),(sl(o)['firemode'],1))
    elif n==4:
        kind=p['sink'];u.update(num_sinks=10 if kind=='single' else 5,specials={'single':0,'IS-double':8,'Clan-double':32}[kind])
        section(d,0,slots=[special('HEAT_SINK',i) for i in range({'single':1,'IS-double':3,'Clan-double':2}[kind])])
        operation={'direct-critical':'slot','hit-location':'destroy-heat-sink','section-destruction':'destroy-section'}[p['path']]
        actions += [diag(operation,section=0),inspect(),diag(operation if operation=='destroy-heat-sink' else 'slot',section=0)]
        def check(o):checks((state(o,index=1)['sink_capacity'],int(p['capacity'])),(state(o)['sink_capacity'],int(p['capacity'])))
    elif n==5:
        u.update(status=0x48,specials2=0x80,jump_mp=int(p['jets']),jump_speed=int(p['jets'])*10.75)
        section(d,0,slots=[special('JUMP_JET',i) for i in range(2)])
        actions.append(diag('slot',section=0,attacker='enemy'))
        def check(o):checks((state(o)['jump_mp'],int(p['remaining'])),(bool(sl(o,0,1)['firemode']&5),True),(state(o)['fallen'],yes(p['fall'])))
    elif n==6:
        e=p['equipment'];name={'C3-slave':'C3_SLAVE','C3i':'C3I','TAG':'TAG','ECM':'ECM','Angel-ECM':'ANGELECM','Artemis':'ARTEMIS_IV','null-signature':'NULL_SIGNATURE_SYSTEM','DS-mechdoor':'DS_MECHDOOR'}[e]
        u.update(status2=0x3c3,c3i_network=['enemy']);d['units'][1]['c3i_network']=['u']
        mount(d,section_index=4,critical=1);section(d,4,slots=[special(name,data=1),dict(index=1,ammomode=2)])
        actions.append(diag('slot',attacker='enemy'))
        def check(o):
            s=state(o)
            if e=='C3-slave':eq(flag(s['crit_status'],0x80000),True)
            elif e=='C3i':checks((s['relationships']['c3i_network'],[]),(state(o,'enemy')['relationships']['c3i_network'],[]))
            elif e=='TAG':eq(flag(s['crit_status'],4),True)
            elif e=='ECM':eq(s['status2']&0x43,0)
            elif e=='Angel-ECM':eq(s['status2']&0x300,0)
            elif e=='Artemis':eq(sl(o,4,1)['ammomode']&2,0)
            else:checks((s['status2']&0x80,0),(flag(s['crit_status'],0x200),True))
    else:raise ValueError(n)
    return [Case(d,check)]

ACTUATOR={'hand':'HAND_OR_FOOT_ACTUATOR','upper':'UPPER_ACTUATOR','lower':'LOWER_ACTUATOR','shoulder':'SHOULDER_OR_HIP','hip':'SHOULDER_OR_HIP'}
def mobility(n,p):
    d=document();u=d['units'][0]
    if n==1:
        section(d,0,slots=[special(ACTUATOR[k],i,firemode=1) for i,k in enumerate(p['actuators'].split(','))])
        d['actions']=[diag('normalize',section=0),inspect(),diag('normalize',section=0)]
        def check(o):
            for index in (1,None):eq(state(o,index=index)['sections'][0]['basetohit'],int(p['bth']))
    elif n in (2,3):
        u.update(max_speed=64.5,template_max_speed=64.5)
        if n==2:
            u['movement']='QUAD' if p['chassis']=='quad' else 'BIPED'
            for i in ((0,1,5,6) if p['chassis']=='quad' else (5,6))[:int(p['lost'])]:section(d,i,armor=0,internal=0)
        else:
            section(d,5,slots=[special(ACTUATOR['hip'],firemode=1)]);u['crit_status']=32
            if p['right']!='intact':section(d,6,slots=[special(ACTUATOR[p['right'].split('-')[0]],firemode=1)])
            if p['right']=='hip-destroyed':u['crit_status']|=0x20000
        d['actions']=[diag('normalize'),inspect(),diag('normalize')]
        def check(o):
            for index in (1,None):
                s=state(o,index=index);checks((s['max_speed'],float(p['speed'])),(s['pilot_skill_base'],int(p['psr'])))
                if n==2:eq(s['fallen'],yes(p['fallen']))
    elif n==4:
        u['specials2']=0x400000 if p['gyro']=='hardened' else 0
        section(d,4,slots=[special('GYRO',i) for i in range(int(p['hits']))])
        d['actions']=[diag('slot',slot=i,attacker='enemy') for i in range(int(p['hits']))]
        def check(o):
            s=state(o);checks((flag(s['crit_status2'],1),yes(p['hard'])),(flag(s['crit_status'],16),yes(p['damaged'])),(flag(s['crit_status'],1),yes(p['destroyed'])),(s['fallen'],yes(p['fallen'])))
    elif n==5:
        u.update(max_speed=30,speed=int(p['current']),desired_speed=int(p['desired']));d['actions']=[diag('correct-speed')]
        def check(o):checks((state(o)['speed'],int(p['actual'])),(state(o)['desired_speed'],int(p['wanted'])))
    else:raise ValueError(n)
    return [Case(d,check)]


def dispatch(n,p):
    d=document(p.get('unit_class','MECH'));u=d['units'][0];rng=d['random']['streams']
    if n==1:
        if yes(p['safe']):u['status']=0x400008
        u['specials']=0x40000000 if yes(p['proof']) else 0;d['config']['vcrit']=int(p['vcrit'])
        section(d,4,slots=[special('LIFE_SUPPORT')]);rng['critical_mw_gate']=[int(p['draw'])]
        d['actions']=[diag('critical',count=1)]
        def check(o):eq(len(o['results'][0]),int(p['count']))
    elif n in (2,3):
        cases=[]
        for roll,effect in enumerate(p['effects'].split(','),6 if n==2 else 0):
            q=document(p['unit_class']);v=q['units'][0];v['sections']=[sec(i) for i in range(8)]
            loc=LOC[p['location']] if n==2 else 3
            if n==2:v['specials']=0x400000
            mount(q,'autocannon' if n==2 else 'energy',section_index=loc,rounds=3 if n==2 else None)
            q['config'].update(fasaadvvtolcrit=int(n==2),fasaadvvhlcrit=int(n==2),fasacrit=int(p.get('profile')=='FASA'))
            q['random']['streams'].update(vehicle_critical_roll=[roll],vehicle_motive_gate=[6],vehicle_legacy_critical=[roll],vehicle_weapon_slot=[0]*10,vehicle_weapon_weight=[5]*10,vehicle_jam_recycle=[60])
            q['actions']=[diag('critical',section=loc,count=1,attacker='enemy')]
            def check(o,effect=effect,loc=loc):
                s=state(o);t=s['sections'][loc]
                if effect=='cargo':eq(notices(s,'fails to hit a critical system'),1)
                elif effect=='weapon-jam':eq(sl(o,loc)['temp_failure'],1)
                elif effect=='weapon-destroyed':eq(flag(sl(o,loc)['firemode'],1),True)
                elif effect=='stabilizer':eq(flag(t['config'],32),True)
                elif effect in ('driver','pilot'):eq(s['pilot_skill_base'],2)
                elif effect in ('sensor','copilot'):eq(s['base_to_hit'],1)
                elif effect=='commander':checks((s['pilot_skill_base'],1),(s['base_to_hit'],1),(flag(s['tank_crit_status'],16),True))
                elif effect=='crew-stun':eq(flag(s['tank_crit_status'],16),True)
                elif effect in ('crew-killed','fuel','cockpit','powerplant'):
                    eq(s['destroyed'],True)
                    if n==3:eq(s['kill_reason'],{'crew-killed':'PILOT','fuel':'FUELTANK','cockpit':'COCKPIT','powerplant':'POWERPLANT'}[effect])
                elif effect=='ammo':checks((sl(o,2,8)['data'],0),(t['internal'],85))
                elif effect=='engine':eq(s['max_speed'],64.5 if p['unit_class']=='VTOL' and n==2 else 0)
                elif effect=='turret-jam':eq(flag(s['tank_crit_status'],2),True)
                elif effect=='turret-lock':eq(flag(s['tank_crit_status'],1),True)
                elif effect=='turret-off':eq(t['internal'],0)
                elif effect=='rotor-damage':eq(s['max_speed'],53.75)
                elif effect=='tail-rotor':eq(flag(s['tank_crit_status'],32),True)
                elif effect=='rotor-destroyed':eq(s['sections'][5]['internal'],0)
                elif effect=='head-injury':eq(s['pilot_hits'],1)
                elif effect=='main-jam':eq(sl(o,loc)['temp_failure'],5)
                else:raise ValueError(effect)
            cases.append(Case(q,check,note=f'Independent chart roll {roll}: {effect}'))
        return cases
    elif n==4:
        slots=[]
        for i,name in enumerate(p['slots'].split(',')):
            if name=='damaged-weapon':s=dict(index=i,weapon=WEAP['energy'],firemode=8)
            else:s=special(name.removeprefix('disabled-'),i,firemode=2 if name.startswith('disabled-') else 0)
            slots.append(s)
        section(d,4,slots=slots);d['actions']=[diag('critical',count=int(p['requested']))]
        def check(o):
            eq(destroyed_slots(o,4),[] if p['destroyed']=='none' else list(map(int,p['destroyed'].split(','))))
            for i in (0,1,2,3,5,6,7):eq(destroyed_slots(o,i),[])
    elif n==5:
        section(d,7,slots=[special('COCKPIT'),special('LIFE_SUPPORT',1)])
        d['actions']=[diag('critical',section=7,count=2)]
        def check(o):checks((destroyed_slots(o,7),[0,1]),(len(o['results'][0]),2),(count_draw(o,'critical_slot'),2))
    else:raise ValueError(n)
    return [Case(d,check)]


def vehicle_effects(n,p):
    d=document('GROUND',periodic=n in (1,5));u=d['units'][0];rng=d['random']['streams'];a=d['actions']
    if n==1:
        fire_setup(d,p['weapon_type'],rounds=10 if p['weapon_type']!='energy' else None)
        rng.update(vehicle_weapon_slot=[0],vehicle_jam_recycle=[int(p['duration'])])
        a += [diag('effect',name='weapon_jam',section=4),inspect(),cmd('fire',0),inspect(),advance(int(p['duration']))]
        def check(o):
            checks((sl(o,index=3)['temp_failure'],TEMP[p['failure']]),(sl(o,index=3)['data'],int(p['duration'])),(sl(o)['temp_failure'],0),(sl(o)['data'],0),(o['results'][4]['ok'],False))
            if p['weapon_type']!='energy':eq(sl(o,2,8)['data'],10)
    elif n==2:
        u['tank_crit_status']=(2 if yes(p['jammed']) else 0)|(1 if yes(p['locked']) else 0)
        a += [diag('effect',name='turret_jam'),cmd('turret',90)]
        def check(o):
            s=state(o);checks((flag(s['tank_crit_status'],2),yes(p['new_jammed'])),(flag(s['tank_crit_status'],1),yes(p['new_locked'])),(o['results'][1][0],False))
    elif n==3:
        mount(d,'autocannon',section_index=3,rounds=int(p['rounds']));section(d,3)
        section(d,2).setdefault('slots',[]).append(dict(index=9,ammo='IS.GaussRifle',data=10))
        a.append(diag('effect',name='ammo_explosion',section=3,attacker='enemy'))
        def check(o):checks((state(o)['sections'][3]['internal'],int(p['internal'])),(sl(o,2,8)['data'],0),(sl(o,2,9)['data'],10),(flag(sl(o,3)['firemode'],1),yes(p['fallback'])))
    elif n==4:
        u.update(**{'class':'VTOL'},movement='VTOL',at=[2,2,20],fuel=100,max_speed=float(p['speed']))
        a.append(diag('effect',name='rotor_damaged'))
        def check(o):checks((state(o)['max_speed'],float(p['remaining'])),(state(o)['sections'][5]['internal']==0,yes(p['destroyed'])),(len(events(state(o),'FALL')),int(p['events'])))
    elif n==5:
        fire_setup(d);a += [diag('effect',name='crew_stunned'),advance(30),diag('effect',name='crew_stunned'),advance(int(p['time'])-30),cmd('fire',0)]
        def check(o):checks((flag(state(o)['tank_crit_status'],16),yes(p['stunned'])),(o['results'][-1]['ok'],yes(p['can_fire'])))
    elif n==6:
        u.update(**{'class':'VTOL'},movement='VTOL',at=[2,2,5],fuel=100)
        d['map']['default']=[p['terrain'],0];rng['pilot_rolls']=[12 if p['roll']=='passes' else 2]*100
        a.append(diag('effect',name='engine_hit',attacker='enemy'))
        def check(o):checks((flag(state(o)['status'],1) and not state(o)['fallen'],yes(p['landed'])),(state(o)['fallen'],yes(p['falls'])))
    elif n==7:
        u.update(max_speed=64.5,speed=60,desired_speed=int(p['desired']));a.append(diag('effect',name='crew_stunned'))
        def check(o):checks((state(o)['speed'],60),(state(o)['desired_speed'],float(p['wanted'])))
    elif n==8:
        mount(d,section_index=0);mount(d,section_index=1);rng['vehicle_weapon_weight']=list(map(int,p['weights'].split(',')))
        a.append(diag('main-weapon-jam'))
        def check(o):checks(([i+1 for i in (0,1) if sl(o,i)['temp_failure']==5],[] if p['selected']=='none' else [int(p['selected'])]),(events(state(o),'MRECOVERY'),[]))
    elif n==9:
        u.update(movement=p['movement'],max_speed=64.5,speed=20,desired_speed=20);rng['motive_rolls']=[int(p['roll'])]
        a.append(diag('motive'))
        def check(o):checks((state(o)['max_speed'],float(p['speed'])),(state(o)['pilot_skill_base'],int(p['penalty'])),(state(o)['fallen'],yes(p['immobile'])))
    else:raise ValueError(n)
    return [Case(d,check)]


def destruction(n,p):
    kind=p.get('unit_class','GROUND' if n in (4,5) else 'VTOL' if n==3 else 'AERO')
    d=document(kind);u=d['units'][0];a=d['actions']
    if n==1:
        loc=LOC[p['section']];mount(d,section_index=loc)
        if kind=='airborne-VTOL':u.update(at=[2,2,20],fuel=100)
        a += [diag('destroy-section',section=loc,attacker='enemy'),cmd('weaponstatus')]
        def check(o):checks((state(o)['destroyed'],yes(p['destroyed'])),(bool(events(state(o),'FALL')),yes(p['fall'])),(flag(sl(o,loc)['firemode'],1),True),(state(o)['weapons'][0]['usable'],False))
    elif n==2:
        a.append(diag('destroy-section',section=3,attacker='enemy'))
        def check(o):eq(state(o)['sections'][1]['internal']==0,yes(p['arm']))
    elif n==3:
        u.update(at=[2,2,20],fuel=100);a += [diag('effect',name='rotor_destroyed'),advance(int(p['time']))]
        def check(o):checks((state(o)['at'][2],int(p['height'])),(state(o)['destroyed'],False))
    elif n==4:
        u.update(specials=0x400000,status2=1,speed=20,desired_speed=20,target=7)
        a += [cmd('speed',20),diag('effect',name='fuel_tank_hit',attacker='enemy')]
        def check(o):
            s=state(o);checks((s['kill_reason'],'FUELTANK'),(all(x['internal']==0 for x in s['sections'] if x['internal_orig']),True),(s['speed'],0),(s['desired_speed'],0),(s['vertical_speed'],0),(s['target'],-1),(s['pilot_present'],False),(s['status2']&1,0),(events(s,'MOVE'),[]))
    elif n==5:
        section(d,4,slots=[special('ENGINE')]);a.append(diag('destroy-section',section=4))
        def check(o):checks((sl(o)['firemode'],1),(state(o)['engine_heat'],0),(state(o)['destroyed'],False))
    elif n==6:
        mount(d,section_index=1);section(d,1,armor=5,armor_orig=5);a.append(diag('damage',section=1,amount=int(p['damage']),attacker='enemy'))
        def check(o):checks((state(o)['sections'][1]['armor'],int(p['armor'])),(not state(o)['weapons'][0]['usable'],yes(p['lost'])))
    else:raise ValueError(n)
    return [Case(d,check)]


def commands(n,p):
    d=document();a=d['actions']
    if n==1:
        d['units'][0]['sections']=[sec(i) for i in range(8)];d['random']['streams']['hit_location_rolls']=[7]*100
        a.append(cmd('damage',*p['argument'].split()))
        def check(o):checks((o['results'][0]['accepted'],yes(p['accepted'])),(state(o)['damage_taken'],int(p['total'])))
    elif n==2:
        section(d,0,armor=50,armor_orig=50);a.append(cmd('dodamage',int(p['total']),int(p['cluster']),0))
        def check(o):checks((state(o)['sections'][0]['armor'],int(p['armor'])),(o['results'][0]['sizes'],list(map(int,p['sizes'].split(',')))))
    elif n==3:
        section(d,2,armor=20,armor_orig=20,rear=10,rear_orig=10);a.append(cmd('damage-section',*p['argument'].split()))
        def check(o):checks((o['results'][0]['accepted'],yes(p['accepted'])),(state(o)['sections'][2]['armor'],int(p['front'])),(state(o)['sections'][2]['rear'],int(p['rear'])))
    elif n==4:
        section(d,0,armor=20,armor_orig=20,internal=10,internal_orig=10,rear=0,rear_orig=0);mount(d,section_index=0)
        a.append(cmd('setarmorstatus','LA',p['type'],p['value']))
        def check(o):
            s=state(o)['sections'][0];checks((o['results'][0]['text'],p['reply']),*[(s[k],int(p[v])) for k,v in [('armor','front'),('internal','internal'),('rear','rear')]],(s['slots'][0]['firemode'],0),(events(state(o),'FALL'),[]),(events(state(o),'MRECOVERY'),[]),(o['draws'],[]))
    elif n==5:
        mount(d);name=p['state'];slot=dict(index=0)
        if name.startswith('temporary-'):slot['temp_failure']={'destroyed':5,'jammed':1,'shorted':2,'empty':4,'dud':3,'ammojammed':6}[name[10:]]
        else:slot['firemode']={'operational':0,'damaged':8,'disabled-and-damaged':10,'broken-and-disabled':6}[name]
        section(d,4,slots=[slot]);a.append(cmd('weaponstatus'))
        def check(o):eq(state(o)['weapons'][0]['status'],p['status'])
    elif n==6:
        mount(d,section_index=0);mount(d,'autocannon',section_index=0,critical=1);mount(d,'missile',section_index=1)
        a += [diag('weapon-count',section=int(p['section'])),diag('weapon-type',section=int(p['section']),ordinal=int(p['ordinal']))]
        def check(o):
            eq(o['results'][0],int(p['count']))
            if p['weapon']=='none':eq(o['results'][1],-1)
            else:
                section_index,critical=(0,1) if p['weapon']=='autocannon' else (1,0)
                eq(o['results'][1],sl(o,section_index,critical)['type']-1)
    else:raise ValueError(n)
    return [Case(d,check)]


def enhanced(n,p):
    d=document(p.get('unit_class','MECH'));rng=d['random']['streams'];a=d['actions']
    if n==1:
        mount(d,p['weapon_type'],metadata={'crits':6});a.append(diag('enhanced',roll=int(p['roll'])))
        def check(o):
            eq(flag(sl(o)['firemode'],1),yes(p['destroyed']))
            eq(sl(o)['weap_damage_flags'],FLAGS.get(p['kind'],0))
    elif n==2:
        mount(d,metadata={'crits':4});section(d,4,slots=[dict(index=i,firemode=8) for i in range(int(p['damaged']))])
        a.append(diag('weapon-threshold',increment=yes(p['increment'])))
        def check(o):eq(o['results'][0],yes(p['destroy']))
    elif n==3:
        fire_setup(d,metadata={'damage':10,'heat':5,'range_short':3,'crits':6},distance=int(p['range']))
        section(d,4,slots=[dict(index=i,firemode=8,weap_damage_flags=FLAGS[name]) for i,name in enumerate(p['flags'].split(','))])
        a += [diag('weapon-modifiers',range_bracket=int(p['range'])>3),cmd('fire',0)]
        a[-2]['options']['range_bracket']=int(int(p['range'])>3)
        def check(o):
            attack=o['results'][-1]['attack'];checks((o['results'][-2]['bth'],int(p['bth'])),(attack['critical_bth'],int(p['bth'])),(attack['damage_dealt'],int(p['damage'])),(state(o)['weap_heat'],int(p['heat'])))
    elif n==4:
        kind=p['part'].split('-')[0];fire_setup(d,kind,metadata={'damage':5},rounds=10 if kind!='energy' else None)
        flagname={'energy-crystal':'crystal','ballistic-feed':'ballistic-feed','missile-feed':'missile-feed','ballistic-barrel':'barrel'}[p['part']]
        section(d,4,slots=[dict(index=0,firemode=8,weap_damage_flags=FLAGS[flagname])]);rng['attack_rolls']=[int(p['roll'])]
        a += [inspect(),cmd('fire',0)]
        def check(o):
            checks((sum(s['internal'] for s in state(o,index=2)['sections'])-sum(s['internal'] for s in state(o)['sections']),int(p['internal'])),(10-sl(o,2,8)['data'] if kind!='energy' else 0,int(p['ammo'])))
            if p['outcome']=='AMMOCRITJAMMED':eq(sl(o)['temp_failure'],7)
            else:eq(o['results'][-1]['attack']['shot_aborted'],p['outcome']=='exploded')
    elif n==5:
        mount(d);section(d,4,slots=[dict(index=0,firemode=8,weap_damage_flags=FLAGS[p['flag']])])
        a += [cmd('weaponstatus'),diag('weapon-detail'),diag('weapon-modifiers')]
        def check(o):
            index={'moderate':0,'focus':1,'crystal':2}[p['flag']]
            checks((o['results'][1]['damage_hits'][index],int(p['display_count'])),(o['results'][2][{'moderate':'bth','focus':'damage','crystal':'heat'}[p['flag']]],1))
    else:raise ValueError(n)
    return [Case(d,check)]


def failures(n,p):
    d=document();rng=d['random']['streams'];a=d['actions']
    if n==1:
        category=p['category']
        if category in ('computer','radio'):part=-1 if category=='computer' else -2
        else:
            # Catalog IDs are fixture metadata, checked separately against the source inventory.
            part={'energy':2,'autocannon':20,'missile':49,'flamer':8,'PCOMBAT':99999}[category]
        a += [diag('brand-index',part_type=part),diag('brand',part_type=part,level=int(p['level']))]
        def check(o):checks((o['results'][0],int(p['index'])),(o['results'][1] or 'none',p['brand']))
    elif n in (2,4):
        mount(d,brand=int(p.get('level',1)),metadata={'damage':20} if n==4 else None)
        rng.update(failure_weapon_chance=[int(p.get('chance',9))],failure_reliability=[int(p.get('reliability',100))],failure_outcome=list(map(int,p.get('draws','1').split(','))))
        a.append(diag('weapon-failure'))
        def check(o):
            eq(o['results'][0]['type'],p['failure'])
            if n==4:eq(count_draw(o,'failure_outcome'),int(p['count']))
    elif n==3:
        mount(d,p['category'],metadata={'damage':20,'heat':10});rng.update(failure_weapon_recycle=[20],failure_dud_recycle=[20])
        a.append(diag('failure',category=CATEGORY[p['category']],outcome=int(p['outcome'])))
        def check(o):checks((o['results'][0]['type'],p['failure']),(o['results'][0]['modifier'],int(p['modifier'])),(sl(o)['temp_failure'],TEMP[p['temporary']]),(sl(o)['data'],int(p['recycle'])))
    elif n==5:
        kind='missile' if p['failure'].startswith('missile') else 'autocannon'
        fire_setup(d,kind,brand=1,rounds=10,metadata={'damage':5})
        outcome={'autocannon-dud':2,'autocannon-jam':3,'missile-spike':5,'autocannon-FAIL_NONE-dud':1}[p['failure']]
        rng.update(failure_weapon_chance=[9],failure_reliability=[100],failure_outcome=[outcome],failure_weapon_recycle=[20],failure_dud_recycle=[20])
        a.append(cmd('fire',0))
        def check(o):checks((sl(o,2,8)['data'],int(p['rounds'])),(state(o,'enemy')['sections'][4]['armor'],int(p['armor'])),(o['results'][-1]['attack']['shot_aborted'],yes(p['aborted'])))
    else:raise ValueError(n)
    return [Case(d,check)]


def recovery(n,p):
    d=document(periodic=n in (4,6));u=d['units'][0];a=d['actions'];rng=d['random']['streams']
    if n in (1,2,3):
        rng.update(failure_recovery_upper=[40]*3,failure_recovery_delay=[40]*3)
        if n==1:u['radio_range']=int(p['initial_range']);outcome=3 if p['reduction']=='15' else 4
        elif n==2:u['radio_range']=30;outcome=6
        else:u.update(tac_range=20,lrs_range=30,scan_range=40);outcome={'TAC':2,'LRS':3,'SCAN':4,'all':5}[p['channel']]
        a += [diag('failure',category=24 if n==3 else 30,outcome=outcome),advance(int(p['time']))]
        def check(o):
            s=state(o)
            if n==3:checks((s['tac_range'],int(p['tac'])),(s['lrs_range'],int(p['lrs'])),(s['scan_range'],int(p['scan'])))
            else:eq(s['radio_range'],int(p['range']))
            eq(notices(s,'operational again'),int(p.get('notices',0)))
            names=[x['name'] for x in o['draws'] if x['name'].startswith('failure_recovery')]
            eq(names,['failure_recovery_upper','failure_recovery_delay']*(3 if n==3 and p['channel']=='all' else 1))
    elif n==4:
        u.update(started=yes(p['started']),movement=p['movement'],target=7,computer_brand=1)
        rng.update(failure_generic_chance=[42],failure_reliability=[100],failure_outcome=[1])
        a += [advance(28),inspect(),advance(2)]
        def check(o):checks((state(o,index=1)['target'],7),(state(o)['target'],int(p['target'])),(count_draw(o,'failure_generic_chance'),int(p['checks'])))
    elif n==5:
        u['target']=int(p['target']);a.append(diag('failure',category=24,outcome=1))
        def check(o):checks((state(o)['target'],int(p['after'])),(len(state(o)['messages']),int(p['notices'])))
    elif n==6:
        mount(d);section(d,4,slots=[dict(index=0,temp_failure=5,data=int(p['recycle']))]);a.append(advance(1))
        def check(o):checks((sl(o)['temp_failure'],TEMP[p['state']]),(sl(o)['data'],0))
    else:raise ValueError(n)
    return [Case(d,check)]
