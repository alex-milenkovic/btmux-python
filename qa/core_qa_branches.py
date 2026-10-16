"""Additional source branch procedures; all interactions use the public CLI."""
from copy import deepcopy
from core_simulation_qa import A,C,D,I,K,S,case,check as q
from core_qa_events import events
from core_qa_workflows import finite


def build():
    case('recovery','latest-deadline-and-independent-clock',
         [S('mech_recovery_event',30),S('mech_recovery_event',40),K('skip_seconds',seconds=100),K('heartbeat'),D('ProlongUncon',5)],
         [events('state','RECOVERY',[45],True),q('state.clocks',dict(wall=100,event=0,global_tick=1))])
    for destroyed,uncon in [(True,True),(False,False)]:
        case('recovery',f'callback-noop-{destroyed}-{uncon}',[I(),D('callback','mech_recovery_event')],
             [q('state.random.total_rolls',0),q('state.units.u.status',same_as='results.0.units.u.status')],units=[dict(name='u',status=8|(8192 if uncon else 0)|(32 if destroyed else 0))])
    for started in (False,True):
        for callback,text in [('mech_standfail_event','recovered from your attempt to stand'),('mech_jumpstabil_event','stabilized')]:
            case('movement_events',f'notice-{callback}-{started}',[D('callback',callback)],
                 [q('state.units.u.messages',1 if callback=='mech_standfail_event' else int(started),count_text=text)],units=[dict(name='u',started=started)])
    for kind,move in [('MECH','BIPED'),('MECH','QUAD'),('VEH_GROUND','TRACK')]:
        for offset,data in [(60,2),(0,8)]:
            case('movement_events',f'lateral-{kind}-{move}-{offset}',[D('callback','mech_lateral_event',data)],
                 [q('state.units.u.lateral',offset),events('state','SIDESLIP',int(move!='QUAD' and offset!=0))],units=[dict(name='u',**{'class':kind},movement=move)])
    for success,ace in [(True,False),(False,False),(True,True),(False,True)]:
        case('movement_events',f'sideslip-{success}-{ace}',[D('callback','mech_sideslip_event')],
             [q('state.units.u.speed',10 if success else 0),q('state.units.u.lateral',60 if success else 0),events('state','SIDESLIP',[30] if success else [],True),q('state.random.total_rolls',1)],
             units=[dict(name='u',**{'class':'VEH_GROUND'},speed=10,desired_speed=12,facing=350,core={'lateral':60},pilot_details={'maneuvering_ace':ace})],random={'streams':{'pilot_rolls':[12 if success else 2],'sideslip_rotation':[1]}})
    case('clocks','recycle-once-per-event-tick',[K('heartbeat'),I(),K('heartbeat'),I(),K('dispatch'),K('heartbeat'),I()],
         [q('results.1.units.u.sections.0.recycle',9),q('results.3.units.u.sections.0.recycle',9),q('results.6.units.u.sections.0.recycle',8)],units=[dict(name='u',sections=[dict(index=0,recycle=10)],core={'last_weapon_recycle':-1})])
    for stopped in (False,True):
        case('clocks','idle-vtol-fuel-'+str(stopped),[K('heartbeat'),I(),K('heartbeat')],
             [q('results.1.units.u.fuel',1 if stopped else 0),q('state.units.u.fuel',1 if stopped else -1),events('state','FALL',int(not stopped))],
             units=[dict(name='u',**{'class':'VTOL'},started=not stopped,fuel=1,at=[3,3,5])],random={'streams':{'fuel_check':[1,1]}})
    for level in (0,1,2,3,7):
        for tons in (35,36,55,56,75,76):
            offset=1 if tons<=35 else 0 if tons<=55 else -1 if tons<=75 else -2
            case('stagger',f'weight-boundary-{tons}-{level}',[D('calcNewStaggerBTHMod',level,True),D('calcNewStaggerBTHMod',level,False)],
                 [q('results',[level-1+offset,level-1])],units=[dict(name='u',tonnage=tons)])
    case('stagger','stopped-modifiers',[D('calcNewStaggerBTHMod',3),D('calcStaggerBTHMod')],[q('results',[999,999])],units=[dict(name='u',started=False)])
    for age in (59,60,61):
        for state,flag in [('standing',8),('fallen',8|128),('jumping',8|64)]:
            case('stagger',f'expiry-{state}-{age}',[D('get_stagger_damage',age),D('clear_old_stagger_damage',age)],
                 [q('results.0',20 if age<=60 else 0),q('state.units.u.stagger_damage_list',int(age<60),length=True)],
                 units=[dict(name='u',status=flag,core={'stagger_damage_list':[dict(amount=20,occurred_at=0,counted=False)]})])
    for operation,expected in [('mark_stagger_damage',[True,True,False]),('clear_stagger_damage',[False])]:
        case('stagger','whole-node-'+operation,[D(operation,1)],
             [q('state.units.u.stagger_damage_list',expected,project='counted')],units=[dict(name='u',core={'stagger_damage_list':[dict(amount=a,occurred_at=0,counted=False) for a in (15,10,5)]})])
    for amount in (19,20,40,60):
        for mode in (1,2):
            case('stagger',f'ordinary-threshold-{mode}-{amount}',[C('dodamage',amount,amount,4),I(),A(4),I(),A(1),I()],
                 [q('results.1.units.u.stagger_damage_list',[0],project='occurred_at'),q('results.3.random.total_rolls',1),q('state.random.total_rolls',1+int(amount>=20)),q('state.units.u.last_stagger_check',5),q('state.units.u.stagger_damage_list',int(mode==1 or amount<20),length=True)],
                 units=[dict(name='u',sections=[dict(index=4,armor=100,armor_orig=100)])],config={'new_stagger':mode},random=finite(pilot_rolls=[12]),mode='ordinary')
    for valid,xtype,allocated,text in [(False,'bad',False,'Index out of range!'),(True,'',False,'That is not a valid map! (no XTYPE!)'),(True,'map',False,'That is not a valid map!'),(True,'MAP',False,'The map has not been allocated!!'),(True,'MAP',True,'')]:
        case('targets',f'validmap-{valid}-{xtype.encode().hex()}-{allocated}',[D('ValidMap','main',valid,xtype,allocated)],
             [q('results.0',dict(id=1000 if not text else None,error=text))])
    for linked in (False,True):
        for x,y in [(-1,12),(12,-1),(-1,-1),(12,12)]:
            case('targets',f'edge-{linked}-{x}-{y}',[dict(op='core',values={'x':x,'y':y}),D('CheckEdgeOfMap')],
                 [q('state.units.u.at',[x%12,y%12,0] if linked else [max(0,min(11,x)),max(0,min(11,y)),0]),q('state.units.u.speed',20 if linked else 0),q('state.units.u.desired_speed',30 if linked else 0)],map={'linked':linked},units=[dict(name='u',speed=20,desired_speed=30)])
    for need in range(4):
        case('targets',f'hex-los-{need}',[D('find_mech_in_hex',3,2,need)],
             [q('results.0',3 if need&2 else 2)],map={'hexes':[dict(at=[3,2],terrain='GRASSLAND',elevation=3)]},units=[dict(name='u',team=1),dict(name='v',team=2,at=[3,2,3]),dict(name='friend',team=1,at=[4,3,0])])
    for mode in ('BIPED','QUAD'):
        for config in (2,4,8):
            positions=[5,6]+([0,1] if mode=='QUAD' else [])
            case('parts',f'legs-{mode}-{config}',[D('CountDestroyedLegs'),D('IsMechLegLess')],
                 [q('results',[len(positions),True])],units=[dict(name='u',movement=mode,sections=[dict(index=i,armor=0 if config==2 else 12,internal=0 if config==2 else 8,config=config) for i in positions])])
    case('parts','leg-exclusion-nonmech',[D('CountDestroyedLegs'),D('IsMechLegLess')],[q('results',[0,False])],units=[dict(name='u',**{'class':'VEH_GROUND'},sections=[dict(index=i,internal=0,config=2) for i in range(8)])])
    for flags in (0,1,2,4,8):
        case('parts',f'functional-and-all-counts-{flags}',[D('FindObj',4,401),D('FindObjWithDest',4,401)],
             [q('results',[1 if flags in (0,8) else 0,1])],units=[dict(name='u',sections=[dict(index=4,slots=[dict(index=0,special='ENGINE',firemode=flags)])])])
    for kind,move,high in [('MECH','BIPED',8),('VEH_GROUND','TRACK',5),('VEH_NAVAL','HULL',5),('VTOL','VTOL',6)]:
        case('parts',f'section-bounds-{kind}',[D('ArmorStringFromIndex',-1),D('ArmorStringFromIndex',high),D('ArmorStringFromIndex',high+1)],
             [q('results',['Invalid!!']*3)],units=[dict(name='u',**{'class':kind},movement=move)])
    for base in (1,3,5,11,65535):
        for mode,fire,ammo in [('plain',0,0),('half',128,0),('AP',0,8192),('precision',0,65536),('caseless',0,262144),('mml',0,4194304),('combined',128,8192|262144|4194304)]:
            value=base//2 if fire or ammo&(8192|65536) else base*2 if ammo&262144 else (base*12+5)//10 if ammo&4194304 else base
            case('ammunition',f'capacity-{base}-{mode}',[D('ammo_capacity',base,fire,ammo)],[q('results.0',value)])
    case('repair','refill-preserves-destroyed-bin',[C('refill',0,0)],[q('state.units.u.sections.0.slots.0.data',5),q('state.units.u.sections.0.slots.0.firemode',129)],
         units=[dict(name='u',ammo=[dict(weapon='IS.AC/10',rounds=0,section=0,critical=0)],sections=[dict(index=0,slots=[dict(index=0,firemode=129)])])],mode='ordinary')
    case('repair','all-weapon-repair-fields',[C('repair',0,0)],[q('state.units.u.sections.0.slots.0.data',0),q('state.units.u.sections.0.slots.0.brand',3),q('state.units.u.sections.0.slots.0.weap_damage_flags',0),q('state.units.u.sections.0.slots.0.firemode',32|256)],
         units=[dict(name='u',weapons=[dict(name='IS.SmallLaser',section=0)],sections=[dict(index=0,slots=[dict(index=0,data=19,brand=163,weap_damage_flags=123,firemode=1|2|4|8|32|64|256|512)])])],mode='ordinary')
    for price in (0,2**53+1,2**64-1):
        case('cost',f'table-persistence-{price}',[D('SetPartCost',1,price),I(),D('GetPartCost',1),D('initialize_part_costs'),D('GetPartCost',1)],
             [q('results.2',price),q('results.4',0),q('state.costs',{})])
    for part in (-1,1024):
        case('cost',f'unsafe-table-index-{part}',[D('GetPartCost',part)],[],error='outside')
    case('integration','stand-shutdown-cancellation',[C('stand'),A(1),I(),C('shutdown'),A(30)],
         [q('results.0.accepted',True),events('results.2','STAND',1),q('results.3.accepted',True),events('state','STAND',0),q('state.units.u.messages',0,count_text='finished standing'),q('state.units.u.damage_taken',0)],
         units=[dict(name='u',fallen=True,piloting=2)],random={'seed':5489},mode='ordinary')
    case('integration','jump-shutdown-single-impact',[C('jump',0,3),A(1),I(),C('shutdown'),I(),A(30)],
         [q('results.0.accepted',True),events('results.2','JUMP',1),events('results.4','JUMP',0),events('results.4','FALL',[4],True),q('state.units.u.at.2',0),q('state.units.u.messages',1,count_text='Mech fell'),q('state.units.u.last_fall_levels',3),q('state.units.u.damage_taken',16),events('state','FALL',0)],
         units=[dict(name='u',jump_mp=5,weapons=['IS.MediumLaser']),dict(name='v',at=[3,2,0],team=2)],random={'seed':5489},mode='ordinary')
    case('integration','jump-combat-dfa',[C('jump','01'),A(20)],
         [q('results.0.accepted',True),q('state.units.u.at',[3,2,0]),q('state.units.u.messages',1,count_text='You land on your target legs first!'),q('state.units.u.damage_taken',10),q('state.units.v.damage_taken',positive=True),events('state','JUMP',0)],
         units=[dict(name='u',jump_mp=5,piloting=2,weapons=['IS.MediumLaser']),dict(name='v',at=[3,2,0],team=2)],random={'seed':5489},mode='ordinary')
    case('integration','repeated-injury-keeps-deadline',
         [C('dodamage',1,1,7),A(10),I(),C('dodamage',1,1,7),I(),C('speed',10),C('fire',0,'01'),A(19),I(),A(1),I(),C('speed',10),C('fire',0,'01')],
         [q('results.2.units.u.pilot_hits',1),q('results.4.units.u.pilot_hits',2),events('results.4','RECOVERY',[30],True),q('results.4.random.total_rolls',3),q('results.5.accepted',False),q('results.6.accepted',False),q('results.8.units.u.status',8192,mask=8192),q('results.10.units.u.status',0,mask=8192),q('results.10.units.u.pilot_hits',2),events('results.10','RECOVERY',0),q('results.11.accepted',True),q('results.12.accepted',True),q('state.units.u.messages',1,count_text='pilot regains consciousness')],
         units=[dict(name='u',weapons=['IS.MediumLaser']),dict(name='v',at=[3,2,0],team=2)],
         random=finite(rolls=[2,12],attack_rolls=[12],failure_reliability=[12]*10,failure_weapon_chance=[1],hit_location_rolls=[7]),mode='ordinary')
    case('recovery','ordinary-pilot-death',[C('dodamage',1,1,7) for _ in range(6)],
         [q('state.units.u.pilot_hits',6),q('state.units.u.destroyed',True),q('state.units.u.pilot',None),q('state.units.u.speed',0),q('state.units.u.messages',1,count_text='killed from personal injuries')],
         units=[dict(name='u',sections=[dict(index=7,armor=100,armor_orig=100)])],random=finite(rolls=[12]*6),mode='ordinary')
    case('integration','seeded-shared-consumers',
         [C('stand'),A(24),C('fire',0,'01'),C('sensor','I','E'),A(12),C('contacts'),C('rollstats'),I(),C('rollstats'),I()],
         [q('results.0.accepted',True),q('results.2.accepted',True),q('results.5.contacts',2,length=True),q('draws',positive=True,where={'name':'pilot_rolls'},length=True),q('draws',positive=True,where={'name':'attack_rolls'},length=True),q('draws',positive=True,where={'name':'sensor.detect'},length=True),q('draws',positive=True,where={'name':'sensor.random'},length=True),q('results.6',same_as='results.8'),q('results.7.random',same_as='results.9.random'),dict(shared_source=True)],
         units=[dict(name='u',fallen=True,piloting=2,jump_mp=5,weapons=['IS.MediumLaser'],sensors=['I','E']),dict(name='v',at=[3,2,0],team=2),dict(name='w',at=[10,10,0],team=2,heat=30)],
         map={'light':0,'mapvis':10},config={'random_state':True},random={'seed':5489},mode='ordinary',repeat=True)
    case('randomness','fresh-inspection-repeat',[I(),I()],
         [q('results.0',same_as='results.1'),q('state.clocks',dict(wall=0,event=0,global_tick=0)),q('state.random.words_consumed',0)],repeat=True)
    # C history initializer must overwrite every slot, not merely used types.
    case('hooks','all-100-initialized',[D('history_input',[17]*100),D('muxevent_count_initialize'),D('debug_EventTypes','history')],
         [q('state.event_history',[0]*100),q('results.2',['Event history (by use)'])])
    counts=[(i*13)%17+1 for i in range(81)]+[0]*19;order=list(range(100))
    for i in range(99):
        for j in range(i+1,100):
            if counts[order[i]]>counts[order[j]]:order[i],order[j]=order[j],order[i]
    case('hooks','complete-nested-swap-order',[D('history_input',counts),D('debug_EventTypes','history')],
         [q(f'results.1.{i+1}',t,leading_integer=True) for i,t in enumerate(t for t in order if counts[t])]+[q('state.event_history',counts)])
    case('hooks','callback-replaces-same-type-peers',[S('mech_recovery_event',1),S('mech_recovery_event',10),K('dispatch')],
         [events('state','RECOVERY',[40],True),q('state.event_trace',[2,2,1],where={'kind':'RECOVERY'},project='pending_same_type'),q('state.event_history',[0]*100),q('state.random.total_rolls',1)],
         units=[dict(name='u',status=8|8192,pilot_hits=4)],random={'streams':{'rolls':[2]}})
    intact=dict(name='u',weapons=[dict(name='IS.AC/5',section=4,critical=0)],ammo=[dict(weapon='IS.AC/5',section=2,critical=0,rounds=20)],core={'template_ref':'intact','engine_rating':200})
    damaged=deepcopy(intact);damaged['ammo'][0]['rounds']=1
    case('integration','gameplay-damage-repair-move-heat-fire',
         [I(),C('fire',0,'01'),I(),A(30),C('damage-section',4,1,0,1),C('damage-section',5,1,0,1),I(),C('fire',0,'01')]+[C('repair',4,i) for i in range(4)]+[C('repair',5,1),C('refill',2,0),C('weaponstatus'),I(),C('speed',10),A(2),C('fire',0,'01'),I()],
         [q('results.1.accepted',True),q('results.2.units.u.sections.2.slots.0.data',0),q('results.6.units.u.sections.4.slots.0.firemode',1,mask=1),q('results.6.units.u.sections.5.slots.1.firemode',1,mask=1),q('results.6.units.u.max_speed',53.75),q('results.7.accepted',False),q('results.15.units.u.sections.2.slots.0.data',20),q('results.15.units.u.max_speed',64.5),q('results.18.accepted',True),q('state.units.u.sections.2.slots.0.data',19),q('state.units.u.shots_fired',2),q('state.units.u.speed',positive=True),q('state.units.u.weap_heat',1),q('state.templates',same_as='results.0.templates')],
         units=[damaged,dict(name='v',at=[3,2,0],team=2)],templates=[dict(name='intact',unit=intact)],
         random=finite(attack_rolls=[12]*10,failure_weapon_chance=[1]*10,failure_reliability=[12]*100,enhanced_rolls=[12]*100,hit_location_rolls=[7]*100,critical_rolls=[8,8]+[7]*100,critical_slot=[0,1],pilot_rolls=[12]*100),mode='ordinary')
