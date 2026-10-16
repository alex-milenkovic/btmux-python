# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mine.c

"""Map mine objects, coverage, contact and channel detonation (mine.c)."""
from dataclasses import dataclass
from enum import IntEnum
import random

from core.randomness import draw
from entities.map import ICE
from physics.hexmath import hex_distance
from systems.damage import blast_hit_hexes, TABLE_KICK
from systems.movement_commands import notify
from systems.combat_commands import read_number, parse_attributes, command_message
from core.effects import notify_actor, emit_channel, did_it


class MineType(IntEnum):
    STANDARD = 1
    INFERNO = 2
    COMMAND = 3
    VIBRA = 4
    TRIGGER = 5


@dataclass(eq=False)
class Mine:
    x: int
    y: int
    type: MineType
    strength: int
    extra: int = 0
    creator: int = 0
    mapobj_type: int = 0  # Native record byte; datac remains the logical mine kind.


def real_tons(unit):
    return int(unit.rtons / 1024)


def recalculate_minefields(board):
    covered = set()
    for mine in board.mines:
        if mine.type not in tuple(MineType):
            continue
        distance = int((100 - mine.extra) / 10)
        if mine.type == MineType.TRIGGER:
            radius = mine.extra
        elif mine.type == MineType.VIBRA and distance:
            radius = distance
        else:
            covered.add((mine.x, mine.y))
            continue
        for x in range(mine.x-radius, mine.x+radius+1):
            for y in range(mine.y-radius, mine.y+radius+1):
                if not board.valid(x, y):
                    continue
                inside = (round(hex_distance(mine.x, mine.y, x, y)) <= radius
                          if mine.type == MineType.TRIGGER else
                          abs(x-mine.x)+abs(y-mine.y) <= int(distance*3/2))
                if inside:
                    covered.add((x, y))
    board.mine_hexes = covered
    from entities.map_objects import sync_mine_bits
    sync_mine_bits(board,covered)


def add_mine(board, x, y, damage):
    if not board.valid(x, y):
        return None
    if (x,y) in board.mine_hexes and any((mine.x, mine.y) == (x, y) for mine in board.mines):
        return None
    mine = Mine(x, y, MineType.STANDARD, (int(damage)+32768)%65536-32768)
    board.mines.insert(0,mine)
    board.flags |= 1
    return mine


def map_add_mine(board, text, creator=0, *, caller=None):
    if board is None:
        return None
    actor=creator if caller is None else caller
    try:
        args = parse_attributes(text,6)
        if len(args) not in (4, 5):
            raise ValueError('Invalid arguments!')
        x, y, strength = (read_number(args[i]) for i in (0, 1, 3))
        extra = read_number(args[4]) if len(args) == 5 else 0
        try:
            kind = MineType[args[2].upper()]
        except KeyError as error:
            raise ValueError('Invalid mine type!') from error
        if not board.valid(x, y):
            raise ValueError('X,Y out of range!')
    except ValueError as error:
        notify_actor(board,actor,str(error))
        raise
    mine = Mine(x, y, kind, (strength+32768)%65536-32768, extra, creator)
    board.mines.insert(0,mine)
    board.flags |= 1
    notify_actor(board,actor,f'{kind.name.title()} mine added to ({x},{y}) (strength: {strength} / extra: {extra})')
    recalculate_minefields(board)
    return mine


def make_mine_explode(unit, board, mine, x, y, reason):
    from systems.sensors import los_broadcast
    from systems.notifications import hex_broadcast
    from systems.parts import mech_ids
    if mine.type == MineType.TRIGGER:
        if reason not in ('step', 'land'):
            return False
        emit_channel(unit,'MineTriggers',f'#{unit._id} {mech_ids(unit)} activated trigger at {mine.x},{mine.y}.')
        if unit._id>0:
            did_it(unit,unit,unit,awhat='A_AMINETRIGGER')
        return True
    if mine.type == MineType.COMMAND:
        hex_broadcast(board,mine.x,mine.y,'A mine explodes in $H!')
    elif reason == 'step':
        los_broadcast(unit,f'moves to {x},{y}, and triggers a mine!')
        notify(unit,f'As you move to {x},{y}, you trigger a mine!')
    elif reason in ('land','fall','drop'):
        los_broadcast(unit,'triggers a mine!')
        notify(unit,'You trigger a mine!')
    if mine.type not in (MineType.STANDARD,MineType.INFERNO,MineType.COMMAND,MineType.VIBRA):
        recalculate_minefields(board)
        return False
    persistent = mine.strength >= 5
    if mine.type in (MineType.STANDARD, MineType.INFERNO):
        reduced = int(mine.strength * 2 / 3)
        if reduced >= 5:
            mine.strength = reduced
    inferno = mine.type == MineType.INFERNO
    armor = int(mine.strength / 3) if inferno else mine.strength
    heat = mine.strength if inferno else 0
    neighbors = mine.type in (MineType.COMMAND, MineType.VIBRA)
    if neighbors:
        # unset_hex_mine is observable before blast damage/terrain callbacks.
        from entities.map_objects import bits_for
        board.mine_hexes.discard((mine.x,mine.y))
        bits=bits_for(board,False)
        if bits is not None:bits.unset(mine.x,mine.y,1)
        if mine.type==MineType.VIBRA and (mine.x,mine.y)!=(x,y):
            hex_broadcast(board,mine.x,mine.y,'A mine explodes in $H!')
    message = 'Globs of flaming gel hit you!' if inferno else 'A blast of shrapnel hits you!'
    observer = 'is hit by globs of flaming gel!' if inferno else 'is hit by shrapnel!'
    blast_hit_hexes(board, armor, 5, heat, mine.x, mine.y, message, observer,
                    'A little blast of shrapnel hits you!' if neighbors else None,
                    'is hit by some of the shrapnel!' if neighbors else None,
                    TABLE_KICK, 2, 1, True, 1, engine=getattr(unit, '_engine', None))
    if neighbors or not persistent:
        # mapobj_del removes every object at these coordinates, preserving list identity.
        board.mines[:] = [other for other in board.mines if (other.x,other.y)!=(mine.x,mine.y)]
    recalculate_minefields(board)
    return True


def possible_mine_explosion(unit, board, x, y, reason):
    count = 0
    tons = real_tons(unit)
    bounding = int((tons-20)/10)
    for mine in list(board.mines):
        if mine not in board.mines:continue
        same_hex = (mine.x, mine.y) == (x, y)
        if same_hex:
            if mine.type == MineType.TRIGGER and mine.strength > tons:
                continue
            if mine.type == MineType.VIBRA and mine.extra > tons:
                continue
            if mine.type == MineType.COMMAND:
                notify(unit, 'You spot small bomblets lying on the ground here..')
                continue
        elif mine.type == MineType.TRIGGER:
            if mine.strength > tons or round(hex_distance(x, y, mine.x, mine.y)) > mine.extra:
                continue
        elif mine.type == MineType.VIBRA:
            if (mine.extra >= tons or abs(mine.x-x) > bounding or abs(mine.y-y) > bounding
                    or hex_distance(x, y, mine.x, mine.y) > int((tons-mine.extra)/10)):
                continue
        else:
            continue
        count += make_mine_explode(unit, board, mine, x, y, reason)
    return count


def possible_mine_poof(unit, reason):
    board = unit.map
    x, y = unit.x, unit.y
    if board is None or (x, y) not in board.mine_hexes:
        return 0
    floor = 0 if board.rterrain(x, y) == ICE else board.base_elevation(x, y)
    if unit.z > floor:
        return 0
    return possible_mine_explosion(unit, board, x, y, reason)


def explode_mines(unit, channel):
    board = unit.map
    if board is None:
        return 0
    count = 0
    for mine in list(board.mines):
        if mine not in board.mines:continue
        if mine.type == MineType.COMMAND and mine.extra == channel:
            count += make_mine_explode(unit, board, mine, 0, 0, None)
    if count:recalculate_minefields(board)
    return count


def possibly_remove_mines(unit, x, y):
    """The executable C body deliberately leaves all mine objects untouched."""


def show_mines_in_hex(unit, distance, x, y, *, caller=None):
    board = unit.map
    def nothing():
        command_message(unit,'You see nothing else of interest in the hex, either.',caller=caller)
        return False
    if board is None or (x, y) not in board.mine_hexes:
        return nothing()
    if not any((mine.x, mine.y) == (x, y) for mine in board.mines):
        return nothing()
    if draw('mine_discovery', 2, 9, lambda: random.randint(2, 9)) < int(distance):
        return nothing()
    from systems.experience import perception
    if not perception(unit,0):
        return nothing()
    notify(unit, 'Small bomblets litter the hex, interesting... You vaguely recall them from some class or other.')
    return True
