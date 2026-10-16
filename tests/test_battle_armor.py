"""Eight-member swarm actions, source hide clock and pack semantics."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from core.game_loop import GameEngine
from core.randomness import use_source
from core.events import EventType as E
from entities.map import GameMap,ROUGH
from entities.mech import Mech,UnitType as U,MechStatus as S,MechStatus2 as S2,CritStatus as C,FireMode as F,SectionConfig
from entities.pilot import Pilot
from entities.weapon import get_weapon
from systems import swarm as b

class BattleArmorTest(unittest.TestCase):
    def setUp(self):
        self.engine=GameEngine();self.board=GameMap(12,12)
        self.board._id=100;self.engine.register_entity(self.board)
        self.suit=Mech.create_test_mech();self.host=Mech.create_test_mech()
        for i,u in enumerate((self.suit,self.host),10):
            u._id=i;u.contact_id=f'A{i-10}';u.status=S.STARTED;u.team=i;u.set_hex_position(3,3);u.pilot=Pilot(piloting=0)
            self.board.add_mech(u);self.engine.register_entity(u)
        self.suit.unit_type=U.BSUIT;self.suit.infantry_specials=7
        self.suit.sections[6].internal=self.suit.sections[7].internal=0
        from systems.sensors import update_los_info
        from systems.targeting import plos_event
        with use_source(lambda name,lo,hi,fallback:hi):
            update_los_info(self.board)
            for u in (self.suit,self.host):plos_event(SimpleNamespace(data=u,data2=self.engine))

    def test_eight_members_busy_destroyed_section_and_mirror_height(self):
        for s in self.suit.sections:s.internal=0
        self.suit.sections[7].internal=1;self.suit.sections[7].config|=SectionConfig.SECTION_DESTROYED
        self.assertEqual(1,b.members(self.suit))
        slot=self.suit.sections[7].criticals[0];slot.type=get_weapon('PC.SMG').index+1;slot.data=3
        self.suit.sections[7].recycle=9
        self.suit.sections[7].internal=self.suit.sections[7].armor=0
        self.assertIsNone(b.common_checks(self.suit))
        self.suit.sections[7].internal=1;self.suit.sections[7].recycle=0
        self.suit.sections[7].config&=~SectionConfig.SECTION_DESTROYED
        self.assertIn('weapons',b.common_checks(self.suit))
        self.host.z=2;self.host.elev=1;self.host.fz=129
        b.mirror(self.host,self.suit)
        self.assertEqual((3,2,193.5),(self.suit.z,self.suit.elev,self.suit.fz))

    def test_shared_hit_and_transfer_tables_include_section_seven(self):
        from systems.hit_locations import live_suit_hit_location,transfer_target,find_hit_location
        from systems.combat import HitGroup
        for section in self.suit.sections:section.internal=0
        self.suit.sections[7].internal=1;bounds=[]
        def choose(name,lo,hi,fallback):bounds.append((name,lo,hi));return hi
        with use_source(choose):
            self.assertEqual(7,live_suit_hit_location(self.suit))
            self.assertEqual(7,transfer_target(self.suit,0))
            self.suit.sections[7].internal=0
            self.assertEqual(7,find_hit_location(self.suit,HitGroup.FRONT)[0])
        self.assertEqual(('empty_suit_location',0,7),bounds[-1])

    def test_swarm_hidden_success_and_host_destroy_intentionally_detaches(self):
        self.suit.set_crit_status(C.HIDDEN);self.suit.speed=2;self.suit.desired_speed=3
        self.engine.schedule_event(10,E.HIDE,lambda e:None,data=self.suit)
        with use_source(lambda name,lo,hi,fallback:hi):r=b.swarm(self.suit,self.suit.pilot,self.host)
        self.assertTrue(r['success'],r);self.assertEqual(self.host._id,self.suit.swarm_target)
        self.assertEqual((270,270,0,0),(self.suit.facing,self.suit.desired_facing,self.suit.speed,self.suit.desired_speed))
        self.assertFalse(self.suit.has_crit_status(C.HIDDEN));self.assertFalse(self.engine.has_event(E.HIDE,self.suit))
        from systems.damage import destroy_mech
        with use_source(lambda *args: (_ for _ in ()).throw(AssertionError('destroy must detach intentionally'))):destroy_mech(self.host,None)
        self.assertEqual(-1,self.suit.swarm_target);self.assertEqual([20]*6,[s.recycle for s in self.suit.sections[:6]])

    def test_unhidden_attempt_retains_pending_hide_and_failed_leg_retains_hidden(self):
        self.engine.schedule_event(10,E.HIDE,lambda e:None,data=self.suit)
        with use_source(lambda name,lo,hi,fallback:lo):b.swarm(self.suit,self.suit.pilot,self.host)
        self.assertTrue(self.engine.has_event(E.HIDE,self.suit))
        self.suit.swarm_target=None
        for section in self.suit.sections:section.recycle=0
        self.suit.pilot.piloting=20;self.suit.set_crit_status(C.HIDDEN)
        with use_source(lambda name,lo,hi,fallback:lo):r=b.attackleg(self.suit,self.suit.pilot,self.host)
        self.assertFalse(r['success']);self.assertTrue(self.suit.has_crit_status(C.HIDDEN))
        self.assertEqual([30]*6,[s.recycle for s in self.suit.sections[:6]])

    def test_critical_twelve_destroys_before_three_criticals(self):
        with patch('systems.criticals.check_and_apply_criticals') as criticals:
            def after(unit,loc,n,**kwargs):
                self.assertEqual(0,unit.sections[loc].internal);self.assertEqual(3,n);return []
            criticals.side_effect=after
            with use_source(lambda name,lo,hi,fallback:hi):r=b.attackleg(self.suit,self.suit.pilot,self.host)
        self.assertEqual('destroy-leg-then-critical3',r['effect']);self.assertEqual(1,criticals.call_count)
        self.assertTrue(self.host.is_fallen)

    def test_hide_full_deadline_and_movement_cancels_pending(self):
        self.host.clear_status(S.STARTED);self.board.set_terrain(3,3,ROUGH);self.suit.terrain=ROUGH
        self.suit.unit_type=U.MW
        self.assertTrue(b.hide(self.suit,self.suit.pilot)['ok'])
        for _ in range(20):self.engine.process_tick();self.assertFalse(self.suit.has_crit_status(C.HIDDEN))
        self.engine.process_tick();self.assertTrue(self.suit.has_crit_status(C.HIDDEN))
        self.suit.clear_crit_status(C.HIDDEN);b.hide(self.suit,self.suit.pilot)
        from physics.movement import on_hex_entered
        on_hex_entered(self.suit,2,3)
        self.assertFalse(self.engine.has_event(E.HIDE,self.suit))

    def test_jettison_all_slots_preserves_other_flags_and_updates_runtime(self):
        from systems.weapon_inventory import sync_weapon_states
        self.suit.infantry_specials|=0x200
        slot=self.suit.sections[7].criticals[11];slot.type=get_weapon('PC.SMG').index+1
        slot.firemode=F.WILL_JETTISON_MODE|F.BROKEN_MODE|F.DISABLED_MODE|F.DAMAGED_MODE
        sync_weapon_states(self.suit)
        r=b.jettison(self.suit,self.suit.pilot);self.assertEqual(1,r['count'])
        self.assertEqual(F.WILL_JETTISON_MODE|F.DAMAGED_MODE|F.DESTROYED_MODE|F.IS_JETTISONED_MODE,slot.firemode)
        self.assertTrue(self.suit.weapons[-1].destroyed);self.assertEqual(0,b.jettison(self.suit,self.suit.pilot)['count'])

    def test_swarm_and_detach_notify_both_participants_with_distinct_outcomes(self):
        with use_source(lambda name,lo,hi,fallback:hi):
            r=b.swarm(self.suit,self.suit.pilot,self.host)
            self.assertTrue(r['success'])
            self.assertTrue(any('swarms you!' in m for m in self.host.movement_messages))
            b.detach(self.suit,True)
        self.assertTrue(any('lets go of you!' in m for m in self.host.movement_messages))
        self.assertTrue(any('let your hold loosen' in m for m in self.suit.movement_messages))

    def test_leg_surface_damage_and_falling_suit_bypass_swarm_interception(self):
        real=__import__('systems.combat',fromlist=['apply_damage_with_transfer']).apply_damage_with_transfer
        with patch('systems.combat.apply_damage_with_transfer',wraps=real) as damage:
            with use_source(lambda name,lo,hi,fallback:7 if name=='leg_critical' else 2 if name=='critical_rolls' else hi):
                b.attackleg(self.suit,self.suit.pilot,self.host)
            self.assertTrue(damage.call_args.kwargs['ignore_swarmers'])
        self.suit.pilot.piloting=30;self.suit.swarm_target=self.host._id
        with patch('systems.combat.apply_damage_with_transfer') as damage:
            with use_source(lambda name,lo,hi,fallback:hi):b.detach(self.suit)
            self.assertTrue(damage.call_args.kwargs['ignore_swarmers'])

    def test_fallen_only_modifier_composition_preserves_extra_swarm_term(self):
        from systems.combat import is_target_immobile,calculate_target_movement_modifier
        for index,section in enumerate(self.suit.sections):section.internal=1 if index<4 else 0
        self.host.unit_type=U.MECH;self.host.status=S.STARTED|S.FALLEN
        self.host.speed=self.host.desired_speed=0
        self.assertFalse(is_target_immobile(self.host))
        self.assertEqual(-2,calculate_target_movement_modifier(self.host,0,self.suit))
        self.assertEqual(-2,b.modifier(self.suit,self.host))
        self.assertEqual(-3,b.modifier(self.suit,self.host,True))
        self.suit.set_crit_status(C.HIDDEN)
        self.assertEqual(-2,b.modifier(self.suit,self.host))
        self.assertEqual(-3,b.modifier(self.suit,self.host,True))
