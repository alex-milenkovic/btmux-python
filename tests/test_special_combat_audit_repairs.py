"""Source boundaries and connected effects from the Special Combat repair pass."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.events import EventType as E
from core.randomness import use_source
from entities.mech import AmmoMode as A, MechStatus2 as S2
from entities.pilot import Pilot
from entities.weapon import get_weapon
from entities.map_objects import bits_for
from physics.hexmath import ZSCALE, hex_to_float
from systems import artillery, combat_equipment as equipment, mines
from tools.combat_resolution import CombatSession


class SpecialCombatAuditTest(unittest.TestCase):
    def setUp(self):
        self.session=CombatSession({'actions':[]})
        self.unit=self.session.units['u']
        self.board=self.session.map

    def test_signature_notices_precede_queue_and_status(self):
        unit=self.unit;unit.specials2=0x10
        original=equipment.reply;queue_states=[]
        def capture(*args,**kwargs):
            queue_states.append(self.session.engine.events.has_event_type_data(E.NSS,unit))
            return original(*args,**kwargs)
        with patch.object(equipment,'reply',capture):
            self.assertTrue(equipment.command(unit,'nullsig')['accepted'])
        self.assertEqual([False],queue_states)
        flag_states=[]
        with patch.object(equipment,'notify',side_effect=lambda *args:flag_states.append(bool(unit.status2&S2.NULLSIGSYS_ON))):
            equipment.signature_event(SimpleNamespace(data=unit,data2=('nullsig',True)))
        self.assertEqual([False],flag_states)
        self.assertTrue(unit.status2&S2.NULLSIGSYS_ON)

    def test_self_destruct_signed_countdown_and_override_abort(self):
        unit=self.unit
        equipment.explode_event(SimpleNamespace(data=unit,data2=0))
        self.assertIn('Self-destruction in -1 second..',unit.movement_messages)
        self.session.engine.events.cancel_by_type_and_data(E.EXPLODE,unit)
        pilot=unit.pilot;observed=[]
        original=equipment.notify
        def notice(owner,text):
            observed.append((text,owner.pilot));original(owner,text)
        with patch.object(equipment,'notify',notice):
            self.assertTrue(equipment.explode(unit,'reactor override',caller=pilot,wizard=True)['accepted'])
        # The expected-time notice is delivered while the pilot still controls the unit.
        self.assertIs(pilot,observed[-1][1])
        self.assertIsNone(unit.pilot)
        self.assertTrue(equipment.explode(unit,'stop override',caller=pilot,wizard=True)['accepted'])
        self.assertIn('stopped the self-destruction sequence.',unit.debug_messages[-1])

    def test_artillery_scatter_constant_and_mode_message_precedence(self):
        weapon=get_weapon('IS.Sniper')
        def shot(mode=0,hit=True):
            return artillery.ArtilleryShot(3,3,4,4,weapon.index,mode,hit,self.unit._id,self.board)
        with patch.object(artillery,'number',side_effect=[90,2]),patch.object(artillery,'artillery_hit_hex') as hit:
            artillery.artillery_hit(self.session.engine,shot(hit=False))
        self.assertEqual((3,5),hit.call_args_list[0].args[3:5])
        for mode,fragment in ((A.SMOKE_MODE,'hits $h,'),(A.CLUSTER_MODE|A.SMOKE_MODE,"hits $H's"),(A.MINE_MODE|A.SMOKE_MODE,'hits $H!')):
            with patch.object(artillery,'artillery_hit_hex'),patch.object(artillery,'artillery_cluster_hit'):
                artillery.artillery_hit(self.session.engine,shot(mode))
            self.assertIn(fragment,self.board.combat_messages[-1]['message'])

    def test_spotter_uses_height_and_notifies_before_adjustment(self):
        from systems.notifications import MECHSTARTED
        from systems.targeting import find_range
        spotter=self.session.units['v'];self.unit.spotter=spotter._id
        self.unit.targ_x=self.unit.targ_y=4;spotter.fz=10*ZSCALE
        seen=[];before=self.unit.fire_adjustment
        with patch('systems.los.in_line_of_sight',return_value=True) as los, \
             patch('systems.notifications.identity',return_value='friendly [ab]'), \
             patch('systems.notifications.mech_notify',side_effect=lambda unit,aud,text:seen.append((aud,text,self.unit.fire_adjustment))):
            artillery.artillery_friendly_adjustment(self.session.engine,self.unit._id,self.board,4,4)
        fx,fy=hex_to_float(4,4)
        self.assertEqual(find_range(spotter.fx,spotter.fy,spotter.fz,fx,fy,0),los.call_args.args[-1])
        self.assertEqual([(MECHSTARTED,'friendly [ab] sent you some trajectory-correction data.',before),
                          (MECHSTARTED,'You provide friendly [ab] with information about the miss.',before)],seen)
        self.assertEqual(before+1,self.unit.fire_adjustment)

    def test_mine_insertion_and_pre_blast_coordinate_deletion(self):
        for _ in range(2):mines.add_mine(self.board,4,4,10)
        self.assertEqual(2,len(self.board.mines));self.assertNotIn((4,4),self.board.mine_hexes)
        mines.recalculate_minefields(self.board)
        self.assertIsNone(mines.add_mine(self.board,4,4,10))
        mine=mines.map_add_mine(self.board,'4 4 Command 10 7')
        bits_for(self.board).set(4,4,2)
        hangar_bit=bits_for(self.board).query(4,4,2)
        seen=[]
        with patch('systems.notifications.hex_broadcast',side_effect=lambda *args:seen.append('hex')), \
             patch.object(mines,'blast_hit_hexes',side_effect=lambda *args,**kwargs:seen.append(((4,4) in self.board.mine_hexes,bits_for(self.board).query(4,4,1),len(self.board.mines)))):
            mines.make_mine_explode(self.unit,self.board,mine,0,0,None)
        self.assertEqual(['hex',(False,0,3)],seen)
        self.assertEqual([],self.board.mines)
        self.assertEqual(hangar_bit,bits_for(self.board).query(4,4,2))

    def test_trigger_channel_then_action_and_positive_id_gate(self):
        mine=mines.map_add_mine(self.board,'4 4 Trigger 1 2')
        listener=Pilot();sink=self.session.engine.effects;sink.subscribe('MineTriggers',listener)
        seen=[]
        sink.hooks[(self.unit._id,'AMINETRIGGER')]=lambda actor,victim:seen.append(listener.inbox[-1])
        self.assertFalse(mines.make_mine_explode(self.unit,self.board,mine,4,4,'fall'))
        self.assertTrue(mines.make_mine_explode(self.unit,self.board,mine,4,4,'land'))
        self.assertEqual([f'#{self.unit._id} {self.unit.contact_id} activated trigger at 4,4.'],seen)
        self.assertTrue(self.unit.action_requests[-1]['applied'])
        self.assertIn(mine,self.board.mines)
        self.unit._id=0
        mines.make_mine_explode(self.unit,self.board,mine,4,4,'step')
        self.assertEqual(1,len(seen));self.assertEqual(2,len(listener.inbox))

    def test_admin_width_notice_order_and_discovery_actor_xp(self):
        actor=Pilot();actor._id=501
        with patch.object(mines,'recalculate_minefields') as recalc:
            mine=mines.map_add_mine(self.board,'4 4 Standard 65535',creator=501,caller=actor)
            self.assertEqual(-1,mine.strength)
            self.assertEqual('Standard mine added to (4,4) (strength: 65535 / extra: 0)',actor.inbox[-1])
            recalc.assert_called_once()
        mines.recalculate_minefields(self.board)
        with use_source(lambda name,low,high,fallback:high):
            self.assertFalse(mines.show_mines_in_hex(self.unit,1,4,4,caller=actor))
            self.assertIn('nothing else of interest',actor.inbox[-1])
            self.unit.in_character=True;self.unit.pilot._id=51;self.unit.pilot.location=self.unit._id
            self.session.engine.sim_now=61
            self.assertTrue(mines.show_mines_in_hex(self.unit,1,4,4,caller=actor))
        self.assertTrue(self.unit.per)
        self.assertEqual('Perception',self.unit.xp_requests[-1]['skill'])
        self.assertTrue(self.unit.xp_requests[-1]['applied'])

    def test_remote_vibra_uses_integer_radius_and_unknown_type_has_no_coverage(self):
        self.unit.rtons=50*1024
        mine=mines.map_add_mine(self.board,'4 4 Vibra 10 32')
        with patch.object(mines,'make_mine_explode') as detonate:
            mines.possible_mine_explosion(self.unit,self.board,3,3,'step')
            detonate.assert_not_called()
        mine.type=99;mines.recalculate_minefields(self.board)
        self.assertEqual(set(),self.board.mine_hexes)
