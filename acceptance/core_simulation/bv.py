"""Independent source BV examples exercise the production algorithms."""
from dataclasses import replace
from . import step, eq
from entities.mech import Mech
from entities.pilot import Pilot
from entities.crittypes import i2weapon
from entities.weapon import WEAPON_INDEX
from systems import battle_value


@step(r'a MECH with current armor 100 internal 50 tons 50 standard engine and no parts or jump')
def defense_fixture(world):
    unit = world['unit'] = Mech(tonnage=50, max_speed=0)
    unit.sections[0].armor, unit.sections[0].internal = 100, 50


@step(r'defensive BV uses running MP (\d+)')
def defense(world, mp):
    world['unit'].max_speed = int(mp) * 10.75
    world['bv'] = battle_value.defensive_bv(world['unit']).value


@step(r'(?:defensive|offensive) BV is (\d+)')
def result(world, value): eq(world['bv'], int(value))


@step(r'a 50-ton MECH with no jump and (\d+) active sinks and weapons of BV 101 and 80 each heat 5')
def offense_fixture(world, sinks):
    unit = world['unit'] = Mech(tonnage=50, max_speed=0, num_sinks=int(sinks))
    for pos in range(2): unit.sections[0].criticals[pos].type = i2weapon(pos)


@step(r'new offensive BV is calculated')
def offense(world):
    original = WEAPON_INDEX[:2]
    try:
        WEAPON_INDEX[:2] = [replace(weapon, bv=value, heat=5) for weapon, value in zip(original, (101,80))]
        world['bv'] = battle_value.offensive_bv(world['unit']).value
    finally:
        WEAPON_INDEX[:2] = original


@step(r'legacy BV cache value 777 last checked at tick 0 and a zero-speed empty 50-ton unit with skills 4 and 5')
def legacy_fixture(world):
    unit = world['unit'] = Mech(tonnage=50, max_speed=0, num_sinks=10)
    unit.bv, unit.bv_last, unit.pilot = 777, 0, Pilot(gunnery=4,piloting=5)


@step(r'CalculateBV receives both skill sentinels 100 at tick (\d+)')
def legacy(world, tick):
    world['bv'] = battle_value.calculate_bv(world['unit'], tick=int(tick)).value


@step(r'result is (\d+) and BVLast is (\d+)')
def legacy_result(world, value, last):
    eq(world['bv'], int(value))
    eq(world['unit'].bv_last, int(last))
    eq(world['unit'].bv, 777)
