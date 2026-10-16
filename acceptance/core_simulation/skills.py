"""Source skill selection and generic pilot-roll guard contracts."""
from types import SimpleNamespace
from core.randomness import use_source
from entities.mech import MoveType, MechStatus as S
from entities.weapon import WeaponType as W
from systems import piloting as p
from . import step, eq
from .startup import fixture


@step(r'unit quiet ([01]) skill text (\S+) and no valid pilot')
def overrides(world, quiet, text):
    unit = fixture(world)
    unit.quiet, unit.mechskills = quiet == '1', '' if text == 'none' else text.replace(',', ' ')


@step(r'piloting gunnery spotting and artillery skills are resolved')
def resolve(world):
    unit = world['unit']
    world['skills'] = (p.find_pilot_piloting(unit), p.find_pilot_gunnery(unit), p.find_pilot_spotting(unit), p.find_pilot_arty_gun(unit))


@step(r'skill tuple is (\S+)')
def tuple_result(world, values):
    eq(world['skills'], tuple(map(int, values.split(','))))


@step(r'unit (\w+) movement (\w+) terrain (\w+) extended mode ([01]) and weapon (\S+)')
def names_input(world, kind, move, terrain, extended, weapon):
    unit = fixture(world, kind)
    unit.move_type, unit.terrain = MoveType[move], '~' if terrain == 'WATER' else ' '
    engine = world['core_engine']
    engine.extended_gunnery = engine.extended_piloting = extended == '1'
    world['weapon'] = SimpleNamespace(name=weapon, weapon_type=W.TMISSILE if weapon == 'missile' else W.TBEAM)


@step(r'gunnery and piloting skill names are resolved')
def names(world):
    world['names'] = (p.find_gunnery_skill_name(world['unit'], world['weapon']), p.find_piloting_skill_name(world['unit']))


@step(r'skill name pair is (\S+)')
def names_result(world, expected):
    eq(world['names'], tuple(expected.split('/')))


@step(r'unit fallen ([01]) stopped ([01]) and succeedWhenFallen ([01])')
def roll_input(world, fallen, stopped, succeed):
    unit = fixture(world, started=stopped == '0')
    if fallen == '1': unit.status |= S.FALLEN
    world['succeed'] = succeed == '1'


@step(r'the noXP piloting check runs with otherwise valid state and successful dice')
def roll(world):
    with use_source(lambda name, low, high, fallback: 12):
        world['roll'] = world['core_engine'].inject_command(world['unit'], lambda: p.make_piloting_roll(
            world['unit'], succeed_when_fallen=world['succeed'], award_xp=False))


@step(r'check success is ([01]) and Roll count is (\d+)')
def roll_result(world, success, count):
    eq(world['roll'].success, success == '1')
    eq(world['core_engine'].randomness.total_rolls, int(count))
