"""Movement context acceptance bindings using production behavior."""
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from unittest.mock import patch
from entities.map import GameMap
from entities.mech import Mech, MechStatus as S, MechStatus2 as S2
from entities.pilot import Pilot
from core.game_loop import GameEngine
from tools.path_cost_inputs import terrain_value, stored_elevation

FLAGS = {'NONE': S2.NONE, 'SPRINT': S2.SPRINTING, 'EVADE': S2.EVADING, 'DODGE': S2.DODGING}


from acceptance.assertions import boolean, equal, near


def bounded_integer(value, minimum, maximum, label):
    result = int(value)
    if not minimum <= result <= maximum:
        raise ValueError(f'{label} must be from {minimum} through {maximum}: {value}')
    return result


def set_hex(w, name, depth=0, xy=None):
    unit, board = w['unit'], w['map']
    x, y = xy or (unit.x, unit.y)
    board.set_terrain(x, y, terrain_value(name))
    board.set_elevation(x, y, stored_elevation(depth))
    if (unit.x, unit.y) == (x, y):
        unit.elev = int(depth)


def psr(w, success=True):
    from systems.piloting import PilotingResult
    return patch('systems.piloting.make_piloting_roll', return_value=PilotingResult(success=success))


def advance(w, ticks):
    with ExitStack() as stack:
        if 'roll' in w:
            from core.randomness import use_source
            stack.enter_context(use_source(lambda name,low,high,fallback: int(w['roll']) if name=='pilot_rolls' else fallback()))
        # The real event loop deliberately logs callback errors and continues.
        # An acceptance example must not pass on a partially executed event.
        output = StringIO()
        with redirect_stdout(output):
            w['engine'].run_ticks(int(ticks))
        captured = output.getvalue()
        assert 'raised exception:' not in captured.casefold(), captured


def fresh(w):
    unit = Mech.create_test_mech()
    unit.set_status(S.STARTED)
    unit.pilot = Pilot()
    unit.pilot.dodge_maneuver = True
    unit.pilot.maneuvering_ace = True
    unit.measured_mass = unit.tonnage * 1024
    unit.set_hex_position(3, 3)
    board = GameMap(12, 12)
    board.add_mech(unit)
    engine = GameEngine()
    engine.register_entity(unit)
    unit._engine = engine
    w.update(unit=unit, map=board, engine=engine)


BINDINGS = [
    (r'a fresh movement session with the standard ready unit and clear map', fresh),
]
