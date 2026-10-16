import unittest
from types import SimpleNamespace
from core.game_loop import GameEngine
from core.events import EventType as E
from entities.mech import Mech,MechStatus as S,Specials,MoveType
from entities.map import GameMap
from systems.occupants import pickup
from systems.towing import attach_cables,detach_cables,dropoff


class TowingCommandTests(unittest.TestCase):
    def setUp(self):
        self.engine=GameEngine();self.board=GameMap(10,10);self.board._id=10;self.engine.register_entity(self.board)
        self.actor=SimpleNamespace(_id=7,god=False,wizard=False)
        self.units=[]
        for identity in (12,13,14):
            unit=Mech.create_test_mech();unit._id=identity;unit.contact_id=str(identity);unit._engine=self.engine
            unit.team=1;unit.in_character=True;unit.x=unit.y=2;unit.map=self.board;unit.mapindex=10
            unit.measured_mass=unit.tonnage*1024;unit.cargo_inventory=[];self.board.add_mech(unit);self.engine.register_entity(unit);self.units.append(unit)
        self.operator,self.tower,self.load=self.units
        from entities.crittypes import i2special,Special
        for loc in (0,1):
            self.operator.sections[loc].criticals[0].type=i2special(Special.SHOULDER_OR_HIP)
            self.operator.sections[loc].criticals[3].type=i2special(Special.HAND_OR_FOOT_ACTUATOR)
        self.operator.status|=S.STARTED;self.operator.pilot=self.actor
        from systems.sensors import update_los_info
        update_los_info(self.board)
        from systems.targeting import plos_event
        self.operator.pnum_seen=2
        plos_event(SimpleNamespace(data=self.operator,data2=self.engine))
    def test_pickup_sets_existing_relation_and_source_target_flags(self):
        self.tower.status|=S.HULLDOWN;self.tower.tank_crit_status=4
        result=pickup(self.operator,self.actor,'13')
        self.assertTrue(result['ok'],result)
        self.assertIs(self.operator.towed_unit,self.tower);self.assertEqual(self.operator.carrying,13)
        self.assertTrue(self.tower.has_status(S.TOWED|S.FALLEN));self.assertFalse(self.tower.has_status(S.HULLDOWN))
        self.assertFalse(self.tower.tank_crit_status&4)
    def test_intact_enemy_refused_by_pickup_but_allowed_by_cables(self):
        self.load.team=2
        self.assertFalse(pickup(self.operator,self.actor,'14')['ok'])
        self.assertTrue(attach_cables(self.operator,self.actor,'13 14')['ok'])
        self.assertIs(self.tower.towed_unit,self.load)
    def test_pickup_arm_and_speed_boundaries(self):
        self.operator.speed=1.01;self.assertFalse(pickup(self.operator,self.actor,'13')['ok'])
        self.operator.speed=1;self.operator.vertical_speed=-1
        self.assertTrue(pickup(self.operator,self.actor,'13')['ok'])
    def test_cables_keep_real_position_and_require_exact_stationary(self):
        self.tower.speed=.01;self.assertFalse(attach_cables(self.operator,self.actor,'13 14')['ok'])
        self.tower.speed=0;self.load.fx=42
        self.assertTrue(attach_cables(self.operator,self.actor,'13 14')['ok']);self.assertEqual(self.load.fx,42)
    def test_detach_allows_enemy_and_moving_tower_without_fall_or_fz_write(self):
        self.tower.carrying=14;self.tower.towed_unit=self.load;self.load.status|=S.TOWED
        self.tower.team=2;self.tower.speed=5;self.load.z=3;self.load.fz=37
        result=detach_cables(self.operator,self.actor,'13');self.assertTrue(result['ok'],result)
        self.assertEqual(self.load.z,0);self.assertEqual(self.load.fz,37);self.assertFalse(self.engine.has_event(E.FALL,self.load))
    def test_dropoff_uses_shared_release_and_schedules_fall(self):
        self.operator.carrying=13;self.operator.towed_unit=self.tower;self.tower.z=3;self.tower.status|=S.TOWED|S.FALLEN
        self.assertTrue(dropoff(self.operator,self.actor)['ok'])
        event=self.engine.events.pending_events(E.FALL,self.tower)[0]
        self.assertEqual((event.tick,event.data2),(3,-1));self.assertTrue(self.tower.is_fallen)
    def test_missing_load_clears_relation_before_refusal(self):
        self.tower.carrying=999
        self.assertFalse(detach_cables(self.operator,self.actor,'13')['ok']);self.assertEqual(self.tower.carrying,-1)
    def test_pickup_releases_existing_load_with_its_debug_request(self):
        self.tower.carrying=14;self.tower.towed_unit=self.load;self.load.status|=S.TOWED
        self.assertTrue(pickup(self.operator,self.actor,'13')['ok'])
        self.assertFalse(self.load.has_status(S.TOWED));self.assertEqual(self.tower.carrying,-1)
        self.assertIn('#13 has dropped off #14', self.tower.debug_messages)
        self.assertTrue(any(item['channel'] == 'MechDebugInfo' and item['text'] == '#13 has dropped off #14'
                            for item in self.engine.effects.channels))

    def test_release_and_detach_use_signed_floor_and_source_fall_notices(self):
        from unittest.mock import patch
        from entities.map import WATER
        self.board.set_terrain(2,2,WATER);self.board.set_elevation(2,2,3)
        self.tower.carrying=14;self.tower.towed_unit=self.load
        result=detach_cables(self.operator,self.actor,'13')
        self.assertTrue(result['ok']);self.assertEqual(self.load.z,-3)
        self.operator.carrying=13;self.operator.towed_unit=self.tower;self.tower.z=0
        with patch('systems.sensors.los_broadcast') as broadcast,patch('systems.notifications.mech_notify') as notify:
            self.assertTrue(dropoff(self.operator,self.actor)['ok'])
        self.assertTrue(self.engine.has_event(E.FALL,self.tower))
        self.assertTrue(any('closer to the ground' in c.args[-1] for c in notify.call_args_list))
        self.assertTrue(any('falls through the sky' in c.args[-1] for c in broadcast.call_args_list))

    def test_existing_mw_pickup_moves_real_character_while_already_carrying(self):
        from data.characters import CharacterStore
        from systems.occupants import Personnel
        from entities.mech import UnitType
        chars=CharacterStore();world=Personnel(self.engine,chars,used_store=901)
        for unit in self.units:world.add(unit,10)
        chars.create(8,'Stray',location=13);person=chars.actor(8);world.add(person,13)
        self.tower.unit_type=UnitType.MW
        self.operator.carrying=14;self.operator.towed_unit=self.load
        result=pickup(self.operator,self.actor,'13')
        self.assertTrue(result['ok'],result)
        self.assertEqual(person.location,12);self.assertEqual(self.operator.carrying,14)
        self.assertTrue(person.inbox)

    def test_live_movement_mirrors_until_shared_dropoff(self):
        from physics.movement import update_movement
        self.assertTrue(pickup(self.operator,self.actor,'13')['ok'])
        self.operator.speed=self.operator.desired_speed=10
        update_movement(self.operator)
        self.assertEqual((self.tower.fx,self.tower.fy),(self.operator.fx,self.operator.fy))
        self.assertTrue(dropoff(self.operator,self.actor)['ok'])
        old=(self.tower.fx,self.tower.fy)
        update_movement(self.operator)
        self.assertEqual((self.tower.fx,self.tower.fy),old)

if __name__=='__main__':unittest.main()
