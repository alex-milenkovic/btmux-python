"""Measured-load cache boundaries and speed enhancements through the public API."""
from core.events import EventType
from entities.mech import Mech, MechStatus as S, MechStatus2 as S2, Specials, CritStatus
from physics.cargo import cargo_max_speed, CACHE_FLAGS
from tests.movement_fixture import MovementTestCase


class CargoTests(MovementTestCase):
    def test_missing_fixture_mass_uses_canonical_weight_and_flags(self):
        from systems.construction_weight import get_weight
        self.unit.measured_mass = None
        cargo_max_speed(self.unit)
        self.assertEqual(get_weight(self.unit), self.unit.rtons)
        self.unit.carried_cargo = 1
        self.unit.clear_crit_status(CritStatus.LOAD_OK)
        self.assertGreater(cargo_max_speed(self.unit), 0)
        self.assertEqual(2, self.unit.rcw)

    def test_tow_resolves_its_canonical_weight(self):
        from systems.construction_weight import get_weight
        tow = Mech.create_test_mech()
        self.engine.register_entity(tow)
        self.unit.carrying = tow._id
        cargo_max_speed(self.unit)
        self.assertEqual(2 * get_weight(tow), self.unit.rcw)

    def test_destroyed_unit_needs_no_load_measurement(self):
        self.unit.set_status(S.DESTROYED)
        self.unit.measured_mass = None
        self.unit.carried_cargo = 1
        self.assertEqual(0, cargo_max_speed(self.unit))

    def test_mass_sentinel_underweight_and_overweight(self):
        for mass, expected in ((1, 64.5), (40 * 1024, 64.5), (60 * 1024, 49.61538314819336)):
            with self.subTest(mass=mass):
                self.unit.measured_mass = mass
                self.assertAlmostEqual(expected, cargo_max_speed(self.unit))

    def test_missing_cache_flag_recomputes_without_compounding_boosters(self):
        self.unit.set_status(S.MASC_ENABLED)
        self.assertEqual(86, cargo_max_speed(self.unit))
        self.assertEqual(64.5, self.unit.cached_max_speed)
        for flag in (CritStatus.LOAD_OK, CritStatus.OWEIGHT_OK, CritStatus.SPEED_OK):
            with self.subTest(flag=flag):
                self.unit.cached_max_speed = 1
                self.unit.clear_crit_status(flag)
                self.assertEqual(86, cargo_max_speed(self.unit))
                self.assertEqual(CACHE_FLAGS, self.unit.crit_status & CACHE_FLAGS)

    def test_tow_weight_flag_invalidates_unchanged_load_inputs(self):
        tow = Mech()
        tow.measured_mass = 10 * 1024
        tow.set_crit_status(CritStatus.OWEIGHT_OK)
        self.unit.towed_unit = tow
        expected = 46.07143020629883  # source float RMaxSpeed
        self.assertAlmostEqual(expected, cargo_max_speed(self.unit))
        self.unit.cached_max_speed = 1
        self.assertEqual(1, cargo_max_speed(self.unit))
        tow.clear_crit_status(CritStatus.OWEIGHT_OK)
        self.assertAlmostEqual(expected, cargo_max_speed(self.unit))

    def test_hot_myomer_sprint_bonus_is_configurable(self):
        self.unit.specials |= Specials.TRIPLE_MYOMER_TECH
        self.unit.heat = 9
        self.assertEqual(86, cargo_max_speed(self.unit))
        self.unit.set_status2(S2.SPRINTING)
        self.assertEqual(96.75, cargo_max_speed(self.unit))
        self.unit.tsm_sprint_bonus = False
        self.assertEqual(86, cargo_max_speed(self.unit))

    def test_speed_demon_requires_no_pending_transition_and_gravity_runs_last(self):
        self.unit.set_status2(S2.SPRINTING)
        self.unit.pilot.speed_demon = True
        self.unit.set_status(S.UNDERSPECIAL | S.UNDERGRAVITY)
        self.board.grav = 25
        self.assertEqual(193.5, cargo_max_speed(self.unit))
        event=self.engine.events.schedule(60,EventType.MOVEMODE,lambda ev:None,self.unit)
        self.unit._mode_event=event
        self.assertEqual(172, cargo_max_speed(self.unit))
        event.cancel()
        self.assertEqual(193.5, cargo_max_speed(self.unit))
