"""Movement controls acceptance bindings using production behavior."""
from entities.mech import UnitType, MoveType
from systems import movement_commands as commands
from acceptance.movement.context import advance, boolean, equal, near


def speed_text(w, maximum, request):
    w['unit'].max_speed = float(maximum)
    w['speed_text'] = request


def speed_request(w):
    w['command'] = commands.speed(w['engine'], w['unit'], w['speed_text'])
    assert w['command'][0], w['command']


def speeds(w, desired, actual):
    near(w['unit'].desired_speed, desired)
    near(w['unit'].speed, actual)


def heading_lateral(w, heading, lateral, ticks):
    from systems.maneuver import set_lateral
    result = commands.heading(w['engine'], w['unit'], heading)
    assert result[0], result
    result = set_lateral(w['engine'], w['unit'], lateral)
    assert result[0] or result[1] == 'You are going that way already!', result
    advance(w, ticks)


def lateral_result(w, heading, offset, description):
    from systems.maneuver import LATERAL_NAMES
    equal((w['unit'].desired_facing, w['unit'].lateral, LATERAL_NAMES[w['unit'].lateral]),
          (int(heading), int(offset), description))


def pending_lateral(w, offset, request):
    from systems.maneuver import set_lateral
    w['unit'].lateral = int(offset)
    result = set_lateral(w['engine'], w['unit'], request)
    assert result[0], result


def replace_lateral(w, now, request, tick):
    from systems.maneuver import set_lateral
    advance(w, now)
    result = set_lateral(w['engine'], w['unit'], request)
    assert result[0], result
    advance(w, int(tick) - int(now))


def pending_lateral_result(w, offset, pending):
    equal(w['unit'].lateral, int(offset))
    equal(commands.pending(w['unit'], '_lateral_event'), boolean(pending))


def vtol(w, maximum, desired):
    w['unit'].unit_type = UnitType.VTOL
    w['unit'].move_type = MoveType.VTOL
    w['unit'].max_speed = float(maximum)
    w['unit'].desired_speed = float(desired)
    w['unit'].fuel = 100


def vertical_request(w, speed):
    w['command'] = commands.vertical(w['engine'], w['unit'], speed)


def vertical_result(w, outcome, speed):
    equal(w['command'][0], outcome == 'ACCEPTED')
    near(w['unit'].vertical_speed, speed)


def eta_target(w, distance, speed):
    from physics.hexmath import hex_to_float
    u = w['unit']
    u.targ_x, u.targ_y, u.target = 3, 3 + int(distance), -1
    u.fx, u.fy = hex_to_float(3, 3)
    u.speed = float(speed)


def eta_request(w):
    w['command'] = commands.eta(w['engine'], w['unit'])


def eta_result(w, text):
    assert text in w['command'][1], w['command']


BINDINGS = [
    (r'maximum speed ([-.\d]+) KPH and requested speed text (\S+)', speed_text),
    (r'the pilot uses the speed command', speed_request),
    (r'desired speed is ([-.\d]+) KPH and actual speed remains ([-.\d]+) KPH', speeds),
    (r'the pilot requests heading ([-\d]+) and lateral (\S+) then advances (\d+) seconds', heading_lateral),
    (r'desired facing is (\d+) and lateral offset is (\d+) with description (\S+)', lateral_result),
    (r'lateral offset (\d+) degrees and a pending (\S+) request made at second 0', pending_lateral),
    (r'at second (\d+) the pilot requests lateral (\S+) and advances to second (\d+)', replace_lateral),
    (r'lateral offset is (\d+) and changing lateral is (True|False)', pending_lateral_result),
    (r'an airborne VTOL with maximum speed ([-.\d]+) KPH and desired horizontal speed ([-.\d]+) KPH', vtol),
    (r'the pilot requests vertical speed ([-.\d]+) KPH', vertical_request),
    (r'the command is (ACCEPTED|REJECTED) and vertical speed is ([-.\d]+) KPH', vertical_result),
    (r'a hex target (\d+) hex ranges away and actual speed ([-.\d]+) KPH', eta_target),
    (r'the pilot requests ETA for the default hex target', eta_request),
    (r'ETA display contains (.+)', eta_result),
]
