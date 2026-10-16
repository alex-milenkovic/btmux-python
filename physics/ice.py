# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.ice.c

"""Ice growth, melting and ice/bridge breakage with C scan ordering.

Terrain reads use the map's real-terrain boundary. Random draws are inclusive,
and temporary markers preserve the original scan ordering.
"""
from core.randomness import draw
import random
from entities.map import WATER, ICE, BRIDGE
from entities.mech import UnitType, MoveType
import re
from entities.map import neighbors


def growable(board, x, y):
    count = sum(board.rterrain(*xy) in (WATER, BRIDGE, '1')
                for xy in neighbors(board, x, y))
    return count <= 4 and (count < 2 or draw('neighbor_d6', 1, 6, lambda: random.randint(1, 6)) > count)


def meltable(board, x, y):
    count = sum(board.rterrain(*xy) == ICE for xy in neighbors(board, x, y))
    return count <= 4 or draw('neighbor_d3', 1, 3, lambda: random.randint(1, 3)) == 1


def _evolve(board, percent, melting):
    source, destination = (ICE, WATER) if melting else (WATER, ICE)
    eligible = meltable if melting else growable
    count = 0
    for x in range(board.map_width):
        for y in range(board.map_height):
            if (board.rterrain(x, y) == source and draw('percentage_draws', 1, 100, lambda: random.randint(1, 100)) <= percent
                    and eligible(board, x, y)):
                if melting:
                    break_surface(board, None, x, y, 'goes swimming as ice breaks!')
                board.set_terrain(x, y, '1')
                count += 1
    for x in range(board.map_width):
        for y in range(board.map_height):
            if board.rterrain(x, y) == '1':
                board.set_terrain(x, y, destination)
    return count


def ice_growth(board, percent):
    return _evolve(board, percent, False)


def ice_melt(board, percent):
    return _evolve(board, percent, True)


def _ice_command(board, argument, melting):
    from systems.movement_commands import attributes
    args = attributes(argument, 2)
    if len(args) != 1:
        return False, 'Invalid arguments!'
    from systems.movement_commands import c_number
    percent = c_number(args[0], True)
    if not percent and args[0] != '0':
        return False, 'Invalid number!'
    count = _evolve(board, percent, melting)
    action = 'melted' if melting else "'iced'"
    return True, f"{count or 'No'} hexes {action}."


def map_addice(board, argument):
    return _ice_command(board, argument, False)


def map_delice(board, argument):
    return _ice_command(board, argument, True)


def break_surface(board, trigger, x, y, message='goes swimming!'):
    from physics.jump import mech_falls
    from physics.movement import _notify
    from systems.damage import destroy_mech, KILL_TYPE_FLOOD

    bridge = board.rterrain(x, y) == BRIDGE
    board.set_terrain(x, y, WATER)
    if bridge:
        board.set_elevation(x, y, 1)
    if not board.base_elevation(x, y):
        return
    for unit in list(board.mechs_on_map):
        if not hasattr(unit, 'unit_type') or unit is trigger or (unit.x, unit.y) != (x, y):
            continue
        unit.terrain = WATER
        if ((bridge and unit.z == unit.elev) or
                (not bridge and unit.z == 0 and unit.move_type != MoveType.HOVER)):
            from systems.sensors import los_broadcast as mech_los_broadcast
            mech_los_broadcast(unit, message)
            mech_falls(unit, unit.elev + int(bridge), notify_fall=False)
            if unit.unit_type == UnitType.VEH_GROUND and not unit.is_destroyed:
                _notify(unit, 'Water renders your vehicle inoperable.')
                mech_los_broadcast(unit, 'fizzles and pops as water renders it inoperable.')
                destroy_mech(unit, unit, showboom=False, reason=KILL_TYPE_FLOOD)


def blast_surface(board, x, y, damage):
    terrain = board.rterrain(x, y)
    if terrain == ICE:
        limit = 15
    elif terrain == BRIDGE and not getattr(board, 'bridges_cs', False):
        limit = 10 * (1 + board.elevation(x, y))
    else:
        return False
    from systems.notifications import hex_broadcast
    if draw('surface_draws', 1, limit, lambda: random.randint(1, limit)) > damage:
        if terrain == BRIDGE:
            hex_broadcast(board, x, y, 'The bridge at $H shudders from direct hit!')
        return False
    hex_broadcast(board, x, y, 'The ice breaks from the blast!' if terrain == ICE else 'The bridge at $H is blown apart!')
    break_surface(board, None, x, y, 'goes swimming as ice breaks!' if terrain == ICE else 'goes swimming as the bridge is blown apart!')
    return True
