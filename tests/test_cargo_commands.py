import unittest
from types import SimpleNamespace
from core.game_loop import GameEngine
from data.construction_catalog import source_part
from entities.mech import Mech,MechStatus as S,Specials
from entities.map import GameMap
from systems.economic_inventory import InventoryStore
from systems.cargo_commands import CargoCommands
from systems.vehicle_combat import correct_speed


class CargoCommandTests(unittest.TestCase):
    def setUp(self):
        self.engine=GameEngine();self.store=InventoryStore();self.commands=CargoCommands(self.store)
        self.unit=Mech();self.unit._id=12;self.unit.location=self.unit.mapindex=10;self.unit.map=GameMap(10,10)
        self.unit.map._id=10;self.engine.register_entity(self.unit.map)
        self.unit._engine=self.engine;self.unit.status|=S.STARTED;self.unit.specials|=Specials.CARGO_TECH
        self.unit.measured_mass=self.unit.tonnage*1024;self.unit.in_character=True
        self.actor=SimpleNamespace(_id=7,location=12,wizard=False);self.unit.pilot=self.actor
        self.store.register(10,in_character=False);self.store.register(12,self.unit);self.store.register(7,self.actor)
        self.store.set(10,546,0,5)
    def test_load_and_unload_share_actual_room_and_unit_inventory(self):
        self.commands.command(self.actor,self.unit,'loadcargo','Internal 3')
        self.assertEqual((self.store.find(12,546),self.store.find(10,546)),(3,2))
        self.unit.status&=~S.STARTED;self.unit.speed=12;self.store.put(10,'in_character',True);self.store.put(10,'MECHSKILLS','5 5 1')
        self.commands.command(self.actor,self.unit,'unloadcargo','Internal 2')
        self.assertEqual((self.store.find(12,546),self.store.find(10,546)),(1,4))
    def test_bay_reveals_coordinates_only_with_nonzero_third_number(self):
        self.store.put(10,'MECHSKILLS','5 5 1')
        with self.assertRaisesRegex(ValueError,'5,5'):self.commands.command(self.actor,self.unit,'loadcargo','Internal 1')
        self.store.put(10,'MECHSKILLS','5 5 0')
        with self.assertRaises(ValueError) as error:self.commands.command(self.actor,self.unit,'loadcargo','Internal 1')
        self.assertNotIn('5,5',str(error.exception));self.assertEqual(self.store.find(10,546),5)
    def test_transfer_failure_still_refreshes_weight(self):
        self.unit.carried_cargo=1000
        with self.assertRaises(ValueError):self.commands.command(self.actor,self.unit,'loadcargo','NoSuchItem 1')
        self.assertEqual(self.unit.carried_cargo,0)
    def test_manifest_and_admin_mutations_target_actor_location(self):
        self.actor.location=10;self.actor.wizard=True;self.commands.command(self.actor,self.unit,'Raddstuff','Electric 3')
        self.assertEqual(self.store.find(10,545),3);self.assertEqual(self.store.find(12,545),0)
        self.assertEqual(len(self.commands.command(self.actor,self.unit,'manifest','')['rows']),2)
    def test_correct_speed_uses_previous_weight_once(self):
        self.unit.max_speed=60;self.unit.speed=self.unit.desired_speed=55
        self.unit.tonnage=20;self.unit.measured_mass=20480;self.store.set(12,source_part('Ammo_IS.LRM-15'),0,10)
        correct_speed(self.unit);self.assertEqual(self.unit.speed,55)
        correct_speed(self.unit);self.assertEqual(self.unit.speed,40)
    def test_exact_stationary_gate_precedes_store_transfer(self):
        self.unit.speed=-.1
        with self.assertRaisesRegex(ValueError,'moving'):self.commands.command(self.actor,self.unit,'loadcargo','Internal 1')
        self.assertEqual(self.store.find(10,546),5)

if __name__=='__main__':unittest.main()
