"""Range and to-hit diagnostics against live production functions."""
from dataclasses import replace
from . import step,unit,session,call,eq
from .commands import acquire_contacts
from entities.weapon import get_weapon,WeaponFlags as W,WeaponType as T
from entities.mech import MechStatus as S,MechStatus2 as S2,UnitType as U,MoveType as M,FireMode as F,AmmoMode as A
from core.events import EventType as E
from systems import combat_ranges as ranges,combat


@step(r'a weapon with air minimum 0 short 3 medium 6 long 9 extreme 12')
def weapon(w):
    w['weapon']=replace(get_weapon('IS.MediumLaser'),range_min=0,range_short=3,range_medium=6,range_long=9)
    session(w).engine.erange=1


def signature(w,name):
    unit(w,'v').status2|={'ordinary':0,'stealth':S2.STH_ARMOR_ON,'nullsig':S2.NULLSIGSYS_ON}[name]


@step(r'range is ([0-9.]+) and target signature is (ordinary|stealth|nullsig)')
def normal(w,distance,name):
    signature(w,name)
    w['range_result']=call(w,ranges.by_range,unit(w),unit(w,'v'),4,w['weapon'],float(distance))


@step(r'C3 range diagnostic uses actual ([0-9.]+) network ([0-9.]+) and signature (ordinary|stealth|nullsig)')
def c3(w,actual,network,name):
    signature(w,name)
    w['range_result']=call(w,ranges.by_c3_range,unit(w),unit(w,'v'),4,w['weapon'],float(actual),float(network))


@step(r'range bracket is (SHORT|MED|LONG|EXTREME|TOFAR|NOWATER) and range modifier is ([0-9]+)')
def range_result(w,bracket,modifier):eq(w['range_result'],(bracket,int(modifier)))


@step(r'artillery skill 4 range 20 maximum 100 and adjustment ([0-9]+)')
def artillery(w,adjustment):
    unit(w).pilot.artillery=4
    unit(w).fire_adjustment=int(adjustment)
    w['weapon']=replace(get_weapon('IS.MediumLaser'),weapon_type=T.TARTILLERY,range_long=5)


@step(r'artillery BTH is requested with (direct|indirect-none|indirect-other|underwater) and spotter skill ([0-9]+)')
def artillery_bth(w,path,skill):
    from systems.artillery import artillery_bth
    if path=='indirect-other':
        unit(w).spotter=unit(w,'v')._id
        unit(w,'v').pilot.spotting=int(skill)
    if path=='underwater':unit(w).z=-2
    w['bth']=call(w,artillery_bth,unit(w),4,w['weapon'],20,path!='direct')


@step(r'artillery BTH is ([0-9]+)')
def artillery_result(w,bth):eq(w['bth'],int(bth))


@step(r'a ready attacker with movement profile (.+)')
def attacker(w,profile):
    u=unit(w)
    u.desired_facing=u.facing
    if 'turning' in profile:u.desired_facing+=1
    if profile.startswith('walking'):u.speed=1
    if profile.startswith('running'):u.speed=u.max_speed
    if 'jumping' in profile:u.status|=S.JUMPING
    if profile.startswith('battlesuit'):u.unit_type=U.BSUIT
    if 'prone' in profile:u.status|=S.FALLEN
    if 'quad' in profile:u.move_type=M.QUAD
    if profile in ('standing','stabilizing'):
        session(w).engine.events.schedule(12,E.STAND if profile=='standing' else E.JUMPSTABIL,lambda e:None,data=u)


@step(r'its attack movement modifier is requested')
def attack_move(w):w['modifier']=call(w,combat.calculate_attacker_movement_modifier,unit(w))


@step(r'the attack movement modifier is ([0-9]+)')
def attack_result(w,modifier):eq(w['modifier'],int(modifier))


@step(r'an otherwise mobile target with profile (.+) at range ([0-9.]+)')
def target(w,profile,distance):
    v=unit(w,'v')
    w['distance']=float(distance)
    if profile.startswith('purifier'):v.infantry_specials=8
    if profile.startswith('prone'):v.status|=S.FALLEN
    if profile.endswith('kph'):v.speed=float(profile.split('-')[1][:-3])


@step(r'its target movement modifier is requested')
def target_move(w):w['modifier']=call(w,combat.calculate_target_movement_modifier,unit(w,'v'),w['distance'],unit(w))


@step(r'target movement modifier is (-?[0-9]+)')
def target_result(w,modifier):eq(w['modifier'],int(modifier))


@step(r'a stable short-range shot with gunnery 4 and all other modifiers zero')
def stable(w):
    weapon(w)
    acquire_contacts(w)
    unit(w).desired_facing=unit(w).facing
    unit(w).target=unit(w,'v')._id


@step(r'the isolated BTH condition is (.+)')
def condition(w,condition):
    u,v=unit(w),unit(w,'v')
    kw={}
    if condition.startswith('target-'):v.unit_type={'target-MW':U.MW,'target-BA':U.BSUIT,'target-dropship':U.DS}[condition]
    if condition in ('pulse','MRM','heavy-weapon','rocket'):
        w['weapon']=replace(w['weapon'],special={'pulse':W.PULSE,'MRM':W.MRM,'heavy-weapon':W.HVYW,'rocket':W.ROCKET}[condition])
    if condition=='AP-ammo':kw['w_ammo_mode']=A.AC_AP_MODE
    if condition=='attacker-haywire':
        from systems.missile import INARC_HAYWIRE_ATTACHED
        u.sections[4].specials|=INARC_HAYWIRE_ATTACHED
    if condition=='targetless-hex-ON_TC':
        v=None
        u.status|=S.LOCK_HEX
        kw['w_fire_mode']=F.ON_TC
    if condition=='missing-indirect-spotter':kw['indirect_fire']=2
    w['bth']=call(w,combat.calculate_bth,u,v,w['weapon'],1,4,4,**kw).total


@step(r'normal shot BTH is ([0-9]+)')
def normal_bth_result(w,bth):eq(w['bth'],int(bth))
