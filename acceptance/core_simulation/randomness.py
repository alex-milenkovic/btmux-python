"""Raw words and named dice are inputs, never preselected rule outcomes."""
from entities.mech import Mech
from entities.map import GameMap
from core.randomness import MT19937, RandomState, use_source
from systems.sensors import m_number
from . import step, eq


@step(r'a fresh MT stream initialized by (\S+)')
def initialize(world, initialization):
    mt = MT19937()
    if initialization == 'seed5489':
        mt.seed(5489)
    elif initialization == 'array123-234-345-456':
        mt.init_by_array([0x123, 0x234, 0x345, 0x456])
    elif initialization != 'default':
        raise AssertionError(initialization)
    world['mt'] = mt


@step(r'zero-based word (\d+) is drawn')
def nth_word(world, index):
    for _ in range(int(index)+1):
        world['value'] = world['mt'].int32()


@step(r'unsigned32 word is (\d+)')
def word_result(world, value):
    eq(world['value'], int(value))


@step(r'raw32 words (\S+)')
def words(world, values):
    world['random'] = RandomState()
    world['random'].mt.use_words([] if values == 'none' else [int(word, 16) for word in values.split(',')])


@step(r'Number is called with low (-?\d+) and high (-?\d+)')
def number(world, low, high):
    world['value'] = world['random'].number(int(low), int(high))


@step(r'result is (-?\d+) and raw words consumed is (\d+)')
def number_result(world, result, used):
    eq((world['value'], world['random'].mt.words_consumed), (int(result), int(used)))


@step(r'cached random (\d+) last window (\d+) and next int31 input (\d+)')
def cached(world, cached, window, next_word):
    unit = Mech()
    world['core_engine'].register_entity(unit)
    unit.map = GameMap(12, 12)
    unit.rnd, unit.last_rnd_update = int(cached), int(window)
    world['unit'], world['next'], world['draws'] = unit, int(next_word), []


@step(r'MNumber from (\d+) to (\d+) runs at event tick (\d+) with map tick (\d+) and heartbeat tick (\d+)')
def mnumber(world, low, high, tick, map_tick, heartbeat):
    engine, unit = world['core_engine'], world['unit']
    engine.events.set_tick(int(tick))
    unit.map.current_tick = int(map_tick)
    engine.global_tick = int(heartbeat)
    def source(name, low, high, fallback):
        eq((name, low, high), ('sensor.random', 0, 2**31-1))
        world['draws'].append(world['next'])
        return world['next']
    with use_source(source):
        world['value'] = engine.inject_command(unit, lambda: m_number(unit, int(low), int(high)))


@step(r'result is (\d+) and int31 draw count is (\d+)')
def cached_result(world, result, count):
    eq((world['value'], len(world['draws'])), (int(result), int(count)))


@step(r'source Roll die pairs (\S+)')
def pairs(world, values):
    world['pairs'] = [[int(value) for value in pair.split(',')] for pair in values.split(';')]
    world['random'] = RandomState()
    # Number(1,6) selects the high three bits. These words need no rejection.
    world['random'].mt.use_words([(die-1) << 29 for pair in world['pairs'] for die in pair])


@step(r'all pairs are rolled and init_stat reseeds without another roll')
def rolls(world):
    for _ in world['pairs']:
        world['random'].roll()
    world['random'].init_stat(5489)


@step(r'total rolls is (\d+) and nonzero histogram is (\S+)')
def histogram(world, total, histogram):
    state = world['random']
    expected = {int(key): int(count) for key, count in (item.split(':') for item in histogram.split(','))}
    eq(state.total_rolls, int(total))
    eq({i+2: count for i, count in enumerate(state.rolls) if count}, expected)


@step(r'MT seed (\d+) and prior calls (\S+)')
def prior(world, seed, prior):
    world['mt'] = MT19937(int(seed))
    if prior != 'none':
        for name in prior.split(','):
            getattr(world['mt'], name)()


@step(r'generator (int31|real1|real2|real3|res53) is called')
def generate(world, name):
    world['value'] = getattr(world['mt'], name)()


@step(r'output is ([\d.]+) and total raw32 words consumed is (\d+)')
def output(world, value, used):
    assert abs(world['value'] - float(value)) <= 1e-15, (world['value'], value)
    eq(world['mt'].words_consumed, int(used))
