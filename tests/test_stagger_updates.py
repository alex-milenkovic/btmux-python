"""Timed stagger list and actual heartbeat/turn integration."""

from unittest.mock import patch
from types import SimpleNamespace
from tests.movement_fixture import MovementTestCase
from entities.mech import CritStatus, Location, MechStatus
from core.game_loop import mech_heartbeat
from systems import stagger


class StaggerUpdates(MovementTestCase):
    def test_failed_heartbeat_and_queued_stagger_falls_are_quiet(self):
        from core.events import EventType
        from core.randomness import use_source
        from physics.jump import mech_falls
        for queued in (False, True):
            with self.subTest(queued_legacy=queued):
                self.setUp()
                if queued:
                    self.engine.new_stagger = 0
                    self.unit.stagger_damage = 20
                    self.engine.schedule_event(1, EventType.CHECK_STAGGER, stagger.check_stagger_event, data=self.unit)
                else:
                    stagger.record_damage(self.unit, 20, self.engine)
                    self.engine.sim_now = 5
                with use_source(lambda name, low, high, fallback: high), patch('systems.stagger.make_piloting_roll', return_value=SimpleNamespace(success=False)), patch('physics.jump.mech_falls', wraps=mech_falls) as fall, patch('systems.sensors.los_broadcast') as los:
                    if queued:
                        self.engine.run_ticks(1)
                    else:
                        mech_heartbeat(self.engine, self.unit)
                self.assertTrue(self.unit.is_fallen)
                fall.assert_called_once_with(self.unit, 1, notify_fall=False)
                messages = [call.args[1] for call in los.call_args_list]
                self.assertEqual(1, messages.count('tumbles over, staggered by the damage!'))
                self.assertNotIn('falls down!', messages)


    def test_failed_stopped_stability_roll_falls_without_gravity_damage(self):
        from systems.stability import update_pilot_skill_rolls

        self.unit.clear_status(MechStatus.STARTED)
        self.engine.events.set_tick(29)
        with patch(
            "systems.stability.make_piloting_roll",
            return_value=SimpleNamespace(success=False),
        ) as roll, patch("physics.jump.mech_falls") as fall, patch(
            "systems.criticals.apply_internal_damage_with_transfer"
        ) as damage:
            update_pilot_skill_rolls(self.engine, self.unit)
        roll.assert_called_once_with(self.unit, 3)
        fall.assert_called_once_with(self.unit, 1, notify_fall=False)
        damage.assert_not_called()

    def test_gravity_overspeed_takes_priority_over_stopped_modifier(self):
        from systems.stability import update_pilot_skill_rolls

        self.unit.clear_status(MechStatus.STARTED)
        self.unit.set_status(MechStatus.UNDERSPECIAL | MechStatus.UNDERGRAVITY)
        self.unit.speed = self.unit.max_speed + 10.75
        self.engine.events.set_tick(30)
        with patch(
            "systems.stability.make_piloting_roll",
            return_value=SimpleNamespace(success=True),
        ) as roll:
            update_pilot_skill_rolls(self.engine, self.unit)
        roll.assert_called_once_with(self.unit, 0)

    def test_fallen_heartbeat_prunes_without_counting_new_damage(self):
        stagger.record_damage(self.unit, 25, self.engine)
        self.unit.set_status(MechStatus.FALLEN)
        self.engine.sim_now = 60
        with patch("systems.stagger.make_piloting_roll") as roll:
            mech_heartbeat(self.engine, self.unit)
        roll.assert_not_called()
        self.assertEqual(self.unit.stagger_damage_list, [])
        self.assertEqual(self.unit.last_stagger_check, 0)

    def test_legacy_damage_checks_once_until_same_tick_next_turn(self):
        self.engine.new_stagger = 0
        self.engine.events.set_tick(4)
        stagger.record_damage(self.unit, 20, self.engine)
        with patch(
            "systems.stagger.make_piloting_roll",
            return_value=SimpleNamespace(success=True),
        ) as roll:
            stagger.check_damage(self.engine, self.unit)
            self.assertEqual(self.unit.stagger_stamp, 4)
            self.assertEqual(self.unit.turn_damage, 0)
            self.engine.events.set_tick(6)
            stagger.record_damage(self.unit, 20, self.engine)
            stagger.check_damage(self.engine, self.unit)
            self.assertEqual(roll.call_count, 1)
            self.assertEqual(self.unit.turn_damage, 20)
            self.engine.events.set_tick(34)
            stagger.check_damage(self.engine, self.unit)
            self.assertEqual(roll.call_count, 2)
            self.assertEqual(self.unit.turn_damage, 0)

    def test_inclusive_sum_then_exclusive_expiry(self):
        self.unit.stagger_damage_list = [
            dict(amount=12, occurred_at=0, counted=False),
            dict(amount=9, occurred_at=0, counted=True),
        ]
        self.assertEqual(stagger.current_damage(self.unit, 60), 12)
        self.assertEqual(stagger.current_damage(self.unit, 60, counted=True), 9)
        stagger.clear_expired(self.unit, 60)
        self.assertEqual(self.unit.stagger_damage_list, [])

    def test_mark_and_remove_keep_whole_hits(self):
        self.unit.stagger_damage_list = [
            dict(amount=n, counted=c, occurred_at=0)
            for n, c in [(12, False), (9, True), (15, False), (8, False)]
        ]
        stagger.mark_damage(self.unit, 1)
        self.assertEqual(stagger.current_damage(self.unit, 0), 8)
        self.assertEqual(stagger.current_damage(self.unit, 0, True), 36)
        stagger.remove_damage(self.unit, 1)
        self.assertEqual([n["amount"] for n in self.unit.stagger_damage_list], [15, 8])

    def test_damage_uses_wall_time_at_insertion_and_one_node_for_transfer(self):
        from systems.combat import apply_damage_with_transfer

        self.engine.sim_now = 100
        self.engine.events.set_tick(3)
        apply_damage_with_transfer(self.unit, Location.LARM, 20, engine=self.engine)
        self.assertEqual(len(self.unit.stagger_damage_list), 1)
        self.assertEqual(self.unit.stagger_damage_list[0]["occurred_at"], 100)

    def test_heartbeat_counts_only_new_damage(self):
        stagger.record_damage(self.unit, 20, self.engine)
        with patch(
            "systems.stagger.make_piloting_roll",
            return_value=SimpleNamespace(success=True),
        ) as roll:
            self.engine.sim_now = 4
            mech_heartbeat(self.engine, self.unit)
            roll.assert_not_called()
            self.engine.sim_now = 5
            mech_heartbeat(self.engine, self.unit)
            roll.assert_called_once_with(self.unit, 0)
            self.engine.sim_now = 10
            mech_heartbeat(self.engine, self.unit)
            self.assertEqual(roll.call_count, 1)
            stagger.record_damage(self.unit, 20, self.engine)
            self.engine.sim_now = 15
            mech_heartbeat(self.engine, self.unit)
            roll.assert_called_with(self.unit, 1)

    def test_mode_two_consumes_history(self):
        self.engine.new_stagger = 2
        stagger.record_damage(self.unit, 20, self.engine)
        self.engine.sim_now = 5
        with patch(
            "systems.stagger.make_piloting_roll",
            return_value=SimpleNamespace(success=True),
        ):
            mech_heartbeat(self.engine, self.unit)
        self.assertEqual(self.unit.stagger_damage_list, [])

    def test_odd_tick_fixup_and_gravity_injure_real_legs(self):
        from systems.stability import update_pilot_skill_rolls

        u = self.unit
        u.set_status(MechStatus.UNDERSPECIAL | MechStatus.UNDERGRAVITY)
        self.board.grav = 150
        u.speed = 75.25
        before = [u.sections[loc].internal for loc in (Location.LLEG, Location.RLEG)]
        self.engine.events.set_tick(29)
        with patch(
            "systems.stability.make_piloting_roll",
            return_value=SimpleNamespace(success=False),
        ), patch("systems.combat.roll_2d6", return_value=2):
            # Exercise real internal damage without an unrelated random limb critical.
            update_pilot_skill_rolls(self.engine, u)
        self.assertEqual(
            [u.sections[loc].internal for loc in (Location.LLEG, Location.RLEG)],
            [n - 2 for n in before],
        )
        self.assertFalse(u.is_fallen)
