"""Small command adapter for querying the three production tile costs."""
import argparse

from entities import map as terrain
from tools.path_cost_inputs import (
    COST_FUNCTIONS, positive_dimension, stored_elevation, terrain_value,
)


def _argument_parser():
    parser = argparse.ArgumentParser(description=(
        'Query a directed BTMux tile cost. WATER and ICE use signed negative '
        'floor depths; other elevations are positive. The legacy guard rejects '
        'a destination row at or beyond map width. Decorated FIRE/SMOKE overlay '
        'terrain is deferred and cannot be represented faithfully.'))
    parser.add_argument('--mode', required=True, choices=COST_FUNCTIONS)
    parser.add_argument('--size', required=True, nargs=2, metavar=('WIDTH', 'HEIGHT'),
                        help='positive map width and height')
    parser.add_argument('--from', dest='source_xy', required=True, nargs=2,
                        type=int, metavar=('X', 'Y'))
    parser.add_argument('--to', dest='destination_xy', required=True, nargs=2,
                        type=int, metavar=('X', 'Y'))
    for endpoint in ('source', 'destination'):
        parser.add_argument('--' + endpoint, required=True, nargs=2,
                            metavar=('TERRAIN', 'ELEVATION'),
                            help='symbolic terrain name and stored elevation 0-9')
    return parser


def _query_map(args):
    width, height = map(positive_dimension, args.size)
    source = (terrain_value(args.source[0]), stored_elevation(args.source[1]))
    destination = (terrain_value(args.destination[0]), stored_elevation(args.destination[1]))
    if args.source_xy == args.destination_xy and source != destination:
        raise ValueError('same-hex source and destination values must agree')
    game_map = terrain.GameMap(width, height)
    for coordinates, (terrain_code, elevation) in (
        (args.source_xy, source), (args.destination_xy, destination),
    ):
        if game_map.valid(*coordinates):
            game_map.set_terrain(*coordinates, terrain_code)
            game_map.set_elevation(*coordinates, elevation)
    return game_map


def main(argv=None):
    parser = _argument_parser()
    args = parser.parse_args(argv)
    try:
        game_map = _query_map(args)
    except ValueError as error:
        parser.error(str(error))
    cost = COST_FUNCTIONS[args.mode](game_map, *args.source_xy, *args.destination_xy)
    print(f'cost={cost}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
