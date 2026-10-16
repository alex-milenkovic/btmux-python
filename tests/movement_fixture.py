"""Ready movement unit and owning map/engine shared by focused unit tests."""
import unittest
from entities.mech import Mech, MechStatus as S
from entities.map import GameMap
from entities.pilot import Pilot
from core.game_loop import GameEngine


class MovementTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.unit = Mech.create_test_mech()
        self.unit.measured_mass = self.unit.tonnage * 1024
        self.unit.pilot = Pilot()
        self.unit.set_status(S.STARTED)
        self.board = GameMap(20, 20)
        self.board._id = 100
        self.engine.register_entity(self.board)
        self.unit.set_hex_position(10, 10)
        self.board.add_mech(self.unit)
        self.engine.register_entity(self.unit)
