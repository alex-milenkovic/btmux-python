import unittest
from entities.mech import Mech,UnitType
from entities.crittypes import i2special,Special
from data.templates import fill_default_criticals_section


class ConstructionCatalogTest(unittest.TestCase):
    def test_source_ids_brand_policy_and_exact_cursor(self):
        from data.construction_catalog import Catalog,source_part,runtime_part
        from entities.weapon import get_weapon
        catalog=Catalog()
        part=source_part('IS.MediumLaser')
        self.assertEqual(79,part)  # Active C rows exclude eight commented-out entries.
        self.assertEqual(get_weapon('IS.MediumLaser').index+1,runtime_part(part))
        self.assertEqual(('ML','MediumLaser','IS.MediumLaser'),catalog.names(part))
        self.assertEqual('Martell.IS.MediumLaser',catalog.names(part,3)[2])
        self.assertEqual('CL.ERLargeLaser',catalog.names(source_part('CL.ERLargeLaser'),3)[2])
        self.assertEqual('IS.MediumLaser',Catalog(parts=False).names(part,3)[2])
        match=catalog.match('vlong','is.mediumlaser',-1)
        self.assertEqual(part,match['source_part_id'])
        self.assertIsNone(catalog.match('vlong','IS.MediumLaser',match['cursor']))
        self.assertIsNone(catalog.match('vlong','IS.*',-1))
        self.assertEqual(part,catalog.match('long','MediumLas?r',-1)['source_part_id'])
        self.assertEqual('#-1 INVALID PART NUMBER',catalog.packed_name(1427,'v'))

    def test_source_helper_ids_and_shared_short_labels(self):
        from data.construction_catalog import weapon_id,legacy_ammo_id
        from systems.damage_commands import short_section
        self.assertEqual((79,179),(weapon_id('IS.MediumLaser'),legacy_ammo_id('Ammo_IS.MediumLaser')))
        self.assertEqual((-1,-1),(weapon_id('not-a-weapon'),legacy_ammo_id('IS.MediumLaser')))
        unit=Mech();unit.unit_type=UnitType.BSUIT
        self.assertEqual('S8',short_section(unit,7))

    def test_ordered_reference_shadows_and_duplicate_match_text(self):
        from data.construction_catalog import Catalog,identify
        self.assertEqual(['Champion','Hatchetman','Thor-',None],
                         [identify(ref) for ref in ('CHP-W5','HCT-3F','Thor','as7-D')])
        catalog=Catalog()
        self.assertEqual('403 403 ',catalog.partmatch('HeatSink'))
        self.assertEqual('#-1 PERMISSION DENIED',catalog.partmatch('HeatSink',wizard=False))
        self.assertEqual('HeatSink',catalog.partname('403suffix','v'))

    def test_aero_defaults_clear_modes_but_preserve_brand_and_damage(self):
        unit=Mech();unit.unit_type=UnitType.AERO
        for slot in unit.sections[5].criticals:
            slot.type=1;slot.data=8;slot.firemode=128;slot.ammomode=1;slot.brand=4;slot.damage=3
        fill_default_criticals_section(unit,5)
        self.assertEqual([i2special(Special.ENGINE) if i in (2,10) else i2special(Special.HEAT_SINK) for i in range(12)],
                         [slot.type for slot in unit.sections[5].criticals])
        self.assertTrue(all((s.data,s.firemode,s.ammomode,s.brand,s.damage)==(0,0,0,4,3) for s in unit.sections[5].criticals))
