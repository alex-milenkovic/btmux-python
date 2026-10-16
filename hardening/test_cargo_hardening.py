"""C fixed-point and configuration boundaries exposed by source mutation."""
import unittest

from entities.mech import Mech, MechStatus as S, Specials, CritStatus
from entities.pilot import Pilot
from physics.cargo import cargo_max_speed


def ready_unit():
    unit = Mech.create_test_mech()
    unit.pilot = Pilot()
    unit.measured_mass = 50 * 1024
    return unit


class TestCargoHardening(unittest.TestCase):
    def test_heat_does_not_enable_uninstalled_myomer(self):
        unit = ready_unit()
        unit.specials = Specials.NONE
        unit.heat = 9
        self.assertEqual(64.5, cargo_max_speed(unit))

    def test_cargo_equipment_halves_effective_mech_load(self):
        unit = ready_unit()
        unit.specials |= Specials.CARGO_TECH
        unit.carried_cargo = 10 * 1024
        self.assertEqual(53.75, cargo_max_speed(unit))

    def test_mass_rounding_remains_integer_under_load(self):
        # The denominator is the adjusted fixed-point mass plus cargo, or
        # nominal + floor(cargo/3) when that is larger (mech.move.c).
        for mass, cargo, denominator in ((1, 10240, 71680),
                                          (51201, 10240, 71681),
                                          (40960, 12800, 69973),
                                          (1024, 3073, 53248)):
            with self.subTest(mass=mass, cargo=cargo):
                unit = ready_unit()
                unit.measured_mass = mass
                unit.carried_cargo = cargo
                self.assertAlmostEqual(3302400 / denominator, cargo_max_speed(unit), places=10)

    def test_one_ton_nominal_is_at_the_denominator_floor(self):
        unit = ready_unit()
        unit.tonnage = 1
        unit.measured_mass = 1024
        self.assertEqual(64.5, cargo_max_speed(unit))

    def test_tow_bonus_configuration_invalidates_loaded_speed(self):
        unit = ready_unit()
        tow = ready_unit()
        tow.measured_mass = 10 * 1024
        tow.set_crit_status(CritStatus.OWEIGHT_OK)
        unit.towed_unit = tow
        unit.specials |= Specials.TRIPLE_MYOMER_TECH
        unit.heat = 9
        cargo_max_speed(unit)
        self.assertEqual(53.75, unit.cached_max_speed)
        unit.tsm_tow_bonus = False
        cargo_max_speed(unit)
        self.assertAlmostEqual(3302400 / 71680, unit.cached_max_speed)
        unit.tsm_tow_bonus = True
        cargo_max_speed(unit)
        self.assertEqual(53.75, unit.cached_max_speed)

    def test_combined_tow_reductions_truncate_fixed_point_remainders(self):
        unit = ready_unit()
        tow = ready_unit()
        tow.measured_mass = 10243
        unit.towed_unit = tow
        unit.specials |= Specials.TRIPLE_MYOMER_TECH | Specials.SALVAGE_TECH
        unit.specials2 = 0x80000
        unit.heat = 9
        cargo_max_speed(unit)
        # 20486 -> 10243 -> 5121 -> 2560 fixed-point mass.
        self.assertAlmostEqual(3302400 / 53760, unit.cached_max_speed, places=10)

    def test_unrelated_special_flag_does_not_grant_carrier_tow_bonus(self):
        unit = ready_unit()
        tow = ready_unit()
        tow.measured_mass = 10 * 1024
        unit.towed_unit = tow
        unit.specials2 = 1
        self.assertAlmostEqual(3302400 / 71680, cargo_max_speed(unit))

    def test_walk_xp_uses_unboosted_integer_speed_and_a_minimum(self):
        unit = ready_unit()
        unit.set_status(S.MASC_ENABLED)
        cargo_max_speed(unit)
        self.assertAlmostEqual(128 / 10.75, unit.walk_xp_factor)
        unit.carried_cargo = 100 * 1024
        self.assertEqual(0, cargo_max_speed(unit))
        self.assertEqual(2, unit.walk_xp_factor)

    def test_unavailable_mass_has_explicit_diagnostics(self):
        unit = ready_unit()
        unit.measured_mass = None
        unit.carried_cargo = 1
        with self.assertRaisesRegex(ValueError, '^Cargo requires measured_mass; live get_weight is not implemented$'):
            cargo_max_speed(unit)
        unit.measured_mass = 51200
        unit.towed_unit = Mech()
        with self.assertRaisesRegex(ValueError, '^Towed unit requires measured_mass$'):
            cargo_max_speed(unit)
