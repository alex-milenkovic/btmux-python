import unittest
from entities.mech import Mech, Location, FireMode, SectionConfig, MechStatus
from entities.map import GameMap, WATER
from entities.crittypes import Special, i2special
from physics.flooding import flood_location, flood_unit


class FloodingTests(unittest.TestCase):
    def setUp(self):
        self.unit = Mech.create_test_mech()
        self.board = GameMap(2, 2)
        self.board.set_terrain(0, 0, WATER)
        self.board.set_elevation(0, 0, 1)
        self.unit.z = -1
        self.unit.set_status(MechStatus.FALLEN)
        self.board.add_mech(self.unit)

    def test_breach_disables_and_does_not_destroy_or_repeat_sink_loss(self):
        section = self.unit.sections[Location.LARM]
        section.armor = 0
        section.criticals[0].type = i2special(Special.HEAT_SINK)
        sinks = self.unit.num_sinks
        flood_unit(self.unit)
        self.assertTrue(section.config & SectionConfig.SECTION_FLOODED)
        self.assertTrue(section.criticals[0].firemode & FireMode.DISABLED_MODE)
        self.assertFalse(section.criticals[0].firemode & FireMode.DESTROYED_MODE)
        self.assertEqual(sinks - 1, self.unit.num_sinks)
        flood_unit(self.unit)
        self.assertEqual(sinks - 1, self.unit.num_sinks)

    def test_upright_shallow_torso_does_not_flood(self):
        self.unit.clear_status(MechStatus.FALLEN)
        self.unit.sections[Location.CTORSO].armor = 0
        flood_location(self.unit, Location.CTORSO, -1)
        self.assertFalse(self.unit.sections[Location.CTORSO].config & SectionConfig.SECTION_FLOODED)

    def test_head_flood_destroys_unit(self):
        self.unit.sections[Location.HEAD].armor = 0
        flood_unit(self.unit)
        self.assertTrue(self.unit.is_destroyed)
