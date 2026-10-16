"""Public command status, recipients and historical missile selection."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from core.events import EventType
from entities.mech import UnitType as U, MechStatus as S, Specials, AmmoMode
from entities.weapon import get_weapon
from systems import combat, missile, targeting, tic
from tests.test_damage_review_corrections import WatchingInbox, crew_session


class FiringReviewCorrections(unittest.TestCase):
    def session(self, units=None):
        session = crew_session({'actions': [], **({'units': units} if units else {})})
        session.streams.update(missile_pre_roll=[1, 2, 3] * 30, missile_cluster=[2] * 30,
                               damage_entry=[7] * 100, hit_location_rolls=[7] * 100, swarm_rolls=[12] * 20)
        for unit in session.units.values():
            for section in unit.sections:
                section.armor = section.rear = 200
                section.internal = 100
        return session

    def test_coordinate_confirmation_is_personal_and_precedes_stop_lock(self):
        for mode in ('', ' H'):
            with self.subTest(mode=mode):
                session = self.session()
                unit = session.units['u']
                unit.status |= S.LOCK_BUILDING
                old = session.engine.events.schedule(20, EventType.LOCK, lambda e: None, unit)
                observed = []
                actor = SimpleNamespace(_id=777, inbox=WatchingInbox(lambda text: observed.append((text, unit.targ_x, unit.targ_y, bool(unit.status & S.LOCK_BUILDING), old.zombie))))
                pilot = unit.pilot
                pilot.inbox = []
                ok, message = targeting.lock_command(session.engine, unit, '4 5' + mode, caller=actor, wizard=True)
                self.assertTrue(ok)
                self.assertEqual([(message, 4, 5, True, False)], observed)
                self.assertEqual([], pilot.inbox)
                self.assertTrue(old.zombie)
                self.assertFalse(unit.status & S.LOCK_BUILDING)

    def test_dug_in_uses_firer_in_sight_and_signed_diagnostic(self):
        for kind in (U.MECH, U.AERO):
            with self.subTest(kind=kind):
                session = self.session()
                unit, target = session.units.values()
                unit.unit_type = kind
                unit.prefs |= 512
                weapon = get_weapon('IS.MediumLaser')
                base = combat.calculate_bth(unit, target, weapon, 1, 4).total
                target.tank_crit_status = 4
                self.assertEqual(base, combat.calculate_bth(unit, target, weapon, 1, 4).total)
                target.tank_crit_status = 0
                unit.tank_crit_status = 4
                result = session.invoke(combat.resolve_attack, unit, target, weapon, 1, 4, to_hit_roll=12, sight=True)
                self.assertEqual(base + 3, result.bth)
                diagnostic = next(text for text in reversed(unit.pilot.inbox) if text.startswith('BTHDebug:'))
                self.assertIn('DugIn: +3', diagnostic)
                target.z = -1
                combat.calculate_bth(unit, target, weapon, 1, 4)
                self.assertNotIn('DugIn:', unit.pilot.inbox[-1])

    def test_redirected_host_recomputes_firer_dug_in_bth(self):
        session = self.session([{'name': 'u', 'at': [3, 3, 0]}, {'name': 'v', 'at': [3, 2, 0], 'team': 2},
                                {'name': 'host', 'at': [3, 2, 0], 'team': 2}])
        unit, suit, host = session.units.values()
        unit.tank_crit_status = 4
        unit.target = host._id
        unit.prefs |= 512
        suit.unit_type = U.BSUIT
        suit.swarm_target = host._id
        session.engine.glancing_blows = 0
        result = session.invoke(combat.resolve_attack, unit, suit, get_weapon('IS.MediumLaser'), 1, 4, to_hit_roll=7)
        self.assertEqual((host._id, 8, 7, 5), (result.target_id, result.bth, result.impact_bth, result.damage_dealt))
        self.assertEqual(2, sum('DugIn: +3' in text for text in unit.pilot.inbox))

    def test_tic_acceptance_comes_from_guard_and_selector_status(self):
        for condition in ('shutdown', 'destroyed', 'no-map', 'invalid-map', 'blinded', 'unconscious'):
            with self.subTest(condition=condition):
                session = self.session()
                unit = session.units['u']
                if condition == 'shutdown':unit.clear_status(S.STARTED)
                elif condition == 'destroyed':unit.set_status(S.DESTROYED)
                elif condition == 'no-map':unit.mapindex = -1
                elif condition == 'invalid-map':unit.mapindex = 999999
                elif condition == 'blinded':unit.set_status(S.BLINDED)
                else:unit.set_status(S.UNCONSCIOUS)
                reply = session.action({'op': 'command', 'name': 'firetic', 'args': ['0']})
                self.assertFalse(reply['accepted'])
                self.assertFalse(reply['result'].accepted)
        session = self.session()
        unit = session.units['u']
        unit.set_status(S.BLINDED)
        self.assertFalse(session.action({'op': 'command', 'name': 'listtic', 'args': ['0']})['accepted'])
        unit.clear_status(S.BLINDED)
        unit.in_character = True
        foreign = SimpleNamespace(_id=888)
        self.assertFalse(tic.tic_command(session.engine, unit, 'firetic', '0', caller=foreign).accepted)
        unit.in_character = False
        self.assertTrue(session.action({'op': 'command', 'name': 'firetic', 'args': ['0']})['accepted'])
        self.assertTrue(session.action({'op': 'command', 'name': 'listtic', 'args': ['0']})['accepted'])
        self.assertFalse(session.action({'op': 'command', 'name': 'cleartic', 'args': ['0,99']})['accepted'])
        self.assertFalse(session.action({'op': 'command', 'name': 'addtic', 'args': ['0']})['accepted'])

    def test_direct_nonmissile_calls_leave_live_ams_resources_untouched(self):
        for name in ('IS.AC/10', 'IS.LB10-XAC', 'IS.MediumLaser'):
            for roll in (6, 12):
                with self.subTest(weapon=name, roll=roll):
                    session = self.session([{'name': 'u'}, {'name': 'v', 'at': [3, 2, 0], 'team': 2,
                        'weapons': [{'name': 'IS.Anti-MissileSystem', 'section': 'RT', 'metadata': {'crits': 1}}],
                        'ammo': [{'weapon': 'IS.Anti-MissileSystem', 'rounds': 10}]}])
                    unit, target = session.units.values()
                    target.status |= S.AMS_ENABLED
                    target.specials |= Specials.IS_ANTI_MISSILE_TECH
                    before = (target.heat, tuple(slot.data for section in target.sections for slot in section.criticals))
                    with patch.object(missile, 'locate_ams_defenses', wraps=missile.locate_ams_defenses) as search:
                        result = session.invoke(missile.missile_hit_target, unit, target, get_weapon(name), 4, 0, 7, roll, 10, 7, cluster_roll=2)
                    search.assert_not_called()
                    self.assertEqual(0, result.ams_shot_down)
                    self.assertEqual(before, (target.heat, tuple(slot.data for section in target.sections for slot in section.criticals)))

    def test_historical_rows_follow_incoming_streak_and_exact_tie_rule(self):
        cases = [('IS.MRM-30', 12, 2, 4, 8), ('IS.MRM-40', 30, 4, 16, 14),
                 ('IS.RL-10', 10, 2, 2, 8), ('IS.MRM-10', 10, 2, 3, 7),
                 ('IS.StreakSRM-6', 3, 2, 4, 1)]
        for name, incoming, roll, damage, remaining in cases:
            with self.subTest(name=name):
                session = self.session()
                unit, target = session.units.values()
                unit.unit_type = U.AERO
                result = session.invoke(missile.missile_hit_target, unit, target, get_weapon(name), 4, 0, 7, 12, incoming, 12, cluster_roll=roll)
                self.assertEqual((damage, remaining), (result.damage_dealt, result.missiles_remaining))
        session = self.session()
        unit, target = session.units.values()
        general = session.invoke(missile.missile_hit_target, unit, target, get_weapon('IS.MRM-30'), 4, 0, 7, 12, 12, 12, cluster_roll=2)
        self.assertEqual((10, 2), (general.damage_dealt, general.missiles_remaining))
        unit.unit_type = U.AERO
        with patch.object(missile, 'missile_hit_index') as index:
            empty = session.invoke(missile.missile_hit_target, unit, target, get_weapon('IS.StreakSRM-6'), 4, 0, 7, 12, 1, 12)
        index.assert_not_called()
        self.assertEqual((0, 0), (empty.damage_dealt, empty.missiles_remaining))

    def test_historical_swarm_reselects_row_for_each_remainder(self):
        from systems.los import MECHLOSFLAG_SEESP
        session = self.session([{'name': 'u', 'at': [3, 3, 0]}, {'name': 'v', 'at': [3, 2, 0], 'team': 2},
                                {'name': 'b', 'at': [3, 1, 0], 'team': 2}])
        unit, first, second = session.units.values()
        unit.unit_type = U.AERO
        unit.sections[4].criticals[0].ammomode = AmmoMode.SWARM1_MODE
        session.map.losinfo[(first._id, second._id)] = MECHLOSFLAG_SEESP
        result = session.invoke(missile.swarm_hit_target, unit, first, get_weapon('IS.MRM-30'), 4, 0, 7, 12, 1, True, 12, cluster_roll=2)
        self.assertEqual([first._id, second._id], result.swarm_targets)
        self.assertEqual((16, 14), (result.damage_dealt, result.missiles_remaining))
