# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# Host-derived portions also retain notices/TinyMUX.txt.
# General sources:
#   btech/btpr/conf.c
#   btech/crit.c
#   btech/mech.bth.c
#   btech/mech.combat.c
#   btech/mech.combat.misc.c
#   btech/mech.combat.missile.c
#   btech/mech.damage.c
#   btech/mech.hitloc.c
#   btech/mech.ice.c
#   btech/mech.notify.c
#   btech/mech.ood.c
#   btech/mech.scan.c
#   btech/mech.update.c
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/mech.combat.h
#   btech/src/btech/mech.h
#   btech/src/glue.scode.c
#   btech/src/include/btconfig.h
#   src/conf.c
# Historical Aerospace sources:
#   btech/crit.c
#   btech/ds.turret.c
#   btech/mech.bth.c
#   btech/mech.damage.c
#   btech/mech.hitloc.c
#   btech/mech.utils.c
#   src/hcode/btech/btmacros.h
#   src/hcode/btech/mech.combat.h
#   src/hcode/btech/mech.h
#   src/hcode/glue.scode.c
#   src/hcode/include/btconfig.h

"""
Combat system for BTMux Python reimplementation.

This module implements the combat resolution mechanics including:
- Base to-hit (BTH) calculation
- Hit location determination
- Damage application
- Weapon recycle tracking

Reference:
- BTMux btech/src/btech/mech.bth.c - To-hit calculations
- BTMux btech/src/btech/mech.hitloc.c - Hit location tables
- BTMux btech/src/btech/mech.combat.c - Combat resolution
- BTMux btech/src/btech/mech.damage.c - Damage application

Key mechanics:
- 2d6 roll to-hit vs. Base To-Hit (BTH)
- BTH = gunnery skill + range modifier + movement modifiers + other
- Damage applied to hit location (2d6 location table)
- Armor absorbs damage, then internals, then criticals
"""
from core.randomness import record_critical_roll, roll as source_roll
from core.randomness import draw

import random
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from entities.mech import Mech
    from entities.weapon import Weapon

from entities.mech import (
    Location, UnitType, MechStatus, MechStatus2, CritStatus, MoveType,
    Specials, FireMode, AmmoMode, VehicleLocation, AeroLocation, SectionConfig,
    NUM_CRITICALS, NUM_SECTIONS,
)
from entities.crittypes import i2ammo, i2weapon
from physics.hexmath import (
    NOARC, FORWARDARC, LSIDEARC, RSIDEARC, REARARC, TURRETARC,
)


# Targeting-computer types (mech.h:1209-1214).  Carried on Mech.targcomp,
# a plain attribute: the C has NO targcomp command; MechTargComp is written
# only via softcode (glue.scode.c:468).
TARGCOMP_NORMAL = 0     # mech.h:1210
TARGCOMP_SHORT = 1      # mech.h:1211
TARGCOMP_LONG = 2       # mech.h:1212
TARGCOMP_MULTI = 3      # mech.h:1213
TARGCOMP_AA = 4         # mech.h:1214

# The four explicit hex-lock modes (mech.h; set by `settarget x y B/I/C/H`,
# mech.combat.c:280-295).  A plain coordinate lock is LOCK_TARGET without
# any of these bits (MechLockFire, mech.h:1078-1080).
HEX_LOCK_MODES = (MechStatus.LOCK_BUILDING | MechStatus.LOCK_HEX |
                  MechStatus.LOCK_HEX_IGN | MechStatus.LOCK_HEX_CLR)

# Sentinel for calculate_bth's unstable_lock_arc kwarg: FindTargetXY failed,
# so the shot is a coordinate-less hip shot (mech.bth.c:278-280).
UNSTABLE_LOCK_HIPSHOT = -1


# =============================================================================
# Combat Constants
# =============================================================================

# Hit groups (attack direction)
class HitGroup(IntEnum):
    """Attack direction for hit location determination."""
    FRONT = 0
    LEFTSIDE = 1
    RIGHTSIDE = 2
    BACK = 3


# mudconf.btech_hit_arcs - which hit-location arc rules to use:
#   0 = TW rules (mech front 90/aft 30, vehicles 30/30)
#   1 = classic BTMUX rules (45/45 for everything)
#   2 = BMR rules (90/30 for everything)
# Default 0, matching the C (src/conf.c:93). Table at mech.hitloc.c:2854-2879.
BTECH_HIT_ARCS = 0


# Default gunnery / piloting skills - defined once in systems/piloting.py
# alongside the FindPilot* chain (mech.utils.c:580-629), re-exported here so the
# historical `from systems.combat import DEFAULT_GUNNERY` imports keep resolving.
from systems.piloting import (
    DEFAULT_GUNNERY, DEFAULT_PILOTING, find_pilot_spotting,
)

# BTH modifiers
BTH_PULSE_BONUS = -2          # Pulse lasers get -2
BTH_MRM_PENALTY = 1           # MRMs get +1
BTH_HEAVY_WEAPON_PENALTY = 1  # Heavy weapons get +1
BTH_ROCKET_PENALTY = 1        # Rocket launchers get +1
BTH_HEAT_THRESHOLDS = [
    (24, 4),  # 24+ heat: +4 BTH
    (17, 3),  # 17-23 heat: +3 BTH
    (13, 2),  # 13-16 heat: +2 BTH
    (8, 1),   # 8-12 heat: +1 BTH
]

# Movement BTH modifiers
BTH_STANDING = 2              # Standing from prone
BTH_JUMPING = 3               # Jumping
BTH_FALLEN = 2                # Fallen (quad with legs ok = 0)
BTH_WALKING = 1               # Walking
BTH_RUNNING = 2               # Running

# Movement point speeds in KPH (mech.h:54-60). TargetMovementMods compares the
# target's *float* KPH straight against these with contiguous <= tests, so
# fractional MP can never fall into a gap the way an integer hex bracket can.
MP1 = 10.75                   # mech.h:54 - #define MP1 10.75
MP2 = 21.50                   # mech.h:55 - #define MP2 21.50
MP4 = 43.00                   # mech.h:57 - #define MP4 43.00
MP6 = 64.50                   # mech.h:59 - #define MP6 64.50
MP9 = 96.75                   # mech.h:60 - #define MP9 96.75

# Target movement modifiers
TARGET_IMMOBILE_BONUS = -4    # Immobile target: -4
TARGET_FALLEN_CLOSE_BONUS = -2  # Fallen target at range <= 1
TARGET_FALLEN_FAR_PENALTY = 1   # Fallen target at range > 1
TARGET_JUMPING_PENALTY = 1      # Jumping target: +1

# mudconf.btech_extendedmovemod - use MaxTech's extended target movement
# modifiers for speeds above MP9 (mech.bth.c:778-781). Default 1, matching the
# C's shipped default (src/conf.c:132, identically btech/btpr/conf.c:75).
#
# Oddity kept deliberately: the extended formula is
# `4 + (target_speed - 10 * MP1) / MP4` assigned to an int, so speeds just past
# MP9 (96.75) score *below* the flat +4 cap - 100 KPH gives 3, and +4 is only
# reached again at 10 MP (107.5 KPH). Set to 0 for the flat +4.
BTECH_EXTENDEDMOVEMOD = 1

# mudconf btech_moddamagewithwoods (src/conf.c:108, default 0): woods grant
# a to-hit bonus instead of the usual treatment.
BTECH_MODDAMAGEWITHWOODS = 0


# =============================================================================
# Hit Location Tables (from mech.hitloc.c)
# =============================================================================

# Standard mech hit locations by 2d6 roll
# Format: {hit_group: {roll: location}}

MECH_HIT_LOCATIONS = {
    HitGroup.FRONT: {
        2:  (Location.CTORSO, True),   # Critical hit
        3:  Location.RARM,
        4:  Location.RARM,
        5:  Location.RLEG,
        6:  Location.RTORSO,
        7:  Location.CTORSO,
        8:  Location.LTORSO,
        9:  Location.LLEG,
        10: Location.LARM,
        11: Location.LARM,
        12: Location.HEAD,
    },
    HitGroup.LEFTSIDE: {
        2:  (Location.LTORSO, True),   # Critical hit
        3:  Location.LLEG,
        4:  Location.LARM,
        5:  Location.LARM,
        6:  Location.LLEG,
        7:  Location.LTORSO,
        8:  Location.CTORSO,
        9:  Location.RTORSO,
        10: Location.RARM,
        11: Location.RLEG,
        12: Location.HEAD,
    },
    HitGroup.RIGHTSIDE: {
        2:  (Location.RTORSO, True),   # Critical hit
        3:  Location.RLEG,
        4:  Location.RARM,
        5:  Location.RARM,
        6:  Location.RLEG,
        7:  Location.RTORSO,
        8:  Location.CTORSO,
        9:  Location.LTORSO,
        10: Location.LARM,
        11: Location.LLEG,
        12: Location.HEAD,
    },
    HitGroup.BACK: {
        2:  (Location.CTORSO, True),   # Critical hit
        3:  Location.RARM,
        4:  Location.RARM,
        5:  Location.RLEG,
        6:  Location.RTORSO,
        7:  Location.CTORSO,
        8:  Location.LTORSO,
        9:  Location.LLEG,
        10: Location.LARM,
        11: Location.LARM,
        12: Location.HEAD,
    },
}

# Punch hit locations (1d6)
PUNCH_HIT_LOCATIONS = {
    HitGroup.FRONT: {
        1: Location.LARM,
        2: Location.LTORSO,
        3: Location.CTORSO,
        4: Location.RTORSO,
        5: Location.RARM,
        6: Location.HEAD,
    },
    HitGroup.LEFTSIDE: {
        1: Location.LTORSO,
        2: Location.LTORSO,
        3: Location.CTORSO,
        4: Location.LARM,
        5: Location.LARM,
        6: Location.HEAD,
    },
    HitGroup.RIGHTSIDE: {
        1: Location.RTORSO,
        2: Location.RTORSO,
        3: Location.CTORSO,
        4: Location.RARM,
        5: Location.RARM,
        6: Location.HEAD,
    },
    HitGroup.BACK: {
        1: Location.LARM,
        2: Location.LTORSO,
        3: Location.CTORSO,
        4: Location.RTORSO,
        5: Location.RARM,
        6: Location.HEAD,
    },
}

# Kick hit locations (1d6)
KICK_HIT_LOCATIONS = {
    HitGroup.FRONT: {
        1: Location.RLEG,
        2: Location.RLEG,
        3: Location.RLEG,
        4: Location.LLEG,
        5: Location.LLEG,
        6: Location.LLEG,
    },
    HitGroup.LEFTSIDE: {
        1: Location.LLEG,
        2: Location.LLEG,
        3: Location.LLEG,
        4: Location.LLEG,
        5: Location.LLEG,
        6: Location.LLEG,
    },
    HitGroup.RIGHTSIDE: {
        1: Location.RLEG,
        2: Location.RLEG,
        3: Location.RLEG,
        4: Location.RLEG,
        5: Location.RLEG,
        6: Location.RLEG,
    },
    HitGroup.BACK: {
        1: Location.RLEG,
        2: Location.RLEG,
        3: Location.RLEG,
        4: Location.LLEG,
        5: Location.LLEG,
        6: Location.LLEG,
    },
}

# Transfer damage locations (when a section is destroyed)
TRANSFER_LOCATIONS = {
    Location.LARM: Location.LTORSO,
    Location.RARM: Location.RTORSO,
    Location.LLEG: Location.LTORSO,
    Location.RLEG: Location.RTORSO,
    Location.LTORSO: Location.CTORSO,
    Location.RTORSO: Location.CTORSO,
    Location.HEAD: None,       # Head destruction = death
    Location.CTORSO: None,     # CT destruction = death
}


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class AttackResult:
    """Result of an attack attempt."""
    command_accepted: bool = False  # FireWeaponNumber return value.
    target_id: Optional[int] = None      # Resolved unit, including spotter/hex selection
    hex_target_label: Optional[str] = None  # Source short_hextarget firing-log label
    observer_modifier: Optional[int] = None  # FireSpot's indirectFire input
    hit: bool = False                    # Did the attack hit?
    glancing: bool = False
    impact_bth: Optional[int] = None
    swarm_attack: bool = False
    range_ok: bool = True
    ams_shot_down: int = 0
    missiles_remaining: int = 0
    swarm_targets: list = field(default_factory=list)
    roll: int = 0                        # The 2d6 roll
    bth: int = 0                         # Base to-hit number
    margin: int = 0                      # Roll - BTH (positive = hit)
    location: Optional[Location] = None  # Where it hit
    is_rear: bool = False                # Hit rear armor?
    is_critical: bool = False            # Automatic critical?
    damage_dealt: int = 0                # Total damage dealt
    armor_damage: int = 0                # Damage to armor
    internal_damage: int = 0             # Damage to internals
    criticals_rolled: int = 0            # Number of critical hits
    target_destroyed: bool = False       # Was target destroyed?
    messages: list[str] = field(default_factory=list)
    message_audiences: list = field(default_factory=list)
    # Full BTH breakdown of the attack (None for gate failures that never
    # reached resolve_attack).  Port observability aid: the C prints the
    # BTHADD trail with the SHOWBTH debug flag (mech.bth.c:33-39).
    bth_breakdown: Optional['BTHBreakdown'] = None
    # Impossible shots return after the attack draw, before shot resources.
    roll_impossible: bool = False
    shot_aborted: bool = False
    streak_lock_failed: bool = False
    failure_type: str = "NONE"
    failure_modifier: int = 0
    critical_bth: int = 0
    handled: bool = True                # FireSpot C return: false means unhandled
    los: Optional[int] = None            # Source firing LOS, distinct from observer LOS


@dataclass
class BTHBreakdown:
    """Detailed breakdown of BTH calculation."""
    base: int = 0                        # Base gunnery skill
    range_mod: int = 0                   # Range modifier
    range_bracket: str = 'TOFAR'
    c3_ref: int = -1
    attacker_move: int = 0               # Attacker movement modifier
    target_move: int = 0                 # Target movement modifier
    weather_mod: int = 0                 # Authorized shared weather term.
    heat_mod: int = 0                    # Heat modifier
    terrain_mod: int = 0                 # Terrain modifier
    other_mods: int = 0                  # Misc modifiers
    weapon_mod: int = 0                  # Weapon-specific modifiers
    section_mod: int = 0                 # Firing section's basetohit (crits)
    unstable_lock_mod: int = 0           # Unstable lock / hip shot (mech.bth.c:269-281)
    hex_mod: int = 0                     # "HexBonus" -4, explicit hex-lock
                                         # shot at an empty hex (mech.bth.c:292-295)
    spotting_mod: int = 0                # "Spotting": spotter skill - 4 on an
                                         # indirect shot (mech.bth.c:78-86) and
                                         # +1 while self-spotting (mech.bth.c:305-307)
    idf_terrain_mod: int = 0             # "IDFTerrain": the spotter-side terrain
                                         # term threaded through indirectFire
                                         # (mech.bth.c:301-303)
    targcomp_mod: int = 0                # TargComp SHORT/LONG bracket, AA and
                                         # MULTI side-arc terms (mech.bth.c:
                                         # 161-180, 257-263, 284-288)
    aim_mod: int = 0                     # "HeadTarget" +7 / "HeadTarget-Fake"
                                         # +25 and "TC" -1 / +3
                                         # (mech.bth.c:324-339)
    ammo_mode_mod: int = 0               # "ArmorPiercing" +1 / "LBX" -1|-3
                                         # (mech.bth.c:221-222, 265-267)
    pod_mod: int = 0                     # "HaywirePod" +1 / "iNARC" -1
                                         # (mech.bth.c:224-230)
    total: int = 0                       # Final BTH

    def calculate_total(self) -> int:
        """Calculate total BTH from components."""
        self.total = (
            self.base + self.range_mod + self.attacker_move +
            self.target_move + self.heat_mod + self.terrain_mod +
            self.other_mods + self.weapon_mod + self.section_mod +
            self.unstable_lock_mod + self.hex_mod + self.spotting_mod +
            self.idf_terrain_mod + self.targcomp_mod + self.aim_mod +
            self.ammo_mode_mod + self.pod_mod + self.weather_mod
        )
        return self.total


# =============================================================================
# Dice Rolling
# =============================================================================

def roll_1d6() -> int:
    """Roll one 6-sided die."""
    from core.randomness import number
    return number(1, 6)


def roll_2d6() -> int:
    """Roll two 6-sided dice."""
    return source_roll()


def roll_dice(count: int, sides: int = 6) -> int:
    """Roll multiple dice."""
    from core.randomness import number
    return sum(number(1, sides) for _ in range(count))


# =============================================================================
# BTH Calculation Functions
# =============================================================================

def calculate_overheat_modifier(heat: float) -> int:
    """
    Calculate BTH modifier from heat.

    Reference: mech.bth.c OverheatMods()
    """
    for threshold, modifier in BTH_HEAT_THRESHOLDS:
        if heat >= threshold:
            return modifier
    return 0


def calculate_attacker_movement_modifier(mech: 'Mech') -> int:
    """
    Calculate BTH modifier from attacker's movement.

    Reference: mech.bth.c AttackMovementMods()
    """
    from systems.combat_ranges import config
    from systems.parts import count_destroyed_legs
    from core.events import EventType
    if mech.unit_type == UnitType.BSUIT:
        return 0
    maximum = mech.max_speed
    if mech.heat >= 9 and mech.specials & Specials.TRIPLE_MYOMER_TECH:
        maximum += 1.5 * MP1
    if mech.is_jumping:
        return 3
    if (mech.is_fallen and mech.unit_type not in (UnitType.DS, UnitType.SPHEROID_DS)
            and (mech.move_type != MoveType.QUAD or count_destroyed_legs(mech) > 0)):
        return 2
    queue = getattr(getattr(mech, '_engine', None), 'events', None)
    if queue and any(queue.has_event_type_data(kind, mech)
                     for kind in (EventType.STAND, EventType.JUMPSTABIL)):
        return 2
    base = int(bool(config(mech, 'fasaturn', 1)) and mech.facing != mech.desired_facing)
    if mech.speed == 0:
        return base
    return 2 if mech.speed > maximum * 2 / 3 + 0.1 else base + 1


def is_target_immobile(target: 'Mech') -> bool:
    """Source Immobile, retaining the historical Aerospace macro.

    The recovered pre-AT2 predicate has no FORTIFIED term; general units
    retain that term. Destruction reaches this predicate through Shutdown.
    """
    # !Started(a)
    if not target.is_started:
        return True

    # Uncon(a) - mech.h:1085 - MechStatus & UNCONSCIOUS
    if target.is_unconscious:
        return True

    # Fortified(a) - btmacros.h:478 - MechStatus2 & FORTIFIED
    if not is_aero(target) and target.status2 & MechStatus2.FORTIFIED:
        return True

    # Blinded(a) - mech.h:1083 - MechStatus & BLINDED
    if target.has_status(MechStatus.BLINDED):
        return True

    # MechMove(a) == MOVE_NONE - mech.h:741
    if target.move_type == MoveType.NONE:
        return True

    # Fallen non-mechs (vehicles etc.) are immobile; fallen mechs and ejected
    # MechWarriors are not (they get the Fallen term at mech.bth.c:788-790).
    if target.is_fallen and target.unit_type not in (UnitType.MECH, UnitType.MW):
        return True

    return False


def is_aero(unit):
    return unit is not None and unit.unit_type in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS)


def is_flying_type(unit):
    return is_aero(unit) or unit.move_type == MoveType.VTOL


def calculate_target_movement_modifier(target: 'Mech', distance: float, attacker=None) -> int:
    """TargetMovementMods: aero velocity, jump capability, swarm host and stealth."""
    from math import hypot
    from systems.combat_ranges import config
    from systems.combat_firing import swarm_id
    from systems.targeting import resolve_unit
    if is_aero(target):
        divisor = 5 if is_aero(attacker) else 1
        from core.randomness import float32
        target_speed = float32(hypot(target.speed / divisor, target.vertical_speed / divisor))
    else:
        mover = target
        if not target.is_jumping and swarm_id(target) > 0:
            mover = resolve_unit(target, swarm_id(target))
        target_speed = 0 if mover is None else abs(mover.speed)
        if mover is not None and mover.is_jumping:
            target_speed = mover.jump_speed
            if mover.status & MechStatus.UNDERGRAVITY and target.map:
                target_speed *= 100 / max(50, target.map.grav)
    if target.infantry_specials & 8:
        modifier = 3 if target_speed == 0 else 2 if target_speed <= MP1 else 1 if target_speed <= MP2 else 0
    elif target_speed <= MP2:
        # Mech moved 0-2 hexes
        modifier = 0
    elif target_speed <= MP4:
        # Mech moved 3-4 hexes
        modifier = 1
    elif target_speed <= MP6:
        # Mech moved 5-6 hexes
        modifier = 2
    elif target_speed <= MP9:
        # Mech moved 7-9 hexes
        modifier = 3
    else:
        # Moving more than 9 hexes
        if config(target, 'extendedmovemod', BTECH_EXTENDEDMOVEMOD):
            # mech.bth.c:779 - int(...) reproduces the C's float-to-int
            # truncation towards zero, so 100 KPH gives +3, not +4.
            modifier = int(4 + (target_speed - 10 * MP1) / MP4)
        else:
            modifier = 4

    # Immobile bonus (mech.bth.c:785-786)
    if is_target_immobile(target):
        modifier += TARGET_IMMOBILE_BONUS

    # Fallen modifier - mechs and ejected MechWarriors only (mech.bth.c:788-790)
    if target.is_fallen and target.unit_type in (UnitType.MECH, UnitType.MW):
        if distance <= 1.0:
            modifier += TARGET_FALLEN_CLOSE_BONUS
        else:
            modifier += TARGET_FALLEN_FAR_PENALTY

    # Jumping modifier (mech.bth.c:792-793)
    if target.is_jumping:
        modifier += TARGET_JUMPING_PENALTY

    return modifier


def calculate_weapon_bth_modifier(weapon: 'Weapon') -> int:
    """
    Calculate BTH modifier from weapon special properties.
    """
    from entities.weapon import WeaponFlags

    modifier = 0

    if weapon.special & WeaponFlags.PULSE:
        modifier += BTH_PULSE_BONUS

    if weapon.special & WeaponFlags.MRM:
        modifier += BTH_MRM_PENALTY

    if weapon.special & WeaponFlags.HVYW:
        modifier += BTH_HEAVY_WEAPON_PENALTY

    if weapon.special & WeaponFlags.ROCKET:
        modifier += BTH_ROCKET_PENALTY

    return modifier


def calculate_bth(
    attacker: 'Mech',
    target: Optional['Mech'],
    weapon: 'Weapon',
    distance: float,
    gunnery_skill: Optional[int] = None,
    section: Optional[Location] = None,
    unstable_lock_arc: Optional[int] = None,
    w_ammo_mode: int = 0,
    indirect_fire: int = 1000,
    spotter: Optional['Mech'] = None,
    hex_lock_modes: Optional[int] = None,
    w_fire_mode: int = 0,
    critical: Optional[int] = None,
) -> BTHBreakdown:
    """FindNormalBTH with source-ordered, signed pilot diagnostics.

    The C non-debug build reads an uninitialized bthbuf. We always build the
    defined BTH_DEBUG text, retaining the structured breakdown API as well.
    """
    from systems import combat_ranges as ranges
    from systems.piloting import find_pilot_gunnery,find_pilot_spotting
    from systems.missile import check_all_sections,INARC_HAYWIRE_ATTACHED,INARC_HOMING_ATTACHED
    from systems.targeting import resolve_unit
    from entities.weapon import WeaponFlags,WeaponType
    from entities.map import WATER,LIGHT_FOREST,HEAVY_FOREST
    from core.effects import notify_actor
    b = BTHBreakdown(base=find_pilot_gunnery(attacker,weapon) if gunnery_skill is None else gunnery_skill)
    terms = [f'Base {b.base}']
    def add(field,label,value):
        value=int(value)
        setattr(b,field,getattr(b,field)+value)
        if value:terms.append(f'{label}: {value:+d}')
    if indirect_fire<1000:
        spotter=spotter or resolve_unit(attacker,attacker.spotter)
        if spotter is None:
            from systems.movement_commands import notify
            notify(attacker,'Error finding your spotter! (notify a wiz)')
            return BTHBreakdown()
        add('spotting_mod','Spotting',find_pilot_spotting(spotter)-4)
    if target is not None and is_aero(attacker) and not is_aero(target) and not attacker.status&MechStatus.LANDED:
        add('other_mods','Aero strafing',2)
    if target is not None and target.unit_type==UnitType.MW:add('other_mods','MechWarrior',2)
    add('other_mods','MechBTHMod',attacker.base_to_hit)
    if section is not None:add('section_mod','MechLocBTHMod',attacker.sections[section].basetohit)
    if target is not None and attacker.map and attacker.map.rterrain(attacker.x,attacker.y)==WATER and attacker.z<0:
        add('other_mods','InWater',1)
    if distance>ranges.extreme_range(attacker,weapon)+(7 if w_ammo_mode&AmmoMode.STINGER_MODE else 0):
        add('range_mod','OutOfRange',1000)
    elif 0<weapon.range_min and distance<=weapon.range_min:
        minimum=0
        if not ranges.hotloading(weapon,w_fire_mode):minimum=int(weapon.range_min-distance+1)
        elif ranges.config(attacker,'hotloadaddshalfbthmod',0):minimum=int((weapon.range_min-distance+2)/2)
        add('range_mod','MinRange',minimum)
    elif ranges.c3_available(attacker) and getattr(attacker,'c3_network',[]):
        network,b.c3_ref=ranges.find_c3_range(attacker,target,distance)
        b.range_bracket,value=ranges.by_c3_range(attacker,target,section,weapon,distance,network,w_ammo_mode)
        add('range_mod','C3Range',value)
    elif ranges.c3_available(attacker,False) and getattr(attacker,'c3i_network',[]):
        network,b.c3_ref=ranges.find_c3_range(attacker,target,distance,False)
        b.range_bracket,value=ranges.by_c3_range(attacker,target,section,weapon,distance,network,w_ammo_mode)
        add('range_mod','C3iRange',value)
    else:
        b.range_bracket,value=ranges.by_range(attacker,target,section,weapon,distance,w_fire_mode,w_ammo_mode)
        add('range_mod','Range',value)
    tc=attacker.targcomp
    if tc in (TARGCOMP_SHORT,TARGCOMP_LONG):
        long=ranges.rounded(weapon,distance)>(weapon.range_medium_water if ranges.underwater(attacker,section) else weapon.range_medium)
        add('targcomp_mod','TargComp/Long' if long else 'TargComp/Short',-1 if tc==(TARGCOMP_LONG if long else TARGCOMP_SHORT) else 1)
    if target is not None:
        infantry=target.infantry_specials
        stealth,label=({'SHORT':1,'MED':2,'LONG':3},'FWLStealthBonus') if infantry&0x20 else ({'MED':1,'LONG':2},'DCStealthBonus') if infantry&0x10 else ({'MED':1,'LONG':2},'FCStealthBonus') if infantry&0x40 else ({'SHORT':1,'MED':1,'LONG':2},'FCStealthIIBonus') if infantry&0x80 else ({},'')
        add('other_mods',label,stealth.get(b.range_bracket,0))
    doubled=section is not None and attacker.sections[section].config&SectionConfig.STABILIZERS_DESTROYED
    add('attacker_move','AttackMoveX2' if doubled else 'AttackMove',calculate_attacker_movement_modifier(attacker)*(2 if doubled else 1))
    add('heat_mod','Overheat',calculate_overheat_modifier(attacker.heat))
    if w_ammo_mode&AmmoMode.AC_AP_MODE:add('ammo_mode_mod','ArmorPiercing',1)
    if check_all_sections(attacker,INARC_HAYWIRE_ATTACHED):add('pod_mod','HaywirePod',1)
    if target is not None and w_ammo_mode&AmmoMode.NARC_MODE and not weapon.special&WeaponFlags.NARC and check_all_sections(target,INARC_HOMING_ATTACHED):add('pod_mod','iNARC',-1)
    for flag,label,value in [(WeaponFlags.PULSE,'Pulse',-2),(WeaponFlags.MRM,'MRM',1),(WeaponFlags.HVYW,'HeavyWeapon',1)]:
        if weapon.special&flag:add('weapon_mod',label,value)
    if target is not None and w_ammo_mode&AmmoMode.STINGER_MODE:
        if is_flying_type(target) and not target.status&MechStatus.LANDED:add('other_mods','Stinger (Flying)',-3)
        elif target.cocoon:add('other_mods','Stinger (OOD)',-1)
    if weapon.special&WeaponFlags.ROCKET:add('weapon_mod','Rocket Launcher',1)
    if target is not None and target.unit_type==UnitType.VTOL and (target.speed or target.vertical_speed):add('other_mods','TargetVTOL',1)
    if target is not None and tc==TARGCOMP_AA:
        if not target.status&MechStatus.LANDED and (is_flying_type(target) or target.is_jumping or target.cocoon):
            add('targcomp_mod','TargComp/AA-Fly',-3 if attacker.specials&Specials.AA_TECH else -2)
        else:add('targcomp_mod','TargComp/AA-Ground',1)
    if w_ammo_mode&AmmoMode.LBX_MODE:add('ammo_mode_mod','LBX',-3 if target is not None and target.unit_type==UnitType.VTOL else -1)
    if unstable_lock_arc is not None and spotter is None:
        label,value=('HipShot-NoLock',2) if unstable_lock_arc==UNSTABLE_LOCK_HIPSHOT else ('UnstableLock/Fwarc',1) if unstable_lock_arc&(FORWARDARC|TURRETARC) else ('UnstableLock',2)
        add('unstable_lock_mod',label,value)
    if tc==TARGCOMP_MULTI:
        xyz=find_target_xy(attacker)
        if xyz is not None:
            from physics.hexmath import in_weapon_arc
            if not in_weapon_arc(attacker,xyz[0],xyz[1])&FORWARDARC:add('targcomp_mod','TargComp/MultiSideArc',1)
    modes=hex_lock_modes if hex_lock_modes is not None else int(attacker.status&HEX_LOCK_MODES)
    if target is None and modes:add('hex_mod','HexBonus',-4)
    if target is not None and target.cocoon>0:add('other_mods','OODbonus',-2)
    if indirect_fire<1000:add('idf_terrain_mod','IDFTerrain',indirect_fire)
    if attacker.spotter==attacker._id:add('spotting_mod','Spotting',1)
    if target is not None:
        # MechDugIn(target) expands to the firing unit in both source profiles.
        if getattr(attacker,'tank_crit_status',0)&4 and target.z>=attacker.z:
            if not ranges.config(attacker,'dig_only_fs',0) or determine_hit_group(attacker,target)==HitGroup.FRONT:
                add('other_mods','DugIn',ranges.config(attacker,'digbonus',3))
        if target.unit_type in (UnitType.DS,UnitType.SPHEROID_DS):add('other_mods','DSBonus',-3)
        if target.unit_type==UnitType.BSUIT:add('other_mods','Bsuitbonus',1)
        if weapon.weapon_type!=WeaponType.TMISSILE and (attacker.aim==Location.HEAD and target.unit_type in (UnitType.MECH,UnitType.MW) or attacker.aim==AeroLocation.COCKPIT and target.unit_type==UnitType.AERO):
            add('aim_mod','HeadTarget' if is_target_immobile(target) else 'HeadTarget-Fake',7 if is_target_immobile(target) else 25)
        elif w_fire_mode&FireMode.ON_TC and not attacker.has_crit_status(CritStatus.TC_DESTROYED) and not w_ammo_mode&AmmoMode.LBX_MODE:
            aimed=attacker.aim!=NUM_SECTIONS and not is_target_immobile(target)
            add('aim_mod','TC-Target-NotImmobile' if aimed else 'TC',3 if aimed else -1)
        move=calculate_target_movement_modifier(target,distance,attacker)
        if attacker.unit_type==UnitType.AERO:move=int(move*3/4)
        if w_ammo_mode&AmmoMode.AC_PRECISION_MODE:move=max(0,move-2)
        if w_ammo_mode&AmmoMode.SGUIDED_MODE and target.tagged_by>0:
            tagger=resolve_unit(attacker,target.tagged_by)
            if tagger is not None:
                if tagger.team==attacker.team and tagger is not attacker:
                    if move<0:add('target_move','TargetMove (SG Tag -MoveMod)',move)
                else:add('target_move','TargetMove (SG No Tag)',move)
        else:add('target_move','TargetMove',move)
        if indirect_fire>=1000 and attacker.map:
            from systems.los import add_terrain_mod
            terrain=add_terrain_mod(attacker,target,attacker.map,distance,w_ammo_mode)
            if terrain<1000:add('terrain_mod','Terrain/Light(Sensor)',terrain)
        if ranges.config(attacker,'moddamagewithwoods',BTECH_MODDAMAGEWITHWOODS) and attacker.map and target.z-2<=attacker.map.base_elevation(target.x,target.y):
            terrain=attacker.map.rterrain(target.x,target.y)
            if terrain in (LIGHT_FOREST,HEAVY_FOREST):add('terrain_mod','Light Woods bonus' if terrain==LIGHT_FOREST else 'Heavy Woods bonus',-1 if terrain==LIGHT_FOREST else -2)
        from entities.mech import MechStatus2
        if target.status2&MechStatus2.SPRINTING:add('other_mods','SprintingTarget',getattr(target,'btech_sprint_bth',-4))
        if target.status2&MechStatus2.EVADING and not target.is_fallen:add('other_mods','EvadingTarget',1)
    b.critical_bth=0
    if section is not None and critical is not None:
        from systems.enhanced_crits import get_crit_added_bth
        b.critical_bth=get_crit_added_bth(attacker,section,critical,0 if b.range_bracket=='SHORT' else 1)
        add('other_mods','CritDamage',b.critical_bth)
    # Preserve the independently verified Maps weather adapter.
    from physics.environment import gun_modifier
    add('weather_mod','Weather',gun_modifier(attacker.map,weapon.weapon_type))
    b.calculate_total()
    if getattr(attacker,'prefs',0)&512:notify_actor(attacker,attacker.pilot,'BTHDebug: '+', '.join(terms))
    return b


# =============================================================================
# Hit Location Functions
# =============================================================================

def get_hit_arc_half_widths(rule_set=None) -> tuple[int, int, int, int]:
    """
    Half-widths (degrees) of the front and aft hit arcs for the active rule set.

    Reference: mech.hitloc.c:2854-2879 (FindAreaHitGroup rule-set switch)

    The front side center is always 0 degrees and the aft side center always
    180; only the half-width to each side of those centers is configurable.
    Left and right side are whatever is left over.

    Returns:
        (m_fs_hw, m_as_hw, fs_hw, as_hw) - mech front/aft then vehicle
        front/aft half-widths.
    """
    if rule_set is None:
        rule_set = BTECH_HIT_ARCS
    if rule_set == 1:
        # case 1: classic BTMUX rules (mech.hitloc.c:2864-2870)
        return (45, 45, 45, 45)
    if rule_set == 2:
        # case 2: BMR rules (mech.hitloc.c:2872-2878)
        return (90, 30, 90, 30)
    # case 0 and default: TW rules (mech.hitloc.c:2855-2862)
    return (90, 30, 30, 30)


def find_attack_direction(attacker, target) -> int:
    """
    Compute the attack direction in degrees relative to the target's nose.

    Reference: mech.hitloc.c:2881-2884

        ad = AcceptableDegree(FindBearing(MechFX(target), MechFY(target),
                                         MechFX(mech), MechFY(mech))
                              - MechFacing(target));

    Note the direction: the bearing runs from the *target* to the *attacker*,
    so ad == 0 means the attacker is dead ahead of the target and ad == 180
    means it is directly behind. Python's % 360 matches AcceptableDegree
    (mech.utils.c:2226-2240) over the reachable input range.

    The bearing is taken from the *float* cartesian positions, as the C does -
    MechFX/MechFY are sub-hex precise (FindBearing itself takes floats,
    mech.utils.c:395-418). Snapping to hex centers instead would misclassify
    close-range shots by tens of degrees, which is enough to cross an arc
    boundary.
    """
    from physics.hexmath import find_bearing

    bearing = find_bearing(target.fx, target.fy, attacker.fx, attacker.fy)
    return (bearing - target.facing) % 360


def determine_hit_group(
    attacker: 'Mech',
    target: 'Mech',
) -> HitGroup:
    """
    Determine which hit table to use based on attack angle.

    Reference: mech.hitloc.c:2833-2924 FindAreaHitGroup(), CLASS_MECH branch
    at mech.hitloc.c:2888-2899

    The C's arc bounds are inclusive on both ends, so at the default TW widths
    ad of exactly 90 or 270 is still FRONT and ad of exactly 150 or 210 is
    still BACK.

    The C switches on MechType(target) (mech.hitloc.c:2887): only CLASS_MECH
    gets the wide m_fs_hw/m_as_hw pair. Every other class - including CLASS_MW
    and CLASS_BSUIT, which reach the vehicle arm through the `default:`
    FALLTHROUGH at mech.hitloc.c:2901-2911 - uses the narrower fs_hw/as_hw
    pair, 30/30 at the default rules.
    """
    if target.unit_type in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS):
        from physics.hexmath import find_bearing, acceptable_degree
        quadr = acceptable_degree(find_bearing(attacker.fx, attacker.fy, target.fx, target.fy) - target.facing)
        if 135 <= quadr <= 225:
            return HitGroup.FRONT
        if quadr < 45 or quadr > 315:
            return HitGroup.BACK
        return HitGroup.LEFTSIDE if quadr < 135 else HitGroup.RIGHTSIDE

    m_fs_hw, m_as_hw, fs_hw, as_hw = get_hit_arc_half_widths(
        getattr(getattr(target, "_engine", None), "hit_arcs", None))

    # switch (MechType(target)) - mech.hitloc.c:2887-2921
    if target.unit_type == UnitType.MECH:
        fs_hw, as_hw = m_fs_hw, m_as_hw

    ad = find_attack_direction(attacker, target)

    if ad >= (360 - fs_hw) or ad <= (0 + fs_hw):
        return HitGroup.FRONT
    elif ad >= (180 - as_hw) and ad <= (180 + as_hw):
        return HitGroup.BACK
    elif ad >= 180:
        return HitGroup.LEFTSIDE
    else:
        return HitGroup.RIGHTSIDE


def get_hit_location(target, hit_group, roll=None, *, critical=False):
    from systems.hit_locations import find_hit_location
    return find_hit_location(target, hit_group, roll, critical=critical)


def get_punch_location(target, hit_group, roll=None):
    from systems.hit_locations import physical_location
    return physical_location(target, hit_group, 'punch', roll)


def get_kick_location(target, hit_group, roll=None):
    from systems.hit_locations import physical_location
    return physical_location(target, hit_group, 'kick', roll)


# =============================================================================
# Aimed shots / targeting computer hit locations (mech.hitloc.c:2977-3147)
# =============================================================================

# Aimed sections that are masked (unreachable) from one attack side:
# the switch arms of FindAimHitLoc (mech.hitloc.c:3087-3109) and the
# matching arms of FindTCHitLoc (mech.hitloc.c:2991-3005, 3010-3015).
_MECH_AIM_MASKED_SIDE = {
    Location.RARM: HitGroup.LEFTSIDE,
    Location.LARM: HitGroup.RIGHTSIDE,
    Location.RTORSO: HitGroup.LEFTSIDE,
    Location.LTORSO: HitGroup.RIGHTSIDE,
    Location.RLEG: HitGroup.LEFTSIDE,      # legs also masked by PARTIAL_COVER
    Location.LLEG: HitGroup.RIGHTSIDE,
}


def _vehicle_aim_mask(aim: int, hit_group: HitGroup) -> tuple:
    """
    The vehicle aim switch shared by FindTCHitLoc (mech.hitloc.c:3046-3068)
    and FindAimHitLoc (mech.hitloc.c:3117-3141): a side aim is masked when
    the shot comes from the opposite arc; TURRET always connects.

    Returns (aim, connected).
    """
    if aim == VehicleLocation.RSIDE:
        return (aim, hit_group != HitGroup.LEFTSIDE)
    if aim == VehicleLocation.LSIDE:
        return (aim, hit_group != HitGroup.RIGHTSIDE)
    if aim == VehicleLocation.FSIDE:
        return (aim, hit_group != HitGroup.BACK)
    if aim == VehicleLocation.BSIDE:
        return (aim, hit_group != HitGroup.FRONT)
    if aim == VehicleLocation.TURRET:
        return (aim, True)
    return (aim, False)


def _aim_fallback(target: 'Mech', hit_group: HitGroup, is_rear: bool,
                  punch_roll: Optional[int],
                  location_roll: Optional[int]) -> tuple:
    """
    Shared FindTCHitLoc/FindAimHitLoc fallback (mech.hitloc.c:3070-3074,
    3143-3146): a mech under PARTIAL_COVER rolls on the punch table, anyone
    else on the normal table (FindHitLocation — the port's mech table; the
    C's per-class tables for vehicles are a pre-existing port limitation).
    """
    if target.unit_type == UnitType.MECH and \
            target.has_status(MechStatus.PARTIAL_COVER):
        return (get_punch_location(target, hit_group, punch_roll),
                is_rear, False)
    loc, is_crit = get_hit_location(target, hit_group, location_roll)
    return (loc, is_rear, is_crit)


def find_aim_hit_loc(
    attacker: 'Mech',
    target: 'Mech',
    punch_roll: Optional[int] = None,
    location_roll: Optional[int] = None,
) -> tuple:
    """
    Hit location for a successful aimed shot (immobile target, 6/7/8 roll).

    Port of FindAimHitLoc (mech.hitloc.c:3077-3147).  Returns
    (location, is_rear, is_critical); BACK hit group sets is_rear
    (mech.hitloc.c:3083-3084).

    Masking per the C's switch (mech.hitloc.c:3086-3113): the aim connects
    unless the shot comes from the side that hides the section; legs are
    additionally masked by PARTIAL_COVER (:3094-3101); CTORSO and HEAD
    ALWAYS connect (:3108-3111).  An aero target returns the aim
    UNCONDITIONALLY (:3114-3115).  A masked aim falls through to the
    partial-cover punch table for covered mechs, else the normal table
    (:3143-3146).
    """
    hit_group = determine_hit_group(attacker, target)
    is_rear = (hit_group == HitGroup.BACK)
    aim = attacker.aim

    if target.unit_type in (UnitType.MECH, UnitType.MW):
        if aim in (Location.CTORSO, Location.HEAD):
            # mech.hitloc.c:3108-3111 — no side condition at all
            return (Location(aim), is_rear, False)
        masked_side = _MECH_AIM_MASKED_SIDE.get(aim)
        if masked_side is not None and hit_group != masked_side:
            if aim in (Location.RLEG, Location.LLEG) and \
                    target.has_status(MechStatus.PARTIAL_COVER):
                pass    # legs hidden by partial cover (:3094-3101)
            else:
                return (Location(aim), is_rear, False)
    elif target.unit_type in (UnitType.AERO, UnitType.DS,
                              UnitType.SPHEROID_DS):
        # is_aero(target): `return MechAim(mech);` — no masking, no
        # fallback (mech.hitloc.c:3114-3115)
        return (aim, is_rear, False)
    else:
        loc, connected = _vehicle_aim_mask(aim, hit_group)
        if connected:
            return (loc, is_rear, False)

    return _aim_fallback(target, hit_group, is_rear, punch_roll,
                         location_roll)


def find_tc_hit_loc(
    attacker: 'Mech',
    target: 'Mech',
    success_roll: Optional[int] = None,
    punch_roll: Optional[int] = None,
    location_roll: Optional[int] = None,
) -> tuple:
    """
    Hit location for a targeting-computer shot.

    Port of FindTCHitLoc (mech.hitloc.c:2977-3075).  Returns
    (location, is_rear, is_critical).

    Gate (mech.hitloc.c:2986): the stored aim_type must equal the target's
    type AND a fresh d6 must come up >= 3; the d6 is only rolled when the
    types match (C short-circuit).  Mech masking mirrors FindAimHitLoc
    except: CTORSO always connects — its side condition is commented out
    in the C (:3016-3019) — and HEAD connects only against an Immobile
    target (:3020-3022).

    C QUIRK ported verbatim: the CLASS_AERO/CLASS_DS case has NO `break`
    before CLASS_VEH_GROUND (mech.hitloc.c:3024-3043), so an aero aim that
    fails its own switch falls THROUGH into the vehicle switch, where the
    AeroLocation value is compared against RSIDE/LSIDE/FSIDE/BSIDE/TURRET
    (e.g. a masked AERO_LWING aim, value 1, resurrects as RSIDE, value 1).

    Args:
        success_roll: optional pre-rolled d6 for the >= 3 gate.
    """
    hit_group = determine_hit_group(attacker, target)
    is_rear = (hit_group == HitGroup.BACK)
    aim = attacker.aim

    tc_success = False
    if attacker.aim_type == target.unit_type:
        r = success_roll if success_roll is not None else draw("tc_location", 1, 6, roll_1d6)
        tc_success = (r >= 3)

    if tc_success:
        if target.unit_type in (UnitType.MECH, UnitType.MW):
            if aim == Location.CTORSO:
                # `/* if (hitGroup != LEFTSIDE && hitGroup != RIGHTSIDE) */`
                # (mech.hitloc.c:3016-3019) — the condition is commented
                # out in the C, so CTORSO always connects.
                return (Location.CTORSO, is_rear, False)
            if aim == Location.HEAD:
                if is_target_immobile(target):     # mech.hitloc.c:3020-3022
                    return (Location.HEAD, is_rear, False)
            else:
                masked_side = _MECH_AIM_MASKED_SIDE.get(aim)
                if masked_side is not None and hit_group != masked_side:
                    if aim in (Location.RLEG, Location.LLEG) and \
                            target.has_status(MechStatus.PARTIAL_COVER):
                        pass    # mech.hitloc.c:2996-3005
                    else:
                        return (Location(aim), is_rear, False)
        else:
            fell_through = False
            if target.unit_type in (UnitType.AERO, UnitType.DS):
                if aim == AeroLocation.NOSE and hit_group != HitGroup.BACK:
                    return (aim, is_rear, False)
                if aim == AeroLocation.LWING and \
                        hit_group != HitGroup.RIGHTSIDE:
                    return (aim, is_rear, False)
                if aim == AeroLocation.RWING and \
                        hit_group != HitGroup.LEFTSIDE:
                    return (aim, is_rear, False)
                if aim == 3 and hit_group != HitGroup.FRONT:
                    return (aim, is_rear, False)
                if aim == AeroLocation.COCKPIT and hit_group != HitGroup.BACK:
                    return (aim, is_rear, False)
                if aim == AeroLocation.ENGINE and hit_group != HitGroup.FRONT:
                    return (aim, is_rear, False)
                # Missing-break fall-through into the vehicle switch
                # (mech.hitloc.c:3043 — no break; see docstring).
                fell_through = True
            if fell_through or target.unit_type in (
                    UnitType.VEH_GROUND, UnitType.VEH_NAVAL, UnitType.VTOL):
                loc, connected = _vehicle_aim_mask(aim, hit_group)
                if connected:
                    return (loc, is_rear, False)

    return _aim_fallback(target, hit_group, is_rear, punch_roll,
                         location_roll)


# =============================================================================
# Damage Application
# =============================================================================

# mudconf.btech_newstagger (src/conf.c:129, default 1) — stagger damage is
# recorded per-hit on a timestamped list; the legacy path accumulates
# MechTurnDamage instead (mech.damage.c:604-640).
BTECH_NEWSTAGGER = 1


def cause_armor_damage(target, location, damage, is_rear=False, attacker=None,
                       is_critical=False, weapon=None, w_ammo_mode=0, engine=None, *, los=1):
    """cause_armordamage: armor, criticals and fighter depletion, in source order."""
    from systems.damage import armor_warning, destroy_section, destroy_mech, _notify
    from entities.mech import Specials, UnitType as U
    from physics.flooding import flood_location
    if target.unit_type == U.MW:
        return 0, max(0, damage), 0, []
    section = target.sections[location]
    if target.specials & Specials.HARDA_TECH and damage > 0:
        damage = (damage + 1) // 2
    rear_armor = target.unit_type == U.MECH and is_rear and location in (2, 3, 4)
    field, original = ('rear', section.rear_orig) if rear_armor else ('armor', section.armor_orig)
    before = getattr(section, field)
    excess = damage - before
    setattr(section, field, max(0, before - damage))
    applied = before - getattr(section, field)
    after = getattr(section, field)
    if not rear_armor and not section.armor:
        flood_location(target, location, target.z)
    count, results = 0, []
    if is_critical:
        r = record_critical_roll(source_roll('critical_rolls', roll_2d6), target)
        count = 1 if r in (8, 9) else 2 if r in (10, 11) else 3 if r == 12 else 0
    elif weapon is not None:
        from systems.damage import check_ap_critical
        count = check_ap_critical(target, location, weapon, w_ammo_mode, False, excess, is_rear)
    if count:
        results = check_for_critical(target, location, count, attacker, engine=engine, los=los)[1]
    if target.unit_type == U.AERO and excess >= 0:
        destroy_section(target, attacker, location, engine=engine, los=los)
        if target.is_destroyed:
            return applied, 0, count, results
        if location == AeroLocation.COCKPIT:
            destroy_mech(target, attacker, True, engine=engine)
            return applied, 0, count, results
        if location == AeroLocation.ENGINE:
            from systems.vehicle_combat import make_vehicle_fall, set_max_speed
            from physics.orbital import fall_event
            from core.events import EventType
            make_vehicle_fall(target)
            target.speed = 0
            set_max_speed(target, 0)
            target.vertical_speed = 0
            _notify(target, 'The computer reports engine destroyed!' if target.has_status(MechStatus.LANDED) else 'You feel the thrust die..')
            if not target.has_status(MechStatus.LANDED) and target._engine:
                target._engine.events.schedule(3, EventType.FALL, fall_event, target, -1)
    armor_warning(target, location, before, after, original, is_rear, penetrated=excess > 0)
    return applied, max(0, excess), count, results


def apply_damage_to_location(target, location, damage, is_rear=False, attacker=None,
                             is_critical=False, weapon=None, w_ammo_mode=0, engine=None,
                             *, los=1):
    """Single-location adapter; the full damage entry owns injury and transfer."""
    from systems.damage import cause_internal_damage
    armor, overflow, count, results = cause_armor_damage(
        target, location, damage, is_rear, attacker, is_critical, weapon, w_ammo_mode, engine, los=los)
    structure = 0
    if overflow > 0 and not is_aero(target):
        before = target.sections[location].internal
        overflow, internal_results = cause_internal_damage(target, attacker, location, overflow,
            bool(count), engine=engine, los=los)
        results += internal_results
        structure = before - target.sections[location].internal
    return armor, structure, overflow, results


def apply_damage_with_transfer(target, location, damage, is_rear=False,
                               attacker=None, is_critical=False, weapon=None,
                               w_ammo_mode=0, engine=None, *, ignore_swarmers=False,
                               internal=False, transfer=False, _transferred=False, _on_hit=None,
                               bth=0, physical=0, attack_pilot=None, _entry_processed=False, los=None,
                               internal_damage=None, cause=None):
    """DamageMech's two signed channels; legacy internal/transfer flags adapt at entry."""
    from entities.mech import UnitType as U, Specials, MechStatus2, SectionConfig
    from systems.damage import cause_internal_damage, destroy_mech, _notify, section_destroyed
    from systems.hit_locations import transfer_target, find_hit_location
    from systems.notifications import mech_printf, MECHALL, pair_los_broadcast
    from systems.sensors import los_broadcast
    from systems.parts import armor_string
    engine = engine or target._engine
    source = attacker or target
    los = 0 if los is None else los
    aero = is_aero(target)
    # Explicit channels preserve mixed inputs and -1/-2 sentinels. The adapter's
    # internal mode alone does not enable transfer for non-mechs.
    if internal_damage is None:
        if internal:
            internal_damage, damage = damage, (-2 if _transferred else -1 if transfer else 0)
        else:
            internal_damage = -2 if _transferred else -1 if transfer else 0
    cause = (weapon.index if weapon is not None else -1) if cause is None else cause
    from entities.weapon import get_weapon_by_index
    cause_weapon = get_weapon_by_index(cause) if cause >= 0 else None
    entry_roll = source_roll('damage_entry', roll_2d6)
    if (target.status & MechStatus.COMBAT_SAFE or
            source.map and getattr(source.map, 'buildflag', 0) & 2):
        if source is not target: _notify(source, 'Your efforts only scratch the paint!')
        return 0
    if not aero and source.status2 & MechStatus2.WEAPONS_HOLD and source is not target:
        _notify(source, 'You are currently in weapons hold!')
    if not ignore_swarmers:
        from systems.swarm import swarmers
        suits = swarmers(target)
        if suits and suits[0] is not source:
            suit = suits[0]
            eligible = location in ((2, 3, 4) if is_rear else (2, 3))
            chance = 20 * sum(sec.internal != 0 for sec in suit.sections) if eligible else 0
            if chance >= entry_roll and target.sections[location].armor:
                if attacker is not None and source is not target:
                    _notify(source, 'The battlesuits crawling all over your target absorb the damage!')
                _notify(target, 'The battlesuits crawling all over you absorb the damage!')
                _notify(suit, 'You absorb the damage!')
                loc, _ = find_hit_location(suit, HitGroup.FRONT)
                return apply_damage_with_transfer(suit, loc, damage, attacker=attacker,
                    engine=engine, internal_damage=0, _on_hit=_on_hit, cause=cause,
                    weapon=weapon, w_ammo_mode=w_ammo_mode, bth=bth, physical=physical,
                    attack_pilot=attack_pilot, los=los, ignore_swarmers=ignore_swarmers)
    if damage > 0 or internal_damage > 0:
        from systems.movement_commands import damage_interrupt, pending
        damage_interrupt(target)
        if target.has_crit_status(CritStatus.HIDDEN):
            target.clear_crit_status(CritStatus.HIDDEN)
            los_broadcast(target, "loses it's cover as it takes damage!" if aero else 'loses its cover as it takes damage!')
            _notify(target, 'Your cover is ruined you take damage!' if aero else 'Your cover is ruined as you take damage!')
        if engine is not None and pending(target, '_mode_event'):
            from core.events import EventType
            events = engine.events.pending_events(EventType.MOVEMODE, target)
            encoded = events[0].data2
            if isinstance(encoded, tuple):
                flag, entering = encoded[:2]
                # Preserve the independently verified queued-sprint entry exception.
                cancel = entering and not flag & (MechStatus2.SPRINTING | MechStatus2.EVADING | MechStatus2.DODGING)
            else:
                cancel = not int(encoded) & (1 | 4 | 16 | 8)  # OFF, SPRINT, EVADE, DODGE
            if cancel:
                engine.cancel_events_of_type(EventType.MOVEMODE, target)
                target._mode_event = None
                _notify(target, 'Your movement mode changes are cancelled as you take damage!')
    if damage > 0 and internal_damage == 0:
        if target.unit_type == U.VTOL and location == 5:
            divisor = getattr(engine, 'divrotordamage', 0)
            damage = max(1, int(damage / divisor)) if divisor > 0 else max(1, damage)
        if attacker is not None:
            from systems.characters import attached
            from systems.piloting import valid_pilot
            actor = attack_pilot if attack_pilot is not None else valid_pilot(attacker, True)
            if isinstance(actor, int) and actor >= 0:
                actor = getattr(getattr(engine, 'personnel', None), 'objects', {}).get(actor)
            if attached(actor):
                from systems import experience
                if physical == 0 and cause_weapon is not None:
                    experience.gun(actor, attacker, target, damage, 1, cause_weapon, bth)
                elif physical == 1 and not target.is_destroyed and target.in_character and target.team != attacker.team and (target.unit_type != U.MW or attacker.unit_type == U.MW):
                    experience.piloting(actor, attacker, damage // 3, True)
        if target.unit_type == U.MW:
            from systems.personal_damage import damage_to_personal
            damage = damage_to_personal(target, cause_weapon, damage)
    snap_tow, blow_dump = False, False
    if is_rear:
        if not target.specials & Specials.SALVAGE_TECH:
            snap_tow = source_roll('tow_rolls', roll_2d6) <= 5 and location in (2, 3, 4)
        if target.unit_type == U.MECH:
            from systems.ammo_dump import sync_dump_state
            sync_dump_state(target)
            blow_dump = bool(target.dumping and location in (2, 3, 4) and cause >= 0)
        else:
            if location == 2: location = 3
            is_rear = False
    may_transfer = bool(transfer or target.unit_type in (U.MECH, U.MW))
    was_transfer = _transferred
    if damage < 0:
        was_transfer |= damage == -2
        may_transfer |= damage in (-1, -2)
        damage = 0
    elif internal_damage < 0:
        was_transfer |= internal_damage == -2
        may_transfer |= internal_damage in (-1, -2)
        internal_damage = 0

    def recurse(loc, armor, internals):
        return apply_damage_with_transfer(target, loc, armor, is_rear, attacker,
            is_critical, weapon, w_ammo_mode, engine, ignore_swarmers=ignore_swarmers,
            internal_damage=internals, cause=cause, _on_hit=_on_hit, bth=bth,
            physical=physical, attack_pilot=attack_pilot, los=los)

    kill = 0
    route_class = target.unit_type in (U.MECH, U.MW, U.BSUIT) or aero
    while not kill and (target.sections[location].armor == 0 if aero else target.sections[location].internal == 0):
        if may_transfer:
            location = transfer_target(target, location)
            if location >= 0 and route_class:
                # C normalized the old sentinel already; this hop drops any
                # original internal payload and marks its external amount -2.
                return recurse(location, damage, -2)
        if route_class:
            location = transfer_target(target, location)
            if location >= 0:
                continue
        if not aero or target.is_destroyed:
            return 0
        location = -1
        if target.unit_type != U.AERO and target.si > damage:
            target.si -= damage
            kill = -1
        else:
            kill = 1
    amount = damage + max(0, internal_damage)
    if target.cocoon > 0 and source_roll('interception_rolls', roll_2d6) > 8:
        from physics.orbital import cocoon_damage
        cocoon_damage(target, source, amount)
        return 0
    notification = (f'for {amount} points of damage in the structure.' if location == -1 else
                    f'for {amount} points of damage in the {armor_string(target, location)} ' + ('(Rear)' if is_rear else ''))[:79]
    if not was_transfer:
        target.damage_taken += amount
        if source is not target: source.damage_inflicted += amount
    if los:
        mech_printf(source, MECHALL, '%%cg%s%s%%c', 'Damage transfer.. ' if was_transfer else 'You hit ', notification)
    if target.unit_type == U.MW and not was_transfer and damage > 0:
        from systems.personal_damage import personal_armor_effect
        damage = personal_armor_effect(target, cause_weapon, location, damage, internal_damage)
        if damage == 0: return 0
    mech_printf(target, MECHALL, '%%ch%%cyYou have been hit %s%s%%c', notification, '(transfer)' if was_transfer else '')
    if damage > 0 and internal_damage <= 0 and not was_transfer:
        from systems.stagger import record_damage
        record_damage(target, damage, engine, source)
    if (target.unit_type == U.MECH and location == Location.HEAD or
            target.unit_type == U.AERO and location == AeroLocation.COCKPIT):
        from systems.piloting import head_hit_mw_damage
        head_hit_mw_damage(target, attacker, 1)
    if kill:
        if kill == 1:
            _notify(target, "The blast causes last of your craft's structural integrity disappear, blowing")
            _notify(target, "it's pieces all over the sky!")
            airborne_started = not target.has_status(MechStatus.LANDED) and target.is_started
            if airborne_started:
                _notify(source, 'You shoot the craft from the sky!')
                pair_los_broadcast(source, target, 'shoots %s from the sky!')
            destroy_mech(target, attacker, not airborne_started, engine=engine)
        return damage if kill == -1 else 0
    section = target.sections[location]
    armor = structure = total = 0
    results = []
    from systems.damage import possibly_breach, breach_location
    if damage > 0:
        eligible_light = ((target.unit_type == U.MECH and location in (2, 3, 4)) or
                          (target.unit_type == U.VEH_GROUND and location == 2))
        if eligible_light and not is_rear and target.specials & Specials.SLITE_TECH and not target.has_crit_status(CritStatus.SLITE_DEST):
            if source_roll('searchlight_rolls', roll_2d6) > 6 and (target.status2 & MechStatus2.SLITE_ON or source_roll('searchlight_rolls', roll_2d6) > 5):
                target.set_crit_status(CritStatus.SLITE_DEST)
                target.status2 &= ~int(MechStatus2.SLITE_ON)
                los_broadcast(target, "'s searchlight is blown apart!")
                _notify(target, '%ch%cyYour searchlight is destroyed!%cn')
        armor, excess, count, results = cause_armor_damage(target, location, damage, is_rear,
            attacker, is_critical, weapon, w_ammo_mode, engine, los=los)
        internal_damage += excess
        from systems.damage import record_stat_hit
        record_stat_hit(source, target, location, damage, internal_damage, weapon, bth, is_rear)
        if internal_damage >= 0:
            from physics.flooding import flood_location
            flood_location(target, location, target.z)
        if internal_damage > 0 and not aero:
            before = section.internal
            internal_damage, extra = cause_internal_damage(target, attacker, location, internal_damage,
                bool(count), engine=engine, los=los)
            results += extra
            structure = before - section.internal
            if not internal_damage and not section_destroyed(target, location):
                breach_location(target, attacker, location)
        else:
            possibly_breach(target, attacker, location)
        total = armor + structure
        if _on_hit is not None: _on_hit(target, location, armor, structure, results)
        if internal_damage > 0 and may_transfer and target.unit_type != U.BSUIT:
            location = transfer_target(target, location)
            if location < 0:
                destroy_mech(target, attacker, True, engine=engine)
                return total
            total += recurse(location, internal_damage, -2)
    elif internal_damage > 0:
        if aero:
            armor, internal_damage, count, results = cause_armor_damage(target, location, internal_damage,
                is_rear, attacker, is_critical, weapon, w_ammo_mode, engine, los=los)
        else:
            before = section.internal
            internal_damage, results = cause_internal_damage(target, attacker, location, internal_damage, engine=engine, los=los)
            structure = before - section.internal
        total = armor + structure
        if _on_hit is not None: _on_hit(target, location, armor, structure, results)
        if not section_destroyed(target, location):
            possibly_breach(target, attacker, location)
        contained = section.config & SectionConfig.CASE_TECH or target.specials & Specials.CLAN_TECH
        if internal_damage > 0 and may_transfer and not contained:
            location = transfer_target(target, location)
            if location < 0:
                destroy_mech(target, attacker, True, engine=engine)
                return total
            total += recurse(location, internal_damage, -2) if aero else recurse(location, -2, internal_damage)
    if snap_tow and target.carrying > 0:
        from systems.targeting import resolve_unit
        tow_target = resolve_unit(target, target.carrying)
        if tow_target is not None:
            _notify(target, 'The hit causes your tow line to let go!')
            _notify(tow_target, 'Your tow lines go suddenly slack!')
            los_broadcast(target, "'s tow lines release and flap freely behind it!")
            from systems.damage import release_tow
            release_tow(target)
    if weapon and weapon.index > 0 and 'IS.PlasmaRifle' in weapon.name and target.unit_type == U.MECH:
        target.weap_heat += draw('plasma_heat', 1, 6, lambda: random.randint(1, 6))
    if blow_dump:
        from systems.ammo_dump import blow_dumping_ammo
        blow_dumping_ammo(target, attacker, location)
    return total


# =============================================================================
# Critical Hit Resolution
# =============================================================================

def check_for_critical(
    target: 'Mech',
    location: Location,
    num_crits: int = 1,
    attacker: Optional['Mech'] = None,
    engine=None,
    *, los=1,
) -> tuple[int, list]:
    """
    Roll for and apply critical hits with full effects.

    Reference: crit.c HandleCritical()

    Args:
        target: The target mech
        location: Location to check for criticals
        num_crits: Number of critical slots to potentially damage
        attacker: Who caused the damage (optional)

    Returns:
        Tuple of (number of criticals applied, list of CriticalResult)
    """
    from systems.criticals import check_and_apply_criticals

    # Use the new criticals system
    results = check_and_apply_criticals(target, location, num_crits, attacker,
                                        engine=engine, los=los)

    return (len(results), results)


def roll_critical_hits(through_armor: bool = False) -> int:
    """
    Roll 2d6 to determine number of critical hits.

    Reference: crit.c

    Args:
        through_armor: Whether damage went through armor (affects roll)

    Returns:
        Number of critical slots to check (0, 1, 2, or 3)
    """
    roll = roll_2d6()

    if through_armor:
        # Critical through armor
        if roll <= 7:
            return 0
        elif roll <= 9:
            return 1
        elif roll <= 11:
            return 2
        else:
            return 3
    else:
        # Normal critical (2d6 roll of 2)
        if roll <= 8:
            return 1
        elif roll <= 10:
            return 2
        else:
            return 3


# =============================================================================
# Hex hitting (mech.combat.c:1810-2012)
# =============================================================================

def short_hextarget(mech):
    for bit,label in ((MechStatus.LOCK_HEX_IGN,'ign'),(MechStatus.LOCK_HEX_CLR,'clr'),
                      (MechStatus.LOCK_HEX,'hex'),(MechStatus.LOCK_BUILDING,'bld')):
        if mech.status&bit:return label
    return 'reg'


def hex_target_id(mech) -> str:
    """
    Flavor phrase for the firing message of a hex shot, keyed off the
    firer's lock mode.  Port of hex_target_id (mech.combat.c:1814-1826).
    """
    if mech.has_status(MechStatus.LOCK_HEX_IGN):
        return "at the hex, trying to ignite it"
    if mech.has_status(MechStatus.LOCK_HEX_CLR):
        return "at the hex, trying to clear it"
    if mech.has_status(MechStatus.LOCK_HEX):
        return "at the hex"
    if mech.has_status(MechStatus.LOCK_BUILDING):
        return "at the building at"
    return "at"


def hit_building(mech, x: int, y: int, weapon_idx: int, damage: int) -> None:
    """Apply damage to a registered local building, retaining missing-object evidence."""
    from entities.map_objects import find_object,resolve_map
    board=mech.map
    obj=find_object(board,x,y,4) if board is not None and board.valid(x,y) else None
    if obj is not None and resolve_map(board,obj.obj) is not None:
        from systems.buildings import hit_building as resolve
        return resolve(mech,x,y,weapon_idx,damage)
    from systems.damage import external_effect
    external_effect(mech,'hit_building / persistent building objects',f'building damage {damage} at {x},{y}')


def possibly_ignite_or_clear(mech, weapon_idx: int, ammo_mode: int,
                             damage: int, x: int, y: int,
                             intentional: int) -> None:
    from systems.terrain_combat import possibly_ignite_or_clear as resolve
    return resolve(mech, weapon_idx, ammo_mode, damage, x, y, intentional)


def possibly_blow_ice(mech, weapon_idx: int, x: int, y: int) -> None:
    from entities.map import ICE
    from entities.weapon import get_weapon_by_index
    from physics.ice import blast_surface
    if mech.map is not None and mech.map.rterrain(x, y) == ICE:
        weapon = get_weapon_by_index(weapon_idx)
        if weapon is None:
            raise ValueError('Unknown weapon index')
        blast_surface(mech.map, x, y, weapon.damage)


def possibly_blow_bridge(mech, weapon_idx: int, x: int, y: int) -> None:
    from entities.map import BRIDGE
    from entities.weapon import get_weapon_by_index
    from physics.ice import blast_surface
    if mech.map is not None and mech.map.rterrain(x, y) == BRIDGE:
        weapon = get_weapon_by_index(weapon_idx)
        if weapon is None:
            raise ValueError('Unknown weapon index')
        blast_surface(mech.map, x, y, weapon.damage)


def hex_hit(mech, x: int, y: int, weapon_idx: int, ammo_mode: int,
            damage: int, ishit: int) -> None:
    """
    Dispatch a weapon impact on hex (x, y).  Port of hex_hit
    (mech.combat.c:1992-2012) — PURE dispatch: it does nothing unless the
    firer holds one of the four explicit hex-lock-mode bits, so a plain
    LOCK_TARGET coordinate shot that found no one is a no-op
    (mech.combat.c:1995-1997).
    """
    if not mech.has_status(HEX_LOCK_MODES):
        return

    # Ok.. we either try to clear/ignite the hex, or alternatively we try
    # to hit building in it (mech.combat.c:1999-2010)
    if mech.has_status(MechStatus.LOCK_BUILDING):
        if ishit > 0:
            hit_building(mech, x, y, weapon_idx, damage)
    else:
        possibly_ignite_or_clear(mech, weapon_idx, ammo_mode, damage, x, y, 1)

        if mech.has_status(MechStatus.LOCK_HEX):
            possibly_blow_ice(mech, weapon_idx, x, y)
            possibly_blow_bridge(mech, weapon_idx, x, y)


# =============================================================================
# Attack Resolution
# =============================================================================

def attack_draw(weapon,distance):
    """FireWeapon's three-die DFM/short-ELRM roll and normal Roll."""
    from core.randomness import draw
    from entities.weapon import WeaponFlags
    if weapon.special&WeaponFlags.DFM or weapon.special&WeaponFlags.ELRM and distance<weapon.range_min:
        r1,r2,r3=(draw('attack_dice',1,6,roll_1d6) for _ in range(3))
        if r1>r2:r1,r2=r2,r1
        if r2>r3:r2,r3=r3,r2
        return r1+r2
    return source_roll('attack_rolls', roll_2d6)


def resolve_attack(
    attacker: 'Mech',
    target: Optional['Mech'],
    weapon: 'Weapon',
    distance: float,
    gunnery_skill: Optional[int] = None,
    to_hit_roll: Optional[int] = None,
    location_roll: Optional[int] = None,
    section: Optional[Location] = None,
    unstable_lock_arc: Optional[int] = None,
    w_ammo_mode: int = 0,
    mapx: int = -1,
    mapy: int = -1,
    ishex: int = 0,
    hex_lock_modes: Optional[int] = None,
    indirect_fire: int = 1000,
    spotter: Optional['Mech'] = None,
    weapon_idx: int = -1,
    w_fire_mode: int = 0,
    w_section: Optional[int] = None,
    w_critical: Optional[int] = None,
    engine=None,
    aim_roll: Optional[int] = None,
    tc_roll: Optional[int] = None,
    cluster_roll: Optional[int] = None,
    ams_roll: Optional[int] = None,
    location_rolls: Optional[list] = None,
    swarm_attack: int = 0,
    shot_checks=None,
    post_streak_checks=None,
    gattling_shots: int = 0,
    sight: bool = False,
    los: Optional[int] = None,
) -> AttackResult:
    """
    Resolve a weapon attack.

    Args:
        attacker: The attacking mech
        target: The target mech, or None for a hex impact — hits dispatch
            through hex_hit and misses still fire the ignite/clear
            machinery (mech.combat.c:1800-1802, 1339-1351)
        weapon: The weapon being fired
        distance: Distance to target in hexes
        gunnery_skill: Attacker's gunnery skill
        to_hit_roll: Optional pre-rolled attack roll
        location_roll: Optional pre-rolled location roll
        section: Section the firing weapon is mounted in, for the per-section
            basetohit term (mech.bth.c:101); None skips it
        unstable_lock_arc: Passed through to calculate_bth (mech.bth.c:269-281)
        w_ammo_mode: Passed through to calculate_bth / AddTerrainMod
        mapx, mapy: Impact hex for a hex shot (the C's mapx/mapy locals)
        ishex: The C's ishex parameter — 1 for a hex-lock shot, 2 for
            spotted indirect fire; gates the impossible-roll check
            (mech.combat.c:961-966)
        hex_lock_modes: Firer's hex-lock bits frozen at fire time, threaded
            to calculate_bth's "HexBonus" term (mech.bth.c:292-295)
        indirect_fire: The C's indirectFire (< 1000 = spotted shot, carries
            the spotter-side terrain sum) — see calculate_bth
        spotter: The spotting unit for an indirect shot
        weapon_idx: Weapon catalog index, forwarded to hex_hit /
            possibly_ignite_or_clear (the C's weapindx)
        w_fire_mode: Firing crit slot's fire mode word (ON_TC / burst modes)
        w_section, w_critical: Firing crit coordinates, needed by
            MissileHitIndex (mech.combat.missile.c:119-189); None falls
            back to a bare 2d6-2 cluster row
        engine: GameEngine, needed only by the inferno burn scheduler
        aim_roll: pre-rolled 2d6 for the aimed-shot 6/7/8 gate
            (mech.combat.c:1585-1591)
        tc_roll: pre-rolled d6 for FindTCHitLoc's >= 3 gate
        cluster_roll: pre-rolled 2d6 for the cluster table
        ams_roll: pre-rolled AMS shot-down count (1d6 IS / 2d6 Clan)
        location_rolls: pre-rolled 2d6 location rolls for multi-hit groups
        swarm_attack: 1 when the firer swarms the target — the C's
            tIsSwarmAttack, which forces the BTH to 0 (mech.combat.c:871-873)

    Returns:
        AttackResult with all details
    """
    from entities.weapon import WeaponFlags, WeaponType, get_missiles_hit

    if los is None:
        from systems.los import in_line_of_sight_nb
        los = in_line_of_sight_nb(attacker, target,
                                   target.x if target is not None else mapx,
                                   target.y if target is not None else mapy,
                                   distance) if attacker.map else 1
    result = AttackResult(target_id=target._id if target is not None else None, los=los,
                          hex_target_label=short_hextarget(attacker) if ishex or target is None else None,
                          observer_modifier=indirect_fire if indirect_fire < 1000 else None)

    if weapon_idx is None or weapon_idx<0:weapon_idx=weapon.index
    # Calculate BTH
    is_artillery = weapon.weapon_type == WeaponType.TARTILLERY
    if is_artillery:
        from systems.artillery import artillery_bth
        from systems.los import in_line_of_sight_nb
        indirect = indirect_fire < 1000 or not los
        total = artillery_bth(attacker,section,weapon,distance,indirect)
        bth = BTHBreakdown(base=total,total=total)
    else:
        bth = calculate_bth(attacker, target, weapon, distance, gunnery_skill,
                        section, unstable_lock_arc=unstable_lock_arc,
                        w_ammo_mode=w_ammo_mode, indirect_fire=indirect_fire,
                        spotter=spotter, hex_lock_modes=hex_lock_modes,
                        w_fire_mode=w_fire_mode,critical=w_critical)
    result.critical_bth = getattr(bth,'critical_bth',0)
    result.bth = bth.total
    result.bth_breakdown = bth

    # A swarm attack always connects: tIsSwarmAttack forces the BTH to 0
    # (mech.combat.c:871-873).
    if swarm_attack:
        result.bth = 0

    result.roll = to_hit_roll if to_hit_roll is not None else attack_draw(weapon,distance)
    result.margin = result.roll - result.bth
    label=target.name if target is not None and not ishex else f'({mapx},{mapy})'
    unit_shot=target is not None and not ishex
    out_of_range=result.bth>=900 if unit_shot else result.bth>900
    impossible=result.bth>12 and (unit_shot or not is_artillery)
    if sight and not out_of_range or not sight and not impossible:
        from systems.combat_ranges import send_c3_track_emit
        send_c3_track_emit(attacker,bth.c3_ref)
    from systems.combat_firing import firing_feedback
    feedback=firing_feedback(attacker,target,weapon,result,sight,ishex,mapx,mapy,is_artillery,los=los)
    if sight:
        result.shot_aborted = out_of_range
        result.messages.append(feedback)
        return result
    if impossible:
        result.roll_impossible=True
        result.messages.append(f'Fire {weapon.name[3:]} at {label} - BTH: {result.bth}  Roll: Impossible!')
        return result
    if target is None:
        result.messages.append(f'You fire {weapon.name[3:]} {hex_target_id(attacker)} ({mapx},{mapy})!')

    from systems.combat_firing import record_attack_channels
    record_attack_channels(attacker,target,result,mapx,mapy,ishex)
    if shot_checks is not None:
        shot_checks(result)
        if result.shot_aborted:return result
    # Brand failures precede Streak's conditional homing check.
    if weapon.special & WeaponFlags.STREAK:
        from systems.ecm import angel_ecm_disturbed,angel_ecm_protected
        confused=target is not None and (angel_ecm_disturbed(attacker) or angel_ecm_protected(target))
        if confused:
            from systems.movement_commands import notify
            text='The ECM confuses your streak homing system!'
            notify(attacker,text);result.messages.append(text)
        elif result.margin < 0:
            result.streak_lock_failed=True
            return result

    if post_streak_checks is not None:
        post_streak_checks(result)
        if result.shot_aborted:
            return result
    from systems.combat_firing import begin_shot
    begin_shot(attacker)
    from systems.combat_firing import announce_shot
    from systems.combat_ranges import config,extreme_range
    broadcast_bth=result.bth-(config(attacker,'glancing_blows',1)==2)
    range_ok=result.range_ok
    announce_shot(attacker,target,weapon,mapx,mapy,result.roll>=broadcast_bth and range_ok,is_artillery,ishex)
    attacker.status|=MechStatus.FIRED
    if not ishex:attacker.shots_fired+=1
    if is_artillery:
        from systems.artillery import artillery_shoot
        result.hit = result.roll >= result.bth
        artillery_shoot(engine or attacker._engine,attacker,mapx,mapy,
                         weapon.index,w_ammo_mode,result.hit)
        return result
    from systems.combat_ranges import config,extreme_range
    from systems.combat_impacts import determine_damage
    glancing=config(attacker,'glancing_blows',1)
    result.impact_bth=result.bth-(glancing==2 and weapon.weapon_type!=WeaponType.TMISSILE)
    result.margin=result.roll-result.impact_bth
    result.glancing=bool(glancing and result.roll==result.impact_bth)
    result.swarm_attack=bool(swarm_attack)
    if not result.range_ok:return result
    # A missed nonmissile shot at mounted suits may strike their host instead.
    try_clear=True
    if result.margin<0 and weapon.weapon_type!=WeaponType.TMISSILE and target is not None:
        from systems.combat_firing import swarm_id
        from systems.targeting import resolve_unit
        if target.unit_type==UnitType.BSUIT and swarm_id(target)>-1:
            host=resolve_unit(attacker,swarm_id(target))
            if host is not None:
                from systems.combat_firing import unstable_arc
                alternate=calculate_bth(attacker,host,weapon,distance,gunnery_skill,section,
                    unstable_lock_arc=unstable_arc(engine or attacker._engine,attacker,host),
                    w_ammo_mode=w_ammo_mode,indirect_fire=indirect_fire,spotter=spotter,
                    w_fire_mode=w_fire_mode,critical=w_critical)
                if result.roll>=alternate.total:
                    from systems.movement_commands import notify
                    from systems.sensors import los_broadcast
                    notify(host,'The shot hits you instead!')
                    los_broadcast(host,'manages to get in the way of the shot instead!')
                    target=host;result.target_id=host._id
                    result.impact_bth=alternate.total;result.margin=result.roll-alternate.total
                    result.glancing=bool(glancing and result.margin==0)
                elif target.map and target.map.base_elevation(target.x,target.y)<target.z-2:try_clear=False
    aim_hit=False
    if target is not None and (weapon.weapon_type==WeaponType.TMISSILE or result.margin>=0) and attacker.aim!=NUM_SECTIONS and is_target_immobile(target) and not swarm_attack:
        r=aim_roll if aim_roll is not None else source_roll('aim_rolls', roll_2d6)
        aim_hit=r in (6,7,8)
    # Check hit
    if result.margin < 0:
        result.hit = False
        result.messages.append(f"Attack missed (rolled {result.roll} vs BTH {result.bth})")
        if weapon.weapon_type != WeaponType.TMISSILE:
            damage=determine_damage(attacker,target,weapon,distance,w_section,w_critical,
                gattling_shots=gattling_shots,ammo_mode=w_ammo_mode,
                failure_type=result.failure_type,failure_modifier=result.failure_modifier,temporary=True,hit_x=mapx,hit_y=mapy)
            if try_clear:possibly_ignite_or_clear(attacker,weapon_idx,w_ammo_mode,damage,mapx,mapy,0)
        return result

    result.hit = True
    result.messages.append(f"Attack hit! (rolled {result.roll} vs BTH {result.bth})")

    base_damage=weapon.damage
    if weapon.weapon_type != WeaponType.TMISSILE:
        from dataclasses import replace
        damage=determine_damage(attacker,target,weapon,distance,w_section,w_critical,
            gattling_shots=gattling_shots,ammo_mode=w_ammo_mode,
            failure_type=result.failure_type,failure_modifier=result.failure_modifier,hit_x=mapx,hit_y=mapy)
        if result.glancing and target is not None:
            from systems.movement_commands import notify
            from systems.sensors import los_broadcast
            los_broadcast(target,'is nicked by a glancing blow!')
            notify(target,'You are nicked by a glancing blow!')
            damage=max(1,(damage+1)//2)
        weapon=replace(weapon,damage=damage)

    # HitTarget checks membership before cluster draws or count notices.
    if weapon.weapon_type!=WeaponType.TMISSILE and (w_ammo_mode&AmmoMode.LBX_MODE or w_fire_mode&(FireMode.ULTRA_MODE|FireMode.RFAC_MODE|FireMode.RAC_MODES)):
        from data.missile_clusters import missile_row
        if missile_row(weapon,attacker,w_fire_mode) is None:return result

    if weapon.weapon_type == WeaponType.TMISSILE:
        from data.missile_clusters import missile_row
        if missile_row(weapon,attacker) is None:return result
        from systems.missile import swarm_hit_target
        if target is not None and w_ammo_mode & (AmmoMode.SWARM_MODE | AmmoMode.SWARM1_MODE):
            swarm=swarm_hit_target(attacker,target,weapon,w_section,w_critical,result.bth,
                result.bth+1,weapon.missiles,bool(w_ammo_mode&AmmoMode.SWARM1_MODE),result.roll,
                cluster_roll=cluster_roll,ams_roll=ams_roll,location_rolls=location_rolls,swarm_attack=swarm_attack)
            for name in ('damage_dealt','armor_damage','internal_damage','criticals_rolled','ams_shot_down',
                         'missiles_remaining','swarm_targets','location','is_rear','is_critical'):
                setattr(result,name,getattr(swarm,name))
            result.messages.extend(swarm.messages)
            result.message_audiences.extend(swarm.message_audiences)
        else:
            _missile_weapon_hit(result,attacker,target,weapon,w_fire_mode,w_ammo_mode,w_section,
                w_critical,engine or attacker._engine,cluster_roll,ams_roll,location_rolls,
                location_roll,los=los,hit_x=mapx,hit_y=mapy)
        result.target_destroyed=target.is_destroyed if target is not None else False
        return result

    # Hex impact: no hit location — each hit dispatches through hex_hit
    # (the mech.combat.c:1800-1802 hitMech-else-hex_hit pattern; cluster
    # weapons dispatch once per hitting missile with the per-missile
    # damage, mech.combat.c:1784-1805 loop shape)
    if target is None:
        is_lbx=bool(w_ammo_mode & AmmoMode.LBX_MODE)
        salvo=(base_damage if is_lbx else
               2 if w_fire_mode & (FireMode.ULTRA_MODE|FireMode.RFAC_MODE|FireMode.RAC_TWOSHOT_MODE) else
               4 if w_fire_mode & FireMode.RAC_FOURSHOT_MODE else
               6 if w_fire_mode & FireMode.RAC_SIXSHOT_MODE else 1)
        hits=_cluster_hits(attacker,weapon,w_section,w_critical,None,salvo,cluster_roll,result.glancing,w_fire_mode) if salvo>1 or is_lbx else 1
        if salvo>1 or is_lbx:_notify_hit_count(result,attacker,hits,"pellet" if is_lbx else "slug",los)
        for _ in range(hits):
            hex_hit(attacker,mapx,mapy,weapon_idx,w_ammo_mode,1 if is_lbx else weapon.damage,1)
        return result

    # ---- Missile weapons: MissileWeaponHit -> Missile_Hits delegation ----
    # (mech.combat.missile.c:191-371): cluster row via MissileHitIndex, AMS
    # after the cluster roll, inferno/NARC routing, grouped damage through
    # Missile_Hit with salvo_size = Clustersize(weapindx).
    if weapon.weapon_type == WeaponType.TMISSILE:
        _missile_weapon_hit(
            result, attacker, target, weapon, w_fire_mode, w_ammo_mode,
            w_section, w_critical, engine, cluster_roll, ams_roll,
            location_rolls, location_roll, los=los)
    else:
        # tUsingTC (mech.combat.c:1580-1584): firing crit carries ON_TC,
        # weapon is neither missile nor artillery, TC not destroyed, an aim
        # is set and the stored aim type matches the target's type.
        t_using_tc = (
            bool(w_fire_mode & FireMode.ON_TC) and
            weapon.weapon_type != WeaponType.TARTILLERY and
            not attacker.has_crit_status(CritStatus.TC_DESTROYED) and
            attacker.aim != NUM_SECTIONS and
            attacker.aim_type == target.unit_type)

        # Non-missile multiple-hit weapons: LBX pellets, Ultra/RFAC/RAC
        # slugs (mech.combat.c:1671-1805)
        is_lbx = bool(w_ammo_mode & AmmoMode.LBX_MODE)
        salvo = 0
        if is_lbx:
            salvo = base_damage       # Table size does not shrink with glancing damage
        elif w_fire_mode & (FireMode.ULTRA_MODE | FireMode.RFAC_MODE):
            salvo = 2
        elif w_fire_mode & FireMode.RAC_TWOSHOT_MODE:
            salvo = 2
        elif w_fire_mode & FireMode.RAC_FOURSHOT_MODE:
            salvo = 4
        elif w_fire_mode & FireMode.RAC_SIXSHOT_MODE:
            salvo = 6

        if salvo > 1 or is_lbx:
            from systems.missile import clustersize, missile_hit

            num_hit = _cluster_hits(attacker, weapon, w_section, w_critical,
                                    target, salvo, cluster_roll, result.glancing,w_fire_mode)
            # "You hit with %d %s%s!" (mech.combat.c:1760-1767)
            word = "pellet" if is_lbx else "slug"
            _notify_hit_count(result,attacker,num_hit,word,los)

            if is_lbx:
                # Missile_Hit with damage 1 and Clustersize (== 1 for LBX)
                # (mech.combat.c:1769-1772); each pellet group lands
                # through the DamageMech-shaped callback
                # (mech.combat.missile.c:107-111), which accumulates the
                # damage on `result` and rolls criticals.
                mh = missile_hit(
                    attacker, target, weapon, num_hit, 1,
                    clustersize(weapon), fire_mode=w_fire_mode,
                    ammo_mode=w_ammo_mode, location_rolls=location_rolls,
                    los=los,bth=result.impact_bth,swarm_attack=result.swarm_attack,
                    damage_func=_group_damage_func(
                        result, attacker, target, weapon, w_ammo_mode,
                        engine=engine))
                _extend_log(result,mh.messages)
                if mh.groups:
                    result.location = mh.groups[0][0]
                    result.is_rear = mh.groups[0][2]
            else:
                # Per-slug loop (mech.combat.c:1784-1805).
                rolls = list(location_rolls) if location_rolls else []
                first = True
                while num_hit:
                    # C QUIRK PORTED VERBATIM (mech.combat.c:1786-1795,
                    # Part 1 #13): there is NO `else` between the aim_hit
                    # and tUsingTC branches, so when aim_hit is set and the
                    # TC is not in play the FindAimHitLoc result is
                    # immediately OVERWRITTEN by FindTargetHitLoc — aimed
                    # shots never steer multi-hit slugs.
                    if aim_hit:
                        loc, isrear, iscrit = find_aim_hit_loc(
                            attacker, target)
                    if t_using_tc:
                        loc, isrear, iscrit = find_tc_hit_loc(
                            attacker, target, success_roll=tc_roll)
                    else:
                        hg = determine_hit_group(attacker, target)
                        isrear = (hg == HitGroup.BACK)
                        roll = rolls.pop(0) if rolls else (
                            location_roll if first else None)
                        from systems.hit_locations import target_hit_location
                        loc, isrear, iscrit = target_hit_location(attacker, target, hg, roll)
                    _apply_single_hit(result, attacker, target, weapon,
                                      loc, isrear, iscrit, weapon.damage,
                                      w_ammo_mode, engine=engine)
                    first = False
                    num_hit -= 1
        else:
            # Single-hit dispatch (mech.combat.c:1592-1598):
            if 'Flamer' in weapon.name and w_fire_mode & FireMode.HEAT_MODE:
                from systems.movement_commands import notify
                text='%cy%chThe flaming plasma sprays all over you!%cn'
                notify(target,text);result.messages.append(text)
                notify(attacker,'%cgYou cover your target in flaming plasma!%cn')
                target.weap_heat+=base_damage
                return result
            if 'Coolant' in weapon.name and target.unit_type!=UnitType.MW:
                cooled=attacker if w_fire_mode & FireMode.HEAT_MODE else target
                from systems.movement_commands import notify
                if not w_fire_mode&FireMode.HEAT_MODE:notify(attacker,'%ccYou hit with the stream of coolant!!%c')
                text='%ccCoolant washes over your systems!!%c'
                notify(cooled,text);result.messages.append(text)
                cooled.weap_heat-=base_damage
                return result
            # aim_hit -> FindAimHitLoc, elif tUsingTC -> FindTCHitLoc,
            # else FindTargetHitLoc.
            if aim_hit:
                loc, isrear, iscrit = find_aim_hit_loc(
                    attacker, target, location_roll=location_roll)
            elif t_using_tc:
                loc, isrear, iscrit = find_tc_hit_loc(
                    attacker, target, success_roll=tc_roll,
                    location_roll=location_roll)
            else:
                hit_group = determine_hit_group(attacker, target)
                isrear = (hit_group == HitGroup.BACK)
                from systems.hit_locations import target_hit_location
                loc, isrear, iscrit = target_hit_location(attacker, target, hit_group, location_roll)
            result.is_rear = isrear
            _apply_single_hit(result, attacker, target, weapon, loc,
                              isrear, iscrit, weapon.damage, w_ammo_mode,
                              engine=engine)

    result.target_destroyed = target.is_destroyed

    return result


# =============================================================================
# Attack-resolution helpers (E.4 / fire-path wiring)
# =============================================================================

def _cluster_hits(attacker,weapon,w_section,w_critical,target,salvo,
                  cluster_roll=None,glance=False,fire_mode=None,table_row=None):
    """Source weapon row, or RAC's named SRM row; no generic rack substitution."""
    from data.missile_clusters import missile_row
    from entities.weapon import WeaponFlags
    from systems.missile import missile_hit_index
    if fire_mode is None:
        fire_mode=attacker.sections[w_section].criticals[w_critical].firemode if w_section is not None and w_critical is not None else 0
    row=table_row if table_row is not None else missile_row(weapon,attacker,fire_mode)
    if row is None:return 0
    if w_section is not None and w_critical is not None:
        index=missile_hit_index(attacker,weapon,w_section,w_critical,target,glance=glance,fresh_roll=cluster_roll)
    elif weapon.special&WeaponFlags.STREAK:
        index=10
    else:
        roll=cluster_roll if cluster_roll is not None else source_roll('cluster_rolls',roll_2d6)
        index=max(-1 if glance else 0,min(10,roll-2-(4 if glance else 0)))
    return 1 if index<0 else row[index]


def _notify_hit_count(result,attacker,count,word,los,*,swarm=False):
    if not los:return
    from systems.movement_commands import notify
    text=f'%cg{"The swarm hits" if swarm else "You hit"} with {count} {word}{"s" if count>1 else ""}!%c'
    notify(attacker,text)
    result.messages.append(text)


def _extend_log(result: AttackResult, log) -> None:
    """Fold a systems.missile MessageLog into the AttackResult messages."""
    if log is None:
        return
    entries=getattr(log,'ordered',[]) or [(audience,text) for audience in ('attacker','target','broadcast') for text in getattr(log,audience,[])]
    for audience,text in entries:
        result.messages.append(text)
        result.message_audiences.append(dict(audience=audience,text=text))


def _group_damage_func(result: AttackResult, attacker, target, weapon,
                       w_ammo_mode: int, engine=None):
    """
    missile_hit damage_func standing in for DamageMech
    (mech.combat.missile.c:107-111): every missile/pellet group runs the
    same armor/transfer/critical path as a single hit, so salvos that eat
    internal structure roll criticals exactly as the C's HandleCritical
    arm does.  Damage accumulates on `result`; the return value feeds
    MissileHitResult.total_damage.
    """
    def damage_group(location, damage, is_rear, is_critical):
        before = result.damage_dealt
        _apply_single_hit(result, attacker, target, weapon, location,
                          is_rear, is_critical, damage, w_ammo_mode,
                          engine=engine)
        return result.damage_dealt - before
    return damage_group


def _missile_weapon_hit(result, attacker, target, weapon, w_fire_mode,
                        w_ammo_mode, w_section, w_critical, engine,
                        cluster_roll, ams_roll, location_rolls,
                        location_roll, incoming=None, los=1, hit_x=-1, hit_y=-1) -> AttackResult:
    """
    Missile salvo resolution against a unit — port of the Missile_Hits
    core (mech.combat.missile.c:191-371), mech-target arm:

    - AMS prefill BEFORE the hit branch (:231-240): the AMS spends heat,
      recycle and ammo even when the salvo missed; pods count as
      incoming 1.
    - NARC/iNARC pod weapons route to narc_attach (:242-300); a shot-down
      pod is wholly stopped.
    - Cluster row via MissileHitIndex (:325-330), then AMS kills applied
      AFTER the cluster roll (:337-358).
    - INFERNO_MODE salvos jelly the target instead of doing damage
      (:362-364).
    - Everything else lands through Missile_Hit with
      salvo_size = Clustersize(weapindx) (mech.combat.h:17): LRMs in 5s,
      SRMs one location per 2-damage missile.

    Ordinary resolve_attack calls are guarded by HitTarget's player-roll
    threshold (mech.combat.c:1730-1734). Direct missile_hit_target calls,
    including later Swarm hops, can still miss and stop after AMS/pod
    handling, before any cluster or damage draw.
    """
    from systems import missile as msl
    from entities.weapon import WeaponType, WeaponFlags

    result.los = los
    pod = msl.resolve_narc_pod_type(weapon, w_ammo_mode)
    from data.missile_clusters import missile_row
    row=missile_row(weapon,attacker) or (1,)*11  # Direct C calls reach the NoWeapon sentinel row.
    salvo = row[10] if incoming is None else incoming
    if result.failure_type == 'CRAZY_MISSILES':
        salvo=int(salvo*result.failure_modifier/100)
    result.missiles_remaining = salvo

    # AMS prefill (mech.combat.missile.c:231-240)
    shot_down = 0
    if weapon.weapon_type == WeaponType.TMISSILE and target is not None and msl.ams_defends_against(w_ammo_mode):
        defense = msl.locate_ams_defenses(target)
        if defense is not None:
            fired = msl.ams_missiles(
                attacker, target,
                1 if pod != msl.NARC_POD_NONE else salvo,
                defense.weapon, defense.ammo_section,
                defense.ammo_critical, los, result.hit,
                shots_roll=ams_roll)
            shot_down = fired.shot_down
            result.ams_shot_down = shot_down
            _extend_log(result, fired.messages)

    # NARC/iNARC pods (mech.combat.missile.c:242-300)
    if pod != msl.NARC_POD_NONE:
        result.missiles_remaining = 0
        if target is None:return result
        attach = msl.narc_attach(attacker, target, pod, result.hit, los,
                                 ams_shot_down=shot_down,
                                 location_roll=location_roll)
        _extend_log(result, attach.messages)
        if attach.attached:
            result.location = Location(attach.location)
            result.is_rear = attach.is_rear
        return result

    if not result.hit:
        return result

    # Recovered Aerospace selects by remaining incoming and STREAK flag.
    # Its no-row return precedes MissileHitIndex (and its random draw).
    if is_aero(attacker):
        from data.missile_clusters import historical_hit_row
        row = historical_hit_row(weapon, salvo)
        if row is None:
            result.missiles_remaining = 0
            return result

    # Cluster row -> hit count (mech.combat.missile.c:325-330)
    num_hit = min(salvo,_cluster_hits(attacker, weapon, w_section, w_critical,
                            target, salvo, cluster_roll, result.glancing,w_fire_mode,table_row=row))

    _notify_hit_count(result,attacker,num_hit,'missile',los,swarm=los!=1)

    # AMS kills come off AFTER the cluster roll (mech.combat.missile.c:
    # 337-358)
    num_hit, ams_log = msl.apply_ams_to_salvo(num_hit, shot_down, los,attacker=attacker,target=target)
    _extend_log(result, ams_log)
    if num_hit <= 0:
        result.missiles_remaining=0
        return result
    result.missiles_remaining=salvo-num_hit

    if w_ammo_mode & AmmoMode.INFERNO_MODE:
        # Inferno: jelly, NO normal damage (mech.combat.missile.c:362-364)
        if target is None:
            hex_hit(attacker,hit_x,hit_y,weapon.index,w_ammo_mode,0,0)
        elif engine is not None:
            burn = msl.inferno_hit(engine, attacker, target, num_hit, los)
            _extend_log(result, getattr(burn, 'messages', None))
        else:
            # No engine to schedule the burn end event on; the splash is
            # still damage-free.
            result.messages.append(
                "%d inferno missile%s splash the target!" % (
                    num_hit, "s" if num_hit > 1 else ""))
        return result

    if result.glancing and target is not None and not weapon.special&WeaponFlags.STREAK:
        from systems.sensors import los_broadcast
        from systems.movement_commands import notify
        los_broadcast(target,'is nicked by a glancing blow!')
        notify(target,'You are nicked by a glancing blow!')
    per_missile = weapon.damage_per_missile or weapon.damage
    # Each group lands through the DamageMech-shaped callback
    # (mech.combat.missile.c:107-111), which accumulates the damage on
    # `result` and rolls criticals — do NOT add total_damage again.
    salvo_hit = msl.missile_hit(
        attacker, target, weapon, num_hit, per_missile,
        msl.clustersize(weapon), fire_mode=w_fire_mode,
        ammo_mode=w_ammo_mode, location_rolls=location_rolls,hit_x=hit_x,hit_y=hit_y,los=los,bth=result.impact_bth if result.impact_bth is not None else result.bth,
        swarm_attack=result.swarm_attack,
        damage_func=_group_damage_func(result, attacker, target, weapon,
                                       w_ammo_mode, engine=engine))
    _extend_log(result, salvo_hit.messages)
    if salvo_hit.groups:
        result.location = salvo_hit.groups[0][0]
        result.is_rear = salvo_hit.groups[0][2]
    return result


def _apply_single_hit(result: AttackResult, attacker, target, weapon,
                      location, is_rear: bool, is_critical: bool,
                      damage: int, w_ammo_mode: int = 0,
                      engine=None) -> None:
    """
    Apply one hit's damage, transfer and critical rolls to the target.

    The armor/internal/transfer sequence is DamageMech's
    (mech.damage.c:488-539); the critical brackets are HandleCritical's;
    the armor-piercing crit-through-armor arm is mech.damage.c:167-191
    (systems.damage.check_ap_critical).
    """
    if result.location is None:
        result.location = location
    result.is_critical = result.is_critical or is_critical
    first_hop = True

    def observed_hit(recipient, hit_location, armor, structure, crit_results):
        nonlocal first_hop
        if first_hop:
            result.armor_damage += armor
            result.internal_damage += structure
            first_hop = False
        if crit_results:
            result.criticals_rolled += len(crit_results)
            result.messages.append(f"Critical hit! {len(crit_results)} critical(s)")
            for critical in crit_results:
                if critical.message:
                    result.messages.append(f"  - {critical.message}")
                if critical.mech_destroyed:
                    result.target_destroyed = True

    from systems.personal_damage import personal_to_damage
    damage=personal_to_damage(target,weapon,damage)
    result.damage_dealt += apply_damage_with_transfer(
        target, location, damage, is_rear, attacker, is_critical,
        weapon, w_ammo_mode, engine, _on_hit=observed_hit,bth=result.impact_bth if result.impact_bth is not None else result.bth,
        los=result.los,ignore_swarmers=result.swarm_attack)
    result.target_destroyed = target.is_destroyed


# =============================================================================
# Weapon Recycle Tracking
# =============================================================================

@dataclass
class WeaponSlot:
    """Tracks a weapon's mount and recycle status."""
    weapon: 'Weapon'                 # The weapon definition
    section: Location                # Where it's mounted
    recycle: int = 0                 # Ticks until ready (0 = ready)
    ammo_count: int = -1            # -1 = infinite, else shots remaining
    destroyed: bool = False          # Is the weapon destroyed?

    @property
    def is_ready(self) -> bool:
        """Check if weapon is ready to fire."""
        return self.recycle <= 0 and not self.destroyed

    @property
    def has_ammo(self) -> bool:
        """Check if weapon has ammo (or doesn't need it)."""
        return self.ammo_count != 0

    def fire(self) -> bool:
        """
        Fire the weapon, starting recycle timer.

        Returns True if weapon was fired, False if not ready.
        """
        if not self.is_ready or not self.has_ammo:
            return False

        self.recycle = self.weapon.vrt
        if self.ammo_count > 0:
            self.ammo_count -= 1
        return True

    def tick(self) -> None:
        """Advance recycle timer by one tick (second)."""
        if self.recycle > 0:
            self.recycle -= 1


# =============================================================================
# Weapon Fire Pipeline (heat + ammo + recycle)
# =============================================================================

# Reference: src/include/btconfig.h:136 - #define WEAPON_TICK 2
# One recycle "tick" is 2 seconds; a weapon's recycle countdown is
# WEAPON_TICK * vrt (mech.combat.c:1353-1354).
WEAPON_TICK = 2


def part_is_nonfunctional(mech: 'Mech', loc: int, slot: int) -> bool:
    """
    Is a crit slot disabled, broken, or destroyed?

    Reference: btmacros.h:324 - PartIsNonfunctional(a,b,c) =
    PartIsDisabled || PartIsBroken || PartIsDestroyed.  Expanding the three
    macros (btmacros.h:328, 331, 334) the flag union is
    DISABLED_MODE | BROKEN_MODE | DESTROYED_MODE.  DAMAGED_MODE alone does
    *not* make a part nonfunctional.
    """
    firemode = mech.sections[loc].criticals[slot].firemode
    return bool(firemode & (FireMode.DISABLED_MODE | FireMode.BROKEN_MODE |
                            FireMode.DESTROYED_MODE))


def find_ammo_in_section(mech: 'Mech', section: int, ammo_type: int,
                         nogof: int = 0, gof: int = 0) -> int:
    """
    Find a usable ammo bin of the given crit type in one section.

    Port of findAmmoInSection (mech.utils.c:1301-1321).  A usable bin is a
    slot whose type matches, that is not PartIsNonfunctional, whose ammo
    mode passes the (nogof, gof) filter pair — no forbidden NOGOF bit set,
    and at least one required GOF bit when gof is nonzero
    (mech.utils.c:1308-1312; the C's comment: "Can't use LBX ammo as
    normal, but can use Narc and Artemis as normal") — and whose data byte
    (rounds remaining, mech.h:599-608) is > 0.  The loop bound is
    NUM_CRITICALS exactly as in the C (mech.utils.c:1305), not
    crits_in_loc.

    The C checks PartIsNonfunctional twice (mech.utils.c:1308 and 1314)
    with the mode filters in between; the two checks collapse into one.

    Returns the slot index, or -1 if no bin was found.
    """
    for i in range(NUM_CRITICALS):
        crit = mech.sections[section].criticals[i]
        if (crit.type == ammo_type and
                not part_is_nonfunctional(mech, section, i) and
                (not nogof or not (crit.ammomode & nogof)) and
                (not gof or (crit.ammomode & gof)) and
                crit.data > 0):
            return i
    return -1


def find_ammo_for_weapon(
    mech: 'Mech', weapon_idx: int, section: int, nogof: int = 0,
    gof: int = 0, *, critical: int = None, start: int = None,
) -> Optional[tuple[Location, int]]:
    """FindAmmoForWeapon_sub: mount preference, start, then other sections.

    section/critical identify the mount; either -1 (or critical=None) disables
    preference. start independently selects the first ordinary search section.
    Existing firing callers default start to their mount section.
    """
    start = section if start is None else start
    if not 0 <= start < len(mech.sections):
        raise ValueError('Unsupported ammunition search start section')
    desired = i2ammo(weapon_idx)
    desired_loc = -1
    if section >= 0 and critical is not None and critical >= 0:
        from systems.enhanced_crits import get_weap_data
        _, _, first = get_weap_data(mech, section, critical)
        desired_loc = mech.sections[section].criticals[first].desired_ammo_loc
    if desired_loc >= 0:
        found = find_ammo_in_section(mech, desired_loc, desired, nogof, gof)
        if found >= 0:
            return (Location(desired_loc), found)
    found = find_ammo_in_section(mech, start, desired, nogof, gof)
    if found >= 0:
        return (Location(start), found)
    for loc in range(len(mech.sections)):
        if loc == start or loc == desired_loc:
            continue
        found = find_ammo_in_section(mech, loc, desired, nogof, gof)
        if found >= 0:
            return (Location(loc), found)
    return None


def fire_weapon(
    attacker: 'Mech',
    target: 'Mech',
    weapon_number: int,
    distance: float,
    **kwargs,
) -> AttackResult:
    """
    Fire a weapon by number: gates, attack resolution, then post-fire state.

    Port of the FireWeaponNumber validation subset (mech.combat.c:372+) and
    the FireWeapon core's post-fire tail (mech.combat.c:767+, 1280,
    1352-1401).  `weapon_number` indexes `attacker.weapons`, the port's
    analogue of the C's per-mech weapon numbering
    (FindWeaponNumberOnMech_Advanced, mech.utils.c:1162-1217).

    Failure style: every gate failure returns an AttackResult with hit=False
    and a single explanatory message (the C's DOCHECK notify text), matching
    resolve_attack's out-of-range return.  No exceptions are raised.

    Extra kwargs (to_hit_roll, location_roll) pass through to resolve_attack
    for deterministic tests.

    Arc / LOS / target-lock validation lives in the command-level wrapper
    fire_weapon_number (mech.combat.c:527-655) — direct fire_weapon callers
    (mapless tests, AI harnesses) intentionally skip those gates.

    """
    from entities.weapon import WeaponFlags, get_weapon_by_index
    from systems.enhanced_crits import get_crit_added_heat
    from systems.piloting import find_pilot_gunnery

    def _fail(message: str, deliver=True) -> AttackResult:
        if deliver:
            from systems.movement_commands import notify
            notify(attacker,message)
        result = AttackResult()
        result.messages.append(message)
        return result

    from systems.weapon_inventory import sync_weapon_states
    sync_weapon_states(attacker)
    if not 0 <= weapon_number < len(attacker.weapons):
        return _fail("Illegal Weapon Number!")
    ws = attacker.weapons[weapon_number]
    weapon = get_weapon_by_index(ws.weapon_idx)
    slot = attacker.sections[ws.section].criticals[ws.critical]
    sight = kwargs.pop('sight', False)

    # Started gate: the C command layer refuses fire from an unstarted mech
    # before FireWeaponNumber is ever reached (cch(MECH_USUALO),
    # mech.combat.c:352).
    if not attacker.is_started:
        return _fail("Reactor is not online!")

    # Destroyed section / destroyed weapon: destroying a section DestroyPart()s
    # its crits, so both cases surface as PartIsNonfunctional and
    # FindWeaponNumberOnMech_Advanced returns TIC_NUM_DESTROYED
    # (mech.utils.c:1182-1185), reported as "That weapon has been destroyed!"
    # (mech.combat.c:509-510).
    if attacker.unit_type != UnitType.AERO and attacker.is_section_destroyed(ws.section):
        return _fail("That weapon has been destroyed!")
    if part_is_nonfunctional(attacker, ws.section, ws.critical):
        return _fail("That weapon has been destroyed!")

    # Recycle gate: a weapon crit's data byte is its recycle countdown
    # (mech.h:599-608); data > 0 makes FindWeaponNumberOnMech_Advanced return
    # TIC_NUM_RELOADING (mech.utils.c:1186-1190), reported as "That weapon is
    # still reloading!" (mech.combat.c:440-441).
    if slot.data > 0 and not sight:
        return _fail("That weapon is still reloading!")

    from systems.enhanced_crits import part_temp_nuke
    if part_temp_nuke(slot) and not sight:
        return _fail('That weapon has a temporary failure!')

    if slot.ammomode & AmmoMode.STINGER_MODE:
        if kwargs.get('ishex'):return _fail('Stinger missiles cannot shoot hexes!')
        if target is not None and not (target.is_jumping or target.cocoon or
                target.move_type in (MoveType.FLY,MoveType.VTOL) and not target.has_status(MechStatus.LANDED)):
            return _fail('Stinger missiles can only engage airborne targets!')
    if 'Coolant' in weapon.name and slot.firemode & FireMode.HEAT_MODE:target=attacker
    submerged=attacker.z<0 and (attacker.z<-1 or attacker.is_fallen or ws.section in (Location.LLEG,Location.RLEG) or
        attacker.move_type==MoveType.QUAD and ws.section in (Location.LARM,Location.RARM))
    if submerged and weapon.range_short_water<=0:return _fail('This weapon may not be fired underwater.')

    # CrewStunned is the vehicle crew event (btmacros.h:384). The separate
    # MECH_STUNNED guard belongs to non-sight FireWeaponNumber attempts.
    from core.events import EventType
    queue=getattr(attacker,'_engine',None)
    if queue is not None and queue.events.has_event_type_data(EventType.UNSTUN_CREW,attacker):
        return _fail("You are too stunned to fire a weapon!")
    if queue is not None:
        for kind,message in ((EventType.UNJAM_TURRET,'turret'),(EventType.UNJAM_AMMO,'weapon')):
            if queue.events.has_event_type_data(kind,attacker):return _fail(f'You are too busy unjamming {"your turret" if message=="turret" else "a weapon"}!')
        if queue.events.has_event_type_data(EventType.REMOVE_PODS,attacker):return _fail('You are too busy removing iNARC pods!')
    if getattr(attacker,'removing_pods',False):return _fail('You are too busy removing iNARC pods!')

    # MechSwarmTarget gates (mech.combat.c:795-833): a swarming attacker may
    # fire only at the mech it clings to; that shot is a swarm attack, whose
    # BTH is forced to 0 downstream (mech.combat.c:871-873).
    from systems.movement_commands import mode_locked
    if mode_locked(attacker):
        return _fail('Movement modes disallow weapons fire.')
    swarm_attack = 0
    from systems.combat_firing import swarm_id
    swarm_carrier = swarm_id(attacker)
    if swarm_carrier > 0:
        if target is None or target._id != swarm_carrier:
            return _fail("You're too busy holding on for dear life!")
        swarm_attack = 1

    # A gattling burst rolls its shot count at fire time, Number(1, 6)
    # (mech.combat.c:841).
    gattling_shots = 0
    if slot.firemode & FireMode.GATTLING_MODE:
        from core.randomness import draw
        gattling_shots = draw('gattling_shots',1,6,roll_1d6)

    from entities.weapon import WeaponType
    from systems.combat_ammunition import find_and_check,AmmoPlan
    ammo_plan = AmmoPlan(gattling_shots=gattling_shots) if sight else find_and_check(attacker, ws, gattling_shots)
    if not ammo_plan.accepted:
        return _fail(ammo_plan.message,deliver=False)
    ammo_bin, ammo_bin1 = ammo_plan.first, ammo_plan.second
    gattling_shots = ammo_plan.gattling_shots

    # The firing crit's ammo mode word feeds AddTerrainMod's incendiary
    # light trick (mech.bth.c:369, GetPartAmmoMode); an explicit kwarg from
    # the caller wins.
    kwargs.setdefault('w_ammo_mode', int(slot.ammomode))
    # The firing crit's fire mode (ON_TC / burst modes) and coordinates,
    # for the TC term (mech.bth.c:331-339), tUsingTC (mech.combat.c:
    # 1580-1584) and MissileHitIndex (mech.combat.missile.c:119-189).
    kwargs.setdefault('w_fire_mode', int(slot.firemode))
    kwargs.setdefault('w_section', int(ws.section))
    kwargs.setdefault('w_critical', int(ws.critical))
    # The C's weapindx, forwarded to hex_hit / possibly_ignite_or_clear
    # (mech.combat.c:1801, 1343).
    kwargs.setdefault('weapon_idx', ws.weapon_idx)

    def consume_ammunition():
        from systems.combat_ammunition import decrement
        decrement(attacker, ws.weapon_idx, ws, ammo_plan)

    def check_brand_failure(result):
        from systems.failures import check_weapon_failed
        from systems.enhanced_crits import (can_weap_explode_from_damage,
            can_weap_jam_from_damage, set_part_temp_nuke, get_weap_data)
        failure = check_weapon_failed(attacker, ws.section, ws.critical)
        result.failure_type, result.failure_modifier = failure.type, failure.modifier
        if failure.type in ('WEAPON_DUD', 'WEAPON_JAMMED', 'POWER_SPIKE'):
            if failure.type != 'POWER_SPIKE':
                consume_ammunition()
            ws.recycle = slot.data
            result.shot_aborted = True
        elif failure.type == 'RANGE':
            from systems.combat_ranges import extreme_range,underwater
            result.range_ok = extreme_range(attacker,weapon,underwater(attacker,ws.section))-failure.modifier >= distance
            if not result.range_ok:
                from systems.movement_commands import notify
                text='Due to weapons failure your shot falls short of its target!'
                notify(attacker,text);result.messages.append(text)
    def check_firing_damage(result):
        from systems.combat_ammunition import risky_mode_failure
        from systems.enhanced_crits import (can_weap_explode_from_damage,
            can_weap_jam_from_damage,set_part_temp_nuke,get_weap_data)
        if risky_mode_failure(attacker,ws,result,ammo_plan):return
        if can_weap_explode_from_damage(attacker, ws.section, ws.critical, result.roll):
            from systems.criticals import destroy_weapon,find_first_weapon_crit
            from systems.sensors import los_broadcast
            from systems.movement_commands import notify
            text=(f'%ch%crThe damaged charging crystal on your {weapon.name[3:]} overloads!%cn'
                  if weapon.weapon_type==WeaponType.TBEAM else
                  f'%ch%crThe damaged ammo feed on your {weapon.name[3:]} triggers an internal explosion!%cn')
            notify(attacker,text);result.messages.append(text)
            if weapon.weapon_type != WeaponType.TBEAM:
                consume_ammunition()
            los_broadcast(attacker,'shudders from an internal explosion!')
            size=weapon.crits if attacker.unit_type==UnitType.MECH else 1
            first=find_first_weapon_crit(attacker,ws.section,-1,0,slot.type,size)
            destroy_weapon(attacker, ws.section, slot.type, first, size, size)
            for mount in attacker.weapons:
                if mount.section==ws.section and mount.critical==first:mount.destroyed=True
            apply_damage_with_transfer(attacker,ws.section,0,attacker=attacker,
                engine=kwargs.get('engine') or attacker._engine,internal_damage=weapon.damage,
                ignore_swarmers=True,cause=-1,bth=0,attack_pilot=-1,los=0)
            result.shot_aborted = True

        elif can_weap_jam_from_damage(attacker, ws.section, ws.critical, result.roll):
            from systems.movement_commands import notify
            text=f'%ch%crThe ammo loader mechanism jams on your {weapon.name[3:]}!%cn'
            notify(attacker,text);result.messages.append(text)
            set_part_temp_nuke(slot, 7)
            result.shot_aborted = True

    result = resolve_attack(
        attacker, target, weapon, distance,
        gunnery_skill=find_pilot_gunnery(attacker, weapon),
        section=Location(ws.section),
        swarm_attack=swarm_attack,
        shot_checks=check_brand_failure,
        post_streak_checks=check_firing_damage,
        gattling_shots=gattling_shots,
        sight=sight,
        **kwargs,
    )

    # Impossible hex roll (mech.combat.c:961-966): the C returns before the
    # FIRED/heat/ammo/recycle tail — nothing was fired.
    if sight or result.roll_impossible or result.shot_aborted:
        return result

    # Streak lock failure: the C recycles the launcher and returns *before*
    # the FIRED/heat/ammo tail (mech.combat.c:1064-1074: SetRecyclePart with
    # the same WEAPON_TICK * vrt, "Your streak fails to lock on.", return).
    if result.streak_lock_failed:
        if getattr(attacker,'_engine',None):
            from core.game_loop import update_recycling
            update_recycling(attacker._engine,attacker)
        slot.data = WEAPON_TICK * weapon.vrt
        ws.recycle = slot.data
        from systems.movement_commands import notify
        text='Your streak fails to lock on.'
        notify(attacker,text);result.messages.append(text)
        return result

    # Recycle the weapon: SetRecyclePart(mech, section, critical,
    # WEAPON_TICK * MechWeapons[weapindx].vrt) (mech.combat.c:1353-1354,
    # WEAPON_TICK = 2 at src/include/btconfig.h:136).
    if getattr(attacker,'_engine',None):
        from core.game_loop import update_recycling
        update_recycling(attacker._engine,attacker)
    slot.data = WEAPON_TICK * weapon.vrt
    # Port-only mirror on the parallel weapon list; the crit slot's data byte
    # is authoritative (mech.h:599-608).
    ws.recycle = slot.data

    # Set the heat after firing (mech.combat.c:1355-1393), keyed off the
    # crit's LIVE fire mode — the ultra probe above may have stripped it: a
    # gattling burst heats one point per shot; a RAC burst multiplies the
    # base heat by its round count (the C's selector default of 1 is
    # unreachable behind the mode test, kept anyway); everything else takes
    # base heat plus damaged-crystal heat (energy weapons only,
    # getCritAddedHeat), with ultra / rapid-fire doubling the base heat.
    fire_mode = slot.firemode
    extra_heat = result.failure_modifier if result.failure_type == 'HEAT' else 0
    attacker.weap_heat += extra_heat
    if fire_mode & FireMode.GATTLING_MODE:
        attacker.weap_heat += float(gattling_shots)
    elif weapon.special & WeaponFlags.RAC:
        if fire_mode & FireMode.RAC_TWOSHOT_MODE:
            rac_rounds = 2
        elif fire_mode & FireMode.RAC_FOURSHOT_MODE:
            rac_rounds = 4
        elif fire_mode & FireMode.RAC_SIXSHOT_MODE:
            rac_rounds = 6
        else:
            rac_rounds = 1
        attacker.weap_heat += float((weapon.heat + extra_heat) * rac_rounds)
    else:
        attacker.weap_heat += float(
            weapon.heat + get_crit_added_heat(attacker, ws.section,
                                              ws.critical))
        if fire_mode & (FireMode.ULTRA_MODE | FireMode.RFAC_MODE):
            attacker.weap_heat += float(weapon.heat + extra_heat)

    # Common expenditure includes one-use markers and warning thresholds.
    consume_ammunition()

    if weapon.special & WeaponFlags.HVYGAUSS and attacker.unit_type==UnitType.MECH and abs(attacker.speed)>0:
        from systems.piloting import make_piloting_roll
        from systems.movement_commands import notify
        text='You realize that moving while firing this weapon may not be a good idea after all.'
        notify(attacker,text);result.messages.append(text)
        modifier=2 if attacker.tonnage<=35 else 1 if attacker.tonnage<=55 else 0 if attacker.tonnage<=75 else -1
        if not make_piloting_roll(attacker,modifier).success:
            from physics.jump import mech_falls
            from systems.sensors import los_broadcast
            text="The weapon's recoil knocks you to the ground!"
            notify(attacker,text);result.messages.append(text)
            los_broadcast(attacker,f"topples over from the {weapon.name[3:]}'s recoil!")
            mech_falls(attacker,1,notify_fall=False)

    return result


# =============================================================================
# Command-level fire entry (FireWeaponNumber, mech.combat.c:372-712)
# =============================================================================

def find_target_xy(mech) -> Optional[tuple]:
    """Source FindTargetXY: unit identity wins, hex coordinates need no lock bits."""
    from systems.targeting import resolve_unit
    from physics.hexmath import hex_to_float, ZSCALE
    from core.randomness import float32
    if mech.target != -1:
        target = resolve_unit(mech, mech.target)
        if target is not None and hasattr(target, 'fx'):
            return float32(target.fx), float32(target.fy), float32(target.fz)
        return None
    if mech.targ_x != -1 and mech.targ_y != -1:
        fx, fy = hex_to_float(mech.targ_x, mech.targ_y)
        return fx, fy, float32(mech.targ_z * ZSCALE)
    return None


def is_in_weapon_arc(mech, x: float, y: float, section: int,
                     critical: int) -> int:
    """
    Is the cartesian point (x, y) inside the arc the weapon at
    (section, critical) may fire into?  Port of IsInWeaponArc
    (mech.utils.c:1755-1868).

    Returns the matched arc bits (0 = not in arc), exactly like the C's
    `wantarc ? (wantarc & weaponarc) : 0`.

    """
    from physics.hexmath import in_weapon_arc

    # Leg-mounted (and quad "arm") weapons ignore torso twist: the C clears
    # the twist bits around the InWeaponArc call (mech.utils.c:1760-1768).
    if mech.unit_type == UnitType.MECH and (
            section in (Location.LLEG, Location.RLEG) or
            (mech.move_type == MoveType.QUAD and
             section in (Location.LARM, Location.RARM))):
        ts = mech.status & (MechStatus.TORSO_LEFT | MechStatus.TORSO_RIGHT)
        mech.status &= ~ts
        weaponarc = in_weapon_arc(mech, x, y)
        mech.status |= ts
    else:
        weaponarc = in_weapon_arc(mech, x, y)

    wantarc = NOARC
    if mech.unit_type in (UnitType.MECH, UnitType.BSUIT, UnitType.MW):
        # mech.utils.c:1770-1786
        firemode = mech.sections[section].criticals[critical].firemode
        flipped = mech.has_status(MechStatus.FLIPPED_ARMS)
        if firemode & FireMode.REAR_MOUNT:
            wantarc = REARARC
        elif section == Location.LARM and flipped:
            wantarc = REARARC | LSIDEARC
        elif section == Location.LARM:
            wantarc = FORWARDARC | LSIDEARC
        elif section == Location.RARM and flipped:
            wantarc = REARARC | RSIDEARC
        elif section == Location.RARM:
            wantarc = FORWARDARC | RSIDEARC
        else:
            wantarc = FORWARDARC
    elif mech.unit_type in (UnitType.VEH_GROUND, UnitType.VEH_NAVAL,
                            UnitType.VTOL):
        # mech.utils.c:1787-1805
        if section == VehicleLocation.TURRET:
            wantarc = TURRETARC
        elif section == VehicleLocation.FSIDE:
            wantarc = FORWARDARC
        elif section == VehicleLocation.LSIDE:
            wantarc = LSIDEARC
        elif section == VehicleLocation.RSIDE:
            wantarc = RSIDEARC
        elif section == VehicleLocation.BSIDE:
            wantarc = REARARC
    elif mech.unit_type==UnitType.AERO:
        rear=bool(mech.sections[section].criticals[critical].firemode&FireMode.REAR_MOUNT)
        wantarc={0:FORWARDARC|LSIDEARC|RSIDEARC,1:LSIDEARC|(REARARC if rear else FORWARDARC),
                 2:RSIDEARC|(REARARC if rear else FORWARDARC),
                 3:FORWARDARC|LSIDEARC|RSIDEARC|REARARC,5:REARARC}.get(section,NOARC)
    elif mech.unit_type==UnitType.DS:
        wantarc={5:FORWARDARC,1:LSIDEARC,2:LSIDEARC,0:RSIDEARC,3:RSIDEARC,4:REARARC}.get(section,NOARC)
    elif mech.unit_type==UnitType.SPHEROID_DS:
        wantarc={5:FORWARDARC,1:FORWARDARC|LSIDEARC,2:REARARC|LSIDEARC,
                 0:FORWARDARC|RSIDEARC,3:REARARC|RSIDEARC,4:REARARC}.get(section,NOARC)

    return (wantarc & weaponarc) if wantarc else 0


def mech_lock_fire(mech) -> bool:
    """
    Is the mech holding a *plain* coordinate lock — fire-at-coordinates
    without an explicit hex-lock mode?  Port of MechLockFire
    (mech.h:1078-1080): LOCK_TARGET set AND none of LOCK_BUILDING /
    LOCK_HEX / LOCK_HEX_IGN / LOCK_HEX_CLR.  Only this lock shape runs the
    find_mech_in_hex probe at fire time (mech.combat.c:574-586).
    """
    return (mech.has_status(MechStatus.LOCK_TARGET) and
            not mech.has_status(HEX_LOCK_MODES))


def fire_weapon_number(engine, mech, weapon_number: int, target=None, **kwargs) -> AttackResult:
    """C FireWeaponNumber: command guards, target selection, and firing."""
    from systems.combat_firing import fire_number
    return fire_number(engine,mech,weapon_number,target,**kwargs)


def _in_weapon_arc_of(mech, x: float, y: float) -> int:
    """InWeaponArc(mech, enemyX, enemyY) (mech.bth.c:273) - thin local
    wrapper so fire_weapon_number's two call sites share the lazy import."""
    from physics.hexmath import in_weapon_arc
    return in_weapon_arc(mech, x, y)


# =============================================================================
# Convenience Functions
# =============================================================================

def can_attack(
    attacker: 'Mech',
    target: 'Mech',
    weapon: 'Weapon',
    distance: float,
) -> tuple[bool, str]:
    """
    Check if an attack is possible.

    Returns (can_attack, reason).
    """
    # Check if attacker is operational
    if attacker.is_destroyed:
        return (False, "Attacker is destroyed")

    if not attacker.is_started:
        return (False, "Attacker is not started")

    # Check if target is valid
    if target.is_destroyed:
        return (False, "Target is already destroyed")

    # Check range
    if not weapon.can_fire_at_range(distance):
        return (False, "Target out of range")

    return (True, "")


def estimate_hit_chance(bth: int) -> float:
    """
    Estimate probability of hitting with given BTH.

    Returns probability as percentage (0-100).
    """
    if bth >= 13:
        return 0.0
    if bth <= 2:
        return 100.0

    # 2d6 probability distribution
    probabilities = {
        2: 2.78, 3: 5.56, 4: 8.33, 5: 11.11, 6: 13.89,
        7: 16.67, 8: 13.89, 9: 11.11, 10: 8.33, 11: 5.56, 12: 2.78
    }

    # Sum probabilities of rolling >= BTH
    hit_chance = sum(prob for roll, prob in probabilities.items() if roll >= bth)
    return hit_chance


def decrement_firing_ammunition(attacker, ws, fire_mode, ammo_bin, ammo_bin1, gattling_shots):
    """Compatibility entrypoint for the common source expenditure routine."""
    from systems.combat_ammunition import AmmoPlan, decrement
    decrement(attacker, ws.weapon_idx, ws, AmmoPlan(first=ammo_bin,
              second=ammo_bin1, gattling_shots=gattling_shots))
