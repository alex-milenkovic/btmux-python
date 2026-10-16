import unittest
from tools.core_simulation import CoreSession
from core.events import EventType


def finite(**streams):
    return dict(streams=dict(visibility_change=[0]*100,failure_generic_chance=[5000]*10,
                            damage_entry=[7]*10,tow_rolls=[7]*10,**streams))


class CoreWorkflowsTest(unittest.TestCase):
    def test_actual_head_damage_failed_recovery_extends_then_recovers_once(self):
        session = CoreSession({'random':finite(character_d6=[1,1,1,1,6,6]),'actions':[]})
        session.action({'op':'command','name':'dodamage','args':[1,1,7]})
        session.action({'op':'advance','seconds':30})
        unit = session.units['u']
        self.assertTrue(unit.is_unconscious)
        self.assertEqual([60],[e.tick for e in session.engine.events.pending_events(EventType.RECOVERY,unit)])
        session.action({'op':'advance','seconds':30})
        self.assertFalse(unit.is_unconscious)
        self.assertEqual(1,unit.movement_messages.count('The pilot regains consciousness!'))

    def test_damage_history_causes_one_fall_with_actual_five_point_damage(self):
        session = CoreSession({'units':[{'name':'u','sections':[{'index':4,'armor':100,'armor_orig':100}]}],
            'random':finite(pilot_rolls=[2,12],fall_directions=[1],hit_location_rolls=[7]),'actions':[]})
        session.action({'op':'command','name':'dodamage','args':[20,20,4]})
        self.assertEqual(20,sum(node['amount'] for node in session.units['u'].stagger_damage_list))
        session.action({'op':'advance','seconds':5})
        unit = session.units['u']
        self.assertEqual((True,25,75),(unit.is_fallen,unit.damage_taken,unit.sections[4].armor))
        self.assertEqual(1,sum('loose the battle with gravity' in message for message in unit.movement_messages))

    def test_repeated_actual_vehicle_criticals_clear_crew_once(self):
        session = CoreSession({'units':[{'name':'u','class':'VEH_GROUND','movement':'TRACK'}],
            'config':{'fasaadvvhlcrit':1},'random':finite(critical_rolls=[8,8],vehicle_critical_roll=[8,8]),'actions':[]})
        for _ in range(2): session.action({'op':'command','name':'damage-section','args':['Left',1,0,1]})
        unit = session.units['u']
        self.assertTrue(unit.crew_stunned)
        self.assertEqual(2,len(session.engine.events.pending_events(EventType.UNSTUN_CREW,unit)))
        session.action({'op':'advance','seconds':60})
        self.assertFalse(unit.crew_stunned)
        self.assertEqual(1,unit.movement_messages.count("Your head clears and you're able to control your vehicle again."))

    def test_foreign_actor_cannot_fire_in_character_unit(self):
        session = CoreSession({'units':[{'name':'u','in_character':True,'weapons':['IS.SmallLaser']},
                                       {'name':'v','at':[3,2,0],'team':2}],'actions':[]})
        result = session.action({'op':'command','name':'fire','args':[0,'01'],'actor':{'id':20000}})
        self.assertFalse(result['accepted'])
        self.assertIn('only the pilot',result['text'])
