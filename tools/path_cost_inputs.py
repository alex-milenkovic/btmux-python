"""Shared path-cost modes and input values for command and acceptance adapters."""
from entities import map as terrain
from physics.path_costs import mech_tile_cost, hover_tank_tile_cost, tracked_tank_tile_cost


COST_FUNCTIONS = {
    'mech': mech_tile_cost,
    'hover': hover_tank_tile_cost,
    'tracked': tracked_tank_tile_cost,
}
TERRAINS = {name: getattr(terrain, name) for name in (
    'GRASSLAND', 'LIGHT_FOREST', 'HEAVY_FOREST', 'WATER', 'HIGHWATER',
    'ROUGH', 'MOUNTAINS', 'ROAD', 'BUILDING', 'FIRE', 'TFIRE', 'SMOKE',
    'WALL', 'DESERT', 'BRIDGE', 'SNOW', 'ICE', 'UNKNOWN_TERRAIN')}


def terrain_value(name):
    if name not in TERRAINS:
        raise ValueError(f'unknown terrain: {name}')
    return TERRAINS[name]


def stored_elevation(value):
    result = int(value)
    if not 0 <= result <= terrain.MAX_ELEV:
        raise ValueError('stored elevation must be an integer from 0 through 9')
    return result


def positive_dimension(value):
    result = int(value)
    if result <= 0:
        raise ValueError('map dimensions must be positive integers')
    return result
