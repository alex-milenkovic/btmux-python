"""Queued source callbacks, including real falls, landing, and pilot recovery."""
from types import SimpleNamespace
from unittest.mock import patch
from core.events import EventType as E
from core.randomness import use_source
from entities.mech import MechStatus as S, CritStatus as C
from systems import piloting, vehicle_combat, hit_locations, stagger
from physics import jump, orbital
from . import step, eq
from .startup import fixture, advance


@step(r'a recovery callback is due at tick 30')
def recovery(world):
    unit = fixture(world, started=True)
    piloting.prolong_uncon(unit, 30)


@step(r'at event tick (\d+) unconsciousness is prolonged by (\d+)')
def prolong(world, now, length):
    advance(world, now)
    piloting.prolong_uncon(world['unit'], int(length))


@step(r'one recovery event remains due at (\d+)')
def recovery_due(world, due):
    events = world['core_engine'].events.pending_events(E.RECOVERY, world['unit'])
    eq([event.tick for event in events], [int(due)])


@step(r'tank crew stun callbacks are scheduled at (\S+)')
def tank(world, deadlines):
    unit = fixture(world, 'VEH_GROUND', True)
    vehicle_combat.tank_flag(unit, vehicle_combat.TankCritStatus.CREW_STUNNED, True)
    for due in deadlines.split(','):
        world['core_engine'].schedule_event(int(due), E.UNSTUN_CREW, vehicle_combat.unstun_crew, data=unit)


@step(r'event time reaches (\d+)')
def time(world, tick):
    advance(world, tick)


@step(r'tank crew stunned is ([01]) and recovery notices is (\d+)')
def tank_result(world, stunned, messages):
    unit = world['unit']
    eq(unit.crew_stunned, stunned == '1')
    eq(sum('Your head clears' in message for message in unit.movement_messages), int(messages))


@step(r'a MECH with stunned bit set and state (\w+)')
def stunned(world, state):
    unit = fixture(world, started=state == 'started')
    if state == 'destroyed': unit.status |= S.DESTROYED
    unit.crit_status |= C.MECH_STUNNED


@step(r'the crewstun callback runs')
def unstun(world):
    engine = world['core_engine']
    engine.schedule_event(1, E.CREWSTUN, hit_locations.crewstun_recovery, data=world['unit'])
    advance(world, 1)


@step(r'stunned bit is zero and recovery notice count is (\d+)')
def unstun_result(world, count):
    eq(bool(world['unit'].crit_status & C.MECH_STUNNED), False)
    eq(sum('recover' in message for message in world['unit'].movement_messages), int(count))


@step(r'a stopped nonflying unit at height (\d+) with fall data ([-\d]+)')
def falling(world, height, speed):
    unit = fixture(world)
    unit.status |= S.COMBAT_SAFE
    unit.z, unit.fz = int(height), int(height) * 64.5
    world['event'] = world['core_engine'].schedule_event(1, E.FALL, orbital.fall_event, data=unit, data2=int(speed))


@step(r'one fall callback runs')
def fall(world):
    advance(world, 1)


@step(r'remaining height is (\d+) impact levels is (\d+) and next fall data is (\S+)')
def fall_result(world, height, levels, data):
    unit = world['unit']
    eq(unit.z, int(height))
    eq(getattr(unit, 'last_fall_levels', 0), int(levels))
    events = world['core_engine'].events.pending_events(E.FALL, unit)
    eq([event.data2 for event in events], [] if data == 'none' else [int(data)])
    if events: eq(events[0].tick - world['core_engine'].muxevent_tick, 3)


@step(r'a pending stand callback and fallen state ([01])')
def stand(world, fallen):
    unit = fixture(world, started=True)
    if fallen == '1': unit.status |= S.FALLEN
    world['callback_kind'] = E.STAND
    world['core_engine'].schedule_event(1, E.STAND, jump._stand_done, data=unit)


@step(r'a source jump callback whose movement ends jumping ([01])')
def jumping(world, ended):
    unit = fixture(world, started=True)
    unit.set_hex_position(3, 3, 0)
    unit.status |= S.JUMPING | S.COMBAT_SAFE
    unit.jump_speed, unit.jump_top = 64.5, 64.5
    unit.jump_length = 1 if ended == '1' else 1000
    unit.start_fx, unit.start_fy = unit.fx, unit.fy
    unit.going_x, unit.going_y = 3, 2
    world['callback_kind'] = E.JUMP
    world['core_engine'].schedule_event(1, E.JUMP, jump._jump_event_callback, data=unit)


@step(r'the callback executes')
def callback(world):
    from systems import ecm
    with patch.object(ecm, 'mark_for_los_update', wraps=ecm.mark_for_los_update) as invalidations:
        advance(world, 1)
        world['invalidations'] = invalidations.call_count


@step(r'fallen is zero and LOS invalidation count increases by 1')
def stand_result(world):
    eq(world['unit'].is_fallen, False)
    eq(world['invalidations'], 1)


@step(r'pending jump callbacks is (\d+)')
def jump_result(world, count):
    eq(len(world['core_engine'].events.pending_events(E.JUMP, world['unit'])), int(count))


@step(r'a started unit of tons (\d+) at stagger level (\d+)')
def tonnage(world, tons, level):
    unit = fixture(world, started=True)
    unit.tonnage, unit.stagger_damage = int(tons), int(level) * 20


@step(r'new weighted new unweighted and legacy modifiers are inspected')
def modifiers(world):
    unit = world['unit']
    level = int(unit.stagger_damage / 20)
    world['modifiers'] = (stagger.stagger_modifier(unit, level), stagger.stagger_modifier(unit, level, False), stagger.legacy_modifier(unit))


@step(r'modifier triple is (\S+)')
def modifier_result(world, triple):
    eq(world['modifiers'], tuple(map(int, triple.split(','))))


@step(r'uncounted damage 20 and counted damage 20 in the active window')
def history(world):
    unit = fixture(world, started=True)
    stagger.record_damage(unit, 20)
    stagger.record_damage(unit, 20)
    unit.stagger_damage_list[1]['counted'] = True


@step(r'mode ([12]) stagger check runs at its deadline with a successful pilot roll')
def check_history(world, mode):
    engine = world['core_engine']
    engine.new_stagger = int(mode)
    engine.skip_seconds(5)
    with use_source(lambda name, low, high, fallback: 12):
        with patch.object(stagger, 'make_piloting_roll', wraps=stagger.make_piloting_roll) as roll:
            engine.heartbeat()
            world['observed_level'] = roll.call_args.args[1] + 1


@step(r'observed stagger level is (\d+) and retained history points is (\d+)')
def counted(world, level, points):
    eq(world['observed_level'], int(level))
    eq(sum(node['amount'] for node in world['unit'].stagger_damage_list), int(points))


@step(r'a legacy stagger callback with state (\w+) and damage (\d+)')
def legacy(world, state, damage):
    unit = fixture(world, started=True)
    if state != 'upright': unit.status |= {'jumping': S.JUMPING, 'fallen': S.FALLEN}[state]
    unit.stagger_damage = int(damage)
    world['core_engine'].schedule_event(1, E.CHECK_STAGGER, stagger.check_stagger_event, data=unit)


@step(r'the callback executes with successful rolls if needed')
def legacy_run(world):
    with use_source(lambda name, low, high, fallback: 12): advance(world, 1)


@step(r'stagger damage is ([-\d]+) and pilot rolls consumed is (\d+)')
def legacy_result(world, remaining, draws):
    eq(world['unit'].stagger_damage, int(remaining))
    eq(world['core_engine'].randomness.total_rolls, int(draws))
