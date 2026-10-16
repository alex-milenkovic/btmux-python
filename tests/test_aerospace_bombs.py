"""Bomb release owns physical slots and a durable scheduled impact."""
from unittest.mock import patch
from tests import test_aerospace_flight as flight
from tests.movement_fixture import MovementTestCase
from entities.crittypes import i2bomb
from systems import bombing as b
from core.events import EventType


class BombTests(MovementTestCase):
    def setUp(self):
        super().setUp()
        self.board._id=self.unit.mapindex=100
        self.unit.unit_type=flight.U.AERO
        self.unit.move_type=flight.M.FLY
        self.unit.max_speed=60
        self.unit.fuel=1000
        self.unit.z, self.unit.fz = 50, 3225
        self.slot = self.unit.sections[0].criticals[0]
        self.slot.type = i2bomb(2)

    def test_aim_time_suffix_and_no_payload_mutation(self):
        self.unit.fz = 1.125*64.5
        result = b.aim(self.unit)
        self.assertAlmostEqual(result['time'], 1.5)
        self.assertIn('1.5 seconds', result['message'])
        self.assertEqual(self.slot.type, i2bomb(2))

    def test_ballistic_radicand_uses_source_float_addition(self):
        from core.randomness import float32
        self.unit.fz=float32(68.22)
        self.unit.start_fz=float32(19.02)
        # C calc_dest expression, with float operands before sqrt promotion.
        self.assertEqual(b.calc_dest(self.unit)[0],float32(1.77890038))

    def test_offmap_drop_rolls_but_keeps_payload_and_cargo(self):
        self.unit.start_fx = 10000
        before = self.unit.carried_cargo
        with patch('systems.piloting.make_piloting_roll') as psr:
            psr.return_value.success = True
            result = b.drop(self.unit,1)
        psr.assert_called_once_with(self.unit,5)
        self.assertFalse(result['scheduled'])
        self.assertEqual((self.slot.type,self.unit.carried_cargo),(i2bomb(2),before))
        self.assertEqual(self.engine.events.count_type(EventType.ARTILLERY_HIT),0)

    def test_destroyed_slots_list_but_drop_numbers_skip_them(self):
        self.slot.firemode |= __import__("entities.mech",fromlist=["FireMode"]).FireMode.DESTROYED_MODE
        live = self.unit.sections[0].criticals[2]
        live.type = i2bomb(5)
        self.assertEqual(len(b.payload(self.unit)),2)
        with patch('systems.piloting.make_piloting_roll') as psr:
            psr.return_value.success = True
            result=b.drop(self.unit,1)
        self.assertTrue(result['scheduled'])
        self.assertEqual((self.slot.type,live.type),(i2bomb(2),0))

    def test_hit_event_captures_map_type_and_hex(self):
        with patch('systems.piloting.make_piloting_roll') as psr:
            psr.return_value.success = True
            b.drop(self.unit,1)
        self.unit.map = None
        self.unit.set_status(__import__('entities.mech',fromlist=['MechStatus']).MechStatus.DESTROYED)
        with patch('systems.damage.blast_hit_hexes') as blast:
            self.engine.events.run_by_type(EventType.ARTILLERY_HIT)
        self.assertEqual(blast.call_args.args[:6],(self.board,130,10,0,10,10))
        self.assertEqual(self.engine.events.count_type(EventType.ARTILLERY_HIT),0)
