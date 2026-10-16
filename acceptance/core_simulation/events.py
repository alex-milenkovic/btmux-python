"""Clock and no-op hook contracts use the real queue and heartbeat consumers."""
from types import SimpleNamespace
from core.events import EventType, very_fake_func
from entities.mech import Mech, MechStatus, Location
from . import step, eq


@step(r'a queued event marked zombie ([01])')
def queued(world, zombie):
    engine = world['core_engine']
    world['trace'] = []
    engine.events.observe_execution = lambda phase, event: world['trace'].append(phase)
    event = engine.events.schedule(1, EventType.MOVE, lambda e: world['trace'].append('callback'))
    if zombie == '1':
        event.cancel()


@step(r'it is executed by (due|type)')
def execute(world, method):
    queue = world['core_engine'].events
    queue.muxevent_run() if method == 'due' else queue.run_by_type(EventType.MOVE)


@step(r'hook and callback trace is (\S+) and history count remains 0')
def trace(world, expected):
    eq(world['trace'], [] if expected == 'none' else expected.split(','))
    eq(sum(world['core_engine'].events.history), 0)


@step(r'history counts for source types 0 1 and 2 are (\S+)')
def history(world, counts):
    world['core_engine'].events.history[:3] = [int(value) for value in counts.split(',')]


@step(r'nonempty event history is requested')
def show_history(world):
    queue = world['core_engine'].events
    world['rows'], world['text'] = queue.history_rows(), queue.debug_event_types('history')


@step(r'displayed nonzero type order is (\S+)')
def history_order(world, order):
    eq([row['type'] for row in world['rows']], [] if order == 'none' else list(map(int, order.split(','))))


@step(r'three events of one source type with (\d+) cancelled')
def pending(world, cancelled):
    queue = world['core_engine'].events
    for i in range(3):
        event = queue.schedule(1, EventType.FALL, very_fake_func)
        if i < int(cancelled):
            event.cancel()


@step(r'blank event summary is requested')
def show_pending(world):
    state = world['core_engine'].randomness
    world['roll_before'] = state.total_rolls, state.mt.words_consumed
    world['text'] = world['core_engine'].events.debug_event_types('')


@step(r'pending total is (\d+) and roll state is unchanged')
def pending_total(world, count):
    eq(world['text'][-1], count+' total')
    state = world['core_engine'].randomness
    eq((state.total_rolls, state.mt.words_consumed), world['roll_before'])


@step(r'a fresh engine at all clock values zero')
def zero(world):
    engine = world['core_engine']
    eq((engine.sim_now, engine.muxevent_tick, engine.global_tick), (0, 0, 0))


@step(r'the clock sequence is (\S+)')
def clock(world, sequence):
    for name in sequence.split(','):
        if name not in ('dispatch', 'heartbeat'):
            raise AssertionError(name)
        getattr(world['core_engine'], name)()


@step(r'wall time is (\d+) event tick is (\d+) and heartbeat tick is (\d+)')
def clocks(world, wall, event, heart):
    engine = world['core_engine']
    eq((engine.sim_now, engine.muxevent_tick, engine.global_tick), tuple(map(int, (wall, event, heart))))


@step(r'the heartbeat timer is stopped')
def stopped(world):
    world['core_engine'].heartbeat_stop()


@step(r'the timer commands are (\S+)')
def timer_commands(world, commands):
    for name in commands.split(','):
        if name not in ('init', 'stop'):
            raise AssertionError(name)
        getattr(world['core_engine'], 'heartbeat_'+name)()


@step(r'pending heartbeat timer count is (\d+)')
def timer_count(world, count):
    eq(world['core_engine'].heartbeat_timer_count, int(count))


@step(r'one registered object of type (MECH|AUTO|MAP|OTHER)')
def registered(world, kind):
    engine = world['core_engine']
    if kind == 'MECH':
        obj = Mech()
        obj.status |= MechStatus.STARTED
        obj.last_weapon_recycle = -1
        obj.sections[Location.LARM].recycle = 10
    else:
        obj = SimpleNamespace(xcode_type=kind, _id=1, mymech=object(), weaplist=None)
    world['object'] = obj
    engine.register_entity(obj)


@step(r'one heartbeat fires')
def heartbeat(world):
    world['core_engine'].heartbeat()


@step(r'the dispatch recipient is (mech|auto-boundary|none) and heartbeat tick is 1')
def recipient(world, expected):
    obj = world['object']
    if expected == 'mech':
        eq(obj.sections[Location.LARM].recycle, 9)
        eq(obj.last_weapon_recycle, 0)
    elif expected == 'auto-boundary':
        eq(len(obj.external_effects), 3)
        eq([entry['applied'] for entry in obj.external_effects], [False]*3)
    else:
        eq(getattr(obj, 'external_effects', []), [])
    eq(world['core_engine'].global_tick, 1)
