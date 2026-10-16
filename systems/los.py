# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.los.c
#   btech/mech.combat.c
#   btech/mech.los.c
#   btech/mech.sensor.c
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/map.h
#   btech/src/btech/mech.h
#   btech/src/include/btconfig.h
#   mech.lostracer.c

"""
Line-of-sight — port of the BTMux LOS layer (mech.los.c, map.los.c).

The per-map pairwise LOS/sensor flag matrix (MAP.LOSinfo, map.h:189) is
stored on GameMap as `losinfo`: a dict keyed by (looker._id, target._id)
with int flag values; a missing key means 0.  (Container deviation from the
C's index-parallel [i][j] array — same values, keyed by unit id instead of
roster slot.)

Ported from the standard build: btconfig.h defines both ADVANCED_LOS
(../include/btconfig.h:209) and BT_PARTIAL (../include/btconfig.h:82), so
in_line_of_sight() reads the CACHED SEES bits (up to 1 s stale — that
staleness is the game feel) and partial cover is decided by the
hex-before-target rule, not the in-loop height test.
"""

import math
import sys
from core.randomness import float32 as f32

from entities.map import (
    bounded,
    WATER, HIGHWATER, ICE, BRIDGE,
    LIGHT_FOREST, HEAVY_FOREST, MOUNTAINS, FIRE, SMOKE,
)
from entities.mech import MechStatus, CritStatus, UnitType, MoveType, Specials
from entities.vehicle import TankCritStatus
from physics.collision import mech_rterrain
from physics.hexmath import hex_to_float

# --- LOSinfo flag bits (map.h:131-157) ---
MECHMAPFLAG_MOVED = 1       # mech has moved since last LOS update

MECHLOSFLAG_SEEN = 0x0001   # <mech> has seen <target> (before)
MECHLOSFLAG_SEESP = 0x0002  # <mech> sees <target> now w/ primary
MECHLOSFLAG_SEESS = 0x0004  # <mech> sees <target> now w/ secondary
MECHLOSFLAG_SEEC2 = 0x0008  # The terrain flag has been calculated
MECHLOSFLAG_MNTN = 0x0010   # Intervening mountain hexes?

MECHLOSFLAG_WOOD = 0x0020   # The number of intervening woods hexes
MECHLOSFLAG_WOOD2 = 0x0040  # Heavywood = 2, Light = 1
MECHLOSFLAG_WOOD3 = 0x0080
MECHLOSFLAG_WOOD4 = 0x0100
MECHLOSBYTES_WOOD = 4
MECHLOSMAX_WOOD = 16        # No sensors penetrate this far

MECHLOSFLAG_WATER = 0x0200  # The number of intervening water hexes
MECHLOSFLAG_WATER2 = 0x0400
MECHLOSFLAG_WATER3 = 0x0800
MECHLOSBYTES_WATER = 3
MECHLOSMAX_WATER = 8        # No sensors penetrate this far

MECHLOSFLAG_PARTIAL = 0x1000  # The target's in partial cover for da shooter
MECHLOSFLAG_FIRE = 0x2000     # Fire between mech and target
MECHLOSFLAG_SMOKE = 0x4000    # Smoke between mech and target
MECHLOSFLAG_BLOCK = 0x8000    # Something blocks vision (elevation probably)


# --- TraceLOS constants (mech.lostracer.c:147-152) ---
DEG60 = 1.0471976           # 60 degrees in radians (mech.lostracer.c:147)
DEG30 = 0.5235988           # mech.lostracer.c:148
ROOT3 = 1.7320508           # mech.lostracer.c:149
TRACESCALEMAP = 1           # mech.lostracer.c:150

# hexdir enum (mech.lostracer.c:152)
N, NE, SE, S, SW, NW = range(6)

# Ammo mode bit used by Sensor_ToHitBonus's light modifier (mech.h:652)
AC_INCENDIARY_MODE = 0x00008000


def _c_mod2(v: int) -> int:
    """
    C's `v % 2` (truncation toward zero): 0 for even, 1 for positive odd,
    -1 for negative odd.  Python's % would give +1 for negative odd.
    """
    return v % 2 if v >= 0 else -((-v) % 2)


# =============================================================================
# LOS flag accessor macros (btmacros.h)
# =============================================================================

def mech_los_flag_wood_count(flag: int) -> int:
    """Intervening-woods count in a LOS flag.  MechLOSFlag_WoodCount (btmacros.h:872-873)."""
    return (flag // MECHLOSFLAG_WOOD) % MECHLOSMAX_WOOD


def mech_los_flag_water_count(flag: int) -> int:
    """Intervening-water count in a LOS flag.  MechLOSFlag_WaterCount (btmacros.h:874-875)."""
    return (flag // MECHLOSFLAG_WATER) % MECHLOSMAX_WATER


def mech_to_mech_los_flag(gamemap, looker, target) -> int:
    """
    Cached LOS flag for an ordered pair.  MechToMech_LOSFlag (btmacros.h:877-878):
    map->LOSinfo[from->mapnumber][to->mapnumber].

    Container deviation (authorized): losinfo is a dict keyed by
    (looker._id, target._id); losinfo=None (LOS wave not yet run) and a
    missing key both read as 0.
    """
    if gamemap is None or gamemap.losinfo is None:
        return 0
    return gamemap.losinfo.get((looker._id, target._id), 0)


# =============================================================================
# Predicate macros used by the LOS math (btmacros.h / mech.h)
# =============================================================================

def is_water(terrain: str) -> bool:
    """IsWater (btmacros.h:685): ICE, WATER or BRIDGE."""
    return terrain == ICE or terrain == WATER or terrain == BRIDGE


def in_water(mech) -> bool:
    """InWater (btmacros.h:686): on water real-terrain with z < 0."""
    return is_water(mech_rterrain(mech)) and mech.z < 0


def water_beast(mech) -> bool:
    """WaterBeast (btmacros.h:707): MOVE_HULL or MOVE_FOIL movement."""
    return mech.move_type == MoveType.HULL or mech.move_type == MoveType.FOIL


def is_ds(mech) -> bool:
    """IsDS (mech.h:725) via DropShip (mech.h:724): CLASS_DS or CLASS_SPHEROID_DS."""
    return mech.unit_type == UnitType.DS or mech.unit_type == UnitType.SPHEROID_DS


def mech_dug_in(mech) -> bool:
    """MechDugIn (btmacros.h:407): tank crit status DUG_IN.  Mechs have no
    tank_crit_status field, which reads as 0 here."""
    return bool(getattr(mech, 'tank_crit_status', 0) & TankCritStatus.DUG_IN)


# =============================================================================
# TraceLOS — the hex line-trace engine (mech.lostracer.c)
# =============================================================================

def get_adj_hex(currx: int, curry: int, nexthex: int) -> tuple:
    """
    Coordinates of the adjacent hex in a given direction.
    Port of GetAdjHex (mech.lostracer.c:174-206).
    """
    if nexthex == N:
        return currx, curry - 1
    elif nexthex == NE:
        return currx + 1, curry - _c_mod2(currx)
    elif nexthex == SE:
        return currx + 1, curry - _c_mod2(currx) + 1
    elif nexthex == S:
        return currx, curry + 1
    elif nexthex == SW:
        return currx - 1, curry - _c_mod2(currx) + 1
    elif nexthex == NW:
        return currx - 1, curry - _c_mod2(currx)
    # Preserve the source stderr diagnostic before the fallback.
    print("XXX ARGH: TraceLos doesn't know where to go!", file=sys.stderr)
    return currx + 1, curry + 1


def _los_map_coord_to_real_coord(x: int, y: int) -> tuple:
    """
    TraceLOS's own hex->cartesian conversion (unit-scale, distinct from
    hexmath's SCALEMAP one).  LOS_MapCoordToRealCoord (mech.lostracer.c:170-172).
    """
    # ROOT3 and 0.5 are double literals; round the float assignments.
    cx = f32(f32(x) * ROOT3 / 2 * TRACESCALEMAP)
    cy = f32((f32(y) - 0.5 * _c_mod2(x)) * TRACESCALEMAP)
    return cx, cy


def _store_best_of(gamemap, found, x1, y1, x2, y2) -> None:
    """
    Of two tied hexes, store the one better for the defender (higher
    elevation); off-map candidates lose the tie.  Store_BestOf
    (mech.lostracer.c:159-168).
    """
    if x1 < 0 or x1 >= gamemap.map_width or y1 < 0 or y1 >= gamemap.map_height:
        found.append((x2, y2))
    elif x2 < 0 or x2 >= gamemap.map_width or y2 < 0 or y2 >= gamemap.map_height:
        found.append((x1, y1))
    elif gamemap.base_elevation(x1, y1) > gamemap.base_elevation(x2, y2):
        found.append((x1, y1))
    else:
        found.append((x2, y2))


def trace_los(gamemap, ax: int, ay: int, bx: int, by: int) -> list:
    """
    Trace the hex line from (ax,ay) to (bx,by).  Port of TraceLOS
    (mech.lostracer.c:208-431).

    Returns the list of (x, y) hexes the line passes through, in order,
    EXCLUDING the start hex and INCLUDING the end hex (which is always the
    last element).  (Signature deviation: the C fills a static
    lostrace_info buffer through an out-param and returns the count; here
    the list is returned directly and its len() is the count.)
    """
    found = []  # found_coords / Store_Hex (mech.lostracer.c:154-157)

    # THE base case (mech.lostracer.c:245-249)
    if ax == bx and ay == by:
        found.append((bx, by))
        return found

    # Is it vertical? (mech.lostracer.c:251-261)
    if ax == bx:
        if ay > by:
            for i in range(ay - 1, by, -1):
                found.append((ax, i))
        else:
            for i in range(ay + 1, by):
                found.append((ax, i))
        found.append((bx, by))
        return found

    # Does it lie along a 90 degree 'tie' direction? (mech.lostracer.c:263-283)
    # IF(even-number-of-cols apart AND same-y-coord)
    if not ((bx - ax) % 2) and ay == by:
        currx = ax
        i = 1 if bx > ax else -1
        while currx != bx:
            # Do best of (currx+1,by-currx%2) or (currx+1,by-currx%2+1)
            _store_best_of(gamemap, found,
                           currx + 1 * i, by - _c_mod2(currx),
                           currx + 1 * i, by - _c_mod2(currx) + 1)
            if currx != bx:     # always true here; kept verbatim (:274)
                found.append((currx + 2 * i, by))
            currx += 2 * i
        # Store_Hex(bx,by) is commented out in the C (:280); the endpoint
        # was already stored by the in-loop Store_Hex above.
        return found

    # Does it lie along a 30, 150, 210, 330 degree 'tie' direction?
    # (mech.lostracer.c:285-334)
    if abs(by - ay) == (3 * abs(bx - ax)) // 2 + abs(_c_mod2(bx - ax)) * abs(
            _c_mod2(ax) if by < ay else 1 - _c_mod2(ax)):
        # x and y 'multipliers' -- either 1 or -1 (:298-313)
        if bx > ax:
            xmul = 1
            ymul = 1 if by > ay else -1
        elif by > ay:
            xmul = -1
            ymul = 1
        else:
            xmul = -1
            ymul = -1

        currx = ax
        curry = ay
        while currx != bx and curry != by:
            _store_best_of(gamemap, found,
                           currx, curry + ymul,
                           currx + xmul,
                           curry + 1 - _c_mod2(currx) if ymul == 1
                           else curry - _c_mod2(currx))

            curry += (2 - _c_mod2(currx)) if ymul == 1 else (-1 - _c_mod2(currx))
            currx += xmul

            if currx == bx and curry == by:
                continue

            found.append((currx, curry))
        found.append((currx, curry))
        return found

    # --- OK, now we know it's not a special case (mech.lostracer.c:336-362) ---

    acx, acy = _los_map_coord_to_real_coord(ax, ay)
    bcx, bcy = _los_map_coord_to_real_coord(bx, by)

    slope = f32(f32(acy - bcy) / f32(acx - bcx))
    uangle = f32(-math.atan(slope))
    sinu = f32(math.sin(uangle))
    cosu = f32(math.cos(uangle))

    liney = f32(f32(acx * sinu) + f32(acy * cosu))     # TRANSFORMED y coord of the line
    enddist = f32(f32(bcx * cosu) - f32(bcy * sinu))   # distance along at end of line

    tempangle = abs(uangle)
    while tempangle > DEG60:
        tempangle = f32(tempangle - DEG60)
    effrad = f32(math.cos(tempangle - DEG30) * TRACESCALEMAP / ROOT3)

    # Setup over, here's the loop (mech.lostracer.c:364-431)
    currx = ax
    curry = ay
    currcx, currcy = _los_map_coord_to_real_coord(currx, curry)
    currdist = f32(f32(currcx * cosu) - f32(currcy * sinu))
    bestdist = enddist          # worst possible point to go to
    bestx = 0
    besty = 0

    while not (currx == bx and curry == by):
        for nexthex in range(N, NW + 1):
            nextx, nexty = get_adj_hex(currx, curry, nexthex)
            nextcx, nextcy = _los_map_coord_to_real_coord(nextx, nexty)

            # Is it on the line?
            if abs(f32(f32(f32(nextcx * sinu) + f32(nextcy * cosu)) - liney)) > effrad:
                continue

            # Where is it?  Find the transformed x coord
            nextdist = f32(f32(nextcx * cosu) - f32(nextcy * sinu))

            # is it forward of the current hex?
            if abs(f32(enddist - nextdist)) > abs(f32(enddist - currdist)):
                continue

            # Is it better than what we have?
            if abs(f32(enddist - nextdist)) >= abs(f32(enddist - bestdist)):
                bestdist = nextdist
                bestx = nextx
                besty = nexty

        if bestx == bx and besty == by:
            # Found the last hex; jump to the end of the loop.  (The C also
            # saves currx/y into lastx/lasty here, which it never reads:
            # dead stores, mech.lostracer.c:404-405.)
            currx = bestx
            curry = besty
            continue

        found.append((bestx, besty))

        currx = bestx           # Reset the curr hex for the next iteration
        curry = besty
        currdist = bestdist
        bestdist = enddist      # reset to worst possible value

    # the LAST hex (mech.lostracer.c:424-428)
    found.append((currx, curry))
    return found


# =============================================================================
# CalculateLOSFlag and friends (mech.los.c)
# =============================================================================

def actual_elevation(gamemap, x: int, y: int, mech) -> float:
    """
    Effective eye/target elevation of a mech (or a bare hex when mech is
    None).  Port of ActualElevation (mech.los.c:36-53).
    """
    if not gamemap:
        return 0.0
    if not mech:
        return f32(f32(gamemap.base_elevation(x, y)) + 0.1)
    if mech.unit_type == UnitType.MECH and not mech.has_status(MechStatus.FALLEN):
        return float(mech.z) + 1.5
    elif mech.move_type == MoveType.NONE:
        return float(mech.z) + 1.5
    elif is_ds(mech):
        return float(mech.z) + 2.5 + (0 if mech.unit_type == UnitType.DS else 2)
    if mech_dug_in(mech):
        return f32(f32(mech.z) + 0.1)
    return float(mech.z) + 0.5


def calculate_los_flag(mech, target, gamemap, x: int, y: int, ff: int,
                       hex_range: float) -> int:
    """
    Recalculate the terrain-derived LOS flag for mech seeing target (or hex
    (x,y) if target is None); ff is the previous flag.  Port of
    CalculateLOSFlag (mech.los.c:61-284), ADVANCED_LOS / BT_PARTIAL build.
    """
    hex_range = f32(hex_range)
    new_flag = (ff & MECHLOSFLAG_SEEN) + MECHLOSFLAG_SEEC2
    woods_count = 0
    water_count = 0
    uwatercount = 0

    # A Hex target off the map? Don't bother (mech.los.c:80-83)
    if not target and (x < 0 or y < 0 or x >= gamemap.map_width or
                       y >= gamemap.map_height):
        return new_flag + MECHLOSFLAG_BLOCK

    # Outside max sensor range in the worst case? Don't bother. (:85-90)
    if hex_range > (180 if ((mech.specials & Specials.AA_TECH) or
                            (target and (target.specials & Specials.AA_TECH)))
                    else gamemap.maxvis):
        return new_flag + MECHLOSFLAG_BLOCK

    # We start at (MechX(mech), MechY(mech)) and wind up at (x,y) (:92-96)
    pos_x = mech.x
    pos_y = mech.y
    pos_z = actual_elevation(gamemap, pos_x, pos_y, mech)
    end_z = actual_elevation(gamemap, x, y, target)

    # Definition of 'both worlds': According to FASA, if a mech is half
    # submerged, or a sub is surfaced, or any naval or hover is on top
    # of the water, it can see in both the underwater and overwater
    # 'worlds'. (mech.los.c:98-103)

    if end_z > 10 and pos_z > 10:
        return new_flag
    bothworlds = is_water(mech_rterrain(mech)) and (
        ((mech.unit_type == UnitType.MECH) and (mech.z == -1)) or
        (water_beast(mech) and (mech.z == 0)) or
        ((mech.move_type == MoveType.HOVER) and (mech.z == 0)))
    underwater = in_water(mech) and (pos_z < 0.0)

    # Ice hex targeting special case (:113-115)
    if not target and not underwater and gamemap.rterrain(x, y) == ICE:
        end_z = 0.0

    if target:
        # What about him? Both worlds? Or flat out underwater? (:117-124)
        t_bothworlds = is_water(mech_rterrain(target)) and (
            ((target.unit_type == UnitType.MECH) and (target.z == -1)) or
            (water_beast(target) and (target.z == 0)) or
            ((target.move_type == MoveType.HOVER) and (target.z == 0)))
        t_underwater = in_water(target) and (end_z < 0.0)
    else:
        if gamemap.rterrain(x, y) == ICE:
            t_bothworlds = 1
        else:
            t_bothworlds = 0
        t_underwater = end_z < 0.0      # Is the hex underwater?

    # And now we look once more to make sure we aren't wasting our time (:133-137)
    if (underwater and not t_underwater) or (t_underwater and not underwater):
        return new_flag + MECHLOSFLAG_BLOCK

    # Worth our time to mess with figuring partial cover? (:139-141)
    dopartials = 0
    if target and mech:
        dopartials = (target.unit_type == UnitType.MECH) and \
            not target.has_status(MechStatus.FALLEN)

    # Same hex is always LoS (:143-145)
    if x == pos_x and y == pos_y:
        return new_flag

    # Special cases are out of the way, looks like we have to do actual
    # work. (:147-153)
    coords = trace_los(gamemap, pos_x, pos_y, x, y)
    coordcount = len(coords)
    if coordcount > 0:
        z_inc = f32(f32(end_z - pos_z) / f32(coordcount))
    else:
        z_inc = 0.0             # In theory, this should never happen.

    # (BT_PARTIAL build: the #ifndef BT_PARTIAL partial_z/p_z_inc in-loop
    # cover test at mech.los.c:155-158/250-253 is compiled out.)

    if coordcount > 0:          # not in same hex; in same hex, you see always
        for i in range(coordcount):
            pos_z = f32(pos_z + z_inc)
            cx, cy = coords[i]
            if cx < 0 or cx >= gamemap.map_width or \
               cy < 0 or cy >= gamemap.map_height:
                continue
            # Should be possible to see into water.. perhaps. But not
            # on vislight (:169-173)
            terrain = gamemap.rterrain(cx, cy)
            height = gamemap.base_elevation(cx, cy)  # Elevation (btmacros.h:46)

            # If you, personally, are underwater, the only way you can see
            # someone is if they are underwater or in both worlds AND your
            # LoS passes thru nothing but water hexes AND your LoS doesn't
            # go thru the sea floor (:175-177)
            if underwater:
                # LoS hits sea floor (:180-185)
                if not is_water(terrain) or (terrain != BRIDGE and
                                             height >= pos_z):
                    new_flag |= MECHLOSFLAG_BLOCK
                    return new_flag

                # LoS pops out of water, AND we're not tracing to
                # half-submerged mech's head (:187-191)
                if not t_bothworlds and pos_z > 0.0:
                    new_flag |= MECHLOSFLAG_BLOCK
                    return new_flag

                # uwatercount = # hexes LoS travel UNDERWATER (:193-196)
                if pos_z <= 0.0:
                    uwatercount += 1
                water_count += 1
            else:               # Viewer is not underwater
                # keep track of how many wooded hexes we cross (:198-244)
                if pos_z < (height + 2):
                    raw = gamemap.terrain(cx, cy)   # GetTerrain (:200)
                    if raw == SMOKE:
                        if i < coordcount - 1:
                            new_flag |= MECHLOSFLAG_SMOKE
                    elif raw == FIRE:
                        if i < coordcount - 1:
                            new_flag |= MECHLOSFLAG_FIRE

                    if terrain == LIGHT_FOREST or terrain == HEAVY_FOREST:
                        if i < coordcount - 1:
                            woods_count += 1 if terrain == LIGHT_FOREST else 2
                    elif terrain == HIGHWATER:
                        water_count += 1
                    elif terrain == ICE:
                        if pos_z < -0.0:
                            new_flag |= MECHLOSFLAG_BLOCK
                            return new_flag
                        water_count += 1
                    elif terrain == WATER:
                        # LoS goes INTO water and we're not tracing to a
                        # target in both worlds (:228-232)
                        if not bothworlds and (pos_z < 0.0):
                            new_flag |= MECHLOSFLAG_BLOCK
                            return new_flag
                        # Hexes in LoS that are physically underwater (:234-236)
                        if pos_z < 0.0:
                            uwatercount += 1
                        water_count += 1
                    elif terrain == MOUNTAINS:
                        if i < coordcount - 1:
                            new_flag |= MECHLOSFLAG_MNTN

                # make this the new 'current hex' (:245-249)
                if height >= pos_z and terrain != BRIDGE:
                    new_flag |= MECHLOSFLAG_BLOCK
                    return new_flag

    # Then, we check the hex before target hex (BT_PARTIAL build,
    # mech.los.c:257-271)
    if coordcount >= 2:
        if dopartials:
            px, py = coords[coordcount - 2]
            # (bounds guard: the C's Elevation() reads out of the map array
            # unchecked here — UB; skip the test for off-map hexes instead)
            if target.z >= mech.z and gamemap.valid(px, py) and \
               gamemap.base_elevation(px, py) == (target.z + 1):
                new_flag |= MECHLOSFLAG_PARTIAL
            if target.z == -1 and mech_rterrain(target) == WATER:
                new_flag |= MECHLOSFLAG_PARTIAL

    water_count = bounded(0, water_count, MECHLOSMAX_WATER - 1)
    woods_count = bounded(0, woods_count, MECHLOSMAX_WOOD - 1)
    new_flag += MECHLOSFLAG_WOOD * woods_count
    new_flag += MECHLOSFLAG_WATER * water_count

    # Block EM after 2, Vis/IR after 6 (:278-282)
    if uwatercount > 2:
        new_flag |= MECHLOSFLAG_MNTN
    if uwatercount > 6:
        new_flag |= MECHLOSFLAG_FIRE
    return new_flag


# =============================================================================
# Sensor-layer delegation (real ports live in systems/sensors.py and
# physics/hexmath.py; the lazy imports avoid the sensors -> los import cycle)
# =============================================================================

def sensor_to_hit_bonus(mech, target, flag: int, maplight: int,
                        hex_range: float, w_ammo_mode: int) -> int:
    """
    BTH bonus from the current sensors for a given LOS flag.
    Sensor_ToHitBonus (mech.sensor.c:27-77) — real port in systems.sensors.
    """
    from systems.sensors import sensor_to_hit_bonus as _real
    return _real(mech, target, flag, maplight, hex_range, w_ammo_mode)


def sensor_can_see(mech, target, flag: int, arc: int, hex_range: float,
                   mapvis: int, maplight: int, cloudbase: int) -> int:
    """
    Whether the current sensors could see target/hex; 0 = no, else 1
    (primary) + 2 (secondary).  Sensor_CanSee (mech.sensor.c:79-158) — real
    port in systems.sensors.
    """
    from systems.sensors import sensor_can_see as _real
    return _real(mech, target, flag, arc, hex_range, mapvis, maplight,
                 cloudbase)


def gamemap_ok(mech) -> bool:
    """The C's `if (!map || !mech)` guard in Sensor_CanSee (mech.sensor.c:86-88)."""
    return mech is not None and mech.map is not None


def in_weapon_arc(mech, x: float, y: float) -> int:
    """
    Which weapons arc the cartesian point (x, y) is in.  InWeaponArc
    (mech.utils.c:420-457) — real port in physics.hexmath.
    """
    from physics.hexmath import in_weapon_arc as _real
    return _real(mech, x, y)


# =============================================================================
# AddTerrainMod / InLineOfSight readers (mech.los.c:286-372)
# =============================================================================

def add_terrain_mod(mech, target, gamemap, hex_range: float,
                    w_ammo_mode: int = 0) -> int:
    """
    Woods/partial-cover BTH term from the cached LOS flag; also sets/clears
    the target's PARTIAL_COVER status as a side effect.  Port of
    AddTerrainMod (mech.los.c:286-301).
    """
    # Possibly do a quickie check only
    if mech and target:
        if mech_to_mech_los_flag(gamemap, mech, target) & MECHLOSFLAG_PARTIAL:
            target.set_status(MechStatus.PARTIAL_COVER)
        else:
            target.clear_status(MechStatus.PARTIAL_COVER)

        return sensor_to_hit_bonus(mech, target,
                                   mech_to_mech_los_flag(gamemap, mech, target),
                                   gamemap.maplight, hex_range, w_ammo_mode)
    return 0


def in_line_of_sight_nb(mech, target, x: int, y: int, hex_range: float) -> int:
    """
    InLineOfSight with the BLOCK bit filtered out ("no-block" reader used
    at fire time).  Port of InLineOfSight_NB (mech.los.c:303-314).

    target may be None for a pure hex-LOS check — the hex-fire path calls
    LOS_NB(mech, tempMech-or-NULL, mapx, mapy, range) (mech.combat.c:599,
    :602); in_line_of_sight below already routes a None target through the
    live hex computation (mech.los.c:344-359).  Existing mech-target
    callers are unaffected.
    """
    if mech is target:
        return 1

    i = in_line_of_sight(mech, target, x, y, hex_range)
    if i & MECHLOSFLAG_BLOCK:
        return 0
    return i


def in_line_of_sight(mech, target, x: int, y: int, hex_range: float) -> int:
    """
    Can mech see target (or hex (x,y))?  Port of InLineOfSight
    (mech.los.c:316-372), ADVANCED_LOS build: for a mech target this READS
    THE CACHED SEES BITS from map.losinfo (up to 1 s stale — the update
    wave refreshes them; that staleness is the game feel).  Nonzero return
    may include MECHLOSFLAG_BLOCK (sensor lock without LOS).
    """
    gamemap = mech.map
    if not gamemap:
        from core.effects import send_error
        from systems.notifications import mech_notify, MECHPILOT
        mech_notify(mech, MECHPILOT, 'You are on an invalid map! Map index reset!')
        send_error(mech, f'InLineOfSight:invalid map:Mech {mech._id}  Index {mech.mapindex}')
        mech.mapindex = -1
        return 0
    if not gamemap.valid(x,y):
        # C diagnoses then continues into unsafe indexing. Refuse invalid
        # coordinates at the Python boundary instead of wrapping indices.
        from core.effects import send_error
        send_error(mech, f'x:{x} y:{y} out of bounds for #{mech._id} (LOS check)')
        return 0

    # Possibly do a quickie check only (:337-339)
    if mech.has_crit_status(CritStatus.CLAIRVOYANT):
        return 1

    if target:
        x1 = target.fx
        y1 = target.fy
    else:
        x1, y1 = hex_to_float(x, y)     # MapCoordToRealCoord (:345)
    arc = in_weapon_arc(mech, x1, y1)

    if mech and target:
        # ADVANCED_LOS branch (mech.los.c:361-366)
        if mech_to_mech_los_flag(gamemap, mech, target) & (MECHLOSFLAG_SEESP |
                                                           MECHLOSFLAG_SEESS):
            return mech_to_mech_los_flag(gamemap, mech, target) & \
                (MECHLOSFLAG_SEESP | MECHLOSFLAG_SEESS | MECHLOSFLAG_BLOCK)
        return 0

    losflag = calculate_los_flag(mech, None, gamemap, x, y, 0, hex_range)
    return sensor_can_see(mech, None, losflag, arc, hex_range,
                          gamemap.mapvis, gamemap.maplight, gamemap.cloudbase)


class LOSMap:
    """Fresh rectangle of map.los.c flags; visited (1) does not mean visible."""
    def __init__(self, sx, sy, width, height):
        self.sx, self.sy, self.width, self.height = sx, sy, width, height
        self.cells = [0] * (width * height)
        self.has_light = False

    def contains(self, x, y):
        return self.sx <= x < self.sx + self.width and self.sy <= y < self.sy + self.height

    def index(self, x, y):
        if not self.contains(x, y):
            raise ValueError(f'LOSMap request from out of bounds hex: {x},{y}')
        return (y - self.sy) * self.width + x - self.sx

    def position(self, index):
        return self.sx + index % self.width, self.sy + index // self.width

    def mark(self, x, y, flag):
        if self.contains(x, y):
            self.cells[self.index(x, y)] |= flag | 1

    def light(self, x, y):
        if self.contains(x, y):
            self.has_light = True
            self.cells[self.index(x, y)] |= 8

    def lit(self, x, y):
        return self.contains(x, y) and bool(self.cells[self.index(x, y)] & 8)

    def render(self, gamemap):
        result = []
        for i, flags in enumerate(self.cells):
            x, y = self.position(i)
            result.append(dict(x=x, y=y, terrain=gamemap.terrain(x,y) if flags & 2 else None,
                               elevation=gamemap.base_elevation(x,y) if flags & 4 else None))
        return result


def map_eye_height(mech):
    if mech.unit_type == UnitType.MECH:
        return mech.z + .2 + (not mech.is_fallen)
    return mech.z + {UnitType.SPHEROID_DS:4.2, UnitType.DS:2.2,
                     UnitType.MW:.01, UnitType.VEH_NAVAL:.01}.get(mech.unit_type,.2)


def map_sensor_range(mech, gamemap, x, y, z, slot, lit=False):
    from systems.sensors import sensors
    from systems.targeting import find_range
    from physics.hexmath import ZSCALE, FORWARDARC, TURRETARC
    sn = mech.sensor[slot]
    row = sensors[sn]
    maximum = gamemap.mapvis if sn < 2 else row.maxvis
    if sn == 1 and gamemap.maplight == 0:
        maximum *= 2
    fx, fy = hex_to_float(x,y)
    if not row.fullvision and not in_weapon_arc(mech,fx,fy) & (FORWARDARC | TURRETARC):
        maximum = maximum * 2 / 3 if mech.sensor[0] == mech.sensor[1] else 0
    distance = find_range(mech.fx,mech.fy,mech.fz,fx,fy,z*ZSCALE)
    if sn == 0 and maximum and distance >= maximum and lit:
        return -1
    return int(distance < maximum)


def _trace_map_light(result, gamemap, mech, destination):
    from physics.hexmath import FORWARDARC, TURRETARC, ZSCALE
    from systems.targeting import find_range
    horizon = -20
    start = map_eye_height(mech)
    for step, (x,y) in enumerate(trace_los(gamemap,mech.x,mech.y,*destination),1):
        if not gamemap.valid(x,y):
            continue
        floor = max(0,gamemap.base_elevation(x,y))
        fx,fy = hex_to_float(x,y)
        if not in_weapon_arc(mech,fx,fy) & (FORWARDARC|TURRETARC) or find_range(mech.fx,mech.fy,mech.fz,fx,fy,floor*ZSCALE) >= 60:
            return
        slope = (floor-start)/step
        if gamemap.terrain(x,y) in (LIGHT_FOREST,HEAVY_FOREST,SMOKE):
            slope += 2
        if slope >= horizon:
            result.light(x,y)
            horizon = slope


def _mark_map_lights(result, gamemap):
    def halo(x,y):
        result.light(x,y)
        for direction in range(6):
            result.light(*get_adj_hex(x,y,direction))
    # Ordered TYPE_FIRE records are authoritative, including direct/loaded
    # objects that have no timed-decoration dictionary entry.
    fire_hexes = set()
    for fire in getattr(gamemap, 'map_objects', [()])[0]:
        halo(fire.x, fire.y)
        fire_hexes.add((fire.x, fire.y))
    # Keep the accepted legacy overlay fixture interface, without duplication.
    for (x,y), decoration in getattr(gamemap, 'decorations', {}).items():
        if (x,y) not in fire_hexes and decoration['terrain'] == FIRE:
            halo(x,y)
    for mech in gamemap.mechs_on_map:
        if mech is None:
            continue
        if mech.crit_status & CritStatus.JELLIED:
            halo(mech.x,mech.y)
        if mech.status2 & 0x20:
            for index in range(len(result.cells)):
                _trace_map_light(result,gamemap,mech,result.position(index))


def _trace_map_terrain(result, gamemap, mech, destination):
    from systems.sensors import sensors
    minimum = [-20 if sn < 4 else 1000 for sn in mech.sensor]
    block = minimum.copy()
    woods = [0,0]
    start = map_eye_height(mech)
    for step,(x,y) in enumerate(trace_los(gamemap,mech.x,mech.y,*destination),1):
        if not gamemap.valid(x,y):
            continue
        floor = gamemap.base_elevation(x,y)
        terrain = gamemap.rterrain(x,y)
        angle, canopy = (floor-start)/step, (floor+2-start)/step
        for slot,sn in enumerate(mech.sensor):
            callback = sensors[sn].cansee_func
            if canopy < minimum[slot]:
                result.mark(x,y,0)
            else:
                state = map_sensor_range(mech,gamemap,x,y,floor,slot,result.has_light)
                if not state:
                    result.mark(x,y,0)
                    minimum[slot] = block[slot] = 1000
                else:
                    newwoods = {LIGHT_FOREST:1,HEAVY_FOREST:2}.get(terrain,0)
                    visible_light = state > 0 or result.lit(x,y)
                    if not newwoods:
                        if angle < minimum[slot] or not visible_light:
                            result.mark(x,y,0)
                        else:
                            result.mark(x,y,6)
                            block[slot] = minimum[slot] = angle
                            woods[slot] = 0
                    else:
                        if block[slot] < angle:
                            minimum[slot],block[slot],woods[slot] = angle,canopy,newwoods
                        elif not callback(mech,None,gamemap,1,(woods[slot]+newwoods)*MECHLOSFLAG_WOOD):
                            if canopy >= block[slot]:
                                minimum[slot],block[slot],woods[slot] = block[slot],canopy,newwoods
                            else:
                                minimum[slot] = canopy
                        else:
                            minimum[slot] = angle
                            woods[slot] += newwoods
                        # The source WATER-only branch after this woods test is unreachable.
                        result.mark(x,y,6 if visible_light else 0)
            barrier = (terrain == WATER and not callback(mech,None,gamemap,1,MECHLOSFLAG_WATER) or
                       terrain == MOUNTAINS and not callback(mech,None,gamemap,1,MECHLOSFLAG_MNTN))
            if barrier:
                result.mark(x,y,0)
                minimum[slot] = block[slot] = 1000


def calculate_los_map(gamemap, mech, sx, sy, width, height):
    """Port CalculateLOSMap, preserving edge order and OR writes, with safe bounds."""
    if not (0 < width <= 70 and 0 < height <= 45 and gamemap.valid(sx,sy) and
            gamemap.valid(sx+width-1,sy+height-1)):
        raise ValueError('Invalid LOS rectangle (maximum 70 by 45).')
    result = LOSMap(sx,sy,width,height)
    if mech.crit_status & CritStatus.CLAIRVOYANT:
        result.cells[:] = [7]*len(result.cells)
        return result
    if all(sn >= 4 for sn in mech.sensor):
        result.cells[:] = [1]*len(result.cells)
        return result
    _mark_map_lights(result,gamemap)
    order = (list(range(width)) + list(range((height-1)*width,height*width)) +
             list(range(width,height*width,width)) + list(range(2*width-1,height*width,width)) +
             list(range(width*height)))
    for index in order:
        if not result.cells[index] & 1:
            _trace_map_terrain(result,gamemap,mech,result.position(index))
    return result
