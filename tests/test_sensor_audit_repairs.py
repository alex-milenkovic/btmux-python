"""Focused regression checks for AUD-SENSORS notification and callback repairs."""
from types import SimpleNamespace
from unittest.mock import patch

from core.events import EventType, SOURCE_EVENT_IDS
from entities.mech import MechStatus as S, UnitType, Location, Specials
from systems import sensors
from systems.los import MECHLOSFLAG_SEEC2, in_line_of_sight
from tests.test_communications import CommunicationsFixture
from tests.test_sensor_completion import SensorFixture
from tests.test_spot import SpotFixture


class TestContactWake(SensorFixture):
    def auto(self, flags=0x87):
        auto = SimpleNamespace(_id=500000, _engine=None, flags=flags,
                               xcode_type='AUTO', mymech=self.a, mymechnum=self.a._id, weaplist=[])
        self.engine.register_entity(auto)
        self.a.auto = auto._id
        return auto

    def acquire(self, flag=MECHLOSFLAG_SEEC2):
        return sensors.sensor_do_we_see_now(
            self.a, flag, 2.0, -1, -1, self.b, 30, 2, 200, 1, 0)

    def test_enemy_wakes_once_and_runs_command_at_plus_one(self):
        auto = self.auto()
        called = []
        self.engine.auto_services['command'] = called.append
        flag = self.acquire()
        self.assertEqual(auto.flags, 0x81)
        events = self.engine.events.pending_events(data=auto)
        self.assertEqual([(e.event_type, e.tick, e.data2) for e in events],
                         [(EventType.AUTOCOM, 1, 0)])
        self.acquire(flag)
        self.assertEqual(len(self.engine.events.pending_events(data=auto)), 1)
        self.assertEqual(called, [])
        self.engine.run_ticks(1)
        self.assertEqual(called, [auto])
        self.assertEqual(SOURCE_EVENT_IDS[EventType.AUTOCOM], 25)

    def test_friendly_and_disabled_gunnery_do_not_wake(self):
        auto = self.auto()
        self.b.team = self.a.team
        self.acquire()
        self.assertEqual(auto.flags, 0x87)
        self.assertEqual(self.engine.events.pending_events(data=auto), [])
        auto.flags = 0x82  # GUNZOMBIE without the source Gunning gate.
        self.b.team = self.a.team + 1
        self.acquire()
        self.assertEqual(auto.flags, 0x82)
        self.assertEqual(self.engine.events.pending_events(data=auto), [])

    def test_historical_aerospace_restores_all_four_events(self):
        for unit_type in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS):
            with self.subTest(unit_type=unit_type):
                self.setUp()
                auto = self.auto()
                self.a.unit_type = unit_type
                self.a.status |= S.LANDED
                called = []
                for service in ('profile', 'gun', 'sensor', 'command'):
                    self.engine.auto_services[service] = lambda obj, name=service: called.append((name, obj))
                self.acquire()
                events = self.engine.events.pending_events(data=auto)
                self.assertEqual({e.event_type for e in events},
                                 {EventType.AUTO_PROFILE, EventType.AUTOGUN,
                                  EventType.AUTO_SENSOR, EventType.AUTOCOM})
                self.assertTrue(all(e.tick == 1 and e.data2 == 0 for e in events))
                self.engine.run_ticks(1)
                self.assertEqual(sorted(name for name, obj in called), ['command', 'gun', 'profile', 'sensor'])
                self.assertTrue(all(obj is auto for name, obj in called))
                self.engine.run_ticks(2)
                self.assertEqual(len(called), 4)  # No later general AUTO heartbeat.

    def test_general_auto_keeps_heartbeat_services(self):
        auto = self.auto()
        called = []
        for service in ('profile', 'gun', 'sensor', 'command'):
            self.engine.auto_services[service] = lambda obj, name=service: called.append(name)
        self.acquire()
        self.engine.run_ticks(2)
        self.assertEqual(called, ['command', 'sensor', 'profile', 'gun', 'sensor', 'gun'])

    def test_historical_service_owns_its_rearm_deadline(self):
        from systems.autopilot import auto_com_event
        auto = self.auto()
        self.a.unit_type = UnitType.AERO
        self.a.status |= S.LANDED
        calls = []
        def profile(obj):
            calls.append(self.engine.muxevent_tick)
            self.engine.schedule_event(180, EventType.AUTO_PROFILE, auto_com_event, data=obj, data2=0)
        self.engine.auto_services['profile'] = profile
        self.acquire()
        self.engine.run_ticks(3)
        self.assertEqual(calls, [1])
        pending = self.engine.events.pending_events(data=auto)
        self.assertEqual([(e.event_type, e.tick) for e in pending],
                         [(EventType.AUTO_PROFILE, 181)])


class TestSensorAudiences(CommunicationsFixture):
    def passenger(self):
        self.store.create(500, 'Passenger', location=self.a._id)
        actor = self.store.actor(500)
        self.world.add(actor, self.a._id)
        return actor

    def test_tag_actor_token_and_notification_precede_link(self):
        from systems.targeting import tag
        passenger = self.passenger()
        self.b.team = 2
        self.a.specials2 |= 0x8000
        self.a.last_use = 42
        ok, message = tag(self.engine, self.a, '  BB  ', caller=passenger)
        self.assertFalse(ok)
        self.assertIn('only the pilot', message)
        self.assertEqual(self.a.last_use, 0)
        observed = []
        def notice(unit, text):
            if text.startswith('You light up'):
                observed.append((self.a.tag_target, self.b.tagged_by,
                                 self.engine.has_event(EventType.TAG_RECYCLE, self.a)))
        with patch('physics.movement.NOTIFY_HOOK', notice):
            ok, message = tag(self.engine, self.a, '  BB  ', caller=self.a.pilot)
        self.assertTrue(ok, message)
        self.assertEqual(message, 'You light up B [BB] with your TAG.')
        self.assertEqual(observed, [(0, 0, False)])
        self.assertEqual(self.a.pilot.inbox, [message])
        self.assertEqual(passenger.inbox, [message])
        self.engine.cancel_events_of_type(EventType.TAG_RECYCLE, self.a)
        self.assertTrue(tag(self.engine, self.a, '  -  ', caller=self.a.pilot)[0])
        self.assertEqual((self.a.tag_target, self.b.tagged_by), (0, 0))

    def test_tag_critical_validates_wounded_even_without_attacker(self):
        from systems.criticals import handle_sensor_equipment_critical, EquipmentType
        self.a.tag_target, self.b.tag_target = 99998, 99999
        from entities.mech import CritStatus
        observed = []
        def notice(unit, message):
            observed.append((message, bool(unit.crit_status & CritStatus.TAG_DESTROYED),
                             unit.tag_target, self.engine.has_event(EventType.TAG_RECYCLE, unit)))
        with patch('physics.movement.NOTIFY_HOOK', notice):
            result = handle_sensor_equipment_critical(self.a, EquipmentType.TAG, self.b)
        self.assertEqual(observed, [
            ('Your TAG system has been destroyed!', True, 99998, False),
            ('Your TAG connection has been broken.', True, 0, False)])
        self.assertEqual(result.messages, ['Your TAG system has been destroyed!'])
        self.assertTrue(self.engine.has_event(EventType.TAG_RECYCLE, self.a))
        self.assertEqual((self.a.tag_target, self.b.tag_target), (0, 99999))
        self.a.tag_target = 99998
        handle_sensor_equipment_critical(self.a, EquipmentType.TAG)
        self.assertEqual(self.a.tag_target, 0)
        # checkTAG intentionally has no equipment-destroyed gate.
        self.a.tag_target, self.b.tagged_by = self.b._id, self.a._id
        handle_sensor_equipment_critical(self.a, EquipmentType.TAG)
        self.assertEqual(self.a.tag_target, self.b._id)

    def test_losemit_relaxed_actor_checks_and_invalid_map_repair(self):
        passenger = self.passenger()
        self.a.status = S.STARTED | S.UNCONSCIOUS
        self.a.last_use = 42
        self.assertEqual(sensors.mech_losemit(self.a, 'waves.', passenger),
                         (True, 'Broadcast done.'))
        self.assertEqual(self.a.last_use, 0)
        self.assertIn('unconscious', sensors.mech_losemit(self.a, 'waves.', self.a.pilot)[1])
        self.a.status = S.DESTROYED | S.BLINDED
        self.assertTrue(sensors.mech_losemit(self.a, 'waves.', passenger)[0])
        self.a.status = S.STARTED
        self.a.map, self.a.mapindex = None, 4444
        self.assertEqual(sensors.mech_losemit(self.a, 'waves.', passenger), (False, ''))
        self.assertEqual(passenger.inbox.count('You are on an invalid map! Map index reset!'), 1)
        self.assertEqual(self.a.mapindex, -1)
        self.assertFalse(self.a.is_started)

    def test_invalid_los_diagnostic_and_pilot_only_recipient(self):
        passenger = self.passenger()
        self.a.map, self.a.mapindex = None, 4444
        self.assertEqual(in_line_of_sight(self.a, self.b, 3, 3, 0), 0)
        self.assertEqual(self.a.pilot.inbox,
                         ['You are on an invalid map! Map index reset!'])
        self.assertEqual(getattr(passenger, 'inbox', []), [])
        self.assertEqual(self.engine.effects.channels[-1]['text'],
                         'InLineOfSight:invalid map:Mech 10  Index 4444')
        self.assertEqual(self.a.mapindex, -1)
        self.a.map, self.a.mapindex = self.board, self.board._id
        self.assertEqual(in_line_of_sight(self.a, self.b, -1, 3, 0), 0)
        self.assertEqual(len(self.a.pilot.inbox), 1)
        self.assertEqual(self.engine.effects.channels[-1]['text'],
                         'x:-1 y:3 out of bounds for #10 (LOS check)')

    def test_contact_identity_arc_labels_and_long_loss_color(self):
        from physics.hexmath import LSIDEARC
        self.b.team = 2
        sensors.contact_notice(self.a, self.b, 1, 1, LSIDEARC, True)
        self.assertEqual(self.a.pilot.inbox[-1],
                         '%crYou notice B [BB] in your Left Arm arc.%cn')
        self.a.unit_type = UnitType.VEH_GROUND
        sensors.contact_notice(self.a, self.b, 1, 1, LSIDEARC, True)
        self.assertEqual(self.a.pilot.inbox[-1],
                         '%crYou notice B [BB] in your Left Side arc.%cn')
        sensors.contact_notice(self.a, self.b, 1, 0, LSIDEARC, False)
        self.assertEqual(self.a.pilot.inbox[-1],
                         'You have lost B [BB] from your scanners. It was last in your Left Side arc.%cn')

    def test_fire_spot_failure_audiences_silent_exits_and_order(self):
        from systems.spot import fire_spot
        from tests.test_missile import mount_weapon
        passenger = self.passenger()
        mount_weapon(self.a, 'IS.LRM-10', Location.LARM)
        mount_weapon(self.a, 'IS.PPC', Location.RARM)
        self.a.spotter = -1
        result = fire_spot(self.engine, self.a, 0)
        self.assertEqual((result.handled, result.messages), (False, []))
        self.a.spotter = 99999
        result = fire_spot(self.engine, self.a, 1)
        self.assertEqual((result.handled, result.messages), (False, []))
        result = fire_spot(self.engine, self.a, 0)
        self.assertEqual(self.a.pilot.inbox[-1], 'There is no spotter avilable to IDF with!')
        self.assertEqual(getattr(passenger, 'inbox', []), [])
        self.a.spotter = self.b._id
        observed = []
        with patch('physics.movement.NOTIFY_HOOK',
                   lambda unit, text: observed.append((text, self.a.spotter))):
            fire_spot(self.engine, self.a, 0)
        self.assertEqual(observed, [('You do not have a spotter!', self.b._id)])
        self.assertEqual(passenger.inbox, ['You do not have a spotter!'])
        self.assertEqual(self.a.spotter, -1)
        self.a.spotter, self.b.spotter = self.b._id, self.b._id
        before = len(self.a.pilot.inbox)
        result = fire_spot(self.engine, self.a, 0)
        self.assertEqual(result.messages, ['Your spotter has no target set!'])
        self.assertTrue(result.handled)
        self.assertEqual(len(self.a.pilot.inbox), before)

    def test_spot_string_token_and_pilot_rule(self):
        from systems.spot import mech_spot
        passenger = self.passenger()
        self.assertIn('only the pilot',
                      mech_spot(self.engine, self.a, ' AA ', caller=passenger)[1])
        self.assertTrue(mech_spot(self.engine, self.a, ' AA ', caller=self.a.pilot)[0])
        self.assertEqual(self.a.spotter, self.a._id)
        self.assertEqual(passenger.inbox[-1], 'You are now set as a spotter.')
        self.assertTrue(mech_spot(self.engine, self.a, ' - ', caller=self.a.pilot)[0])
        self.assertEqual(self.a.spotter, -1)


class TestSpottedVisibility(SpotFixture):
    def shoot(self, *, hex_lock=False, ams=False):
        from systems.combat import fire_weapon_number
        from tests.test_missile import mount_weapon, add_ammo
        self.link()
        self.spot_lock()
        self.see(self.att, self.tgt)  # Shooter LOS must not override literal zero.
        if hex_lock:
            self.spt.target = -1
            self.spt.targ_x, self.spt.targ_y = self.tgt.x, self.tgt.y
            self.spt.targ_z = self.tgt.z
        if ams:
            self.tgt.specials |= Specials.IS_ANTI_MISSILE_TECH
            self.tgt.status |= S.AMS_ENABLED
            weapon, slot = mount_weapon(self.tgt, 'IS.Anti-MissileSystem', Location.LLEG)
            add_ammo(self.tgt, weapon, Location.LLEG, 1, 12)
        self.att.movement_messages = []
        self.tgt.movement_messages = []
        return fire_weapon_number(self.engine, self.att, self.LRM, to_hit_roll=12,
                                  cluster_roll=2 if ams else 12, ams_roll=6,
                                  location_roll=7, location_rolls=[7, 7])

    def test_unit_and_hex_spotted_hits_hide_attacker_roll_and_damage(self):
        for hex_lock in (False, True):
            with self.subTest(hex_lock=hex_lock):
                self.setUp()
                result = self.shoot(hex_lock=hex_lock)
                self.assertTrue(result.hit, result.messages)
                self.assertEqual(result.los, 0)
                self.assertGreater(result.damage_dealt, 0)
                self.assertFalse(any('Roll:' in s or 'You hit' in s
                                     for s in self.att.movement_messages))
                self.assertFalse(any('You hit with' in s for s in result.messages))
                self.assertTrue(any('You have been hit' in s
                                    for s in self.tgt.movement_messages))

    def test_ams_all_shot_down_attacker_notice_stays_hidden(self):
        result = self.shoot(ams=True)
        self.assertTrue(result.hit, result.messages)
        self.assertEqual(result.ams_shot_down, 6)
        self.assertEqual(result.damage_dealt, 0)
        self.assertFalse(any('All of your missiles' in s for s in result.messages))
        self.assertFalse(any('You hit with' in s for s in result.messages))

    def test_recursive_damage_keeps_los_and_transfer_notices(self):
        from systems.combat import apply_damage_with_transfer
        for visible in (0, 1):
            with self.subTest(visible=visible):
                self.setUp()
                section = self.tgt.sections[Location.LARM]
                section.armor = section.internal = 1
                for slot in section.criticals:
                    slot.type = 0
                self.att.movement_messages = []
                self.tgt.movement_messages = []
                # A noncritical internal hit must transfer the two excess points.
                with patch('systems.damage.source_roll', return_value=7):
                    apply_damage_with_transfer(self.tgt, Location.LARM, 4,
                                               attacker=self.att, engine=self.engine, los=visible)
                attack_notices = self.att.movement_messages
                self.assertEqual(any('You hit ' in s for s in attack_notices), bool(visible))
                self.assertEqual(any('Damage transfer.. ' in s for s in attack_notices), bool(visible))
                self.assertTrue(any('(transfer)' in s for s in self.tgt.movement_messages))


class TestReviewCommandOutcomes(CommunicationsFixture):
    def test_invalid_map_notice_precedes_shutdown_and_wizard_authority(self):
        from systems import notifications
        from systems.spot import mech_spot
        from systems.targeting import tag
        invalid = 'You are on an invalid map! Map index reset!'
        refused = 'No shutdowns in mid-air! Are you suicidal?'
        real_notify = notifications.personal_notify
        commands = (sensors.mech_losemit,
                    lambda unit, text, caller: mech_spot(self.engine, unit, text, caller),
                    lambda unit, text, caller: tag(self.engine, unit, text, caller))
        for command in commands:
            for kind in (UnitType.DS, UnitType.SPHEROID_DS):
                for wizard in (False, True):
                    with self.subTest(command=command, kind=kind, wizard=wizard):
                        self.setUp()
                        unit, actor = self.a, self.a.pilot
                        unit.unit_type = kind
                        unit.map, unit.mapindex, unit.last_use = None, 4444, 99
                        actor.wizard = wizard
                        observed = []
                        def delivery(recipient, message, **context):
                            if recipient is actor:
                                observed.append((message, unit.mapindex, unit.is_started))
                            return real_notify(recipient, message, **context)
                        with patch.object(notifications, 'personal_notify', delivery):
                            result = command(unit, ' BB ', actor)
                        self.assertEqual(result, (False, ''))
                        second = 'Dropship has been shutdown!' if wizard else refused
                        self.assertEqual(observed, [(invalid, 4444, True), (second, 4444, True)])
                        self.assertEqual(actor.inbox, [invalid, second])
                        self.assertEqual(unit.mapindex, -1)
                        self.assertEqual(unit.last_use, 0)
                        self.assertEqual(unit.is_started, not wizard)

    def test_null_sensor_commands_are_silent_failures_including_cli(self):
        from systems.spot import mech_spot
        from systems.targeting import tag
        from tools.sensors_los import SensorSession
        for command in (sensors.mech_losemit,
                        lambda unit, text, caller: mech_spot(self.engine, unit, text, caller),
                        lambda unit, text, caller: tag(self.engine, unit, text, caller)):
            self.assertEqual(command(None, 'x', self.a.pilot), (False, ''))
        session = SensorSession({'actions': []})
        for name in ('losemit', 'spot', 'tag'):
            self.assertEqual(session.command(None, name, ['x']),
                             {'ok': False, 'message': ''})
        self.assertEqual(getattr(self.a.pilot, 'inbox', []), [])

    def test_shared_consumers_stop_on_silent_failure(self):
        from systems import communications, c3, bombing, dropships, hangar, observation, status_display, turrets
        actor = self.a.pilot
        calls = (
            lambda: communications.send_channel(None, actor, 'a=hello'),
            lambda: communications.directed_radio(None, actor, 'BB=hello'),
            lambda: c3.command(None, actor, 'join', 'BB'),
            lambda: bombing.command(None, 'list', actor),
            lambda: dropships.enter_bay(None, '', actor),
            lambda: hangar.enter_base(None, '', actor),
            lambda: observation.brief(None),
            lambda: status_display.status(None),
            lambda: turrets.delegate(None, 'fire', '0', actor),
            lambda: turrets.delegate(None, 'status', '', actor),
        )
        for call in calls:
            result = call()
            if isinstance(result, tuple):
                self.assertEqual(result, (False, ''))
            else:
                self.assertFalse(result['ok'])
                self.assertEqual(result.get('message', result.get('error')), '')
        self.assertEqual(getattr(actor, 'inbox', []), [])

    def test_invalid_map_c3_adapter_does_not_repeat_notice(self):
        from systems.c3 import command
        actor = self.a.pilot
        self.a.unit_type = UnitType.DS
        self.a.map, self.a.mapindex = None, 4444
        self.assertEqual(command(self.a, actor, 'join', 'BB'), {'ok': False, 'error': ''})
        self.assertEqual(actor.inbox, ['You are on an invalid map! Map index reset!',
                                     'No shutdowns in mid-air! Are you suicidal?'])


class TestReviewDamageNotices(CommunicationsFixture):
    def empty_location(self, kind):
        self.b.unit_type = kind
        self.b.si = 20
        if kind == UnitType.AERO:
            self.b.sections = self.b.sections[:6]
            self.b.sections[3].armor = 0  # Historical Fuselage, terminal destination.
        location = Location.CTORSO if kind in (UnitType.MECH, UnitType.MW) else 0
        self.b.sections[location].armor = 0
        self.b.sections[location].internal = 0
        return location

    def test_live_firing_callback_formats_structural_damage(self):
        from systems.combat import AttackResult, _apply_single_hit
        from entities.weapon import get_weapon
        for kind in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS):
            for visible in (0, 1):
                with self.subTest(kind=kind, visible=visible):
                    self.setUp()
                    location = self.empty_location(kind)
                    actor, victim = self.a.pilot, self.b.pilot
                    result = AttackResult(los=visible)
                    _apply_single_hit(result, self.a, self.b, get_weapon('IS.MediumLaser'),
                                      location, False, False, 5, engine=self.engine)
                    attacker_hits = [m for m in getattr(actor, 'inbox', []) if m.startswith('%cgYou hit ')]
                    victim_hits = [m for m in getattr(victim, 'inbox', []) if m.startswith('%ch%cyYou have been hit ')]
                    self.assertEqual(attacker_hits,
                                     ['%cgYou hit for 5 points of damage in the structure.%c'] if visible else [])
                    self.assertEqual(victim_hits,
                                     ['%ch%cyYou have been hit for 5 points of damage in the structure.%c'])
                    if kind != UnitType.AERO:
                        self.assertEqual(self.b.si, 15)
                        self.assertEqual(result.damage_dealt, 5)
                        self.assertFalse(self.b.is_destroyed)

    def test_structural_transfer_retains_prefix_and_suffix(self):
        from systems.combat import apply_damage_with_transfer
        for visible in (0, 1):
            with self.subTest(visible=visible):
                self.setUp()
                location = self.empty_location(UnitType.DS)
                apply_damage_with_transfer(self.b, location, 5, attacker=self.a,
                                           engine=self.engine, los=visible, _transferred=True)
                self.assertEqual(getattr(self.a.pilot, 'inbox', []),
                                 ['%cgDamage transfer.. for 5 points of damage in the structure.%c'] if visible else [])
                self.assertEqual(self.b.pilot.inbox,
                                 ['%ch%cyYou have been hit for 5 points of damage in the structure.(transfer)%c'])
                self.assertEqual(self.b.si, 15)

    def test_source_discarded_terminal_hits_publish_no_normal_notice(self):
        from systems.combat import AttackResult, _apply_single_hit
        from entities.weapon import get_weapon
        for kind in (UnitType.MECH, UnitType.MW, UnitType.VEH_GROUND,
                     UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS):
            with self.subTest(kind=kind):
                self.setUp()
                location = self.empty_location(kind)
                if kind in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS):
                    self.b.status |= S.DESTROYED
                actor, victim = self.a.pilot, self.b.pilot
                result = AttackResult(los=1)
                _apply_single_hit(result, self.a, self.b, get_weapon('IS.MediumLaser'),
                                  location, False, False, 5, engine=self.engine)
                for recipient in (actor, victim):
                    self.assertFalse(any(m.startswith(('%cgYou hit ', '%cgDamage transfer.. ',
                                                       '%ch%cyYou have been hit '))
                                         for m in getattr(recipient, 'inbox', [])))
