"""Shared part quantities, source list formatting, and mobility predicates."""
import unittest
from entities.mech import Mech, FireMode as F, SectionConfig as C, UnitType as U, MoveType as M, Specials as S
from entities.crittypes import Special, i2special, i2weapon, i2ammo
from systems import parts


class PartsTest(unittest.TestCase):
    def test_signed_rounding_and_tolerance(self):
        self.assertEqual([0, 0, 512, 512, 512, 1024], [parts.round_to_halfton(v) for v in (-1, 1, 2, 512, 513, 514)])
        self.assertEqual(-512, parts.round_to_halfton(-513))
        self.assertEqual(768, parts.round_to_quarterton(514))

    def test_totals_rear_and_unclamped_percentages(self):
        unit = Mech()
        unit.sections[0].armor_orig, unit.sections[0].rear_orig = 2, 1
        unit.sections[0].armor, unit.sections[0].rear = 1, 1
        self.assertEqual((2, 66), (parts.armorpoints(unit), parts.remaining_armor_percent(unit)))
        unit.sections[0].internal_orig, unit.sections[0].internal = 10, 11
        self.assertEqual((11, 110), (parts.intpoints(unit), parts.remaining_internal_percent(unit)))

    def test_live_breached_flooded_legs_and_nonmech(self):
        unit = Mech.create_test_mech()
        unit.sections[5].config |= C.SECTION_BREACHED
        unit.sections[6].config |= C.SECTION_FLOODED
        self.assertEqual(2, parts.count_destroyed_legs(unit))
        self.assertTrue(parts.is_mech_legless(unit))
        unit.move_type = M.QUAD
        self.assertFalse(parts.is_mech_legless(unit))
        unit.unit_type = U.VEH_GROUND
        self.assertEqual(0, parts.count_destroyed_legs(unit))

    def test_part_list_uses_runs_and_keeps_original_separators(self):
        unit = Mech()
        slots = unit.sections[0].criticals
        slots[0].type, slots[0].firemode = i2weapon(0), F.DESTROYED_MODE
        slots[1].type, slots[1].firemode = i2weapon(0), F.BROKEN_MODE
        slots[2].type = i2special(Special.ENGINE)
        slots[3].type = i2special(Special.UPPER_ACTUATOR)
        slots[4].type = i2special(Special.ENDO_STEEL)
        slots[5].type = i2ammo(0)  # Energy ammo has no source part name.
        unit.sections[0].armor, unit.sections[0].internal = 5, 3
        expected = 'ARMOR:5|INTERNAL:3|#-1 INVALID PART NUMBER:1|Engine:1||Actuator:1'
        self.assertEqual(expected, parts.unit_parts_list(unit))
        self.assertEqual(expected, parts.unit_parts_list(unit, -1))
        slots[2].firemode = F.DESTROYED_MODE
        self.assertEqual('|Actuator:1', parts.partlist(unit))

    def test_weight_tables_preserve_source_index_mismatches(self):
        self.assertEqual(512, parts.part_weight(i2weapon(0)))
        self.assertEqual(1024, parts.part_weight(i2ammo(0)))
        self.assertEqual(1020, parts.part_weight(385))
        self.assertEqual(1024, parts.part_weight(i2special(Special.SUPERCHARGER)))
        with self.assertRaisesRegex(ValueError, 'weight table'):
            parts.part_weight(i2special(Special.SPLIT_CRIT_LEFT))
        self.assertEqual(102, parts.part_weight(i2special(Special.SPLIT_CRIT_LEFT), tables=False))

    def test_source_names_and_uppercase_only_first_character(self):
        unit = Mech(unit_type=U.SPHEROID_DS, contact_id='Ab')
        self.assertEqual('aerofighter', parts.mechtypename(unit))
        self.assertEqual('ab', parts.mech_ids(unit, True))
        self.assertEqual('**', parts.mech_ids(None))
        self.assertEqual('Hello world', parts.my_to_upper('hello world'))
        unit.unit_type = U.VEH_GROUND
        self.assertEqual('Invalid!!', parts.armor_string(unit, 5))
        self.assertEqual('Rotor', parts.section_strings(unit)[5])

    def test_startup_cargo_recomputation_reads_real_inventory_and_mounted_tanks(self):
        from systems.startup import complete_startup
        from tests.test_core_startup import fixture
        engine, unit, actor = fixture(U.AERO)
        unit.pilot = actor
        unit.cargo_inventory = [(385, 0, 2)]
        unit.sections[0].criticals[0].type = i2special(Special.FUELTANK)
        unit.fuel_orig, unit.fuel = 1000, 1200
        complete_startup(engine, unit)
        self.assertEqual(3000, unit.fuel_max)
        self.assertEqual(8 * 1020 + 102 + 200, unit.carried_cargo)

    def test_repair_materials_share_source_priorities_and_size_families(self):
        # Numeric expectations from compiled mech.utils.c, not cargo labels.
        unit = Mech(tonnage=11, engine_rating=101)
        self.assertEqual((1, 5, 1), tuple(parts.part_mod(unit, kind) for kind in (i2special(Special.GYRO), i2special(Special.ENGINE), 0)))
        unit.specials = S.XL_TECH | S.ICE_TECH | S.FF_TECH | S.HARDA_TECH
        self.assertEqual('FF_Armor', parts.part_name(parts.proper_armor(unit)))
        self.assertEqual(814, parts.alias_part(unit, i2special(Special.ENGINE), 0, True))
        self.assertEqual(730, parts.alias_part(unit, i2special(Special.SHOULDER_OR_HIP), 0, True))
        unit.move_type = M.QUAD
        self.assertEqual(760, parts.alias_part(unit, i2special(Special.SHOULDER_OR_HIP), 0, True))
        self.assertEqual('Actuator', parts.part_name(parts.alias_part(unit, i2special(Special.SHOULDER_OR_HIP), 0, False)))
        unit.specials |= S.ES_TECH | S.REINFI_TECH
        self.assertEqual(710, parts.proper_internal(unit, True))
        self.assertEqual('ES_Internal', parts.part_name(parts.proper_internal(unit, False)))
