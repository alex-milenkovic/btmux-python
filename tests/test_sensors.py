"""
Tests for systems/sensors.py — the sensors[] table, per-sensor see-chance /
can-see / to-hit functions, and Sensor_ToHitBonus.

C references: mech.sensor.h:116-171 (table), mech.sensor.functions.c
(per-sensor math), mech.sensor.c:27-77 (Sensor_ToHitBonus), :95-96
(MaxVis/MaxVar).
"""

import unittest
from unittest.mock import patch

from entities.map import GameMap, LIGHT_FOREST, HEAVY_FOREST
from entities.mech import Mech, MechStatus, CritStatus, UnitType, MoveType, Specials
from systems.los import (
    MECHLOSFLAG_BLOCK, MECHLOSFLAG_FIRE, MECHLOSFLAG_SMOKE,
    MECHLOSFLAG_MNTN, MECHLOSFLAG_PARTIAL,
    MECHLOSFLAG_SEESP, MECHLOSFLAG_SEESS,
    MECHLOSFLAG_WOOD, MECHLOSFLAG_WATER,
)
from systems.sensors import (
    sensors, NUM_SENSORS, SensorStruct,
    SENSOR_VIS, SENSOR_LA, SENSOR_IR, SENSOR_EM, SENSOR_SE, SENSOR_RA,
    SENSOR_BAP, SENSOR_BHAP,
    SENSOR_ATTR_SEISMIC, BLOODHOUND_PROBE_TECH, AC_INCENDIARY_MODE,
    sensor_index_from_letter,
    mech_losflag_wood_count, mech_losflag_water_count,
    heat_modifier, weight_modifier, move_modifier, nwood_count,
    vislight_see, liteamp_see, infrared_see, electrom_see, seismic_see,
    radar_see, bap_see, blood_see,
    vislight_csee, liteamp_csee, infrared_csee, electrom_csee,
    seismic_csee, radar_csee, bap_csee, blood_csee,
    vislight_tohit, liteamp_tohit, infrared_tohit, electrom_tohit,
    seismic_tohit, radar_tohit, bap_tohit, blood_tohit,
    max_vis, max_var, maxvr, sensor_to_hit_bonus,
)


def make_mech(**kw):
    """Test mech on a small map, started, at (5,5)."""
    mech = Mech.create_test_mech()
    mech.x, mech.y = 5, 5
    for k, v in kw.items():
        setattr(mech, k, v)
    return mech


def make_pair():
    """Looker + target on a shared 20x20 grassland map."""
    from core.game_loop import GameEngine
    game_map = GameMap(20, 20, "test")
    game_map._engine = GameEngine()
    m = make_mech()
    t = make_mech()
    t.x, t.y = 8, 5
    game_map.add_mech(m)
    game_map.add_mech(t)
    m.set_status(MechStatus.STARTED)
    t.set_status(MechStatus.STARTED)
    return m, t, game_map


class TestSensorTable(unittest.TestCase):
    """sensors[] integrity vs mech.sensor.h:116-169."""

    def test_row_count(self):
        self.assertEqual(NUM_SENSORS, 9)
        self.assertEqual(len(sensors), 9)

    def test_matchletters(self):
        self.assertEqual([s.matchletter for s in sensors],
                         ["V", "L", "I", "E", "S", "R", "B", "A", "H"])

    def test_maxvis_and_maxvvar(self):
        self.assertEqual([s.maxvis for s in sensors],
                         [60, 60, 15, 24, 8, 180, 6, 3, 8])
        self.assertEqual([s.maxvvar for s in sensors],
                         [0, 0, 0, 8, 4, 0, 0, 0, 0])

    def test_fullvision(self):
        self.assertEqual([s.fullvision for s in sensors],
                         [0, 0, 1, 1, 1, 1, 1, 1, 1])

    def test_light_and_specials_columns(self):
        # Only light-amp uses the light window (0..1); the rest are -1/-1
        self.assertEqual((sensors[SENSOR_LA].min_light,
                          sensors[SENSOR_LA].max_light), (0, 1))
        self.assertEqual((sensors[SENSOR_VIS].min_light,
                          sensors[SENSOR_VIS].max_light), (-1, -1))
        self.assertEqual(sensors[SENSOR_VIS].required_special, 0)
        self.assertEqual(sensors[SENSOR_LA].required_special,
                         0 - Specials.NS_TECH)
        self.assertEqual(sensors[SENSOR_RA].required_special, Specials.AA_TECH)
        self.assertEqual(sensors[SENSOR_BAP].required_special,
                         Specials.BEAGLE_PROBE_TECH)
        self.assertEqual(sensors[7].required_special, Specials.LIGHT_BAP_TECH)
        self.assertEqual(sensors[8].required_special, BLOODHOUND_PROBE_TECH)
        self.assertEqual(sensors[8].specials_set, 2)
        self.assertEqual([s.specials_set for s in sensors[:8]], [1] * 8)
        self.assertEqual(sensors[SENSOR_SE].attribute_check, SENSOR_ATTR_SEISMIC)

    def test_letter_lookup(self):
        self.assertEqual(sensor_index_from_letter("v"), 0)
        self.assertEqual(sensor_index_from_letter("H"), 8)
        self.assertEqual(sensor_index_from_letter("A"), 7)
        self.assertEqual(sensor_index_from_letter("x"), -1)

    def test_losflag_counts(self):
        flag = 5 * MECHLOSFLAG_WOOD + 3 * MECHLOSFLAG_WATER
        self.assertEqual(mech_losflag_wood_count(flag), 5)
        self.assertEqual(mech_losflag_water_count(flag), 3)


class TestSeeChance(unittest.TestCase):
    """SEEFUNC bodies (mech.sensor.functions.c:25-66)."""

    def setUp(self):
        self.m, self.t, self.map = make_pair()

    def test_vislight_basic(self):
        # In range: (100 - r/3); day (l=2)
        self.assertEqual(vislight_see(self.t, self.map, 0, 30.0, 30, 2), 90)
        # Out of range
        self.assertEqual(vislight_see(self.t, self.map, 0, 31.0, 30, 2), 0)
        # No target at all still works
        self.assertEqual(vislight_see(None, self.map, 0, 30.0, 30, 2), 90)

    def test_vislight_lit_target_at_night_triples_range(self):
        self.t.crit_status |= CritStatus.SLITE_LIT
        # r=50 > c=20 normally, but lit target at night (l=0): limit 60
        self.assertEqual(vislight_see(self.t, self.map, 0, 50.0, 20, 0), 83)
        # Same range in daylight (l=2): out of range
        self.assertEqual(vislight_see(self.t, self.map, 0, 50.0, 20, 2), 0)

    def test_vislight_bsuit_divisor(self):
        self.t.unit_type = UnitType.BSUIT
        self.assertEqual(vislight_see(self.t, self.map, 0, 30.0, 30, 2), 30)

    def test_liteamp_ranges(self):
        # Perfect darkness: 2x conditionrange, flat 70 - r
        self.assertEqual(liteamp_see(self.t, self.map, 1, 50.0, 30, 0), 20)
        # Dawn/dusk (l=1): plain conditionrange
        self.assertEqual(liteamp_see(self.t, self.map, 1, 50.0, 30, 1), 0)
        self.assertEqual(liteamp_see(self.t, self.map, 1, 25.0, 30, 1), 45)

    def test_infrared(self):
        self.assertEqual(infrared_see(self.t, self.map, 2, 10.0, 15, 0), 70)

    def test_electrom(self):
        self.assertEqual(electrom_see(self.t, self.map, 3, 20.0, 24, 0), 10)
        self.assertEqual(electrom_see(self.t, self.map, 3, 25.0, 24, 0), 5)
        # r < 24 floors the numerator at 2 -> chance 1
        self.assertEqual(electrom_see(self.t, self.map, 3, 23.9, 24, 0), 6)

    def test_seismic(self):
        self.assertEqual(seismic_see(self.t, self.map, 4, 5.0, 8, 0), 30)

    def test_radar_bounded(self):
        self.assertEqual(radar_see(self.t, self.map, 5, 10.0, 180, 0), 90)
        self.assertEqual(radar_see(self.t, self.map, 5, 100.0, 180, 0), 80)
        self.assertEqual(radar_see(self.t, self.map, 5, 175.0, 180, 0), 10)

    def test_probes_always_101(self):
        self.assertEqual(bap_see(self.t, self.map, 6, 5.0, 6, 0), 101)
        self.assertEqual(blood_see(self.t, self.map, 8, 5.0, 8, 0), 101)


class TestCanSee(unittest.TestCase):
    """CSEEFUNC bodies (mech.sensor.functions.c:74-143)."""

    def setUp(self):
        self.m, self.t, self.map = make_pair()

    def test_vislight_blockers(self):
        self.assertEqual(vislight_csee(self.m, self.t, self.map, 3.0, 0), 1)
        for f in (MECHLOSFLAG_BLOCK, MECHLOSFLAG_FIRE, MECHLOSFLAG_SMOKE,
                  3 * MECHLOSFLAG_WOOD):
            self.assertEqual(vislight_csee(self.m, self.t, self.map, 3.0, f), 0)
        self.assertEqual(
            vislight_csee(self.m, self.t, self.map, 3.0, 2 * MECHLOSFLAG_WOOD), 1)

    def test_vislight_submerged_target(self):
        # Fallen mech at z=-1: ActualElevation z+0.5 < 0, 6 water hexes block
        self.t.z = -1
        self.t.set_status(MechStatus.FALLEN)
        f = 6 * MECHLOSFLAG_WATER
        self.assertEqual(vislight_csee(self.m, self.t, self.map, 3.0, f), 0)
        # 5 water hexes is still fine (block_desc: "5 underwater hexes")
        self.assertEqual(
            vislight_csee(self.m, self.t, self.map, 3.0, 5 * MECHLOSFLAG_WATER), 1)
        # Standing mech (z + 1.5 >= 0) is seen through 6 water hexes
        self.t.status &= ~MechStatus.FALLEN
        self.assertEqual(vislight_csee(self.m, self.t, self.map, 3.0, f), 1)

    def test_liteamp(self):
        self.assertEqual(liteamp_csee(self.m, self.t, self.map, 3.0, 0), 1)
        self.assertEqual(
            liteamp_csee(self.m, self.t, self.map, 3.0, 2 * MECHLOSFLAG_WOOD), 0)
        self.assertEqual(
            liteamp_csee(self.m, self.t, self.map, 3.0, 1 * MECHLOSFLAG_WATER), 0)
        self.t.crit_status |= CritStatus.SLITE_LIT   # lit targets ruin liteamp
        self.assertEqual(liteamp_csee(self.m, self.t, self.map, 3.0, 0), 0)

    def test_infrared(self):
        # Smoke does NOT block IR (only BLOCK | FIRE)
        self.assertEqual(
            infrared_csee(self.m, self.t, self.map, 3.0, MECHLOSFLAG_SMOKE), 1)
        self.assertEqual(
            infrared_csee(self.m, self.t, self.map, 3.0, MECHLOSFLAG_FIRE), 0)
        self.assertEqual(
            infrared_csee(self.m, self.t, self.map, 3.0, 6 * MECHLOSFLAG_WOOD), 0)
        self.t.unit_type = UnitType.BSUIT
        self.assertEqual(infrared_csee(self.m, self.t, self.map, 3.0, 0), 0)

    def test_electrom(self):
        self.assertEqual(electrom_csee(self.m, self.t, self.map, 3.0, 0), 1)
        self.assertEqual(
            electrom_csee(self.m, self.t, self.map, 3.0, MECHLOSFLAG_MNTN), 0)
        self.m.ecm_disturbed = 1  # TODO(ECM wave) attribute contract
        self.assertEqual(electrom_csee(self.m, self.t, self.map, 3.0, 0), 0)

    def test_seismic_requires_moving_grounded_target(self):
        # Stationary target: not seen
        self.assertEqual(seismic_csee(self.m, self.t, self.map, 3.0, 0), 0)
        self.t.speed = 20.0
        self.assertEqual(seismic_csee(self.m, self.t, self.map, 3.0, 0), 1)
        # Jumping looker loses seismic
        self.m.set_status(MechStatus.JUMPING)
        self.assertEqual(seismic_csee(self.m, self.t, self.map, 3.0, 0), 0)
        self.m.status &= ~MechStatus.JUMPING
        # Jumping / hover / unstarted targets aren't seen
        self.t.set_status(MechStatus.JUMPING)
        self.assertEqual(seismic_csee(self.m, self.t, self.map, 3.0, 0), 0)
        self.t.status &= ~MechStatus.JUMPING
        self.t.move_type = MoveType.HOVER
        self.assertEqual(seismic_csee(self.m, self.t, self.map, 3.0, 0), 0)
        self.t.move_type = MoveType.BIPED
        self.t.status &= ~MechStatus.STARTED
        self.assertEqual(seismic_csee(self.m, self.t, self.map, 3.0, 0), 0)

    def test_radar(self):
        # Too low
        self.t.z = 1
        self.assertEqual(radar_csee(self.m, self.t, self.map, 20.0, 0), 0)
        # z in (2,10): seen only within z*z hexes
        self.t.z = 5
        self.assertEqual(radar_csee(self.m, self.t, self.map, 20.0, 0), 1)
        self.assertEqual(radar_csee(self.m, self.t, self.map, 30.0, 0), 0)
        # High targets seen at any range, but not through blocks
        self.t.z = 12
        self.assertEqual(radar_csee(self.m, self.t, self.map, 170.0, 0), 1)
        self.assertEqual(
            radar_csee(self.m, self.t, self.map, 170.0, MECHLOSFLAG_BLOCK), 0)

    def test_bap_and_bloodhound(self):
        self.assertEqual(bap_csee(self.m, self.t, self.map, 3.0, 0), 1)
        self.assertEqual(blood_csee(self.m, self.t, self.map, 3.0, 0), 1)
        self.t.status2 |= 0x00000040  # STH_ARMOR_ON (btmacros.h)
        self.assertEqual(bap_csee(self.m, self.t, self.map, 3.0, 0), 0)
        # Bloodhound ignores stealth armor...
        self.assertEqual(blood_csee(self.m, self.t, self.map, 3.0, 0), 1)
        # ...but not Angel ECM or own disturbance
        self.t.angel_ecm_protected = 1
        self.assertEqual(blood_csee(self.m, self.t, self.map, 3.0, 0), 0)
        self.t.angel_ecm_protected = 0
        self.m.ecm_disturbed = 1
        self.assertEqual(blood_csee(self.m, self.t, self.map, 3.0, 0), 0)

    def test_map_sensorflags_oddity(self):
        # Map-wide sensor blocking; Bloodhound checks bit SENSOR_BHAP (7),
        # the LBAP table slot, not its own row index (8) — C oddity.
        self.map.sensorflags = 1 << SENSOR_VIS
        self.assertEqual(vislight_csee(self.m, self.t, self.map, 3.0, 0), 0)
        self.map.sensorflags = 1 << SENSOR_BHAP
        self.assertEqual(blood_csee(self.m, self.t, self.map, 3.0, 0), 0)
        self.map.sensorflags = 1 << 8
        self.assertEqual(blood_csee(self.m, self.t, self.map, 3.0, 0), 1)


class TestToHit(unittest.TestCase):
    """TOHITFUNC bodies (mech.sensor.functions.c:168-216)."""

    def setUp(self):
        self.m, self.t, self.map = make_pair()

    def test_vislight(self):
        self.assertEqual(vislight_tohit(self.m, self.t, self.map, 0, 2), 0)
        self.assertEqual(vislight_tohit(self.m, self.t, self.map, 0, 0), 2)
        # Lit target removes the darkness penalty
        self.t.crit_status |= CritStatus.SLITE_LIT
        self.assertEqual(vislight_tohit(self.m, self.t, self.map, 0, 0), 0)
        self.t.crit_status &= ~CritStatus.SLITE_LIT
        # Partial cover +3, hulldown further +2
        f = MECHLOSFLAG_PARTIAL
        self.assertEqual(vislight_tohit(self.m, self.t, self.map, f, 2), 3)
        self.t.set_status(MechStatus.HULLDOWN)
        self.assertEqual(vislight_tohit(self.m, self.t, self.map, f, 2), 5)

    def test_vislight_target_own_forest_hex(self):
        # nwood_count adds target hex forest unless it's above the trees
        self.map.set_terrain(self.t.x, self.t.y, HEAVY_FOREST)
        self.assertEqual(vislight_tohit(self.m, self.t, self.map, 0, 2), 2)
        self.map.set_terrain(self.t.x, self.t.y, LIGHT_FOREST)
        self.assertEqual(vislight_tohit(self.m, self.t, self.map, 0, 2), 1)
        self.t.z = 3  # above the trees (elev 0 + 2 < 3)
        self.assertEqual(vislight_tohit(self.m, self.t, self.map, 0, 2), 0)

    def test_liteamp(self):
        # (2-l)/2 int division
        self.assertEqual(liteamp_tohit(self.m, self.t, self.map, 0, 0), 1)
        self.assertEqual(liteamp_tohit(self.m, self.t, self.map, 0, 1), 0)
        # woods * 3 / 2
        f = 2 * MECHLOSFLAG_WOOD
        self.assertEqual(liteamp_tohit(self.m, self.t, self.map, f, 2), 3)

    def test_infrared_heat_scaling(self):
        # HEAT_MODIFIER(MechHeat + 7) (mech.sensor.functions.c:155,190)
        for heat, expected in ((0.0, 2), (3.0, 1), (8.0, 0), (15.0, -1), (16.0, -2)):
            self.t.heat = heat
            self.assertEqual(
                infrared_tohit(self.m, self.t, self.map, 0, 2), expected,
                "heat=%s" % heat)

    def test_electrom(self):
        with patch.object(self.map._engine.randomness, 'number', return_value=0):
            # 50 tons, stationary, unfired: all modifiers zero
            self.assertEqual(electrom_tohit(self.m, self.t, self.map, 0, 2), 0)
            self.t.tonnage = 80
            self.t.speed = 20.0
            self.t.set_status(MechStatus.FIRED)
            # weight -1, moving +1, fired -1
            self.assertEqual(electrom_tohit(self.m, self.t, self.map, 0, 2), -1)
        self.map._engine.run_ticks(6)  # MNumber refreshes only once per six seconds.
        with patch.object(self.map._engine.randomness, 'number', return_value=1):
            self.t.tonnage = 50
            self.t.speed = 0.0
            self.t.status &= ~MechStatus.FIRED
            self.assertEqual(electrom_tohit(self.m, self.t, self.map, 0, 2), 1)

    def test_seismic(self):
        from data.templates import update_oweight
        update_oweight(self.t, self.t.tonnage * 1024)
        with patch.object(self.map._engine.randomness, 'number', return_value=0):
            # Base 2, medium weight 0, stationary 0
            self.assertEqual(seismic_tohit(self.m, self.t, self.map, 0, 2), 2)
            # Moving target is EASIER for seismic (minus move modifier)
            self.t.speed = 20.0
            self.assertEqual(seismic_tohit(self.m, self.t, self.map, 0, 2), 1)
            self.t.tonnage = 20   # light +1
            update_oweight(self.t, 20 * 1024)
            self.assertEqual(seismic_tohit(self.m, self.t, self.map, 0, 2), 2)

    def test_seismic_consumes_cached_real_weight(self):
        from data.templates import update_oweight
        self.t.tonnage = 80
        with patch.object(self.map._engine.randomness, 'number', return_value=0):
            update_oweight(self.t, 20 * 1024)
            self.assertEqual(seismic_tohit(self.m, self.t, self.map, 0, 2), 3)
            update_oweight(self.t, 80 * 1024)
            self.assertEqual(seismic_tohit(self.m, self.t, self.map, 0, 2), 1)

    def test_radar(self):
        self.assertEqual(radar_tohit(self.m, self.t, self.map, 0, 2), 0)
        self.t.z = 12
        self.assertEqual(radar_tohit(self.m, self.t, self.map, 0, 2), -3)
        # Reduced partial-cover penalty (2, not 3)
        self.assertEqual(
            radar_tohit(self.m, self.t, self.map, MECHLOSFLAG_PARTIAL, 2), -1)
        self.t.z = 0
        self.t.move_type = MoveType.VTOL  # FlyingT
        self.assertEqual(radar_tohit(self.m, self.t, self.map, 0, 2), -3)

    def test_probes(self):
        self.map._engine.run_ticks(6)  # Initial source window0 reuses rnd0; refresh at6.
        with patch.object(self.map._engine.randomness, 'number', return_value=2) as rnd:
            self.assertEqual(bap_tohit(self.m, self.t, self.map, 0, 2), 2)
            self.assertEqual(blood_tohit(self.m, self.t, self.map, 0, 2), 2)
            rnd.assert_called_once_with(0, 2**31 - 1)


class TestHelpers(unittest.TestCase):
    """HEAT/WEIGHT/MOVE_MODIFIER (mech.sensor.functions.c:155-161)."""

    def test_heat_modifier(self):
        self.assertEqual([heat_modifier(v) for v in (7, 10, 15, 22, 23)],
                         [2, 1, 0, -1, -2])

    def test_weight_modifier(self):
        self.assertEqual([weight_modifier(v) for v in (100, 66, 65, 36, 35, 20)],
                         [-1, -1, 0, 0, 1, 1])

    def test_move_modifier(self):
        self.assertEqual(move_modifier(10.75), 1)
        self.assertEqual(move_modifier(-10.75), 1)
        self.assertEqual(move_modifier(10.7), 0)


class TestMaxVis(unittest.TestCase):
    """MaxVis/MaxVar (mech.sensor.c:95-96)."""

    def test_max_vis_moving(self):
        mech = make_mech()
        self.assertEqual(max_vis(mech, SENSOR_IR), 15)
        self.assertEqual(max_vis(mech, SENSOR_VIS), 60)

    def test_max_vis_stationary_boost(self):
        mech = make_mech(move_type=MoveType.NONE)
        # 140% boost only for sensor index >= 2
        self.assertEqual(max_vis(mech, SENSOR_IR), 21)
        self.assertEqual(max_vis(mech, SENSOR_RA), 252)
        self.assertEqual(max_vis(mech, SENSOR_VIS), 60)
        self.assertEqual(max_vis(mech, SENSOR_LA), 60)

    def test_max_var_and_maxvr(self):
        mech = make_mech()
        self.assertEqual(max_var(mech, SENSOR_EM), 8)
        self.assertEqual(max_var(mech, SENSOR_SE), 4)
        self.assertEqual(maxvr(mech, SENSOR_EM), 16)


class TestSensorToHitBonus(unittest.TestCase):
    """Sensor_ToHitBonus (mech.sensor.c:27-77)."""

    def setUp(self):
        self.m, self.t, self.map = make_pair()

    def test_sees_with_neither(self):
        self.assertEqual(
            sensor_to_hit_bonus(self.m, self.t, 0, 2, 5.0, 0), 10000)

    def test_primary_only(self):
        self.m.sensor = [SENSOR_VIS, SENSOR_IR]
        self.assertEqual(
            sensor_to_hit_bonus(self.m, self.t, MECHLOSFLAG_SEESP, 2, 5.0, 0), 0)

    def test_secondary_only_gets_plus_one(self):
        self.m.sensor = [SENSOR_VIS, SENSOR_IR]
        self.t.heat = 0.0  # infrared_tohit -> +2
        self.assertEqual(
            sensor_to_hit_bonus(self.m, self.t, MECHLOSFLAG_SEESS, 2, 5.0, 0), 3)

    def test_identical_sensors_use_primary_straight(self):
        self.m.sensor = [SENSOR_IR, SENSOR_IR]
        f = MECHLOSFLAG_SEESP | MECHLOSFLAG_SEESS
        self.t.heat = 0.0
        self.assertEqual(sensor_to_hit_bonus(self.m, self.t, f, 2, 5.0, 0), 2)

    def test_both_sensors_take_min(self):
        self.m.sensor = [SENSOR_VIS, SENSOR_IR]
        f = MECHLOSFLAG_SEESP | MECHLOSFLAG_SEESS
        # day: vislight 0, IR 2+1=3 -> 0
        self.assertEqual(sensor_to_hit_bonus(self.m, self.t, f, 2, 5.0, 0), 0)
        # night: vislight 2, IR 3 -> 2
        self.assertEqual(sensor_to_hit_bonus(self.m, self.t, f, 0, 5.0, 0), 2)

    def test_incendiary_lights_the_night(self):
        self.m.sensor = [SENSOR_VIS, SENSOR_VIS]
        # maplight 1 -> vislight penalty (2-1)=1
        self.assertEqual(
            sensor_to_hit_bonus(self.m, self.t, MECHLOSFLAG_SEESP, 1, 5.0, 0), 1)
        # incendiary ammo bumps light by 1 -> penalty 0
        self.assertEqual(
            sensor_to_hit_bonus(self.m, self.t, MECHLOSFLAG_SEESP, 1, 5.0,
                                AC_INCENDIARY_MODE), 0)

    def test_maplight_clamped(self):
        self.m.sensor = [SENSOR_VIS, SENSOR_VIS]
        # maplight -3 clamps to 0 -> penalty 2
        self.assertEqual(
            sensor_to_hit_bonus(self.m, self.t, MECHLOSFLAG_SEESP, -3, 5.0, 0), 2)
        # maplight 5 clamps to 2 -> penalty 0
        self.assertEqual(
            sensor_to_hit_bonus(self.m, self.t, MECHLOSFLAG_SEESP, 5, 5.0, 0), 0)


class TestNwoodCount(unittest.TestCase):
    """nwood_count (mech.sensor.functions.c:163-166)."""

    def test_flag_plus_own_hex(self):
        _, t, game_map = make_pair()
        f = 2 * MECHLOSFLAG_WOOD
        self.assertEqual(nwood_count(t, f), 2)
        game_map.set_terrain(t.x, t.y, HEAVY_FOREST)
        self.assertEqual(nwood_count(t, f), 4)
        t.z = 5  # above the trees
        self.assertEqual(nwood_count(t, f), 2)


if __name__ == '__main__':
    unittest.main()
