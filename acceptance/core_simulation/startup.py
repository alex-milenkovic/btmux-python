"""Source startup/shutdown commands on registered units and real event clocks."""
from core.events import EventType as E
from entities.map import GameMap, WATER
from entities.mech import Mech, UnitType as U, MoveType as M, MechStatus as S, MechStatus2 as S2
from entities.pilot import Pilot
from systems import startup
from . import step, eq


def fixture(world, kind='MECH', started=False):
    unit = Mech.create_test_mech()
    unit.unit_type = U[kind]
    unit.move_type = {U.VTOL: M.VTOL, U.VEH_NAVAL: M.HULL, U.VEH_GROUND: M.TRACK,
                      U.DS: M.FLY, U.AERO: M.FLY}.get(unit.unit_type, M.BIPED)
    unit.x = unit.y = 3
    unit.status = S.STARTED if started else S.NONE
    board = GameMap(12, 12)
    board.add_mech(unit)
    actor = Pilot()
    unit.pilot = actor if started else None
    world['unit'], world['actor'] = unit, actor
    world['core_engine'].register_entity(unit)
    world['wizard'] = False
    return unit


def command(world, name, argument=''):
    engine = world['core_engine']
    world['reply'] = engine.inject_command(world['actor'], lambda: getattr(startup, name)(
        engine, world['unit'], argument, caller=world['actor'], wizard=world['wizard']))


def advance(world, ticks):
    for _ in range(int(ticks)):
        world['core_engine'].process_tick()


@step(r'a stopped eligible (\w+) requesting startup with (\w+) as wizard ([01])')
def request(world, kind, argument, wizard):
    fixture(world, kind)
    world['wizard'] = wizard == '1'
    command(world, 'startup', '' if argument == 'none' else argument)
    eq(world['reply'][0], True)


@step(r'the normal clock reaches (\d+)')
def reaches(world, tick):
    advance(world, int(tick) - world['core_engine'].sim_now)


@step(r'started is ([01]) and boot message count is (\d+)')
def boot_count(world, started, count):
    eq(world['unit'].is_started, started == '1')
    eq(len(world['unit'].boot_messages), int(count))


@step(r'an otherwise eligible stopped unit with heat ([\d.]+)')
def heat(world, amount):
    fixture(world).heat = float(amount)


@step(r'actor wizard ([01]) requests startup argument (\w+)')
def hot_request(world, wizard, argument):
    world['wizard'] = wizard == '1'
    command(world, 'startup', '' if argument == 'none' else argument)


@step(r'startup scheduling is ([01]) and random draws consumed is 0')
def scheduled(world, yes):
    engine = world['core_engine']
    eq(engine.has_event(E.STARTUP, world['unit']), yes == '1')
    eq(engine.randomness.mt.words_consumed, 0)


@step(r'a stopped (\w+) in water with waterproof ([01])')
def water(world, kind, proof):
    unit = fixture(world, kind)
    unit.map.set_terrain(3, 3, WATER)
    unit.map.set_elevation(3, 3, 2)
    unit.terrain, unit.elev, unit.z = WATER, 2, -2
    unit.specials2 = 0x100000 if proof == '1' else 0


@step(r'normal startup advances to (\d+)')
def flood_start(world, tick):
    command(world, 'startup')
    advance(world, tick)


@step(r'destroyed is ([01]) and remaining startup events is (\d+)')
def flood_result(world, dead, pending):
    eq(world['unit'].is_destroyed, dead == '1')
    eq(world['core_engine'].events.count_type(E.STARTUP), int(pending))


@step(r'normal MECH startup has reached tick (\d+)')
def begin_abort(world, tick):
    fixture(world)
    command(world, 'startup')
    advance(world, tick)


@step(r'shutdown is followed by a new startup and 30 clock ticks')
def restart(world):
    command(world, 'shutdown')
    eq(world['reply'][0], True)
    world['old_message_count'] = len(world['unit'].boot_messages)
    command(world, 'startup')
    eq(world['reply'][0], True)
    advance(world, 30)


@step(r'only the new sequence completes and started is 1')
def restarted(world):
    unit, engine = world['unit'], world['core_engine']
    eq(unit.is_started, True)
    eq(len(unit.boot_messages), world['old_message_count'] + 6)
    eq(unit.last_startup, engine.sim_now)
    eq(engine.events.count_type(E.STARTUP), 0)


@step(r'an eligible grounded started MECH moving at ([-\d.]+) MP')
def moving(world, mp):
    unit = fixture(world, started=True)
    unit.speed = unit.desired_speed = float(mp) * 10.75
    unit.status |= S.COMBAT_SAFE


@step(r'ordinary shutdown executes')
def shutdown(world):
    command(world, 'shutdown')


@step(r'fall count is (\d+) and both speeds are zero')
def stopped(world, falls):
    unit = world['unit']
    eq(sum(message.startswith('Mech fell ') for message in unit.movement_messages), int(falls))
    eq((unit.speed, unit.desired_speed), (0, 0))
    eq(unit.is_fallen, bool(int(falls)))


@step(r'a started (\w+) with jumping ([01]) at (\d+) above terrain and wizard ([01])')
def airborne(world, kind, jumping, height, wizard):
    unit = fixture(world, kind, True)
    unit.z, unit.fz = int(height), int(height) * 64.5
    if jumping == '1': unit.status |= S.JUMPING
    world['wizard'] = wizard == '1'


@step(r'started is ([01]) and fall callback deadline offset is (\w+)')
def fall_due(world, yes, offset):
    eq(world['unit'].is_started, yes == '1')
    eq(world['core_engine'].events.time_until_type_data(E.FALL, world['unit']),
       None if offset == 'none' else int(offset))


@step(r'a unit is ([\w-]+) with pilot and source cleanup fields populated')
def cleanup_input(world, state):
    unit = fixture(world, 'MW' if state == 'MW-started' else 'MECH', state in ('started', 'MW-started'))
    if state == 'starting': command(world, 'startup')
    unit.target, unit.charge_target = 8, 9
    unit.masc_counter, unit.scharge_counter = 3, 4
    unit.status2 = S2.SLITE_ON | S2.ECM_ENABLED | S2.SPRINTING
    world['before'] = (unit.target, unit.charge_target, unit.masc_counter, unit.scharge_counter, unit.status2)


@step(r'observed cleanup profile is ([\w-]+)')
def cleanup_result(world, profile):
    unit = world['unit']
    observed = unit.target, unit.charge_target, unit.masc_counter, unit.scharge_counter, unit.status2
    eq(observed, (-1, -1, 0, 0, 0) if profile == 'full' else world['before'])
    eq(world['reply'][0], profile != 'refused')
    if profile != 'refused': eq(unit.pilot, None)
