"""Independent stateful CLI workflows and movement/stagger/target examples."""
from core_simulation_qa import A,C,D,I,K,S,case,check as q,examples
from core_qa_events import events


def finite(**streams):
    return dict(streams=dict(visibility_change=[0]*200,failure_generic_chance=[5000]*50,
         damage_entry=[7]*100,tow_rolls=[7]*100,**streams))


def build():
    for n,r in enumerate(examples('movement_events',1)):
        case('movement_events',f'example-01-{n}',[D('callback','mech_fall_event',int(r['speed']))],
             [q('state.units.u.at.2',int(r['remaining'])),q('state.units.u.last_fall_levels',int(r['impact'])),q('state.events',[] if r['next']=='none' else [int(r['next'])],where={'kind':'FALL'},project='data2')],
             units=[dict(name='u',started=False,at=[3,3,int(r['height'])],sections=[dict(index=i,armor=100,armor_orig=100,internal=50,internal_orig=50) for i in range(8)])],
             random=finite(rolls=[12]*100,pilot_rolls=[12]*20,fall_directions=[1]*20,hit_location_rolls=[7]*100))
    for n,r in enumerate(examples('movement_events',2)):
        case('movement_events',f'example-02-{n}',[I(),S('mech_stand_event'),K('dispatch')],
             [q('state.units.u.fallen',False),q('state.maps.main.moves',1),q('state.units.u.messages',1,count_text='finally finished standing')],
             units=[dict(name='u',fallen=bool(int(r['fallen'])))])
    for n,r in enumerate(examples('movement_events',3)):
        case('movement_events',f'example-03-{n}',[D('callback','mech_jump_event')],[events('state','JUMP',int(r['pending']))],
             units=[dict(name='u',status=8|64,jump_speed=64.5,core=dict(jump_top=64.5,jump_length=1 if int(r['ended']) else 1000,start_fx=1024.0750732421875,start_fy=967.5,going_x=3,going_y=2))])
    for n,r in enumerate(examples('stagger',1)):
        case('stagger',f'example-01-{n}',[D('calcNewStaggerBTHMod',int(r['level']),True),D('calcNewStaggerBTHMod',int(r['level']),False),D('calcStaggerBTHMod')],
             [q('results',list(map(int,r['mods'].split(','))))],units=[dict(name='u',tonnage=int(r['tons']),core={'stagger_damage':int(r['level'])*20})])
    for n,r in enumerate(examples('stagger',2)):
        case('stagger',f'example-02-{n}',[K('skip_seconds',seconds=5),K('heartbeat')],[q('state.units.u.stagger_damage_list',int(r['points']),project='amount',sum=True),q('state.units.u.messages',contains='You stagger from the damage!'),q('state.random.total_rolls',1)],
             units=[dict(name='u',core={'stagger_damage_list':[dict(amount=20,occurred_at=0,counted=False),dict(amount=20,occurred_at=0,counted=True)]})],config={'new_stagger':int(r['mode'])},random=finite(pilot_rolls=[12]))
    for n,r in enumerate(examples('stagger',3)):
        case('stagger',f'example-03-{n}',[D('callback','check_stagger_event')],[q('state.units.u.stagger_damage',int(r['remaining'])),q('state.random.total_rolls',int(r['draws']))],
             units=[dict(name='u',fallen=r['state']=='fallen',status=8|(64 if r['state']=='jumping' else 0)|(0x80 if r['state']=='fallen' else 0),core={'stagger_damage':int(r['damage'])})],random=finite(pilot_rolls=[12]))
    for n,r in enumerate(examples('targets',1)):
        target={'minus1':-1,'missing-unit':999,'registered-unit':'v'}[r['target']]
        checks=[q('results.1',None)] if r['result']=='none' else [q('results.1.2',193.5 if r['result']=='hex-z3' else 129)]
        case('targets',f'example-01-{n}',[dict(op='configure',unit='u',values={'target':target,'targ_x':3,'targ_y':2,'targ_z':3}),D('FindTargetXY')],checks,
             units=[dict(name='u'),dict(name='v',at=[3,2,2])])
    for n,r in enumerate(examples('targets',2)):
        case('targets',f'example-02-{n}',[dict(op='core',unit='v',values={'contact_id':'Ab'}),D('FindMechOnMap',r['text'])],[q('results.1',1 if int(r['ordinal'])==0 else -1)],
             units=[dict(name='u',contact_id='AB'),dict(name='v',contact_id='AC',at=[3,2,0])])
    for n,r in enumerate(examples('targets',3)):
        case('targets',f'example-03-{n}',[D('MarkForLOSUpdate')]*4+[dict(op='core',values={'mapflag':int(r['flags'])}),I(),D('MarkForLOSUpdate')],
             [q('results.5.maps.main.moves',4),q('state.maps.main.moves',5),q('state.units.u.mapflag',1)])
    # Workflow 1: all six boot phases, PLOS, lock/fire, shutdown and new boot sequence.
    actions=[C('startup')]
    checks=[q('results.0.accepted',True)]
    for phase in range(6):
        actions += [A(4 if phase==0 else 4),I(),A(1),I()]
        before,after=len(actions)-3,len(actions)-1
        checks += [q(f'results.{before}.units.u.started',False),q(f'results.{before}.units.u.boot_messages',phase,length=True),q(f'results.{after}.units.u.boot_messages',phase+1,length=True)]
    actions += [A(1),C('lock','01'),A(8),I(),C('fire',0),I(),C('shutdown'),I(),C('startup'),A(30),I()]
    fire=len(actions)-7; before=fire-1; after=fire+1; shutdown=fire+3
    checks += [q(f'results.{fire}.accepted',True),q(f'results.{after}.units.u.shots_fired',1),q(f'results.{after}.units.v.damage_taken',positive=True),q(f'results.{shutdown}.units.u.started',False),q('state.units.u.started',True),q('state.units.u.boot_messages',12,length=True),events('state','STARTUP',0)]
    case('integration','example-01-0',actions,checks,units=[dict(name='u',started=False,weapons=['IS.MediumLaser']),dict(name='v',at=[3,2,0],team=2)],random={'seed':5489},mode='ordinary')
    # Workflow 2: damage, failed injury recovery, then one successful recovery.
    case('integration','example-01-1',[C('dodamage',1,1,7),A(30),I(),A(30)],
         [events('results.2','RECOVERY',[60],True),q('results.2.units.u.status',8192,mask=8192),q('state.units.u.status',0,mask=8192),q('state.units.u.pilot_hits',1),q('state.units.u.messages',1,count_text='pilot regains consciousness')],random=finite(rolls=[2,2,12]),mode='ordinary')
    case('integration','example-01-2',[C('damage-section',1,1,0,1),C('damage-section',1,1,0,1),I(),A(60)],
         [events('results.2','UNSTUN_CREW',2),q('state.units.u.damage_taken',2),q('state.units.u.tank_crit_status',0,mask=16),q('state.units.u.messages',1,count_text='Your head clears')],
         units=[dict(name='u',**{'class':'VEH_GROUND'})],config={'fasaadvvhlcrit':1},random=finite(critical_rolls=[8,8],vehicle_critical_roll=[8,8]),mode='ordinary')
    case('integration','example-01-3',[C('dodamage',20,20,4),I(),A(5)],
         [q('results.1.units.u.stagger_damage_list',20,project='amount',sum=True),q('state.units.u.fallen',True),q('state.units.u.damage_taken',25),q('state.units.u.sections.4.armor',75),q('state.units.u.messages',1,count_text='Mech fell')],
         units=[dict(name='u',sections=[dict(index=4,armor=100,armor_orig=100)])],random=finite(pilot_rolls=[2,12],fall_directions=[1],hit_location_rolls=[7]),mode='ordinary')
    case('integration','example-01-4',[C('fire',0,'01'),C('repair',4,0),C('refill',2,0),I(),C('fire',0,'01'),I()],
         [q('results.0.accepted',False),q('results.1.accepted',True),q('results.3.units.u.sections.2.slots.0.data',20),q('results.4.accepted',True),q('state.units.u.sections.2.slots.0.data',19),q('state.units.u.sections.4.slots.0.firemode',0,mask=1),q('state.units.u.shots_fired',1)],
         units=[dict(name='u',weapons=[dict(name='IS.AC/5',fire_mode=1)],ammo=[dict(weapon='IS.AC/5',rounds=0)]),dict(name='v',at=[3,2,0],team=2)],random={'seed':5489},mode='ordinary')
    case('integration','example-01-5',[C('stand'),A(24),C('fire',0,'01'),C('rollstats'),I(),C('rollstats'),I()],
         [q('results.0.accepted',True),q('results.2.accepted',True),q('results.3',same_as='results.5'),q('results.4.random',same_as='results.6.random'),q('state.random.total_rolls',positive=True),q('draws',positive=True,where={'name':'pilot_rolls'},length=True),q('draws',positive=True,where={'name':'attack_rolls'},length=True)],
         units=[dict(name='u',fallen=True,piloting=2,weapons=['IS.MediumLaser']),dict(name='v',at=[3,2,0],team=2)],random={'seed':5489},mode='ordinary')
    boundary_cases=[
        ([C('startup'),A(30)],[q('state.units.u.started',True),q('state.units.u.external_effects',positive=True,where={'operation':'initialize_pc','applied':False},length=True)],dict(units=[dict(name='u',started=False)])),
        ([D('ChannelEmitKill','v','test')],[q('state.units.v.units_killed',1),q('state.units.u.hook_requests',positive=True,length=True)],dict(units=[dict(name='u'),dict(name='v',at=[3,2,0],team=2)])),
        ([C('stand')],[q('results.0.accepted',True),q('state.units.u.xp_requests',positive=True,length=True)],dict(units=[dict(name='u',fallen=True)],random=finite(pilot_rolls=[12]))),
        ([K('heartbeat')],[q('state.clocks.global_tick',1),q('state.objects.auto.external_effects',[False]*3,project='applied')],dict(objects=[dict(name='auto',id=42,type='AUTO',mymech='u')])),
        ([D('Leave_Hangar')],[q('state.units.u.map','outside'),q('state.units.u.at',[5,6,0]),q('state.units.u.external_effects',positive=True,where={'operation':'loud_teleport','applied':False},length=True)],dict(maps=[dict(name='bay',id=1000,flags=1,cf=10,leave_target=1001),dict(name='outside',id=1001,entrances=[dict(target=1000,x=5,y=6,name='Bay')])])),
    ]
    for n,(actions,checks,fixture) in enumerate(boundary_cases):case('integration',f'example-02-{n}',actions,checks,mode='blocked',**fixture)
