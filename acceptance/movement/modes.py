"""Movement modes acceptance bindings using production behavior."""
from entities.mech import Mech, MechStatus as S, MechStatus2 as S2, UnitType, MoveType, Location, FireMode, SectionConfig
from entities.pilot import Pilot
from systems import movement_commands as commands
from acceptance.movement.context import FLAGS, advance, boolean, equal, near, psr, set_hex


def unit_mode(w, name, mode):
    w['unit'].unit_type = UnitType[name]
    w['unit'].status2 = FLAGS[mode]


def request_mode(w, mode):
    unit = w['unit']
    w['before_events'] = w['engine'].events.pending_count
    w['command'] = (commands.hulldown(w['engine'], unit) if mode == 'hulldown' else
                    commands.set_mode(w['engine'], unit, mode, w.get('caller')))
    w['new_transition'] = w['engine'].events.pending_count > w['before_events']


def advance_session(w, ticks):
    advance(w, ticks)


def mode_state(w, active, pending):
    equal(w['unit'].status2 & S2.MOVE_MODES, FLAGS[active])
    event = w['unit']._mode_event
    value = 'NONE'
    if event is not None and not event.zombie:
        value = {S2.SPRINTING: 'SPRINT', S2.EVADING: 'EVADE', S2.DODGING: 'DODGE'}[event.data2[0]]
        value += '_ON' if event.data2[1] else '_OFF'
    equal(value, pending)


def condition(w, name):
    u = w['unit']
    if name in ('FORTIFIED', 'SPRINTING'):
        u.set_status2(S2[name])
    elif name in ('FALLEN', 'JUMPING'):
        u.set_status(S[name])
    elif name == 'OOD':
        u.cocoon = 11
    elif name == 'STANDING':
        u.set_status(S.FALLEN)
        with psr(w):
            result = commands.stand(w['engine'], u)
        assert result[0], result
    elif name == 'TOWING':
        u.carrying = 2
    elif name.startswith('IN_WATER'):
        set_hex(w, 'WATER', 2)
        u.z = -2
        if name.endswith('SPRINTING'):
            u.set_status2(S2.SPRINTING)
    elif name.startswith('HIP_DISABLED'):
        u.sections[Location.LLEG].criticals[0].firemode |= FireMode.DISABLED_MODE
        if name.endswith('EVADING'):
            u.set_status2(S2.EVADING)
    elif name == 'WEAPON_RECYCLE':
        from entities.mech import WeaponState
        u.weapons.append(WeaponState(recycle=20))
    elif name == 'LIMB_RECYCLE':
        u.sections[Location.LARM].recycle = 20
    elif name == 'NO_DODGE_ADVANTAGE':
        u.pilot.dodge_maneuver = False
    elif name == 'OTHER_PILOT':
        w['caller'] = Pilot()
    elif name == 'CHANGING_MODE':
        commands.set_mode(w['engine'], u, 'sprint')
    elif name == 'CHARGING':
        u.charge_target = 2
    elif name == 'MOUNTED':
        u.swarm_target = Mech()
    elif name in ('LEFT_LEG_DESTROYED', 'QUAD_FRONT_LEG_DESTROYED'):
        loc = Location.LLEG if name == 'LEFT_LEG_DESTROYED' else Location.LARM
        if loc == Location.LARM:
            u.move_type = MoveType.QUAD
        u.sections[loc].config |= SectionConfig.SECTION_DESTROYED
    else:
        raise ValueError(name)


def command_transition(w, outcome, scheduled):
    equal(w['command'][0], outcome == 'ACCEPTED')
    equal(w['new_transition'], boolean(scheduled))


def pending_mode(w, mode, cond):
    request_mode(w, mode)
    if cond == 'SHUTDOWN':
        w['unit'].clear_status(S.STARTED)
    elif cond == 'DESTROYED':
        w['unit'].set_status(S.DESTROYED)
    else:
        condition(w, cond)


def due_event(w):
    advance(w, 30)


def mode_speed(w, mode, speed):
    w['unit'].status2 = FLAGS[mode]
    w['unit'].speed = float(speed)


def heat(w):
    from systems.heat import calculate_movement_heat
    w['heat'] = calculate_movement_heat(w['unit'])


def heat_result(w, expected):
    near(w['heat'], expected)


def movement_speed(w, move, speed):
    w['unit'].move_type = MoveType[move]
    w['unit'].speed = float(speed)


def quad(w, maximum):
    w['unit'].move_type = MoveType.QUAD
    w['unit'].max_speed = float(maximum)


def hull_workflow(w, workflow, ticks):
    if workflow not in ('LOWER', 'RAISE', 'LOWER_STOP', 'RAISE_STOP', 'LOWER_SHUTDOWN'):
        raise ValueError(f'Unknown hull down workflow: {workflow}')
    if workflow.startswith('RAISE'):
        w['unit'].set_status(S.HULLDOWN)
    result = commands.hulldown(w['engine'], w['unit'], '-' if workflow.startswith('RAISE') else '')
    assert result[0], result
    if workflow.endswith('STOP'):
        commands.hulldown(w['engine'], w['unit'], 'stop')
    elif workflow.endswith('SHUTDOWN'):
        w['unit'].clear_status(S.STARTED)
    advance(w, ticks)


def hull_state(w, active, pending):
    equal(w['unit'].has_status(S.HULLDOWN), boolean(active))
    equal(commands.pending(w['unit'], '_hulldown_event'), boolean(pending))


BINDINGS = [
    (r'unit class (\w+) with movement mode (\w+)', unit_mode),
    (r'the pilot requests (sprint|evade|dodge|hulldown)', request_mode),
    (r'the session advances (\d+) seconds', advance_session),
    (r'movement mode is (\w+) and pending transition is (\w+)', mode_state),
    (r'movement condition (\w+)', condition),
    (r'the command is (ACCEPTED|REJECTED) and a new transition is (True|False)', command_transition),
    (r'a pending (\w+) activation with completion condition (\w+)', pending_mode),
    (r'its due event runs', due_event),
    (r'active mode (\w+) and actual speed ([-.\d]+) KPH', mode_speed),
    (r'movement heat is evaluated', heat),
    (r'movement heat contribution is ([-.\d]+)', heat_result),
    (r'unit movement (\w+) and actual speed ([-.\d]+) KPH', movement_speed),
    (r'a quad with maximum speed ([-.\d]+) KPH', quad),
    (r'the pilot performs hull down workflow (\w+) and advances (\d+) seconds', hull_workflow),
    (r'hull down is (True|False) and changing hull down is (True|False)', hull_state),
]
