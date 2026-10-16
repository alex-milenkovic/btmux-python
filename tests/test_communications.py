"""Source communication audiences and command-created network behavior."""
import unittest

from core.game_loop import GameEngine
from data.characters import CharacterStore
from entities.map import GameMap
from entities.mech import Mech, MechStatus as S, Specials, CritStatus as C
from systems.occupants import Personnel


class CommunicationsFixture(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.board = GameMap(30, 30)
        self.board._id = 1000
        self.engine.register_entity(self.board)
        self.store = CharacterStore()
        self.world = Personnel(self.engine, self.store)
        self.units = [self.make_unit(i, name) for i, name in enumerate('ABC', 10)]
        self.a, self.b, self.c = self.units

    def make_unit(self, ident, name):
        unit = Mech.create_test_mech()
        unit._id = ident
        unit.name = name
        unit.contact_id = name * 2
        unit.team = 1
        unit.status = S.STARTED
        unit.specials = Specials.C3_SLAVE_TECH
        unit.specials2 = 0x20
        unit.working_c3_masters = 1 if name == 'A' else 0
        unit.in_character = True
        unit.x = unit.y = 3
        from physics.hexmath import hex_to_float
        unit.fx, unit.fy = hex_to_float(3, 3)
        self.board.add_mech(unit)
        unit.mapindex = self.board._id
        self.engine.register_entity(unit)
        self.world.add(unit, self.board._id)
        self.store.create(ident + 100, name + ' pilot', location=ident)
        unit.pilot = self.store.actor(ident + 100)
        self.world.add(unit.pilot, ident)
        # Real source LOS cache identifies contacts in both sensors.
        from systems.los import MECHLOSFLAG_SEESP, MECHLOSFLAG_SEESS
        for other in self.board.mechs_on_map:
            self.board.losinfo[unit._id, other._id] = MECHLOSFLAG_SEESP | MECHLOSFLAG_SEESS
            self.board.losinfo[other._id, unit._id] = MECHLOSFLAG_SEESP | MECHLOSFLAG_SEESS
        return unit


class NotificationTest(CommunicationsFixture):
    def test_pilot_all_started_and_physical_location(self):
        from systems.notifications import mech_notify, MECHPILOT, MECHALL, MECHSTARTED
        self.store.create(300, 'Passenger', location=self.a._id)
        passenger = self.store.actor(300)
        self.world.add(passenger, self.a._id)
        mech_notify(self.a, MECHPILOT, 'pilot')
        mech_notify(self.a, MECHALL, 'all')
        self.a.status = S.DESTROYED | S.STARTED
        mech_notify(self.a, MECHALL, 'blocked')
        mech_notify(self.a, MECHSTARTED, 'started')
        mech_notify(self.a, MECHPILOT, 'direct despite destroyed')
        self.assertEqual(['pilot', 'all', 'started', 'direct despite destroyed'], self.a.pilot.inbox)
        self.assertEqual(['all', 'started'], passenger.inbox)
        self.world.move(self.a.pilot._id, self.b._id)
        self.a.status = S.NONE
        mech_notify(self.a, MECHPILOT, 'fallback')
        self.assertEqual('fallback', passenger.inbox[-1])
        self.assertNotIn('fallback', self.a.pilot.inbox)

    def test_suppression_and_turret_audience(self):
        from systems.notifications import mech_notify, MECHALL
        self.a.aero_turrets = [self.b._id]
        self.engine.arc_override = 1
        for flag in (S.UNCONSCIOUS, S.BLINDED):
            self.a.status = flag
            self.assertEqual([], mech_notify(self.a, MECHALL, 'suppressed'))
        self.a.status = S.STARTED
        self.assertEqual([110, 111], mech_notify(self.a, MECHALL, 'turrets'))
        self.assertEqual(['turrets'], self.b.pilot.inbox)

    def test_common_flags_passenger_and_invalid_map_shutdown(self):
        from systems.communications import common_checks, MECH_USUAL, MECH_USUALO
        self.a.status |= S.UNCONSCIOUS
        self.assertIsNone(common_checks(self.a, self.b.pilot, MECH_USUAL))
        self.assertIn('only the pilot', common_checks(self.a, self.b.pilot, MECH_USUALO))
        self.assertIn('unconscious', common_checks(self.a, self.a.pilot, MECH_USUAL))
        self.a.status = S.STARTED
        self.a.map = None
        self.a.mapindex = 9999
        actor = self.a.pilot
        self.assertEqual('', common_checks(self.a, actor, MECH_USUAL))
        self.assertEqual(actor.inbox[0], 'You are on an invalid map! Map index reset!')
        self.assertEqual(-1, self.a.mapindex)
        self.assertFalse(self.a.is_started)


class NetworkTest(CommunicationsFixture):
    def test_long_network_message_truncates_each_recipient_frame(self):
        from systems import c3
        for ordinary in (True, False):
            with self.subTest(ordinary=ordinary):
                self.assertTrue(c3.command(self.b, self.b.pilot, 'join', 'AA', ordinary=ordinary)['ok'])
                kind = 'C3' if ordinary else 'C3i'
                message = 'x' * 16382
                self.assertTrue(c3.command(self.a, self.a.pilot, 'message', message, ordinary=ordinary)['ok'])
                self.assertEqual((f'%ch{kind}/A [AA]: ' + message + '%cn')[:16383], self.b.pilot.inbox[-1])
                self.assertEqual((f'%ch{kind}/You: ' + message + '%cn')[:16383], self.a.pilot.inbox[-1])

    def test_real_join_order_message_and_leave(self):
        from systems import c3
        self.assertTrue(c3.command(self.b, self.b.pilot, 'join', 'AA', ordinary=False)['ok'])
        self.assertTrue(c3.command(self.c, self.c.pilot, 'join', 'BB', ordinary=False)['ok'])
        self.assertEqual([[11, 12], [10, 12], [11, 10]], [u.c3i_network for u in self.units])
        result = c3.command(self.b, self.b.pilot, 'message', '   hello', ordinary=False)
        self.assertTrue(result['ok'])
        self.assertEqual('%chC3i/B [BB]: hello%cn', self.a.pilot.inbox[-1])
        self.assertEqual('%chC3i/You: hello%cn', self.b.pilot.inbox[-1])
        c3.command(self.b, self.b.pilot, 'join', '-', ordinary=False)
        self.assertEqual([[12], [], [10]], [u.c3i_network for u in self.units])

    def test_stored_and_temporary_gates_are_independent(self):
        from systems import c3
        for state, targeting, messaging in ((S.NONE, False, False), (S.STARTED | S.UNCONSCIOUS, True, False), (S.STARTED | S.BLINDED, True, True)):
            self.b.status = state
            self.a.c3i_network = [11]
            self.a.c3i_network_size = 1
            c3.validate(self.a, False)
            self.assertEqual([11], self.a.c3i_network)
            self.assertEqual([11] if targeting else [], c3.temporary(self.a, False, True, True, False))
            self.assertEqual([11] if messaging else [], c3.temporary(self.a, False, True, True, True))

    def test_negative_prefix_does_not_repair_peers_and_holes_compact(self):
        from systems import c3
        self.a.c3i_network = [11, -1, 12]
        self.b.c3i_network = [10]
        self.a.c3i_network_size = -1
        c3.validate(self.a, False)
        self.assertEqual([], self.a.c3i_network)
        self.assertEqual([10], self.b.c3i_network)
        self.a.c3i_network = [11, -1, 12]
        self.a.c3i_network_size = 3
        c3.validate(self.a, False)
        self.assertEqual([11, 12], self.a.c3i_network)
        self.a.c3i_network = [11, 11]
        self.a.c3i_network_size = 2
        c3.validate(self.a, False)
        self.assertEqual([11, 11], self.a.c3i_network)

    def test_critical_clears_integer_peers(self):
        from systems import c3
        from systems.criticals import linked_equipment_critical, EquipmentType
        c3.add(self.a, self.b, False)
        linked_equipment_critical(self.b, 0, 0, EquipmentType.C3I)
        self.assertEqual([], self.a.c3i_network)
        self.assertEqual([], self.b.c3i_network)

    def test_head_window_reads_allocated_slots_beyond_location_count(self):
        from systems.c3 import part_of_working_master
        from entities.crittypes import i2special, Special
        from entities.mech import Location, FireMode
        for section in self.a.sections:
            for slot in section.criticals: slot.type = slot.firemode = 0
        self.a.sections[Location.HEAD].criticals[4].type = i2special(Special.C3_MASTER)
        self.assertTrue(part_of_working_master(self.a, Location.HEAD, 4))
        self.a.sections[Location.HEAD].criticals[7].firemode = FireMode.DESTROYED_MODE
        self.assertFalse(part_of_working_master(self.a, Location.HEAD, 4))


class RadioConfigurationTest(CommunicationsFixture):
    def test_frequency_prefix_and_exact_zero(self):
        from systems.communications import set_frequency
        self.a.radio_type = 114
        for argument, expected in (('a=0', 0), ('A=123tail', 123), (' b = 999999', 999999)):
            result = set_frequency(self.a, argument)
            self.assertTrue(result['ok'], result)
            self.assertEqual(expected, self.a.freq[0 if argument[0] != ' ' else 1])
        for argument in ('a=00', 'a=0x1', 'a=-1', 'a=1000000', 'c=17', 'a17', 'a=', ''):
            self.assertFalse(set_frequency(self.a, argument)['ok'], argument)

    def test_mode_prefix_capabilities_title_and_color_buffer(self):
        from systems.communications import set_mode, set_title, color_code
        self.a.radio_type = 114
        for text, expected in (('DIUES', 31), ('Drg', 97), ('DX', 289), ('D?S', 1), ('?D', 0)):
            self.assertTrue(set_mode(self.a, 'a=' + text)['ok'])
            self.assertEqual(expected, self.a.freqmodes[0])
        self.a.freqmodes[0] = 1
        self.assertFalse(set_mode(self.a, 'a=E')['ok'])
        self.assertEqual(1, self.a.freqmodes[0])
        result = set_title(self.a, 'a= 1234567890123456')
        self.assertEqual('123456789012345', self.a.chantitle[0])
        self.assertIn('set to set to 1234567890123456', result['message'])
        result = set_title(self.a, 'a=' + 'x' * 16382)
        self.assertEqual('x' * 15, self.a.chantitle[0])
        self.assertEqual(('Channel A title set to set to ' + 'x' * 16382 + '.')[:16383], result['message'])
        set_mode(self.a, 'a=r')
        self.assertEqual('%cr', color_code(self.a, 0))
        self.assertEqual('%cr', color_code(self.a, 0, observer=True, team=0))
        set_mode(self.a, 'a=X')
        self.assertEqual('%ch%c', color_code(self.a, 0))

    def test_parser_retains_empty_tokens_and_channel_Z_quirk(self):
        from systems.communications import parse_attributes, parse_channel_send
        self.a.radio_type = 114
        self.assertEqual(['a', '=', ' hello'], parse_attributes('a= hello'))
        self.assertEqual(['', 'a', '=hello'], parse_attributes(' a=hello'))
        for text in ('Z=hello', 'a=hello', '0 ignored hello'):
            self.assertEqual((0, 'hello'), parse_channel_send(self.a, text))
        with self.assertRaises(ValueError): parse_channel_send(self.a, 'A=hello')

    def test_relay_directed_edges_equal_paths_and_recursive_difference(self):
        from systems.communications import find_comm_link, route_graph
        from physics.hexmath import SCALEMAP
        for u, x in zip(self.units, (0, 5, 10)):
            u.fx, u.fy, u.fz = x * SCALEMAP, 0, 0
            u.radio_type = 114
            u.freq, u.freqmodes, u.chantitle = [17, 0], [5, 0], ['', '']
            u.radio_range = 5
        result = find_comm_link(self.board, self.a, self.c, 17)
        self.assertEqual([10, 11], result['path'])
        self.b.radio_range = 1
        self.assertIsNone(find_comm_link(self.board, self.a, self.c, 17))
        graph = [[0, 1, 1, 0], [0, 0, 0, 1], [0, 0, 0, 1], [0, 0, 0, 0]]
        self.assertEqual([0, 2], route_graph(graph)['path'])
        self.assertEqual([0], route_graph([[0,1,0],[0,0,1],[0,0,0]], recursive=True)['path'])


class RadioTransmissionTest(CommunicationsFixture):
    def configure_radios(self):
        for unit in self.units:
            unit.radio_type = 114
            unit.freq, unit.freqmodes, unit.chantitle = [17, 17], [0, 0], ['', '']

    def test_scramble_boundaries_draw_order_and_spaces(self):
        from systems.communications import scramble_message
        from core.randomness import use_source
        with use_source(lambda *args: (_ for _ in ()).throw(AssertionError('unexpected draw'))):
            self.assertEqual(('A B', False), scramble_message('A B', 80, 80, 80))
        stream = iter([51, 8, 1, 3])
        with use_source(lambda *args: next(stream)):
            self.assertEqual(('>', True), scramble_message('A', 100, 50, 100, bth=4))
        stream = iter([50, 1])
        with use_source(lambda *args: next(stream)):
            self.assertEqual(('!', True), scramble_message(' ', 1, 80, 80, under_ecm=True))

    def test_selection_muting_stopped_reception_and_sender_echo(self):
        from systems.communications import transmit
        self.configure_radios()
        self.b.freqmodes[0] = 2
        self.b.status = S.NONE
        self.c.status = S.UNCONSCIOUS
        transmit(self.a, 0, 'hello')
        self.assertEqual(1, len(self.a.pilot.inbox))
        self.assertEqual('(B:180) hello%c', self.b.pilot.inbox[-1])
        self.assertFalse(getattr(self.c.pilot, 'inbox', []))

    def test_scan_retunes_but_never_delivers_current_message(self):
        from systems.communications import transmit
        from core.randomness import use_source
        self.configure_radios()
        self.a.freq[0] = 1000
        self.b.freq, self.b.freqmodes = [900, 0], [16, 0]
        self.c.radio_type = 0
        draws = iter([20, 20])
        with use_source(lambda *args: next(draws)):
            transmit(self.a, 0, 'x' * 20)
        self.assertEqual(920, self.b.freq[0])
        self.assertEqual(2, len(self.b.pilot.inbox))
        self.assertIn('somewhat', self.b.pilot.inbox[-1])

    def test_frequency_abuse_requests_do_not_collapse_identical_channels(self):
        from systems.communications import set_frequency
        self.configure_radios()
        self.b.team = 2
        set_frequency(self.a, 'a=17')
        self.assertEqual(2, len([e for e in self.a.external_effects if e['service'] == 'MechFreqs']))


class NetworkRangeTest(CommunicationsFixture):
    def test_command_formation_supplies_actual_range_and_disabled_reference(self):
        from systems import c3
        from systems.combat_ranges import find_c3_range
        from physics.hexmath import SCALEMAP
        c3.command(self.b, self.b.pilot, 'join', 'AA', ordinary=False)
        self.a.fx, self.b.fx, self.c.fx = 0, 9 * SCALEMAP, 12 * SCALEMAP
        self.a.fy = self.b.fy = self.c.fy = 0
        self.assertEqual((3, 11), find_c3_range(self.a, self.c, 12, False))
        self.b.status |= S.UNCONSCIOUS
        self.assertEqual((3, 11), find_c3_range(self.a, self.c, 12, False))
        self.b.status = S.NONE
        self.assertEqual((12, 0), find_c3_range(self.a, self.c, 12, False))
        self.assertEqual([11], self.a.c3i_network)
        self.a.crit_status |= C.C3I_DESTROYED
        self.assertEqual((12, 77), c3.range_query(self.a, self.c, 12, False, reference=77))
        self.assertEqual([], self.b.c3i_network)

    def test_map_transfer_removes_real_peers(self):
        from systems import c3
        from systems.map_transitions import transfer
        from core.randomness import use_source
        c3.add(self.a, self.b, False)
        destination = GameMap(12,12)
        destination._id = 2000
        self.engine.register_entity(destination)
        with use_source(lambda name,lo,hi,fallback:lo):
            transfer(self.b, destination)
        self.assertEqual([], self.a.c3i_network)
        self.assertEqual([], self.b.c3i_network)
        self.assertIs(self.b.map, destination)


class PresentationTest(CommunicationsFixture):
    def test_ammo_and_fire_priorities_are_distinct_and_use_actual_slots(self):
        from systems.network_reports import ammo_description, ammo_letter, fire_letter, slot_ammo_letter
        from entities.mech import AmmoMode as A, FireMode as F
        from entities.weapon import get_weapon
        weapon = get_weapon('IS.MediumLaser')
        self.assertEqual(' Shotgun', ammo_description(weapon, A.LBX_MODE | A.CLUSTER_MODE))
        self.assertEqual('C', ammo_letter(weapon, A.LBX_MODE | A.CLUSTER_MODE))
        self.assertEqual('H', fire_letter(F.HOTLOAD_MODE | F.ULTRA_MODE))
        self.a.sections[0].criticals[0].type = weapon.index + 1
        self.a.sections[0].criticals[0].ammomode = A.MML_LRM_MODE
        self.assertEqual('#', slot_ammo_letter(self.a, 0, 0))

    def test_flags_private_levels_and_spinning_viewer(self):
        from systems.network_reports import show_flags, status_char
        self.a.status = S.DESTROYED | S.TORSO_RIGHT | S.TORSO_LEFT
        self.assertEqual(['DESTROYED', 'SHUTDOWN'], show_flags(self.a, level=1))
        self.assertEqual([], show_flags(self.a, level=2))
        self.a.crit_status |= C.SPINNING
        self.assertEqual('X', status_char(self.a, self.b, 3))


class BroadcastTest(CommunicationsFixture):
    def test_long_los_broadcasts_preserve_source_output_limits(self):
        from systems.sensors import los_broadcast
        from systems.notifications import pair_los_broadcast
        message = 'x' * 16382
        los_broadcast(self.a, message)
        self.assertEqual(('A [aa] ' + message)[:16383], self.c.pilot.inbox[-1])
        pair_los_broadcast(self.a, self.b, '%s ' + message)
        self.assertEqual(('A [aa] B [bb] ' + message)[:16383], self.c.pilot.inbox[-1])

    def test_single_los_includes_observer_identity_and_apostrophe(self):
        from systems.sensors import los_broadcast
        from core.randomness import use_source
        with use_source(lambda name,lo,hi,fallback:lo):
            los_broadcast(self.a, "'s arm")
        self.assertEqual("A [aa]'s arm", self.b.pilot.inbox[-1])
        self.assertFalse(getattr(self.a.pilot, 'inbox', []))

    def test_limited_counts_geometry_even_when_inbox_suppressed(self):
        from systems.notifications import limited_broadcast
        from physics.hexmath import SCALEMAP
        for unit in self.units:
            unit.fx,unit.fy,unit.fz = 20*SCALEMAP,0,0
        self.a.fx,self.a.fz = 5*SCALEMAP,10*SCALEMAP
        self.assertEqual(1,limited_broadcast(self.board,0,0,0,5,'2d',dimensions=2))
        self.assertEqual(0,limited_broadcast(self.board,0,0,0,5,'3d',dimensions=3))
        self.a.fz=0
        self.a.status|=S.UNCONSCIOUS
        self.assertEqual(1,limited_broadcast(self.board,0,0,0,5,'silent',dimensions=3))
        self.assertEqual(['2d'],self.a.pilot.inbox)

class CommunicationIntegrationTest(CommunicationsFixture):
    def test_long_directed_radio_truncates_local_frames_and_reply_request(self):
        from systems.communications import directed_radio
        from core.events import EventType
        self.b.radio_type=2; self.b.freq=[17,0]; self.b.autopilot=900
        self.store.create(900,'AUTO',location=self.b._id)
        self.world.add(self.store.actor(900),self.b._id)
        message = 'x' * 16382
        self.assertTrue(directed_radio(self.a, self.a.pilot, 'BB=' + message)['ok'])
        self.assertEqual(("You radio B [bb] with, '" + message + "'")[:16383], self.a.pilot.inbox[-1])
        self.assertEqual(("A [aa] radios you with, '" + message + "'")[:16383], self.b.pilot.inbox[-1])
        event = self.engine.events.pending_events(event_type=EventType.AUTO_REPLY, data=self.b)[0]
        self.assertEqual(("A [aa] radio'ed me '" + message + "'")[:16383], event.data2)

    def test_direct_movement_and_missile_callbacks_deliver_once_and_keep_hooks(self):
        from unittest.mock import patch
        from physics import movement
        from systems import missile, movement_commands
        observed=[]
        with patch.object(movement,'NOTIFY_HOOK',lambda u,t:observed.append(('move',t))), patch.object(missile,'NOTIFY_HOOK',lambda u,t:observed.append(('missile',t))):
            movement._notify(self.a,'terrain warning')
            movement_commands.notify(self.a,'heading changed')
            missile._notify(self.a,'missile event')
            self.a.status|=S.UNCONSCIOUS
            movement._notify(self.a,'suppressed')
        self.assertEqual(['terrain warning','heading changed','missile event'],self.a.pilot.inbox)
        self.assertEqual(1,observed.count(('move','heading changed')))
        self.assertIn(('missile','missile event'),observed)

    def test_route_array_limit_matches_250_source_slots(self):
        from systems.communications import route_graph
        with self.assertRaisesRegex(ValueError,'graph array'):
            route_graph([[False]*251 for _ in range(251)])
        edges=[[False]*250 for _ in range(250)];edges[0][-1]=True
        self.assertEqual([0],route_graph(edges)['path'])

    def test_direct_range_wins_even_when_a_relay_cannot_reach_receiver(self):
        from systems.communications import find_comm_link
        from physics.hexmath import SCALEMAP
        for p,distance,radius in zip(self.units,(0,5,10),(10,1,1)):
            p.fx,p.fy,p.fz=distance*SCALEMAP,0,0;p.radio_range=radius
            p.radio_type=114;p.freq,p.freqmodes=[17,0],[5,0]
        self.assertEqual([10],find_comm_link(self.board,self.a,self.c,17)['path'])
        self.a.radio_range=5
        self.assertIsNone(find_comm_link(self.board,self.a,self.c,17))

    def test_relay_path_and_local_reception_do_not_execute_autopilot_parser(self):
        from systems.communications import transmit
        from physics.hexmath import SCALEMAP
        for p,distance in zip(self.units,(0,5,10)):
            p.fx,p.fy,p.fz=distance*SCALEMAP,0,0;p.radio_range=5
            p.radio_type=114;p.freq,p.freqmodes,p.chantitle=[17,0],[13,0],['Ops','']
        self.c.autopilot=900
        self.store.create(900,'Autopilot',location=self.c._id)
        self.world.add(self.store.actor(900),self.c._id)
        rows=transmit(self.a,0,'hold')
        self.assertEqual('[A:270] {R-path:[BB]-h:270} <Ops> hold%c',self.c.pilot.inbox[-1])
        self.assertEqual([112,900],rows[-1]['recipients'])
        request=[e for e in self.c.external_effects if e['service']=='autopilot parser']
        self.assertEqual(1,len(request));self.assertFalse(request[0]['applied'])

    def test_safe_radio_formatters_truncate_the_combined_output(self):
        from systems.communications import scramble_message,transmit
        self.assertEqual((('<Ops> '+'x'*16382)[:16383],False),scramble_message('x'*16382,0,80,80,title='Ops',digital=1))
        for p in self.units:
            p.radio_type=114;p.freq=[17,0];p.freqmodes=[1,0];p.chantitle=['Ops','']
        rows=transmit(self.a,0,'x'*16382)
        self.assertEqual(16383,len(rows[0]['text']))
        self.assertTrue(rows[0]['text'].startswith('[A:180] <Ops> '))
        with self.assertRaisesRegex(ValueError,'input buffer'):
            transmit(self.a,0,'x'*16384)


    def test_local_inbox_preserves_raw_text_and_executes_local_delivery(self):
        from systems.notifications import mech_notify,MECHPILOT
        text='%chhello%cn'
        mech_notify(self.a,MECHPILOT,text)
        mech_notify(self.a,MECHPILOT,text)
        self.assertEqual([text,text],self.a.pilot.inbox)
        requests=self.a.pilot.notification_requests
        self.assertEqual(2,len(requests))
        self.assertTrue(all(r['recipient']==110 and r['message']==text and r['applied'] for r in requests))
        self.a.status|=S.BLINDED
        mech_notify(self.a,MECHPILOT,'suppressed')
        self.assertEqual(2,len(requests))

    def test_formatted_notification_and_flag_buffers_match_source_allocation(self):
        from systems.notifications import mech_printf,MECHALL
        from systems.network_reports import show_flags
        mech_printf(self.a,MECHALL,'%s%d','x'*16382,17)
        self.assertEqual('x'*16382+'1',self.a.pilot.inbox[-1])
        self.assertEqual([],show_flags(self.a,spaces=2047))
        self.a.status|=S.COMBAT_SAFE
        self.assertEqual(' '*1500+'%cb%chCOMBAT SAFE%cn',show_flags(self.a,spaces=1500)[0])
        with self.assertRaisesRegex(ValueError,'buffer'):
            show_flags(self.a,spaces=2047)


if __name__ == '__main__':
    unittest.main()
