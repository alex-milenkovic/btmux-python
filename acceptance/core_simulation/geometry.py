"""Coordinate, neighbor, arc, target and LOS helpers through production owners."""
from entities.map import GameMap, visit_neighbor_hexes
from entities.mech import Mech
from physics import hexmath as h
from systems import combat, targeting, ecm
from . import step, eq
from .startup import fixture


@step(r'integer heading ([-\d]+)')
def heading(world, value):
    world['heading'] = int(value)


@step(r'AcceptableDegree is evaluated')
def degree(world):
    world['heading_result'] = h.acceptable_degree(world['heading'])


@step(r'heading result is (\d+)')
def degree_result(world, value):
    eq(world['heading_result'], int(value))


@step(r'source point zero and target coordinates (\S+)')
def point(world, xyz):
    world['point'] = tuple(map(float, xyz.split(',')))


@step(r'horizontal and vertical bearings are requested')
def bearings(world):
    x, y, z = world['point']
    world['bearings'] = h.find_bearing(0, 0, x, y), h.find_z_bearing(0, 0, 0, x, y, z)


@step(r'horizontal bearing is (\d+) and absolute vertical bearing is (\d+)')
def bearing_result(world, horizontal, vertical):
    eq(world['bearings'], (int(horizontal), int(vertical)))


@step(r'an empty 4 by 4 map')
def board(world):
    world['board'] = GameMap(4, 4)


@step(r'neighbors of hex (\S+) are visited')
def neighbors(world, xy):
    world['neighbors'] = []
    visit_neighbor_hexes(world['board'], *map(int, xy.split(',')),
                        lambda board, x, y: world['neighbors'].append((x, y)))


@step(r'ordered callback coordinates are (\S+)')
def neighbors_result(world, coordinates):
    eq(world['neighbors'], [tuple(map(int, xy.split(','))) for xy in coordinates.split(';')])


@step(r'a non-turret unit with source relative bearing (\d+)')
def arc_input(world, relative):
    unit = fixture(world)
    unit.fx = unit.fy = 0
    unit.facing = int(relative)


@step(r'general weapon arc is classified')
def arc(world):
    world['arc'] = h.in_weapon_arc(world['unit'], 0, -100)


@step(r'arc is (\w+)')
def arc_result(world, name):
    eq(world['arc'], {'forward': h.FORWARDARC, 'rear': h.REARARC, 'right': h.RSIDEARC, 'left': h.LSIDEARC}[name])


@step(r'stored target ([\w-]+) and valid hex coordinates with target Z 3')
def target_input(world, mode):
    unit = fixture(world)
    unit.targ_x, unit.targ_y, unit.targ_z = 2, 3, 3
    if mode == 'missing-unit': unit.target = 10000000
    elif mode == 'registered-unit':
        peer = Mech()
        peer.fx, peer.fy, peer.fz = 10, 20, 30
        world['core_engine'].register_entity(peer)
        unit.target = peer._id


@step(r'FindTargetXY is requested')
def target(world):
    world['target_xyz'] = combat.find_target_xy(world['unit'])


@step(r'target resolution is ([\w-]+)')
def target_result(world, value):
    eq(world['target_xyz'], {'none': None, 'unit-xyz': (10, 20, 30), 'hex-z3': (*h.hex_to_float(2, 3), 193.5)}[value])


@step(r'roster IDs AB followed by Ab with distinct identities')
def roster(world):
    unit = fixture(world)
    unit.contact_id = 'AB'
    peer = Mech(contact_id='Ab')
    unit.map.add_mech(peer)
    world['core_engine'].register_entity(peer)


@step(r'target ID text (\S+) is resolved')
def contact(world, token):
    world['contact'] = targeting.contact_target(world['unit'], token)


@step(r'selected roster ordinal is ([-\d]+)')
def ordinal(world, expected):
    contact = world['contact']
    eq(world['unit'].map.mechs_on_map.index(contact) if contact else -1, int(expected))


@step(r'unit map flag is (\d+) and map moves is 4')
def flag(world, bits):
    unit = fixture(world)
    unit.mapflag, unit.map.moves = int(bits), 4


@step(r'MarkForLOSUpdate runs')
def los(world):
    ecm.mark_for_los_update(world['unit'])


@step(r'unit map flag is 1 and map moves is 5')
def los_result(world):
    eq((world['unit'].mapflag, world['unit'].map.moves), (1, 5))
