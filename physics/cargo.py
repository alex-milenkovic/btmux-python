# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.move.c
#   btech/mech.update.c
# Historical Aerospace sources:
#   btech/mech.move.c

"""MechCargoMaxSpeed with construction mass or an explicit fixture measurement."""
import math
from core.randomness import float32
from entities.mech import MechStatus as S, MechStatus2 as S2, Specials, CritStatus, UnitType

MP1 = 10.75
CACHE_FLAGS = CritStatus.LOAD_OK | CritStatus.OWEIGHT_OK | CritStatus.SPEED_OK
AERO_TYPES = (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS)


def _hot_myomer(unit):
    return bool(unit.specials & Specials.TRIPLE_MYOMER_TECH) and unit.heat >= 9


def _carried_mass(unit, tow_mass):
    lugged = (tow_mass or 0) * 2
    for halve in (unit.specials & Specials.SALVAGE_TECH,
                  _hot_myomer(unit) and (unit.unit_type in AERO_TYPES or getattr(unit, 'tsm_tow_bonus', True)),
                  unit.specials2 & 0x80000):
        if halve:
            lugged //= 2
    coefficient = 1 if unit.specials & Specials.CARGO_TECH else 2
    if unit.unit_type == UnitType.MECH:
        coefficient *= 2
    return lugged + int(getattr(unit, 'carried_cargo', 0) * coefficient / 2)


def _adjusted_mass(mass, nominal):
    if mass == 1:
        return nominal
    if mass > nominal:
        return mass + (mass - nominal) // 2
    return mass + (nominal - mass) // 3


def _loaded_speed(unit, mass, lugged):
    nominal = unit.tonnage * 1024
    adjusted = _adjusted_mass(mass, nominal)
    if lugged + adjusted > 3 * nominal:
        return 0.0
    denominator = max(nominal + lugged // 3, 1024, adjusted + lugged)
    return float32(float32(unit.max_speed)*unit.tonnage)*1024.0/denominator


def _base_speed(unit):
    managed=getattr(unit,'construction_managed',False)
    mass=getattr(unit,'measured_mass',None)
    tow=getattr(unit,'towed_unit',None)
    if unit.carrying > 0:
        from systems.targeting import resolve_unit
        tow=resolve_unit(unit,unit.carrying)
    # Explicit measured fixtures act as measurement producers. A changed
    # measurement invalidates their caches; live unit state uses the C flags.
    if not managed and mass is not None:
        measured=(mass,getattr(unit,'carried_cargo',0),id(tow),getattr(tow,'measured_mass',None))
        if hasattr(unit,'_measured_load_key') and unit._measured_load_key!=measured:
            unit.clear_crit_status(CACHE_FLAGS)
        unit._measured_load_key=measured
    if tow is not None and not tow.has_crit_status(CritStatus.OWEIGHT_OK):
        unit.clear_crit_status(CritStatus.LOAD_OK)
    # The source checks the cache before Destroyed and before any weight call.
    # In particular, correct_speed must be able to capture a signed old limit.
    if unit.crit_status & CACHE_FLAGS == CACHE_FLAGS:
        return unit.cached_max_speed
    if managed or mass is None:
        from systems.construction_weight import get_weight
        mass=get_weight(unit)
    unit.rtons=mass
    unit.set_crit_status(CritStatus.OWEIGHT_OK)
    if not unit.has_crit_status(CritStatus.LOAD_OK):
        tow_mass=getattr(tow,'measured_mass',None)
        if tow is not None and (getattr(tow,'construction_managed',False) or tow_mass is None):
            from systems.construction_weight import get_weight
            tow_mass=get_weight(tow)
        unit.rcw=_carried_mass(unit,tow_mass)
        unit.set_crit_status(CritStatus.LOAD_OK)
    base=0.0 if unit.is_destroyed else _loaded_speed(unit,mass,getattr(unit,'rcw',0))
    unit.cached_max_speed=float32(base)
    unit.walk_xp_factor=int(max(1,int(unit.cached_max_speed)/MP1)*2)
    unit.set_crit_status(CritStatus.SPEED_OK)
    return unit.cached_max_speed


def _boosted_speed(unit, base):
    from systems.characters import actor_advantage
    historical=unit.unit_type in AERO_TYPES
    sprint=unit.has_status2(S2.SPRINTING)
    engine=getattr(unit,'_engine',None)
    if engine is not None:
        from core.events import EventType
        changing=engine.events.has_event_type_data(EventType.MOVEMODE,unit)
    else:
        event=getattr(unit,'_mode_event',None)
        changing=event is not None and not getattr(event,'zombie',False)
    boosters=sum((unit.has_status(S.MASC_ENABLED),unit.has_status(S.SCHARGE_ENABLED),
                  sprint and (not historical or not changing)))
    result=float32(float32(2.0*base)/3.0*(1.5+.5*boosters)) if boosters else float32(base)
    if not historical and _hot_myomer(unit) and (not sprint or getattr(unit,'tsm_sprint_bonus',True)):
        result=float32(math.ceil((round(result/1.5/MP1)+1)*1.5)*MP1)
    if sprint and not changing and actor_advantage(unit.pilot,'Speed_Demon'):
        result=float32(result+MP1)
    if not historical and unit.has_status(S.UNDERSPECIAL) and unit.has_status(S.UNDERGRAVITY) and unit.map:
        # C promotes the numerator and division to double until assignment.
        result=float32(result*100.0/float32(max(50,unit.map.grav)))
    return result


def cargo_max_speed(unit):
    return _boosted_speed(unit,_base_speed(unit))
