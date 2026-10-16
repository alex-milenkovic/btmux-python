"""Recovered Aerospace callback boundaries omitted by the original port."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from tests import test_aerospace_flight as flight_tests, test_aerospace_bays as bay_tests
from entities.mech import Mech, UnitType as U, MechStatus as S, MechStatus2 as S2
from entities.map import LIGHT_FOREST
from entities.map_objects import MapObject
from physics import aerospace as flight
from systems import dropships, map_links, swarm
from tools.aerospace import AerospaceSession


class AerospaceAuditRepairs(unittest.TestCase):
    def flight_fixture(self):
        f=flight_tests.FlightTests('runTest');f.setUp()
        return f.engine,f.board,f.unit

    def test_fighter_engine_guard_and_historical_fortification(self):
        engine,board,unit=self.flight_fixture()
        unit.set_status(S.LANDED);unit.set_status2(S2.FORTIFIED);unit.speed=40
        unit.sections[5].armor=0
        self.assertEqual(flight.takeoff(engine,unit),(False,'The engines are dead!'))
        unit.sections[5].armor=10
        self.assertTrue(flight.takeoff(engine,unit)[0])

    def test_lz_profile_and_axis_prefilter(self):
        engine,board,unit=self.flight_fixture()
        engine.blzmapmode=1
        board.set_terrain(unit.x,unit.y,LIGHT_FOREST)
        self.assertEqual(flight.improper_lz(unit),1)
        board.map_objects[9]=[MapObject(x=unit.x+4,y=unit.y,datai=3,datac=0)]
        with patch('systems.map_links.find_range',return_value=0) as distance:
            self.assertFalse(map_links.blocked_lz(unit,board,unit.x,unit.y))
            distance.assert_not_called()
            unit.unit_type=U.MECH
            self.assertTrue(map_links.blocked_lz(unit,board,unit.x,unit.y))

    def test_control_notices_observe_source_state_and_precede_schedule(self):
        engine,board,unit=self.flight_fixture()
        trace=[]
        with patch('physics.aerospace.notify',side_effect=lambda u,m:trace.append(('notice',u.desired_speed,u.desired_angle)) or m), patch('physics.aerospace.maybe_move',side_effect=lambda e,u:trace.append(('move',))):
            self.assertTrue(flight.thrust(engine,unit,'20')[0])
            self.assertTrue(flight.vheading(unit,'30')[0])
        self.assertEqual(trace,[('notice',20,0),('move',),('notice',20,0)])
        self.assertEqual(unit.desired_angle,30)

    def test_private_queries_and_bay_confirmation_deliver_once(self):
        engine,board,unit=self.flight_fixture()
        unit.command_actor=unit.pilot
        session=SimpleNamespace(engine=engine,maps={})
        with patch('systems.notifications.personal_notify') as notice:
            for command in ('thrust','climb','dive','createbays'):
                self.assertTrue(AerospaceSession.command(session,unit,command,'')['ok'])
        self.assertEqual(notice.call_count,4)
        self.assertTrue(all(call.args[0] is unit.pilot for call in notice.call_args_list))
        self.assertEqual(notice.call_args.args[1],'0 bay(s) set up!')

    def test_entry_uses_voluntary_historical_detachment(self):
        f=bay_tests.BayTests('runTest');f.setUp()
        unit=f.unit
        suit=Mech.create_test_mech();suit.unit_type=U.BSUIT
        suit.set_status(S.STARTED);suit.swarm_target=unit._id
        suit.set_status2(S2.UNIT_MOUNTING);unit.set_status2(S2.UNIT_MOUNTED)
        f.board.add_mech(suit);f.engine.register_entity(suit)
        unit.vertical_speed=f.ship.vertical_speed+10.9
        self.assertTrue(dropships.enter_bay(unit)[0])
        with patch('systems.piloting.make_piloting_roll') as roll:
            f.engine.events.run_by_type(__import__('core.events',fromlist=['EventType']).EventType.ENTER_HANGAR)
            roll.assert_not_called()
        self.assertEqual(suit.swarm_target,-1)
        self.assertTrue(suit.has_status2(S2.UNIT_MOUNTING))
        self.assertTrue(unit.has_status2(S2.UNIT_MOUNTED))
        self.assertTrue(all(s.recycle==20 for s in suit.sections if s.internal))
        self.assertIs(unit.map,f.bay)
        self.assertEqual(dropships.matching_ships(SimpleNamespace(map=None)),[])

    def turret_fixture(self):
        from tests import test_aerospace_turrets
        f=test_aerospace_turrets.TurretTests('runTest');f.setUp()
        f.unit.unit_type=U.DS
        return f

    def test_turret_original_actor_guards_delivery_and_parse_order(self):
        from systems import turrets
        f=self.turret_fixture();u=f.unit;actor=f.actor
        u.set_status(S.UNCONSCIOUS);u.pilot=None
        for command,args in [('bearing','1 1'),('range','1 1'),('eta','1 1 ignored'),('findcenter','')]:
            self.assertTrue(turrets.command(f.engine,f.turret,actor,command,args)['ok'],command)
        self.assertEqual(sum(m.startswith('Bearing to ') for m in actor.inbox),1)
        self.assertEqual(sum('Range to  ' in m for m in actor.inbox),1)
        self.assertEqual(sum('Current hex:' in m for m in actor.inbox),1)
        u.in_character=True
        # SIGHT uses MECH_USUAL and reaches mount validation before extra args.
        result=turrets.command(f.engine,f.turret,actor,'sight','999 bad extra surplus')
        self.assertIn('Illegal Weapon Number',result['message'])
        self.assertEqual(actor.inbox[-1],result['message'])

    def test_navigation_defined_edges_dark_integer_z_and_actor_preferences(self):
        from systems import turrets
        from systems.observation import navigation
        f=self.turret_fixture();u=f.unit
        self.assertTrue(navigation(u,'bearing',f'{f.board.map_width} 1 1 999',caller=f.actor)['ok'])
        f.board.flags|=32;u.z=2;u.fz=2*64.5+32.25
        result=navigation(u,'range',f'{u.x} {u.y}',caller=f.actor)
        self.assertGreater(result['range'],0)
        self.assertEqual(result['ground_range'],0)
        # Recovered map flag 32 IS darkness (map.h:71,109).
        from systems.map_display import forced_los
        self.assertTrue(forced_los(u))
        f.actor.tacsize='5 5';u.tacsize='24 40'
        f.board.flags=0
        result=turrets.command(f.engine,f.turret,f.actor,'tactical','')
        self.assertTrue(result['ok']);self.assertEqual(result['window'][2:],[5,5])
        self.assertEqual(f.actor.inbox[-len(result['lines']):],result['lines'])

    def test_original_player_heat_glyphs_and_historical_h_branch(self):
        from systems.status_display import status,heat_bar
        from core.attributes import AttributeStore
        f=self.turret_fixture();u=f.unit
        f.engine.attributes=AttributeStore()
        f.engine.attributes.set(f.actor._id,'A_HEATCHARS','[01234567')
        u.plus_heat=80;u.minus_heat=2
        text=heat_bar(u,f.actor)['text']
        for glyph in '1234567':self.assertIn(glyph,text)
        self.assertNotIn('heat_scale',status(u,'H',caller=f.actor))
        u.unit_type=U.MECH
        self.assertIn('heat_scale',status(u,'H',caller=f.actor))
        f.engine.attributes.set(f.actor._id,'A_HEATCHARS','bad')
        self.assertNotIn('heat_scale',status(u,'H',caller=f.actor))

    def test_historical_recycle_waits_for_full_interval(self):
        from core.game_loop import recycle_weaponry
        from entities.crittypes import i2weapon
        from entities.weapon import get_weapon
        from systems.enhanced_crits import set_part_temp_nuke,part_temp_nuke,FAIL_DESTROYED
        engine,board,unit=self.flight_fixture()
        slot=unit.sections[0].criticals[0]
        slot.type=i2weapon(get_weapon('IS.MediumLaser').index);slot.data=5
        set_part_temp_nuke(slot,FAIL_DESTROYED)
        unit.last_weapon_recycle=engine.muxevent_tick-1
        recycle_weaponry(engine,unit)
        self.assertEqual((slot.data,part_temp_nuke(slot)),(5,FAIL_DESTROYED))
        unit.last_weapon_recycle=engine.muxevent_tick-5
        recycle_weaponry(engine,unit)
        self.assertEqual((slot.data,part_temp_nuke(slot)),(0,0))
        self.assertEqual(engine.arc_override,0)


if __name__=='__main__':
    unittest.main()
