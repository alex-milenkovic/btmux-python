import unittest
from entities.mech import Mech,UnitType as U,MoveType as M,Specials as S,FireMode as F,AmmoMode as A
from entities.crittypes import i2ammo
from entities.weapon import get_weapon


def minimal():
    unit=Mech();unit.tonnage=50;unit.engine_rating=200;unit.original_sinks=10
    for s,n in zip(unit.sections,(10,10,15,15,20,10,10,10)):
        s.internal=s.internal_orig=n;s.armor=s.armor_orig=s.rear=s.rear_orig=0
        for slot in s.criticals:slot.type=0
    return unit


class ConstructionWeightTest(unittest.TestCase):
    def test_live_cargo_uses_construction_mass_and_recomputes_after_consumption(self):
        from physics.cargo import cargo_max_speed
        unit=minimal();unit.construction_managed=True;unit.max_speed=64.5;unit.measured_mass=None
        unit.carried_cargo=40*1024
        slot=unit.sections[0].criticals[0];slot.type=i2ammo(get_weapon('IS.AC/5').index);slot.data=20
        before=cargo_max_speed(unit)
        self.assertGreater(before,0);self.assertLess(before,64.5)
        mass=unit.rtons
        from systems.combat_ammunition import expenditure_check
        expenditure_check(unit,get_weapon('IS.AC/5').index,20)
        slot.data=0
        self.assertGreater(cargo_max_speed(unit),before);self.assertEqual(mass-1024,unit.rtons)
        unit.construction_dynspeed=False
        from physics.cargo import CACHE_FLAGS
        unit.clear_crit_status(CACHE_FLAGS)
        cargo_max_speed(unit);self.assertEqual(50*1024,unit.rtons)

    def test_internals_correct_originals_but_retain_existing_damage(self):
        from systems.construction_weight import internal_check
        unit=minimal();unit.sections[0].internal_orig=8;unit.sections[0].internal=2
        internal_check(unit)
        self.assertEqual((8,2),(unit.sections[0].internal_orig,unit.sections[0].internal))
        self.assertEqual(16,unit.sections[4].internal_orig)
        unit.move_type=M.QUAD;internal_check(unit)
        self.assertEqual((12,12),(unit.sections[0].internal_orig,unit.sections[0].internal))

    def test_engine_priority_and_source_rounding(self):
        from systems.construction_weight import engine_weight
        unit=minimal()
        for flags,expected in ((0,8704),(S.XL_TECH,4608),(S.XXL_TECH,3072),(S.LE_TECH,6656),
                               (S.CE_TECH,13312),(S.ICE_TECH|S.XL_TECH,17408)):
            unit.specials=flags;self.assertEqual(expected,engine_weight(unit))
        unit.specials=0;unit.unit_type=U.VEH_GROUND;unit.move_type=M.WHEEL;unit.engine_rating=220
        self.assertEqual(13312,engine_weight(unit))

    def test_total_current_armor_and_destroyed_center_gyro_quirk(self):
        from systems.construction_weight import weight
        unit=minimal();self.assertEqual(18944,weight(unit,0)['total'])
        unit.sections[0].armor_orig=17;unit.sections[0].armor=1
        self.assertEqual(1536,weight(unit,0)['terms']['armor'])
        self.assertEqual(512,weight(unit,-1)['terms']['armor'])
        unit.sections[4].internal=0
        self.assertEqual(-1024,weight(unit,-1)['terms']['gyro'])

    def test_ammo_design_caseless_truncates_each_addition_and_cache_observes_consumption(self):
        from systems.construction_weight import weight,get_weight
        unit=minimal();unit.construction_managed=True
        for slot in unit.sections[0].criticals[:2]:
            slot.type=i2ammo(get_weapon('IS.AC/5').index);slot.data=40;slot.ammomode=A.AC_CASELESS_MODE
        self.assertEqual(0,weight(unit,0)['terms'].get('equipment',0))
        self.assertEqual(4096,weight(unit,-1)['terms']['ammunition'])
        before=get_weight(unit);unit.sections[0].criticals[0].data-=1
        self.assertEqual(before-52,get_weight(unit))

    def test_vehicle_destroyed_frame_and_hover_minimum(self):
        from systems.construction_weight import weight
        unit=minimal();unit.unit_type=U.VEH_GROUND;unit.move_type=M.HOVER;unit.engine_rating=235;unit.num_sinks=0
        for s in unit.sections:s.internal=s.internal_orig=0
        unit.sections[2].internal=unit.sections[2].internal_orig=5
        self.assertEqual(23040,weight(unit,0)['total'])
        unit.sections[2].internal=0
        self.assertEqual(5120,weight(unit,0)['total']);self.assertEqual(1,weight(unit,-1)['total'])
