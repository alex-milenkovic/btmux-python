"""Part quantity and reporting acceptance uses real critical layouts."""
from . import step, eq
from .startup import fixture
from systems import parts
from entities.crittypes import i2special, i2weapon, i2ammo, Special
from entities.mech import FireMode


@step(r'fixed-point weight ([-\d]+)')
def weight(world, value): world['weight'] = int(value)


@step(r'half-ton and quarter-ton rounding are requested')
def rounded(world):
    world['rounded'] = parts.round_to_halfton(world['weight']), parts.round_to_quarterton(world['weight'])


@step(r'rounded weights are ([-\d]+) and ([-\d]+)')
def rounded_result(world, half, quarter): eq(world['rounded'], (int(half), int(quarter)))


@step(r'original points (\d+) and remaining points (\d+)')
def points(world, original, remaining):
    unit = fixture(world)
    for sec in unit.sections: sec.internal = sec.internal_orig = 0
    unit.sections[0].internal_orig, unit.sections[0].internal = int(original), int(remaining)


@step(r'remaining percentage is calculated')
def percent(world): world['percent'] = parts.remaining_internal_percent(world['unit'])


@step(r'percentage is (\d+)')
def percent_result(world, value): eq(world['percent'], int(value))


@step(r'the same partially damaged unit with source payload and parts')
def damaged(world):
    unit = fixture(world)
    unit.sections[0].armor -= 1
    for pos, kind in enumerate((i2weapon(0), i2weapon(0), i2ammo(0), i2special(Special.ENGINE), i2special(Special.UPPER_ACTUATOR))):
        unit.sections[0].criticals[pos].type = kind
    unit.sections[0].criticals[0].firemode = FireMode.DESTROYED_MODE
    world['list_zero'] = parts.unit_parts_list(unit, 0)


@step(r'UnitPartsList is requested with mode ([-\d]+)')
def report(world, mode): world['part_list'] = parts.unit_parts_list(world['unit'], int(mode))


@step(r'the complete string equals the mode zero result')
def same(world): eq(world['part_list'], world['list_zero'])
