"""Complete core workflows through the public session's commands and clocks."""
from . import step, eq
from tools.core_simulation import CoreSession
from entities.mech import FireMode


def finite(**streams):
    return dict(streams=dict(visibility_change=[0]*100,failure_generic_chance=[5000]*10,
                            damage_entry=[7]*10,tow_rolls=[7]*10,**streams))


def act(world,op,**fields):
    reply = world['session'].action(dict(op=op,**fields))
    world.setdefault('replies',[]).append(reply)
    return reply


@step(r'normal workflow (\S+)')
def workflow(world,name):
    world['workflow'] = name
    docs = {
        'startup-lock-fire-shutdown':dict(units=[{'name':'u','started':False,'weapons':['IS.MediumLaser']},
                                                {'name':'v','at':[3,2,0],'team':2}],random={'seed':5489}),
        'knockout-extend-recover':dict(random=finite(rolls=[2,2,12])),
        'stun-twice':dict(units=[{'name':'u','class':'VEH_GROUND'}],config={'fasaadvvhlcrit':1},
                          random=finite(critical_rolls=[8,8],vehicle_critical_roll=[8,8])),
        'damage-stagger-fall':dict(units=[{'name':'u','sections':[{'index':4,'armor':100,'armor_orig':100}]}],
                                 random=finite(pilot_rolls=[2,12],fall_directions=[1],hit_location_rolls=[7])),
        'repair-refill-fire':dict(units=[{'name':'u','weapons':[{'name':'IS.AC/5','fire_mode':int(FireMode.DESTROYED_MODE)}],
                                         'ammo':[{'weapon':'IS.AC/5','rounds':0}]},
                                        {'name':'v','at':[3,2,0],'team':2}],random={'seed':5489}),
        'seeded-fire-pilot-statistics':dict(units=[{'name':'u','fallen':True,'piloting':2,'weapons':['IS.MediumLaser']},
                                                 {'name':'v','at':[3,2,0],'team':2}],random={'seed':5489}),
    }
    if name not in docs: raise AssertionError('unknown workflow '+name)
    world['session'] = CoreSession(dict(actions=[],**docs[name]))


@step(r'the documented commands and clock steps execute')
def execute(world):
    name,unit = world['workflow'],world['session'].units['u']
    if name=='startup-lock-fire-shutdown':
        eq(act(world,'command',name='startup')['accepted'],True)
        act(world,'advance',seconds=29)
        eq(unit.is_started,False)
        eq(act(world,'command',name='fire',args=[0])['accepted'],False)
        act(world,'advance',seconds=2)
        eq(act(world,'command',name='lock',args=['01'])['accepted'],True)
        act(world,'advance',seconds=8)
        world['shot'] = act(world,'command',name='fire',args=[0])
        eq(act(world,'command',name='shutdown')['accepted'],True)
    elif name=='knockout-extend-recover':
        act(world,'command',name='dodamage',args=[1,1,7])
        act(world,'advance',seconds=30)
        snapshot = act(world,'inspect')
        eq([e['deadline'] for e in snapshot['events'] if e['kind']=='RECOVERY'],[60])
        eq(unit.is_unconscious,True)
        act(world,'advance',seconds=30)
    elif name=='stun-twice':
        for _ in range(2): act(world,'command',name='damage-section',args=[1,1,0,1])
        eq(unit.crew_stunned,True)
        act(world,'advance',seconds=60)
    elif name=='damage-stagger-fall':
        act(world,'command',name='dodamage',args=[20,20,4])
        eq(sum(n['amount'] for n in unit.stagger_damage_list),20)
        act(world,'advance',seconds=5)
    elif name=='repair-refill-fire':
        eq(act(world,'command',name='fire',args=[0,'01'])['accepted'],False)
        eq(act(world,'command',name='repair',args=[4,0])['accepted'],True)
        act(world,'command',name='refill',args=[2,0])
        eq(unit.sections[2].criticals[0].data,20)
        world['shot'] = act(world,'command',name='fire',args=[0,'01'])
    elif name=='seeded-fire-pilot-statistics':
        eq(act(world,'command',name='stand')['accepted'],True)
        act(world,'advance',seconds=24)
        world['shot'] = act(world,'command',name='fire',args=[0,'01'])
        world['stats'] = act(world,'command',name='rollstats')
    else: raise AssertionError(name)


@step(r'real outcome (\S+) is observed with no duplicate effects')
def outcome(world,name):
    session = world['session']
    unit = session.units['u']
    if name=='delayed-ready-shot-stopped':
        eq(world['shot']['accepted'],True)
        eq(world['shot']['attack']['hit'],True)
        eq(unit.shots_fired,1)
        eq(unit.is_started,False)
        eq(len(unit.boot_messages),6)
    elif name=='one-late-recovery':
        eq(unit.is_unconscious,False)
        eq(unit.pilot_hits,1)
        eq(unit.movement_messages.count('The pilot regains consciousness!'),1)
    elif name=='one-final-clear':
        eq(unit.crew_stunned,False)
        eq(unit.damage_taken,2)
        eq(unit.movement_messages.count("Your head clears and you're able to control your vehicle again."),1)
    elif name=='actual-fall-damage':
        eq((unit.is_fallen,unit.damage_taken,unit.sections[4].armor),(True,25,75))
        eq(sum(m.startswith('Mech fell') for m in unit.movement_messages),1)
    elif name=='repaired-mount-spends-bin':
        eq(world['shot']['accepted'],True)
        eq(unit.sections[4].criticals[0].firemode & FireMode.DESTROYED_MODE,0)
        eq(unit.sections[2].criticals[0].data,19)
        eq(unit.shots_fired,1)
    elif name=='shared-stream-and-roll-count':
        eq(world['shot']['accepted'],True)
        state = session.engine.randomness
        draws = [draw for draw in session.draws if (draw['low'],draw['high'])==(2,12)]
        assert any(draw['name']=='pilot_rolls' for draw in draws)
        assert any(draw['name']=='attack_rolls' for draw in draws)
        eq(state.total_rolls,len(draws))
        eq(state.total_rolls,sum(state.rolls))
        eq(state.mt.words_consumed,sum(draw['raw_words'] for draw in session.draws))
        eq(world['stats']['result'][-1],f'Total rolls: {state.total_rolls}')
    else: raise AssertionError('unknown outcome '+name)


@step(r'required service (\S+) is unavailable')
def unavailable(world,service): world['service'] = service


@step(r'workflow (\S+) reaches that boundary')
def boundary(world,workflow):
    docs = {
        'startup-player-init':dict(units=[{'name':'u','started':False}],actions=[{'op':'command','name':'startup'},{'op':'advance','seconds':30}]),
        'channel-kill':dict(units=[{'name':'u'},{'name':'v','at':[3,2,0],'team':2}],
            actions=[{'op':'diagnose','kind':'ChannelEmitKill','args':['v','test']}]),
        'successful-pilot-roll':dict(units=[{'name':'u','fallen':True}],random=finite(pilot_rolls=[12]),actions=[{'op':'command','name':'stand'}]),
        'AUTO-heartbeat':dict(objects=[{'name':'auto','id':42,'type':'AUTO','mymech':'u'}],actions=[{'op':'clock','name':'heartbeat'}]),
        'hangar-exit':dict(maps=[{'name':'bay','id':1000,'flags':1,'cf':10,'leave_target':1001},
            {'name':'outside','id':1001,'entrances':[{'target':1000,'x':5,'y':6,'name':'Bay'}]}],
            actions=[{'op':'diagnose','kind':'Leave_Hangar'}]),
    }
    if workflow not in docs: raise AssertionError(workflow)
    doc = docs[workflow]
    world['session'] = CoreSession(doc)
    world['boundary_workflow'] = workflow
    for action in doc['actions']: world['session'].action(action)


@step(r'the unavailable operation is reported with applied false and available local effects remain')
def boundary_result(world):
    session,service = world['session'],world['service']
    unit = session.units['u']
    effects = getattr(unit,'external_effects',[])
    if service=='persistent-character':
        eq(unit.is_started,True)
        relevant = [e for e in effects if e['operation']=='initialize_pc']
    elif service=='MUX-channels-and-hooks':
        eq(session.units['v'].units_killed,1)
        relevant = [e for e in effects if 'AMECHDEST' in e['operation']]
    elif service=='persistent-XP':
        eq(unit.is_fallen,False)
        eq(len(unit.xp_requests),1)
        relevant = unit.xp_requests
    elif service=='autopilot-gameplay':
        eq(session.engine.global_tick,1)
        relevant = session.objects['auto'].external_effects
        eq(len(relevant),3)
    elif service=='persistent-map-objects':
        eq((unit.map.name,unit.x,unit.y),('outside',5,6))
        relevant = [e for e in effects if e['operation']=='loud_teleport']
    else: raise AssertionError(service)
    assert relevant
    assert all(e['applied'] is False for e in relevant)
