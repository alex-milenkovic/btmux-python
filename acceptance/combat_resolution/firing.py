"""Firing APS uses mapped contacts, mounted weapons and real dice streams."""
from . import step,unit,session,call,dice,eq
from .modes import mount
from .commands import acquire_contacts
from entities.mech import MechStatus as S,MechStatus2 as S2,CritStatus,UnitType as U,Location as L
from entities.crittypes import i2ammo,i2weapon
from entities.weapon import get_weapon
from systems.combat import fire_weapon_number,fire_weapon,calculate_bth


def ready(w):
    mount(w,'IS.AC/5',L.LARM)
    u=unit(w);v=unit(w,'v')
    slot=u.sections[L.LTORSO].criticals[9]
    slot.type=i2ammo(u.weapons[0].weapon_idx)
    slot.data=20
    w['fire_ammo']=slot
    acquire_contacts(w)
    u.target=v._id
    dice(w,'attack_rolls',[12])


def resources(w):
    u=unit(w);ws=u.weapons[0]
    return u.weap_heat,u.sections[ws.section].criticals[ws.critical].data,w['fire_ammo'].data,u.shots_fired


@step(r'a hidden ready attacker with a loaded weapon and visible locked enemy')
def hidden_fixture(w):
    ready(w)
    unit(w).crit_status|=CritStatus.HIDDEN


@step(r'fire is attempted with condition (\S+)')
def guarded_fire(w,condition):
    from core.events import EventType as E
    from systems.combat_equipment import unjam_ammo_event
    u=unit(w)
    if condition=='weapons-hold':u.status2|=S2.WEAPONS_HOLD
    elif condition=='sprinting':u.status2|=S2.SPRINTING
    elif condition=='weapon-recycling':u.sections[L.LARM].criticals[4].data=10
    elif condition=='carrying-club-in-mount':u.sections[L.LARM].specials|=0x20
    elif condition=='dug-in-nonturret':u.tank_crit_status=4;u.dug_in=True
    elif condition=='AMS-weapon':
        weapon=get_weapon('IS.Anti-MissileSystem')
        for part in u.sections[L.LARM].criticals:part.type=0
        u.weapons.clear()
        mount(w,weapon.name,L.LARM)
    elif condition=='ammo-unjam-pending':session(w).engine.events.schedule(60,E.UNJAM_AMMO,unjam_ammo_event,u,0)
    elif condition!='invalid-weapon':raise AssertionError(condition)
    w['before_resources']=resources(w)
    w['fire_result']=call(w,fire_weapon_number,session(w).engine,u,99 if condition=='invalid-weapon' else 0)


@step(r'firing is rejected and hidden state is (retained|cleared) and shot resources are unchanged')
def guarded_result(w,hidden):
    eq(w['fire_result'].bth_breakdown,None)
    eq(bool(unit(w).crit_status&CritStatus.HIDDEN),hidden=='retained')
    eq(resources(w),w['before_resources'])


@step(r'a ready shooter and target selected by (default|explicit-contact|hex-occupant)')
def safety_fixture(w,path):
    ready(w)
    w['fire_path']=path
    if path=='hex-occupant':
        u=unit(w);v=unit(w,'v')
        u.target=-1
        u.targ_x,u.targ_y=v.x,v.y
        u.status|=S.LOCK_TARGET


@step(r'target safety condition is (\S+) and fire is attempted')
def safety_fire(w,condition):
    from entities.map import MAPFLAG_NOFRIENDLYFIRE
    u=unit(w);v=unit(w,'v')
    if condition.startswith('friendly'):v.team=u.team
    if condition=='friendly-with-FFSafety':u.prefs|=128
    elif condition=='friendly-with-map-safety':u.map.flags|=MAPFLAG_NOFRIENDLYFIRE
    elif condition=='stealth-without-stable-lock':v.status2|=S2.STH_ARMOR_ON
    elif condition=='own-swarmer':v.swarming=u._id
    elif condition=='enemy-with-no-lock':u.target=-1
    elif condition=='MW-with-safety':v.unit_type=U.MW;u.prefs&=~1
    elif condition=='friendly-coolant':
        weapon=get_weapon('IS.CoolantGun')
        for part in u.sections[L.LARM].criticals:part.type=0
        u.weapons.clear()
        mount(w,weapon.name,L.LARM)
        w['fire_ammo'].type=i2ammo(weapon.index)
        u.prefs|=128
        u.map.flags|=MAPFLAG_NOFRIENDLYFIRE
    w['fire_result']=call(w,fire_weapon_number,session(w).engine,u,0,v if w['fire_path']=='explicit-contact' else None)


@step(r'shot disposition is (rejected|fired)')
def safety_result(w,result):
    eq(w['fire_result'].bth_breakdown is not None,result=='fired')
    if result=='fired':eq(unit(w).has_status(S.FIRED),True)


@step(r'a ready non-artillery shot with source BTH (\d+) and attack roll 7')
def bth_fixture(w,bth):
    ready(w)
    w['requested_bth']=int(bth)
    dice(w,'attack_rolls',[7])


@step(r'the action is (sight|fire-unit|fire-hex)')
def bth_fire(w,action):
    u=unit(w)
    target=None if action=='fire-hex' else unit(w,'v')
    weapon=get_weapon('IS.AC/5')
    original=call(w,calculate_bth,u,target,weapon,1,u.pilot.gunnery,L.LARM)
    u.pilot.gunnery+=w['requested_bth']-original.total
    w['before_resources']=resources(w)
    w['draw_start']=len(session(w).draws)
    w['fire_result']=call(w,fire_weapon,u,target,0,1,sight=action=='sight',ishex=int(target is None),mapx=3,mapy=1)
    eq(w['fire_result'].bth,w['requested_bth'])


@step(r'attack draws consumed are 1 and resources spent are ([01])')
def bth_result(w,spent):
    draws=session(w).draws[w['draw_start']:]
    eq(sum(d['name']=='attack_rolls' for d in draws),1)
    if spent=='0':eq(resources(w),w['before_resources'])
    else:
        eq(w['before_resources'][2]-w['fire_ammo'].data,1)
        eq(unit(w).has_status(S.FIRED),True)
