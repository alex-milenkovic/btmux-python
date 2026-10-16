"""Focused regressions from the independent AUD-UTILS repair review."""
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from core.game_loop import GameEngine
from core.randomness import use_source
from entities.crittypes import i2ammo, i2weapon
from entities.mech import Mech, UnitType as U, AmmoMode as A, FireMode as F
from entities.pilot import Pilot
from entities.weapon import get_weapon
from systems import battle_value, economy, heat
from systems.damage import channel_emit_kill


class UtilitiesReviewCorrections(unittest.TestCase):
    def test_fasa_interleaves_section_prices_and_errors_but_bv_collects_first(self):
        engine = GameEngine()
        engine.cost_debug = True
        unit = Mech(tonnage=50, max_speed=0, num_sinks=10)
        unit._id = 10
        engine.register_entity(unit)
        first, broken, last = map(get_weapon, ('IS.SmallLaser', 'IS.AC/5', 'IS.MediumLaser'))
        for loc, weapon in enumerate((first, broken, last)):
            unit.sections[loc].criticals[0].type = i2weapon(weapon.index)
        result = economy.fasa_cost(unit)
        prices = [f'Addprice - {w.name:>25} {w.cost:8.0f}' for w in (first, last)]
        error = f'Error in the numcriticals for weapon on #10! (Should be: {broken.crits}, is: 1)'
        observed = [(r['channel'], r['text']) for r in engine.effects.channels
                    if r['channel'] == 'MechErrors' or r['text'] in prices]
        self.assertEqual([('MechDebugInfo', prices[0]), ('MechErrors', error),
                          ('MechDebugInfo', prices[1])], observed)
        self.assertFalse(any(r['label'] == broken.name for r in result.components))
        engine.effects.channels.clear()
        battle_value.offensive_bv(unit)
        self.assertEqual('MechErrors', engine.effects.channels[0]['channel'])
        self.assertTrue(all(r['channel'] == 'MechDebugInfo' for r in engine.effects.channels[1:]))

    def test_empty_inferno_does_not_raise_live_overheat_risk(self):
        unit = Mech(heat=19)
        inferno, ordinary = unit.sections[0].criticals[:2]
        inferno.type = i2ammo(get_weapon('IS.SRM-6').index)
        inferno.ammomode, inferno.data = A.INFERNO_MODE, 0
        ordinary.type, ordinary.data = i2ammo(get_weapon('IS.AC/5').index), 10
        explosion = SimpleNamespace(damage=1, mech_destroyed=False, pilot_damage=0, message='boom')
        with patch.object(heat, 'BTECH_INFERNO_PENALTY', True), \
             patch.object(heat, 'check_shutdown', return_value=(False, True)), \
             patch.object(heat, 'trigger_heat_ammo_explosion', return_value=explosion) as boom, \
             use_source(lambda name, low, high, default: 5):
            self.assertFalse(heat.check_overheat(unit, tick=30).ammo_explosion)
            boom.assert_not_called()
            inferno.data = 1
            self.assertTrue(heat.check_overheat(unit, tick=60).ammo_explosion)
            boom.assert_called_once_with(unit)

    def test_inferno_presence_keeps_catalog_order_and_positive_damage_guards(self):
        unit = Mech()
        slot = unit.sections[0].criticals[0]
        weapon = get_weapon('IS.SRM-6')
        slot.type, slot.ammomode, slot.data = i2ammo(weapon.index), A.INFERNO_MODE, 0
        with patch('entities.weapon.get_weapon_by_index', return_value=None):
            with self.assertRaisesRegex(ValueError, 'Unsupported ammunition catalog'):
                heat.has_inferno_ammo(unit)
            slot.ammomode = A.NONE
            self.assertFalse(heat.has_inferno_ammo(unit))
            slot.ammomode, slot.firemode = A.INFERNO_MODE, F.DESTROYED_MODE
            self.assertFalse(heat.has_inferno_ammo(unit))
        slot.firemode, slot.data = F.NONE, 1
        slot.type = i2ammo(get_weapon('IS.GaussRifle').index)
        self.assertFalse(heat.has_inferno_ammo(unit))
        slot.type = i2ammo(weapon.index)
        with patch('entities.weapon.get_weapon_by_index', return_value=replace(weapon, damage=0, damage_per_missile=0)):
            self.assertFalse(heat.has_inferno_ammo(unit))
        self.assertTrue(heat.has_inferno_ammo(unit))

    def test_hangar_event_attributes_both_transfers_to_god(self):
        from tools.core_simulation import CoreSession
        from entities.map_objects import MapObject, add_object
        from systems.hangar import enter_base
        from systems.map_transitions import transfer
        session = CoreSession({'maps': [{'name': 'outside', 'id': 100, 'size': [20, 20]},
            {'name': 'inside', 'id': 101, 'size': [20, 20]}],
            'units': [{'name': 'u', 'id': 10}, {'name': 'tow', 'id': 11}],
            'config': {'periodic_updates': False}, 'actions': []})
        unit, cargo = session.units['u'], session.units['tow']
        outside, inside = session.maps['outside'], session.maps['inside']
        add_object(outside, 4, MapObject(x=unit.x, y=unit.y, obj=101))
        add_object(inside, 6, MapObject(x=4, y=4, datac=ord('n')))
        god, commander = Pilot(name='God'), Pilot(name='Commander')
        god._id, commander._id = 1, 77
        session.engine.register_entity(god)
        unit.command_actor = commander
        unit.carrying = cargo._id
        unit.preferred_contact_id, cargo.preferred_contact_id = 'AA', 'BB'
        self.assertTrue(enter_base(unit)['ok'])
        session.engine.run_ticks(18)
        self.assertEqual(['MapIndex changed to 101', 'Your ID: AA', 'Pos changed to 4,4,0',
                          'MapIndex changed to 101', 'Your ID: BB', 'Pos changed to 4,4,0'], god.inbox)
        for moved in (unit, cargo):
            self.assertIs(inside, moved.map)
            self.assertTrue(all(r['recipient'] == 1 and r['applied'] for r in moved.admin_requests))
            self.assertEqual([f"#1 set #{moved._id}'s mapindex to #101.",
                              f"#1 set #{moved._id}'s pos to 4,4,0."],
                             [r['text'] for r in moved.location_requests[-2:]])
            self.assertFalse(any(s.startswith(('MapIndex changed', 'Your ID:'))
                                 for s in getattr(moved.pilot, 'inbox', [])))
        self.assertFalse(getattr(commander, 'inbox', []))
        self.assertTrue(transfer(unit, outside, actor=commander))
        self.assertEqual('MapIndex changed to 100', commander.inbox[-2])
        self.assertEqual(77, unit.admin_requests[-1]['recipient'])
        self.assertEqual(6, len(god.inbox))

    def test_recovered_aerospace_channels_precede_zero_argument_hooks(self):
        for kind in (U.AERO, U.DS, U.SPHEROID_DS):
            for reason in (None, '', 'engine destruction'):
                with self.subTest(kind=kind, reason=reason):
                    engine = GameEngine()
                    unit, attacker = Mech(unit_type=kind), Mech()
                    unit._id, attacker._id = 10, 11
                    unit.template_ref, attacker.template_ref = 'victim-template', 'attacker-template'
                    engine.register_entity(unit)
                    channels = ['MechDebugInfo'] + ([] if kind == U.AERO else ['DSInfo'])
                    observer, calls = Pilot(), []
                    for channel in ('MechDebugInfo', 'MechDeaths', 'DSInfo'):
                        engine.effects.subscribe(channel, observer)
                    def hook(actor, victim, *args):
                        self.assertEqual(channels, [r['channel'] for r in engine.effects.channels])
                        calls.append((actor, victim, args))
                    engine.effects.hooks[(10, 'AMECHDEST')] = hook
                    channel_emit_kill(unit, attacker, reason)
                    self.assertEqual([(attacker, unit, ())], calls)
                    self.assertEqual(['#10 has been killed by #11'] * len(channels), observer.inbox)
                    self.assertTrue(all(r['applied'] for r in unit.channel_requests + unit.hook_requests))

    def test_recovered_hook_uses_positive_ids_and_keeps_unavailable_handler_explicit(self):
        for victim_id, attacker_id in ((0, 11), (-1, 11), (10, 0), (10, -1)):
            with self.subTest(victim_id=victim_id, attacker_id=attacker_id):
                engine = GameEngine()
                unit, attacker = Mech(unit_type=U.AERO), Mech()
                unit._id, attacker._id = victim_id, attacker_id
                engine.register_entity(unit)
                channel_emit_kill(unit, attacker, 'ignored')
                self.assertEqual(1, len(engine.effects.channels))
                self.assertFalse(getattr(unit, 'hook_requests', []))
        engine = GameEngine()
        unit = Mech(unit_type=U.DS)
        unit._id, unit.valid_object = 10, False
        engine.register_entity(unit)
        channel_emit_kill(unit, reason='ignored')
        self.assertEqual(['MechDebugInfo', 'DSInfo'], [r['channel'] for r in engine.effects.channels])
        self.assertEqual([], unit.hook_requests[-1]['args'])
        self.assertFalse(unit.hook_requests[-1]['applied'])
        self.assertEqual('AMECHDEST', unit.external_effects[-1]['operation'])

    def test_general_kill_delivery_preserves_reason_and_validity_contract(self):
        for reason in (None, '', 'test'):
            with self.subTest(reason=reason):
                engine = GameEngine()
                unit, attacker = Mech(), Mech()
                unit._id, attacker._id = 10, 11
                unit.template_ref, attacker.template_ref = 'victim', 'attacker'
                engine.register_entity(unit)
                calls = []
                engine.effects.hooks[(10, 'AMECHDEST')] = lambda actor, victim, *args: calls.append(args)
                channel_emit_kill(unit, attacker, reason)
                self.assertEqual([() if reason is None else (reason,)], calls)
                text = '#10 [victim] has been killed by #11 [attacker]'
                if reason is not None: text += f' ({reason})'
                self.assertEqual([('MechDebugInfo', text), ('MechDeaths', text)],
                                 [(r['channel'], r['text']) for r in engine.effects.channels])
                unit.valid_object = False
                channel_emit_kill(unit, attacker, reason)
                self.assertEqual(1, len(calls))
                before = len(engine.effects.channels)
                channel_emit_kill(unit)
                self.assertEqual(before, len(engine.effects.channels))
