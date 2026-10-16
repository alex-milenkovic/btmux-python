"""AUD-PILOTS review regressions through real commands and effect adapters."""
import unittest
from unittest.mock import patch
from core.randomness import use_source
from core.events import EventType as E
from entities.mech import UnitType as U, MechStatus as S, MechStatus2 as S2
from systems import occupants, swarm, experience
from systems.characters import set_value
from systems.notifications import personal_notify
from tests import test_transport as transport_fixture, test_character_awards as award_fixture


class ReviewTransportTests(unittest.TestCase):
    setUp=transport_fixture.TransportTest.setUp
    make=transport_fixture.TransportTest.make

    def test_mounted_suit_boards_then_shutdown_releases_integer_host(self):
        from core.game_loop import update_recycling
        self.own.unit_type=U.BSUIT;self.own.infantry_specials=7
        set_value(self.store,101,'Piloting-BSuit',8)
        for section in self.own.sections:section.armor=section.armor_orig=100
        with use_source(lambda name,lo,hi,fallback:hi):
            result=swarm.swarm(self.own,self.actor,self.carrier)
        self.assertTrue(result['success'],result)
        self.assertEqual(20,self.own.swarm_target)
        self.assertEqual(10,self.carrier.swarmer)
        self.engine.events._tick=20;update_recycling(self.engine,self.own)
        self.assertEqual([0]*8,[section.recycle for section in self.own.sections])
        observed=[];draws=[]
        def draw(name,lo,hi,fallback):
            draws.append(name)
            if name=='damage_entry':return hi
            self.assertEqual('suit_fall_location',name)
            observed.append((self.own.map,self.own.location,self.own.is_started,self.own.pilot,
                             self.own.swarm_target,self.carrier.swarmer,self.carrier.cargo_space))
            return 0
        with use_source(draw):result=occupants.embark(self.own,self.actor,self.carrier)
        self.assertTrue(result['ok'],result)
        self.assertEqual([(None,20,False,None,-1,-1,300)],observed)
        self.assertEqual(['suit_fall_location','damage_entry'],draws)
        self.assertFalse(self.own.status2&S2.UNIT_MOUNTING)
        self.assertFalse(self.carrier.status2&S2.UNIT_MOUNTED)
        self.assertEqual(89,self.own.sections[0].armor)
        self.assertEqual([45]*8,[section.recycle for section in self.own.sections])
        self.assertFalse(self.engine.has_event(E.MOVE,self.own))

    def test_stale_target_notice_observes_old_id_and_explicit_failure_is_personal(self):
        from systems.movement_commands import notify
        self.own.unit_type=U.BSUIT;self.own.infantry_specials=7
        self.store.create(102,'Bob',location=10);other=self.store.actor(102);self.world.add(other,10)
        for command in (swarm.swarm,swarm.attackleg):
            with self.subTest(command=command.__name__):
                self.own.target=999;self.actor.inbox=[];other.inbox=[];observed=[]
                def announce(unit,text,audience=2):
                    observed.append((text,unit.target,audience))
                    return notify(unit,text,audience)
                with patch('systems.movement_commands.notify',side_effect=announce):
                    result=command(self.own,self.actor,'')
                self.assertFalse(result['ok']);self.assertEqual(-1,self.own.target)
                self.assertEqual([('Invalid default target!',999,2)],observed)
                self.assertEqual(['Invalid default target!'],self.actor.inbox)
                self.assertEqual(self.actor.inbox,other.inbox)
                self.actor.inbox=[];other.inbox=[]
                result=command(self.own,self.actor,'ZZ')
                self.assertFalse(result['ok']);self.assertEqual([],other.inbox)
                self.assertEqual(['Target is not in line of sight!'],self.actor.inbox)

    def test_command_invalid_map_delivers_each_shutdown_refusal_before_reset(self):
        initial='You are on an invalid map! Map index reset!'
        stopped="The 'mech hasn't been started yet!"
        snore='You snore for a while.. and then _start_ yourself back up.'
        cases=((occupants.eject,U.MECH,False,stopped),
               (occupants.disembark,U.MECH,False,stopped),
               (occupants.embark,U.MW,True,snore),
               (occupants.pickup,U.MW,True,snore),
               (swarm.hide,U.MW,True,snore),
               (occupants.eject,U.MECH,True,None))
        for command,kind,started,refusal in cases:
            with self.subTest(command=command.__name__,kind=kind,refusal=refusal):
                self.own.unit_type=kind;self.own.status=S.STARTED if started else S.NONE
                self.own.pilot=self.actor if refusal else None
                self.own.mapindex=999;self.actor.inbox=[];observed=[]
                def notice(actor,text,**context):
                    observed.append((actor._id,text,self.own.mapindex));return personal_notify(actor,text,**context)
                with patch('systems.notifications.personal_notify',side_effect=notice):
                    args=(self.own,self.actor,self.carrier) if command in (occupants.embark,occupants.pickup) else (self.own,self.actor)
                    result=command(*args)
                expected=[initial]+([refusal] if refusal else [])
                self.assertFalse(result['ok']);self.assertEqual(-1,self.own.mapindex)
                self.assertEqual(expected,self.actor.inbox)
                self.assertEqual([(101,text,999) for text in expected],observed)

    def test_eject_and_disembark_preserve_wizard_shutdown_on_airborne_dropship(self):
        initial='You are on an invalid map! Map index reset!'
        for command in (occupants.eject,occupants.disembark):
            for wizard in (False,True):
                with self.subTest(command=command.__name__,wizard=wizard):
                    self.world.update(self.actor,wizard=wizard)
                    self.own.unit_type=U.DS;self.own.status=S.STARTED;self.own.pilot=self.actor
                    self.own.mapindex=999;self.actor.inbox=[]
                    result=command(self.own,self.actor)
                    self.assertFalse(result['ok']);self.assertEqual(-1,self.own.mapindex)
                    self.assertEqual(not wizard,self.own.is_started)
                    self.assertEqual([initial,'Dropship has been shutdown!' if wizard else
                                      'No shutdowns in mid-air! Are you suicidal?'],self.actor.inbox)

    def test_setxy_and_ood_deliver_god_refusals_without_changing_ood_equality_guard(self):
        from systems.map_transitions import set_xy
        from physics.orbital import initiate_ood
        self.store.create(1,'God',wizard=True,god=True);god=self.store.actor(1);self.world.add(god,1000)
        initial='You are on an invalid map! Map index reset!'
        for ood,kind,started in ((False,U.DS,False),(False,U.MW,True),(True,U.MECH,False),(True,U.MW,True)):
            with self.subTest(ood=ood,kind=kind):
                self.own.unit_type=kind;self.own.status=S.STARTED if started else S.NONE
                self.own.mapindex=999;self.own.pilot=self.actor;self.own.cocoon=0
                god.inbox=[];self.actor.inbox=[];observed=[]
                def notice(actor,text,**context):
                    observed.append((actor._id,text,self.own.mapindex));return personal_notify(actor,text,**context)
                with patch('systems.notifications.personal_notify',side_effect=notice):
                    result=initiate_ood(self.engine,self.own,'3 3 9',actor=self.actor) if ood else set_xy(self.own,3,3,actor=1)
                refusal=('You snore for a while.. and then _start_ yourself back up.' if started else
                         "The 'mech hasn't been started yet!")
                self.assertEqual([initial,refusal],god.inbox)
                self.assertEqual([(1,initial,999),(1,refusal,999)],observed[:2])
                self.assertEqual(-1,self.own.mapindex)
                if ood:
                    self.assertTrue(result[0],result)
                    self.assertEqual((3,3,9),(self.own.x,self.own.y,self.own.z))
                    self.assertEqual([(101,'OOD initiated.',-1)],observed[2:])
                    self.assertTrue(self.engine.has_event(E.OOD,self.own))
                    self.engine.cancel_events_of_type(E.OOD,self.own)
                else:self.assertFalse(result)


class ReviewXPTests(unittest.TestCase):
    setUp=award_fixture.CharacterAwardsTest.setUp
    config=award_fixture.CharacterAwardsTest.config

    def test_old_and_new_mw_awards_use_object_name_without_changing_draws_or_channel_order(self):
        self.unit.unit_type=self.target.unit_type=U.MW
        self.unit.name=self.target.name='MechWarrior'
        self.unit.object_name='MechWarrior - Alice';self.target.object_name='MechWarrior - Bob'
        weapon=self.config(noisy_xpgain=True)
        for old in (True,False):
            with self.subTest(old=old):
                self.engine.xp_config.oldxpsystem=old;self.engine.sim_now+=31
                self.engine.effects.channels.clear();draws=[]
                with use_source(lambda name,lo,hi,fallback:(draws.append(name) or lo)):
                    self.assertTrue(experience.gun(self.actor,self.unit,self.target,10,100,weapon,8))
                self.assertEqual(['xp_old_gate'] if old else [],draws)
                channels=self.engine.effects.channels
                self.assertEqual(['MechAttackXP'] if old else ['MechAttackXP','MechXP'],[r['channel'] for r in channels])
                text=channels[0]['text']
                self.assertTrue(text.endswith('against MechWarrior - Bob'),text)
                self.assertRegex(text,r'feat of \d+\.\d{6}')
                self.assertIn('(10 occurences)' if old else '(10 damage)',text)

    def test_invalid_old_tonnage_uses_object_name_and_fallback_without_a_draw(self):
        self.unit.tonnage=0;self.unit.name='MechWarrior';self.unit.object_name='MechWarrior - Alice'
        def no_draw(*args):raise AssertionError('The tonnage error must precede randomness')
        with use_source(no_draw):
            self.assertEqual(0,experience.gun_amount(self.unit,self.target,10,1,self.weapon,8))
            del self.unit.object_name
            self.assertEqual(0,experience.gun_amount(self.unit,self.target,10,1,self.weapon,8))
        self.assertEqual([
            'AccumulateGunXP: Weird tonnage for IC mech #10 (MechWarrior - Alice): 0',
            'AccumulateGunXP: Weird tonnage for IC mech #10 (MechWarrior): 0',
        ],[r['text'] for r in self.engine.effects.channels])
        self.assertEqual(['MechErrors']*2,[r['channel'] for r in self.engine.effects.channels])
