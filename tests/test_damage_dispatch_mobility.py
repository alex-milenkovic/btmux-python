"""Critical selection guards, continued dispatch, and derived limb state."""
import unittest
from core.randomness import use_source
from core.game_loop import GameEngine
from entities.mech import Mech, Location as L, FireMode as F, MechStatus as S, Specials, UnitType, MoveType, CritStatus
from entities.crittypes import i2special, Special
from systems.criticals import check_and_apply_criticals, recalculate_mech_stats
from tests.test_damage_failures import Draws


class DispatchMobilityTest(unittest.TestCase):
    def setUp(self):
        self.u = Mech.create_test_mech()
        self.e = GameEngine()
        self.e.register_entity(self.u)
        for section in self.u.sections:
            for slot in section.criticals:
                slot.type = 0

    def test_safety_and_critproof_return_before_slot_selection(self):
        self.u.sections[L.CTORSO].criticals[0].type = i2special(Special.LIFE_SUPPORT)
        for flag, field in ((S.COMBAT_SAFE, 'status'), (Specials.CRITPROOF_TECH, 'specials')):
            setattr(self.u, field, flag)
            with use_source(Draws()):
                self.assertEqual([], check_and_apply_criticals(self.u, L.CTORSO, 1))
            setattr(self.u, field, 0)

    def test_death_does_not_stop_requested_slot_criticals(self):
        for i, kind in enumerate((Special.COCKPIT, Special.LIFE_SUPPORT)):
            self.u.sections[L.HEAD].criticals[i].type = i2special(kind)
        with use_source(Draws(0, 0)):
            results = check_and_apply_criticals(self.u, L.HEAD, 2)
        self.assertEqual(2, len(results))
        self.assertTrue(self.u.sections[L.HEAD].criticals[1].firemode & F.DESTROYED_MODE)

    def test_hand_no_bth_and_shoulder_overrides_other_arm_actuators(self):
        from systems.criticals import normalize_location_actuators
        arm = self.u.sections[L.LARM]
        for i, kind in enumerate((Special.HAND_OR_FOOT_ACTUATOR, Special.UPPER_ACTUATOR, Special.SHOULDER_OR_HIP)):
            arm.criticals[i].type = i2special(kind)
        arm.criticals[0].firemode = F.DESTROYED_MODE
        normalize_location_actuators(self.u, L.LARM)
        self.assertEqual(0, arm.basetohit)
        arm.criticals[1].firemode = F.DESTROYED_MODE
        normalize_location_actuators(self.u, L.LARM)
        self.assertEqual(1, arm.basetohit)
        arm.criticals[2].firemode = F.DESTROYED_MODE
        normalize_location_actuators(self.u, L.LARM)
        self.assertEqual(4, arm.basetohit)

    def test_global_rebuild_is_repeatable_preserves_sensor_bth_and_quad_loss_table(self):
        self.u.move_type = MoveType.QUAD
        self.u.template_max_speed = 64.5
        self.u.base_to_hit = 75
        for loc in (L.LARM, L.RARM):
            self.u.sections[loc].armor = self.u.sections[loc].internal = 0
        for _ in range(2):
            recalculate_mech_stats(self.u)
            self.assertEqual((10.75, 7, 75), (self.u.max_speed, self.u.pilot_skill_base, self.u.base_to_hit))

    def test_hardened_gyro_absorbs_first_hit_then_really_falls_on_third(self):
        from systems.criticals import apply_critical_to_slot
        from unittest.mock import patch
        self.u.specials2 |= 0x400000
        for i in range(3): self.u.sections[L.CTORSO].criticals[i].type = i2special(Special.GYRO)
        with patch('systems.piloting.make_piloting_roll') as psr:
            psr.return_value.success = True
            apply_critical_to_slot(self.u, L.CTORSO, 0, self.u)
            self.assertTrue(self.u.crit_status2 & 1)
            self.assertFalse(self.u.crit_status & CritStatus.GYRO_DAMAGED)
            apply_critical_to_slot(self.u, L.CTORSO, 1, self.u)
            self.assertFalse(self.u.is_fallen)
            apply_critical_to_slot(self.u, L.CTORSO, 2, self.u)
            self.assertTrue(self.u.is_fallen)
