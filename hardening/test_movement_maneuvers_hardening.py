"""Maneuver refusal, C modifier bands and local thrash damage/event context."""
import unittest
from unittest.mock import patch
from acceptance.movement.context import fresh, psr, set_hex
from entities.mech import Mech, MechStatus as S, UnitType, SectionConfig, Location as L
from entities.pilot import Pilot
from systems import movement_commands as maneuvers
from systems import combat


def ready():
    w = {}
    fresh(w)
    return w


class TestMovementManeuversHardening(unittest.TestCase):
    def test_pilot_and_destroyed_guards(self):
        for command, args in ((maneuvers.bootlegger, ('right',)), (maneuvers.thrash, ())):
            w = ready()
            u = w['unit']
            self.assertEqual((False, "You're not the pilot!"), command(w['engine'], u, *args, caller=Pilot()))
            u.set_status(S.DESTROYED)
            self.assertEqual((False, 'Unit is destroyed.'), command(w['engine'], u, *args))

    def test_bootlegger_refusals_preserve_feedback(self):
        for condition, message in (('leg', "You can't perform a bootlegger with destroyed legs!"), ('slow', 'You are going too slow to perform a bootlegger!'), ('direction', 'Invalid turn direction!'), ('busy', 'You have weapons or legs recycling!')):
            w = ready()
            u = w['unit']
            u.speed = 43
            if condition == 'leg': u.sections[L.LLEG].config |= SectionConfig.SECTION_DESTROYED
            if condition == 'slow': u.speed = 42
            if condition == 'busy': u.sections[L.RLEG].recycle = 1
            self.assertEqual((False, message), maneuvers.bootlegger(w['engine'], u, 'X' if condition == 'direction' else 'right'))

    def test_bootlegger_modifier_bands_include_leg_damage_and_water(self):
        for speed, tons, leg_penalty, water, modifier in ((43, 35, 0, False, 1), (44, 36, 0, False, 2), (87, 56, 0, False, 4), (130, 76, 0, False, 6), (43, 35, 3, False, 3), (43, 35, 0, True, 2)):
            w = ready()
            u = w['unit']
            u.speed, u.tonnage = speed, tons
            u.sections[L.LLEG].basetohit = leg_penalty
            u.facing = 350
            u._engine = None
            # An arm recycling does not block the participating biped legs.
            u.sections[L.LARM].recycle = 1
            if water:
                set_hex(w, 'WATER', 2)
                u.z = -2
            with self.subTest(speed=speed, tons=tons, water=water), psr(w) as roll:
                self.assertEqual((True, 'You plant a foot and swivel, changing your heading to 80.'), maneuvers.bootlegger(w['engine'], u, 'right'))
                roll.assert_called_once_with(u, modifier)
                self.assertEqual(modifier, u.last_piloting_modifier)
                self.assertEqual((80, 80, speed / 2), (u.facing, u.desired_facing, u.speed))
                self.assertEqual((30, 30, 1), (u.sections[L.LLEG].recycle, u.sections[L.RLEG].recycle, u.sections[L.LARM].recycle))
                self.assertIs(w['engine'], u._engine)

    def test_failed_bootlegger_falls_by_its_modifier(self):
        w = ready()
        u = w['unit']
        u.speed, u.tonnage = 130, 76
        u.set_status(S.COMBAT_SAFE)
        with psr(w, False), patch.object(combat, 'roll_1d6', return_value=1):
            self.assertEqual((True, 'You plant a foot and try to swivel... but fall!'), maneuvers.bootlegger(w['engine'], u, 'left'))
        self.assertEqual(6, u.last_fall_levels)
        self.assertTrue(u.is_fallen)
        self.assertIn('You plant a foot and try to swivel... but fall!', u.movement_messages)

    def test_thrash_refusals_and_destroyed_limb_exclusion(self):
        for condition, message in (('upright', 'You need to be prone to thrash!'), ('woods', 'Thrashing only works in clear terrain or on roads or bridges.'), ('no_limbs', 'You need intact limbs without recycling!'), ('busy', 'You need intact limbs without recycling!')):
            w = ready()
            u = w['unit']
            if condition != 'upright': u.set_status(S.FALLEN)
            if condition == 'woods': set_hex(w, 'LIGHT_FOREST')
            if condition == 'no_limbs':
                for loc in (L.RARM, L.LARM, L.LLEG, L.RLEG): u.sections[loc].config |= SectionConfig.SECTION_DESTROYED
            if condition == 'busy': u.sections[L.RARM].recycle = 1
            self.assertEqual((False, message), maneuvers.thrash(w['engine'], u))
        w = ready()
        u = w['unit']
        u.set_status(S.FALLEN)
        u.sections[L.HEAD].recycle = 1
        u.sections[L.LARM].config |= SectionConfig.SECTION_DESTROYED
        with psr(w):
            self.assertTrue(maneuvers.thrash(w['engine'], u)[0])
        self.assertEqual(0, u.sections[L.LARM].recycle)
        self.assertEqual((60, 60, 60), (u.sections[L.RARM].recycle, u.sections[L.LLEG].recycle, u.sections[L.RLEG].recycle))

    def test_thrash_skips_distant_target_then_hits_near_target_in_five_point_clusters(self):
        w = ready()
        u = w['unit']
        u.set_status(S.FALLEN)
        u.tonnage, u.team = 50, 1
        u._engine = None
        for i, xy in enumerate(((10, 10), (3, 3))):
            suit = Mech.create_test_mech()
            suit._id, suit.unit_type, suit.team = 10 + i, UnitType.BSUIT, 2
            suit.set_hex_position(*xy)
            w['map'].add_mech(suit)
        before = suit.sections[L.CTORSO].armor
        with psr(w) as roll, patch('random.randint', return_value=int(L.CTORSO)) as draw, patch.object(combat, 'apply_damage_with_transfer', wraps=combat.apply_damage_with_transfer) as applied:
            self.assertEqual((True, 'You start to flail your arms and legs like a wild man!'), maneuvers.thrash(w['engine'], u))
        self.assertEqual([5, 5, 5, 1], [call.args[2] for call in applied.call_args_list])
        for call in applied.call_args_list:
            self.assertEqual((suit, int(L.CTORSO)), call.args[:2])
            self.assertEqual({'attacker': u, 'engine': w['engine']}, call.kwargs)
        self.assertEqual(before - 16, suit.sections[L.CTORSO].armor)
        for call in draw.call_args_list: self.assertEqual((0, 5), call.args)
        roll.assert_called_once_with(u, 0)
        self.assertIs(w['engine'], u._engine)
        self.assertIn('You start to flail your arms and legs like a wild man!', u.movement_messages)

    def test_failed_thrash_piloting_uses_one_level_fall(self):
        w = ready()
        u = w['unit']
        u.set_status(S.FALLEN | S.COMBAT_SAFE)
        with psr(w, False) as roll, patch.object(combat, 'roll_1d6', return_value=1):
            self.assertTrue(maneuvers.thrash(w['engine'], u)[0])
        roll.assert_called_once_with(u, 0)
        self.assertEqual(1, u.last_fall_levels)
