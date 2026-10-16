"""Personal combat source arithmetic and character-driven initialization."""
import unittest
from core.randomness import use_source
from data.characters import CharacterStore
from systems.characters import set_value
from entities.mech import Mech, UnitType, CritStatus, Location as L
from entities.weapon import get_weapon
from systems.personal_damage import personal_to_damage, damage_to_personal, personal_armor_effect, initialize_pc


class PersonalCharacterTest(unittest.TestCase):
    def setUp(self):
        self.unit=Mech();self.unit.unit_type=UnitType.MW
        self.store=CharacterStore();self.store.create(101,'Alice')
        self.actor=self.store.actor(101)
        self.pc=get_weapon('PC.SMG');self.seen=[]

    def draws(self,values):
        values=iter(values)
        def draw(name,lo,hi,fallback):
            value=next(values);self.assertTrue(lo<=value<=hi)
            self.seen.append(name);return value
        return use_source(draw)

    def test_conversion_remainder_draw_and_signed_c_division(self):
        self.unit.unit_type=UnitType.MECH
        with self.draws([1,50,51,1]):
            self.assertEqual([2,3,2,-2],[personal_to_damage(self.unit,self.pc,n) for n in (200,250,250,-250)])
        self.assertEqual(4,len(self.seen))
        self.unit.unit_type=UnitType.MW
        with self.draws([80,130]):
            self.assertEqual(210,damage_to_personal(self.unit,None,2))
            self.assertEqual(250,personal_to_damage(self.unit,self.pc,250))
            self.assertEqual(0,damage_to_personal(self.unit,None,-1))

    def test_armor_projection_signed_damage_and_id_minus_two(self):
        self.unit.sections[L.CTORSO].armor=6
        with self.draws([2,1,1]):
            self.assertEqual(-50,personal_armor_effect(self.unit,self.pc,L.LTORSO,-100,id=-2))
        self.assertEqual(['personal_weak_point','personal_half','personal_block'],self.seen)
        self.assertEqual(6,self.unit.sections[L.CTORSO].armor)
        with self.draws([100,1,2,1]):
            with self.assertRaisesRegex(ValueError,'division by zero'):
                personal_armor_effect(self.unit,self.pc,L.CTORSO,0)

    def test_protection_mismatch_and_unknown_armor_keep_luck_draws(self):
        self.unit.sections[L.HEAD].armor=1
        with self.draws([100,2,1]):
            self.assertEqual(100,personal_armor_effect(self.unit,get_weapon('PC.Sword'),L.HEAD,100))
        self.unit.sections[L.HEAD].armor=9
        with self.draws([100,1,1]):
            self.assertEqual(200,personal_armor_effect(self.unit,self.pc,L.HEAD,100))
        self.assertNotIn('personal_block',self.seen)

    def init_stats(self):
        for name,val in dict(Build=5,Reflexes=4,Running=3,Bruise=10,Lethal=10).items():
            set_value(self.store,101,name,val)

    def test_initializer_body_equipment_runtime_inventory_and_idempotence(self):
        self.init_stats();self.store.records[101]['pcequip']='1234 PC.SMG PC.LaserRifle 3 4'
        initialize_pc(self.actor,self.unit)
        self.assertAlmostEqual(14.333333,self.unit.max_speed,places=5)
        self.assertEqual([25,25,29,29,41,29,29,13],[s.internal for s in self.unit.sections])
        self.assertEqual([s.internal for s in self.unit.sections],[s.internal_orig for s in self.unit.sections])
        self.assertEqual([0]*8,[s.armor_orig for s in self.unit.sections])
        self.assertEqual([1,2,3,4],[self.unit.sections[i].armor for i in (7,4,1,6)])
        self.assertEqual([3,4],[self.unit.sections[i].criticals[1].data for i in (1,0)])
        self.assertEqual(2,len(self.unit.weapons))
        self.store.records[101]['pcequip']='invalid'
        initialize_pc(self.actor,self.unit)
        self.assertEqual(2,self.unit.sections[4].armor)

    def test_initializer_partial_equipment_failure_sets_flag_and_keeps_left(self):
        self.init_stats();self.store.records[101]['pcequip']='1234 bad PC.SMG'
        self.assertIn('Invalid PC weapon',initialize_pc(self.actor,self.unit))
        self.assertEqual('MechErrors',self.unit.channel_requests[-1]['source_channel'])
        self.assertTrue(self.unit.has_crit_status(CritStatus.PC_INITIALIZED))
        self.assertEqual(self.pc.index+1,self.unit.sections[L.LARM].criticals[0].type)
        self.assertEqual(self.pc.ammo_per_ton,self.unit.sections[L.LARM].criticals[1].data)
        self.assertEqual(1,len(self.unit.weapons));self.assertEqual(0,self.unit.sections[7].armor)
