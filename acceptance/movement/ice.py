"""Movement ice acceptance bindings using production behavior."""
from unittest.mock import patch
from entities import map as terrain
from entities.map import GameMap
from physics import ice
from acceptance.movement.context import equal, set_hex, bounded_integer
from tools.path_cost_inputs import terrain_value


def candidate_neighbors(w, name, count, kind):
    count = bounded_integer(count, 0, 6, 'neighbor count')
    # Put candidate last in scan order; noncandidate ice is gated out by its
    # percentage draw, waterlike neighbors are bridges and never candidates.
    u = w['unit']
    w['map'].remove_mech(u)
    w['candidate'] = (3, 3)
    w['map'].set_terrain(3, 3, terrain_value(name))
    for xy in list(ice.neighbors(w['map'], 3, 3))[:count]:
        w['map'].set_terrain(*xy, terrain.BRIDGE if kind == 'waterlike' else terrain.ICE)
    w['single_candidate'] = True


def ice_random(w, percent, draw, die):
    w.update(percent=int(percent), draw=bounded_integer(draw, 1, 100, 'percentage draw'), die=int(die))


def evolve(w, operation):
    if operation not in ('growth', 'melting'):
        raise ValueError(f'Unknown ice operation: {operation}')
    board = w['map']
    if 'die' in w:
        bounded_integer(w['die'], 1, 6 if operation == 'growth' else 3, 'neighbor die')
    if w.get('single_candidate'):
        # Each percentage roll is tied to the actual eligible scan cell;
        # skip unrelated ICE neighbors through their percentage gate.
        source = terrain.WATER if operation == 'growth' else terrain.ICE
        candidates = [(x, y) for x in range(board.map_width) for y in range(board.map_height)
                      if board.rterrain(x, y) == source]
        percent_draws = iter(w['draw'] if xy == w['candidate'] else 100 for xy in candidates)
        draw = lambda lo, hi: next(percent_draws) if hi == 100 else w['die']
    elif 'neighbor_dice' in w:
        dice = iter(w['neighbor_dice'])
        draw = lambda lo, hi: w['draw'] if hi == 100 else next(dice)
    else:
        draw = lambda lo, hi: w.get('draw', 1) if hi == 100 else w['die']
    def checked_draw(lo, hi):
        return bounded_integer(draw(lo, hi), lo, hi, 'ice random draw')
    with patch.object(ice.random, 'randint', side_effect=checked_draw):
        w['count'] = (ice.ice_growth if operation == 'growth' else ice.ice_melt)(board, w['percent'])


def candidate_result(w, name, count):
    equal(w['map'].terrain(*w['candidate']), terrain_value(name))
    equal(w['count'], int(count))


def isolated_water(w, depth):
    w['map'].remove_mech(w['unit'])
    w['candidate'] = (3, 3)
    set_hex(w, 'WATER', depth, w['candidate'])


def ice_path(w, percent, height):
    from physics.path_costs import mech_tile_cost
    w['percent'] = int(percent)
    evolve(w, 'growth')
    w['map'].set_elevation(3, 2, int(height))
    w['cost'] = mech_tile_cost(w['map'], 3, 2, 3, 3)


def ice_path_result(w, depth, cost):
    equal((w['map'].terrain(3, 3), w['map'].elevation(3, 3), w['cost']), (terrain.ICE, int(depth), int(cost)))


def triangle(w):
    w['map'].remove_mech(w['unit'])
    for xy in ((3, 3), (3, 4), (4, 3)):
        set_hex(w, 'WATER', xy=xy)


def triangle_dice(w, percent, draw, first, second, third):
    w.update(percent=int(percent), draw=bounded_integer(draw, 1, 100, 'percentage draw'),
             neighbor_dice=[bounded_integer(die, 1, 6, 'neighbor die') for die in (first, second, third)])


def triangle_result(w, name, count):
    equal([w['map'].terrain(*xy) for xy in ((3, 3), (3, 4), (4, 3))], [terrain_value(name), terrain.WATER, terrain.WATER])
    equal(w['count'], int(count))


def ice_square(w, side, depth):
    w['map'] = GameMap(int(side), int(side))
    for x in range(int(side)):
        for y in range(int(side)):
            set_hex(w, 'ICE', depth, (x, y))


def melt_square(w, percent, draw):
    w.update(percent=int(percent), draw=bounded_integer(draw, 1, 100, 'percentage draw'))
    evolve(w, 'melting')


def count_surfaces(w, water, ice_count):
    board = w['map']
    cells = [board.terrain(x, y) for x in range(board.map_width) for y in range(board.map_height)]
    equal((cells.count(terrain.WATER), cells.count(terrain.ICE)), (int(water), int(ice_count)))


BINDINGS = [
    (r'one (WATER|ICE) candidate with (\d+) (waterlike|ICE) neighbors and all other hexes GRASSLAND', candidate_neighbors),
    (r'ice percentage ([-\d]+) percentage draw (\d+) and neighbor die (\d+)', ice_random),
    (r'ice (growth|melting) runs', evolve),
    (r'candidate terrain is (\w+) and changed hex count is (\d+)', candidate_result),
    (r'a WATER hex at stored depth (\d+) and no waterlike neighbors', isolated_water),
    (r'ice growth at (\d+) percent runs and a mech path cost from adjacent GRASSLAND at height (\d+) is queried', ice_path),
    (r'candidate terrain is ICE stored depth is (\d+) and mech path cost is (\d+)', ice_path_result),
    (r'WATER at 3 3 and 3 4 and 4 3 on an otherwise empty GRASSLAND map', triangle),
    (r'growth percentage (\d+) with percentage draws (\d+) and neighbor dice (\d+) then (\d+) then (\d+)', triangle_dice),
    (r'terrain at 3 3 is (\w+) and at 3 4 and 4 3 is WATER with changed hex count (\d+)', triangle_result),
    (r'an empty square ICE map of side (\d+) with stored elevation (\d+)', ice_square),
    (r'melting at (\d+) percent runs with percentage draws (\d+)', melt_square),
    (r'WATER hex count is (\d+) and ICE hex count is (\d+)', count_surfaces),
]
