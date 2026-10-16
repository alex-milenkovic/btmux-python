"""Boundary and lifecycle procedures beyond the representative feature examples."""
from copy import deepcopy
from damage_support import *
from damage_feature_cases import armor as armor_feature, vehicle_locations as vehicle_feature


def command_cases():
    values=[None,[],True,{'actions':[],'extra':1},{'actions':'bad'},{'actions':[{'op':'bogus'}]},
        {'actions':[advance(-1)]},{'actions':[advance(True)]},
        {'units':[{'name':'u'},{'name':'u'}],'actions':[]},
        {'units':[{'name':'u','weapons':['unknown']}],'actions':[]},
        {'units':[{'name':'u','sections':[{'index':-1}]}],'actions':[]},
        {'units':[{'name':'u','sections':[{'index':0,'slots':[{'index':12}]}]}],'actions':[]},
        {'units':[{'name':'u','sections':[{'index':0,'slots':[{'index':0,'special':'bogus'}]}]}],'actions':[]},
        {'random':{'streams':{'damage_entry':[]}},'actions':[diag('damage',amount=1)]},
        {'random':{'streams':{'damage_entry':[13]}},'actions':[diag('damage',amount=1)]},
        {'random':{'streams':{'damage_entry':[True]}},'actions':[diag('damage',amount=1)]},
        {'actions':[diag('slot',section=0,slot=-1)]},{'actions':[diag('physical-location',attack='kick',roll=7)]},
        {'actions':[diag('location',profile='unknown')]},'{broken json',
        {'units':[{'name':'u','num_sinks':True}],'actions':[]},
        {'actions':[diag('critical',count=True)]}]
    for i,value in enumerate(values):yield Case(value,lambda o:None,label=f'commands-supp-invalid-{i:02d}',invalid=True)
    d=document();d['actions']=[inspect(),inspect()]
    yield Case(d,lambda o:checks((o['results'][0],o['results'][1]),(o['results'][1],o['state']),(o['draws'],[])),label='commands-supp-inspect')
    for argument,accepted in [('1 1 0 0',True),('1000 1000 0 0',True),('10 10 0 0',True),('5 1 0',False),('5 1 0 0 1',False)]:
        d=document();d['units'][0]['sections']=[sec(i,armor=2000) for i in range(8)];d['random']['streams']['hit_location_rolls']=[7]
        d['actions']=[cmd('damage',*argument.split())]
        yield Case(d,lambda o,accepted=accepted:eq(o['results'][0]['accepted'],accepted),label='commands-supp-bounds-'+argument.replace(' ','_'))
    d=document('MW');d['actions']=[cmd('damage',5,1,0,0)]
    yield Case(d,lambda o:eq(o['results'][0]['accepted'],False),label='commands-supp-mw-refusal')
    for direction in range(22):
        d=document();d['units'][0]['sections']=[sec(i) for i in range(8)];d['random']['streams'].update(hit_location_rolls=[7]*10,physical_location=[1]*10)
        d['actions']=[diag('dodamage',total=11,cluster=5,direction=direction,message='Damage audit',broadcast='Damage broadcast')]
        def check(o):checks((o['results'][0]['accepted'],True),(o['results'][0]['sizes'],[5,5,1]),(state(o)['damage_taken'],11))
        yield Case(d,check,label=f'commands-supp-direction-{direction:02d}')
    d=document();d['actions']=[diag('dodamage',total=1,cluster=1,direction=22)]
    yield Case(d,lambda o:None,label='commands-supp-direction-22',invalid=True)
    d=document();section(d,0,internal_orig=0);d['actions']=[cmd('setarmorstatus','LA',0,1)]
    yield Case(d,lambda o:eq(o['results'][0]['accepted'],False),label='commands-supp-empty-setter')


def armor_cases():
    for original in (0,1,3,7,41):
        for before in sorted({0,1,original//2,original//4,max(0,original//2-1)}):
            for rear in (False,True):
                d=document();d['units'][0]['armor_warnings']=True
                section(d,2,armor=before,armor_orig=original,rear=before,rear_orig=original)
                d['actions']=[diag('damage',section=2,amount=1,rear=rear,attacker='enemy')]
                def severity(v):return 0 if original==0 else 3 if v==0 else 2 if v<original//4 else 1 if v<original//2 else 0
                expected=severity(max(0,before-1));count=int(expected!=severity(before) and expected!=0)
                def check(o,count=count,expected=expected):
                    notices_=state(o)['armor_notices'];eq(len(notices_),count)
                    if count:eq(notices_[0]['severity'],['none','low','critical','breached'][expected])
                yield Case(d,check,label=f'armor-supp-warning-{original}-{before}-{rear}')
    d=document();d['units'][0]['armor_warnings']=True;section(d,2,armor=10,armor_orig=40,rear=20,rear_orig=40)
    d['actions']=[diag('damage',section=2,amount=1),diag('damage',section=2,amount=1),diag('damage',section=2,amount=1,rear=True)]
    yield Case(d,lambda o:eq([n['severity'] for n in state(o)['armor_notices']],['critical','low']),label='armor-supp-independent-warnings')
    for value in range(12):
        d=document();d['actions']=[diag('serious',value=value),diag('serious',value=value%4)]
        yield Case(d,lambda o:eq(o['results'][0],o['results'][1]),label=f'armor-supp-serious-wrap-{value}')
    for rear in (False,True):
        d=document();fire_setup(d,metadata={'damage':5});d['units'][1]['facing']=180 if rear else 0
        d['actions'].append(cmd('fire',0))
        def check(o,rear=rear):
            s=state(o,'enemy')['sections'][4];checks((s['armor'],100 if rear else 95),(s['rear'],15 if rear else 20),(o['results'][-1]['attack']['damage_dealt'],5))
        yield Case(d,check,label=f'armor-supp-live-fire-{rear}')
    for loc in (0,4,7):
        d=document();section(d,loc,armor=0,slots=[special('LIFE_SUPPORT',i) for i in range(6)])
        d['random']['streams']['critical_rolls']=[12];d['actions']=[diag('damage',section=loc,amount=1,attacker='enemy')]
        def check(o,loc=loc):
            if loc==4:eq(len(destroyed_slots(o,4)),3)
            else:eq(state(o)['sections'][loc]['internal'],0)
        yield Case(d,check,label=f'armor-supp-roll12-{loc}')
    d=document('AERO');d['units'][0].update(at=[2,2,20],fuel=100);section(d,3,armor=5,armor_orig=5)
    d['actions']=[diag('damage',section=3,amount=5,attacker='enemy')]
    yield Case(d,lambda o:checks((state(o)['sections'][3]['armor'],0),(state(o)['max_speed'],0),(events(state(o),'FALL'),[3])),label='armor-supp-aft-zero-airborne')


def recovery_cases():
    for stopped in (False,True):
        d=document();d['config']['exile_stun_code']=1;d['random']['streams']['physical_location']=[1,1]
        d['actions']=[diag('location',roll=12),advance(5),diag('location',roll=12),advance(5),inspect()]
        if stopped:d['actions'].append(cmd('shutdown'))
        d['actions'].append(advance(5))
        def check(o,stopped=stopped):
            checks((flag(state(o,index=4)['crit_status'],0x40000000),True),(flag(state(o)['crit_status'],0x40000000),False),(notices(state(o),'recover from your stunning experience'),0 if stopped else 1))
        yield Case(d,check,label=f'locations-supp-exile-replace-stopped-{stopped}')
    for chance in (41,42,43):
        d=document(periodic=True);d['units'][0].update(computer_brand=1,target=7)
        d['random']['streams'].update(failure_generic_chance=[chance],failure_reliability=[100],failure_outcome=[1])
        d['actions']=[advance(29),inspect(),advance(1),inspect(),advance(1)]
        def check(o,chance=chance):checks((state(o,index=1)['target'],7),(state(o,index=3)['target'],-1 if chance==42 else 7),(state(o)['target'],-1 if chance==42 else 7))
        yield Case(d,check,label=f'recovery-supp-turn-{chance}')
    for field in ('tac_range','lrs_range','scan_range'):
        for outcome in (4,5):
            d=document();d['units'][0].update(tac_range=20,lrs_range=30,scan_range=40);d['units'][0][field]=0
            d['actions']=[diag('failure',category=24,outcome=outcome)]
            def check(o,field=field):
                s=state(o);checks((events(s,'MRECOVERY'),[]),(s['tac_range'],0 if field=='tac_range' else 20),(s['lrs_range'],0 if field=='lrs_range' else 30),(s['scan_range'],0 if field=='scan_range' else 40))
            yield Case(d,check,label=f'recovery-supp-scanner-gate-{field}-{outcome}')
    d=document();d['units'][0].update(tac_range=20,lrs_range=30,scan_range=40)
    d['random']['streams'].update(failure_recovery_upper=[40,50,60],failure_recovery_delay=[40,50,60])
    d['actions']=[diag('failure',category=24,outcome=5),advance(40),inspect(),advance(10),inspect(),advance(10)]
    def check_scanners(o):
        for idx,expected in [(2,(20,0,0)),(4,(20,286,0)),(None,(20,286,552))]:
            s=state(o,index=idx);eq(tuple(s[k] for k in ('tac_range','lrs_range','scan_range')),expected)
        eq([(x['name'],x['value']) for x in o['draws']],[(f'failure_recovery_{kind}',n) for n in (40,50,60) for kind in ('upper','delay')])
    yield Case(d,check_scanners,label='recovery-supp-distinct-scanner-timers')
    for short in (False,True):
        d=document();d['units'][0]['radio_range']=40
        d['random']['streams'].update(failure_recovery_upper=[40,60],failure_recovery_delay=[40,60])
        d['actions']=[diag('failure',category=30,outcome=3),diag('failure',category=30,outcome=6 if short else 4),inspect(),advance(40),inspect(),advance(20)]
        def check(o,short=short):checks((state(o,index=2)['radio_range'],0 if short else 1),(state(o,index=4)['radio_range'],15 if short else 16),(state(o)['radio_range'],40))
        yield Case(d,check,label=f'recovery-supp-radio-overlap-{short}')
    for destroyed in (False,True):
        d=document();d['units'][0].update(destroyed=destroyed,tac_range=0,lrs_range=0,scan_range=0,radio_range=0)
        d['actions']=[diag('scanner-recovery',value=20),diag('scanner-recovery',value=286),diag('scanner-recovery',value=552),diag('radio-recovery',value=30)]
        def check(o,destroyed=destroyed):
            s=state(o);checks((s['tac_range'],20),(s['lrs_range'],286),(s['scan_range'],552),(s['radio_range'],30),(notices(s,'operational again'),0 if destroyed else 4))
        yield Case(d,check,label=f'recovery-supp-raw-callback-destroyed-{destroyed}')
    d=document();d['random']['streams'].update(failure_recovery_upper=[40],failure_recovery_delay=[40]);d['actions']=[diag('failure',category=24,outcome=2),diag('destroy-section',section=4,attacker='enemy'),advance(40)]
    yield Case(d,lambda o:checks((state(o)['tac_range'],0),(notices(state(o),'operational again'),0),(events(state(o),'MRECOVERY'),[])),label='recovery-supp-destruction-cancellation')


def failure_cases():
    brands=[['Lords','Hesperus','Martell','Magna','Agra'],['Luxor','SperryBrowning','Oriente','Deprus','Armstrong'],['Coventry','Shannon','Bical','Holly','Telos'],['Pynes','Hotshot','Firestorm','Purity','Ventra'],['Dalban','Hartford','Garet','Ares','Tek'],['Duoteck','CeresCom','Achernar','Tek','Iriad']]
    for part,names in zip((2,20,49,8,-1,-2),brands,strict=True):
        for level,name in enumerate(names,1):
            d=document();d['actions']=[diag('brand',part_type=part,level=level)]
            yield Case(d,lambda o,name=name:eq(o['results'][0],name),label=f'failures-supp-brand-{part}-{level}')
    for category in (24,30):
        for outcome in range(1,7):
            d=document();d['units'][0].update(target=7,tac_range=20,lrs_range=30,scan_range=40,radio_range=50)
            d['random']['streams'].update(failure_recovery_upper=[40]*3,failure_recovery_delay=[40]*3)
            d['actions']=[diag('failure',category=category,outcome=outcome)]
            def check(o,category=category,outcome=outcome):
                s=state(o)
                if category==24:
                    if outcome==1:eq(s['target'],-1)
                    elif outcome==6:eq(s['started'],False)
                    else:eq(tuple(s[k] for k in ('tac_range','lrs_range','scan_range')),{2:(0,30,40),3:(20,0,40),4:(20,30,0),5:(0,0,0)}[outcome])
                elif outcome<=2:checks((o['results'][0]['type'],'STATIC'),(o['results'][0]['modifier'],50 if outcome==1 else 70),(s['messages'],[]))
                else:eq(s['radio_range'],{3:35,4:20,5:0,6:0}[outcome])
            yield Case(d,check,label=f'failures-supp-row-{category}-{outcome}')
    d=document();mount(d,'autocannon',metadata={'vrt':17});d['actions']=[diag('failure',category=6,outcome=1)]
    yield Case(d,lambda o:checks((sl(o)['data'],17),(sl(o)['temp_failure'],0),(o['results'][0]['type'],'NONE')),label='failures-supp-autocannon-row-one')
    for kind,field,base in [('DAMAGE','damage',21),('HEAT','heat',11),('RANGE','range_long',15)]:
        for percent in (15,20,30,45,100):
            d=document();mount(d,metadata={field:base});d['actions']=[diag('percentage-failure',weapon=WEAP['energy'],type=kind,percentage=percent)]
            # C source default btech_erange=1 selects max(long, twice medium); laser medium is six.
            expected=int((base if kind!='RANGE' else max(base,12))*percent/100)
            yield Case(d,lambda o,expected=expected:eq(o['results'][0]['modifier'],expected),label=f'failures-supp-odd-{kind}-{percent}')
    for category,outcome in [(0,4),(6,4),(6,5)]:
        d=document();mount(d,'energy' if category==0 else 'autocannon',metadata={'heat':0})
        d['actions']=[diag('failure',category=category,outcome=outcome)]
        yield Case(d,lambda o:checks((o['results'][0]['type'],'NONE'),(o['draws'],[])),label=f'failures-supp-heatless-{category}-{outcome}')
    d=document();mount(d,brand=1);d['config']['parts']=0;d['random']['streams']['failure_weapon_chance']=[];d['actions']=[diag('weapon-failure')]
    yield Case(d,lambda o:checks((o['results'][0]['type'],'NONE'),(o['draws'],[])),label='failures-supp-parts-off')


def external_cases():
    d=document();d['actions']=[diag('failure',category=30,outcome=1)]
    yield Case(d,lambda o:checks((state(o)['external_effects'][0]['applied'],False),(o['results'][0]['modifier'],50)),label='failures-supp-radio-delivery-blocked',blocked='B4: radio transmission and recipient service is unavailable; local static modifier is verified.')
    for roll in (25,26):
        d=document('BSUIT');d['units'][0].update(in_character=True,sections=[sec(i,internal=10 if i==0 else 0) for i in range(8)])
        d['random']['streams']['suit_ejection']=[roll];d['actions']=[diag('destroy-section',section=0,attacker='enemy')]
        def check(o,roll=roll):
            s=state(o);checks((s['destroyed'],True),(s['pilot_present'],False),(all(not e['applied'] for e in s['external_effects']),True),(any('autoeject' in e['service'] for e in s['external_effects']),roll==25))
        yield Case(d,check,label=f'destruction-supp-ba-eject-{roll}',blocked='B1/B2/B3: persistent ejected character, occupant database, discard and kill channel unavailable.')
    d=document();d['units'][0]['in_character']=True;d['units'][1]['in_character']=True;d['actions']=[diag('damage',amount=1,attacker='enemy')]
    def xp(o):
        effects=state(o)['external_effects']+state(o,'enemy')['external_effects'];assert any('XP' in e['service'] and not e['applied'] for e in effects),effects
    yield Case(d,xp,label='transfer-supp-persistent-xp',blocked='B5: persistent character XP storage is unavailable; local damage counters must still change.')


def routing_cases():
    for rear in (False,True):
        d=document();fire_setup(d,metadata={'damage':10});d['units'][1]['facing']=180 if rear else 0
        d['units'][1]['sections'][4]=sec(4,armor=2,internal=100,rear=2)
        d['units'][1].update(hidden=True,status2=0x10000)
        d['actions'].append(cmd('fire',0))
        def check(o):
            s=state(o,'enemy');checks((s['damage_taken'],10),(state(o)['damage_inflicted'],10),(s['stagger'],10),(flag(s['crit_status'],8),False),(flag(s['status2'],0x10000),False),(count_draw(o,'damage_entry'),1),(s['sections'][4]['internal'],92))
        yield Case(d,check,label=f'transfer-supp-live-fire-routing-{rear}')
    d=document();fire_setup(d,metadata={'damage':10});d['units'][1]['sections'][0]=sec(0,armor=2,internal=3)
    d['random']['streams']['hit_location_rolls']=[10]
    d['actions'].append(cmd('fire',0))
    yield Case(d,lambda o:checks((state(o,'enemy')['sections'][0]['internal'],0),(state(o,'enemy')['sections'][2]['armor'],95),(count_draw(o,'damage_entry'),2),(state(o,'enemy')['damage_taken'],10)),label='transfer-supp-live-fire-chain')
    for ignore,attacker,armor_value,loc,rear in [(False,'enemy',10,2,False),(True,'enemy',10,2,False),(False,'suit',10,2,False),(False,'enemy',0,2,False),(False,'enemy',10,7,True)]:
        d=document();u=d['units'][0];u.update(hidden=True,status2=0x10000);section(d,loc,armor=armor_value)
        d['units'].append(dict(name='suit',**{'class':'BSUIT'},swarm_target='u',sections=[sec(i,internal=10 if i in (0,4) else 0) for i in range(8)]))
        d['random']['streams'].update(suit_choice=[0],hit_location_rolls=[7])
        d['actions']=[diag('damage',section=loc,amount=3,rear=rear,attacker=attacker,ignore_swarmers=ignore)]
        absorbed=not ignore and attacker!='suit' and armor_value>0 and loc==2
        def check(o,absorbed=absorbed):checks((state(o,'suit')['damage_taken']>0,absorbed),(flag(state(o)['crit_status'],8),absorbed),(flag(state(o)['status2'],0x10000),absorbed))
        yield Case(d,check,label=f'transfer-supp-swarm-{ignore}-{attacker}-{armor_value}-{loc}')
    for roll in (8,9):
        d=document();d['units'][0].update(cocoon=10,at=[2,2,20]);d['random']['streams']['interception_rolls']=[roll]
        section(d,4,armor=20);d['actions']=[diag('damage',section=4,amount=3,attacker='enemy')]
        yield Case(d,lambda o,roll=roll:eq(state(o)['sections'][4]['armor'],17 if roll==8 else 20),label=f'transfer-supp-interception-{roll}')
    for amount in (4,5):
        d=document('AERO');d['units'][0].update(si=5,sections=[sec(i,armor=0) for i in range(8)])
        d['actions']=[diag('damage',section=4,amount=amount,attacker='enemy')]
        def check(o,amount=amount):
            eq(state(o)['destroyed'],amount==5)
            if amount<5:eq(state(o)['si'],1)
        yield Case(d,check,label=f'transfer-supp-aero-si-{amount}')
    d=document();mount(d,'autocannon',rounds=2);section(d,2,internal=3,internal_orig=3);section(d,4,internal=30)
    d['actions']=[diag('slot',section=2,slot=8,attacker='enemy')]
    yield Case(d,lambda o:checks((sl(o,2,8)['data'],0),(state(o)['sections'][2]['internal'],0),(state(o)['sections'][4]['internal'],23)),label='transfer-supp-ammo-internal-chain')
    d=document();d['units'][0]['sections']=[sec(i) for i in range(8)];d['units'][0]['at']=[2,2,0];d['units'][0]['facing']=180
    d['units'][1]['sections']=[sec(i) for i in range(8)];d['units'][1]['sections'][0]=sec(0,armor=1,internal=1);d['units'][1]['real']=[744.7818472546172,967.5,0]
    for i,name in enumerate(('SHOULDER_OR_HIP','UPPER_ACTUATOR','LOWER_ACTUATOR','HAND_OR_FOOT_ACTUATOR')):section(d,0).setdefault('slots',[]).append(special(name,i))
    d['config']['periodic_updates']=True;d['random']['streams'].update(physical_attack=[12],physical_location=[1])
    d['actions']=[advance(10),cmd('punch','L','01')]
    def check_physical(o):checks((o['results'][-1]['attacks'][0]['hit'],True),(state(o,'enemy')['sections'][0]['internal'],0),(state(o,'enemy')['sections'][2]['armor'],97),(count_draw(o,'damage_entry'),2))
    yield Case(d,check_physical,label='transfer-supp-physical-chain')


def equipment_cases():
    # Nonfunctional-first ordering across the special switch surface.
    names=('LIFE_SUPPORT','SENSORS','COCKPIT','ENGINE','GYRO','HEAT_SINK','JUMP_JET','TARGETING_COMPUTER','C3_MASTER','C3_SLAVE','C3I','TAG','ECM','ANGELECM','ARTEMIS_IV','NULL_SIGNATURE_SYSTEM','DS_MECHDOOR','BEAGLE_PROBE','BLOODHOUND_PROBE','LIGHT_BAP')
    for name in names:
        for condition in (2,4):
            d=document();section(d,4,slots=[special(name,firemode=condition,brand=3,temp_failure=2,weap_damage_flags=4,data=7)])
            d['actions']=[inspect(),diag('slot')]
            def check(o):
                s=state(o);before=state(o,index=0);checks((sl(o)['firemode'],1),(sl(o)['brand'],3),(sl(o)['data'],7),(sl(o)['temp_failure'],0),(sl(o)['weap_damage_flags'],0))
                for key in ('engine_heat','sink_capacity','jump_mp','base_to_hit','pilot_skill_base','destroyed','status2','crit_status'):eq(s[key],before[key])
            yield Case(d,check,label=f'components-supp-nonfunctional-{name}-{condition}')
    for gauss,rounds,attacker in [(False,0,'enemy'),(True,10,'enemy'),(False,2,None)]:
        d=document();name='IS.GaussRifle' if gauss else 'IS.AC/5';section(d,2,slots=[dict(index=8,ammo=name,data=rounds)])
        d['actions']=[diag('slot',section=2,slot=8,**({'attacker':attacker} if attacker else {}))]
        expected=rounds if gauss or rounds==0 else 0
        yield Case(d,lambda o,expected=expected:checks((sl(o,2,8)['firemode'],1),(sl(o,2,8)['data'],expected)),label=f'components-supp-bin-{gauss}-{rounds}-{attacker}')
    for selected in (0,4):
        d=document();mount(d,'autocannon',critical=0);mount(d,'autocannon',critical=4)
        d['actions']=[diag('enhanced',slot=selected,roll=9)]
        def check(o,selected=selected):
            for i in range(8):eq(sl(o,4,i)['firemode'],1 if i==selected else 4 if selected<i<selected+4 else 0)
        yield Case(d,check,label=f'enhanced-supp-neighbor-mount-{selected}')
    for loc,marker,parent in [(0,'SPLIT_CRIT_RIGHT',2),(1,'SPLIT_CRIT_LEFT',3)]:
        d=document();mount(d,'IS.AC/20',section_index=parent);section(d,loc,slots=[special(marker,data=0)])
        d['random']['streams']['enhanced_rolls']=[12];d['actions']=[diag('slot',section=loc)]
        yield Case(d,lambda o,parent=parent:eq(flag(sl(o,parent)['firemode'],1),True),label=f'components-supp-split-{loc}')
    d=document();d['units'][0].update(working_c3_masters=2,total_c3_masters=2)
    for loc in (2,3):section(d,loc,slots=[special('C3_MASTER',i) for i in range(5)])
    d['actions']=[diag('slot',section=2,slot=0),inspect(),diag('slot',section=2,slot=1)]
    yield Case(d,lambda o:checks((state(o,index=1)['working_c3_masters'],2),(state(o)['working_c3_masters'],1),(state(o)['total_c3_masters'],2)),label='components-supp-c3-before-destruction')
    for selected in (0,1):
        d=document();d['units'][0]['towed_unit']='enemy';d['units'][0]['measured_mass']=51200;d['units'][1]['measured_mass']=51200
        section(d,0,slots=[special('SHOULDER_OR_HIP'),special('HAND_OR_FOOT_ACTUATOR',1)])
        d['actions']=[diag('slot',section=0,slot=selected,attacker='enemy')]
        yield Case(d,lambda o:eq(state(o)['relationships']['towed_unit'],None),label=f'mobility-supp-tow-release-{selected}')
    d=document();d['units'][0]['fallen']=True;d['actions']=[cmd('stand'),diag('destroy-section',section=5,attacker='enemy'),advance(60)]
    yield Case(d,lambda o:checks((state(o)['fallen'],True),(events(state(o),'STAND'),[])),label='mobility-supp-destroy-leg-during-stand')



def all_cases():
    yield from command_cases()
    yield from armor_cases()
    yield from recovery_cases()
    yield from failure_cases()
    yield from external_cases()
    yield from routing_cases()
    yield from equipment_cases()
    from damage_tables import cases as tables
    from damage_targeting import cases as targeting
    from damage_lifecycle import cases as lifecycle
    yield from tables()
    yield from targeting()
    yield from lifecycle()
    from damage_audit import cases as audit
    yield from audit()
