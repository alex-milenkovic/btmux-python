# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# Host-derived portions also retain notices/TinyMUX.txt.
# General sources:
#   btech/mech.move.c
#   btech/mech.startup.c
#   btech/mech.update.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/mech.h
#   src/conf.c

"""
Collision and stacking checks for BTMux Python reimplementation.

This module handles:
- collision_check() - wall/drop/jump obstacle detection on hex entry
- SkidMod - PSR modifier from speed for skid-style cliff checks
- domino_space() / domino_space_in_hex() - unit stacking resolution
- cause_damage() - clustered collision damage

Reference:
- BTMux btech/src/btech/mech.update.c - collision_check(), SkidMod()
- BTMux btech/src/btech/mech.move.c - domino_space(), domino_space_in_hex(),
  mechs_in_hex(), cause_damage()
- BTMux btech/src/btech/btmacros.h - elevation/terrain accessor macros
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import math
import random

from physics.movement import MP1, MP_PER_KPH

if TYPE_CHECKING:
    from entities.mech import Mech

# =============================================================================
# Collision-check modes (mech.update.c:94-96)
# =============================================================================

JUMP = 0
WALK_WALL = 1
WALK_DROP = 2
HIT_UNDER_BRIDGE = 3
WALK_BACK = 4

# Damage tables for cause_damage (mech.move.c:1991-1993)
NORMAL = 0
PUNCH = 1
KICK = 2

# =============================================================================
# mudconf defaults (src/conf.c cf_init defaults)
# =============================================================================

BTECH_SKIDCLIFF = 0        # mudconf.btech_skidcliff (conf.c:113)

CARRIER_TECH = 0x80000     # mech.h:1186
BTECH_STACKING = 2         # mudconf.btech_stacking (conf.c:133)
BTECH_STACKDAMAGE = 100    # mudconf.btech_stackdamage (conf.c:134)
BTECH_ROLL_ON_BACKWALK = 1  # mudconf.btech_roll_on_backwalk (conf.c:138)


# =============================================================================
# Accessor macro ports (btmacros.h)
# =============================================================================


def move_mod(mech: 'Mech') -> int:
    """
    Maximum climbable level difference per hex.

    Port of MoveMod (btmacros.h:681-683): 3 for MechWarriors, 2 for
    bipeds/quads, else 1.
    """
    from entities.mech import MoveType, UnitType

    if mech.unit_type == UnitType.MW:
        return 3
    if mech.move_type in (MoveType.BIPED, MoveType.QUAD):
        return 2
    return 1


def jump_speed(mech, game_map):
    from entities.mech import MechStatus
    from core.randomness import float32
    speed = float32(mech.jump_speed)
    if mech.has_status(MechStatus.UNDERGRAVITY) and game_map is not None:
        speed = float32(float32(speed * 100) / max(50, game_map.grav))
    return speed


def jump_speed_mp(mech, game_map):
    return int(jump_speed(mech, game_map) * MP_PER_KPH)


def mechs_elevation(mech):
    from entities.map import BRIDGE
    upper = mech_upper_elevation(mech)
    lower = bridge_w_elevation(mech) if mech_rterrain(mech) == BRIDGE else mech_elevation(mech)
    return mech.z - (upper if upper <= mech.z else lower)


# =============================================================================
# Collision check
# =============================================================================

def collision_check(mech: 'Mech', mode: int, le: int, lt) -> int:
    """
    Check whether entering the current hex collides for the given mode.

    Port of collision_check (mech.update.c:98-152).  `le` is the last
    hex's signed elevation, `lt` its terrain char (the C passes ints; the
    JUMP call site passes 0 for both, mech.update.c:1714).

    Returns an int as the C does: 0/1 for most modes, the elevation
    difference for WALK_BACK.
    """
    from entities.map import ICE, BRIDGE
    from entities.mech import MoveType, UnitType

    # mech.update.c:103-104
    if overwater(mech) and le < 0:
        le = 0
    e = mech_elevation(mech)                          # mech.update.c:105
    if mech_rterrain(mech) == ICE:                    # mech.update.c:106-108
        if le >= 0:
            e = 0
    # mech.update.c:109-114
    if le < (mech_upper_elevation(mech) - move_mod(mech)) and lt == BRIDGE:
        if overwater(mech):
            le = 0
        else:
            le = bridge_w_elevation(mech)
    if e < 0 and overwater(mech):                     # mech.update.c:115-116
        e = 0

    if mode == JUMP:                                  # mech.update.c:118-126
        if mech_rterrain(mech) == BRIDGE:
            if mech.z < 0:
                return 1
            if mech.z == (e - 1):
                return 1
            return 0
        return 1 if mech.z < e else 0

    if mode == WALK_DROP:                             # mech.update.c:127-128
        return 1 if (le - e) > move_mod(mech) else 0

    if mode == WALK_WALL:                             # mech.update.c:129-140
        # MOVE_HOVER on-bridge exception (mech.update.c:131-137).
        if (mech.move_type == MoveType.HOVER
                and mech_rterrain(mech) == BRIDGE
                and (lt in (ICE, WATER) or (le == 0 and lt == BRIDGE))):
            return 0
        return 1 if (e - le) > move_mod(mech) else 0

    if mode in (WALK_BACK, HIT_UNDER_BRIDGE):
        if mode == WALK_BACK:                         # mech.update.c:141-143
            # C checks MechMove != MOVE_TRACK && MechType != CLASS_VTOL.
            if (mech.move_type != MoveType.TRACK
                    and mech.unit_type != UnitType.VTOL):
                return abs(le - e) if mech.speed < 0 else 0
            # C oddity: no break - a tracked/VTOL WALK_BACK query falls
            # through into the HIT_UNDER_BRIDGE case (mech.update.c:141-144).
        # HIT_UNDER_BRIDGE - "Hovers only" per the C comment
        # (mech.update.c:144-150).
        if (lt == BRIDGE and mech_rterrain(mech) == BRIDGE and le == 0
                and mech.map is not None
                and mech.map.base_elevation(mech.last_x, mech.last_y) != 0
                and mech.map.base_elevation(mech.x, mech.y) == 1):
            return 1
        return 0

    return 0                                          # mech.update.c:151


def skid_mod(speed_mp: float) -> int:
    """
    PSR modifier for skid-style cliff checks from speed in MP.

    Port of SkidMod (mech.update.c:1632-1643).
    """
    from core.randomness import float32
    speed_mp = float32(speed_mp)
    if speed_mp < 2.1:
        return -1
    if speed_mp < 4.1:
        return 0
    if speed_mp < 7.1:
        return 1
    if speed_mp < 10.1:
        return 2
    return 4


# =============================================================================
# Stacking (domino) checks
# =============================================================================

def mechs_in_hex(game_map, x: int, y: int, friendly: int, team: int) -> int:
    """
    Count stack-relevant mechs in a hex.

    Port of mechs_in_hex (mech.move.c:1965-1989).  friendly < 0 counts
    everyone; friendly 1/0 counts units whose team-match equals it.
    """
    from entities.mech import UnitType

    cnt = 0
    for other in game_map.mechs_on_map:
        if other is None or other.x != x or other.y != y:
            continue
        if other.is_destroyed:                        # mech.move.c:1974-1975
            continue
        # Non-carrier landed/unstarted DropShips count double
        # (mech.move.c:1976-1980).
        from entities.mech import MechStatus
        if (not (int(getattr(other, 'specials2', 0)) & CARRIER_TECH) and
                other.unit_type in (UnitType.SPHEROID_DS, UnitType.DS) and
                (other.has_status(MechStatus.LANDED) or
                 not other.has_status(MechStatus.STARTED))):
            cnt += 2
            continue
        if other.unit_type != UnitType.MECH:          # mech.move.c:1981-1982
            continue
        if other.is_jumping or getattr(other, "cocoon", 0):                          # mech.move.c:1983-1984
            continue
        if friendly < 0 or ((1 if other.team == team else 0) == friendly):
            cnt += 1
    return cnt


def cause_damage(att: 'Mech', mech: 'Mech', dam: int, table: int) -> None:
    """
    Apply collision damage in 5-point clusters.

    Port of cause_damage (mech.move.c:1995-2036).
    """
    from entities.mech import UnitType
    from systems.combat import (
        HitGroup, determine_hit_group, get_hit_location,
        get_punch_location, get_kick_location, apply_damage_with_transfer,
    )

    if not dam:
        return
    sp = int((dam - 1) / 5)
    if att is mech:                                   # mech.move.c:2004-2005
        hit_group = HitGroup.FRONT
    else:
        hit_group = determine_hit_group(att, mech)
    isrear = (hit_group == HitGroup.BACK)
    if mech.is_fallen:                                # mech.move.c:2009-2010
        table = NORMAL
    # C QUIRK preserved: iscrit starts 0 (mech.move.c:1997) and is only
    # rewritten by the FindHitLocation branches, so on the mech PUNCH/KICK
    # paths it carries its previous value into DamageMech.
    iscrit = False
    hitloc = 0
    for _ in range(sp + 1):
        if table == NORMAL:
            hitloc, iscrit = get_hit_location(mech, hit_group, critical=iscrit)
        elif table == PUNCH:
            if mech.unit_type != UnitType.MECH:       # mech.move.c:2017-2021
                hitloc, iscrit = get_hit_location(mech, hit_group, critical=iscrit)
            else:
                hitloc = get_punch_location(mech, hit_group)
        elif table == KICK:
            if mech.unit_type != UnitType.MECH:       # mech.move.c:2024-2028
                hitloc, iscrit = get_hit_location(mech, hit_group, critical=iscrit)
            else:
                hitloc = get_kick_location(mech, hit_group)
        if dam <= 0:                                  # mech.move.c:2030-2031
            return
        # DamageMech forwards the table's iscrit flag (mech.move.c:2032-2034).
        apply_damage_with_transfer(
            mech, hitloc, 5 if dam > 5 else dam, is_rear=isrear, attacker=att,
            is_critical=bool(iscrit), los=int(att is not mech),
            attack_pilot=-1 if att is mech else att.pilot)
        dam -= 5


def domino_space_in_hex(game_map, me: 'Mech', x: int, y: int, friendly: int,
                        mode: int, cnt: int) -> int:
    """
    Resolve a stacking violation against one mech in the hex.

    Port of domino_space_in_hex (mech.move.c:2038-2155).  mode 1/2 = jump
    landing, anything else = walking bump.
    """
    from entities.mech import MechStatus, UnitType
    from physics.jump import mech_falls
    from systems.piloting import make_piloting_roll

    from core.randomness import draw
    tar = draw('domino_target', 0, cnt - 1, lambda: random.randint(0, cnt - 1))
    team = me.team
    target = None

    for other in game_map.mechs_on_map:               # mech.move.c:2044-2067
        if other is None or other.x != x or other.y != y:
            continue
        if other is me:
            continue
        # Landed/unstarted DropShips take tar -= 2 (mech.move.c:2049-2051;
        # IsDS/DropShip, mech.h:724-725; Landed, btmacros.h:482).
        if (other.unit_type in (UnitType.DS, UnitType.SPHEROID_DS) and
                (other.has_status(MechStatus.LANDED) or
                 not other.has_status(MechStatus.STARTED))):
            tar -= 2
        else:
            if not other.has_status(MechStatus.STARTED):  # mech.move.c:2053-2054
                continue
            if other.unit_type != UnitType.MECH:          # mech.move.c:2055-2056
                continue
            if other.is_jumping or getattr(other, "cocoon", 0):                          # mech.move.c:2057-2058
                continue
            if friendly < 0 or ((1 if other.team == team else 0) == friendly):
                tar -= 1                                  # mech.move.c:2059-2060
            else:
                continue
        if tar <= 0:                                  # mech.move.c:2064-2065
            target = other
            break
    if target is None:                                # mech.move.c:2068-2069
        return 0

    from systems.construction_weight import get_weight
    from physics.movement import btech_config
    mass = int(get_weight(me) / 1024)
    stacking = btech_config(me, "btech_stacking", BTECH_STACKING)
    factor = btech_config(me, "btech_stackdamage", BTECH_STACKDAMAGE)
    # Damage potential (mech.move.c:2079-2098)
    if mode in (1, 2):
        # head = MechJumpHeading(me) (:2082) - unused below, kept for parity
        td = int(jump_speed_mp(me, game_map) * (mass + 5) / 10)
    else:
        head = me.facing + me.lateral                 # mech.move.c:2086
        td = int(math.fabs(
            ((me.speed - target.speed *
              math.cos((head - (target.facing + target.lateral)) *
                       (math.pi / 180.0)))
             * MP_PER_KPH) * (mass + 5) / 15))
    if td > 10:                                       # mech.move.c:2094-2095
        td = 10 + (td - 10) // 3
    if td <= 1:                                       # No point in 1pt hits, :2096-2097
        return 0

    from systems.notifications import mech_printf, identity, pair_los_broadcast
    if mode in (1, 2):
        verb, third = ('land on', 'lands on') if stacking == 2 else ('nearly land on', 'nearly lands on')
    else:
        verb, third = ('bump into', 'bumps into') if stacking == 2 else ('nearly bump into', 'nearly bumps into')
    mech_printf(me, 2, 'You %s %s!', verb, identity(me, target))
    mech_printf(target, 2, '%s %s you!', identity(target, me), third)
    pair_los_broadcast(me, target, third + ' %s!')
    if mode in (1, 2):                                # mech.move.c:2098-2125
        if stacking == 2:

            # IsDS target flips the split to 500/100 (mech.move.c:2108-2115).
            if target.unit_type in (UnitType.DS, UnitType.SPHEROID_DS):
                cause_damage(me, target, max(1, td * factor // 500), PUNCH)
                cause_damage(me, me, max(1, td * factor // 100), KICK)
            else:
                cause_damage(me, target, max(1, td * factor // 100), PUNCH)
                cause_damage(me, me, max(1, td * factor // 500), KICK)
        else:

            if not make_piloting_roll(
                    me, cnt + jump_speed_mp(me, game_map) // 2).success:
                mech_falls(me, 1, notify_fall=bool(jump_speed_mp(me, game_map) // 2))
        return 1

    if stacking == 2:                           # mech.move.c:2127-2140

        # IsDS target flips the split to 500/100 (mech.move.c:2135-2139).
        if target.unit_type in (UnitType.DS, UnitType.SPHEROID_DS):
            cause_damage(me, target, max(1, td * factor // 500), NORMAL)
            cause_damage(me, me, max(1, td * factor // 100), NORMAL)
        else:
            cause_damage(me, target, max(1, td * factor // 100), NORMAL)
            cause_damage(me, me, max(1, td * factor // 500), NORMAL)
    else:                                             # mech.move.c:2141-2150

        if not make_piloting_roll(me, cnt).success:
            mech_falls(me, 1, notify_fall=False)
        me.desired_speed = 0
        me.speed = 0
    # Charge target/timer/distance reset (mech.move.c:2151-2153).
    me.charge_target = -1
    me.charge_timer = 0
    me.charge_distance = 0
    return 1


def domino_space(mech: 'Mech', mode: int) -> int:
    """
    Check the mech's hex for stacking violations and resolve them.

    Port of domino_space (mech.move.c:2157-2180).
    """
    from entities.mech import UnitType

    game_map = mech.map
    if game_map is None:                              # mech.move.c:2162-2163
        return 0
    if mech.unit_type != UnitType.MECH:               # mech.move.c:2164-2165
        return 0
    from physics.movement import btech_config
    if btech_config(mech, "btech_stacking", BTECH_STACKING) == 0:                           # mech.move.c:2166-2167
        return 0
    cnt = mechs_in_hex(game_map, mech.x, mech.y, -1, 0)
    if cnt <= 2:                                      # mech.move.c:2169-2170
        return 0
    fcnt = mechs_in_hex(game_map, mech.x, mech.y, 1, mech.team)
    if fcnt > 2:                                      # mech.move.c:2172-2175
        return domino_space_in_hex(game_map, mech, mech.x, mech.y, 1,
                                   mode, fcnt)
    elif cnt > 6:                                     # mech.move.c:2176-2178
        return domino_space_in_hex(game_map, mech, mech.x, mech.y, 0,
                                   mode, cnt - fcnt)
    return 0


def mech_rterrain(mech: 'Mech') -> str:
    """
    Real terrain of the mech's hex.

    Port of MechRTerrain (btmacros.h:225).
    FIRE/SMOKE resolve through the owning map's timed decoration underlay.
    """
    from entities.map import FIRE, SMOKE
    if mech.terrain in (FIRE, SMOKE):
        from entities.map_objects import mech_underlying_terrain
        return mech_underlying_terrain(mech)
    return mech.terrain


def mech_elevation(mech: 'Mech') -> int:
    """
    Signed elevation of the mech's hex from its cached terrain/elev.

    Port of MechElevation (btmacros.h:48-49):
    BaseElev(MechRTerrain(mech), abs(MechElev(mech))).
    """
    from entities.map import base_elev

    return base_elev(mech_rterrain(mech), abs(mech.elev))


def mech_upper_elevation(mech: 'Mech') -> int:
    """Port of MechUpperElevation (btmacros.h:54): 0 on ICE, else MechElevation."""
    from entities.map import ICE

    if mech_rterrain(mech) == ICE:
        return 0
    return mech_elevation(mech)


def overwater(mech: 'Mech') -> bool:
    """
    Whether the unit travels on top of water.

    Port of Overwater (btmacros.h:677-679): hover/foil/hull movement, plus
    CLASS_MW (btmacros.h:678).
    """
    from entities.mech import MoveType, UnitType

    return (mech.move_type in (MoveType.HOVER, MoveType.FOIL,
                               MoveType.HULL) or
            mech.unit_type == UnitType.MW)


def bridge_w_elevation(mech: 'Mech') -> int:
    """Port of bridge_w_elevation (mech.update.c:67-70): always -1."""
    return -1
