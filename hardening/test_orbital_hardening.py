"""Orbital input, class-specific local touchdown and free-fall boundaries."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from acceptance.movement.context import fresh, set_hex, psr
from entities.mech import Mech, MechStatus as S, MechStatus2 as S2, UnitType, MoveType
from physics import orbital
from physics.hexmath import ZSCALE
from core.events import EventType
from systems import combat


def ready():
    w = {}
    fresh(w)
    return w


class TestOrbitalHardening(unittest.TestCase):
    def test_initiation_refusal_feedback_and_relocation_order(self):
        for arg, message in (('1', 'Invalid attributes!'), ('1 2 3 4', 'Invalid attributes!'), ('a 2', 'Invalid number!'), ('1 2 x', 'Invalid number!'), ('-1 2', 'Invalid co-ordinates!')):
            w = ready()
            self.assertEqual((False, message), orbital.initiate_ood(w['engine'], w['unit'], arg))
        for state, message in (('cocoon', 'OOD already in progress!'), ('map', 'Invalid co-ordinates!'), ('fallen', "You'll have to get up first."), ('digging', "You're too busy digging in."), ('mass', 'Orbital drop requires measured equipment mass.')):
            w = ready()
            u = w['unit']
            if state == 'cocoon': u.cocoon = -1
            if state == 'map': u.map = None
            if state == 'fallen': u.set_status(S.FALLEN)
            if state == 'digging': u.digging = True
            if state == 'mass': u.measured_mass = None
            self.assertEqual((False, message), orbital.initiate_ood(w['engine'], u, '4 5'))
            self.assertEqual((4, 5) if state in ('fallen', 'digging', 'mass') else (3, 3), (u.x, u.y))

    def test_default_orbit_height_cancels_only_own_movement_and_clears_modes(self):
        w = ready()
        u = w['unit']
        other = Mech.create_test_mech()
        own = w['engine'].schedule_event(5, EventType.MOVE, lambda e: None, data=u)
        others = w['engine'].schedule_event(5, EventType.MOVE, lambda e: None, data=other)
        u.set_status2(S2.EVADING | S2.SPRINTING)
        u._engine = None
        self.assertEqual((True, 'OOD initiated.'), orbital.initiate_ood(w['engine'], u, '4 5'))
        self.assertEqual((300, 300 * ZSCALE, 11), (u.z, u.fz, u.cocoon))
        self.assertIs(w['engine'], u._engine)
        self.assertFalse(u.has_status2(S2.EVADING | S2.SPRINTING))
        self.assertTrue(own.zombie)
        self.assertFalse(others.zombie)
        self.assertTrue(w['engine'].has_event(EventType.OOD, u))
        self.assertIn('OOD initiated.', u.movement_messages)

    def test_airborne_initialization_needs_no_ground_mass_or_cocoon(self):
        for kind, move in ((UnitType.VTOL, MoveType.VTOL), (UnitType.AERO, MoveType.FLY)):
            w = ready()
            u = w['unit']
            u.unit_type, u.move_type = kind, move
            u.measured_mass = None
            u.set_status(S.LANDED)
            u.desired_angle = 90
            self.assertTrue(orbital.initiate_ood(w['engine'], u, '4 5 20')[0])
            self.assertEqual((20, 20 * ZSCALE, 32.25, 0, 0), (u.z, u.fz, u.desired_speed, u.desired_angle, u.cocoon))
            self.assertFalse(u.has_status(S.LANDED))
            self.assertFalse(w['engine'].has_event(EventType.OOD, u))
            self.assertTrue(w['engine'].has_event(EventType.MOVE, u))

    def test_battlesuit_crash_uses_each_existing_section_and_four_sided_dice(self):
        w = ready()
        u = w['unit']
        u.unit_type = UnitType.BSUIT
        u.sections[7].internal_orig = u.sections[7].internal = u.sections[7].armor = 0
        u.sections[0].internal_orig = u.sections[0].internal = 1
        before = [s.armor for s in u.sections]
        with psr(w), patch('random.randint', return_value=4) as draw, patch.object(combat, 'roll_1d6', return_value=1), patch.object(combat, 'apply_damage_with_transfer', wraps=combat.apply_damage_with_transfer) as applied:
            orbital._crash_battlesuit(u, -2)
        self.assertEqual(14, draw.call_count)
        for call in draw.call_args_list: self.assertEqual((1, 4), call.args)
        self.assertEqual(list(range(7)), [call.args[1] for call in applied.call_args_list])
        for call in applied.call_args_list:
            self.assertEqual(8, call.args[2])
            self.assertEqual({'attacker': u, 'engine': w['engine']}, call.kwargs)
        self.assertEqual([a - 8 for a in before[:7]] + before[7:], [s.armor for s in u.sections])
        self.assertEqual(0, u.last_fall_levels)

    def test_cocoon_feedback_and_engine_requirement(self):
        w = ready()
        u = w['unit']
        u.cocoon, u.z = 11, 10
        orbital.cocoon_damage(u, u, 5)
        self.assertEqual(6, u.cocoon)
        self.assertIn('Your cocoon has been hit for 5 points of damage!', u.movement_messages)
        u.jump_mp = 1
        orbital.cocoon_damage(u, u, 6)
        self.assertEqual(-1, u.cocoon)
        self.assertIn('You initiate your jumpjets to compensate for the breached cocoon!', u.movement_messages)
        u.jump_mp, u.cocoon, u._engine = 0, 1, None
        with self.assertRaises(ValueError) as error:
            orbital.cocoon_damage(u, u, 1)
        self.assertEqual('Orbital damage requires the owning event engine', str(error.exception))
    def test_height_relative_to_ice_bridge_and_raised_ground(self):
        for terrain, elevation, z, expected in (('BRIDGE', 4, 4, 0), ('BRIDGE', 4, 3, 4), ('GRASSLAND', 4, 3, -1), ('GRASSLAND', 4, 7, 3), ('ICE', 4, -1, 3), ('ICE', 4, 0, 0)):
            w = ready()
            set_hex(w, terrain, elevation)
            w['unit'].z = z
            with self.subTest(terrain=terrain, elevation=elevation, z=z):
                self.assertEqual(expected, orbital.height_above_ground(w['unit']))

    def test_touchdown_targets_preserve_class_skill_base_and_absent_pilot_context(self):
        for kind, base, expected in ((UnitType.MW, 3, 6), (UnitType.BSUIT, 3, 6), (UnitType.MECH, 3, 10)):
            w = ready()
            u = w['unit']
            u.unit_type, u.pilot.piloting, u.pilot_skill_base, u.cocoon = kind, 7, base, 1
            self.assertEqual(expected, orbital._touchdown_target(u))
        for ic, pilot, expected in ((False, True, 7), (True, True, 7), (False, False, 7), (True, False, 106)):
            w = ready()
            u = w['unit']
            u.pilot_skill, u.in_character, u.cocoon = 7, ic, 1
            if not pilot: u.pilot = None
            self.assertEqual(expected, orbital._touchdown_target(u))

    def test_touchdown_margin_double_addition_status_penalties_and_xp_cap(self):
        for state, target, roll, expected_margin, xp in (('ready', 5, 5, 0, 2), ('ready', 3, 4, 2, 4), ('ready', 2, 12, 20, 0), ('ready', 3, 12, 18, 20), ('ready', 5, 4, -2, 0), ('fallen', 5, 6, -8, 20), ('unconscious', 5, 6, -18, 20), ('blinded', 5, 6, -18, 20), ('stopped', 15, 6, -38, 0)):
            w = ready()
            u = w['unit']
            u.pilot.piloting = 5 if state == 'stopped' else target
            u.cocoon, u.orbital_pilot_xp = 1, 7
            if state == 'fallen': u.set_status(S.FALLEN)
            if state == 'unconscious': u.set_status(S.UNCONSCIOUS)
            if state == 'blinded': u.set_status(S.BLINDED)
            if state == 'stopped': u.clear_status(S.STARTED)
            with self.subTest(state=state, target=target, roll=roll), patch.object(combat, 'roll_2d6', return_value=roll):
                self.assertEqual(expected_margin, orbital._touchdown_margin(u))
                self.assertEqual(target, u.last_ood_target)
                self.assertEqual(7 + xp, u.orbital_pilot_xp)
                self.assertEqual(0, u.cocoon)

    def test_resolve_touchdown_tie_battlesuit_and_nonmech_factors(self):
        for kind, cocoon, roll, levels in ((UnitType.MECH, 11, 5, None), (UnitType.VEH_GROUND, 11, 4, 6), (UnitType.VEH_GROUND, 1, 4, 2), (UnitType.BSUIT, 11, 3, 0)):
            w = ready()
            u = w['unit']
            u.unit_type, u.cocoon, u.pilot.piloting = kind, cocoon, 5
            # Combat-safe suppresses unrelated fall damage, but BSUIT's C
            # touchdown damage still executes before its zero-level fall.
            u.set_status(S.COMBAT_SAFE)
            with patch.object(combat, 'roll_2d6', return_value=roll), patch.object(combat, 'roll_1d6', return_value=1), patch('random.randint', return_value=1):
                orbital._resolve_touchdown(u)
            self.assertEqual(levels, getattr(u, 'last_fall_levels', None))

    def test_orbital_descent_uses_elevated_ground_and_marks_los(self):
        from systems.los import MECHMAPFLAG_MOVED
        w = ready()
        u = w['unit']
        set_hex(w, 'GRASSLAND', 2)
        u.set_status(S.COMBAT_SAFE)
        u.mapflag = 0
        self.assertTrue(orbital.initiate_ood(w['engine'], u, '3 3 7')[0])
        self.assertTrue(u.mapflag & MECHMAPFLAG_MOVED)
        for expected_z, expected_cocoon in ((5, 11), (2, 0)):
            u.mapflag = 0
            w['engine'].run_ticks(1)
            self.assertEqual((expected_z, expected_z * ZSCALE, expected_cocoon), (u.z, u.fz, u.cocoon))
            self.assertTrue(u.mapflag & MECHMAPFLAG_MOVED)
        self.assertIn('Your unit touches down!', u.movement_messages)
        self.assertTrue(w['engine'].has_event(EventType.MOVE, u))

    def test_cocoon_breach_cancels_only_own_drop(self):
        w = ready()
        u = w['unit']
        self.assertTrue(orbital.initiate_ood(w['engine'], u, '3 3 20')[0])
        other = Mech.create_test_mech()
        other_event = w['engine'].schedule_event(10, EventType.OOD, lambda e: None, data=other)
        orbital.cocoon_damage(u, u, 11)
        self.assertFalse(w['engine'].has_event(EventType.OOD, u))
        self.assertFalse(other_event.zombie)
        self.assertEqual(3, w['engine'].events.time_until_type_data(EventType.FALL, u))

    def test_fall_event_power_and_acceleration_boundaries(self):
        from systems.los import MECHMAPFLAG_MOVED
        for started, move, fuel, free, speed, expected in ((True, MoveType.FLY, 1, False, -2, -1), (True, MoveType.VTOL, 1, False, -2, -1), (True, MoveType.FLY, 0, True, -2, -1), (True, MoveType.FLY, 0, False, -2, -3), (False, MoveType.FLY, 1, True, -2, -3), (True, MoveType.BIPED, 1, True, -2, -3), (False, MoveType.BIPED, 1, True, 0, -1), (False, MoveType.BIPED, 1, True, 1, 2), (True, MoveType.FLY, 1, False, 0, None)):
            w = ready()
            u = w['unit']
            u.move_type, u.fuel, u.free_fuel, u.z = move, fuel, free, 20
            u.fz, u.mapflag = 20 * ZSCALE, 0
            if not started: u.clear_status(S.STARTED)
            with self.subTest(started=started, move=move, fuel=fuel, free=free, speed=speed), patch.object(w['engine'], 'schedule_event', wraps=w['engine'].schedule_event) as schedule:
                orbital.fall_event(SimpleNamespace(data=u, data2=speed))
                if expected is None:
                    schedule.assert_not_called()
                    self.assertEqual(20, u.z)
                else:
                    self.assertEqual((20 - abs(expected), (20 - abs(expected)) * ZSCALE), (u.z, u.fz))
                    self.assertEqual(expected, schedule.call_args.kwargs['data2'])
                    self.assertEqual(3, w['engine'].events.time_until_type_data(EventType.FALL, u))
                    self.assertTrue(u.mapflag & MECHMAPFLAG_MOVED)

    def test_fall_equal_ground_distance_impacts_now(self):
        w = ready()
        u = w['unit']
        u.z = 2
        u.set_status(S.COMBAT_SAFE | S.JUMPING)
        with patch.object(combat, 'roll_1d6', return_value=1):
            orbital.fall_event(SimpleNamespace(data=u, data2=-1))
        self.assertEqual(3, u.last_fall_levels)
        self.assertFalse(u.is_jumping)
        self.assertFalse(w['engine'].has_event(EventType.FALL, u))
        self.assertIn('You hit the ground!', u.movement_messages)
    def test_settle_applies_ice_check_and_stacking_only_while_upright(self):
        from physics import movement, collision
        for fallen in (False, True):
            w = ready()
            u = w['unit']
            set_hex(w, 'ICE', 2)
            if fallen: u.set_status(S.FALLEN)
            with patch.object(movement, 'possibly_drop_thru_ice', wraps=movement.possibly_drop_thru_ice) as ice_check, patch('random.randint', return_value=6), patch.object(collision, 'domino_space', wraps=collision.domino_space) as stacking:
                orbital._settle_touchdown(u)
            ice_check.assert_called_once_with(u)
            if fallen: stacking.assert_not_called()
            else: stacking.assert_called_once_with(u, 2)
            self.assertTrue(w['engine'].has_event(EventType.MOVE, u))

    def test_settle_stops_beached_watercraft_and_preserves_other_desired_speeds(self):
        for move, terrain, expected in ((MoveType.SUB, 'GRASSLAND', 0), (MoveType.SUB, 'WATER', 10), (MoveType.BIPED, 'GRASSLAND', 10)):
            w = ready()
            u = w['unit']
            u.move_type, u.desired_speed = move, 10
            set_hex(w, terrain, 2)
            orbital._settle_touchdown(u)
            self.assertEqual(expected, u.desired_speed)

    def test_settle_water_death_class_and_waterproof_bit(self):
        from systems import damage
        for kind, terrain, special, dies in ((UnitType.VEH_GROUND, 'WATER', 0, True), (UnitType.VTOL, 'WATER', 0, True), (UnitType.BSUIT, 'WATER', 0, True), (UnitType.AERO, 'WATER', 0, True), (UnitType.DS, 'WATER', 0, True), (UnitType.MECH, 'WATER', 0, False), (UnitType.VEH_GROUND, 'GRASSLAND', 0, False), (UnitType.VEH_GROUND, 'WATER', 0x100000, False), (UnitType.VEH_GROUND, 'WATER', 1, True)):
            w = ready()
            u = w['unit']
            u.unit_type, u.specials2 = kind, special
            set_hex(w, terrain, 2)
            with self.subTest(kind=kind, terrain=terrain, special=special), patch.object(damage, 'destroy_mech', wraps=damage.destroy_mech) as destroyed:
                orbital._settle_touchdown(u)
                self.assertEqual(dies, u.is_destroyed)
                if dies:
                    self.assertEqual('FLOOD', u.kill_reason)
                    destroyed.assert_called_once_with(u, u, showboom=False, reason=damage.KILL_TYPE_FLOOD)
                else: destroyed.assert_not_called()

    def test_cocoon_uses_whole_fixed_point_fifths_of_mass(self):
        w = ready()
        u = w['unit']
        u.measured_mass = 49 * 1024 + 1
        self.assertTrue(orbital.initiate_ood(w['engine'], u, '3 3 20')[0])
        self.assertEqual(10, u.cocoon)

    def test_combat_safe_touchdown_still_applies_the_ice_surface_check(self):
        from entities.map import WATER
        w = ready()
        u = w['unit']
        set_hex(w, 'ICE', 2)
        u.set_status(S.COMBAT_SAFE)
        self.assertTrue(orbital.initiate_ood(w['engine'], u, '3 3 0')[0])
        with patch('random.randint', return_value=1), patch.object(combat, 'roll_1d6', return_value=1):
            w['engine'].run_ticks(1)
        self.assertEqual(WATER, w['map'].terrain(3, 3))
        self.assertEqual((-2, 0), (u.z, u.cocoon))
        self.assertTrue(w['engine'].has_event(EventType.MOVE, u))
