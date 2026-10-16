# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/artillery.c
#   btech/mech.bth.c
#   btech/mech.notify.c
#   btech/mech.utils.c

"""Captured artillery projectiles and impact resolution from artillery.c."""
from dataclasses import dataclass
import math
import random

from core.events import EventType
from core.randomness import draw
from entities.mech import AmmoMode as A
from entities.weapon import get_weapon_by_index
from physics.hexmath import hex_to_float, hex_distance, hex_distance_int, find_bearing
from systems.damage import blast_hit_hexf, TABLE_GEN, TABLE_PUNCH
from systems.movement_commands import notify
from systems.sensors import los_broadcast


@dataclass(frozen=True)
class ArtilleryShot:
    from_x: int
    from_y: int
    to_x: int
    to_y: int
    weapon_index: int
    mode: int
    is_hit: bool
    shooter_id: int
    board: object


def number(name, low, high):
    return draw(name, low, high, lambda: random.randint(low, high))


def artillery_type(shot):
    from entities.source_weapon_numbers import SOURCE_WEAPON_NAMES
    weapon=get_weapon_by_index(shot.weapon_index)
    return 'a missile' if weapon and weapon.name in (SOURCE_WEAPON_NAMES[27],SOURCE_WEAPON_NAMES[71]) else 'a round'


def artillery_direction(bearing):
    directions = ((0,'north'),(60,'northeast'),(90,'east'),(120,'southeast'),
                  (180,'south'),(240,'southwest'),(270,'west'),(300,'northwest'))
    return min(directions, key=lambda entry: abs(bearing-entry[0]))[1]


def flight_time(distance):
    return max(10, int(distance/5))


def artillery_round_flight_time(fx, fy, tx, ty):
    from physics.hexmath import find_range
    return flight_time(find_range(fx, fy, tx, ty))


def artillery_bth(unit, section, weapon, distance, indirect):
    from entities.mech import Location as L, MoveType
    from systems.piloting import find_pilot_spotting, find_pilot_arty_gun
    submerged = unit.z < 0 and (unit.z < -1 or unit.is_fallen or
        section in (L.LLEG,L.RLEG) or unit.move_type==MoveType.QUAD and section in (L.LARM,L.RARM))
    if submerged:
        return 5000
    from systems.combat_ranges import extreme_range
    if distance > extreme_range(unit,weapon):
        return 1000
    result = 11+find_pilot_arty_gun(unit)-4
    if indirect:
        engine=unit._engine
        roster=engine.get_entities() if engine else getattr(unit.map,'mechs_on_map',[])
        from systems.targeting import resolve_unit
        spotter=resolve_unit(unit,unit.spotter,engine)
        if spotter is not None and spotter is not unit:
            result += int((find_pilot_spotting(spotter)-4)/2)
        if unit.spotter in (-1,unit._id):
            result += 1
    else:
        result -= 2
    return result-unit.fire_adjustment


def artillery_shoot(engine, unit, x, y, weapon_index, mode, is_hit):
    shot = ArtilleryShot(unit.x, unit.y, x, y, weapon_index, mode,
                         bool(is_hit), unit._id, unit.map)
    if unit.map is None or get_weapon_by_index(weapon_index) is None:
        raise ValueError('Artillery requires a map and known weapon')
    # Capture the map object identity, and attach the event to the shot rather
    # than the unit so unit destruction/unregistration cannot cancel it.
    unit.map.projectiles.append(shot)
    bearing = find_bearing(*hex_to_float(unit.x,unit.y), *hex_to_float(x,y))
    los_broadcast(unit, f'shoots {artillery_type(shot)} towards the {artillery_direction(bearing)}!')
    engine.events.schedule(flight_time(hex_distance(unit.x,unit.y,x,y)),
                           EventType.ARTILLERY_HIT, artillery_hit_event, shot, engine)
    return shot


def artillery_hit_event(event):
    shot, engine = event.data, event.data2
    if shot in shot.board.projectiles:
        shot.board.projectiles.remove(shot)
    if any(entity is shot.board for entity in engine.get_entities()):
        artillery_hit(engine, shot)


def neighbors(board, x, y):
    from entities.map import neighbors as source_neighbors
    yield from source_neighbors(board,x,y)


def artillery_hit_hex(engine, shot, damage, x, y, direct=True):
    board = shot.board
    if not board.valid(x,y):
        return
    if shot.mode & A.SMOKE_MODE:
        from physics.decorations import add_smoke
        add_smoke(engine,board,x,y,number('smoke_duration',90,150))
        return
    if shot.mode & A.MINE_MODE:
        from systems.mines import add_mine
        add_mine(board,x,y,damage)
        return
    cluster = bool(shot.mode & A.CLUSTER_MODE)
    noun = ('bomblets' if damage>2 else 'a bomblet') if cluster else 'fragments'
    owner_message = 'You receive a direct hit!' if direct and not cluster else f'You are hit by {noun}!'
    observer_message = 'receives a direct hit!' if direct and not cluster else f'is hit by {noun}!'
    fx,fy = hex_to_float(x,y)
    blast_hit_hexf(board,damage,2 if cluster else 5,0,fx,fy,fx,fy,
                    owner_message, observer_message,
                    TABLE_PUNCH if cluster else TABLE_GEN,10,4,False,engine=engine)


def artillery_hit_neighbors(engine, shot, damage, x, y):
    for nx,ny in neighbors(shot.board,x,y):
        artillery_hit_hex(engine,shot,damage,nx,ny,False)


def artillery_cluster_hit(engine, shot, damage, x, y):
    targets = {}
    for _ in range(damage):
        while True:
            nx = x+number('artillery_cluster',-2,0)+number('artillery_cluster',0,2)
            ny = y+number('artillery_cluster',-2,0)+number('artillery_cluster',0,2)
            if shot.board.valid(nx,ny):
                break
        targets[nx,ny] = targets.get((nx,ny),0)+2
    for (nx,ny), total in sorted(targets.items()):
        artillery_hit_hex(engine,shot,total,nx,ny)


def artillery_friendly_adjustment(engine, shooter_id, board, x, y):
    from systems.targeting import find_mech_in_hex
    from systems.notifications import sees_hex, identity, mech_notify, MECHSTARTED
    roster = engine.get_entities()
    from entities.mech import Mech
    shooter = next((u for u in roster if isinstance(u,Mech) and u._id==shooter_id),None)
    if shooter is None:
        return
    from systems.targeting import resolve_unit
    spotter=resolve_unit(shooter,shooter.spotter,engine)
    if (shooter.targ_x,shooter.targ_y)!=(x,y) and not (spotter and (spotter.targ_x,spotter.targ_y)==(x,y)):
        return
    if spotter:
        observer = spotter if sees_hex(spotter,board,x,y) else None
    else:
        observer = find_mech_in_hex(shooter,board,x,y,2)
    if observer is None or not observer.is_started or not shooter.is_started:
        return
    if spotter:
        mech_notify(shooter,MECHSTARTED,f'{identity(shooter,spotter)} sent you some trajectory-correction data.')
        mech_notify(spotter,MECHSTARTED,f'You provide {identity(spotter,shooter)} with information about the miss.')
    shooter.fire_adjustment += 1


def hex_los_broadcast(board,x,y,message):
    """Shared HexLOSBroadcast with source recipient and substitution semantics."""
    from systems.notifications import hex_broadcast
    return hex_broadcast(board,x,y,message)


def artillery_hit(engine, shot):
    board = shot.board
    x,y = shot.to_x,shot.to_y
    weapon = get_weapon_by_index(shot.weapon_index)
    if not shot.is_hit:
        direction = number('artillery_scatter_direction',0,359)*0.0174533
        distance = number('artillery_scatter_distance',2,7)
        weight = int(100*(distance*6)/(distance*6+board.windspeed))
        # C computes a wind-adjusted integer direction after its radians,
        # then never uses that new direction for the impact coordinates.
        distance = int((distance*weight+int(board.windspeed/6)*(100-weight))/100)
        x = max(0,min(board.map_width-1,int(x+distance*math.cos(direction))))
        y = max(0,min(board.map_height-1,int(y+distance*math.sin(direction))))
    board.artillery_impacts.append(dict(x=x,y=y,weapon_index=shot.weapon_index,mode=int(shot.mode)))
    if shot.mode & A.CLUSTER_MODE:
        message = "A rain of small bomblets hits $H's surroundings!"
    elif shot.mode & A.MINE_MODE:
        message = 'A rain of small bomblets hits $H!'
    elif shot.mode & A.SMOKE_MODE:
        message = f'A {weapon.name[3:]} {artillery_type(shot)[2:]} hits $h, and smoke starts to billow!'
    else:
        message = f'{weapon.name[3:]} fire hits $H!'
    board.combat_messages.append(dict(x=x,y=y,message=message))
    hex_los_broadcast(board,x,y,message)
    if shot.mode & A.CLUSTER_MODE:
        artillery_cluster_hit(engine,shot,weapon.damage,x,y)
    else:
        artillery_hit_hex(engine,shot,weapon.damage,x,y)
        if not shot.mode & A.MINE_MODE:
            artillery_hit_neighbors(engine,shot,int(weapon.damage/2),x,y)
    if not shot.is_hit:
        artillery_friendly_adjustment(engine,shot.shooter_id,board,shot.to_x,shot.to_y)
