"""Repair APS cases mutate actual sections and derive movement capacity."""
from . import step, eq
from .startup import fixture
from entities.mech import SectionConfig as C, FireMode as F
from entities.crittypes import Special, i2special, i2weapon
from systems import repairs, parts


@step(r'a destroyed flooded section with original internal 10')
def destroyed(world):
    unit = fixture(world)
    section = unit.sections[0]
    section.internal_orig, section.internal, section.armor = 10, 0, 0
    section.config = C.SECTION_DESTROYED | C.SECTION_FLOODED


@step(r'repair operation (reattach|replace-suit) is applied')
def repair(world, operation):
    (repairs.reattach if operation == 'reattach' else repairs.replace_suit)(world['unit'], 0)


@step(r'internal is 10 destroyed is zero and flooded is ([01])')
def repaired(world, flooded):
    unit = world['unit']
    eq((unit.sections[0].internal, unit.is_section_destroyed(0), bool(unit.sections[0].config & C.SECTION_FLOODED)),
       (10, False, flooded == '1'))


@step(r'source engine rating (\d+) and nominal tons (\d+)')
def modifiers_input(world, rating, tons):
    unit = fixture(world)
    unit.engine_rating, unit.tonnage = int(rating), int(tons)


@step(r'gyro engine and ordinary repair modifiers are requested')
def modifiers(world):
    world['modifiers'] = tuple(parts.part_mod(world['unit'], kind) for kind in (i2special(Special.GYRO), i2special(Special.ENGINE), 0))


@step(r'modifier tuple is (\S+)')
def modifier_result(world, expected): eq(world['modifiers'], tuple(map(int, expected.split(','))))


@step(r'a MECH with maximum speed 6 MP and (\d+) jump-jet slots and improved jets ([01])')
def jets_input(world, count, improved):
    unit = fixture(world)
    unit.max_speed = 64.5
    unit.specials2 = 0x80 if improved == '1' else 0
    for ordinal in range(int(count)):
        unit.sections[ordinal // 12].criticals[ordinal % 12].type = i2special(Special.JUMP_JET)


@step(r'do_sub_magic recomputes movement')
def jets(world): repairs.sub_magic(world['unit'])


@step(r'jump capacity is (\d+) MP')
def jets_result(world, mp): eq(world['unit'].jump_speed, int(mp) * 10.75)


@step(r'a live flooded section containing a disabled part additionally marked (\w+)')
def flooded(world, flag):
    unit = fixture(world)
    unit.sections[0].config = C.SECTION_FLOODED
    slot = unit.sections[0].criticals[0]
    slot.type = i2weapon(0)
    slot.firemode = F.DISABLED_MODE | {'none': 0, 'BROKEN': F.BROKEN_MODE, 'DAMAGED': F.DAMAGED_MODE}[flag]


@step(r'ReSeal runs')
def reseal(world): repairs.reseal(world['unit'], 0)


@step(r'disabled is zero and retained extra flag is (\w+)')
def resealed(world, flag):
    eq(world['unit'].sections[0].criticals[0].firemode, {'none': 0, 'BROKEN': F.BROKEN_MODE, 'DAMAGED': F.DAMAGED_MODE}[flag])
