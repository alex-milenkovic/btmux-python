"""State and delivery boundaries reopened by the Damage/Firing source review."""
import unittest
from unittest.mock import patch
from core.events import EventType
from core.effects import LocalEffects
from entities.mech import UnitType as U, MoveType as M, Location as L, MechStatus as S, CritStatus, FireMode as F, Specials
from entities.crittypes import i2ammo, i2weapon, i2special, Special
from entities.weapon import get_weapon
from systems import combat, damage, criticals, enhanced_crits, failures, vehicle_combat
from tools.combat_resolution import CombatSession


class WatchingInbox(list):
    def __init__(self, observe):
        super().__init__()
        self.observe = observe

    def append(self, message):
        self.observe(message)
        super().append(message)


def crew_session(data):
    from data.characters import CharacterStore
    from systems.occupants import Personnel
    session = CombatSession(data)
    world = Personnel(session.engine, CharacterStore())
    for index, unit in enumerate(session.units.values(), 10000):
        world.add(unit, unit.mapindex)
        unit.pilot._id = index
        unit.pilot.inbox = []
        world.add(unit.pilot, unit._id)
    return session


class DamageReviewCorrections(unittest.TestCase):
    def test_zero_original_exact_depletion_is_silent_but_penetration_warns(self):
        for kind, rear in ((U.MECH, False), (U.MECH, True), (U.AERO, False), (U.DS, False)):
            for amount in (5, 6):
                with self.subTest(kind=kind, rear=rear, amount=amount):
                    session = crew_session({'actions': []})
                    unit = session.units['u']
                    unit.unit_type = kind
                    unit.armor_warnings = True
                    section = unit.sections[L.LTORSO]
                    section.armor_orig = section.rear_orig = 0
                    section.armor = section.rear = 5
                    combat.cause_armor_damage(unit, L.LTORSO, amount, is_rear=rear)
                    notices = getattr(unit, 'armor_notices', [])
                    self.assertEqual(0 if amount == 5 else 1, len(notices))
                    if notices:
                        self.assertEqual(('breached', rear), (notices[0]['severity'], notices[0]['rear']))

    def test_inert_and_empty_ammo_notify_before_destroying_preserved_bin(self):
        for kind in (U.MECH, U.AERO):
            for name, rounds in (('IS.GaussRifle', 4), ('IS.AC/5', 0)):
                with self.subTest(kind=kind, name=name):
                    session = crew_session({'actions': []})
                    unit = session.units['u']
                    unit.unit_type = kind
                    slot = unit.sections[2].criticals[0]
                    slot.type, slot.data = i2ammo(get_weapon(name).index), rounds
                    observed = []
                    unit.pilot.inbox = WatchingInbox(lambda text: observed.append((text, bool(slot.firemode & F.DESTROYED_MODE))))
                    criticals.apply_critical_to_slot(unit, 2, 0)
                    self.assertEqual('%ch%cyCRITICAL HIT' + ('!!!' if kind == U.AERO else '!!') + '%c', observed[0][0])
                    expected = ('One of your Gauss Rifle ' + ('Ammo' if kind == U.AERO else 'ammo') + ' feeds is destroyed'
                                if rounds else 'You have no ammunition left in that location, lucky you!')
                    self.assertIn((expected, False), observed)
                    self.assertTrue(slot.firemode & F.DESTROYED_MODE)
                    self.assertEqual(rounds, slot.data)

    def test_broken_quad_front_actuators_use_source_names(self):
        for kind, name in ((Special.SHOULDER_OR_HIP, 'hip'), (Special.HAND_OR_FOOT_ACTUATOR, 'foot actuator'),
                           (Special.UPPER_ACTUATOR, 'arm actuator'), (Special.LOWER_ACTUATOR, 'arm actuator')):
            with self.subTest(kind=kind):
                unit = crew_session({'actions': []}).units['u']
                unit.move_type = M.QUAD
                slot = unit.sections[L.LARM].criticals[0]
                slot.type, slot.firemode = i2special(kind), F.DESTROYED_MODE
                result = criticals.apply_critical_to_slot(unit, L.LARM, 0)
                self.assertEqual(f'Part of your non-working {name} has been hit!', result.message)

    def test_probe_technology_is_cleared_when_destruction_notice_arrives(self):
        for kind, field, flag in ((Special.BEAGLE_PROBE, 'specials', Specials.BEAGLE_PROBE_TECH),
                                  (Special.LIGHT_BAP, 'specials', Specials.LIGHT_BAP_TECH),
                                  (Special.BLOODHOUND_PROBE, 'specials2', 0x800)):
            with self.subTest(kind=kind):
                unit = crew_session({'actions': []}).units['u']
                setattr(unit, field, getattr(unit, field) | flag)
                unit.sections[2].criticals[0].type = i2special(kind)
                observed = []
                unit.pilot.inbox = WatchingInbox(lambda text: observed.append((text, bool(getattr(unit, field) & flag))))
                criticals.apply_critical_to_slot(unit, 2, 0)
                self.assertTrue(any('has been destroyed!' in text and not present for text, present in observed))

    def test_weapon_status_delivers_early_rows_before_later_section_error(self):
        session = crew_session({'actions': []})
        unit = session.units['u']
        unit.sections[0].criticals[4].type = i2weapon(get_weapon('IS.MediumLaser').index)
        unit.sections[1].criticals[4].type = i2weapon(get_weapon('IS.AC/10').index)  # Incomplete run.
        session.engine.effects = LocalEffects()
        session.engine.effects.subscribe('MechErrors', unit.pilot)
        unit.pilot.inbox = []
        result = enhanced_crits.weapon_status_command(unit)
        messages = unit.pilot.inbox
        self.assertTrue(result['accepted'])
        self.assertIn('WEAPON SYSTEMS STATUS', messages[0])
        self.assertIn('Weapon Name', messages[1])
        self.assertIn('MediumLaser', messages[2])
        self.assertGreater(next(i for i, text in enumerate(messages) if 'numcriticals' in text), 2)
        self.assertEqual(['MediumLaser'], [row['name'] for row in result['weapons']])

    def test_main_weapon_skips_destroyed_section_before_malformed_scan(self):
        unit = crew_session({'actions': []}).units['u']
        unit.sections[0].criticals[4].type = i2weapon(get_weapon('IS.MediumLaser').index)
        unit.sections[1].criticals[4].type = i2weapon(get_weapon('IS.AC/10').index)
        unit.sections[1].armor = unit.sections[1].internal = 0
        with patch('systems.vehicle_combat.vehicle_draw', return_value=10):
            selected = vehicle_combat.main_weapon(unit)
        self.assertEqual((0, 4), (selected.section, selected.critical))
        self.assertFalse(any(row['source_channel'] == 'MechErrors' for row in getattr(unit, 'channel_requests', [])))

    def test_overdue_dud_observes_and_clears_new_failure_before_timer_write(self):
        for outcome in (1, 2, 6):
            with self.subTest(outcome=outcome):
                session = crew_session({'actions': [], 'units': [{'name': 'u', 'weapons': ['IS.AC/5']}]})
                unit = session.units['u']
                mount = unit.weapons[0]
                slot = unit.sections[mount.section].criticals[mount.critical]
                slot.data = 5
                session.engine.events.set_tick(10)
                unit.pilot.inbox = []
                with patch('systems.failures.number', return_value=1):
                    result = failures.apply_failure(unit, 6, outcome, mount.section, mount.critical)
                self.assertEqual(0, enhanced_crits.part_temp_nuke(slot))
                self.assertEqual(get_weapon('IS.AC/5').vrt if outcome == 1 else 31, slot.data)
                self.assertEqual('NONE' if outcome == 1 else 'WEAPON_DUD', result.type)
                word = 'finished recycling' if outcome == 1 else 'is operational again'
                self.assertTrue(any(word in text for text in unit.pilot.inbox))

    def test_hosted_suit_detaches_after_destroyed_and_stun_before_cancel(self):
        for historical in (False, True):
            with self.subTest(historical=historical):
                session = crew_session({'actions': []})
                host, suit = session.units.values()
                if historical:
                    host.unit_type = U.AERO
                suit.unit_type = U.BSUIT
                suit.swarm_target = host._id
                host.swarmer = suit._id
                host.crit_status |= CritStatus.MECH_STUNNED
                event = session.engine.events.schedule(30, EventType.UNSTUN_CREW, lambda e: None, host)
                host_pilot = host.pilot
                host_pilot.inbox = []
                observed = []
                suit.pilot.inbox = WatchingInbox(lambda text: observed.append((text, host.is_destroyed, bool(host.crit_status & CritStatus.MECH_STUNNED), event.zombie)))
                damage.destroy_state(host, session.engine, historical=historical)
                state = next(row[1:] for row in observed if 'let your hold loosen' in row[0])
                self.assertEqual((True, False, False), state)
                self.assertFalse(any('lets go of you' in text for text in host_pilot.inbox))
                self.assertEqual(-1,suit.swarm_target)
                self.assertTrue(event.zombie)
