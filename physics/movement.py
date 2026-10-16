# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# Host-derived portions also retain notices/TinyMUX.txt.
# General sources:
#   btech/mech.events.c
#   btech/mech.ice.c
#   btech/mech.move.c
#   btech/mech.update.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/mech.h
#   btech/src/include/btconfig.h
#   src/conf.c
# Historical Aerospace sources:
#   btech/aero.move.c
#   btech/mech.update.c
#   src/hcode/btech/btmacros.h
#   src/hcode/btech/mech.h
#   src/hcode/include/btconfig.h

"""
Movement system for BTMux Python reimplementation.

This module handles mech movement including:
- Heading updates (turning toward desired facing)
- Speed updates (acceleration/deceleration)
- Position updates (moving based on speed and heading)
- Hex crossing detection

Reference:
- BTMux btech/src/btech/mech.update.c - move_mech(), UpdateHeading(), UpdateSpeed()
- BTMux btech/src/include/btconfig.h - timing constants
- BTMux btech/src/btech/mech.h - movement constants

Key mechanics:
- Movement updates every MOVE_TICK (1 second)
- Speed is in KPH, position is in SCALEMAP units
- MOVE_MOD (0.5) scales speed to position delta per tick
- Heading change rate depends on speed and unit type
"""

from __future__ import annotations
from core.randomness import draw, float32
import math
import random
from typing import TYPE_CHECKING, Optional, Callable

from physics.hexmath import (
    find_components, float_to_hex, normalize_heading,
    heading_difference, turn_direction, SCALEMAP, ZSCALE
)

if TYPE_CHECKING:
    from entities.mech import Mech
    from core.game_loop import GameEngine
    from core.events import Event

# =============================================================================
# Movement Constants (from BTMux btconfig.h and mech.h)
# =============================================================================

# Timing
MOVE_TICK = 1           # Movement updates every tick
MOVE_MOD = 0.5          # Speed to position multiplier per tick

# Speed constants
MP1 = 10.75             # 1 Movement Point in KPH
MP2 = 21.5              # 2 MP
MP3 = 32.25             # 3 MP
MP4 = 43.0              # 4 MP
MP5 = 53.75             # 5 MP
KPH_PER_MP = 10.75      # KPH per movement point

# Pilot preference bit: jump off cliffs without trying to avoid (mech.h:748).
MECHPREF_AUTOFALL = 0x00000004

# Turn rate constants
# Base turn rate is roughly: degrees per tick = f(speed, max_speed)
# At standstill: 3 * maxspeed * MP_PER_KPH degrees per tick
# While moving: 2 * maxspeed * MP_PER_KPH degrees per tick
# While running: further reduced by (3 * speed / maxspeed - 2)
MP_PER_KPH = 0.0930233  # 1/KPH_PER_MP

WATERPROOF_TECH = 0x100000                 # mech.h:1187

# Message hook, same pattern as systems.missile.NOTIFY_HOOK.
NOTIFY_HOOK = None


def _notify(mech, message, audience=2):
    if audience is not None:
        from systems.notifications import mech_notify
        mech_notify(mech, audience, message)
    elif NOTIFY_HOOK is not None:
        NOTIFY_HOOK(mech, message)


# Acceleration
# Bipeds: maxspeed / 20 per tick
# Quads: maxspeed / 10 per tick
BIPED_ACCEL_DIVISOR = 20.0
QUAD_ACCEL_DIVISOR = 10.0

# Speed demon advantage multiplier (not used initially, but noted)
SPEED_DEMON_MULT = 1.25

# Charge trigger constants (btconfig.h:175-176)
CHARGE_TIMER_LIMIT = 60     # Ticks before a charge times out (btconfig.h:175)
CHARGE_DIST_TRIGGER = 0.6   # Hex range that triggers the charge (btconfig.h:176)


def btech_config(mech: 'Mech', name: str, default):
    """
    Read a btech config knob with its C default (src/conf.c:91-143).

    The engine (attached as ``mech.engine`` where one exists) or, for
    tests, the mech's map may carry an override attribute; otherwise the
    C default applies.  Defaults per src/conf.c:91-143: btech_slowdown=2,
    btech_newcharge=0, btech_tl3_charge=0, btech_fasaturn=1.
    """
    owner=getattr(mech,'_engine',None)
    if owner is not None and hasattr(owner,name.removeprefix('btech_')):
        return getattr(owner,name.removeprefix('btech_'))
    for source in (owner,getattr(mech, 'engine', None), mech.map):
        if source is not None:
            value = getattr(source, name, None)
            if value is not None:
                return value
    return default


# =============================================================================
# Heading Update
# =============================================================================

def _heading_max_speed(mech):
    from physics.cargo import cargo_max_speed
    from entities.mech import Specials, UnitType
    speed = float32(cargo_max_speed(mech))
    if mech.unit_type in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS):
        speed = float32(speed * 5)
    if mech.heat >= 9 and mech.specials & Specials.TRIPLE_MYOMER_TECH:
        speed = float32(speed + 1.5 * MP1)
    return speed


def calculate_turn_rate(mech: 'Mech', max_speed: float) -> float:
    """Source turn offset, including integer truncation in 1/32 degrees."""
    from entities.mech import MoveType, UnitType, MechStatus2
    from systems.characters import actor_advantage
    from physics.jump import get_jump_mp
    max_speed = float32(max_speed)
    original_max = max_speed
    speed = float32(mech.speed)
    normangle = mech.facing * 32 + mech.facing_fraction - mech.desired_facing * 32
    mw_mod = 60 if mech.unit_type in (UnitType.MW, UnitType.BSUIT) else 2 if mech.move_type == MoveType.QUAD else 1
    if btech_config(mech, 'btech_fasaturn', 1):
        if mech.is_jumping:
            offset = 1152
        else:
            if speed < 0:
                max_speed = float32(max_speed * 2.0 / 3.0)
                speed = -speed
            if speed > max_speed or max_speed < .1:
                offset = 0
            else:
                product = float32(576 * float32(max_speed - speed))
                product = float32(product * float32(original_max / max_speed))
                offset = int(float32(product * mw_mod) * MP_PER_KPH / 6)
    elif mech.is_jumping:
        offset = 32 * 6 * get_jump_mp(mech) * mw_mod
    elif abs(speed) < 1:
        offset = int(float32(32 * 3 * max_speed) * MP_PER_KPH * mw_mod)
    else:
        offset = int(float32(32 * 2 * max_speed) * MP_PER_KPH * mw_mod)
        if abs(normangle) * 32 > offset and speed > float32(2 * max_speed) / 3.0 + .1:
            if speed > max_speed:
                offset = int(offset - float32(float32(int(offset / 2) * max_speed) / speed))
            else:
                offset = int(offset - int(offset / 2) * (3.0 * speed / max_speed - 2.0))
    offset = int(offset * MOVE_MOD)
    ace = actor_advantage(mech.pilot, 'Maneuvering_Ace')
    if getattr(mech, 'turn_mode', False) and ace:
        offset = int(offset * 3 / 2)
    if mech.has_status2(MechStatus2.SPRINTING | MechStatus2.EVADING) and not ace:
        offset = int(offset * 2 / 3) if actor_advantage(mech.pilot, 'Speed_Demon') else int(offset / 2)
    if mech.unit_type in (UnitType.DS, UnitType.SPHEROID_DS):
        offset = min(offset, 10 * 32)
    return offset / 32.0


def update_heading(mech: 'Mech') -> bool:
    """Retain fractional facing and the profile-specific source wrap behavior."""
    from entities.mech import CritStatus, UnitType
    from systems.ecm import mark_for_los_update
    if mech.facing == mech.desired_facing:
        return False
    offset = int(calculate_turn_rate(mech, _heading_max_speed(mech)) * 32)
    previous = mech.facing * 32 + mech.facing_fraction
    real = previous
    normangle = real - mech.desired_facing * 32
    if normangle < 0:
        normangle += 360 * 32
    if normangle > 180 * 32:
        real += offset
        if real >> 5 >= 360:
            if mech.unit_type in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS):
                real -= 360 * 32
            else:
                # Checked-in general source passes integer Facing to SetRFacing.
                real = (real >> 5) % 360
        if normangle + offset >= 360 * 32:
            real = mech.desired_facing * 32
    else:
        real -= offset
        if real < 0:
            real += 360 * 32
        if normangle - offset < 0:
            real = mech.desired_facing * 32
    mech.facing = real >> 5
    mech.facing_fraction = real & 31
    mech.set_crit_status(CritStatus.CHEAD)
    mark_for_los_update(mech)
    return real != previous


# =============================================================================
# Speed Update
# =============================================================================

def calculate_effective_max_speed(mech: 'Mech') -> float:
    """
    Calculate effective maximum speed accounting for damage, heat, etc.

    Reference: UpdateSpeed() calculations and MMaxSpeed() macro

    Args:
        mech: The mech to calculate for

    Returns:
        Effective maximum speed in KPH
    """
    from physics.cargo import cargo_max_speed
    return cargo_max_speed(mech)


def calculate_heat_speed_reduction(heat: float, max_speed: float) -> float:
    """DECREASE_HEAT: rounded walking MP, then ceiling of running MP."""
    if heat < 5:
        return 1.0
    penalty = min(5, int(heat / 5))
    if max_speed == 0:
        return 0.0
    return math.ceil((round((max_speed / 1.5) / MP1) - penalty) * 1.5) * MP1 / max_speed


def terrain_speed(mech: 'Mech', tempspeed: float, maxspeed: float,
                  terrain: str, elev: int) -> float:
    """
    Modulate target speed by the terrain the mech is standing in.

    Port of terrain_speed (mech.update.c:937-981), using the DECREASE_NEW
    family of macros the C compiles with (mech.update.c:927-933):
      DECREASE(s):     tempspeed *= MP1 / (MP1 + s)
      INCREASE_OLD(s): tempspeed *= (maxspeed + s) / maxspeed
    `terrain` is the real terrain char, `elev` the signed hex elevation.

    Kept 1:1, including the C's fallthrough chain: ROAD/BRIDGE fall into
    the ICE case (mech.update.c:958-967), and ICE below the surface falls
    into WATER (mech.update.c:967-971).
    """
    from entities.map import (
        SNOW, ROUGH, MOUNTAINS, LIGHT_FOREST, HEAVY_FOREST,
        BRIDGE, ROAD, ICE, WATER,
    )
    from entities.mech import MoveType, UnitType

    tempspeed, maxspeed = float32(tempspeed), float32(maxspeed)
    if terrain in (SNOW, ROUGH):                      # mech.update.c:940-943
        tempspeed = float32(tempspeed * (MP1 / (MP1 + MP1)))
    elif terrain == MOUNTAINS:                        # mech.update.c:944-946
        tempspeed = float32(tempspeed * (MP1 / (MP1 + MP2)))
    elif terrain == LIGHT_FOREST:                     # mech.update.c:947-950
        if mech.unit_type != UnitType.BSUIT:          # mech.update.c:948
            tempspeed = float32(tempspeed * (MP1 / (MP1 + MP1)))
    elif terrain == HEAVY_FOREST:                     # mech.update.c:951-954
        if mech.unit_type != UnitType.BSUIT:          # mech.update.c:952
            tempspeed = float32(tempspeed * (MP1 / (MP1 + MP2)))
    elif terrain in (BRIDGE, ROAD, ICE, WATER):
        if terrain in (BRIDGE, ROAD):                 # mech.update.c:955-965
            # Ground units (wheeled and tracked) get +1 MP on pavement.
            from entities.mech import MechStatus2
            if mech.move_type in (MoveType.TRACK, MoveType.WHEEL) and not mech.has_status2(MechStatus2.SPRINTING):
                tempspeed = float32(tempspeed * ((maxspeed + MP1) / maxspeed))  # INCREASE_OLD(MP1)
            # C oddity: no break - ROAD/BRIDGE fall through into the ICE
            # check (mech.update.c:966).
        if terrain in (BRIDGE, ROAD, ICE):            # mech.update.c:966-968
            if mech.z >= 0:
                return tempspeed
            # under the ice/bridge: treat as water (mech.update.c:969-971)
        # WATER case (mech.update.c:972-979)
        if mech.move_type in (MoveType.BIPED, MoveType.QUAD):
            if elev <= -2:
                tempspeed = float32(tempspeed * (MP1 / (MP1 + MP3)))        # DECREASE(MP3)
            elif elev == -1:
                tempspeed = float32(tempspeed * (MP1 / (MP1 + MP1)))        # DECREASE(MP1)
    return tempspeed


def update_speed(mech: 'Mech') -> bool:
    """Source acceleration, ordered heat/terrain/turn/lateral modifiers and tow tail."""
    from entities.mech import MechStatus, MechStatus2, MoveType, CritStatus, Specials, UnitType
    from systems.characters import actor_advantage
    from physics.collision import mech_rterrain, mech_elevation
    from systems.targeting import resolve_unit
    if mech.is_fallen or mech.is_jumping or mech.max_speed <= 0:
        return False
    target = float32(abs(mech.desired_speed))
    maximum = max(0.0, float32(calculate_effective_max_speed(mech)))
    masc = mech.has_status(MechStatus.MASC_ENABLED)
    supercharger = mech.has_status(MechStatus.SCHARGE_ENABLED)
    if masc and supercharger:
        maximum = float32(math.ceil(round(maximum / 1.5) / MP1 * 2.5) * MP1)
    elif masc or supercharger:
        maximum = float32(4.0 / 3.0 * maximum)
    tsm = bool(mech.specials & Specials.TRIPLE_MYOMER_TECH)
    if tsm:
        if mech.heat >= 9:
            maximum = float32(math.ceil((round(calculate_effective_max_speed(mech) / 1.5 / MP1) + 1) * 1.5) * MP1)
        if mech.desired_speed >= maximum:
            mech.desired_speed = maximum
    if mech.heat >= 5 and not (tsm and 9 <= mech.heat < 10):
        target = float32(target * calculate_heat_speed_reduction(mech.heat, maximum))
    if mech.unit_type != UnitType.MW and mech.move_type != MoveType.VTOL and (mech.move_type != MoveType.FLY or mech.has_status(MechStatus.LANDED)):
        target = terrain_speed(mech, target, maximum, mech_rterrain(mech), mech_elevation(mech))
    ace = actor_advantage(mech.pilot, 'Maneuvering_Ace')
    demon = actor_advantage(mech.pilot, 'Speed_Demon')
    if mech.has_crit_status(CritStatus.CHEAD):
        slowdown = btech_config(mech, 'btech_slowdown', 2)
        if slowdown == 2:
            difference = abs(mech.facing - mech.desired_facing)
            if difference > 180:
                difference = 360 - difference
            if difference:
                band = (difference - 1) // 30 + 2
                product = float32(target * (10 - band))
                target = float32(float32(product / 10) - MP1 * .4) if getattr(mech, 'turn_mode', False) else float32(product / 10)
        elif slowdown == 1:
            target = float32(target * (2.0 / 3.0 if mech.facing != mech.desired_facing else 3.0 / 4.0))
        if mech.has_status2(MechStatus2.SPRINTING | MechStatus2.EVADING) and not (demon or ace):
            target = float32(float32(target * 2) / 3)
        mech.clear_crit_status(CritStatus.CHEAD)
    if mech.lateral:
        penalty = MP1 if mech.move_type == MoveType.QUAD else MP2 if ace else MP3
        target = float32(target * ((maximum - penalty) / maximum)) if maximum else 0.0
    target = max(0.0, target)
    if mech.desired_speed < 0:
        target = -target
    previous = mech.speed
    if target != previous:
        acceleration = float32(maximum / (10.0 if mech.move_type == MoveType.QUAD else 20.0))
        if demon:
            acceleration = float32(acceleration * 1.25)
        mech.speed = max(target, float32(previous - acceleration)) if target < previous else min(target, float32(previous + acceleration))
    if mech.carrying > 0:
        carried = resolve_unit(mech, mech.carrying)
        if carried is not None:
            carried.speed = mech.speed
    return mech.speed != previous


# =============================================================================
# Position Update
# =============================================================================

def map_move_mod(mech: 'Mech') -> float:
    """
    Map movement modifier factor.

    Port of MAPMOVEMOD (btmacros.h:727):
    ``(map)->movemod > 0 ? (float) (map)->movemod / 100.0 : 1.0``.
    Factor is 1.0 when the mech has no map, so mapless movement is
    unchanged.
    """
    game_map = mech.map
    if game_map is None:
        return 1.0
    return game_map.movemod / 100.0 if game_map.movemod > 0 else 1.0


def _invalid_movement(mech, *, coordinates=False, transitioned=False):
    from core.effects import send_error, notify_actor
    from systems.movement_commands import land
    from systems.startup import shutdown
    if transitioned:
        send_error(mech, 'Invalide pointer (mech_map) in move_mech()')
    _notify(mech, 'You are at an invalid map location! Map index reset!' if coordinates else 'You are on an invalid map! Map index reset!')
    mech.cocoon = 0
    if mech.is_jumping:
        ok, message = land(mech._engine, mech, caller=mech.pilot)
        if not ok and message and not getattr(message, 'notified', False): notify_actor(mech, mech.pilot, message)
    ok, message = shutdown(mech._engine, mech, caller=mech.pilot)
    if not ok and message and not getattr(message, 'notified', False): notify_actor(mech, mech.pilot, message)
    send_error(mech, f'move_mech:invalid map:Mech: {mech._id} Index: {mech.mapindex}')
    mech.mapindex = -1


def move_mech(mech):
    """The complete shared movement body, also used by JUMP and aircraft events."""
    from entities.mech import MoveType as M, MechStatus as S
    from entities.map import BRIDGE, ICE
    from systems.targeting import indexed_map, valid_map, map_record
    from systems.ecm import mark_for_los_update
    from systems.map_transitions import check_edge_of_map
    from physics.collision import jump_speed, jump_speed_mp, collision_check, mech_rterrain, JUMP
    from physics.jump import land_mech, mech_falls
    from physics.hexmath import hex_to_float
    from systems.sensors import los_broadcast
    board = indexed_map(mech)
    if board is None and mech.pilot is not None and (mech.pilot if isinstance(mech.pilot, int) else getattr(mech.pilot, '_id', 1)) >= 0:
        board, _ = valid_map(map_record(mech, mech.mapindex), mech.pilot)
    if board is None:
        _invalid_movement(mech)
        return False
    mech.map = board
    if not board.valid(mech.x, mech.y) or not board.valid(mech.last_x, mech.last_y):
        _invalid_movement(mech, coordinates=True)
        return False
    if btech_config(mech, 'btech_newcharge', 0) and mech.charge_target > 0:
        old_timer = mech.charge_timer
        mech.charge_timer += 1
        if old_timer > CHARGE_TIMER_LIMIT:
            _notify(mech, 'Charge timed out, charge reset.')
            reset_charge(mech)
    oz = mech.z
    dx = dy = 0.0
    upd_z = False
    ground = mech.move_type in (M.BIPED, M.QUAD, M.TRACK, M.WHEEL, M.HOVER)
    if mech.move_type in (M.BIPED, M.QUAD) and mech.is_jumping:
        mark_for_los_update(mech)
        dx, dy = find_components(jump_speed(mech, board) * MOVE_MOD * map_move_mod(mech), mech.jump_heading)
        mech.fx, mech.fy = float32(mech.fx + dx), float32(mech.fy + dy)
        progress = float32(math.hypot(float32(mech.fx - mech.start_fx), float32(mech.fy - mech.start_fy)))
        length = mech.jump_length
        remaining = max(0.0, float32(length - progress))
        middle = float32(progress / length) if length else 0.0
        middle = float32((middle - .5) * 2)
        power = float32(middle * middle)
        if mech.jump_top < 1 + jump_speed_mp(mech, board):
            power = float32(float32(power * middle) * middle)
        middle = float32((1.0 - power) * mech.jump_top)
        linear = float32(float32(float32(remaining * mech.start_fz) + float32(progress * mech.end_fz)) / length) if length else mech.end_fz
        mech.fz = float32(linear + middle * ZSCALE)
        mech.z = int(mech.fz / ZSCALE + .5)
        if mech_rterrain(mech) == BRIDGE and collision_check(mech, JUMP, 0, 0) and mech.z > 0:
            _notify(mech, 'CRASH! You crash into the bridge!')
            los_broadcast(mech, 'crashes into the bridge!')
            mech_falls(mech, 1, notify_fall=False)
            return True
        if (mech.x, mech.y) == (mech.going_x, mech.going_y):
            cx, cy = hex_to_float(mech.x, mech.y)
            if math.hypot(float32(cx - mech.start_fx), float32(cy - mech.start_fy)) <= math.hypot(float32(mech.fx - mech.start_fx), float32(mech.fy - mech.start_fy)):
                land_mech(mech)
                mech.fx, mech.fy = float32(cx), float32(cy)
        if mech_rterrain(mech) == ICE:
            if oz < -1 and mech.z >= -1: break_thru_ice(mech)
            elif oz >= -1 and mech.z < -1: drop_thru_ice(mech)
    elif ground:
        if not abs(mech.speed) > 0.0: return False
        dx, dy = find_components(mech.speed * MOVE_MOD * map_move_mod(mech), mech.facing + mech.lateral)
        mech.fx, mech.fy = float32(mech.fx + dx), float32(mech.fy + dy)
        upd_z = True
        if mech.charge_target > 0 and btech_config(mech, 'btech_newcharge', 0):
            scale = float32(1.0 / SCALEMAP)
            scale = float32(scale * scale)
            distance = float32(math.sqrt(float32(float32(scale * dx) * dx) + 9.61482e-6 * dy * dy))
            mech.charge_distance = float32(mech.charge_distance + distance)
    elif mech.move_type in (M.VTOL, M.SUB):
        if mech.move_type == M.VTOL and mech.has_status(S.LANDED): return False
        mark_for_los_update(mech)
        dx, dy = find_components(mech.speed * MOVE_MOD * map_move_mod(mech), mech.facing)
        mech.fx, mech.fy = float32(mech.fx + dx), float32(mech.fy + dy)
        mech.fz = float32(mech.fz + mech.vertical_speed * MOVE_MOD)
        mech.z = int(mech.fz / ZSCALE)
    elif mech.move_type == M.FLY and not mech.has_status(S.LANDED):
        from physics.aerospace import descent
        mark_for_los_update(mech)
        mech.fz = float32(mech.fz + mech.start_fz * MOVE_MOD)
        mech.z = int(mech.fz / ZSCALE)
        mech.fx = float32(mech.fx + mech.start_fx * MOVE_MOD)
        mech.fy = float32(mech.fy + mech.start_fy * MOVE_MOD)
        descent(mech, oz)
    elif mech.move_type in (M.FLY, M.HULL, M.FOIL):
        if not abs(mech.speed) > 0.0: return False
        dx, dy = find_components(mech.speed * MOVE_MOD * map_move_mod(mech), mech.facing)
        mech.fx, mech.fy = float32(mech.fx + dx), float32(mech.fy + dy)
        if mech.move_type == M.FLY: upd_z = True
        else: mech.z = mech.fz = 0
    mech.last_x, mech.last_y = mech.x, mech.y
    last_z = mech.z
    mech.x, mech.y = float_to_hex(mech.fx, mech.fy)
    if (mech.is_jumping and (mech.last_x, mech.last_y) == (mech.going_x, mech.going_y) and
            (mech.x, mech.y) != (mech.last_x, mech.last_y)):
        land_mech(mech)
        mech.fx, mech.fy = float32(mech.fx - dx), float32(mech.fy - dy)
        mech.fz = mech.end_fz
        mech.x, mech.y = mech.going_x, mech.going_y
        mech.fx, mech.fy = hex_to_float(mech.x, mech.y)
        mech.z = int(mech.fz / ZSCALE)
    previous_map = mech.mapindex
    check_edge_of_map(mech)
    if previous_map != mech.mapindex:
        board = indexed_map(mech)
        mech.map = board
    if previous_map != mech.mapindex or check_hex_crossing(mech):
        if board is None:
            _invalid_movement(mech, transitioned=True)
            return True
        on_hex_entered(mech, mech.last_x, mech.last_y, dx, dy, last_z, upd_z=upd_z, previous_z=oz)
    from physics.heights import maintain_height, fiery_death
    maintain_height(mech, oz)
    if mech.charge_target != -1:
        update_charge(mech, 0)
    from systems.towing import follow_tower
    from systems.swarm import mirror_all
    follow_tower(mech)
    mirror_all(mech)
    fiery_death(mech)
    return True


# =============================================================================
# Hex Crossing Detection
# =============================================================================

def check_hex_crossing(mech: 'Mech') -> bool:
    """
    Check if the mech has entered a new hex.

    This is called after move_mech() to detect hex boundary crossings.
    When a mech enters a new hex, various things happen:
    - Terrain effects apply
    - Hex counter increments
    - Combat checks (charges, etc.)

    Reference: The hex crossing logic in move_mech()

    Args:
        mech: The mech to check

    Returns:
        True if mech entered a new hex, False otherwise
    """
    return mech.x != mech.last_x or mech.y != mech.last_y


def bridge_set_elevation(mech: 'Mech') -> None:
    """
    Set Z for a unit standing in a BRIDGE hex.

    Port of bridge_set_elevation (mech.update.c:71-82).
    """
    from physics.collision import move_mod
    from physics.collision import mech_upper_elevation, overwater, bridge_w_elevation

    if mech.z < (mech_upper_elevation(mech) - move_mod(mech)):
        if overwater(mech):
            mech.z = 0
        else:
            mech.z = bridge_w_elevation(mech)
        return
    mech.z = mech_upper_elevation(mech)


def drop_get_elevation(mech: 'Mech') -> int:
    """
    Ground elevation the unit settles at in its current hex.

    Port of DropGetElevation (mech.move.c:1547-1561).
    """
    from entities.map import BRIDGE, ICE
    from physics.collision import mech_rterrain, mech_elevation, overwater, bridge_w_elevation

    if mech_rterrain(mech) == BRIDGE:
        if mech.z < mech.elev:
            if overwater(mech):
                return 0
            return bridge_w_elevation(mech)
        return mech_elevation(mech)
    if overwater(mech) or (mech_rterrain(mech) == ICE and mech.z >= 0):
        return max(0, mech_elevation(mech))
    return mech_elevation(mech)


def drop_set_elevation(mech: 'Mech', wantdrop: int) -> None:
    """
    Snap the unit's Z to its hex's ground elevation.

    Port of DropSetElevation (mech.move.c:1563-1575).
    """
    from entities.map import BRIDGE, ICE
    from physics.collision import mech_rterrain

    if mech_rterrain(mech) == BRIDGE:
        bridge_set_elevation(mech)
        return
    mech.z = drop_get_elevation(mech)
    mech.fz = float32(mech.z * ZSCALE)
    if wantdrop:
        if mech_rterrain(mech) == ICE and mech.z >= 0:
            possibly_drop_thru_ice(mech)


def break_thru_ice(mech: 'Mech') -> None:
    """
    Surface through ice from below (down -> up).

    Port of break_thru_ice (mech.ice.c:91-101).
    Shared map mutation and other occupants are handled by break_surface.
    """
    from entities.map import WATER
    from systems.ecm import mark_for_los_update

    from physics.ice import break_surface
    from systems.sensors import los_broadcast
    mark_for_los_update(mech)
    _notify(mech, "You break through the ice!")
    los_broadcast(mech, "breaks through the ice!")
    if mech.map is not None:
        break_surface(mech.map, mech, mech.x, mech.y)
    mech.terrain = WATER                              # mech.ice.c:99


def drop_thru_ice(mech: 'Mech') -> None:
    """
    Fall through ice from above (up -> down).

    Port of drop_thru_ice (mech.ice.c:64-88).
    Shared map mutation and other occupants are handled by break_surface.
    """
    from entities.map import WATER
    from entities.mech import MechStatus, MoveType, UnitType
    from physics.jump import mech_falls

    from physics.ice import break_surface
    from systems.sensors import los_broadcast
    _notify(mech, "You break the ice!")
    los_broadcast(mech, "breaks the ice!")
    if mech.move_type != MoveType.FOIL and mech.elev > 0:
        los_broadcast(mech, "vanishes into the waters!")
    if mech.map is not None:
        break_surface(mech.map, mech, mech.x, mech.y)
    mech.terrain = WATER                              # mech.ice.c:76
    if mech.move_type != MoveType.FOIL:               # mech.ice.c:77-80
        if mech.elev > 0:
            mech_falls(mech, mech.elev, notify_fall=False)  # MechFalls(mech, MechElev, 0)
    # Ground-vehicle flooding destruction (mech.ice.c:81-88).
    if (mech.elev > 0 and mech.unit_type == UnitType.VEH_GROUND and
            not mech.has_status(MechStatus.DESTROYED) and
            not (int(getattr(mech, 'specials2', 0)) & WATERPROOF_TECH)):
        _notify(mech, "Water renders your vehicle inoperable.")
        los_broadcast(mech, "fizzles and pops as water renders it inoperable.")
        from systems.damage import destroy_mech, KILL_TYPE_ICE
        destroy_mech(mech, mech, showboom=False, reason=KILL_TYPE_ICE)


def possibly_drop_thru_ice(mech: 'Mech') -> int:
    """
    Chance of dropping through the ice based on a 1-in-6 roll.

    Port of possibly_drop_thru_ice (mech.ice.c:103-112).
    """
    from entities.mech import MoveType, UnitType

    if (mech.move_type in (MoveType.HOVER, MoveType.SUB) or
            mech.unit_type == UnitType.BSUIT):        # mech.ice.c:105-107
        return 0
    if draw('ice_d6', 1, 6, lambda: random.randint(1, 6)) != 1:                     # Number(1, 6) != 1, :108
        return 0
    drop_thru_ice(mech)
    return 1


def move_unit_back(mech: 'Mech', deltax: float, deltay: float,
                   lastelevation: int, ot: str, le: int) -> None:
    """
    Move the unit back to its previous location (cliff or similar).

    Port of move_unit_back (mech.update.c:1648-1661).  Note the C oddity:
    the signed last elevation `le` is written into the unsigned MechElev
    cache verbatim (mech.update.c:1659).
    """
    mech.fx = float32(float32(mech.fx) - float32(deltax))
    mech.fy = float32(float32(mech.fy) - float32(deltay))
    mech.x = mech.last_x
    mech.y = mech.last_y
    mech.z = (int(lastelevation) + 32768) % 65536 - 32768
    mech.fz = float32(mech.z * ZSCALE)
    mech.terrain = ot
    mech.elev = int(le) % 256


def new_hex_entered(mech, deltax, deltay, last_z):
    """NewHexEntered, preserving each movement class's early returns."""
    from entities.map import WATER, ICE, BRIDGE, HIGHWATER, FIRE, LIGHT_FOREST, HEAVY_FOREST, ROUGH, ROAD, GRASSLAND, BUILDING
    from entities.mech import MoveType as M, UnitType as U, MechStatus as S, MechStatus2 as S2
    from physics.collision import collision_check, skid_mod, domino_space, JUMP, WALK_WALL, WALK_DROP, WALK_BACK, HIT_UNDER_BRIDGE, mech_rterrain, mech_elevation, bridge_w_elevation
    from physics.jump import mech_falls, land_mech
    from physics.flooding import flood_unit
    from systems.piloting import make_piloting_roll, valid_pilot
    from systems.sensors import los_broadcast
    from systems.notifications import mech_printf
    from systems.ecm import mark_for_los_update
    from systems.damage import destroy_mech, KILL_TYPE_FLOOD
    board = mech.map
    if board is None:
        return
    aero = mech.unit_type in (U.AERO, U.DS, U.SPHEROID_DS)
    ot = board.terrain(mech.last_x, mech.last_y)
    if mech.move_type == M.HOVER and (ot in (WATER, ICE) or ot == BRIDGE and last_z == 0):
        le = old = elevation = 0
    else:
        le = old = board.base_elevation(mech.last_x, mech.last_y)
        elevation = mech_elevation(mech)
        if mech.move_type == M.HOVER:
            elevation = max(0, elevation)
        if ot == ICE and mech.z >= 0:
            le = old = 0
        if aero:
            le = min(le, mech.z)
    done = False
    skid = btech_config(mech, 'btech_skidcliff', 0)
    reverse = btech_config(mech, 'btech_roll_on_backwalk', 1)
    absent = mech.pilot is None or getattr(mech.pilot, '_id', mech.pilot) == -1
    walking = mech.move_type in (M.BIPED, M.QUAD)
    def back(): move_unit_back(mech, deltax, deltay, old, ot, le)
    def stop(): mech.speed = mech.desired_speed = 0
    def say(local, remote=None, audience=2):
        _notify(mech, local, audience)
        if remote: los_broadcast(mech, remote)
    def roll(mod, noxp=False):
        return make_piloting_roll(mech, int(mod), award_xp=not noxp, succeed_when_fallen=True).success
    def avoid(): return skid_mod(abs(mech.speed) / MP1) if skid else int(abs(mech.speed + MP1) / MP1 / 3)
    def fall(n, show=False): mech_falls(mech, int(n), notify_fall=show)
    def reverse_collision(extra=0):
        if not (reverse and mech.speed < 0 and collision_check(mech, WALK_BACK, old, ot)):
            return False
        up = elevation > old
        mech_printf(mech, 2, 'You notice a %s behind you!', 'small incline' if up else 'small drop')
        if absent or roll(collision_check(mech, WALK_BACK, old, ot) - 1):
            say('You manage to overcome the obstacle.')
        else:
            mech_printf(mech, 2, '%s', 'You stumble on your rear and fall down.' if up else 'You fall on your rear off the small incline.')
            los_broadcast(mech, ("falls on it's back walking up an incline." if aero else 'falls on its back walking up an incline.') if up else 'falls off the back of a small incline.')
            fall(abs(old - elevation) + extra, True)
            stop()
            if up: back()
        return True
    def slow(one, many):
        delta = abs(elevation - old)
        if walking and mech.z != elevation: delta = 0
        if delta:
            cost = one if delta == 1 else many
            mech.speed = max(0, float32(mech.speed - cost)) if mech.speed > 0 else min(0, float32(mech.speed + cost))
        return delta
    def water_edge(suit=False):
        if (int(mech.specials2) & WATERPROOF_TECH or elevation >= 0 or
                not (mech_rterrain(mech) == WATER or mech_rterrain(mech) == BRIDGE and old < elevation - 1)):
            return False
        say('You notice a body of water in front of you')
        if absent or roll(int(abs(mech.speed + MP1) / MP1) / 3):
            say('You manage to stop before falling in.', 'stops suddenly to avoid going for a swim!' if suit else ('stops suddenly to driving into the water!' if mech.move_type == M.WHEEL else 'stops suddenly to avoid driving into the water!'))
        else:
            if suit:
                say('You trip at the edge of the water and plunge in...')
                flood_unit(mech)
            else:
                say('You drive into the water and your vehicle becomes inoperable.')
                destroy_mech(mech, mech, showboom=False, reason=KILL_TYPE_FLOOD)
            return True
        back()
        stop()
        return True
    def trees(heavy_penalty=True, rough=False):
        terrain = mech_rterrain(mech)
        if abs(mech.speed) <= MP1: return
        rock = rough and terrain == ROUGH
        forest = terrain in (LIGHT_FOREST, HEAVY_FOREST) if heavy_penalty else terrain == HEAVY_FOREST
        if not (forest or rock): return
        say('You try to avoid the rocks..' if rock else 'You try to dodge the larger trees..')
        modifier = abs(mech.speed) / MP1 / 6 + (3 if heavy_penalty and terrain == HEAVY_FOREST else 0)
        if absent or roll(modifier):
            say("You manage to dodge 'em!")
        else:
            say("You swerve, but not enough! This'll hurt!", 'cruises headlong at a rock!' if rock else 'cruises headlong at a tree!')
            speed = float32(abs(mech.speed))
            mech.speed = float32(mech.speed / 2)
            fall(max(1, int(math.sqrt(speed / MP1 / 2))))
    if walking and mech.is_jumping:
        if mech_rterrain(mech) == WATER: return
        if collision_check(mech, JUMP, 0, 0):
            ed = max(1, 1 + mech.z - board.base_elevation(mech.x, mech.y))
            back()
            say('%chYou attempt to jump over elevation that is too high!%c')
            if valid_pilot(mech) and roll(int(mech.fz) / ZSCALE / 3):
                say('%chYou land safely.%c')
                land_mech(mech)
            else:
                say('%chYou crash into the obstacle and fall from the sky!%c', 'crashes into an obstacle and falls from the sky!')
                fall(ed)
                domino_space(mech, 2)
        return
    if walking or mech.move_type in (M.TRACK, M.WHEEL, M.HOVER):
        if collision_check(mech, WALK_WALL, old, ot):
            if walking: back()
            elif mech.move_type == M.HOVER: mech.elev, mech.terrain = le % 256, ot
            say('You attempt to climb a hill too steep for you.')
            if absent or roll(avoid(), True):
                say('You manage to stop before crashing.', 'stops suddenly to avoid a cliff!')
            elif walking:
                say('You run headlong into the cliff and fall down!', 'runs headlong into a cliff and falls down!')
                fall(1 if skid else int(int(1 + mech.speed * MP_PER_KPH) / 4))
            elif skid:
                say('You skid to a violent halt!', 'goes into a skid!' if mech.move_type == M.TRACK else 'skids to a halt!')
                fall(0)
            else:
                say('You smash into a cliff!', 'smashes into a cliff!' if mech.move_type == M.HOVER else 'crashes to a cliff!')
                fall(mech.speed * MP_PER_KPH / 4)
            if not walking: back()
            stop()
            if walking: mech.z = old
            return
        if collision_check(mech, WALK_DROP, old, ot):
            say('You notice a large drop in front of you')
            if absent or not (int(mech.prefs) & MECHPREF_AUTOFALL) and roll(avoid(), True):
                say('You manage to stop before falling off.', 'stops suddenly to avoid driving off a cliff!' if mech.move_type == M.WHEEL else 'stops suddenly to avoid falling off a cliff!')
                back()
                stop()
            else:
                say('You run off the cliff and fall to the ground below.' if walking else 'You drive off the cliff and fall to the ground below.', 'runs off a cliff and falls to the ground below!' if walking else 'drives off a cliff and falls to the ground below.')
                fall(old - elevation)
                if mech.move_type in (M.TRACK, M.WHEEL):
                    domino_space(mech, 2)
                    if mech_rterrain(mech) == WATER and not int(mech.specials2) & WATERPROOF_TECH:
                        say('You drive into the water and your vehicle becomes inoperable.')
                        destroy_mech(mech, mech, showboom=False, reason=KILL_TYPE_FLOOD)
                if walking: stop()
            return
        if mech.move_type == M.HOVER and collision_check(mech, HIT_UNDER_BRIDGE, old, ot):
            say('You notice the underside of the bridge in front of you!')
            if absent or roll(avoid()):
                say('You manage to stop before slamming into the bridge.', 'stops suddenly to avoid slamming into the bridge!')
            else:
                say('You drive right into the underside of the bridge.', 'drives right into the underside of the bridge.')
                fall(1)
            back(); stop()
            return
        if reverse_collision(): return
        if walking:
            # C reuses le and deltax for elevation cost before the suit rollback.
            le = slow(MP1, MP2)
            if le:
                deltax = MP1 if le == 1 else MP2
            if mech.unit_type == U.BSUIT:
                if water_edge(True): return
            elif (mech.unit_type != U.MW and not int(mech.specials2) & WATERPROOF_TECH and
                  (mech_rterrain(mech) == HIGHWATER or mech_rterrain(mech) in (WATER, BRIDGE, ICE) and mech.z < 0)):
                from physics.cargo import cargo_max_speed
                from systems.heat import is_running
                from systems.movement_commands import pending, schedule_mode
                maximum = cargo_max_speed(mech)
                mech.desired_speed = float32(min(mech.desired_speed, maximum * 2 / 3))
                if mech.has_status2(S2.SPRINTING):
                    los_broadcast(mech, 'breaks out of its sprint as it enters water!')
                    say('You lose your sprinting momentum as you enter water!')
                    if mech._engine is not None and not pending(mech, '_mode_event'):
                        schedule_mode(mech._engine, mech, S2.SPRINTING, False, 30)
                # The queued exit removes Speed Demon from this second C query.
                running = is_running(mech.speed, cargo_max_speed(mech))
                say('You struggle to keep control as you run into the water!' if running else 'You use your piloting skill to maneuver through the water.', audience=0)
                terrain = mech_rterrain(mech)
                mod = (2 if running else 0) + (-2 if terrain == HIGHWATER else bridge_w_elevation(mech) if terrain == BRIDGE else 1 if mech.elev > 3 else mech.elev - 2)
                if not make_piloting_roll(mech, mod, award_xp=False, succeed_when_fallen=False).success:
                    say('You slip in the water and fall down', 'slips in the water and falls down!')
                    fall(1, bool(running))
                    done = True
        else:
            if mech.move_type in (M.TRACK, M.WHEEL) and water_edge(): return
            if mech.move_type == M.HOVER or btech_config(mech, 'btech_newterrain', 0):
                trees(mech.move_type != M.TRACK, mech.move_type == M.WHEEL)
            slow(MP2, MP3)
    elif mech.move_type in (M.HULL, M.FOIL, M.SUB):
        if mech_rterrain(mech) not in (WATER, BRIDGE) or abs(mech.elev) < abs(mech.z) + (-1 if mech.move_type == M.FOIL else 0):
            mech.elev, mech.terrain = le % 256, ot
            say('You attempt to get too close with ground!')
            if absent or roll(int(abs(mech.speed + MP1) / MP1) / 3):
                say('You manage to stop before crashing.', 'stops suddenly to avoid running aground!')
                back()
            else:
                say('You smash into the ground!', 'smashes aground!')
                fall(mech.speed * MP_PER_KPH / 4)
            stop(); mech.vertical_speed = 0
            return
    elif mech.move_type in (M.VTOL, M.FLY):
        terrain = mech_rterrain(mech)
        if (mech.has_status(S.LANDED) and terrain not in (ROAD, BRIDGE, GRASSLAND, BUILDING) or
                not aero and terrain in (LIGHT_FOREST, HEAVY_FOREST) and mech.z < mech_elevation(mech) + 2):
            say('You go where no flying thing has ever gone before..')
            if valid_pilot(mech) and roll(5):
                say('You stop in time!'); back()
            else:
                say("Eww.. You've a bad feeling about this.", 'crashes!'); fall(1)
            stop()
            return
        if mech.has_status(S.LANDED) and reverse_collision(1000): return
        if terrain == WATER: return
        if collision_check(mech, JUMP, 0, 0):
            back()
            say('You attempt to fly over elevation that is too high!!' if aero else 'You attempt to fly over elevation that is too high!')
            if absent or roll(mech.fz / ZSCALE / 3) and ot in (GRASSLAND, ROAD, BUILDING):
                say('You land safely.')
                mech.set_status(S.LANDED)
                mech.speed = mech.vertical_speed = 0
            else:
                say('You crash into the obstacle and fall from the sky!!!!!' if aero else 'You crash into the obstacle and fall from the sky!', 'crashes into an obstacle and falls from the sky!')
                from physics.collision import mechs_elevation
                fall(mechs_elevation(mech) + 1)
                domino_space(mech, 2)
    if not done:
        from systems.mines import possible_mine_poof
        possible_mine_poof(mech, 'step')
        if (btech_config(mech, 'btech_fasaadvvhlfire', getattr(mech._engine, 'advanced_vehicle_fire', False)) and
                mech.unit_type == U.VEH_GROUND and mech.terrain == FIRE):
            from systems.vehicle_fire import check_vehicle_in_fire
            check_vehicle_in_fire(mech._engine, mech, from_hex=True)
    if not aero:
        mark_for_los_update(mech)


def on_hex_entered(mech: 'Mech', old_x: int, old_y: int,
                   deltax: float = 0.0, deltay: float = 0.0,
                   last_z: int = 0, *, upd_z=None, previous_z=None) -> None:
    """
    Handle a mech entering a new hex.

    This is a callback for when check_hex_crossing() returns True.  It is
    the Python analogue of move_mech's hex-crossing block
    (mech.update.c:593-682): break cover, refresh the terrain/elev caches,
    ice checks, DropSetElevation, NewHexEntered, then the stacking check.

    With no map only the counter/hidden handling runs - mapless behavior
    is unchanged.

    Args:
        mech: The mech that moved
        old_x: Previous hex X
        old_y: Previous hex Y
        deltax: This tick's float X delta (for moving the unit back)
        deltay: This tick's float Y delta
        last_z: Z level before the move (the C's oz/last_z, mech.update.c:231)
    """
    from entities.mech import CritStatus

    # Break hidden status when moving (mech.update.c:604-609)
    if mech.has_crit_status(CritStatus.HIDDEN):
        from systems.sensors import los_broadcast
        _notify(mech, 'You move too much and break your cover!')
        los_broadcast(mech, 'breaks from its cover.')
        mech.clear_crit_status(CritStatus.HIDDEN)
    from systems.swarm import stop_hiding
    stop_hiding(mech)

    if mech.map is None:
        mech.hexes_walked += 1.0
        return

    from entities.map import ICE
    from entities.mech import UnitType
    from physics.collision import domino_space
    from physics.collision import mech_rterrain

    x = mech.x
    y = mech.y
    mech.terrain = mech.map.terrain(x, y)             # mech.update.c:616
    mech.elev = mech.map.elevation(x, y)              # mech.update.c:617

    iced = 0
    oz = last_z if previous_z is None else previous_z
    # upd_z block (mech.update.c:639-658): set while walking, not while
    # jumping (mech.update.c:359 vs the jump branch).
    if upd_z if upd_z is not None else not mech.is_jumping:
        # Chance of breaking through ICE (mech.update.c:641-647)
        if mech_rterrain(mech) == ICE:
            if oz < -1 and mech.z >= -1:
                break_thru_ice(mech)
            elif mech.z == 0:
                if possibly_drop_thru_ice(mech):
                    iced = 1

        # Check for bridges and basic elevation changes (mech.update.c:651)
        drop_set_elevation(mech, 0)

        # To fix certain slide-under-ice-effect for _mechs_
        # (mech.update.c:653-658)
        if (mech.unit_type == UnitType.MECH and mech_rterrain(mech) == ICE
                and oz == -1 and mech.z == -1):
            mech.z = 0
            mech.fz = float32(mech.z * ZSCALE)

    if not iced:                                      # mech.update.c:662-663
        new_hex_entered(mech, deltax, deltay, last_z)

    if mech.x == x and mech.y == y:                   # mech.update.c:665
        if mech.unit_type in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS):
            from systems.ecm import mark_for_los_update
            mark_for_los_update(mech)
        from physics.flooding import flood_unit
        flood_unit(mech)
        from physics.flooding import extinguish_in_water
        extinguish_in_water(mech)
        from systems.buildings import query as step_building
        step_building(mech,mech.x,mech.y,step=True)
        if mech.in_character:
            mech.hexes_walked += 1.0
            from systems.piloting import valid_pilot
            if int(mech.hexes_walked) % 10 == 0 and valid_pilot(mech):
                from systems.experience import piloting
                piloting(mech.pilot, mech, 1, False)

        # Check for stacking (mech.update.c:681)
        domino_space(mech, 0)


# =============================================================================
# Charge Trigger Hook
# =============================================================================

def reset_charge(mech: 'Mech') -> None:
    """Reset the mech's charge state (target/timer/distance)."""
    mech.charge_target = -1
    mech.charge_timer = 0
    mech.charge_distance = 0.0


def update_charge(mech, hexes_moved=0):
    """Post-height charge contact check; timer and distance belong before entry."""
    from systems.targeting import resolve_unit, fa_mech_range
    target = resolve_unit(mech, mech.charge_target)
    if target is None:
        _notify(mech, 'Invalid CHARGE target!', 0)
        reset_charge(mech)
        return ['Invalid CHARGE target!']
    if fa_mech_range(mech, target) < CHARGE_DIST_TRIGGER:
        from systems.physical import charge_mech
        mech.last_charge_result = charge_mech(mech, target)
        reset_charge(mech)
    return []


# =============================================================================
# Combined Movement Update
# =============================================================================

def update_movement(mech: 'Mech', *, source_callback=False, flight_vectors=False) -> dict:
    """
    Perform a full movement update for one tick.

    This is the main function called by the game loop's movement system.
    It handles heading, speed, and position in the correct order.

    Args:
        mech: The mech to update

    Returns:
        Dict with results: {heading_changed, speed_changed, position_changed, hex_crossed}
    """
    from entities.mech import MechStatus

    result = {
        'heading_changed': False,
        'speed_changed': False,
        'position_changed': False,
        'hex_crossed': False,
        'old_x': mech.x,
        'old_y': mech.y,
        'messages': [],
    }

    # Must be started to move
    if not source_callback and not mech.is_started:
        return result

    # Can't move if destroyed
    if not source_callback and mech.is_destroyed:
        return result

    # Update heading
    if not flight_vectors:
        result['heading_changed'] = update_heading(mech)

    # Update speed
    if not flight_vectors:
        result['speed_changed'] = update_speed(mech)

    old_map = mech.mapindex
    result['position_changed'] = move_mech(mech)
    result['hex_crossed'] = result['position_changed'] and (old_map != mech.mapindex or check_hex_crossing(mech))
    return result


# =============================================================================
# Game Loop Integration
# =============================================================================

def movement_periodic(engine: 'GameEngine') -> None:
    """
    Periodic movement update for all registered mechs.

    This is registered with the game engine to run every MOVE_TICK.
    It iterates all entities and updates their movement.

    Args:
        engine: The game engine
    """
    from entities.mech import Mech

    for entity in engine.get_entities():
        if isinstance(entity, Mech):
            update_movement(entity)
        elif getattr(entity, 'has_turret', False):
            # Vehicle branch of the per-second update: autoturn turret
            # snap (mech.update.c:2932-2965).  Full vehicle movement is
            # a later workstream.
            from systems.maneuver import update_autoturn_turret
            update_autoturn_turret(entity, getattr(entity, 'map', None))


def register_movement_system(engine: 'GameEngine') -> None:
    """
    Register the movement system with the game engine.

    This sets up the periodic movement updates.

    Args:
        engine: The game engine to register with
    """
    engine.register_periodic("movement", MOVE_TICK, movement_periodic)


# =============================================================================
# Event-Driven Movement
# =============================================================================

def mech_move_event(event: 'Event') -> None:
    """
    Per-mech movement event callback.

    Port of mech_move_event (mech.events.c:319-347): the event runs
    UpdateHeading -> UpdateSpeed -> move_mech (our update_movement), then
    re-arms itself at MOVE_TICK (re-arm sites mech.events.c:329,346) while
    the mech still has speed, a desired speed, or an unfinished facing
    change.  When all three are settled the chain simply dies -- a
    stationary mech has NO movement event (mech.events.c:319-347).

    Event convention: data = the mech, data2 = the engine (used to re-arm).

    Args:
        event: The firing Event; event.data is the Mech, event.data2 the
            GameEngine
    """
    from core.events import EventType

    mech = event.data
    engine = mech._engine or event.data2

    from entities.mech import UnitType, MoveType, MechStatus
    from systems.movement_commands import legs
    from physics.heights import fuel_check
    from physics.collision import mech_rterrain
    from entities.map import WATER, ICE, BRIDGE
    if mech.unit_type == UnitType.VTOL and (mech.has_status(MechStatus.LANDED) or fuel_check(mech)):
        return

    from systems.parts import is_mech_legless
    legless = is_mech_legless(mech)
    if legless or mech.is_jumping or getattr(mech, "cocoon", 0):
        update_heading(mech)
        if mech.facing != mech.desired_facing:
            engine.schedule_event(MOVE_TICK, EventType.MOVE, mech_move_event,
                                  data=mech, data2=engine)
        return
    update_movement(mech, source_callback=True)
    if mech.mapindex < 0:
        return
    if mech.unit_type == UnitType.VEH_NAVAL and mech_rterrain(mech) not in (BRIDGE, ICE, WATER):
        return

    # mech.events.c:342-346: re-arm while still moving, ordered to move,
    # or mid-turn; otherwise let the event chain die.
    if (mech.speed != 0 or mech.desired_speed != 0
            or (mech.unit_type == UnitType.VTOL or mech.move_type == MoveType.SUB) and mech.vertical_speed != 0
            or mech.facing != mech.desired_facing):
        engine.schedule_event(
            MOVE_TICK, EventType.MOVE, mech_move_event,
            data=mech, data2=engine,
        )



def aero_move_event(event):
    """Source aero callback using the shared fuel and movement owners."""
    from physics import aerospace
    from core.events import EventType
    from entities.mech import UnitType, MechStatus
    from physics.heights import fuel_check
    from physics.collision import mech_elevation
    unit = event.data
    engine = unit._engine
    if not unit.has_status(MechStatus.LANDED):
        if fuel_check(unit):
            return
        if unit.is_started:
            aerospace.update_heading(unit)
            aerospace.update_speed(unit)
        if unit.is_fallen:
            unit.start_fz -= 1
        update_movement(unit, source_callback=True, flight_vectors=True)
        if (unit.unit_type in (UnitType.DS, UnitType.SPHEROID_DS) and unit.z <= mech_elevation(unit) + 5
                and (engine.muxevent_tick // 2) % 10 == 0):
            aerospace.exhaust(unit, 8)
        engine.schedule_event(MOVE_TICK, EventType.MOVE, aero_move_event, data=unit)
    elif not unit.is_fallen and unit.unit_type in (UnitType.AERO, UnitType.DS):
        update_movement(unit, source_callback=True)
        if (abs(unit.speed) > 0 or abs(unit.desired_speed) > 0 or unit.desired_facing != unit.facing) and not fuel_check(unit):
            engine.schedule_event(MOVE_TICK, EventType.MOVE, aero_move_event, data=unit)


def start_move_event(engine: 'GameEngine', mech: 'Mech') -> None:
    """
    Schedule a mech's movement event chain if one is not already pending.

    This is the entry point speed/heading mutators and commands call.  It
    mirrors the C MECHEVENT(mech, EVENT_MOVE, mech_move_event, MOVE_TICK, 0)
    arming sites: a mech has at most one pending EVENT_MOVE, guarded here
    via the queue's type+data lookup.  The event's data is the mech itself
    (mech.events.c:319-347).

    Args:
        engine: The game engine whose event queue drives the chain
        mech: The mech to start moving
    """
    from core.events import EventType
    from physics.heights import AERO_TYPES

    if engine.has_event(EventType.MOVE, mech):
        return

    engine.schedule_event(
        MOVE_TICK, EventType.MOVE, aero_move_event if mech.unit_type in AERO_TYPES else mech_move_event,
        data=mech, data2=engine,
    )
