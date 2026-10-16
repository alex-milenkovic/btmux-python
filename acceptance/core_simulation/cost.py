"""Economy APS invokes shared accumulators and the full source calculation."""
from . import step, eq
from .startup import fixture
from entities.mech import Mech, UnitType
from entities.crittypes import i2special
from systems import economy


@step(r'a non-Clan standard 50-ton cost fixture with engine (\d+) no armor actuators weapons or parts and ten single sinks')
def sparse(world, engine):
    world['unit'] = Mech(tonnage=50, max_speed=0, engine_rating=int(engine), num_sinks=10)


@step(r'a unit of type (\w+)')
def kind(world, name): world['unit'] = Mech(unit_type=UnitType[name])


@step(r'FASA cost is calculated')
def cost(world): world['cost'] = economy.fasa_cost(world['unit']).value


@step(r'cost is (\d+)')
def cost_result(world, value): eq(world['cost'], int(value))


@step(r'a 50-ton unit with one upper one lower and one terminal actuator plus shoulder or hip')
def actuators(world):
    world['unit'] = Mech(tonnage=50)
    for i in range(4): world['unit'].sections[0].criticals[i].type = i2special(i)


@step(r'location math is applied for (arm|leg)')
def location(world, name): world['price'] = economy.actuator_cost(world['unit'], 0, name == 'leg').value


@step(r'added price is (\d+)')
def price(world, value): eq(world['price'], int(value))


@step(r'a valid source part category (\w+)')
def table(world, category):
    world['tables'] = economy.CostTables()
    world['part'] = {'weapon':1, 'ammo':193, 'special':394, 'bomb':385, 'cargo':512}[category]


@step(r'its cost is set to (\d+)')
def set_cost(world, value): world['tables'].set(world['part'], int(value))


@step(r'reading the same part returns exactly (\d+)')
def get_cost(world, value): eq(world['tables'].get(world['part']), int(value))
