"""Movement orbital acceptance bindings using production behavior."""
from unittest.mock import patch
from entities.mech import Location
from core.events import EventType
from physics import orbital
from acceptance.movement.context import advance, boolean, equal, set_hex, bounded_integer


def orbit_setup(w, tons, height, roll):
    w['unit'].tonnage = int(tons)
    w['unit'].measured_mass = int(tons) * 1024
    w.update(height=int(height), roll=bounded_integer(roll, 2, 12, 'pilot roll'))


def orbit_start(w, ticks):
    u = w['unit']
    result = orbital.initiate_ood(w['engine'], u, f'{u.x} {u.y} {w["height"]}')
    assert result[0], result
    advance(w, ticks)


def orbit_state(w, height, cocoon, pending):
    equal((w['unit'].z, w['unit'].cocoon, w['engine'].has_event(EventType.OOD, w['unit'])),
          (int(height), int(cocoon), boolean(pending)))


def cocoon_setup(w, height, cocoon, capability):
    capability = float(capability)
    if capability < 0:
        raise ValueError('jump capability must be nonnegative')
    w['height'] = int(height)
    orbit_start(w, 0)
    w['unit'].cocoon = int(cocoon)
    w['unit'].jump_mp = capability


def cocoon_hit(w, damage):
    orbital.cocoon_damage(w['unit'], w['unit'], int(damage))


def cocoon_result(w, cocoon, ood, fall):
    equal((w['unit'].cocoon, w['engine'].has_event(EventType.OOD, w['unit']), w['engine'].has_event(EventType.FALL, w['unit'])),
          (int(cocoon), boolean(ood), boolean(fall)))


def touchdown_setup(w, target):
    w['unit'].pilot.piloting = int(target)
    w['height'] = 0
    orbit_start(w, 0)


def touchdown_terrain(w, name, cocoon, roll):
    set_hex(w, name)
    w['unit'].cocoon = int(cocoon)
    w['roll'] = bounded_integer(roll, 2, 12, 'pilot roll')


def touchdown(w):
    advance(w, 1)


def touchdown_result(w, target, levels):
    equal((w['unit'].last_ood_target, getattr(w['unit'], 'last_fall_levels', 0)), (int(target), int(levels)))


def interception_setup(w, cocoon, armor):
    cocoon_setup(w, 20, cocoon, 0)
    w['unit'].sections[Location.CTORSO].armor = int(armor)


def interception(w, damage, roll):
    from systems.combat import apply_damage_with_transfer
    with patch('systems.combat.roll_2d6', return_value=bounded_integer(roll, 2, 12, 'interception roll')):
        apply_damage_with_transfer(w['unit'], Location.CTORSO, int(damage))


def interception_result(w, cocoon, armor):
    equal((w['unit'].cocoon, w['unit'].sections[Location.CTORSO].armor), (int(cocoon), int(armor)))


def falling_setup(w, tons, height, cocoon):
    w['unit'].tonnage = int(tons)
    cocoon_setup(w, height, cocoon, 0)


def fall_advance(w, damage, ticks):
    cocoon_hit(w, damage)
    advance(w, ticks)


def falling_result(w, height, pending, levels):
    equal((w['unit'].z, w['engine'].has_event(EventType.FALL, w['unit']), getattr(w['unit'], 'last_fall_levels', 0)),
          (int(height), boolean(pending), int(levels)))


BINDINGS = [
    (r'a ready (\d+) ton mech at height ([-\d]+) over GRASSLAND with pilot roll (\d+)', orbit_setup),
    (r'orbital drop is initiated at its current coordinates and advances (\d+) seconds', orbit_start),
    (r'height is ([-\d]+) cocoon is ([-\d]+) and orbital descent is (True|False)', orbit_state),
    (r'an orbital dropping mech at height (\d+) with cocoon ([-\d]+) and jump capability ([-.\d]+) MP', cocoon_setup),
    (r'its cocoon takes (\d+) damage', cocoon_hit),
    (r'cocoon is ([-\d]+) orbital descent is (True|False) and free fall is (True|False)', cocoon_result),
    (r'an orbital dropping MECH ready to touch down with piloting target (\d+) before terrain and cocoon modifiers', touchdown_setup),
    (r'touchdown terrain (\w+) cocoon ([-\d]+) and pilot roll (\d+)', touchdown_terrain),
    (r'the touchdown event runs', touchdown),
    (r'required roll is (\d+) and fall levels applied are (\d+)', touchdown_result),
    (r'an orbital dropping mech with cocoon ([-\d]+) and intact torso armor (\d+)', interception_setup),
    (r'external torso damage (\d+) is resolved with interception roll (\d+)', interception),
    (r'cocoon is ([-\d]+) and torso armor is (\d+)', interception_result),
    (r'an orbital dropping (\d+) ton mech at height (\d+) with no jump jets and cocoon (\d+)', falling_setup),
    (r'its cocoon takes (\d+) damage and the session advances (\d+) seconds', fall_advance),
    (r'height is ([-\d]+) free fall is (True|False) and impact fall levels are (\d+)', falling_result),
]
