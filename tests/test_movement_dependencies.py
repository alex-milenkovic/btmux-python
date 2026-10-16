from unittest.mock import patch
from tests.movement_fixture import MovementTestCase
from entities.mech import Mech, MechStatus as S, MechStatus2 as S2, Location, CritStatus
from entities.map import WATER
from systems import movement_commands as commands
from physics import jump


class MovementDependencyTests(MovementTestCase):

    def test_prone_detaches_swarmers_and_recycles_the_suit(self):
        suit = Mech.create_test_mech()
        suit.swarm_target = self.unit
        suit.set_hex_position(10, 10)
        self.board.add_mech(suit)
        with patch('systems.piloting.make_piloting_roll') as roll:
            roll.return_value.success = True
            commands.prone(self.engine, self.unit)
        self.assertEqual(-1, suit.swarm_target)
        self.assertEqual(30, suit.sections[0].recycle)

    def test_water_extinguishes_inferno_after_prone(self):
        self.board.set_terrain(10, 10, WATER)
        self.board.set_elevation(10, 10, 1)
        self.unit.elev, self.unit.z = 1, -1
        self.unit.set_crit_status(CritStatus.JELLIED)
        commands.prone(self.engine, self.unit)
        self.assertFalse(self.unit.has_crit_status(CritStatus.JELLIED))

    def test_jump_uses_gravity_range_and_rejects_towing(self):
        self.unit.jump_mp = 4
        self.unit.jump_speed = 4 * 10.75
        self.unit.set_status(S.UNDERGRAVITY)
        self.board.grav = 200
        self.assertFalse(jump.mech_jump(self.unit, 10, 13).success)
        self.unit.carrying = 2
        self.assertFalse(jump.mech_jump(self.unit, 10, 11).success)

    def test_gravity_does_not_reduce_persistent_jump_capability(self):
        self.unit.jump_mp = 4
        self.unit.jump_speed = 4 * 10.75
        self.unit.set_status(S.UNDERGRAVITY)
        self.board.grav = 200
        self.assertTrue(jump.mech_jump(self.unit, 10, 11).success)
        self.assertEqual(43, self.unit.jump_speed)

    def test_walk_speed_cannot_substitute_for_missing_jump_jets(self):
        from core.events import EventType
        self.unit.jump_mp = 0
        self.unit.jump_speed = 0 * 10.75
        self.unit.walk_speed = 4
        self.assertFalse(jump.mech_jump(self.unit, 10, 11, self.engine.events).success)
        self.assertFalse(self.engine.has_event(EventType.JUMP, self.unit))

    def test_cargo_speed_loss_blocks_jump_before_scheduling(self):
        from core.events import EventType
        self.unit.jump_mp = 4
        self.unit.jump_speed = 4 * 10.75
        self.unit.carried_cargo = 50 * 1024
        self.assertFalse(jump.mech_jump(self.unit, 10, 11, self.engine.events).success)
        self.assertFalse(self.engine.has_event(EventType.JUMP, self.unit))

    def test_running_guard_uses_c_point_one_tolerance(self):
        self.unit.dumping = True
        self.assertTrue(commands.speed(self.engine, self.unit, '43.1')[0])
        self.assertFalse(commands.speed(self.engine, self.unit, '43.11')[0])

    def test_any_nonzero_sprint_speed_generates_mode_heat(self):
        from systems.heat import calculate_movement_heat
        self.unit.set_status2(S2.SPRINTING)
        self.unit.speed = .01
        self.assertEqual(3, calculate_movement_heat(self.unit))
        self.unit.speed = 0
        self.assertEqual(0, calculate_movement_heat(self.unit))

    def test_pending_ground_move_does_not_advance_jump_twice(self):
        import math
        from physics.movement import MOVE_MOD
        self.unit.jump_mp = 4
        self.unit.jump_speed = 4 * 10.75
        commands.speed(self.engine, self.unit, 'walk')
        start = self.unit.fx, self.unit.fy
        self.assertTrue(jump.mech_jump(self.unit, 10, 11, self.engine.events).success)
        self.engine.run_ticks(1)
        self.assertAlmostEqual(43 * MOVE_MOD, math.hypot(self.unit.fx-start[0], self.unit.fy-start[1]))

    def test_damage_entry_interrupts_sprint_for_internal_damage(self):
        from systems.combat import apply_damage_with_transfer
        self.unit._engine = self.engine
        self.unit.set_status2(S2.SPRINTING)
        apply_damage_with_transfer(self.unit, Location.CTORSO, 1, attacker=self.unit, internal=True)
        self.assertFalse(self.unit.has_status2(S2.SPRINTING))

    def test_vertical_motion_runs_without_horizontal_motion(self):
        from entities.mech import UnitType, MoveType
        self.unit.unit_type = UnitType.VTOL
        self.unit.move_type = MoveType.VTOL
        self.unit.fuel = 100
        self.unit.z = 2
        self.unit.fz = 2 * 64.5
        self.assertTrue(commands.vertical(self.engine, self.unit, '43')[0])
        self.engine.run_ticks(3)
        self.assertEqual(3, self.unit.z)
        self.assertAlmostEqual(193.5, self.unit.fz)

    def test_odd_jump_uses_quartic_height_and_interpolated_floor(self):
        self.assertEqual(75, jump.calculate_odd_jump_altitude(25, 100, 10, 30, 64, 4))

    def test_sprint_uses_default_server_bth_and_allows_configuration(self):
        self.unit.set_status2(S2.SPRINTING)
        self.assertEqual(-4, commands.target_mode_bth(self.unit))
        self.unit.btech_sprint_bth = -2
        self.assertEqual(-2, commands.target_mode_bth(self.unit))

    def test_default_dfa_target_is_checked_through_real_los(self):
        target = Mech.create_test_mech()
        target._id = self.unit._id + 1
        target.set_hex_position(10, 11)
        self.board.add_mech(target)
        self.engine.register_entity(target)
        self.unit.target = target._id
        self.unit.jump_mp = 4
        self.unit.jump_speed = 4 * 10.75
        self.assertFalse(commands.jump_command(self.engine, self.unit, '')[0])
        from systems.los import MECHLOSFLAG_SEESP
        self.board.losinfo = {(self.unit._id, target._id): MECHLOSFLAG_SEESP}
        self.assertTrue(commands.jump_command(self.engine, self.unit, '')[0])
        self.assertTrue(self.unit.has_status(S.DFA_ATTACK))
        self.assertEqual(target._id, self.unit.dfa_target)

    def test_physical_attack_is_blocked_during_stand_completion(self):
        from systems.physical import phys_common_checks
        self.unit.set_status(S.FALLEN)
        with patch('systems.piloting.make_piloting_roll') as roll:
            roll.return_value.success = True
            commands.stand(self.engine, self.unit)
        self.assertFalse(self.unit.is_fallen)
        self.assertEqual((False, 'You are still trying to stand up!'), phys_common_checks(self.unit))
