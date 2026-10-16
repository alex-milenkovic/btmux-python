"""Movement settling acceptance bindings using production behavior."""
from unittest.mock import patch
from entities.mech import MechStatus as S, MoveType, Location, SectionConfig
from core.events import EventType
from systems import movement_commands as commands
from physics import jump
from acceptance.movement.context import advance, boolean, equal, psr, set_hex, bounded_integer


def fall_setup(w, tons, name, gravity, facing):
    w['unit'].tonnage = int(tons)
    w['unit'].facing = int(facing)
    w['unit'].set_status(S.UNDERSPECIAL)
    w['map'].grav = int(gravity)
    set_hex(w, name, 2 if name == 'WATER' else 0)
    if name == 'WATER':
        w['unit'].z = -2


def fall(w, levels, die):
    with psr(w), patch('systems.combat.roll_1d6', return_value=bounded_integer(die, 1, 6, 'fall direction die')), patch('systems.combat.roll_2d6', return_value=7):
        w['fall'] = jump.mech_falls(w['unit'], int(levels))


def fall_result(w, damage, facing):
    equal((w['fall'].damage_taken, w['unit'].facing, w['unit'].desired_facing), (int(damage), int(facing), int(facing)))


def flood_setup(w, movement, posture, depth):
    w['unit'].move_type = MoveType[movement]
    if posture == 'FALLEN':
        w['unit'].set_status(S.FALLEN)
    elif posture != 'UPRIGHT':
        raise ValueError(posture)
    set_hex(w, 'WATER', depth)
    w['unit'].z = -int(depth)


def flooded_section(w, location, front, rear, original):
    w['section'] = Location[location]
    s = w['unit'].sections[w['section']]
    front, rear, original = int(front), int(rear), int(original)
    if front > s.armor_orig or rear > original:
        raise ValueError('remaining armor exceeds original armor')
    if original and w['section'] not in (Location.LTORSO, Location.RTORSO, Location.CTORSO):
        raise ValueError('only torso sections have rear armor')
    s.armor, s.rear, s.rear_orig = front, rear, original


def flood(w):
    from physics.flooding import flood_unit
    with psr(w):
        flood_unit(w['unit'])


def flood_result(w, flooded):
    equal(bool(w['unit'].sections[w['section']].config & SectionConfig.SECTION_FLOODED), boolean(flooded))


def workflow_setup(w, workflow):
    if workflow not in ('INTACT_JUMP', 'EARLY_LAND', 'QUAD_STAND', 'STAND_CHECK', 'STAND_BTH_13', 'STAND_CAREFUL'):
        raise ValueError(workflow)
    w['workflow'] = workflow


def workflow(w):
    u, engine, name = w['unit'], w['engine'], w['workflow']
    with psr(w) as roll:
        if name in ('INTACT_JUMP', 'EARLY_LAND'):
            u.jump_mp = 4
            result = jump.mech_jump(u, 3, 6, engine.events)
            assert result.success, result
            if name == 'EARLY_LAND':
                w['command'] = commands.land(engine, u)
            else:
                for _ in range(100):
                    if not u.is_jumping:
                        break
                    advance(w, 1)
        else:
            u.set_status(S.FALLEN)
            if name == 'QUAD_STAND':
                u.move_type = MoveType.QUAD
            if name == 'STAND_BTH_13':
                u.pilot.piloting = 13
            argument = {'STAND_CHECK': 'check', 'STAND_CAREFUL': 'careful'}.get(name, '')
            w['command'] = jump.stand_up(u, engine.events, argument)
        w['roll_calls'] = list(roll.call_args_list)


def workflow_result(w, result):
    u = w['unit']
    if result == 'LANDED_WITHOUT_LANDING_ROLL':
        equal(u.is_jumping, False)
        equal(w['roll_calls'], [])
    elif result == 'JUMP_CANCELLED_AND_STABILIZING':
        equal(u.is_jumping, False)
        equal(commands.pending(u, '_stabil_event'), True)
        equal(len(w['roll_calls']), 1)
    elif result == 'STANDING_WITHOUT_ROLL':
        equal(u.is_fallen, False)
        equal(w['roll_calls'], [])
        advance(w, 10)
        equal(commands.pending(u, '_stand_event'), False)
    elif result == 'BTH_REPORTED_NO_STATE_CHANGE':
        assert 'BTH' in w['command'][1]
        equal(u.is_fallen, True)
        equal(commands.pending(u, '_stand_event'), False)
    elif result == 'REFUSED_WITH_ANYWAY_HINT':
        equal(w['command'][0], False)
        assert 'anyway' in w['command'][1]
    elif result == 'MINUS_TWO_ROLL_DOUBLE_TIME':
        equal(w['roll_calls'][0].args[1], -2)
        equal(w['engine'].event_time_remaining(EventType.STAND, u), 20)
    else:
        raise ValueError(result)


BINDINGS = [
    (r'tonnage (\d+) terrain (\w+) gravity (\d+) percent and facing (\d+) degrees', fall_setup),
    (r'a fall of (\d+) levels uses direction die (\d+) and a successful pilot injury roll', fall),
    (r'total fall damage is (\d+) and facing and desired facing are (\d+)', fall_result),
    (r'a MECH with movement (\w+) posture (\w+) in WATER at depth (\d+)', flood_setup),
    (r'section (\w+) front armor (\d+) rear armor (\d+) and original rear armor (\d+)', flooded_section),
    (r'flooding is evaluated', flood),
    (r'that section is flooded (True|False)', flood_result),
    (r'movement workflow (\w+)', workflow_setup),
    (r'the workflow runs to completion using successful required pilot rolls', workflow),
    (r'observable state is (\w+)', workflow_result),
]
