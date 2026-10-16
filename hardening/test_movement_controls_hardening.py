"""Control input, envelope, permission and destination boundaries."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from acceptance.movement.context import fresh, psr, set_hex
from entities.mech import Mech, MechStatus as S, MechStatus2 as S2, UnitType, MoveType, CritStatus, Specials
from entities.pilot import Pilot
from core.events import EventType
from systems import movement_commands as controls
from systems import combat
from physics.jump import mech_jump


def ready():
    w = {}
    fresh(w)
    w['unit'].jump_mp = 4
    return w


def flying(w):
    u = w['unit']
    u.unit_type, u.move_type, u.fuel = UnitType.VTOL, MoveType.VTOL, 1
    return u


class TestMovementControlsHardening(unittest.TestCase):
    def test_queries_accept_none_and_whitespace_and_preserve_motion(self):
        for arg in (None, '   '):
            w = ready()
            u = flying(w)
            u.facing, u.speed, u.vertical_speed = 123, 12.34, -5.67
            for command, expected in ((controls.heading, 'Your current heading is 123.'), (controls.speed, 'Your current speed is 12.34.'), (controls.vertical, 'Current vertical speed is -5.67 KPH.')):
                with self.subTest(command=command.__name__, arg=arg):
                    self.assertEqual((True, expected), command(w['engine'], u, arg))
            self.assertEqual((123, 12.34, -5.67), (u.facing, u.speed, u.vertical_speed))

    def test_heading_blockers_and_landed_aircraft_exception(self):
        for condition in ('stationary', 'fortified', 'busy', 'dug_in', 'beached', 'spinning'):
            w = ready()
            u = w['unit']
            if condition == 'stationary': u.move_type = MoveType.NONE
            if condition == 'fortified': u.set_status2(S2.FORTIFIED)
            if condition == 'busy': u.set_status(S.PERFORMING_ACTION)
            if condition == 'dug_in': u.dug_in = True
            if condition == 'beached': u.move_type = MoveType.SUB
            if condition == 'spinning':
                u.unit_type = UnitType.AERO
                u.set_crit_status(CritStatus.SPINNING)
            with self.subTest(condition=condition):
                self.assertEqual((False, 'You cannot turn at this time.'), controls.heading(w['engine'], u, '90'))
        for kind in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS):
            w = ready()
            u = w['unit']
            u.unit_type = kind
            u.set_crit_status(CritStatus.SPINNING)
            u.set_status(S.LANDED)
            u.digging = True
            self.assertEqual((True, 'Heading changed to 90.'), controls.heading(w['engine'], u, '90.9'))
            self.assertEqual(90, u.desired_facing)
            self.assertEqual(False, u.digging)

    def test_vtol_horizontal_envelope_includes_the_vertical_limit(self):
        for vertical, accepted, maximum in ((38.7, True, 51.6), (64.5, True, 0), (64.6, False, None), (-64.6, False, None)):
            w = ready()
            u = flying(w)
            u.vertical_speed = vertical
            result = controls.speed(w['engine'], u, 'run')
            with self.subTest(vertical=vertical):
                self.assertEqual(accepted, result[0])
                if accepted: self.assertAlmostEqual(maximum, u.desired_speed)
                else: self.assertEqual('Invalid vertical speed envelope.', result[1])

    def test_vtol_fuel_and_free_fuel_apply_to_both_speed_commands(self):
        for command in (controls.speed, controls.vertical):
            for fuel, free, accepted in ((0, False, False), (1, False, True), (0, True, True)):
                w = ready()
                u = flying(w)
                u.fuel, u.free_fuel = fuel, free
                result = command(w['engine'], u, '1')
                with self.subTest(command=command.__name__, fuel=fuel, free=free):
                    self.assertEqual(accepted, result[0])
                    if not accepted: self.assertEqual("You're out of fuel!", result[1])

    def test_each_run_blocker_and_high_water_rejects_running(self):
        for condition in ('dumping', 'unjamming', 'crew_stunned', 'tail_rotor_destroyed', 'stunned', 'water', 'highwater'):
            w = ready()
            u = w['unit']
            if condition in ('water', 'highwater'):
                set_hex(w, 'WATER' if condition == 'water' else 'HIGHWATER', 2)
                u.z = -2
            elif condition == 'stunned': u.set_crit_status(CritStatus.MECH_STUNNED)
            else: setattr(u, condition, True)
            with self.subTest(condition=condition):
                self.assertEqual((False, "You can't run through water!" if condition in ('water', 'highwater') else 'You cannot run in your current state!'), controls.speed(w['engine'], u, 'run'))
                self.assertTrue(controls.speed(w['engine'], u, 'walk')[0])

    def test_nonpilot_in_character_permission_boundaries(self):
        for caller_kind in ('none', 'pilot', 'visitor', 'wizard'):
            for in_character in (False, True):
                for value in (-1, 0, .5, 43, 43.01):
                    w = ready()
                    u = w['unit']
                    u.in_character = in_character
                    caller = {'none': None, 'pilot': u.pilot, 'visitor': SimpleNamespace(), 'wizard': SimpleNamespace(wizard=True)}[caller_kind]
                    result = controls.speed(w['engine'], u, str(value), caller)
                    allowed = not (in_character and caller_kind == 'visitor' and (value < 0 or value > 43))
                    with self.subTest(caller=caller_kind, ic=in_character, value=value):
                        self.assertEqual(allowed, result[0])
                        if allowed: self.assertAlmostEqual(value, u.desired_speed)
                        else: self.assertEqual('Not being the Pilot, you cannot go backwards or faster than walking speed.', result[1])

    def test_reverse_towing_and_sprinting(self):
        for carrying, salvage, sprint, accepted in ((0, False, False, True), (1, False, False, False), (1, True, False, True), (0, False, True, False)):
            w = ready()
            u = w['unit']
            u.carrying = carrying
            if carrying:
                u.towed_unit = Mech.create_test_mech()
                u.towed_unit.measured_mass = u.towed_unit.tonnage * 1024
            if salvage: u.specials |= Specials.SALVAGE_TECH
            if sprint: u.set_status2(S2.SPRINTING)
            with self.subTest(carrying=carrying, salvage=salvage, sprint=sprint):
                result = controls.speed(w['engine'], u, '-1')
                self.assertEqual(accepted, result[0])
                if not accepted: self.assertEqual('You can not backup while towing or sprinting!', result[1])
                self.assertTrue(controls.speed(w['engine'], u, '0')[0])

    def test_motion_exposes_a_concealed_unit_only_above_one_tenth(self):
        for value, hidden in ((.1, True), (-.1, True), (.11, False), (-.11, False)):
            w = ready()
            u = w['unit']
            u.digging = u.dug_in = True
            u.set_crit_status(CritStatus.HIDDEN)
            self.assertTrue(controls.speed(w['engine'], u, str(value))[0])
            self.assertEqual((hidden, hidden, hidden), (u.digging, u.dug_in, u.has_crit_status(CritStatus.HIDDEN)))

    def test_submarine_vertical_and_vtol_takeoff_requirements(self):
        w = ready()
        u = w['unit']
        u.move_type = MoveType.SUB
        set_hex(w, 'WATER', 2)
        u.z = -2
        self.assertEqual((True, 'Vertical speed changed to -1 KPH'), controls.vertical(w['engine'], u, '-1'))
        self.assertEqual(-1, u.vertical_speed)
        u.z = 0
        self.assertEqual((True, 'Vertical speed changed to -1 KPH'), controls.vertical(w['engine'], u, '-1'))
        set_hex(w, 'GRASSLAND')
        # C WaterBeast is HULL/FOIL, so this guard does not reject a SUB.
        # Height maintenance handles grounding separately from the command.
        self.assertEqual((True, 'Vertical speed changed to 1 KPH'), controls.vertical(w['engine'], u, '1'))
        for status in (S.LANDED, S.FALLEN):
            w = ready()
            u = flying(w)
            u.set_status(status)
            self.assertEqual((False, 'You need to take off first or repair your movement system.'), controls.vertical(w['engine'], u, '1'))
        w = ready()
        u = flying(w)
        u.desired_speed = 64.5
        self.assertTrue(controls.vertical(w['engine'], u, '0')[0])

    def test_eta_default_target_validation_and_hour_minute_display(self):
        w = ready()
        u = w['unit']
        u.targ_x, u.targ_y, u.target = 0, 2, -1
        self.assertIn('Range to hex (0,2)', controls.eta(w['engine'], u)[1])
        self.assertIn('Never, mech not moving.', controls.eta(w['engine'], u)[1])
        self.assertIn('Range to hex (0,2)', controls.eta(w['engine'], u, '0.9 2.9')[1])
        for x, target in ((-1, -1), (0, 0)):
            u.targ_x, u.target = x, target
            self.assertEqual((False, 'You have invalid default target for ETA!'), controls.eta(w['engine'], u))
        for args in ('1', '1 2 3'):
            self.assertEqual((False, 'Invalid number of arguments!'), controls.eta(w['engine'], u, args))
        u.speed = 21.5 / 61
        self.assertEqual((True, 'Range to hex (3,5) is 2.0.  ETA: 01:01.'), controls.eta(w['engine'], u, '3 5'))
        u.speed = .1
        self.assertNotIn('Never', controls.eta(w['engine'], u, '3 5')[1])

    def test_land_success_and_failure_use_real_jump_and_fall_events(self):
        for success in (True, False):
            w = ready()
            u = w['unit']
            u.set_status(S.COMBAT_SAFE)
            self.assertTrue(mech_jump(u, 3, 5, w['engine'].events).success)
            u._engine = None
            with psr(w, success) as roll, patch.object(combat, 'roll_1d6', return_value=1):
                result = controls.land(w['engine'], u)
                roll.assert_called_once_with(u, 0)
            self.assertEqual((True, 'You are able to abort the jump.' if success else "You don't quite make it."), result)
            self.assertIs(w['engine'], u._engine)
            self.assertFalse(u.is_jumping)
            if success: self.assertTrue(w['engine'].has_event(EventType.JUMPSTABIL, u))
            else:
                self.assertEqual((1, -1, 0, 0), (u.last_fall_levels, u.dfa_target, u.going_x, u.going_y))
                self.assertTrue(w['engine'].has_event(EventType.MOVE, u))

    def test_control_guards_and_unsupported_land(self):
        w = ready()
        u = w['unit']
        self.assertEqual((False, "You're not jumping!"), controls.land(w['engine'], u))
        u.unit_type = UnitType.AERO
        self.assertEqual((False, 'Aerospace landing requires the unported aero_land service.'), controls.land(w['engine'], u))
        u.set_status(S.DESTROYED)
        for command, args in ((controls.heading, ('90',)), (controls.speed, ('1',)), (controls.vertical, ('1',)), (controls.eta, ('1 2',)), (controls.land, ()), (controls.jump_command, ('1 2',))):
            self.assertEqual((False, 'Unit is destroyed.'), command(w['engine'], u, *args))

    def test_jump_input_refusals_and_pilot_identity(self):
        w = ready()
        u = w['unit']
        self.assertEqual((False, "You're not the pilot!"), controls.jump_command(w['engine'], u, '180 2', Pilot()))
        self.assertEqual((False, 'Too many arguments to JUMP function!'), controls.jump_command(w['engine'], u, '1 2 3'))
        self.assertEqual((False, 'Invalid Target!'), controls.jump_command(w['engine'], u, '99999'))
        u.unit_type = UnitType.VEH_GROUND
        self.assertEqual((False, 'Only mechs can do Death From Above attacks!'), controls.jump_command(w['engine'], u, ''))

    def test_bearing_range_jump_schedules_real_motion_and_truncates_bearing(self):
        from physics import hexmath
        for bearing in ('180', '180.9'):
            w = ready()
            u = w['unit']
            u._engine = None
            with patch.object(hexmath, 'find_components', wraps=hexmath.find_components) as components:
                result = controls.jump_command(w['engine'], u, bearing + ' 2')
            self.assertTrue(result[0], result)
            components.assert_any_call(2 * hexmath.SCALEMAP, 180)
            self.assertEqual((3, 5), (u.going_x, u.going_y))
            self.assertTrue(w['engine'].has_event(EventType.JUMP, u))
            self.assertIs(w['engine'], u._engine)
            self.assertFalse(u.has_status(S.DFA_ATTACK))

    def test_explicit_dfa_resolves_integer_prefix_and_preserves_failed_jump_state(self):
        from systems.los import MECHLOSFLAG_SEESP
        for xy, succeeds in (((3, 5), True), ((10, 10), False)):
            w = ready()
            u = w['unit']
            u._id = 10
            u.dfa_target = -1
            target = Mech.create_test_mech()
            target._id = 20
            target.set_hex_position(*xy)
            w['map'].add_mech(target)
            w['map'].losinfo = {(10, 20): MECHLOSFLAG_SEESP}
            result = controls.jump_command(w['engine'], u, '20.9', u.pilot)
            self.assertEqual(succeeds, result[0], result)
            self.assertEqual(succeeds, u.has_status(S.DFA_ATTACK))
            self.assertEqual(20 if succeeds else -1, u.dfa_target)
        for kind in ('self', 'pilot', 'invisible'):
            w = ready()
            u = w['unit']
            u._id = 10
            target = u if kind == 'self' else Mech.create_test_mech()
            if kind != 'self':
                target._id = 20
                target.set_hex_position(3, 5)
                w['map'].add_mech(target)
            if kind == 'pilot': target.unit_type = UnitType.MW
            expected = 'Target is not in line of sight!' if kind == 'invisible' else 'Invalid Target!'
            self.assertEqual((False, expected), controls.jump_command(w['engine'], u, str(target._id)))

    def test_speed_and_vertical_refusal_feedback(self):
        w = ready()
        u = w['unit']
        u.set_status(S.PERFORMING_ACTION)
        self.assertEqual((False, 'You are too busy at the moment.'), controls.speed(w['engine'], u, '1'))
        u.clear_status(S.PERFORMING_ACTION)
        u.move_type = MoveType.FLY
        self.assertEqual((False, 'Use thrust command instead!'), controls.speed(w['engine'], u, '1'))
        self.assertEqual((False, 'This command is for VTOLs only.'), controls.vertical(w['engine'], u, '1'))
        flying(w)
        u.desired_speed = 65
        self.assertEqual((False, 'Invalid horizontal speed envelope.'), controls.vertical(w['engine'], u, '1'))

    def test_starting_to_move_intentionally_dismounts_a_battlesuit(self):
        from hardening.test_swarm_hardening import mounted
        w, suit = mounted()
        suit.pilot = Pilot()
        suit.set_status(S.STARTED)
        suit.measured_mass = suit.tonnage * 1024
        with patch('systems.piloting.make_piloting_roll') as roll:
            self.assertEqual((True, 'Desired speed changed to 1 KPH.'), controls.speed(w['engine'], suit, '1'))
        roll.assert_not_called()
        self.assertIsNone(suit.swarm_target)
        self.assertEqual([20] * 6 + [0, 0], [s.recycle for s in suit.sections])

    def test_eta_sixty_minute_boundary_and_exact_stationary_feedback(self):
        w = ready()
        u = w['unit']
        self.assertEqual((True, 'Range to hex (3,5) is 2.0.  ETA: Never, mech not moving.'), controls.eta(w['engine'], u, '3 5'))
        u.speed = 21.5 / 60.01
        self.assertEqual((True, 'Range to hex (3,5) is 2.0.  ETA: 01:00.'), controls.eta(w['engine'], u, '3 5'))

    def test_eastward_jump_changes_x_in_the_correct_direction(self):
        w = ready()
        u = w['unit']
        self.assertTrue(controls.jump_command(w['engine'], u, '90 2')[0])
        self.assertEqual((5, 3), (u.going_x, u.going_y))
