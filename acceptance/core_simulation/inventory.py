"""Weapon and ammunition APS cases against authoritative slot helpers."""
from entities.mech import FireMode as F, AmmoMode as A
from entities.crittypes import i2weapon, i2ammo
from entities.weapon import get_weapon
from systems import weapon_inventory as weapons, combat_ammunition as ammo
from systems.weapon_modes import find_weapon_number_on_mech
from . import step, eq
from .startup import fixture


def mount(world, name, count=None, first=0):
    unit = fixture(world)
    weapon = get_weapon(name)
    for slot in unit.sections[0].criticals[first:first + (weapon.crits if count is None else count)]:
        slot.type = i2weapon(weapon.index)
    world['weapon'] = weapon
    return unit


@step(r'a MECH weapon of category (\w+) with weapon data (\d+) section recycle (\d+) and destroyed ([01])')
def lookup_input(world, category, data, physical, destroyed):
    unit = mount(world, 'IS.SmallLaser' if category == 'beam' else 'IS.LRM-5')
    slot = unit.sections[0].criticals[0]
    slot.data, slot.firemode = int(data), F.DESTROYED_MODE if destroyed == '1' else F.NONE
    unit.sections[0].recycle = int(physical)


@step(r'weapon lookup uses sight ([01])')
def lookup(world, sight):
    world['lookup'] = find_weapon_number_on_mech(world['unit'], 0, sight == '1')[0]


@step(r'lookup result code is ([-\w]+)')
def lookup_result(world, value):
    eq(world['lookup'], world['weapon'].index if value == 'catalog' else int(value))


@step(r'a MECH catalog weapon requiring (\d+) crits and a contiguous run of (\d+) matching slots')
def runs_input(world, required, actual):
    mount(world, {'3': 'IS.PPC', '9': 'CL.LB20-XAC'}[required], int(actual))


@step(r'FindWeapons_Advanced inspects that section')
def runs(world):
    world['runs'] = weapons.find_weapons(world['unit'], 0)


@step(r'weapon count or failure is ([-\d]+)')
def runs_result(world, value):
    eq(-1 if world['runs'] is None else len(world['runs']), int(value))


@step(r'a weapon run of (\d+) with destroyed slots (\d+) and disabled slots (\d+)')
def status_input(world, size, destroyed, disabled):
    unit = mount(world, {'1': 'IS.SmallLaser', '3': 'IS.PPC', '6': 'IS.LB10-XAC'}[size])
    for i, slot in enumerate(unit.sections[0].criticals[:int(destroyed) + int(disabled)]):
        slot.firemode = F.DESTROYED_MODE if i < int(destroyed) else F.DISABLED_MODE


@step(r'WeaponIsNonfunctional is inspected')
def status(world):
    world['functional'] = weapons.weapon_is_nonfunctional(world['unit'], 0, 0)


@step(r'functional status code is ([-\d]+)')
def status_result(world, value):
    eq(world['functional'], int(value))


@step(r'the first weapon run begins at critical 3 and ordinal slot 0 is ([\w-]+) while weapon critical 3 is ready')
def ordinal_input(world, value):
    unit = mount(world, 'IS.SmallLaser', first=3)
    unit.sections[0].criticals[0].firemode = F.DESTROYED_MODE if value == 'empty-destroyed' else F.NONE


@step(r'FindWeaponFromIndex searches that weapon type')
def ordinal(world):
    world['from_index'] = weapons.find_weapon_from_index(world['unit'], world['weapon'].index)


@step(r'found result is ([01]) and returned critical is 3')
def ordinal_result(world, found):
    eq(world['from_index'], (found == '1', 0, 3))


@step(r'ammo base capacity (\d+) with modes ([\w+]+)')
def capacity_input(world, base, modes):
    fire = ammomode = 0
    for mode in modes.split('+'):
        if mode == 'HALFTON': fire |= F.HALFTON_MODE
        else: ammomode |= {'none': 0, 'AP': A.AC_AP_MODE, 'CASELESS': A.AC_CASELESS_MODE, 'MML_LRM': A.MML_LRM_MODE}[mode]
    world['capacity_args'] = int(base), fire, ammomode


@step(r'FullAmmo is requested')
def capacity(world):
    world['capacity'] = ammo.ammo_capacity(*world['capacity_args'])


@step(r'full capacity is (\d+)')
def capacity_result(world, value):
    eq(world['capacity'], int(value))


def bins(world, rounds):
    unit = fixture(world)
    weapon = get_weapon('IS.AC/10')
    for i, count in enumerate(rounds):
        slot = unit.sections[0].criticals[i]
        slot.type, slot.data = i2ammo(weapon.index), count
    return unit


@step(r'same-type same-mode bins of capacity 10 with current rounds 4 and 6 and second nonfunctional ([01])')
def grouped_input(world, broken):
    unit = bins(world, [4, 6])
    unit.sections[0].criticals[1].firemode = F.BROKEN_MODE if broken == '1' else F.NONE


@step(r'ammunition inventory includes all groups')
def grouped(world):
    world['ammo_groups'] = ammo.find_ammunition(world['unit'], True)


@step(r'group current is (\d+) and maximum is 20')
def grouped_result(world, value):
    eq([(g.current, g.maximum) for g in world['ammo_groups']], [(int(value), 20)])


@step(r'one ammo group has zero functional rounds and capacity 10')
def empty_input(world):
    bins(world, [0])


@step(r'ammunition inventory uses returnall ([01])')
def empty(world, returnall):
    world['ammo_groups'] = ammo.find_ammunition(world['unit'], returnall == '1')


@step(r'returned group count is (\d+)')
def empty_result(world, value):
    eq(len(world['ammo_groups']), int(value))
