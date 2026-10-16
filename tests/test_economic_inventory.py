"""Source storage semantics, shared cargo and local persistence."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from data.construction_catalog import Catalog,source_part,runtime_part
from entities.crittypes import i2special,Special
from entities.mech import Mech,UnitType as U,CritStatus
from systems.economic_inventory import InventoryStore
from systems.parts import set_cargo_weight


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.store=InventoryStore(Catalog());self.store.register(10)
        self.a=source_part('Internal');self.b=source_part('Electric')

    def test_first_duplicate_moves_to_end_and_find_does_not_sum(self):
        self.store.set_raw(10,f'[{self.a},0,2],[{self.a},0,5]')
        self.assertEqual(self.store.find(10,self.a),2)
        self.store.change(10,self.a,0,1)
        self.assertEqual(self.store.raw(10),f'[{self.a},0,5],[{self.a},0,3]')
        self.assertEqual(self.store.aggregate(10)[self.a,0],8)

    def test_noop_set_absent_debit_and_invalid_object_do_not_write(self):
        self.store.change(10,self.a,0,2);before=len(self.store.writes)
        self.store.set(10,self.a,0,2);self.store.change(10,self.b,0,-1)
        self.store.change(999,self.a,0,3)
        self.assertEqual(len(self.store.writes),before)

    def test_malformed_record_removal_keeps_original_bytes(self):
        raw=f'[{self.a},0,2';self.store.set_raw(10,raw)
        self.store.remove(10,self.a,0);self.assertEqual(self.store.raw(10),raw)
        self.store.change(10,self.a,0,1);self.assertEqual(self.store.raw(10),raw)

    def test_brand_normalization_and_actuator_redirection(self):
        self.store.change(10,self.a,2,3)
        self.assertEqual(self.store.raw(10),f'[{self.a},0,3]')
        actuator=i2special(Special.SHOULDER_OR_HIP)
        self.store.set_raw(10,f'[{actuator},0,2]')
        self.store.change(10,actuator,0,1)
        self.assertEqual(self.store.find(10,actuator),0)
        self.assertEqual(self.store.find(10,source_part('Actuator')),3)

    def test_resource_costs_are_atomic(self):
        self.store.change(10,self.a,0,5)
        with self.assertRaisesRegex(ValueError,'Not enough units of Electric in store! You need to have at least 2'):
            self.store.consume(10,[(self.a,0,3),(self.b,0,2)])
        self.assertEqual(self.store.find(10,self.a),5)

    def test_inventory_survives_new_store_and_drives_cargo(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'objects.json';store=InventoryStore(Catalog(),path)
            u=Mech();u._id=10;u.unit_type=U.AERO;u.fuel=u.fuel_orig=100
            store.register(10,u);store.change(10,source_part('Ammo_IS.LRM-15'),0,2)
            store.change(10,source_part('Fuel_Tank'),0,2)
            restored=InventoryStore(Catalog(),path);restored.register(10,u)
            self.assertEqual(restored.find(10,source_part('Fuel_Tank')),2)
            self.assertGreaterEqual(set_cargo_weight(u),2048)
            self.assertEqual(u.fuel_max,4100)
            self.assertFalse(u.crit_status&CritStatus.LOAD_OK)

if __name__=='__main__':unittest.main()
