"""DFA damage and refusal are exercised through production landing."""
from . import step,unit,session,call,dice,eq,armor,position
from .pods import arms
from entities.mech import MechStatus as S,Location as L
from systems import physical as p
from physics.jump import land_mech


def airborne(w):
    arms(w)
    u,v=unit(w),unit(w,'v')
    position(u,v.x,v.y,2)
    u.status|=S.JUMPING|S.DFA_ATTACK
    u.dfa_target=v._id
    u.going_x,u.going_y=v.x,v.y
    u.elev=v.elev
    w['target_armor'],w['self_armor']=armor(v),armor(u)
    dice(w,'dfa_rolls',[12])
    dice(w,'pilot_rolls',[12]*20)


@step(r'an airborne attacker of nominal tons (\d+) actual tons (\d+) and upright MECH target')
def hit_fixture(w,nominal,actual):
    airborne(w)
    unit(w).tonnage=int(nominal);unit(w).rtons=int(actual)*1024


@step(r'landing DFA hits and both follow-up piloting rolls succeed')
def hit(w):
    call(w,land_mech,unit(w),event_queue=session(w).engine.events)
    eq(unit(w).last_dfa_result.hit,True)


@step(r'target punch-table damage is (\d+) self kick-table damage is (\d+) and all six sections recycle for 30')
def hit_result(w,target,selfdamage):
    u=unit(w)
    eq((w['target_armor']-armor(unit(w,'v')),w['self_armor']-armor(u)),(int(target),int(selfdamage)))
    eq([u.sections[loc].recycle for loc in p.RESECT],[30]*6)
    eq(sum(d['name']=='physical_location' for d in session(w).draws),(int(target)+4)//5+(int(selfdamage)+4)//5)
    eq(u.is_jumping,False)


@step(r'a 55-ton attacker landing a DFA over ground elevation (-?\d+)')
def miss_fixture(w,floor):
    airborne(w)
    u=unit(w);u.tonnage=55;u.rtons=55*1024
    floor=int(floor)
    if floor<0:
        from entities.map import WATER
        session(w).map.set_terrain(u.x,u.y,WATER)
    session(w).map.set_elevation(u.x,u.y,abs(floor))
    u.elev=abs(floor)
    dice(w,'dfa_rolls',[2])


@step(r'DFA misses and injury piloting succeeds')
def miss(w):call(w,land_mech,unit(w),event_queue=session(w).engine.events)


@step(r'target damage is 0 self back-table damage is 11 attacker is prone and Z is (-?\d+)')
def miss_result(w,floor):
    u=unit(w)
    eq(w['target_armor']-armor(unit(w,'v')),0)
    eq(w['self_armor']-armor(u),11)
    eq(u.is_fallen,True)
    eq(u.z,int(floor))
    eq(sum(d['name']=='fall_directions' for d in session(w).draws),0)


@step(r'an attacker completing a DFA jump with condition (\S+)')
def declined(w,condition):
    airborne(w)
    u=unit(w);v=unit(w,'v')
    if condition=='target-on-different-map':
        from entities.map import GameMap
        v.map=GameMap(12,12)
    elif condition=='target-jumping':v.status|=S.JUMPING
    elif condition=='arm-weapon-recycling':
        from .modes import mount
        slot=mount(w,'IS.MediumLaser',L.LARM);slot.data=10
    elif condition=='leg-physical-recycling':u.sections[L.LLEG].recycle=1
    elif condition=='BTH-over-12':u.pilot.piloting=15
    dice(w,'dfa_rolls',[])


@step(r'the landing callback runs')
def landing(w):call(w,land_mech,unit(w),event_queue=session(w).engine.events)


@step(r'DFA does not roll or damage and ordinary landing runs')
def decline_result(w):
    u=unit(w)
    eq(u.last_dfa_result.success,False)
    eq(w['target_armor']-armor(unit(w,'v')),0)
    eq(w['self_armor']-armor(u),0)
    eq(u.is_jumping,False)
    eq(u.dfa_target,-1)
    eq(sum(d['name']=='dfa_rolls' for d in session(w).draws),0)
