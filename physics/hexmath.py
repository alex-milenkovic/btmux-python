# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/artillery.c
#   btech/mech.notify.c
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/mech.h
#   btech/src/btech/mymath.h
# Historical Aerospace sources:
#   btech/mech.utils.c
#   src/hcode/btech/btmacros.h
#   src/hcode/btech/mech.h
#   src/hcode/btech/mymath.h

"""
Hex coordinate math for BTMux.

This module handles conversions between hex grid coordinates and floating-point
"real" coordinates, as well as distance and bearing calculations.

BTMux uses an offset hex grid where:
- Odd columns (0, 2, 4...) are vertically offset by half a hex
- Hexes have flat tops (pointy sides)
- Heading 0 is north, 90 is east, 180 is south, 270 is west

Reference: BTMux btech/src/btech/mech.utils.c
"""

import math
from core.randomness import float32 as f32

# Core constants from BTMux mech.h
SCALEMAP = 322.5        # Cartesian units per hex height
HEXLEVEL = 5            # Elevation levels per hex
ZSCALE = 64.5           # SCALEMAP / HEXLEVEL
XSCALE = 0.1547         # Hex constant (not directly used here, but for reference)

# Derived constants from mech.utils.c
ROOT3 = 558.58638544096289      # sqrt(3) * SCALEMAP
ALPHA = 93.097730906827152      # ROOT3 / 6 - width of hex edge segment
ANGLE_ALPHA = 0.28867513459481287  # sqrt(3) / 6 - for angle calcs
FULL_Y = SCALEMAP               # Full hex height in cartesian units
HALF_Y = SCALEMAP / 2           # Half hex height

# Trig constant
TWOPIOVER360 = 0.0174533  # mymath.h source constant, distinct from DEG2RAD

# --- Weapon arc bits (mech.h:87-92) ---
NOARC = 0
FORWARDARC = 1
LSIDEARC = 2
RSIDEARC = 4
REARARC = 8
TURRETARC = 16


def hex_to_float(hex_x: int, hex_y: int) -> tuple[float, float]:
    """
    Convert hex grid coordinates to floating-point cartesian coordinates.

    Returns the center point of the hex.

    Reference: MapCoordToRealCoord() in mech.utils.c

    Args:
        hex_x: Hex X coordinate (column)
        hex_y: Hex Y coordinate (row)

    Returns:
        Tuple of (cart_x, cart_y) - center of hex in cartesian coords
    """
    # X position: (2 + 3*hex_x) * ALPHA
    cart_x = f32(f32(2.0 + f32(3.0 * f32(hex_x))) * ALPHA)

    # Y position: depends on column parity (even columns are offset)
    # Odd columns (1, 3, 5...) have no vertical offset
    # Even columns (0, 2, 4...) are offset by HALF_Y
    if hex_x % 2 == 0:
        cart_y = f32(HALF_Y + (f32(hex_y) * FULL_Y))
    else:
        cart_y = f32(f32(hex_y) * FULL_Y)

    return cart_x, cart_y


def float_to_hex(cart_x: float, cart_y: float) -> tuple[int, int]:
    """
    Convert floating-point cartesian coordinates to hex grid coordinates.

    Reference: RealCoordToMapCoord() in mech.utils.c

    The algorithm divides the hex map into repeatable rectangular regions,
    each containing parts of 4 hexes. See the extensive comments in the
    original C code for the full explanation.

    Args:
        cart_x: Cartesian X coordinate
        cart_y: Cartesian Y coordinate

    Returns:
        Tuple of (hex_x, hex_y) - hex grid coordinates
    """
    cart_x, cart_y = f32(cart_x), f32(cart_y)
    # Special case: in section IV of column 0 or off the map
    if cart_x < ALPHA:
        hex_x = -1 if cart_x < 0 else 0
        hex_y = int(math.floor(cart_y / SCALEMAP))
        return _short_coordinates(hex_x, hex_y)

    # Shift map left so repeatable box starts at 0
    shifted_x = f32(cart_x - ALPHA)

    # Figure out which repeatable box we're in (X)
    x_count = int(shifted_x / ROOT3)
    # Offset inside the box from left edge
    x = f32(shifted_x - x_count * ROOT3)

    # Each box holds two X-columns
    x_count *= 2

    # Y coordinate - simple division
    y_count = int(math.floor(cart_y / FULL_Y))
    y = f32(cart_y - y_count * FULL_Y)

    # Determine which region within the repeatable box we're in
    # This follows the exact logic from the C code

    if x < 2 * ALPHA:
        # Clean in area I - no adjustment needed
        pass

    elif x >= 3 * ALPHA and x < 5 * ALPHA:
        # Clean in either area II or III
        # Up x one, and y if in the lower half of the box
        x_count += 1
        if y >= HALF_Y:
            # Area II
            y_count += 1

    elif x >= 2 * ALPHA and x < 3 * ALPHA:
        # Any of areas I, II and III - check the diagonal boundary
        if y >= HALF_Y:
            # Area I or II
            if 2 * ANGLE_ALPHA * (FULL_Y - y) <= x - 2 * ALPHA:
                # Area II, up both
                x_count += 1
                y_count += 1
        else:
            # Area I or III
            if 2 * ANGLE_ALPHA * y <= x - 2 * ALPHA:
                # Area III, up only x
                x_count += 1

    elif y >= HALF_Y:
        # Area II or IV - up x at least one, maybe two, and y maybe one
        x_count += 1
        if 2 * ANGLE_ALPHA * (y - HALF_Y) > (x - 5.0 * ALPHA):
            # Area II
            y_count += 1
        else:
            # Area IV
            x_count += 1

    else:
        # Area III or IV, up x at least one, maybe two
        x_count += 1
        if 2 * ANGLE_ALPHA * y > ROOT3 - x:
            # Area IV
            x_count += 1

    return _short_coordinates(x_count, y_count)


def _short_coordinates(x, y):
    if not (-32768 <= x <= 32767 and -32768 <= y <= 32767):
        raise ValueError('unsupported coordinate outside signed short domain')
    return x, y


def find_components(speed: float, heading: int) -> tuple[float, float]:
    """
    Convert speed and heading to dx, dy velocity components.

    Reference: FindComponents() in mech.utils.c

    BTMux coordinate system:
    - Heading 0 = North (negative Y)
    - Heading 90 = East (positive X)
    - Heading 180 = South (positive Y)
    - Heading 270 = West (negative X)

    Args:
        speed: Speed magnitude (in KPH, typically)
        heading: Direction in degrees (0-359)

    Returns:
        Tuple of (dx, dy) - velocity components per update
    """
    # The original uses (degrees + 90) because standard trig has 0 at East,
    # but BTMux has 0 at North. Then negates both because:
    # - X increases to the right but 90 should go right
    # - Y increases downward but 0 should go up
    rads = f32(TWOPIOVER360 * (heading + 90))
    dx = -f32(f32(speed) * math.cos(rads))
    dy = -f32(f32(speed) * math.sin(rads))
    return dx, dy


def find_bearing(x0: float, y0: float, x1: float, y1: float) -> int:
    """
    Calculate bearing from point (x0, y0) to point (x1, y1).

    Reference: FindBearing() in mech.utils.c

    Args:
        x0, y0: Source position (cartesian)
        x1, y1: Target position (cartesian)

    Returns:
        Bearing in degrees (0-359), where 0 is North
    """
    dx = f32(f32(x1) - f32(x0))
    dy = f32(f32(y1) - f32(y0))

    # Special case: directly north or south
    if dx == 0.0:
        return 0 if dy < 0 else 180

    # atan2(-dx, dy) with BTMux's coordinate system
    rads = f32(math.atan2(-dx, dy))

    # C adds 5 before signed integer division, including negative radians.
    scaled = f32(f32(10.0 * rads) * f32(180.0 / f32(3.14159265)))
    degrees = int((int(scaled) + 5) / 10)

    # Add 180 and normalize to 0-359 (AcceptableDegree in C)
    degrees = acceptable_degree(degrees + 180)

    return degrees


def in_weapon_arc(mech, x: float, y: float) -> int:
    """
    Which weapon arc(s) the cartesian point (x, y) lies in for a unit,
    accounting for torso twist and (for turreted units) the turret.
    Port of InWeaponArc (mech.utils.c:420-457).

    C oddity preserved: torso twist offsets the relative bearing by 59
    degrees, not 60 (mech.utils.c:429-433).
    """
    from entities.mech import MechStatus, UnitType

    res = NOARC
    bearing_to_target = find_bearing(mech.fx, mech.fy, x, y)
    relat = mech.facing - bearing_to_target
    if mech.unit_type in (UnitType.MECH, UnitType.MW, UnitType.BSUIT):
        if mech.status & MechStatus.TORSO_RIGHT:
            relat += 59
        elif mech.status & MechStatus.TORSO_LEFT:
            relat -= 59
    relat = acceptable_degree(relat)    # AcceptableDegree (mech.utils.c:435)
    if relat >= 300 or relat <= 60:
        res |= FORWARDARC
    if 120 < relat < 240:
        res |= REARARC
    if 240 <= relat < 300:
        res |= RSIDEARC
    if 60 < relat <= 120:
        res |= LSIDEARC

    # MechHasTurret (btmacros.h:271-274): ground / naval / VTOL with an
    # original-internals TURRET section (GetSectOInt).
    has_turret = False
    if mech.unit_type in (UnitType.VEH_GROUND, UnitType.VEH_NAVAL,
                          UnitType.VTOL):
        from entities.mech import VehicleLocation
        turret = mech.sections[VehicleLocation.TURRET]
        has_turret = turret.internal_orig > 0
    if has_turret:
        relat = acceptable_degree(
            (mech.facing + getattr(mech, 'turret_facing', 0)) -
            bearing_to_target)                 # mech.utils.c:446-447
        if relat >= 330 or relat <= 30:
            res |= TURRETARC
    # The C SendErrors on res == NOARC (mech.utils.c:452-454); unreachable -
    # the four relat ranges cover 0-359.
    return res


def hex_bearing(x0: int, y0: int, x1: int, y1: int) -> int:
    """
    Calculate bearing between two hex positions.

    Args:
        x0, y0: Source hex coordinates
        x1, y1: Target hex coordinates

    Returns:
        Bearing in degrees (0-359)
    """
    fx0, fy0 = hex_to_float(x0, y0)
    fx1, fy1 = hex_to_float(x1, y1)
    return find_bearing(fx0, fy0, fx1, fy1)


def find_range(x0: float, y0: float, x1: float, y1: float) -> float:
    """
    Calculate range in hexes between two cartesian positions.

    Reference: FindXYRange() / FindHexRange() in mech.utils.c

    Args:
        x0, y0: Source position (cartesian)
        x1, y1: Target position (cartesian)

    Returns:
        Distance in hexes (floating point)
    """
    dx = f32(f32(x0) - f32(x1))
    dy = f32(f32(y0) - f32(y1))
    return f32(f32(1.0 / SCALEMAP) * f32(math.sqrt(f32(f32(dx * dx) + f32(dy * dy)))))


def find_range3d(x0, y0, z0, x1, y1, z1):
    dx, dy, dz = (f32(f32(a) - f32(b)) for a, b in ((x0, x1), (y0, y1), (z0, z1)))
    squared = f32(f32(f32(dx * dx) + f32(dy * dy)) + f32(dz * dz))
    return f32(f32(1.0 / SCALEMAP) * f32(math.sqrt(squared)))


def find_z_bearing(x0, y0, z0, x1, y1, z1):
    adjacent = find_range(x0, y0, x1, y1)
    opposite = f32(f32(1.0 / SCALEMAP) * abs(f32(f32(z1) - f32(z0))))
    radians = f32(math.atan2(opposite, adjacent))
    return math.ceil(f32(radians * f32(180.0 / f32(3.14159265))))


def signed_remainder(value, divisor):
    quotient = abs(value) // abs(divisor)
    if (value < 0) != (divisor < 0):
        quotient = -quotient
    return value - quotient * divisor


def acceptable_degree(degrees):
    if degrees < 0:
        return signed_remainder(degrees, 360) + 360
    return degrees % 360 if degrees >= 360 else degrees


def find_xy(x0, y0, bearing, distance):
    x0, y0, distance = map(f32, (x0, y0, distance))
    correction = f32(f32(signed_remainder(bearing, 60)) / 60.0)
    if correction > .5:
        correction = f32(1.0 - correction)
    correction = f32(-correction * 2.0)
    xscale = f32((1.0 + XSCALE * correction) * SCALEMAP)
    radians = f32(f32(bearing) * f32(f32(3.14159265) / 180.0))
    x = f32(x0 + f32(f32(distance * f32(math.sin(radians))) * xscale))
    y = f32(y0 - f32(distance * f32(math.cos(radians))) * SCALEMAP)
    return x, y


def my_hex_dist(x1, y1, x2, y2, tc):
    xd, yd = abs(x2 - x1), abs(y2 - y1)
    if x1 == x2:
        return yd
    half = xd // 2
    return yd - half + tc + xd if half <= yd else xd + tc


def hex_distance(x0: int, y0: int, x1: int, y1: int) -> float:
    """
    Calculate distance in hexes between two hex positions.

    Args:
        x0, y0: Source hex coordinates
        x1, y1: Target hex coordinates

    Returns:
        Distance in hexes (floating point)
    """
    fx0, fy0 = hex_to_float(x0, y0)
    fx1, fy1 = hex_to_float(x1, y1)
    return find_range(fx0, fy0, fx1, fy1)


def hex_distance_int(x0: int, y0: int, x1: int, y1: int) -> int:
    """
    Calculate distance in hexes, rounded to integer.

    This is typically what's used for range brackets in combat.

    Args:
        x0, y0: Source hex coordinates
        x1, y1: Target hex coordinates

    Returns:
        Distance in hexes (integer, rounded)
    """
    return round(hex_distance(x0, y0, x1, y1))


def normalize_heading(heading: float) -> int:
    """
    Normalize a heading to 0-359 degrees.

    Args:
        heading: Heading in degrees (may be outside 0-359)

    Returns:
        Normalized heading (0-359)
    """
    heading = heading % 360
    if heading < 0:
        heading += 360
    return int(heading)


def virtual_facing(unit):
    """MechVFacing: AcceptableDegree of facing plus lateral movement."""
    return acceptable_degree(unit.facing + unit.lateral)


def heading_difference(h1: int, h2: int) -> int:
    """
    Calculate the smallest angular difference between two headings.

    Args:
        h1: First heading (degrees)
        h2: Second heading (degrees)

    Returns:
        Smallest difference (0-180), positive value
    """
    diff = abs(h1 - h2) % 360
    if diff > 180:
        diff = 360 - diff
    return diff


def turn_direction(current: int, target: int) -> int:
    """
    Determine which direction to turn to reach target heading fastest.

    Args:
        current: Current heading (degrees)
        target: Target heading (degrees)

    Returns:
        -1 for left (counterclockwise), +1 for right (clockwise), 0 if equal
    """
    if current == target:
        return 0

    diff = (target - current) % 360

    # If diff <= 180, turn right (positive)
    # If diff > 180, turn left (negative)
    if diff == 0:
        return 0
    elif diff <= 180:
        return 1
    else:
        return -1
