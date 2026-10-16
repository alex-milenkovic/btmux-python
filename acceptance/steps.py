"""Regex step bindings; all example values reach setup or assertions."""
import re

from entities.map import GameMap
from tools.path_cost_inputs import (
    COST_FUNCTIONS, positive_dimension, stored_elevation, terrain_value,
)


def create_map(world, width, height):
    world['map'] = GameMap(positive_dimension(width), positive_dimension(height))
    terrain, elevation = world.get('default', ('GRASSLAND', '0'))
    for y in range(world['map'].map_height):
        for x in range(world['map'].map_width):
            world['map'].set_terrain(x, y, terrain_value(terrain))
            world['map'].set_elevation(x, y, stored_elevation(elevation))


def default_terrain(world, name, elevation):
    terrain_value(name)
    stored_elevation(elevation)
    world['default'] = (name, elevation)


def coordinates(world, fx, fy, tx, ty):
    world['source'] = (int(fx), int(fy))
    world['destination'] = (int(tx), int(ty))


def fresh_map(world, width, height, fx, fy, tx, ty):
    create_map(world, width, height)
    coordinates(world, fx, fy, tx, ty)


def endpoint_terrain(world, endpoint, name, elevation):
    position = world[endpoint]
    world['map'].set_terrain(*position, terrain_value(name))
    world['map'].set_elevation(*position, stored_elevation(elevation))


def request_cost(world, mode):
    world['costs'] = [COST_FUNCTIONS[mode](world['map'], *world['source'], *world['destination'])]


def request_all(world):
    world['costs'] = [function(world['map'], *world['source'], *world['destination'])
                      for function in COST_FUNCTIONS.values()]


def expect_cost(world, expected):
    expected = int(expected)
    if not world['costs'] or any(cost != expected for cost in world['costs']):
        raise AssertionError(f"expected {expected}, got {world['costs']}")


BINDINGS = [
    (r'all map hexes are (\w+) with stored elevation (-?\d+)', default_terrain),
    (r'map dimensions (-?\d+) by (-?\d+)', create_map),
    (r'source coordinates (-?\d+) (-?\d+) and destination coordinates (-?\d+) (-?\d+)', coordinates),
    (r'a fresh (-?\d+) by (-?\d+) path-cost map with source at (-?\d+) (-?\d+) and destination at (-?\d+) (-?\d+)', fresh_map),
    (r'(source|destination) terrain (\w+) with stored elevation (-?\d+)', endpoint_terrain),
    (r'the (mech|hover|tracked) path cost is requested', request_cost),
    (r'all three path costs are requested', request_all),
    (r'(?:the|each) path cost is (-?\d+)', expect_cost),
]


def execute_step(world, text, example):
    def resolve(match):
        value = example[match.group(1)]
        if not isinstance(value, str):
            raise ValueError('example values must be strings')
        return value

    expanded = re.sub(r'<([A-Za-z0-9_]+)>', resolve, text)
    if 'hud_status' in world or expanded=='a fresh HUD display session with ready units and event time zero':
        from acceptance.hud_status import execute
        return execute(world,expanded)
    if 'repair_economy' in world or expanded=='the repair economy source contract and isolated shared engine fixture':
        from acceptance.repair_economy import execute
        return execute(world,expanded)
    from acceptance.six_location_aerofighters import BACKGROUNDS as FIGHTER_BACKGROUNDS
    if 'six_location_aerofighters' in world or expanded in FIGHTER_BACKGROUNDS:
        from acceptance.six_location_aerofighters import execute
        return execute(world,expanded)
    from acceptance.aerospace import BACKGROUNDS as AERO_BACKGROUNDS
    if 'aerospace' in world or expanded in AERO_BACKGROUNDS:
        from acceptance.aerospace import execute
        return execute(world,expanded)
    from acceptance.c3_communications import BACKGROUNDS as C3_BACKGROUNDS
    if 'c3_communications' in world or expanded in C3_BACKGROUNDS:
        from acceptance.c3_communications import execute
        return execute(world,expanded)
    if 'pilots' in world or expanded in (
        'an isolated public CLI process with independently derived source inputs and writable scratch storage',
        'eight-section battle armor using shared source piloting damage and map membership',
        'ordinary battle armor controls on a source map with normal clock and LOS consumers',
        'a valid source-backed local pilot in an IC map with a loadable MechWarrior template',
        'source-valid co-located units with ordered local occupants and empty enter locks',
        'a source-valid IC carrier and started allied embarking unit with no recycle and free cargo measured in hundredths of tons',
        'a connected in-character pilot and distinct live in-character enemy with valid source skill identities at wall time101 and last skill use0',
        'an attached pilot with Build5 and ordinary simulation recovery events',
        'source personal armor metadata with strict finite Number streams and C integer arithmetic',
        'a genuine project-local MechWarrior template and source-backed character record',
        'an isolated character registry using the complete source value table and production storage',
        'source character attributes Build5 Reflexes4 Intuition3 Learn2 Charisma1 unless overridden',
        'a source character with Gunnery-Battlemech raw BTH4 threshold3000 and XP_MAX16777216'):
        from acceptance.pilots import BINDINGS as PILOT_BINDINGS
        for pattern,handler in PILOT_BINDINGS:
            match=re.fullmatch(pattern,expanded)
            if match:handler(world,*match.groups());return
        raise AssertionError(f'unsupported pilot step: {expanded}')
    if 'template_catalog' in world or expanded.startswith('an isolated template catalog session'):
        from acceptance.template_catalog import BINDINGS as TEMPLATE_CATALOG_BINDINGS
        for pattern,handler in TEMPLATE_CATALOG_BINDINGS:
            match=re.fullmatch(pattern,expanded)
            if match:
                handler(world,*match.groups());return
        raise AssertionError(f'unsupported template catalog step: {expanded}')
    if 'construction_templates' in world or expanded.startswith('a fresh construction session'):
        from acceptance.construction_templates import BINDINGS as CONSTRUCTION_BINDINGS
        for pattern,handler in CONSTRUCTION_BINDINGS:
            match=re.fullmatch(pattern,expanded)
            if match:
                handler(world,*match.groups())
                return
        raise AssertionError(f'unsupported construction step: {expanded}')
    if 'maps_environment' in world or expanded.startswith('a fresh maps environment session'):
        from acceptance.maps_environment import BINDINGS as MAP_BINDINGS
        for pattern,handler in MAP_BINDINGS:
            match=re.fullmatch(pattern,expanded)
            if match:
                handler(world,*match.groups())
                return
        raise AssertionError(f'unsupported maps environment step: {expanded}')
    if 'core_engine' in world or expanded.startswith('a fresh core simulation session'):
        from acceptance.core_simulation import BINDINGS as CORE_BINDINGS
        for pattern, handler in CORE_BINDINGS:
            match = re.fullmatch(pattern, expanded)
            if match:
                handler(world, *match.groups())
                return
        raise AssertionError(f'unsupported core step: {expanded}')
    if 'combat_session' in world or expanded.startswith('a fresh combat session'):
        from acceptance.combat_resolution import BINDINGS as COMBAT_BINDINGS
        for pattern, handler in COMBAT_BINDINGS:
            match = re.fullmatch(pattern, expanded)
            if match:
                handler(world, *match.groups())
                return
        raise AssertionError(f'unsupported combat step: {expanded}')
    if 'damage_session' in world or expanded.startswith('a fresh damage session'):
        from acceptance.damage_criticals import BINDINGS as DAMAGE_BINDINGS
        for pattern, handler in DAMAGE_BINDINGS:
            match = re.fullmatch(pattern, expanded)
            if match:
                handler(world, *match.groups())
                return
        raise AssertionError(f'unsupported damage step: {expanded}')
    if 'sensor_session' in world or expanded.startswith('a fresh sensor session'):
        from acceptance.sensors_los import BINDINGS as SENSOR_BINDINGS
        for pattern, handler in SENSOR_BINDINGS:
            match = re.fullmatch(pattern, expanded)
            if match:
                handler(world, *match.groups())
                return
        raise AssertionError(f'unsupported sensor step: {expanded}')
    from acceptance.movement_steps import BINDINGS as MOVEMENT_BINDINGS
    from acceptance.heat_updates import BINDINGS as HEAT_BINDINGS
    for pattern, handler in BINDINGS + MOVEMENT_BINDINGS + HEAT_BINDINGS:
        match = re.fullmatch(pattern, expanded)
        if match:
            handler(world, *match.groups())
            return
    raise AssertionError(f'unsupported step: {expanded}')
