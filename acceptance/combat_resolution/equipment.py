"""Equipment APS steps drive real commands and scheduled callbacks."""
from types import SimpleNamespace
from . import step,unit,session,call,dice,eq
from systems import combat_equipment as equipment
from entities.mech import MechStatus as S,Specials,MoveType,FireMode,Location as L
from core.events import EventType as E


def advance(w,tick):
    s=session(w)
    call(w,s.engine.run_ticks,int(tick)-s.engine.events.tick)


@step(r'MASC tech with desired speed 30 and counter 0')
def masc_fixture(w):
    u=unit(w)
    u.specials|=Specials.MASC_TECH
    u.desired_speed=30
    u.masc_counter=0


@step(r'MASC turns on and first failure roll is 12 then turns off at tick 2')
def toggle_masc(w):
    dice(w,'booster_rolls',[12])
    eq(call(w,equipment.command,unit(w),'masc')['accepted'],True)
    eq(unit(w).desired_speed,40)
    advance(w,2)
    eq(call(w,equipment.command,unit(w),'masc')['accepted'],True)


@step(r'desired speed is 30 MASC is off and counter at tick (\d+) is (\d+)')
def regen_result(w,tick,counter):
    advance(w,tick)
    eq(unit(w).desired_speed,30)
    eq(bool(unit(w).status&S.MASC_ENABLED),False)
    eq(unit(w).masc_counter,int(counter))


@step(r'both booster counters zero and (MASC|supercharger) enabled with a failure event due now')
def both_counters(w,kind):
    u=unit(w)
    u.masc_counter=u.scharge_counter=0
    u.specials|=Specials.MASC_TECH
    u.specials2|=0x40
    w['booster']='masc' if kind=='MASC' else 'scharge'
    u.status|=S.MASC_ENABLED if kind=='MASC' else S.SCHARGE_ENABLED


@step(r'booster failure roll is 12')
def booster_roll(w):
    dice(w,'booster_rolls',[12])
    call(w,equipment.booster_event,SimpleNamespace(data=unit(w),data2=w['booster']))


@step(r'MASC counter is 1 supercharger counter is 0 and next event is due in 60')
def shared_counter(w):
    eq(unit(w).masc_counter,1)
    eq(unit(w).scharge_counter,0)
    eq(session(w).engine.events.time_until_type_data(equipment.BOOSTERS[w['booster']][3],unit(w)),60)


@step(r'a (biped|quad) with MASC enabled and speed ([\d.]+)')
def failure_fixture(w,chassis,speed):
    u=unit(w)
    u.specials|=Specials.MASC_TECH
    u.status|=S.MASC_ENABLED
    u.move_type=MoveType.QUAD if chassis=='quad' else MoveType.BIPED
    u.speed=float(speed)
    from entities.crittypes import Special,i2special
    for loc in (L.LARM,L.RARM,L.LLEG,L.RLEG):
        u.sections[loc].criticals[0].type=i2special(Special.SHOULDER_OR_HIP)


@step(r'first MASC failure roll is 2')
def masc_failure(w):
    dice(w,'booster_rolls',[2])
    call(w,equipment.booster_event,SimpleNamespace(data=unit(w),data2='masc'))


@step(r'MASC tech is lost all speeds are zero damaged hip slots are (\d+) and fall occurs ([01])')
def failure_result(w,hips,fallen):
    u=unit(w)
    eq(bool(u.specials&Specials.MASC_TECH),False)
    eq((u.speed,u.desired_speed,u.max_speed),(0,0,0))
    eq(sum(bool(u.sections[loc].criticals[0].firemode&FireMode.DESTROYED_MODE) for loc in (L.LARM,L.RARM,L.LLEG,L.RLEG)),int(hips))
    eq(u.is_fallen,bool(int(fallen)))


@step(r'a stopped MASC unit with counter (\d+) and an already pending failure event')
def stopped_fixture(w,initial):
    u=unit(w)
    u.specials|=Specials.MASC_TECH
    u.masc_counter=int(initial)
    u.clear_status(S.STARTED)
    session(w).engine.events.schedule(1,E.MASC_FAIL,equipment.booster_event,u,'masc')


@step(r'that event runs with roll 2')
def stopped_run(w):
    dice(w,'booster_rolls',[2])
    advance(w,1)


@step(r'counter is (\d+) MASC tech remains and no next failure event exists')
def stopped_result(w,final):
    eq(unit(w).masc_counter,int(final))
    eq(bool(unit(w).specials&Specials.MASC_TECH),True)
    eq(session(w).engine.events.has_event_type_data(E.MASC_FAIL,unit(w)),False)


TRANSITIONS={'stealtharmor':E.STEALTH_ARMOR,'nullsig':E.NSS,'dig':E.DIG,
             'fixturret':E.UNJAM_TURRET,'slite':E.SLITE_CHANGE,'heatcutoff':E.HEAT_CUTOFF}


def active(u,name):
    from entities.mech import CritStatus
    return bool(u.status2&64) if name=='stealtharmor' else bool(u.status2&128) if name=='nullsig' else u.dug_in if name=='dig' else not u.tank_crit_status&2 if name=='fixturret' else bool(u.status2&32) if name=='slite' else bool(u.crit_status&CritStatus.HEATCUTOFF)


@step(r'valid equipment for (\w+) and no pending actions')
def transition_fixture(w,name):
    u=unit(w)
    u.specials|=Specials.ECM_TECH|Specials.SLITE_TECH
    u.specials2|=0x11
    u.tank_crit_status=2
    w['transition']=name


@step(r'(stealtharmor|nullsig|dig|fixturret|slite|heatcutoff) is requested at tick 0')
def request_transition(w,name):
    u=unit(w)
    if name=='slite':
        from systems.sensors import slite
        eq(call(w,slite,session(w).engine,u)[0],True)
    elif name=='heatcutoff':
        from systems.heat_control import heat_cutoff
        eq(call(w,heat_cutoff,session(w).engine,u)[0],True)
    else:eq(call(w,equipment.command,u,name)['accepted'],True)


@step(r'transition remains pending at (\d+) and completes at (\d+)')
def transition_result(w,before,due):
    name=w['transition'];queue=session(w).engine.events
    advance(w,before)
    eq(active(unit(w),name),False)
    eq(queue.has_event_type_data(TRANSITIONS[name],unit(w)),True)
    advance(w,due)
    eq(active(unit(w),name),True)
    eq(queue.has_event_type_data(TRANSITIONS[name],unit(w)),False)


@step(r'(stealth|nullsig) activation pending at tick 30')
def pending_signature(w,name):
    name='stealtharmor' if name=='stealth' else name
    transition_fixture(w,name)
    request_transition(w,name)


@step(r'condition (shutdown|Guardian-destroyed|system-destroyed) is introduced before completion')
def interrupt_signature(w,condition):
    from entities.mech import CritStatus
    if condition=='shutdown':unit(w).clear_status(S.STARTED)
    else:unit(w).crit_status |= CritStatus.ECM_DESTROYED if condition=='Guardian-destroyed' else CritStatus.NSS_DESTROYED
    advance(w,30)


@step(r'the system remains inactive and completion does not reschedule')
def signature_cancelled(w):
    name=w['transition']
    eq(active(unit(w),name),False)
    eq(session(w).engine.events.has_event_type_data(TRANSITIONS[name],unit(w)),False)


def add_ammo(w,name='IS.Sniper'):
    from entities.weapon import get_weapon
    from entities.crittypes import i2ammo
    slot=unit(w).sections[L.LTORSO].criticals[9]
    slot.type=i2ammo(get_weapon(name).index)
    slot.data=10
    return slot


@step(r'a jammed single-shot RAC numbered (\d+) with ordinary ammo and gunnery 4 and unjam requested at tick 0')
def unjam_fixture(w,index):
    from .modes import mount
    from systems.enhanced_crits import set_part_temp_nuke,FAIL_AMMOJAMMED
    for loc in range(int(index)):mount(w,'IS.MediumLaser',loc)
    slot=mount(w,'IS.RotaryAC/5',L.CTORSO)
    set_part_temp_nuke(slot,FAIL_AMMOJAMMED)
    unit(w).pilot.gunnery=4
    w['jammed']=slot
    w['ammo']=add_ammo(w,'IS.RotaryAC/5')
    eq(call(w,equipment.unjam_ammo,unit(w),index)['accepted'],True)


@step(r'tick 60 uses unjam roll (\d+)')
def unjam_run(w,rolled):
    dice(w,'unjam_rolls',[int(rolled)])
    advance(w,60)


@step(r'jam remains ([01]) and rounds consumed are (\d+)')
def unjam_result(w,jam,rounds):
    from systems.enhanced_crits import part_temp_nuke
    eq(bool(part_temp_nuke(w['jammed'])),bool(int(jam)))
    eq(10-w['ammo'].data,int(rounds))


@step(r'a MECH with ammo and enabled destruction configuration')
def explode_fixture(w):
    add_ammo(w)
    for key,value in dict(explode_ammo=1,explode_reactor=1,explode_time=120).items():setattr(session(w).engine,key,value)


@step(r'explode text is (ammo|reactor) at tick 0')
def explode_request(w,text):eq(call(w,equipment.explode,unit(w),text)['accepted'],True)


@step(r'pilot control is relinquished and terminal source branch at tick (\d+) is reactor')
def explosion_result(w,due):
    eq(unit(w).pilot,None)
    advance(w,int(due)-1)
    eq(unit(w).is_destroyed,False)
    advance(w,due)
    eq(unit(w).is_destroyed,True)
    eq(unit(w).sections[L.CTORSO].internal,0)
    eq(any('Suddenly you feel great heat' in message for message in unit(w).movement_messages),True)


@step(r'a started MECH with destructive ammo present ([01]) and self-destruct callback data (\d+)')
def encoded_fixture(w,present,data):
    if present=='1':add_ammo(w)
    w['callback_data']=int(data)


@step(r'exactly that callback runs once')
def encoded_run(w):w['callback_result']=call(w,equipment.explode_event,SimpleNamespace(data=unit(w),data2=w['callback_data']))


@step(r'callback disposition is (\S+)')
def encoded_result(w,result):eq(w['callback_result'],result)
