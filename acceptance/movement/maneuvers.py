"""Movement maneuvers acceptance bindings using production behavior."""
from entities.mech import Mech, MechStatus as S, UnitType, Location
from systems import movement_commands as commands
from acceptance.movement.context import equal, near, psr


def boot_setup(w, tons, speed, facing):
    w['unit'].tonnage, w['unit'].speed, w['unit'].facing = int(tons), float(speed) * 10.75, int(facing)


def boot_request(w, direction):
    with psr(w):
        w['command'] = commands.bootlegger(w['engine'], w['unit'], direction)
    assert w['command'][0], w['command']


def boot_result(w, modifier, facing, speed):
    equal((w['unit'].last_piloting_modifier, w['unit'].facing, w['unit'].desired_facing), (int(modifier), int(facing), int(facing)))
    near(w['unit'].speed, float(speed) * 10.75)


def leg_recycle(w, seconds):
    for loc in commands.legs(w['unit']):
        equal(w['unit'].sections[loc].recycle, int(seconds))


def drop_setup(w, speed, roll):
    w['unit'].speed = float(speed)
    w['psr'] = {'PASS': True, 'FAIL': False, 'UNUSED': None}[roll]


def drop(w):
    with psr(w, w['psr']) as roll:
        w['command'] = commands.prone(w['engine'], w['unit'])
        if w['psr'] is None:
            roll.assert_not_called()
        else:
            roll.assert_called()
    assert w['command'][0], w['command']


def drop_result(w, levels):
    equal((w['unit'].is_fallen, w['unit'].speed, w['unit'].desired_speed, getattr(w['unit'], 'last_fall_levels', 0)), (True, 0, 0, int(levels)))


def thrash_setup(w, tons, distance, state):
    from physics.hexmath import SCALEMAP
    distance = float(distance)
    if distance < 0:
        raise ValueError('battlesuit range must be nonnegative')
    unit = w['unit']
    unit.tonnage = int(tons)
    unit.set_status(S.FALLEN)
    other = Mech.create_test_mech()
    other.unit_type = UnitType.BSUIT
    other.team = 2
    other.fx, other.fy = unit.fx, unit.fy + distance * SCALEMAP
    if state == 'JUMPING':
        other.set_status(S.JUMPING)
    elif state == 'OOD':
        other.cocoon = 1
    elif state == 'FRIENDLY':
        other.team = unit.team
    elif state == 'MOUNTED':
        other.swarm_target = unit
    elif state != 'GROUND':
        raise ValueError(state)
    w['map'].add_mech(other)
    # Test fixture supplies intact suit sections; aggregate actual armor loss.
    for section in other.sections:
        section.armor = 100
        section.internal = section.internal_orig = 100
    w['other'] = other
    w['armor_before'] = sum(s.armor + s.internal for s in other.sections)


def thrash(w):
    with psr(w):
        w['command'] = commands.thrash(w['engine'], w['unit'])
    assert w['command'][0], w['command']


def thrash_result(w, damage, seconds):
    equal(w['armor_before'] - sum(s.armor + s.internal for s in w['other'].sections), int(damage))
    for loc in (Location.LLEG, Location.RLEG, Location.LARM, Location.RARM):
        equal(w['unit'].sections[loc].recycle, int(seconds))


BINDINGS = [
    (r'tonnage (\d+) speed ([-.\d]+) MP facing (\d+) and a successful piloting roll', boot_setup),
    (r'the pilot requests bootlegger (\w+)', boot_request),
    (r'piloting modifier is (\d+) facing and desired facing are (\d+) and actual speed is ([-.\d]+) MP', boot_result),
    (r'participating legs recycle for (\d+) seconds', leg_recycle),
    (r'actual speed ([-.\d]+) KPH and piloting result (\w+)', drop_setup),
    (r'the pilot requests prone', drop),
    (r'the unit is fallen with zero actual and desired speeds and fall levels applied are (\d+)', drop_result),
    (r'a prone (\d+) ton mech and enemy battlesuit range ([-.\d]+) with state (\w+)', thrash_setup),
    (r'the pilot thrashes on GRASSLAND with a successful piloting roll', thrash),
    (r'battlesuit damage total is (\d+) and intact limbs recycle for (\d+) seconds', thrash_result),
]
