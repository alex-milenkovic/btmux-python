"""Missile call boundaries and bounded swarm chains."""
import unittest
from unittest.mock import patch
from tools.combat_resolution import CombatSession
from entities.weapon import get_weapon
from entities.mech import AmmoMode as A,MechStatus as S
from systems import missile as m


class MissileCompletionTest(unittest.TestCase):
    def setUp(self):
        self.s=CombatSession({'actions':[],'units':[{'name':'u','at':[3,3,0]},
            {'name':'v','at':[3,2,0],'team':2},{'name':'b','at':[3,1,0],'team':2}]})
        self.u,self.v,self.b=self.s.units.values()
        self.w=get_weapon('IS.LRM-5')
        self.s.streams.update(missile_pre_roll=[1,2,3]*20,missile_cluster=[2]*20,
            swarm_rolls=[12]*20,damage_entry=[7]*100,hit_location_rolls=[7]*100)
        for unit in self.s.units.values():
            for sec in unit.sections:sec.armor=sec.rear=200;sec.internal=100

    def test_hotload_keeps_source_two_swap_order(self):
        from entities.mech import FireMode as F
        self.u.sections[4].criticals[0].firemode=F.HOTLOAD_MODE
        # C sorts (5,6,1) into (5,1,6), never swapping the first pair again.
        self.assertEqual(4,m.missile_hit_index(self.u,self.w,4,0,self.v,dice=(5,6,1)))

    def test_direct_miss_returns_incoming_and_still_checks_ams(self):
        with patch.object(m,'locate_ams_defenses',return_value=None) as ams:
            result=self.s.invoke(m.missile_hit_target,self.u,self.v,self.w,4,0,7,6,5,6)
            self.assertEqual(5,result.missiles_remaining)
            ams.assert_called_once_with(self.v)
            self.assertEqual([],self.s.draws)

    def test_swarm_uses_roster_order_range_los_and_friend_filter(self):
        from systems.los import MECHLOSFLAG_SEESP
        self.u.map.losinfo[(self.v._id,self.b._id)]=MECHLOSFLAG_SEESP
        self.u.map.losinfo[(self.v._id,self.u._id)]=MECHLOSFLAG_SEESP
        self.assertIs(self.u,m.swarm_next_target(self.u,self.v,[self.v],False))
        self.assertIs(self.b,m.swarm_next_target(self.u,self.v,[self.v],True))
        self.b.status|=S.COMBAT_SAFE
        self.assertIsNone(m.swarm_next_target(self.u,self.v,[self.v],True))

    def test_swarm_chain_ignores_incoming_argument_and_uses_remaining_missiles(self):
        from systems.los import MECHLOSFLAG_SEESP
        self.u.map.losinfo[(self.v._id,self.b._id)]=MECHLOSFLAG_SEESP
        self.u.sections[4].criticals[0].ammomode=A.SWARM1_MODE
        self.s.streams['missile_cluster']=[6,6]
        result=self.s.invoke(m.swarm_hit_target,self.u,self.v,self.w,4,0,7,8,1,True,12)
        self.assertEqual([self.v._id,self.b._id],result.swarm_targets)
        self.assertEqual(5,result.damage_dealt)
        self.assertEqual(0,result.missiles_remaining)

    def test_grouped_hex_hit_preserves_cluster_size(self):
        with patch('systems.combat.hex_hit') as hit:
            self.s.invoke(m.missile_hit,self.u,None,self.w,7,1,5,hit_x=4,hit_y=5)
            self.assertEqual([5,2],[call.args[5] for call in hit.call_args_list])


def missile_miss_document(name='IS.SRM-6', ammo_mode=0):
    """A fired miss with finite attack/failure draws and an unused AMS draw."""
    from entities.mech import Specials
    return {'config': {'periodic_updates': False}, 'random': {'streams': {
        'attack_rolls': [2], 'failure_weapon_chance': [1], 'ams_rolls': [4]}},
        'units': [
            {'name': 'u', 'at': [3, 3, 0],
             'weapons': [{'name': name, 'section': 'CT', 'ammo_mode': int(ammo_mode)}],
             'ammo': [{'weapon': name, 'rounds': 10, 'ammo_mode': int(ammo_mode)}]},
            {'name': 'v', 'at': [3, 2, 0], 'team': 2,
             'status': int(S.STARTED | S.AMS_ENABLED), 'specials': int(Specials.IS_ANTI_MISSILE_TECH),
             'weapons': [{'name': 'IS.Anti-MissileSystem', 'section': 'RT'}],
             'ammo': [{'weapon': 'IS.Anti-MissileSystem', 'rounds': 12}]}],
        'actions': [{'op': 'inspect'}, {'op': 'command', 'name': 'fire', 'args': ['0', '01']},
                    {'op': 'inspect'}]}


class FiredMissileMissTest(unittest.TestCase):
    def test_fired_guard_and_direct_miss_have_distinct_resources_and_notices(self):
        from dataclasses import asdict
        from tests.test_damage_review_corrections import WatchingInbox, crew_session
        cases = [('IS.SRM-6', 0, 4, False), ('IS.SRM-6', A.INFERNO_MODE, 4, False),
                 ('IS.NarcBeacon', 0, 1, True), ('IS.NarcBeacon', A.NARC_MODE, 1, False),
                 ('IS.iNarcBeacon', 0, 1, True), ('IS.iNarcBeacon', A.INARC_HAYWIRE_MODE, 1, True),
                 ('IS.iNarcBeacon', A.INARC_ECM_MODE, 1, True)]
        for name, mode, spent, pod in cases:
            for direct in (False, True):
                with self.subTest(weapon=name, mode=mode, direct=direct):
                    session = crew_session(missile_miss_document(name, mode))
                    unit, target = session.units.values()
                    weapon, ams = get_weapon(name), get_weapon('IS.Anti-MissileSystem')
                    mount, defense = unit.weapons[0], target.weapons[0]
                    armor = [(s.armor, s.rear, s.internal, s.specials) for s in target.sections]
                    observed = []
                    def state():
                        return (target.weap_heat, target.sections[defense.section].criticals[defense.critical].data,
                                target.sections[2].criticals[0].data, unit.weap_heat,
                                unit.sections[mount.section].criticals[mount.critical].data,
                                unit.sections[2].criticals[0].data)
                    original_random = session.random_source
                    def random_source(stream, low, high, fallback):
                        if stream == 'ams_rolls':observed.append(('draw', state()))
                        return original_random(stream, low, high, fallback)
                    ams_notice = 'Your Anti-Missile System activates and shoots at the incoming missiles!'
                    pod_notice = 'Your NARC Beacon flies off into the distance.'
                    def target_notice(text):
                        if text == ams_notice:observed.append(('ams', state()))
                        elif ' has fired a ' in text:observed.append(('firing', state()))
                    target.pilot.inbox = WatchingInbox(target_notice)
                    unit.pilot.inbox = WatchingInbox(lambda text: observed.append(('pod', state())) if text == pod_notice else None)
                    with patch.object(session, 'random_source', side_effect=random_source):
                        if direct:
                            result = session.invoke(m.missile_hit_target, unit, target, weapon,
                                mount.section, mount.critical, 7, 2, 6 if name == 'IS.SRM-6' else 1, 2)
                            attack = asdict(result)
                        else:
                            reply = session.action({'op': 'command', 'name': 'fire', 'args': ['0']})
                            self.assertTrue(reply['accepted'])
                            attack = reply['attack']
                    self.assertFalse(attack['hit'])
                    self.assertEqual((0, 0), (attack['damage_dealt'], attack['ams_shot_down']))
                    self.assertFalse(any(text.startswith('Attack hit!') for text in attack['messages']))
                    self.assertEqual(int(direct), attack['messages'].count(ams_notice))
                    self.assertEqual(int(direct and pod), attack['messages'].count(pod_notice))
                    if direct:
                        expected = [('draw', (ams.heat, ams.vrt, 12, 0, 0, 10)),
                                    ('ams', (ams.heat, ams.vrt, 12-spent, 0, 0, 10))]
                        if pod:expected.append(('pod', expected[-1][1]))
                        self.assertEqual((ams.heat, ams.vrt, 12-spent, 0, 0, 10), state())
                        self.assertEqual(['ams_rolls'], [draw['name'] for draw in session.draws])
                        self.assertEqual({'attack_rolls': [2], 'failure_weapon_chance': [1], 'ams_rolls': []}, session.streams)
                    else:
                        # The target's firing notice precedes the ordinary launcher tail.
                        expected = [('firing', (0, 0, 12, 0, 0, 10))]
                        self.assertEqual((0, 0, 12, weapon.heat, 2*weapon.vrt, 9), state())
                        self.assertEqual(['attack_rolls', 'failure_weapon_chance'], [draw['name'] for draw in session.draws])
                        self.assertEqual({'attack_rolls': [], 'failure_weapon_chance': [], 'ams_rolls': [4]}, session.streams)
                        self.assertTrue(unit.status & S.FIRED)
                    self.assertEqual(expected, observed)
                    self.assertEqual(int(not direct), unit.shots_fired)
                    self.assertEqual(armor, [(s.armor, s.rear, s.internal, s.specials) for s in target.sections])

    def test_miss_abort_and_special_gates_leave_ams_untouched(self):
        from contextlib import ExitStack
        from dataclasses import replace
        from systems import failures
        for gate in ('streak', 'sight', 'impossible', 'dud', 'range', 'catalog', 'mine'):
            with self.subTest(gate=gate), ExitStack() as stack:
                name = 'IS.StreakSRM-2' if gate == 'streak' else 'IS.SRM-6'
                mode = A.MINE_MODE if gate == 'mine' else 0
                session = CombatSession(missile_miss_document(name, mode))
                unit, target = session.units.values()
                if gate == 'impossible':unit.pilot.gunnery = 13
                if gate in ('dud', 'range'):
                    stack.enter_context(patch.object(failures, 'check_weapon_failed', return_value=
                        failures.FailureResult('WEAPON_DUD' if gate == 'dud' else 'RANGE', 100)))
                if gate == 'catalog':
                    weapon = get_weapon(name)
                    session.weapon_overrides[weapon.index] = replace(weapon, name='IS.UnlistedMissile')
                before = (target.weap_heat, tuple(s.data for section in target.sections for s in section.criticals))
                reply = session.action({'op': 'command', 'name': 'sight' if gate == 'sight' else 'fire', 'args': ['0']})
                attack = reply['attack']
                self.assertTrue(reply['accepted'])
                self.assertFalse(attack['hit'])
                self.assertEqual(0, attack['damage_dealt'])
                self.assertEqual(before, (target.weap_heat, tuple(s.data for section in target.sections for s in section.criticals)))
                self.assertEqual([4], session.streams['ams_rolls'])
                self.assertFalse(any('Anti-Missile System activates' in text for text in attack['messages']))
                if gate == 'streak':self.assertTrue(attack['streak_lock_failed'])
                elif gate == 'impossible':self.assertTrue(attack['roll_impossible'])
                elif gate == 'dud':self.assertTrue(attack['shot_aborted'])
                elif gate == 'range':self.assertFalse(attack['range_ok'])

    def test_swarm_firing_miss_stops_before_chain_and_hit_still_dispatches(self):
        from systems.combat import resolve_attack
        from systems.los import MECHLOSFLAG_SEESP
        for mode in (A.SWARM_MODE, A.SWARM1_MODE):
            for roll in (2, 12):
                with self.subTest(mode=mode, roll=roll):
                    session = CombatSession({'actions': [], 'units': [
                        {'name': 'u', 'at': [3, 3, 0]}, {'name': 'v', 'at': [3, 2, 0], 'team': 2},
                        {'name': 'b', 'at': [3, 1, 0], 'team': 2}]})
                    unit, first, second = session.units.values()
                    unit.status |= S.COMBAT_SAFE
                    unit.sections[4].criticals[0].ammomode = mode
                    session.map.losinfo[(first._id, second._id)] = MECHLOSFLAG_SEESP
                    session.streams.update(swarm_rolls=[12], hit_location_rolls=[7], damage_entry=[7])
                    before = [(s.armor, s.rear, s.internal) for s in first.sections]
                    second_before = [(s.armor, s.rear, s.internal) for s in second.sections]
                    with patch.object(m, 'locate_ams_defenses') as ams, \
                            patch.object(m, 'swarm_hit_target', wraps=m.swarm_hit_target) as dispatch:
                        result = session.invoke(resolve_attack, unit, first, get_weapon('IS.LRM-5'), 7, 7,
                            to_hit_roll=roll, w_section=4, w_critical=0, w_ammo_mode=mode, cluster_roll=12)
                    if roll == 2:
                        self.assertFalse(result.hit)
                        dispatch.assert_not_called()
                        self.assertEqual([], result.swarm_targets)
                        self.assertEqual(0, result.damage_dealt)
                        self.assertEqual(before, [(s.armor, s.rear, s.internal) for s in first.sections])
                        self.assertEqual([], session.draws)
                        self.assertEqual([7], session.streams['hit_location_rolls'])
                        self.assertEqual([7], session.streams['damage_entry'])
                    else:
                        self.assertTrue(result.hit)
                        dispatch.assert_called_once()
                        self.assertEqual((result.bth, result.bth+1), dispatch.call_args.args[5:7])
                        self.assertEqual(roll, dispatch.call_args.args[9])
                        self.assertEqual([first._id], result.swarm_targets)
                        self.assertEqual((5, 0), (result.damage_dealt, result.missiles_remaining))
                        self.assertEqual(5, sum(a+r for a,r,_ in before)-sum(s.armor+s.rear for s in first.sections))
                    self.assertEqual(second_before, [(s.armor, s.rear, s.internal) for s in second.sections])
                    self.assertEqual([12], session.streams['swarm_rolls'])
                    ams.assert_not_called()

    def test_missed_salvo_and_pod_through_public_stdio(self):
        from tests.test_core_cli import execute
        for name in ('IS.SRM-6', 'IS.NarcBeacon'):
            with self.subTest(weapon=name):
                process, response = execute(missile_miss_document(name))
                self.assertEqual(0, process.returncode, process.stderr)
                self.assertEqual('', process.stderr)
                before, reply, after = response['results']
                self.assertTrue(reply['accepted'])
                self.assertFalse(reply['attack']['hit'])
                self.assertEqual(0, reply['attack']['damage_dealt'])
                target = after['units']['v']
                self.assertEqual(12, target['sections'][2]['slots'][0]['data'])
                self.assertEqual(0, target['weap_heat'])
                self.assertEqual(0, target['sections'][3]['slots'][0]['data'])
                self.assertFalse(any('Anti-Missile System activates' in text or 'flies off' in text for text in reply['attack']['messages']))
                self.assertEqual(9, after['units']['u']['sections'][2]['slots'][0]['data'])
                self.assertEqual([(s['armor'], s['rear'], s['internal'], s['specials']) for s in before['units']['v']['sections']],
                                 [(s['armor'], s['rear'], s['internal'], s['specials']) for s in target['sections']])
                self.assertEqual(['attack_rolls', 'failure_weapon_chance'],
                                 [draw['name'] for draw in response['draws']])
                self.assertEqual(after, response['state'])
