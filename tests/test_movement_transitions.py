"""Event cancellation and completion contracts during movement state changes."""
from unittest.mock import patch
from entities.mech import MechStatus as S, MechStatus2 as S2, MoveType, Location
from core.events import EventType
from systems import movement_commands as commands
from physics.jump import mech_falls, mech_jump
from systems.piloting import PilotingResult
from tests.movement_fixture import MovementTestCase


class MovementTransitionTests(MovementTestCase):
    def test_shutdown_at_mode_completion_clears_active_and_pending_modes(self):
        commands.set_mode(self.engine, self.unit, 'sprint')
        self.unit.set_status2(S2.EVADING)
        self.unit.clear_status(S.STARTED)
        self.engine.run_ticks(30)
        self.assertFalse(self.unit.status2 & S2.MOVE_MODES)
        self.assertIsNone(self.unit._mode_event)

    def test_sprint_completion_stops_desired_reverse_without_changing_actual_speed(self):
        self.unit.speed = self.unit.desired_speed = -10
        commands.set_mode(self.engine, self.unit, 'sprint')
        self.engine.run_ticks(30)
        self.assertEqual((-10, 0), (self.unit.speed, self.unit.desired_speed))
        self.assertTrue(self.unit.has_status2(S2.SPRINTING))

    def test_exit_sprint_clamps_desired_speed_after_removing_boost(self):
        self.unit.set_status2(S2.SPRINTING)
        self.unit.speed = self.unit.desired_speed = 86
        commands.set_mode(self.engine, self.unit, 'sprint')
        self.engine.run_ticks(30)
        self.assertEqual((86, 64.5), (self.unit.speed, self.unit.desired_speed))
        self.assertFalse(self.unit.has_status2(S2.SPRINTING))

    def test_falling_replaces_jump_with_stabilization_and_delayed_mode_exit(self):
        self.unit.jump_mp = 4
        self.unit.jump_speed = 4 * 10.75
        self.assertTrue(mech_jump(self.unit, 10, 11, self.engine.events).success)
        self.unit._engine = self.engine
        self.unit.set_status(S.COMBAT_SAFE)
        self.unit.set_status2(S2.EVADING)
        mech_falls(self.unit, 2)
        self.assertFalse(self.engine.has_event(EventType.JUMP, self.unit))
        self.assertTrue(self.engine.has_event(EventType.JUMPSTABIL, self.unit))
        self.assertTrue(self.engine.has_event(EventType.MOVEMODE, self.unit))
        self.engine.run_ticks(12)
        self.assertIsNone(self.unit._stabil_event)
        self.engine.run_ticks(18)
        self.assertFalse(self.unit.has_status2(S2.EVADING))

    def test_failed_careful_stand_requires_full_recovery_before_retry(self):
        self.unit.set_status(S.FALLEN)
        # Fail the stand, but keep the subsequent fall from injuring the pilot:
        # this test observes recovery timing rather than consciousness rolls.
        with patch('systems.piloting.make_piloting_roll', side_effect=[
            PilotingResult(success=False), PilotingResult(success=True),
        ]), patch('systems.combat.get_hit_location', return_value=(Location.CTORSO, False)):
            self.assertFalse(commands.stand(self.engine, self.unit, 'careful')[0])
        self.assertEqual(30, self.engine.event_time_remaining(EventType.STANDFAIL, self.unit))
        self.assertIn('recovering', commands.stand(self.engine, self.unit)[1])
        self.engine.run_ticks(30)
        self.assertIsNone(self.unit._standfail_event)
        self.unit.move_type = MoveType.QUAD
        self.assertTrue(commands.stand(self.engine, self.unit)[0])

    def test_hulldown_shutdown_completion_leaves_posture_unchanged(self):
        self.unit.move_type = MoveType.QUAD
        commands.hulldown(self.engine, self.unit)
        self.unit.clear_status(S.STARTED)
        self.engine.run_ticks(10)
        self.assertFalse(self.unit.has_status(S.HULLDOWN))
        self.assertIsNone(self.unit._hulldown_event)
