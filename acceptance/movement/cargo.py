"""Movement cargo acceptance bindings using production behavior."""
from entities.mech import MechStatus as S, MechStatus2 as S2
from physics.cargo import cargo_max_speed
from acceptance.movement.context import near


def cached_speed(w, maximum):
    cargo_max_speed(w['unit'])
    w['unit'].cached_max_speed = float(maximum)


def boosts(w, enhancement):
    valid = {'NONE', 'MASC', 'SUPERCHARGER', 'SPRINT', 'MASC_SUPERCHARGER', 'MASC_SPRINT', 'MASC_SUPERCHARGER_SPRINT', 'SPRINT_SPEED_DEMON'}
    if enhancement not in valid:
        raise ValueError(enhancement)
    for name, flag in (('MASC', S.MASC_ENABLED), ('SUPERCHARGER', S.SCHARGE_ENABLED)):
        if name in enhancement:
            w['unit'].set_status(flag)
    if 'SPRINT' in enhancement:
        w['unit'].set_status2(S2.SPRINTING)
    if 'SPEED_DEMON' in enhancement:
        w['unit'].pilot.speed_demon = True


def effective_speed(w):
    w['maximum'] = cargo_max_speed(w['unit'])


def maximum_result(w, maximum):
    near(w['maximum'], maximum)


def masses(w, nominal, actual, load):
    w['unit'].tonnage = int(nominal)
    w['unit'].measured_mass = int(actual) * 1024
    w['unit'].carried_cargo = int(load) * 1024 // 2


def base_speed(w, maximum):
    w['unit'].max_speed = float(maximum)


BINDINGS = [
    (r'cached unboosted maximum speed ([-.\d]+) KPH and no cargo', cached_speed),
    (r'enabled speed enhancements (\w+)', boosts),
    (r'the effective maximum speed is requested', effective_speed),
    (r'effective maximum speed is ([-.\d]+) KPH', maximum_result),
    (r'nominal mass (\d+) tons actual mass (\d+) tons and effective carried mass (\d+) tons', masses),
    (r'unboosted maximum speed ([-.\d]+) KPH with weight overspeeding disabled', base_speed),
]
