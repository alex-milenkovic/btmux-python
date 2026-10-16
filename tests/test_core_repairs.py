"""Repair mutations, recomputation and isolation of intact-template replay."""
import unittest
from copy import deepcopy
from entities.mech import Mech, FireMode as F, MechStatus as S, UnitType as U, SectionConfig as C, Specials
from entities.crittypes import i2special, i2weapon, i2ammo, Special
from systems import repairs
from systems.parts import part_mod
from entities.weapon import get_weapon


class RepairsTest(unittest.TestCase):
    def test_repair_first_critical_restores_only_its_weapon_mirror(self):
        from entities.mech import WeaponState
        unit = Mech()
        unit.weapons = [WeaponState(section=4,critical=0,weapon_idx=0,destroyed=True),
                        WeaponState(section=4,critical=1,weapon_idx=0,destroyed=True)]
        for pos in (0,1):
            slot = unit.sections[4].criticals[pos]
            slot.type,slot.firemode = i2weapon(0),F.DESTROYED_MODE
        repairs.repair_part(unit,4,0)
        self.assertFalse(unit.weapons[0].destroyed)
        self.assertTrue(unit.weapons[1].destroyed)
        self.assertTrue(unit.sections[4].criticals[1].firemode & F.DESTROYED_MODE)

    def test_repair_weapon_clears_damage_but_preserves_mount_modes_and_brand(self):
        unit = Mech()
        slot = unit.sections[0].criticals[0]
        slot.type, slot.data, slot.brand, slot.weap_damage_flags = i2weapon(0), 19, 0xA3, 123
        slot.firemode = F.DESTROYED_MODE | F.BROKEN_MODE | F.DISABLED_MODE | F.DAMAGED_MODE | F.HOTLOAD_MODE | F.OS_USED | F.REAR_MOUNT | F.OS_MODE
        repairs.repair_part(unit, 0, 0)
        self.assertEqual((0, 3, 0, F.REAR_MOUNT | F.OS_MODE), (slot.data, slot.brand, slot.weap_damage_flags, slot.firemode))

    def test_refill_does_not_repair_destroyed_bin(self):
        unit = Mech()
        slot = unit.sections[0].criticals[0]
        slot.type, slot.firemode = i2ammo(get_weapon('IS.AC/10').index), F.DESTROYED_MODE | F.HALFTON_MODE
        repairs.fill_part_ammo(unit, 0, 0)
        self.assertEqual(5, slot.data)
        self.assertTrue(slot.firemode & F.DESTROYED_MODE)

    def test_reattach_replace_and_reseal_have_distinct_flood_effects(self):
        unit = Mech()
        section = unit.sections[0]
        section.internal_orig = 10
        section.config = C.SECTION_DESTROYED | C.SECTION_FLOODED
        repairs.replace_suit(unit, 0)
        self.assertEqual((10, C.SECTION_FLOODED), (section.internal, section.config))
        slot = section.criticals[0]
        slot.type, slot.firemode = i2weapon(0), F.DISABLED_MODE | F.BROKEN_MODE
        repairs.reseal(unit, 0)
        self.assertEqual(F.BROKEN_MODE, slot.firemode)
        self.assertEqual(C.NONE, section.config)
        section.internal, section.config = 0, C.SECTION_DESTROYED | C.SECTION_FLOODED
        repairs.reattach(unit, 0)
        self.assertEqual((10, C.NONE), (section.internal, section.config))

    def test_jet_cap_and_partial_double_sink_groups_loud_mode(self):
        unit = Mech(max_speed=64.5, engine_rating=200, num_sinks=10)
        unit.specials = Specials.DOUBLE_HEAT_TECH
        for slot in unit.sections[0].criticals[:3]: slot.type = i2special(Special.HEAT_SINK)
        unit.sections[0].criticals[0].firemode = F.DESTROYED_MODE
        for slot in unit.sections[1].criticals[:4]: slot.type = i2special(Special.JUMP_JET)
        repairs.sub_magic(unit)
        self.assertEqual((43, 18, 18), (unit.jump_speed, unit.effective_heat_sinks, unit.original_sinks))
        unit.specials2 |= 0x80
        repairs.sub_magic(unit)
        self.assertEqual(21.5, unit.jump_speed)
        unit.real_num_sinks = 99
        repairs.sub_magic(unit, loud=True)
        self.assertEqual((99, 18), (unit.effective_heat_sinks, unit.original_sinks))

    def test_missing_template_is_explicit_after_local_repair(self):
        unit = Mech()
        slot = unit.sections[0].criticals[0]
        slot.type, slot.firemode = i2special(Special.ENGINE), F.DESTROYED_MODE
        self.assertFalse(repairs.repair_part(unit, 0, 0))
        self.assertEqual(F.NONE, slot.firemode)
        self.assertTrue(any('template' in str(e).lower() for e in unit.external_effects))

    def test_template_replay_keeps_template_and_unrelated_units_unchanged(self):
        from core.game_loop import GameEngine
        from entities.map import GameMap
        from core.events import EventType as E
        from systems.criticals import apply_critical_to_slot
        unit = Mech.create_test_mech()
        unit.name = 'replay'
        unit.engine_rating = 200
        unit.max_speed = 64.5
        unit.sections[4].criticals[0].type = i2special(Special.ENGINE)
        unit.sections[4].criticals[1].type = i2special(Special.ENGINE)
        unit.sections[7].criticals[0].type = i2special(Special.SENSORS)
        unit.sections[0].criticals[0].type = i2weapon(0)
        template = deepcopy(unit)
        before = deepcopy(vars(template))
        engine, board = GameEngine(), GameMap(12, 12)
        peer = Mech.create_test_mech(name='peer')
        for actor in (unit, peer): board.add_mech(actor); engine.register_entity(actor)
        engine.templates = {'replay': template}
        peer_before = deepcopy(peer.sections)
        apply_critical_to_slot(unit, 4, 0, engine=engine)
        apply_critical_to_slot(unit, 4, 1, engine=engine)
        apply_critical_to_slot(unit, 7, 0, engine=engine)
        unit.engine_rating = 1
        unit.status |= S.PERFORMING_ACTION
        unit.sections[0].criticals[0].firemode = F.OS_MODE | F.OS_USED
        unit.sections[0].config |= C.STABILIZERS_DESTROYED
        unit.sections[0].specials = 0x1E
        engine.events.schedule(2, E.VEHICLE_BURN, lambda event: None, unit)
        self.assertTrue(repairs.repair_part(unit, 4, 0))
        self.assertEqual((200, 5), (unit.engine_size(), unit.engine_heat))
        self.assertEqual(template.lrs_range // 2, unit.lrs_range)
        self.assertEqual(0, unit.sections[0].specials & 0x1E)
        self.assertFalse(unit.sections[0].config & C.STABILIZERS_DESTROYED)
        self.assertEqual(F.OS_MODE, unit.sections[0].criticals[0].firemode)
        self.assertFalse(engine.has_event(E.VEHICLE_BURN, unit))
        self.assertEqual(before, vars(template))
        self.assertEqual(peer_before, peer.sections)
