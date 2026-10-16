"""Wall-clock work accumulation, parser boundaries and real repair queue identity."""
import unittest
from types import SimpleNamespace
from core.game_loop import GameEngine
from entities.mech import Mech,UnitType
from systems.economic_inventory import InventoryStore
from systems.technician import Technician,parse_part,pack,unpack,variable_minutes


class TechnicianTests(unittest.TestCase):
    def setUp(self):
        self.engine=GameEngine();self.engine.sim_now=1000
        self.store=InventoryStore();self.actor=SimpleNamespace(_id=7,tech=True,wizard=False,location=10)
        self.store.register(7,self.actor);self.tech=Technician(self.engine,self.store)
        self.unit=Mech();self.unit.repair_stall=True

    def test_subminute_backlog_is_preserved_but_fatigue_truncates(self):
        self.store.put(7,'TECHTIME','1059')
        self.assertEqual(self.tech.pending(self.actor),0)
        self.assertEqual(self.tech.add_time(self.actor,2),179)
        self.assertEqual(self.store.get(7,'TECHTIME'),'1179')

    def test_past_timestamp_and_inspection_do_not_move_either_clock(self):
        self.store.put(7,'TECHTIME','999');before=(self.engine.sim_now,self.engine.tick)
        self.assertFalse(self.tech.status(self.actor)['pending'])
        self.assertEqual((self.engine.sim_now,self.engine.tick),before)
        self.assertEqual(self.tech.add_time(self.actor,2),120)

    def test_gate_order_wizard_still_needs_clearance_and_fatigue(self):
        self.actor.wizard=True;self.actor.tech=False
        with self.assertRaisesRegex(ValueError,'clearance'):self.tech.gate(self.actor,None)
        self.actor.tech=True;self.unit.repair_stall=False
        self.tech.gate(self.actor,self.unit)
        self.store.put(7,'TECHTIME',str(1000+600*60))
        with self.assertRaisesRegex(ValueError,'tired'):self.tech.fatigue(self.actor)

    def test_d_gate_default_bypasses_stall_but_c_gate_does_not(self):
        self.unit.repair_stall=False
        self.tech.gate(self.actor,self.unit,'D')
        with self.assertRaisesRegex(ValueError,'stall'):self.tech.gate(self.actor,self.unit,'C')

    def test_parser_retains_atoi_rear_and_fighter_slot_bounds(self):
        self.assertEqual(parse_part(self.unit,'CT 2junk'),(0,4,1,0))
        self.assertEqual(parse_part(self.unit,'CT rear',position=False,rear=True),(0,12,0,0))
        self.assertEqual(parse_part(self.unit,'CT 2 cluster',extra=True),(0,4,1,'c'))
        self.unit.unit_type=UnitType.AERO
        self.assertEqual(parse_part(self.unit,'Cockpit 5'),(0,4,4,0))
        self.assertEqual(parse_part(self.unit,'Cockpit 6')[0],-2)

    def test_aptitude_consumes_the_shared_seeded_generator(self):
        from unittest.mock import patch
        from core.randomness import RandomState,use_simulation
        from data.characters import CharacterStore
        from systems.characters import set_value
        chars=CharacterStore();chars.create(7,'Tech');actor=chars.actor(7)
        set_value(chars,7,'Tech_Aptitude',1)
        reference=RandomState(17);dice=[reference.number(1,6) for _ in range(3)]
        state=RandomState(17)
        with use_simulation(state),patch('random.randint',side_effect=AssertionError('host RNG used')):
            self.tech.roll(actor,self.unit,0)
        self.assertEqual(self.tech.rolls[-1]['roll'],sum(dice)-min(dice))
        self.assertEqual(state.mt.int32(),reference.mt.int32())

    def test_payload_and_defined_variable_time_arithmetic(self):
        self.assertEqual(pack(7,4,3,2),459316)
        self.assertEqual(unpack(459316),(7,4,3,2))
        self.assertEqual(variable_minutes(60,2,True,10),50)
        self.assertEqual(variable_minutes(60,0,True,10),60)
        with self.assertRaisesRegex(ValueError,'divisor'):variable_minutes(60,10,True,10)

if __name__=='__main__':unittest.main()
