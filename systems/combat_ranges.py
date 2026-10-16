# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.bth.c
#   btech/mech.c3.misc.c
#   btech/mech.combat.c

"""mech.bth.c range helpers, including the two different minimum rules."""
from entities.mech import Location as L,MoveType as M,MechStatus2 as S2,FireMode as F,AmmoMode as A
from entities.weapon import WeaponFlags as W,WeaponType as T


def underwater(unit,section):
    return unit.z<0 and (unit.z<-1 or unit.is_fallen or section in (L.LLEG,L.RLEG) or
        unit.move_type==M.QUAD and section in (L.LARM,L.RARM))


def config(unit,name,default):return getattr(getattr(unit,'_engine',None),name,default)


def hotloading(weapon,mode):return bool(weapon.special&W.IDF and mode&F.HOTLOAD_MODE)


def long_range(weapon,water=False):
    if water:return next((r for r in (weapon.range_long_water,weapon.range_medium_water,weapon.range_short_water) if r>0),0)
    return weapon.range_long*(20 if weapon.weapon_type==T.TARTILLERY else 1)


def extreme_range(unit,weapon,water=False):
    maximum=long_range(weapon,water)
    medium=weapon.range_medium_water if water else weapon.range_medium
    if config(unit,'erange',1) and (not water or weapon.range_long_water>0):maximum=max(maximum,medium*2)
    return maximum


def rounded(weapon,distance):
    return int(distance*(10 if weapon.special&(W.PC_IMPA|W.PC_SHAR|W.PC_HEAT) else 1)+.95)


def by_range(unit,target,section,weapon,distance,fire_mode=0,ammo_mode=0):
    r=rounded(weapon,distance)
    hidden=target is not None and bool(target.status2&(S2.STH_ARMOR_ON|S2.NULLSIGSYS_ON))
    if underwater(unit,section):
        if weapon.range_short_water<=0:return 'NOWATER',5000
        if r>extreme_range(unit,weapon,True):return 'TOFAR',1000
        if r>long_range(weapon,True):return 'EXTREME',12 if hidden else 8
        if r>weapon.range_medium_water:return 'LONG',6 if hidden else 4
        if r>weapon.range_short_water:return 'MED',3 if hidden else 2
        if r>weapon.range_min_water:return 'SHORT',0
        if r==0:return 'SHORT',max(0,weapon.range_min_water-r)
        # Nonzero water minimum intentionally falls through to air logic.
    if r>extreme_range(unit,weapon)+(7 if ammo_mode&A.STINGER_MODE else 0):return 'TOFAR',1000
    if r>long_range(weapon):return 'EXTREME',12 if hidden else 8
    if r>weapon.range_medium:return 'LONG',6 if hidden else 4
    if r>weapon.range_short:return 'MED',3 if hidden else 2
    if r>weapon.range_min or r==0 and weapon.range_min==0:return 'SHORT',0
    if hotloading(weapon,fire_mode):
        return 'SHORT',int((weapon.range_min-r+1)/2) if config(unit,'hotloadaddshalfbthmod',0) else 0
    return 'SHORT',weapon.range_min-r+(r!=0)


def by_c3_range(unit,target,section,weapon,actual,network,mode=0):
    real,peer=rounded(weapon,actual),rounded(weapon,network)
    hidden=target is not None and bool(target.status2&(S2.STH_ARMOR_ON|S2.NULLSIGSYS_ON))
    water=underwater(unit,section)
    if water and weapon.range_short_water<=0:return 'NOWATER',5000
    if real>long_range(weapon,water):return 'TOFAR',1000
    medium=weapon.range_medium_water if water else weapon.range_medium
    short=weapon.range_short_water if water else weapon.range_short
    if peer>medium:return 'LONG',6 if hidden else 4
    if peer>short:return 'MED',3 if hidden else 2
    if water or actual>weapon.range_min or peer==0 and weapon.range_min==0:return 'SHORT',0
    # The C negates HotLoading here; FindNormalBTH passes its ammo word.
    if not hotloading(weapon,mode):
        return 'SHORT',int((weapon.range_min-actual+1)/2) if config(unit,'hotloadaddshalfbthmod',0) else 0
    return 'SHORT',int(weapon.range_min-actual+1)


def c3_available(unit, ordinary=True):
    from entities.mech import Specials, CritStatus
    from systems.ecm import any_ecm_disturbed
    tech = unit.specials & (Specials.C3_MASTER_TECH | Specials.C3_SLAVE_TECH) if ordinary else unit.specials2 & 0x20
    destroyed = CritStatus.C3_DESTROYED if ordinary else CritStatus.C3I_DESTROYED
    return bool(tech and not unit.crit_status & destroyed and not any_ecm_disturbed(unit))


def find_c3_range(unit,target,actual,ordinary=True):
    """Use the shared source network service; retain Combat's -1 early reference."""
    from core.randomness import float32
    actual = float32(actual)
    from systems.c3 import range_query, validate
    from entities.mech import CritStatus
    if not c3_available(unit,ordinary):
        if not ordinary and unit.crit_status & CritStatus.C3I_DESTROYED:
            validate(unit,False)
        return actual,-1
    return range_query(unit,target,actual,ordinary)


def send_c3_track_emit(unit,reference):
    from systems.targeting import resolve_unit
    from systems.movement_commands import notify
    peer=resolve_unit(unit,reference)
    if peer is not None and peer is not unit:
        from systems.parts import mech_ids
        notify(unit,f'Using range data from {peer.name} [{mech_ids(peer,lower=True)}]')
