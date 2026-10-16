# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# Host-derived portions also retain notices/TinyMUX.txt.
# General sources:
#   btech/btechstats.c
#   btech/mech.advanced.c
#   btech/mech.events.c
#   btech/mech.lite.c
#   btech/mech.los.c
#   btech/mech.notify.c
#   btech/mech.sensor.c
#   btech/mech.sensor.functions.c
#   btech/mech.update.c
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/mech.h
#   btech/src/btech/mech.sensor.h
#   btech/src/include/btconfig.h
#   src/conf.c

"""
Sensor system — port of the BTMux sensor table and per-sensor math.

Sources:
- mech.sensor.h:20-175   — SensorStruct typedef, sensors[] table, indices
- mech.sensor.functions.c (whole file) — see-chance / can-see / to-hit funcs
- mech.sensor.c:27-77    — Sensor_ToHitBonus
- mech.sensor.c:95-96    — MaxVis / MaxVar macros
- btmacros.h:872-875     — MechLOSFlag_WoodCount / MechLOSFlag_WaterCount

Note on the C build flags: BT_SCALED_INFRARED is not defined anywhere in the
reference tree, so the #else branches of HEAT_MODIFIER
(mech.sensor.functions.c:155) and infrared_tohit (:187-190) are the live
code and are what is ported here.
"""

from __future__ import annotations
import math
import random
from core.randomness import float32 as f32
from dataclasses import dataclass
from typing import Callable, Optional

from entities.map import (
    LIGHT_FOREST, HEAVY_FOREST, FIRE, SMOKE, ICE, BRIDGE,
    base_elev, bounded,
)
from entities.mech import (MechStatus, MechStatus2, CritStatus, UnitType,
                           MoveType, Specials)
from physics.hexmath import SCALEMAP, hex_to_float, find_range3d, in_weapon_arc, \
    FORWARDARC, LSIDEARC, RSIDEARC, REARARC, TURRETARC
from physics.movement import MP1  # 10.75 KPH per MP (mech.h:54)
from systems.los import (
    MECHLOSFLAG_BLOCK, MECHLOSFLAG_FIRE, MECHLOSFLAG_SMOKE,
    MECHLOSFLAG_MNTN, MECHLOSFLAG_PARTIAL,
    MECHLOSFLAG_SEEN, MECHLOSFLAG_SEEC2,
    MECHLOSFLAG_SEESP, MECHLOSFLAG_SEESS,
    MECHLOSFLAG_WOOD, MECHLOSMAX_WOOD,
    MECHLOSFLAG_WATER, MECHLOSMAX_WATER,
    MECHMAPFLAG_MOVED,
    actual_elevation, calculate_los_flag,
)


# =============================================================================
# Constants
# =============================================================================

# Sensor type indices (mech.sensor.h:103-110).
# C oddity preserved: the Light Beagle ActiveProbe row was inserted into the
# sensors[] table at index 7 without a matching SENSOR_* define, so
# SENSOR_BHAP (7) does NOT match the Bloodhound row's table index (8).
# blood_csee checks map sensorflags bit SENSOR_BHAP=7 — the LBAP slot.
SENSOR_VIS = 0
SENSOR_LA = 1
SENSOR_IR = 2
SENSOR_EM = 3
SENSOR_SE = 4
SENSOR_RA = 5
SENSOR_BAP = 6
SENSOR_BHAP = 7

# Sensor attributeCheck values (mech.sensor.h:112-113)
SENSOR_ATTR_NONE = 0
SENSOR_ATTR_SEISMIC = 1

# Blondhound probe lives in the extended specials word (specials_set == 2)
BLOODHOUND_PROBE_TECH = 0x800  # mech.h:1178

# Autocannon incendiary ammo mode (mech.h:652); shares the weapon-mode
# bitfield space with FireMode but is an ammo mode, so defined here.
AC_INCENDIARY_MODE = 0x00008000

# Unit searchlight-on flag, lives in MECH.status2 (mech.h:1033 SLITE_ON).
SLITE_ON = 0x00000020

# Tank crit status: dug in (mech.h:1123, tankcritstatus element).
DUG_IN = 0x04

# mudconf.btech_seismic_see_stopped, default 0 (conf.c:136).
BTECH_SEISMIC_SEE_STOPPED = 0

# ECM umbrella / searchlight ranges (btconfig.h:212, 225).
ECM_RANGE = 6
LITE_RANGE = 30

# Z above which units are 'in atmosphere' (btconfig.h:54).
ATMO_Z = 100

# Infantry stealth specials (mech.h:1199-1207).
CS_PURIFIER_STEALTH_TECH = 0x08
DC_KAGE_STEALTH_TECH = 0x10
FWL_ACHILEUS_STEALTH_TECH = 0x20
FC_INFILTRATOR_STEALTH_TECH = 0x40
FC_INFILTRATORII_STEALTH_TECH = 0x80
STEALTH_TECH = (CS_PURIFIER_STEALTH_TECH | DC_KAGE_STEALTH_TECH |
                FWL_ACHILEUS_STEALTH_TECH | FC_INFILTRATOR_STEALTH_TECH |
                FC_INFILTRATORII_STEALTH_TECH)

# bth_modifier[] (btechstats.c:1296-1300): "Starts from '3', in 1/36's".
bth_modifier = [1, 3, 6, 10, 15, 21, 26, 30, 33, 35, 0, 0, 0, 0]


# =============================================================================
# LOS-flag count extraction (btmacros.h:872-875)
# =============================================================================

def mech_losflag_wood_count(flag: int) -> int:
    """Intervening woods-point count packed in the LOS flag (btmacros.h:872-873)."""
    return (flag // MECHLOSFLAG_WOOD) % MECHLOSMAX_WOOD


def mech_losflag_water_count(flag: int) -> int:
    """Intervening water-hex count packed in the LOS flag (btmacros.h:874-875)."""
    return (flag // MECHLOSFLAG_WATER) % MECHLOSMAX_WATER


# =============================================================================
# Small C-macro helpers
# =============================================================================

def _c_int(x) -> int:
    """C (int) cast: truncate toward zero."""
    return int(x)


def _is_lit(mech) -> bool:
    """
    IsLit (btmacros.h:720): MechLit || MechLites.
    MechLit = critstatus & SLITE_LIT (btmacros.h:718),
    MechLites = status2 & SLITE_ON (btmacros.h:719).
    """
    return bool((mech.crit_status & CritStatus.SLITE_LIT) or
                (mech.status2 & SLITE_ON))


def _jumping(mech) -> bool:
    """Jumping(a) = MechStatus & JUMPING (btmacros.h)."""
    return bool(mech.status & MechStatus.JUMPING)


def _started(mech) -> bool:
    """Started(a) = MechStatus & STARTED (btmacros.h)."""
    return bool(mech.status & MechStatus.STARTED)


def _landed(mech) -> bool:
    """Landed(a) = MechStatus & LANDED (btmacros.h)."""
    return bool(mech.status & MechStatus.LANDED)


def _fallen(mech) -> bool:
    """Fallen(a) = MechStatus & FALLEN (btmacros.h)."""
    return bool(mech.status & MechStatus.FALLEN)


def _is_hulldown(mech) -> bool:
    """IsHulldown(a) = MechStatus & HULLDOWN (btmacros.h:409)."""
    return bool(mech.status & MechStatus.HULLDOWN)


def _is_ds(mech) -> bool:
    """IsDS(m) = DropShip(MechType(m)) (mech.h:724-725)."""
    return mech.unit_type in (UnitType.DS, UnitType.SPHEROID_DS)


def _flying_t(mech) -> bool:
    """FlyingT(a) = is_aero(a) || MechMove(a) == MOVE_VTOL (btmacros.h:420);
    is_aero = CLASS_AERO || IsDS (btmacros.h:36)."""
    return (mech.unit_type == UnitType.AERO or _is_ds(mech) or
            mech.move_type == MoveType.VTOL)


def _mech_rterrain(mech) -> str:
    """
    MechRTerrain (btmacros.h:225): FIRE/SMOKE hexes resolve to the underlying
    terrain (mech_underlying_terrain), otherwise the cached terrain char.
    GameMap.rterrain resolves timed decoration underlays.
    """
    t = mech.terrain
    if t in (FIRE, SMOKE):
        from entities.map_objects import mech_underlying_terrain
        return mech_underlying_terrain(mech)
    return t


def _mech_elevation(mech) -> int:
    """MechElevation (btmacros.h:48-49): BaseElev(MechRTerrain, abs(MechElev))."""
    return base_elev(_mech_rterrain(mech), abs(mech.elev))


def _mech_lower_elevation(mech) -> int:
    """
    MechLowerElevation (btmacros.h:52-53): BRIDGE hexes use
    bridge_w_elevation — hardcoded -1 in this checkout
    (mech.update.c:67-70) — else MechElevation.
    """
    if _mech_rterrain(mech) == BRIDGE:
        return -1
    return _mech_elevation(mech)


def _mech_upper_elevation(mech) -> int:
    """MechUpperElevation (btmacros.h:54): 0 on ICE, else MechElevation."""
    if _mech_rterrain(mech) == ICE:
        return 0
    return _mech_elevation(mech)


def _mechs_elevation(mech) -> int:
    """MechsElevation (btmacros.h:55-56): height of the unit above its hex."""
    upper = _mech_upper_elevation(mech)
    return mech.z - (upper if upper <= mech.z else _mech_lower_elevation(mech))


# How many seconds the same per-mech random is reused for (btconfig.h:165)
RANDOM_TICK = 6


def m_number_bounds(low, high):
    if (type(low) is not int or type(high) is not int or
            not -(1 << 31) <= low < 1 << 31 or
            not -(1 << 31) <= high < 1 << 31 or
            not 0 < high - low + 1 < 1 << 31):
        raise ValueError('Unsupported MNumber signed-int endpoints or span')
    return low, high


def m_number(mech, low: int, high: int, *, event_tick=None, random_state=None) -> int:
    """Cached int31 from the owning simulation's event clock and MT stream.

    Detached callers must supply an event_tick; a map's owning engine also
    supplies this context. An arbitrary map.current_tick is not a source clock.
    Named finite draw injection remains available through core.randomness.
    """
    from core.randomness import draw, source_state
    m_number_bounds(low, high)
    engine = getattr(mech, '_engine', None) or getattr(mech.map, '_engine', None)
    if engine is not None:
        event_tick, random_state = engine.muxevent_tick, engine.randomness
    if event_tick is None:
        raise ValueError('MNumber requires an explicit simulation event clock')
    if (event_tick // RANDOM_TICK) != getattr(mech, 'last_rnd_update', -1):
        mech.rnd = draw('sensor.random', 0, 2**31-1,
                        lambda: source_state(mech).mt.int31(),
                        state=random_state or source_state(mech))
        mech.last_rnd_update = event_tick // RANDOM_TICK
    return low + getattr(mech, 'rnd', 0) % (high - low + 1)


def heat_modifier(a: float) -> int:
    """HEAT_MODIFIER, non-BT_SCALED_INFRARED branch (mech.sensor.functions.c:155)."""
    return 2 if a <= 7 else 1 if a <= 10 else 0 if a <= 15 else -1 if a <= 22 else -2


def weight_modifier(a: float) -> int:
    """WEIGHT_MODIFIER (mech.sensor.functions.c:158): heavy -1, medium 0, light +1."""
    return -1 if a > 65 else 0 if a > 35 else 1


def move_modifier(a: float) -> int:
    """MOVE_MODIFIER (mech.sensor.functions.c:161): moving target +1."""
    return 1 if abs(a) >= 10.75 else 0


def nwood_count(mech, flag: int) -> int:
    """
    nwood_count (mech.sensor.functions.c:163-166): intervening woods points
    plus the target's own hex forest, unless the target is above the trees
    (MechElevation + 2 < MechZ).
    """
    rt = _mech_rterrain(mech)
    own = (0 if (_mech_elevation(mech) + 2) < mech.z else
           1 if rt == LIGHT_FOREST else 2 if rt == HEAVY_FOREST else 0)
    return mech_losflag_wood_count(flag) + own


def _sensorflags(game_map) -> int:
    """MAP.sensorflags; getattr-guarded until the map carries it."""
    return getattr(game_map, 'sensorflags', 0)


def _bsuit_or_mw(mech) -> bool:
    """MechType(t) == CLASS_BSUIT || MechType(t) == CLASS_MW."""
    return mech.unit_type in (UnitType.BSUIT, UnitType.MW)


# =============================================================================
# See-chance functions (mech.sensor.functions.c:24-66)
# Signature mirrors the C: (t=target-or-None, map, num=sensor #, r=range,
# c=condition max range, l=light level).  Return is C (int)-cast.
# =============================================================================

def vislight_see(t, game_map, num: int, r: float, c: int, l: int) -> int:
    """vislight_see (mech.sensor.functions.c:25-39): full chance within
    conditionrange (3x for lit targets in darkness); bsuit/MW divide by 3."""
    r = f32(r)
    if r > (c * (3 if (not l and t is not None and _is_lit(t)) else 1)):
        return 0
    return _c_int(f32(f32(100 - f32(r / 3)) /
                      (3 if (t is not None and _bsuit_or_mw(t)) else 1)))


def liteamp_see(t, game_map, num: int, r: float, c: int, l: int) -> int:
    """liteamp_see (mech.sensor.functions.c:43-57): 2x conditionrange in
    perfect darkness, else conditionrange; flat chance; bsuit/MW divide by 3."""
    r = f32(r)
    if not l and r > (2 * c):
        chance = 0
    elif l and r > c:
        chance = 0
    else:
        chance = f32(70 - r)
    return _c_int(f32(chance / (3 if (t is not None and _bsuit_or_mw(t)) else 1)))


def infrared_see(t, game_map, num: int, r: float, c: int, l: int) -> int:
    """infrared_see (mech.sensor.functions.c:60)."""
    return _c_int(f32(80 - f32(r)))


def electrom_see(t, game_map, num: int, r: float, c: int, l: int) -> int:
    """electrom_see (mech.sensor.functions.c:61):
    MAX(r < 24 ? 2 : 0, 60 - 2r) / 2 (int MAX and int division, as in C)."""
    r = f32(r)
    a = 2 if r < 24 else 0
    b = _c_int(f32(60 - f32(r * 2)))  # implicit float->int at the MAX(int,int) call
    v = a if a > b else b
    return _c_int(v / 2)


def seismic_see(t, game_map, num: int, r: float, c: int, l: int) -> int:
    """seismic_see (mech.sensor.functions.c:62)."""
    return _c_int(f32(50 - f32(f32(r) * 4)))


def radar_see(t, game_map, num: int, r: float, c: int, l: int) -> int:
    """radar_see (mech.sensor.functions.c:64): BOUNDED(10, 180 - r, 90)."""
    return bounded(10, _c_int(f32(180 - f32(r))), 90)


def bap_see(t, game_map, num: int, r: float, c: int, l: int) -> int:
    """bap_see (mech.sensor.functions.c:65): always 101."""
    return 101


def blood_see(t, game_map, num: int, r: float, c: int, l: int) -> int:
    """blood_see (mech.sensor.functions.c:66): always 101."""
    return 101


# =============================================================================
# Can-see functions (mech.sensor.functions.c:68-143)
# Signature mirrors the C: (m=looker, t=target-or-None, map, r=range, f=flag).
# Prior requirement: the seechance > 0 (assumed by the C; only the flag is
# examined here).
# =============================================================================

def vislight_csee(m, t, game_map, r: float, f: int) -> int:
    """vislight_csee (mech.sensor.functions.c:74-80): hampered by
    block/fire/smoke, 3+ woods points, and 6+ water hexes to submerged targets."""
    return _c_int(
        not (_sensorflags(game_map) & (1 << SENSOR_VIS)) and
        not (f & (MECHLOSFLAG_BLOCK | MECHLOSFLAG_FIRE | MECHLOSFLAG_SMOKE)) and
        mech_losflag_wood_count(f) < 3 and
        (t is None or t.z >= 0 or
         actual_elevation(getattr(t, 'map', None), t.x, t.y, t) >= 0.0 or
         mech_losflag_water_count(f) < 6))


def liteamp_csee(m, t, game_map, r: float, f: int) -> int:
    """liteamp_csee (mech.sensor.functions.c:83-86): no water penetration,
    2+ woods blocks, can't look at lit targets."""
    return _c_int(
        not (_sensorflags(game_map) & (1 << SENSOR_LA)) and
        not (f & (MECHLOSFLAG_BLOCK | MECHLOSFLAG_FIRE | MECHLOSFLAG_SMOKE)) and
        (t is None or not _is_lit(t)) and
        mech_losflag_wood_count(f) < 2 and
        not mech_losflag_water_count(f))


def infrared_csee(m, t, game_map, r: float, f: int) -> int:
    """infrared_csee (mech.sensor.functions.c:89-92): 6+ woods blocks;
    can't pick up bsuits/MWs."""
    return _c_int(
        not (_sensorflags(game_map) & (1 << SENSOR_IR)) and
        not (f & (MECHLOSFLAG_BLOCK | MECHLOSFLAG_FIRE)) and
        mech_losflag_wood_count(f) < 6 and
        (t is None or not _bsuit_or_mw(t)))


def electrom_csee(m, t, game_map, r: float, f: int) -> int:
    """electrom_csee (mech.sensor.functions.c:96-101): mountains block;
    8+ woods blocks; disturbed by ECM; can't pick up MWs.
    AnyECMDisturbed(m) (mech.sensor.functions.c:98) reads
    mech.ecm_disturbed, maintained by systems/ecm.py."""
    return _c_int(
        not (_sensorflags(game_map) & (1 << SENSOR_EM)) and
        not (f & (MECHLOSFLAG_BLOCK | MECHLOSFLAG_MNTN)) and
        mech_losflag_wood_count(f) < 8 and
        not getattr(m, 'ecm_disturbed', 0) and
        (t is None or t.unit_type != UnitType.MW))


def seismic_csee(m, t, game_map, r: float, f: int) -> int:
    """seismic_csee (mech.sensor.functions.c:106-121): needs a started,
    grounded, moving target and a grounded, non-jumping looker."""
    return _c_int(
        not (_sensorflags(game_map) & (1 << SENSOR_SE)) and
        t is not None and
        (not _jumping(m)) and
        (True if getattr(game_map, 'seismic_see_stopped', BTECH_SEISMIC_SEE_STOPPED) else (abs(t.speed) > MP1)) and
        (((m.move_type != MoveType.VTOL) or
          ((m.move_type == MoveType.VTOL) and _landed(m))) and
         ((m.move_type != MoveType.FLY) or
          ((m.move_type == MoveType.FLY) and _landed(m))) and
         _started(t) and not _jumping(t) and
         (t.unit_type != UnitType.BSUIT) and
         (t.unit_type != UnitType.MW) and
         (t.move_type != MoveType.HOVER) and
         ((t.move_type != MoveType.VTOL) or
          ((t.move_type == MoveType.VTOL) and _landed(t))) and
         ((t.move_type != MoveType.FLY) or
          ((t.move_type == MoveType.FLY) and _landed(t)))) and
        (t.move_type != MoveType.NONE))


def radar_csee(m, t, game_map, r: float, f: int) -> int:
    """radar_csee (mech.sensor.functions.c:124-130): target must be flying
    (z > 2), unblocked, and either z >= 10 or within z*z hexes."""
    return _c_int(
        not (_sensorflags(game_map) & (1 << SENSOR_RA)) and
        t is not None and
        t.z > 2 and
        not (f & MECHLOSFLAG_BLOCK) and
        (t.z >= 10 or (r < (t.z * t.z))) and
        _mechs_elevation(t) > 1)


def bap_csee(m, t, game_map, r: float, f: int) -> int:
    """bap_csee (mech.sensor.functions.c:133-138): disrupted by ECM; can't
    pick up Angel-ECM / stealth-armor / null-sig units.
    AnyECMDisturbed(m) (:135) reads mech.ecm_disturbed and
    AngelECMProtected(t) (:137) reads target.angel_ecm_protected, both
    maintained by systems/ecm.py; StealthArmorActive / NullSigSysActive
    (:138) are MechStatus2 bits (btmacros.h:817,824)."""
    return _c_int(
        not (_sensorflags(game_map) & (1 << SENSOR_BAP)) and
        not getattr(m, 'ecm_disturbed', 0) and
        t is not None and
        not getattr(t, 'angel_ecm_protected', 0) and
        not (t.status2 & MechStatus2.STH_ARMOR_ON) and
        not (t.status2 & MechStatus2.NULLSIGSYS_ON))


def blood_csee(m, t, game_map, r: float, f: int) -> int:
    """blood_csee (mech.sensor.functions.c:141-143): only disrupted by ECM.
    C oddity preserved: checks sensorflags bit SENSOR_BHAP (7), the LBAP
    table slot, not the Bloodhound row index (8).
    AnyECMDisturbed(m) / AngelECMProtected(t) (:143) read
    mech.ecm_disturbed / target.angel_ecm_protected, maintained by
    systems/ecm.py."""
    return _c_int(
        not (_sensorflags(game_map) & (1 << SENSOR_BHAP)) and
        not getattr(m, 'ecm_disturbed', 0) and
        t is not None and
        not getattr(t, 'angel_ecm_protected', 0))


# =============================================================================
# To-hit bonus functions (mech.sensor.functions.c:168-216)
# Signature mirrors the C: (m=looker, t=target, map, f=flag, l=light level).
# =============================================================================

def vislight_tohit(m, t, game_map, f: int, l: int) -> int:
    """vislight_tohit (mech.sensor.functions.c:170-173): non-day penalty for
    unlit targets, interrupting woods, partial LOS, hulldown."""
    return (((2 - l) if (t is None or not _is_lit(t)) else 0) +
            nwood_count(t, f) +
            ((3 + (2 if _is_hulldown(t) else 0)) if (f & MECHLOSFLAG_PARTIAL) else 0))


def liteamp_tohit(m, t, game_map, f: int, l: int) -> int:
    """liteamp_tohit (mech.sensor.functions.c:176-178): interrupting woods
    (x1.5), partial LOS, hulldown."""
    return (_c_int((2 - l) / 2) +
            _c_int((nwood_count(t, f) * 3) / 2) +
            ((3 + (2 if _is_hulldown(t) else 0)) if (f & MECHLOSFLAG_PARTIAL) else 0))


def infrared_tohit(m, t, game_map, f: int, l: int) -> int:
    """infrared_tohit, non-BT_SCALED_INFRARED branch
    (mech.sensor.functions.c:187-190): woods (x4/3), partial LOS, hulldown,
    target heat (HEAT_MODIFIER(MechHeat + 7))."""
    if getattr(game_map, 'infrared_profile', 'unscaled') == 'scaled':
        plus, minus = f32(t.plus_heat), f32(t.minus_heat)
        # MIN takes int operands in C; the surrounding expression is float.
        heat = f32(f32(2 * f32(plus - minus)) + f32(min(int(plus), int(minus))))
        modifier = 2 if heat <= 0 else -2 if heat > 50 else -1 if heat > 35 else 0 if heat > 20 else 1
        return int(nwood_count(t, f) * 4 / 3) + (3 if f & MECHLOSFLAG_PARTIAL else 0) + modifier
    return (_c_int((nwood_count(t, f) * 4) / 3) +
            ((3 + (2 if _is_hulldown(t) else 0)) if (f & MECHLOSFLAG_PARTIAL) else 0) +
            heat_modifier(f32(f32(t.heat) + 7)))


def electrom_tohit(m, t, game_map, f: int, l: int) -> int:
    """electrom_tohit (mech.sensor.functions.c:194-198): woods (x2/3),
    partial LOS, hulldown, weight/movement, recently fired, random wobble."""
    return (_c_int((nwood_count(t, f) * 2) / 3) +
            ((3 + (2 if _is_hulldown(t) else 0)) if (f & MECHLOSFLAG_PARTIAL) else 0) +
            weight_modifier(t.tonnage) +
            move_modifier(t.speed) +
            (-1 if (t.status & MechStatus.FIRED) else 0) +
            m_number(m, 0, 1))


def seismic_tohit(m, t, game_map, f: int, l: int) -> int:
    """seismic_tohit (mech.sensor.functions.c:201-204): flat +2, partial LOS,
    hulldown, real weight, speed (bonus), random wobble.
    MechRealTons = rd.row / 1024 (btmacros.h:229), represented by the
    existing rtons cache populated by data.templates.update_oweight.
    """
    real_tons = t.rtons // 1024
    return (2 +
            ((3 + (2 if _is_hulldown(t) else 0)) if (f & MECHLOSFLAG_PARTIAL) else 0) +
            weight_modifier(real_tons) -
            move_modifier(t.speed) +
            m_number(m, 0, 1))


def bap_tohit(m, t, game_map, f: int, l: int) -> int:
    """bap_tohit (mech.sensor.functions.c:207): MNumber(m, 0, 2). 'Very evil'."""
    return m_number(m, 0, 2)


def blood_tohit(m, t, game_map, f: int, l: int) -> int:
    """blood_tohit (mech.sensor.functions.c:210): MNumber(m, 0, 2). 'Very evil'."""
    return m_number(m, 0, 2)


def radar_tohit(m, t, game_map, f: int, l: int) -> int:
    """radar_tohit (mech.sensor.functions.c:213-216): -3 vs high/flying
    targets, reduced partial-cover penalty (2), hulldown, interrupting woods."""
    return ((-3 if (t.z >= 10 or _flying_t(t)) else 0) +
            ((2 + (2 if _is_hulldown(t) else 0)) if (f & MECHLOSFLAG_PARTIAL) else 0) +
            nwood_count(t, f))


# =============================================================================
# SensorStruct and the sensors[] table (mech.sensor.h:26-171)
# =============================================================================

@dataclass
class SensorStruct:
    """SensorStruct (mech.sensor.h:26-64)."""
    sensorname: str
    matchletter: str
    fullvision: int          # 360-degree with just one of them?
    maxvis: int              # longest vis this sensor brand sees
    maxvvar: int             # variable factor in maxvis; +-1 every 30 seconds
    seechance_func: Callable
    cansee_func: Callable
    tohitbonus_func: Callable
    min_light: int           # if < 0, not used
    max_light: int
    required_special: int
    specials_set: int        # 1 = original specials struct, 2 = extended
    attribute_check: int     # attributeCheck: special checks in mech.sensor.c
    range_desc: str
    block_desc: str
    special_desc: str


# sensors[] (mech.sensor.h:116-169), every row 1:1.
sensors = [
    SensorStruct("Vislight", "V", 0, 60, 0,
                 vislight_see, vislight_csee, vislight_tohit,
                 -1, -1, 0, 1, SENSOR_ATTR_NONE,
                 "Visual",
                 "Fire/Smoke/Obstacles, 3 pt woods, 5 underwater hexes",
                 "Bad in night-fighting (BTH)"),
    SensorStruct("Light-amplification", "L", 0, 60, 0,
                 liteamp_see, liteamp_csee, liteamp_tohit,
                 0, 1, 0 - Specials.NS_TECH, 1, SENSOR_ATTR_NONE,
                 "Visual (Dawn/Dusk), 2x Visual (Night)",
                 "Fire/Smoke/Obstacles, 2 pt woods, any water",
                 "Somewhat harder enemy detection (than vislight), "
                 "bad in forests (BTH/range)"),
    SensorStruct("Infrared", "I", 1, 15, 0,
                 infrared_see, infrared_csee, infrared_tohit,
                 -1, -1, 0 - Specials.NS_TECH, 1, SENSOR_ATTR_NONE,
                 "15",
                 "Fire/Obstacles, 6 pt woods",
                 "Easy to hit 'hot' targets, not very efficient in forests (BTH)"),
    SensorStruct("Electromagnetic", "E", 1, 24, 8,
                 electrom_see, electrom_csee, electrom_tohit,
                 -1, -1, 0 - Specials.NS_TECH, 1, SENSOR_ATTR_NONE,
                 "16-24",
                 "Mountains/Obstacles, 8 pt woods",
                 "Easy to hit heavies, good in forests (BTH), overall "
                 "unreliable (chances of detection/BTH)"),
    SensorStruct("Seismic", "S", 1, 8, 4,
                 seismic_see, seismic_csee, seismic_tohit,
                 -1, -1, 0 - Specials.NS_TECH, 1, SENSOR_ATTR_SEISMIC,
                 "4-8",
                 "Nothing",
                 "Easier heavy and/or moving object detection (although "
                 "overall hard to detect with), somewhat unreliable(BTH)"),
    SensorStruct("Radar", "R", 1, 180, 0,
                 radar_see, radar_csee, radar_tohit,
                 -1, -1, Specials.AA_TECH, 1, SENSOR_ATTR_NONE,
                 "<=180",
                 "Obstacles, enemy elevation (Enemy Z >= 10, range: 180, "
                 "Enemy Z < 10, range: varies)",
                 "Premier anti-aircraft sensor, partially negates partial "
                 "cover(BTH), doesn't see targets that are too low for detection"),
    SensorStruct("Beagle ActiveProbe", "B", 1, 6, 0,
                 bap_see, bap_csee, bap_tohit,
                 -1, -1, Specials.BEAGLE_PROBE_TECH, 1, SENSOR_ATTR_NONE,
                 "<=6",
                 "Nothing (except range)",
                 "Ultimate sensor in close-range detection (slightly varying "
                 "BTH, but ignores partial/woods/water)"),
    SensorStruct("Light Beagle ActiveProbe", "A", 1, 3, 0,
                 bap_see, bap_csee, bap_tohit,
                 -1, -1, Specials.LIGHT_BAP_TECH, 1, SENSOR_ATTR_NONE,
                 "<=3",
                 "Nothing (except range)",
                 "Short range, but ultimate sensor in close-range detection "
                 "(slightly varying BTH, but ignores partial/woods/water)"),
    SensorStruct("Bloodhound ActiveProbe", "H", 1, 8, 0,
                 blood_see, blood_csee, blood_tohit,
                 -1, -1, BLOODHOUND_PROBE_TECH, 2, SENSOR_ATTR_NONE,
                 "<=8",
                 "Nothing (except range)",
                 "Superior version of the Beagle Active Probe (slightly "
                 "varying BTH, but ignores partial/woods/water)"),
]

NUM_SENSORS = len(sensors)  # mech.sensor.h:171

# Matchletter -> table index lookup (mech.sensor.h matchletter column).
SENSOR_LETTER_INDEX = {s.matchletter: i for i, s in enumerate(sensors)}


def sensor_index_from_letter(letter: str) -> int:
    """Table index for a sensor matchletter (upper-cased), -1 if unknown."""
    return SENSOR_LETTER_INDEX.get(letter.upper(), -1)


# =============================================================================
# MaxVis / MaxVar (mech.sensor.c:95-96)
# =============================================================================

def max_vis(mech, sensor_idx: int) -> int:
    """
    MaxVis (mech.sensor.c:95): sensors of index >= 2 (IR and up) get a 140%
    range boost when the unit is stationary (MechMove(mech) == MOVE_NONE —
    the unit's move class, not its current speed).
    """
    stationary = getattr(mech, 'move_type', None) == MoveType.NONE
    return (sensors[sensor_idx].maxvis *
            (140 if (sensor_idx >= 2 and stationary) else 100)) // 100


def max_var(mech, sensor_idx: int) -> int:
    """MaxVar (mech.sensor.c:96): the sensor's maxvvar."""
    return sensors[sensor_idx].maxvvar


def maxvr(mech, sensor_idx: int) -> int:
    """MAXVR (mech.sensor.c:97): MaxVis - MaxVar."""
    return max_vis(mech, sensor_idx) - max_var(mech, sensor_idx)


# =============================================================================
# Sensor_ToHitBonus (mech.sensor.c:27-77)
# =============================================================================

def sensor_to_hit_bonus(mech, target, flag: int, maplight: int,
                        hex_range: float, w_ammo_mode: int) -> int:
    """
    Sensor_ToHitBonus (mech.sensor.c:27-77).  Combines the primary and
    secondary sensors' to-hit bonuses: 10000 if neither sensor sees the
    target, secondary-only bonus +1, primary-only (or identical sensors)
    bonus straight, otherwise MIN(primary, secondary + 1).

    (The C's `range` parameter is unused by the body; kept as hex_range.)
    """
    w_light_mod = 1 if (w_ammo_mode & AC_INCENDIARY_MODE) else 0
    game_map = getattr(mech, 'map', None)

    maplight = maplight + w_light_mod
    if maplight < 0:
        maplight = 0
    if maplight > 2:
        maplight = 2

    if not (flag & (MECHLOSFLAG_SEESP | MECHLOSFLAG_SEESS)):
        return 10000
    if not (flag & MECHLOSFLAG_SEESP):
        return 1 + sensors[mech.sensor[1]].tohitbonus_func(
            mech, target, game_map, flag, maplight)
    if not (flag & MECHLOSFLAG_SEESS) or (mech.sensor[0] == mech.sensor[1]):
        return sensors[mech.sensor[0]].tohitbonus_func(
            mech, target, game_map, flag, maplight)
    bth1 = sensors[mech.sensor[0]].tohitbonus_func(
        mech, target, game_map, flag, maplight)
    bth2 = 1 + sensors[mech.sensor[1]].tohitbonus_func(
        mech, target, game_map, flag, maplight)
    return min(bth1, bth2)


# =============================================================================
# Range / 360-vision helpers
# =============================================================================

def sees360(mech) -> bool:
    """Sees360 (btmacros.h:667): MOVE_NONE movement or a battlesuit."""
    return (mech.move_type == MoveType.NONE or
            mech.unit_type == UnitType.BSUIT)


def fa_mech_range(mech, target) -> float:
    """
    3-D hex range between two units.  Port of FaMechRange (btmacros.h:733-735)
    over FindRange (mech.utils.c:749-757): cartesian distance / SCALEMAP.
    """
    return find_range3d(mech.fx, mech.fy, mech.fz,
                        target.fx, target.fy, target.fz)


# =============================================================================
# Sensor_CanSee (mech.sensor.c:79-158)
# =============================================================================

def sensor_can_see(mech, target, flag: int, arc: int, hex_range: float,
                   mapvis: int, maplight: int, cloudbase: int) -> int:
    """
    Whether the current sensors COULD see target/hex: 0 = no, else the sum
    of 1 (primary) and 2 (secondary).  Port of Sensor_CanSee
    (mech.sensor.c:79-158).

    (Signature deviation: the C takes int *flag; the body only reads it, so
    it is passed by value here.)

    C oddities preserved:
    - The arc / fullvision gate exists only on the split-sensor path; with
      identical primary and secondary sensors no arc check is made
      (mech.sensor.c:104-107 vs :141-157).
    - The single-sensor path has no cloudbase gate for hex (target-less)
      scans (mech.sensor.c:143-146).
    - "Horrible hack that'll break when new sensors get added": sensors of
      index < 3 (V/L/I) can't see through the cloud deck (mech.sensor.c:115).
    """
    game_map = getattr(mech, 'map', None)
    if not game_map or not mech:                       # mech.sensor.c:86-88
        return 0
    if not (flag & MECHLOSFLAG_SEEC2):                 # mech.sensor.c:89-90
        return 0
    if target and target.has_crit_status(CritStatus.INVISIBLE):   # :91-92
        return 0

    if mech.sensor[0] != mech.sensor[1]:               # mech.sensor.c:94
        j = 0
        for i in range(2):                             # Check both separately
            sn = mech.sensor[i]
            # No chance
            if (not sensors[sn].fullvision and
                    not (arc & (FORWARDARC | TURRETARC)) and
                    not sees360(mech)):                # mech.sensor.c:104-106
                continue
            if max_vis(mech, sn) < hex_range:          # mech.sensor.c:108-109
                continue
            if target:                                 # mech.sensor.c:115-126
                if cloudbase and sn < 3 and (
                        (target.z >= cloudbase) if mech.z < cloudbase
                        else (target.z < cloudbase)):
                    continue
            else:
                if cloudbase and mech.z > cloudbase:
                    continue
            if not sensors[sn].cansee_func(mech, target, game_map,
                                           hex_range, flag):      # :128-129
                continue
            if not sensors[sn].seechance_func(target, game_map, sn, hex_range,
                                              mapvis, maplight):  # :131-133
                continue
            if max_var(mech, sn) and maxvr(mech, sn) < hex_range:  # :135-140
                if (maxvr(mech, sn) +
                        (mech.vis_mod * (max_var(mech, sn) + 1)) // 100) < \
                        hex_range:
                    continue
            j += (i + 1)
        return j

    sn = mech.sensor[0]                                # mech.sensor.c:143
    if max_vis(mech, sn) < hex_range:
        return 0
    if cloudbase and target and sn < 3 and (
            (target.z >= cloudbase) if mech.z < cloudbase
            else (target.z < cloudbase)):              # mech.sensor.c:146-148
        return 0
    if not sensors[sn].cansee_func(mech, target, game_map, hex_range, flag):
        return 0
    if not sensors[sn].seechance_func(target, game_map, sn, hex_range,
                                      mapvis, maplight):
        return 0
    if max_var(mech, sn) and maxvr(mech, sn) < hex_range:  # :152-156
        if (maxvr(mech, sn) +
                mech.vis_mod * (max_var(mech, sn) + 1) // 100) < hex_range:
            return 0
    return 3


# =============================================================================
# Sensor_SeesNow and helpers (mech.sensor.c:160-282)
# =============================================================================

def sensor_arc_base_chance(unit_type, arc: int) -> int:
    """Sensor_ArcBaseChance (mech.sensor.c:160-186)."""
    base = 100
    if unit_type == UnitType.MW:
        if arc & (LSIDEARC | RSIDEARC | REARARC):
            return 0
    elif unit_type in (UnitType.BSUIT, UnitType.MECH):
        if arc & (LSIDEARC | RSIDEARC):
            base = 70
        elif arc & REARARC:
            base = 40
    else:
        if arc & (LSIDEARC | RSIDEARC):
            base = 80
        elif arc & REARARC:
            base = 50
        if arc & TURRETARC:
            base += 15
    return base


def sensor_driver_base_chance(mech) -> int:
    """
    Sensor_DriverBaseChance (mech.sensor.c:190-202): 64 + a perception-skill
    term ("Padded a bit").
    Startup/live registration populates MechPer from Pilot.perception.
    """
    per = mech.per
    if per <= 2:
        i = 36
    elif per >= 12:
        i = 1
    else:
        i = 36 - bth_modifier[per - 2]
    return 64 + i


def sensor_sees(mech, target, f: int, arc: int, hex_range: float, snum: int,
                chance_divisor: int, mapvis: int, maplight: int) -> int:
    """
    One sensor's actual spot-it-now roll.  Port of Sensor_Sees
    (mech.sensor.c:204-244) — "Slow, but sacrifices we make for sake of
    playability".

    Successful enemy detection retains the source's separate XP chance.
    """
    game_map = getattr(mech, 'map', None)
    chance = (sensor_arc_base_chance(mech.unit_type, arc) *
              (sensor_driver_base_chance(mech)
               if (target and mech.team != target.team) else 100)) // 100
    ch2 = sensors[snum].seechance_func(target, game_map, snum, hex_range,
                                       mapvis, maplight)

    if not ch2 or not sensors[snum].cansee_func(mech, target, game_map,
                                                hex_range, f):
        return 0
    if target and _is_ds(target):
        chance = chance * 4
    if target and (target.crit_status & CritStatus.HIDDEN) and \
            mech.team != target.team:                  # mech.sensor.c:222-235
        if (sensors[snum].matchletter[0] == 'B' and
                (getattr(target, 'infantry_specials', 0) & STEALTH_TECH) and
                not (getattr(target, 'infantry_specials', 0) &
                     CS_PURIFIER_STEALTH_TECH)):
            return 0
        if ch2 <= 100:
            if hex_range > 5:
                return 0
            chance = chance // 4
    if hex_range < 3 or \
            sensor_draw('sensor.detect', 1, 10000) < ((chance * ch2) // chance_divisor):
        if target and mech.in_character and target.in_character and mech.team != target.team:
            if sensor_draw('sensor.perception_xp', 0, 5) == 0:
                from systems.experience import perception
                perception(mech, -2)
        return 1
    return 0


def sensor_sees_now(mech, target, f: int, arc: int, hex_range: float,
                    mapvis: int, maplight: int) -> int:
    """
    Do the current sensors actually NOTICE the target this pass?  Port of
    Sensor_SeesNow (mech.sensor.c:246-282).  "If primary & secondary scanner
    differ, check both scanners for chance (with secondary at 1/2 chance).
    Also, if non-360degree scanners are used, check only forward arc for
    them."
    """
    if mech.sensor[0] != mech.sensor[1]:
        for i in range(2):                             # Check both separately
            sn = mech.sensor[i]
            # No chance
            if (not sensors[sn].fullvision and
                    not (arc & (FORWARDARC | TURRETARC)) and
                    not sees360(mech)):
                continue
            if max_vis(mech, sn) < hex_range:
                continue
            if sensor_sees(mech, target, f, arc, hex_range, sn, i + 1,
                           mapvis, maplight):
                return i + 1
        return 0
    sn = mech.sensor[0]
    if max_vis(mech, sn) < hex_range:
        return 0
    return sensor_sees(mech, target, f, arc, hex_range, sn, 1, mapvis,
                       maplight)
    # (Dead `return 3` after the return, mech.sensor.c:281 — unreachable.)


# =============================================================================
# Sensor_DoWeSeeNow (mech.sensor.c:333-461)
# =============================================================================

def sensor_do_we_see_now(mech, flag: int, hex_range: float, x: int, y: int,
                         target, mapvis: int, maplight: int, cloudbase: int,
                         seeanew: int, paranoia: int) -> int:
    """
    Update the SEEN/SEESP/SEESS bits of one LOS flag: maintain (or lose) an
    existing contact when MECHLOSFLAG_SEEN is set, otherwise try to gain one
    (only when seeanew is nonzero — the update_LOSinfo pass runs with
    seeanew=0 and only bumps pnum_seen; the PLOS sweep passes seeanew=1).
    Port of Sensor_DoWeSeeNow (mech.sensor.c:333-461).

    Signature contract: the C's `unsigned short *fl` out-param is the `flag`
    argument in and the updated flag as the return value; the caller writes
    it back into map.losinfo.  `paranoia` is the C's `wlf` (the had-LOS bit
    fed to valid_to_notice for the Lost message).

    New enemy contacts restore suspended AUTO state and command events.
    """
    f = flag
    hex_range = f32(hex_range)
    if not _started(mech):                             # mech.sensor.c:342-343
        return f
    if target:
        x1 = target.fx
        y1 = target.fy
        if mech.z >= ATMO_Z and target.z >= ATMO_Z:    # mech.sensor.c:347-348
            hex_range = f32(hex_range / 3)
    else:
        x1, y1 = hex_to_float(x, y)     # MapCoordToRealCoord (:350)
    arc = in_weapon_arc(mech, x1, y1)

    if f & MECHLOSFLAG_SEEN:                           # mech.sensor.c:352
        sl = sensor_can_see(mech, target, f, arc, hex_range, mapvis,
                            maplight, cloudbase)
        if sl:
            if sl & 1:
                f |= MECHLOSFLAG_SEESP
            if sl & 2:
                f |= MECHLOSFLAG_SEESS
        if not (f & (MECHLOSFLAG_SEESP | MECHLOSFLAG_SEESS)):
            # Contact lost (mech.sensor.c:361-405)
            if mech.team != target.team:
                # MechNumSeen (btmacros.h:167, rd.num_seen): plain attr,
                # calloc default 0.
                mech.num_seen = max(0, getattr(mech, 'num_seen', 0) - 1)
            f &= ~MECHLOSFLAG_SEEN
            contact_notice(mech, target, paranoia, seeanew, arc, gained=False)
            if mech.has_status(MechStatus.LOCK_TARGET) and \
                    target._id == mech.target:         # mech.sensor.c:387-392
                # "Weapon system reports the lock has been lost."
                from systems.targeting import lose_lock
                _notify(mech, "Weapon system reports the lock has been lost.")
                lose_lock(mech, mech._engine)
            mech.pnum_seen += 1                        # mech.sensor.c:401
        return f                                       # *fl = f; return (:403-404)

    sc = sensor_can_see(mech, target, f, arc, hex_range, mapvis, maplight,
                        cloudbase)                     # mech.sensor.c:406-408
    if sc:
        if not seeanew:
            # Whee, something we _could_ see (mech.sensor.c:409-413)
            mech.pnum_seen += 1
            return f
        sl = sensor_sees_now(mech, target, f, arc, hex_range, mapvis,
                             maplight)                 # mech.sensor.c:414-415
        if sl:
            if sc & 1:
                f |= MECHLOSFLAG_SEESP
            if sc & 2:
                f |= MECHLOSFLAG_SEESS
        if f & (MECHLOSFLAG_SEESP | MECHLOSFLAG_SEESS):
            # Contact gained (mech.sensor.c:422-453)
            if mech.team != target.team:
                mech.num_seen = getattr(mech, 'num_seen', 0) + 1
                from systems.autopilot import un_zombify_mech
                un_zombify_mech(mech)
            f |= MECHLOSFLAG_SEEN
            # The C writes through *fl before GetMechToMechID and
            # MechSeemsFriend read NB visibility for the notification.
            if mech.map.losinfo is None:
                mech.map.losinfo = {}
            mech.map.losinfo[(mech._id,target._id)] = f
            contact_notice(mech, target, -1, seeanew, arc, gained=True)
            if mech.team != target.team and target._engine is not None:
                from core.events import EventType
                target._engine.cancel_events_of_type(EventType.HIDE, target)
        else:
            mech.pnum_seen += 1                        # mech.sensor.c:459
    return f


# =============================================================================
# update_LOSinfo (mech.sensor.c:463-580)
# =============================================================================

def _update_losinfo_pair(gamemap, mech, target, mapvis: int,
                         maplight: int) -> None:
    """
    One ordered (looker, target) pair of the update_LOSinfo sweep.  The C
    duplicates this body verbatim in its two triangle loops
    (mech.sensor.c:475-508 and :512-573, the second differing only by a
    commented-out Started/BLOCK short-circuit); factored here.
    """
    losinfo = gamemap.losinfo
    key = (mech._id, target._id)
    rng = fa_mech_range(mech, target)                  # mech.sensor.c:480

    # Side-effect calls hitching a ride on the sweep (mech.sensor.c:481-488)
    from systems.ecm import (
        check_ecm, ecm_enabled, eccm_enabled,
        angel_ecm_enabled, angel_eccm_enabled,
    )
    if ecm_enabled(mech) or eccm_enabled(mech) or \
            angel_ecm_enabled(mech) or angel_eccm_enabled(mech):
        if rng < ECM_RANGE:
            check_ecm(target)
    from systems.targeting import check_tag
    check_tag(mech)
    if mech.status2 & SLITE_ON and rng < LITE_RANGE:
        cause_lite(mech, target)

    if rng > gamemap.maxvis and target.z < 11 and mech.z < 11:
        # Out of worst-case sensor range: flag becomes BLOCK alone, wiping
        # SEEN/SEEC2 too (mech.sensor.c:489-493).
        losinfo[key] = MECHLOSFLAG_BLOCK
        return
    old = losinfo.get(key, 0)
    wlf = int(not (old & MECHLOSFLAG_BLOCK) and
              bool(old & (MECHLOSFLAG_SEESP | MECHLOSFLAG_SEESS)))
    losinfo[key] = calculate_los_flag(mech, target, gamemap, target.x,
                                      target.y, old, float(rng))
    # Then, we update the SEES* (ADVANCED_LOS build, mech.sensor.c:500-507)
    losinfo[key] = sensor_do_we_see_now(
        mech, losinfo[key], rng, -1, -1, target, mapvis, maplight,
        gamemap.cloudbase, 0, wlf)


def update_los_info(gamemap) -> None:
    """
    The per-second pairwise LOS/sensor sweep over a map's roster.  Port of
    update_LOSinfo (mech.sensor.c:463-580).

    Container deviation (authorized): the C's roster-slot matrix
    LOSinfo[i][j] is the (looker._id, target._id) dict on GameMap;
    initialized to {} on first sweep (the C callocs it with the map).

    C fidelity notes:
    - Two triangle loops, upper (i, j>i; mech.sensor.c:472-509) then lower
      (i>=1, j<i; :510-574), each skipping non-Started LOOKERS only —
      shutdown/destroyed units still get scanned as targets.
    - In this checkout the per-pair moved-gating is `if(1)` (both loops):
      every started looker recomputes every pair every sweep.  The
      MECHMAPFLAG_MOVED flags (set by MarkForLOSUpdate) are only cleared at
      the end (mech.sensor.c:574-575); nothing reads them.
    - Sensor_DoWeSeeNow runs with seeanew=0: this sweep maintains and loses
      contacts but never gains one — gains come from the PLOS sweep
      (mech_plos_event, mech.events.c:385-388, seeanew=1).
    """
    mapvis = gamemap.mapvis
    maplight = gamemap.maplight
    if gamemap.losinfo is None:
        gamemap.losinfo = {}
    mechs = gamemap.mechs_on_map

    # First, for all moved mechs, calculate new LOS flags (mech.sensor.c:471)
    for i, mech in enumerate(mechs):                   # mech.sensor.c:472-509
        if mech is None:
            continue
        if not _started(mech):
            continue
        for target in mechs[i + 1:]:
            if target is None:
                continue
            _update_losinfo_pair(gamemap, mech, target, mapvis, maplight)
    for i in range(1, len(mechs)):                     # mech.sensor.c:510-574
        mech = mechs[i]
        if mech is None:
            continue
        if not _started(mech):
            continue
        for target in mechs[:i]:
            if target is None:
                continue
            _update_losinfo_pair(gamemap, mech, target, mapvis, maplight)
    for mech in mechs:                                 # mech.sensor.c:574-575
        if mech is not None:
            mech.mapflag = 0
    if hasattr(gamemap,'mechflags'):
        gamemap.mechflags[:]=[0]*len(gamemap.mechflags)


# =============================================================================
# possibly_see_mech / sensor scramble / blind recovery
# (mech.sensor.c:828-935)
# =============================================================================

# Message hook, same pattern as systems.missile.NOTIFY_HOOK.
NOTIFY_HOOK = None


def _notify(mech, message: str) -> None:
    from systems.movement_commands import notify
    notify(mech, message)
    if NOTIFY_HOOK is not None:
        NOTIFY_HOOK(mech, message)


def possibly_see_mech(mech) -> None:
    """
    Give every other unit on the map an immediate, quiet chance to notice
    this one — the "bonus" contact pass fired by flashy events (reactor
    explosions, aero crashes) outside the 1 Hz sweep.

    Port of possibly_see_mech (mech.sensor.c:828-869): per seer, the pair's
    LOS flag is recomputed and Sensor_DoWeSeeNow runs with seeanew=2
    (gain allowed, no "you notice" message).
    """
    from systems.los import calculate_los_flag

    gamemap = mech.map
    if gamemap is None:
        return
    if gamemap.losinfo is None:
        gamemap.losinfo = {}
    mapvis = gamemap.mapvis
    maplight = gamemap.maplight
    for index, seer in enumerate(gamemap.mechs_on_map):
        if seer is None or seer is mech:
            continue
        if seer.map is not gamemap or seer.mapindex != gamemap._id:
            from core.effects import send_error
            send_error(mech, f'Mech #{seer._id} was on map #{gamemap._id} but with incorrect mapindex ({seer.mapindex})')
            gamemap.mechs_on_map[index] = None
            continue
        rng = fa_mech_range(seer, mech)
        key = (seer._id, mech._id)
        old = gamemap.losinfo.get(key, 0)
        gamemap.losinfo[key] = calculate_los_flag(
            seer, mech, gamemap, mech.x, mech.y, old, float(rng))
        gamemap.losinfo[key] = sensor_do_we_see_now(
            seer, gamemap.losinfo[key], rng, -1, -1, mech, mapvis,
            maplight, gamemap.cloudbase, 2, 0)


def mech_unblind(mech) -> None:
    """
    Blind recovery: EVENT_BLINDREC firing (mech_unblind_event,
    mech.sensor.c:870-877).
    """
    from entities.mech import MechStatus

    mech.clear_status(MechStatus.BLINDED)
    if not mech.has_status(MechStatus.UNCONSCIOUS):
        _notify(mech, "Your sight recovers.")


def scramble_infra_and_liteamp(mech, time: int, chance: int,
                               inframsg: str, liteampmsg: str) -> None:
    """
    Blind every watcher whose primary sensor is infrared or light-amp.

    Port of ScrambleInfraAndLiteAmp (mech.sensor.c:879-935): a quiet
    possibly-see pass first, then every unit with LOS to this one on an
    'I' or 'L' primary sensor (chance% each when chance is nonzero) is
    BLINDED for `time` seconds.  The C's EVENT_BLINDREC is carried as a
    per-mech countdown fired by systems.piloting.piloting_periodic, the
    same shape as the unconsciousness recovery event.
    """
    from entities.mech import MechStatus
    from systems.los import in_line_of_sight

    gamemap = mech.map
    if gamemap is None:
        return
    possibly_see_mech(mech)
    for temp_mech in gamemap.mechs_on_map:
        if temp_mech is None or temp_mech is mech:
            continue
        if not in_line_of_sight(temp_mech, mech, mech.x, mech.y,
                                fa_mech_range(temp_mech, mech)):
            continue
        if (temp_mech.has_status(MechStatus.BLINDED) or
                temp_mech.has_status(MechStatus.UNCONSCIOUS)):
            continue
        letters = sensors[temp_mech.sensor[0]].matchletter
        if letters[0] == 'I' or (len(letters) > 1 and letters[1] == 'I'):
            if chance and sensor_draw('sensor.flash', 1, 100) > chance:
                continue
            _notify(temp_mech, inframsg)
        elif letters[0] == 'L' or (len(letters) > 1 and letters[1] == 'L'):
            if chance and sensor_draw('sensor.flash', 1, 100) > chance:
                continue
            _notify(temp_mech, liteampmsg)
        else:
            continue
        temp_mech.set_status(MechStatus.BLINDED)
        if temp_mech._engine is not None:
            from core.events import EventType
            temp_mech._engine.schedule_event(time, EventType.BLINDREC, lambda e: mech_unblind(e.data), data=temp_mech)
        else:
            temp_mech.blind_recovery_countdown = time


# Unit illumination: mech.lite.c and mech.advanced.c:139-209.
def mech_lites_target(mech, target):
    from systems.los import mech_to_mech_los_flag
    if mech.map is None or target.map is not mech.map or not mech.status2 & SLITE_ON:
        return False
    flag = mech_to_mech_los_flag(mech.map, mech, target)
    return (fa_mech_range(mech, target) <= LITE_RANGE and
            bool(in_weapon_arc(mech, target.fx, target.fy) & FORWARDARC) and
            not flag & MECHLOSFLAG_BLOCK and mech_losflag_wood_count(flag) <= 2 and
            mech_losflag_water_count(flag) == 0)


def cause_lite(mech, target):
    if target.crit_status & CritStatus.SLITE_LIT:
        return
    if mech_lites_target(mech, target):
        target.crit_status |= CritStatus.SLITE_LIT
        if target.sl_warn:
            _notify(target, 'You are being illuminated!')


def end_lite_check(mech):
    if mech.map is None or not mech.crit_status & CritStatus.SLITE_LIT:
        return
    if any(u is not None and u is not mech and mech_lites_target(u, mech)
           for u in mech.map.mechs_on_map):
        return
    mech.crit_status &= ~CritStatus.SLITE_LIT
    if mech.sl_warn:
        _notify(mech, 'You are no longer being illuminated.')


def los_broadcast(mech, message):
    from systems.los import in_line_of_sight
    from systems.notifications import identity, mech_notify, MECHSTARTED, LBUF_SIZE
    possibly_see_mech(mech)
    if mech.map is None:
        return
    for other in mech.map.mechs_on_map:
        if other is not None and other is not mech and in_line_of_sight(other, mech, mech.x, mech.y, fa_mech_range(other, mech)):
            text = identity(other,mech)+('' if message.startswith("'") else ' ')+message
            mech_notify(other, MECHSTARTED, text[:LBUF_SIZE - 1])


def slite_change_event(event):
    mech = event.data
    if mech.crit_status & CritStatus.SLITE_DEST or not mech.is_started:
        return
    if event.data2 == 1:
        mech.status2 |= SLITE_ON
        mech.crit_status |= CritStatus.SLITE_LIT
        _notify(mech, 'Your searchlight comes on to full power.')
        los_broadcast(mech, 'turns on a searchlight!')
    else:
        mech.status2 &= ~SLITE_ON
        mech.crit_status &= ~CritStatus.SLITE_LIT
        _notify(mech, 'Your searchlight shuts off.')
        los_broadcast(mech, 'turns off a searchlight!')
    from systems.ecm import mark_for_los_update
    mark_for_los_update(mech)


def slite(engine, mech, caller=None, *, wizard=False):
    from core.events import EventType
    from systems.combat_commands import command_guard, command_message
    def reply(ok, text, audience=None):
        return ok, command_message(mech,text,caller=caller,audience=audience)
    error = command_guard(mech, caller=caller, wizard=wizard)
    if error:
        return reply(False,error)
    if not mech.specials & Specials.SLITE_TECH:
        return reply(False,"Your 'mech isn't equipped with searchlight!",2)
    if mech.crit_status & CritStatus.SLITE_DEST:
        return reply(False,'Your searchlight has been destroyed already!')
    on = bool(mech.status2 & SLITE_ON)
    if engine.has_event(EventType.SLITE_CHANGE, mech):
        return reply(False,'Your searchlight is already in the process of turning ' + ('off.' if on else 'on.'),2)
    result = reply(True,'Your searchlight starts to ' + ('cool down.' if on else 'warm up.'),2)
    engine.schedule_event(5, EventType.SLITE_CHANGE, slite_change_event, data=mech, data2=int(not on))
    return result


def sensor_draw(name, low, high):
    from core.randomness import draw
    return draw(name,low,high,lambda: random.randint(low,high))


def dump_flag(flag):
    return ','.join(str(i) for i in range(32) if flag & (1<<i))


def valid_to_notice(mech, target, los):
    from systems.los import in_line_of_sight_nb
    friend = mech.team == target.team and (los > 0 or los < 0 and in_line_of_sight_nb(mech,target,target.x,target.y,0))
    warning = 0 if friend else 2
    mode = mech.brief//4
    return {0:1|warning,1:4|warning,2:(1|warning) if warning else 0,
            3:(4|warning) if warning else 0,4:4,5:4 if warning else 0}.get(mode,0)


def contact_notice(mech,target,los,seeanew,arc,gained):
    if getattr(mech,'is_observator',False) or mech.crit_status & CritStatus.OBSERVATORIC:
        return
    if not (target.is_started or int(mech.status) & 0x00800000 or mech.autocon_shutdown):
        return
    style=valid_to_notice(mech,target,los)
    if not style or seeanew >= (2 if gained else 3):
        return
    from systems.network_reports import arc_label
    from systems.notifications import identity_base, MBUF_SIZE
    arcname = arc_label(mech, arc)
    from systems.los import in_line_of_sight_nb
    identified = in_line_of_sight_nb(mech,target,target.x,target.y,0) if gained else los
    name = identity_base(mech, target, identified)
    if style & 4:
        text=f'{"Seen" if gained else "Lost"}: {name}, {arcname} arc.'
    elif gained:
        text=f'You notice {name} in your {arcname} arc.'
    else:
        text=f'You have lost {name} from your scanners. It was last in your {arcname} arc.'
    # C's long Lost snprintf overwrites the initial yellow prefix.
    prefix = ('%cr' if gained else '%cy' if style & 4 else '') if style & 2 else ''
    text = (prefix + text)[:MBUF_SIZE - 1]
    if style & 2:
        text += '%cn'
    _notify(mech,text)


def mech_losemit(mech, text, caller=None):
    """mech_losemit's MECH_USUALSP checks and actor acknowledgement."""
    from systems.communications import common_checks, MECH_USUALSP
    actor = caller if caller is not None else getattr(mech, 'command_actor', getattr(mech, 'pilot', None))
    error = common_checks(mech, actor, MECH_USUALSP)
    if error is not None:
        return False, error
    los_broadcast(mech, text)
    return True, 'Broadcast done.'
