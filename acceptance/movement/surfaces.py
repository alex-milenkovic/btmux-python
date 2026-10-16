"""Movement surfaces acceptance bindings using production behavior."""
from unittest.mock import patch
from entities import map as terrain
from entities.mech import Mech, MechStatus as S, UnitType, MoveType
from physics import ice
from acceptance.movement.context import boolean, equal, psr, set_hex, bounded_integer
from tools.path_cost_inputs import terrain_value


def surface_target(w, name, elevation, protected):
    w['target_xy'] = (4, 4)
    set_hex(w, name, elevation, w['target_xy'])
    w['map'].bridges_cs = boolean(protected)


def blast(w, damage, draw):
    from entities.weapon import get_weapon_by_index
    from systems.combat import hex_hit
    # Registered weapon definition supplies the C weapon-index lookup.
    weapon = get_weapon_by_index(0)
    value = int(draw)
    if value < 1:
        raise ValueError(f'surface draw must be positive: {draw}')
    def checked_draw(lo, hi):
        return bounded_integer(value, lo, hi, 'surface draw')
    with patch.object(weapon, 'damage', int(damage)), patch.object(ice.random, 'randint', side_effect=checked_draw):
        w['unit'].set_status(S.LOCK_HEX)
        hex_hit(w['unit'], *w['target_xy'], 0, 0, int(damage), 1)


def surface_result(w, name, elevation):
    equal((w['map'].terrain(*w['target_xy']), w['map'].elevation(*w['target_xy'])), (terrain_value(name), int(elevation)))


def other_occupant(w, depth, kind, move, z, waterproof):
    set_hex(w, 'ICE', depth)
    if int(z) < w['map'].base_elevation(w['unit'].x, w['unit'].y):
        raise ValueError('occupant height is below the stored floor')
    w['unit'].z = -1
    other = Mech.create_test_mech()
    other.unit_type, other.move_type = UnitType[kind], MoveType[move]
    other.set_hex_position(w['unit'].x, w['unit'].y, int(z))
    other.specials2 = 0x100000 if boolean(waterproof) else 0
    w['map'].add_mech(other)
    w['other'] = other


def break_below(w):
    from physics.movement import break_thru_ice
    with psr(w):
        break_thru_ice(w['unit'])


def other_result(w, levels, destroyed):
    other = w['other']
    equal((other.terrain, getattr(other, 'last_fall_levels', 0), other.is_destroyed), (terrain.WATER, int(levels), boolean(destroyed)))


def ice_unit(w, kind, move, depth):
    w['unit'].unit_type, w['unit'].move_type = UnitType[kind], MoveType[move]
    set_hex(w, 'ICE', depth)


def chance(w, die):
    from physics.movement import possibly_drop_thru_ice
    with patch('physics.movement.random.randint', return_value=bounded_integer(die, 1, 6, 'ice drop die')), psr(w):
        w['dropped'] = bool(possibly_drop_thru_ice(w['unit']))


def chance_result(w, name, dropped):
    equal((w['map'].terrain(w['unit'].x, w['unit'].y), w['dropped']), (terrain_value(name), boolean(dropped)))


BINDINGS = [
    (r'target terrain (\w+) stored elevation (\d+) and bridge protection (True|False)', surface_target),
    (r'a weapon of damage (\d+) hits the hex with surface draw (\d+)', blast),
    (r'target terrain is (\w+) and stored elevation is (\d+)', surface_result),
    (r'ICE at stored depth (\d+) with another occupant of class (\w+) movement (\w+) height ([-\d]+) waterproof (True|False)', other_occupant),
    (r'the triggering unit breaks through from below', break_below),
    (r'the other occupant has cached terrain WATER fall levels (\d+) and destroyed state (True|False)', other_result),
    (r'a unit of class (\w+) movement (\w+) on depth (\d+) ICE', ice_unit),
    (r'the drop through ice chance uses die (\d+)', chance),
    (r'shared terrain is (\w+) and drop happened is (True|False)', chance_result),
]
