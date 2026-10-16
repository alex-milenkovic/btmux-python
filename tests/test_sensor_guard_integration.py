"""End-to-end regression checks for Sensors review follow-ups R1/R2."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from core.events import EventType
from entities.mech import MechStatus as S, UnitType
from physics import aerospace
from tests.test_communications import CommunicationsFixture


class FlightGuardTests(CommunicationsFixture):
    def test_invalid_map_stops_before_flight_work(self):
        unit, actor = self.a, self.a.pilot
        for kind in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS):
            for landed in (False, True):
                for name in ('takeoff', 'checklz'):
                    with self.subTest(kind=kind, landed=landed, command=name):
                        unit.unit_type = kind
                        unit.pilot = actor
                        unit.status = S.STARTED | (S.LANDED if landed else S.NONE)
                        unit.map, unit.mapindex = None, 4444
                        unit.speed = unit.z = 0
                        actor.inbox, actor.notification_requests = [], []
                        with patch.object(aerospace, 'cargo_max_speed') as speed_check, patch.object(aerospace, 'improper_lz') as lz:
                            if name == 'takeoff':
                                result = aerospace.takeoff(self.engine, unit, caller=actor)
                            else:
                                result = aerospace.checklz(unit, caller=actor)
                        self.assertEqual(result, (False, ''))
                        speed_check.assert_not_called()
                        lz.assert_not_called()
                        self.assertFalse(self.engine.has_event(EventType.TAKEOFF, unit))
                        self.assertEqual(unit.mapindex, -1)
                        refused = kind != UnitType.AERO and not landed
                        self.assertEqual(unit.is_started, refused)
                        outcome = ('No shutdowns in mid-air! Are you suicidal?' if refused else
                                   ('Fighter' if kind == UnitType.AERO else 'Dropship') + ' has been shutdown!')
                        expected = ['You are on an invalid map! Map index reset!', outcome]
                        self.assertEqual(actor.inbox, expected)
                        self.assertEqual([row['message'] for row in actor.notification_requests], expected)


class CommandAdapterTests(unittest.TestCase):
    def test_delivered_speed_and_landing_refusals_are_not_echoed(self):
        from tools.aerospace import AerospaceSession
        from entities.mech import CritStatus
        session = AerospaceSession(self.document([('speed', 'run', 'AERO')], invalid=False))
        unit = session.units['u0']
        actor = unit.command_actor
        for landing in (False, True):
            with self.subTest(landing=landing):
                actor.inbox, actor.notification_requests = [], []
                if landing:
                    unit.clear_crit_status(CritStatus.MECH_STUNNED)
                    unit.clear_status(S.LANDED)
                    unit.speed = unit.desired_speed = 40
                    with patch('physics.aerospace.improper_lz', return_value=1):
                        result = session.command(unit, 'land', '')
                    message = 'This location is no good for landing!'
                else:
                    unit.set_crit_status(CritStatus.MECH_STUNNED)
                    result = session.command(unit, 'speed', 'run')
                    message = 'You cannot move faster than cruise speed while stunned!'
                self.assertIs(result['ok'], False)
                self.assertEqual(message, result['message'])
                self.assertTrue(result['message'].notified)
                self.assertEqual([message], actor.inbox)
                self.assertEqual([message], [row['message'] for row in actor.notification_requests])


    def document(self, commands, *, invalid=True):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        document = dict(
            pilots={'root': root.name + '/people'},
            construction={'root': root.name + '/templates'},
            file_root=root.name + '/maps',
            maps=[dict(name='main', id=1000, size=[30, 30])],
            config={'periodic_updates': False},
            units=[], characters=[], actions=[])
        for i, (name, args, kind) in enumerate(commands):
            unit = dict(name='u' + str(i), id=10 + i, contact_id=chr(65 + i) * 2,
                        character=110 + i, at=[3, 3, 0], started=True,
                        in_character=True, **{'class': kind},
                        movement='BIPED' if kind == 'MECH' else 'FLY',
                        communications={'radio_type': 114})
            if invalid:
                unit['communications']['mapindex'] = 4444
            if kind != 'MECH':
                unit['aerospace'] = dict(landed=True, fuel=1000, max_speed=60)
            document['units'].append(unit)
            document['characters'].append(dict(id=110 + i, name='Pilot ' + str(i),
                                                location=10 + i, connected=True))
            document['actions'].append(dict(op='command', unit=unit['name'], name=name, args=args))
        return document

    def test_cli_invalid_map_failures_have_no_blank_or_followup_output(self):
        radios = [('sendchannel', 'a=hello', 'MECH'), ('radio', 'BB=hello', 'MECH')]
        flights = [('sendchannel', 'a=hello', 'AERO'), ('radio', 'BB=hello', 'AERO'),
                   ('bomb', 'list', 'AERO'), ('enterbay', '', 'AERO'),
                   ('takeoff', '', 'AERO'), ('checklz', '', 'AERO')]
        for module, commands in (('tools.communications', radios), ('tools.aerospace', flights)):
            with self.subTest(module=module):
                document = self.document(commands)
                run = subprocess.run([sys.executable, '-B', '-m', module],
                                     input=json.dumps(document), text=True,
                                     capture_output=True, timeout=30)
                self.assertEqual(run.returncode, 0, run.stderr)
                output = json.loads(run.stdout)
                self.assertEqual(len(output['results']), len(commands))
                for i, ((name, args, kind), result) in enumerate(zip(commands, output['results'])):
                    with self.subTest(module=module, command=name):
                        self.assertIs(result['ok'], False)
                        self.assertEqual(result.get('message', result.get('error')), '')
                        expected = ['You are on an invalid map! Map index reset!',
                                    ('Mech' if kind == 'MECH' else 'Fighter') + ' has been shutdown!']
                        self.assertEqual(output['state']['inboxes'][str(110 + i)], expected)
                        requests = [row['message'] for row in output['state']['external_notification_requests']
                                    if row['recipient'] == 110 + i]
                        self.assertEqual(requests, expected)
                self.assertFalse(any(event['kind'] == 'TAKEOFF' for event in output['state']['events']))

    def test_nonempty_adapter_output_still_reaches_actor_once(self):
        from tools.aerospace import AerospaceSession
        session = AerospaceSession(self.document([('checklz', '', 'AERO')], invalid=False))
        unit = session.units['u0']
        actor = unit.command_actor
        cases = (
            ('setchannelfreq', 'a=17', True, 'Channel A set to 17.'),
            ('bomb', '', False, '(At least) one option required.'),
            ('enterbay', 'AA BB', False, 'Hmm, invalid number of arguments?'),
            ('checklz', '3', False, 'Invalid number of parameters!'),
            ('checklz', '', True, 'The hex (3,3) looks good enough for a landing.'),
        )
        for name, args, ok, message in cases:
            with self.subTest(command=name, args=args):
                actor.inbox, actor.notification_requests = [], []
                result = session.command(unit, name, args)
                self.assertIs(result['ok'], ok)
                self.assertEqual(result.get('message', result.get('error')), message)
                self.assertEqual(actor.inbox, [message])
                self.assertEqual([row['message'] for row in actor.notification_requests], [message])

    def test_existing_common_check_acceptance_examples(self):
        from acceptance.c3_communications import base
        from acceptance.c3_communications.notifications import common_fixture, common_run, common_result
        source = Path('features/c3_communications/notifications.feature').read_text()
        table = source.split('Scenario Outline: Communications audiences 05 - common command checks', 1)[1]
        count = 0
        for line in table.splitlines():
            if not line.strip().startswith('|'):
                continue
            state, expected = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if state == 'state':
                continue
            with self.subTest(state=state):
                world = {}
                base(world, 'notifications')
                common_fixture(world, state)
                common_run(world)
                common_result(world, expected)
            count += 1
        self.assertEqual(count, 13)


if __name__ == '__main__':
    unittest.main()
