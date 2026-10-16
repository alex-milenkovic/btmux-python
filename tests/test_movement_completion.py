"""C movement behavior through commands and the real event queue."""
from tests.movement_fixture import MovementTestCase
from unittest.mock import patch
from entities.mech import Mech, MechStatus as S, MechStatus2 as S2, MoveType, UnitType, Location, Specials
from entities.pilot import Pilot
from core.events import EventType
from systems import movement_commands as commands
from physics.cargo import cargo_max_speed
from physics.jump import mech_falls


class MovementCompletionTests(MovementTestCase):
    def test_eta_arity_uses_source_refusal_and_capped_parser(self):
        self.assertEqual((False, 'Invalid number of arguments!'), commands.eta(self.engine, self.unit, '3'))
        self.unit.target = -1
        self.unit.targ_x, self.unit.targ_y = 3, 4
        expected = commands.eta(self.engine, self.unit, '3 4')
        self.assertTrue(expected[0])
        self.assertEqual(expected, commands.eta(self.engine, self.unit))
        self.assertEqual(expected, commands.eta(self.engine, self.unit, '3 4 ignored'))



    def test_mode_completes_at_delay_and_rejects_a_second_request(self):
        self.assertTrue(commands.set_mode(self.engine, self.unit, 'sprint')[0])
        self.assertFalse(commands.set_mode(self.engine, self.unit, 'evade')[0])
        self.engine.run_ticks(29)
        self.assertFalse(self.unit.has_status2(S2.SPRINTING))
        self.engine.run_ticks(1)
        self.assertTrue(self.unit.has_status2(S2.SPRINTING))
        self.assertAlmostEqual(86, cargo_max_speed(self.unit))

    def test_dodge_permits_weapon_recycle_but_rechecks_limbs(self):
        self.unit.pilot.dodge_maneuver = True
        self.assertTrue(commands.set_mode(self.engine, self.unit, 'dodge')[0])
        self.unit.sections[Location.LARM].recycle = 3
        self.engine.run_ticks(1)
        self.assertFalse(self.unit.has_status2(S2.DODGING))

    def test_hulldown_uses_signed_speed_and_can_cancel(self):
        self.unit.move_type = MoveType.QUAD
        self.unit.speed = -1
        self.assertTrue(commands.hulldown(self.engine, self.unit)[0])
        self.assertFalse(commands.heading(self.engine, self.unit, '90')[0])
        self.engine.run_ticks(9)
        self.assertFalse(self.unit.has_status(S.HULLDOWN))
        self.engine.run_ticks(1)
        self.assertTrue(self.unit.has_status(S.HULLDOWN))
        self.assertTrue(commands.hulldown(self.engine, self.unit, '-')[0])
        self.assertTrue(commands.hulldown(self.engine, self.unit, 'stop')[0])
        self.engine.run_ticks(10)
        self.assertTrue(self.unit.has_status(S.HULLDOWN))

    def test_speed_changes_desired_only_and_normalizes_heading(self):
        self.assertTrue(commands.speed(self.engine, self.unit, 'back')[0])
        self.assertEqual((-43, 0), (self.unit.desired_speed, self.unit.speed))
        self.assertTrue(self.engine.has_event(EventType.MOVE, self.unit))
        self.assertTrue(commands.heading(self.engine, self.unit, '-1')[0])
        self.assertEqual(359, self.unit.desired_facing)
        self.assertTrue(commands.speed(self.engine, self.unit, 'garbage')[0])
        self.assertEqual(0, self.unit.desired_speed)

    def test_cargo_mass_and_boosts_do_not_compound(self):
        self.unit.measured_mass = 50 * 1024
        self.unit.carried_cargo = 10 * 1024
        self.assertAlmostEqual(46.07143020629883, cargo_max_speed(self.unit))
        self.unit.set_status(S.MASC_ENABLED | S.SCHARGE_ENABLED)
        self.unit.set_status2(S2.SPRINTING)
        self.assertAlmostEqual(92.14286041259766, cargo_max_speed(self.unit))
        self.assertAlmostEqual(92.14286041259766, cargo_max_speed(self.unit))
        self.unit.carried_cargo = 0
        self.assertAlmostEqual(129, cargo_max_speed(self.unit))

    def test_fall_damage_and_facing_follow_c_and_zero_is_zero(self):
        with patch('systems.combat.roll_1d6', return_value=3), patch('systems.piloting.make_piloting_roll') as roll:
            roll.return_value.success = True
            result = mech_falls(self.unit, 2)
        self.assertEqual((11, 120, 120), (result.damage_taken, self.unit.facing, self.unit.desired_facing))
        self.unit.set_status(S.COMBAT_SAFE)
        self.assertEqual(0, mech_falls(self.unit, 4).damage_taken)
        self.unit.clear_status(S.COMBAT_SAFE)
        self.assertEqual(0, mech_falls(self.unit, 0).damage_taken)

    def test_bootlegger_uses_speed_and_weight_bands(self):
        self.unit.tonnage = 75
        self.unit.speed = 12 * 10.75
        self.unit.facing = 270
        with patch('systems.piloting.make_piloting_roll') as roll:
            roll.return_value.success = True
            self.assertTrue(commands.bootlegger(self.engine, self.unit, 'R')[0])
            roll.assert_called_once_with(self.unit, 4)
        self.assertEqual((0, 0, 6 * 10.75), (self.unit.facing, self.unit.desired_facing, self.unit.speed))
        self.assertEqual(30, self.unit.sections[Location.LLEG].recycle)

    def test_controlled_drop_damages_only_when_fast_roll_fails(self):
        self.unit.speed = 43.1
        with patch('systems.piloting.make_piloting_roll') as roll:
            roll.return_value.success = False
            commands.prone(self.engine, self.unit)
        self.assertEqual(2, self.unit.last_fall_levels)
        self.assertTrue(self.unit.is_fallen)
        self.assertEqual((0, 0), (self.unit.speed, self.unit.desired_speed))

    def test_quad_stands_without_a_roll_and_cannot_move_during_delay(self):
        from physics.jump import stand_up
        self.unit.move_type = MoveType.QUAD
        self.unit.set_status(S.FALLEN)
        with patch('systems.piloting.make_piloting_roll') as roll:
            self.assertTrue(stand_up(self.unit, self.engine.events)[0])
            roll.assert_not_called()
        self.assertFalse(self.unit.is_fallen)
        self.assertFalse(commands.speed(self.engine, self.unit, 'walk')[0])
        self.engine.run_ticks(10)
        self.assertTrue(commands.speed(self.engine, self.unit, 'walk')[0])

    def test_damage_preserves_pending_entry_and_breaks_active_sprint(self):
        from systems.combat import apply_damage_with_transfer
        for restored in (False, True):
            with self.subTest(restored_integer=restored):
                self.setUp()
                commands.set_mode(self.engine, self.unit, 'sprint')
                entry = self.unit._mode_event
                if restored:
                    entry.data2 = 6  # MODE_ON | MODE_SPRINT
                    self.unit._mode_event = None
                apply_damage_with_transfer(self.unit, Location.CTORSO, 1)
                self.assertFalse(entry.zombie)
                self.engine.run_ticks(29)
                self.assertFalse(self.unit.has_status2(S2.SPRINTING))
                self.engine.run_ticks(1)
                self.assertTrue(self.unit.has_status2(S2.SPRINTING))
                apply_damage_with_transfer(self.unit, Location.CTORSO, 1)
                self.assertFalse(self.unit.has_status2(S2.SPRINTING))
                self.assertTrue(self.engine.has_event(EventType.MOVEMODE, self.unit))
                exit_event = self.unit._mode_event
                apply_damage_with_transfer(self.unit, Location.CTORSO, 1)
                self.assertIs(exit_event, self.unit._mode_event)

    def test_live_modes_feed_heat_and_targeting(self):
        from systems.heat import calculate_movement_heat
        from systems.combat import calculate_target_movement_modifier
        self.unit.speed = 10.75
        base = calculate_target_movement_modifier(self.unit, 3)
        self.unit.set_status2(S2.EVADING)
        self.assertEqual(3, calculate_movement_heat(self.unit))
        self.assertEqual(base, calculate_target_movement_modifier(self.unit, 3))
        self.assertEqual(1, commands.target_mode_bth(self.unit))

    def test_command_rejection_does_not_schedule_and_checks_caller(self):
        for condition in ('shutdown', 'blind', 'map', 'caller'):
            with self.subTest(condition=condition):
                self.setUp()
                before = self.engine.events.pending_count
                caller = self.unit.pilot
                if condition == 'shutdown':
                    self.unit.clear_status(S.STARTED)
                elif condition == 'blind':
                    self.unit.set_status(S.BLINDED)
                elif condition == 'map':
                    self.unit.map = None
                    self.unit.mapindex = -1
                else:
                    caller = Pilot()
                    self.unit.in_character = True
                self.assertFalse(commands.set_mode(self.engine, self.unit, 'sprint', caller)[0])
                self.assertEqual(before, self.engine.events.pending_count)

    def test_cargo_three_times_mass_boundary_and_tow_halvings(self):
        self.unit.measured_mass = 50 * 1024
        self.unit.carried_cargo = 50 * 1024
        self.assertAlmostEqual(21.5, cargo_max_speed(self.unit))
        self.unit.carried_cargo += 1
        self.assertEqual(0, cargo_max_speed(self.unit))
        self.unit.carried_cargo = 0
        tow = Mech()
        tow.measured_mass = 40 * 1024
        self.unit.towed_unit = tow
        self.unit.specials |= Specials.SALVAGE_TECH
        self.unit.specials2 |= 0x80000
        self.assertAlmostEqual(46.07143020629883, cargo_max_speed(self.unit))

    def test_negative_cocoon_excluded_from_stacking(self):
        from physics.collision import mechs_in_hex
        self.unit.cocoon = -1
        self.assertEqual(0, mechs_in_hex(self.board, 10, 10, -1, 0))
