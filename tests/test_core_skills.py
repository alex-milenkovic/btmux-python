"""Source skill names, parsed machine overrides, pilot eligibility and XP."""
from types import SimpleNamespace
import unittest
from core.randomness import use_source
from entities.mech import MechStatus as S, MoveType as M, UnitType as U, CritStatus as C
from entities.weapon import get_weapon, WeaponType
from entities.pilot import Pilot
from tests.test_core_startup import fixture
from systems import piloting as p


class SkillSelectionTest(unittest.TestCase):
    def test_default_broad_names_across_unit_classes_and_weapon_families(self):
        engine, unit, _ = fixture()
        self.assertIs(engine.extended_gunnery, False)
        self.assertIs(engine.extended_piloting, False)
        cases = ((U.MECH, M.BIPED, 'Gunnery-Battlemech', 'Piloting-Battlemech'),
                 (U.MECH, M.QUAD, 'Gunnery-Battlemech', 'Piloting-Battlemech'),
                 (U.VEH_GROUND, M.TRACK, 'Gunnery-Conventional', 'Drive'),
                 (U.VEH_GROUND, M.WHEEL, 'Gunnery-Conventional', 'Drive'),
                 (U.VEH_GROUND, M.HOVER, 'Gunnery-Conventional', 'Drive'),
                 (U.VEH_NAVAL, M.HULL, 'Gunnery-Conventional', 'Drive'),
                 (U.AERO, M.FLY, 'Gunnery-Aerospace', 'Piloting-Aerospace'),
                 (U.VTOL, M.VTOL, 'Gunnery-Aerospace', 'Piloting-Aerospace'),
                 (U.DS, M.FLY, 'Gunnery-Spacecraft', 'Piloting-Spacecraft'),
                 (U.SPHEROID_DS, M.FLY, 'Gunnery-Spacecraft', 'Piloting-Spacecraft'),
                 (U.BSUIT, M.BIPED, 'Gunnery-BSuit', 'Piloting-BSuit'))
        for kind, movement, gun, pilot in cases:
            unit.unit_type, unit.move_type = kind, movement
            for weapon in ('IS.MediumLaser', 'IS.AC/10', 'IS.SRM-6', 'IS.Flamer'):
                with self.subTest(kind=kind, movement=movement, weapon=weapon):
                    self.assertEqual(gun, p.find_gunnery_skill_name(unit, get_weapon(weapon)))
                    self.assertEqual(pilot, p.find_piloting_skill_name(unit))
        unit.unit_type, unit.terrain = U.MW, '~'
        self.assertEqual('Running', p.find_piloting_skill_name(unit))
        self.assertEqual('Blade', p.find_gunnery_skill_name(unit, SimpleNamespace(name='PC.Sword')))
        self.assertEqual('Small_Arms', p.find_gunnery_skill_name(unit, SimpleNamespace(name='PC.HeavyGyrojetGun')))

    def test_missing_engine_settings_and_detached_unit_use_broad_skills(self):
        engine, unit, _ = fixture()
        del engine.extended_gunnery, engine.extended_piloting
        for owner in (engine, None):
            unit._engine = owner
            self.assertEqual('Gunnery-Battlemech', p.find_gunnery_skill_name(unit))
            self.assertEqual('Piloting-Battlemech', p.find_piloting_skill_name(unit))

    def test_independent_modes_select_targets_and_preserve_scalar_and_overrides(self):
        from systems.combat import calculate_bth
        for config, gun, pilot in (({}, 3, 4),
                ({'extended_gunnery': False, 'extended_piloting': False}, 3, 4),
                ({'extended_gunnery': True, 'extended_piloting': True}, 8, 9),
                ({'extended_gunnery': True}, 8, 4),
                ({'extended_piloting': True}, 3, 9),
                ({'extended_gunnery': True, 'extended_piloting': False}, 8, 4),
                ({'extended_gunnery': False, 'extended_piloting': True}, 3, 9)):
            with self.subTest(config=config):
                engine, unit, actor = fixture()
                for key, value in config.items(): setattr(engine, key, value)
                actor.skills = {'Gunnery-Battlemech': 3, 'Gunnery-Laser': 8,
                                'Piloting-Battlemech': 4, 'Piloting-Biped': 9}
                original_skills = dict(actor.skills)
                unit.pilot, unit.status = actor, S.STARTED
                weapon = get_weapon('IS.MediumLaser')
                self.assertEqual(gun, calculate_bth(unit, unit, weapon, 1).base)
                with use_source(lambda *args: 8):
                    result = engine.inject_command(unit, lambda: p.make_piloting_roll(unit, award_xp=False))
                self.assertEqual((pilot, pilot <= 8), (result.target, result.success))
                self.assertEqual(original_skills, actor.skills)
                unit.gun_pilot = Pilot(gunnery=2)
                self.assertEqual(2, p.find_pilot_gunnery(unit, weapon))
                self.assertEqual(pilot, p.find_pilot_piloting(unit))
                unit.quiet, unit.mechskills = True, '1 0 7 8'
                self.assertEqual((1, 0, 7, 8), (p.find_pilot_piloting(unit), p.find_pilot_gunnery(unit, weapon),
                    p.find_pilot_spotting(unit), p.find_pilot_arty_gun(unit)))
                unit.quiet, unit.gun_pilot, actor.skills = False, None, {}
                actor.gunnery, actor.piloting = 2, 3
                self.assertEqual(2, calculate_bth(unit, unit, weapon, 1).base)
                self.assertEqual(3, p.piloting_bth(unit))

    def test_quiet_signed_columns_and_partial_parse(self):
        _, unit, actor = fixture()
        unit.pilot, unit.quiet, unit.mechskills = actor, True, ' 0 -1 +3 junk 4'
        self.assertEqual((0, -1, 3, 8), (p.find_pilot_piloting(unit), p.find_pilot_gunnery(unit),
                                      p.find_pilot_spotting(unit), p.find_pilot_arty_gun(unit)))
        unit.quiet = False
        self.assertEqual((5, 4, 8, 8), (p.find_pilot_piloting(unit), p.find_pilot_gunnery(unit),
                                      p.find_pilot_spotting(unit), p.find_pilot_arty_gun(unit)))
        unit.quiet, unit.mechskills = True, '2-3 4 5'
        self.assertEqual(-3, p.find_pilot_gunnery(unit))

    def test_extended_name_branches_and_weapon_precedence(self):
        engine, unit, _ = fixture(U.MW)
        unit.terrain = '~'
        for extended, weapon, gun, pilot in ((False, 'PC.Sword', 'Blade', 'Running'),
                (False, 'PC.Blade', 'Small_Arms', 'Running'),
                (True, 'PC.Sword', 'Small_Arms', 'Swimming'),
                (True, 'PC.Blade', 'Blade', 'Swimming'),
                (True, 'PC.HeavyGyrojetGun', 'Support_Weapons', 'Swimming')):
            engine.extended_gunnery = engine.extended_piloting = extended
            spec = SimpleNamespace(name=weapon, weapon_type=WeaponType.TBEAM)
            self.assertEqual(gun, p.find_gunnery_skill_name(unit, spec))
            self.assertEqual(pilot, p.find_piloting_skill_name(unit))
        self.assertIsNone(p.find_gunnery_skill_name(unit, -1))
        unit.unit_type = U.BSUIT
        self.assertEqual('Piloting-Bsuit', p.find_piloting_skill_name(unit))
        self.assertEqual('Gunnery-Laser', p.find_gunnery_skill_name(unit, SimpleNamespace(name='Flamer', weapon_type=WeaponType.TBEAM)))
        self.assertEqual('Gunnery-Flamer', p.find_gunnery_skill_name(unit, SimpleNamespace(name='Flamer', weapon_type=WeaponType.THAND)))

    def test_named_skills_validity_remote_pilot_and_separate_gunner(self):
        engine, unit, actor = fixture()
        engine.extended_gunnery = engine.extended_piloting = True
        actor.skills = {'Piloting-Biped': 2, 'Gunnery-Laser': 3}
        unit.pilot = actor
        self.assertEqual(2, p.find_pilot_piloting(unit))
        actor.connected = False
        self.assertEqual(6, p.find_pilot_piloting(unit))
        actor.is_player = False
        self.assertEqual(2, p.find_pilot_piloting(unit))
        actor.location = -5
        self.assertEqual(6, p.find_pilot_piloting(unit))
        unit.gun_pilot = Pilot(gunnery=1)
        self.assertEqual(1, p.find_pilot_gunnery(unit, get_weapon('IS.MediumLaser')))
        unit.in_character = True
        unit.pilot_skill_base = 3
        unit.specials2 |= 0x2000000
        self.assertEqual(17, p.piloting_bth(unit, 2))

    def test_technician_names_and_no_tech_for_mw(self):
        _, unit, actor = fixture(U.MW)
        self.assertIsNone(p.find_tech_skill_name(unit))
        self.assertEqual(18, p.find_tech_skill(actor, unit))
        unit.unit_type = U.VEH_NAVAL
        actor.skills = {'Technician-Mechanic': 4}
        self.assertEqual(4, p.find_tech_skill(actor, unit))


class SourcePilotRollTest(unittest.TestCase):
    def test_fallen_success_precedes_all_failure_guards_and_consumes_no_roll(self):
        engine, unit, actor = fixture()
        unit.pilot, unit.status = actor, S.FALLEN | S.UNCONSCIOUS | S.BLINDED
        result = engine.inject_command(unit, lambda: p.make_piloting_roll(unit))
        self.assertTrue(result.success)
        self.assertEqual(0, engine.randomness.total_rolls)
        result = engine.inject_command(unit, lambda: p.make_piloting_roll(unit, succeed_when_fallen=False))
        self.assertFalse(result.success)
        self.assertEqual(0, engine.randomness.total_rolls)

    def test_high_target_rolls_and_uses_accumulated_base_not_inferred_damage(self):
        engine, unit, actor = fixture()
        unit.pilot, unit.status, unit.crit_status = actor, S.STARTED, C.GYRO_DESTROYED
        unit.pilot_skill_base = 20
        with use_source(lambda name, low, high, fallback: 12):
            result = engine.inject_command(unit, lambda: p.make_piloting_roll(unit))
        self.assertEqual((25, 12, False), (result.target, result.roll, result.success))
        self.assertEqual(1, engine.randomness.total_rolls)

    def test_xp_success_bounds_and_noxp(self):
        for skill, mods, xp, requested in ((5, 0, True, 1), (8, 3, True, 4), (2, 0, True, 0), (5, 0, False, 0)):
            engine, unit, actor = fixture()
            unit.pilot, unit.status, actor.piloting = actor, S.STARTED, skill
            with use_source(lambda name, low, high, fallback: 12):
                result = engine.inject_command(unit, lambda: p.make_piloting_roll(unit, mods, award_xp=xp))
            self.assertTrue(result.success)
            self.assertEqual(requested, sum(item['amount'] for item in getattr(unit, 'xp_requests', [])))
            if requested: self.assertFalse(unit.xp_requests[0]['applied'])


if __name__ == '__main__': unittest.main()
