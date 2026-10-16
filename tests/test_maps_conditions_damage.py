import unittest
from unittest.mock import patch
from entities.mech import Mech,UnitType,Location as L,MechStatus as S,FireMode as F
from entities.crittypes import i2special,Special
from systems.damage import destroy_parts,breach_location,reactor_explosion
from tests.test_maps_objects import fixture


class ConditionDamageTest(unittest.TestCase):
    def test_mechwarrior_reaches_common_actuator_normalization(self):
        unit=Mech.create_test_mech(); unit.unit_type=UnitType.MW
        unit.pilot_skill_base=9
        destroy_parts(None,unit,L.CTORSO)
        self.assertEqual(0,unit.pilot_skill_base)

    def test_biped_arm_returns_before_normalization_and_leg_cancels_stand(self):
        from core.events import EventType
        engine,board=fixture(); unit=Mech.create_test_mech(); unit.map=board; unit._engine=engine
        unit.sections[L.LARM].basetohit=7
        destroy_parts(None,unit,L.LARM,engine)
        self.assertEqual(7,unit.sections[L.LARM].basetohit)
        stand=engine.events.schedule(20,EventType.STAND,lambda event:None,unit)
        with patch('physics.jump.mech_falls'),patch('systems.sensors.los_broadcast') as broadcast:
            destroy_parts(unit,unit,L.LLEG,engine)
        self.assertTrue(stand.zombie)
        broadcast.assert_called_with(unit,'crashes to the ground!')

    def test_battlesuit_head_slot_breach_does_not_kill_occupants_or_auto_fall(self):
        engine,board=fixture(); unit=Mech.create_test_mech(); unit.unit_type=UnitType.BSUIT
        unit.map=board; unit._engine=engine; unit.status|=S.CONDITIONS
        with patch('systems.damage._kill_mech_contents') as occupants,patch('systems.damage.destroy_mech') as destroy:
            destroy_parts(unit,unit,L.HEAD,engine,breach=True,disable=True)
        occupants.assert_not_called(); destroy.assert_not_called()

    def test_breach_names_section_and_exposes_mech_cockpit(self):
        engine,board=fixture(); unit=Mech.create_test_mech(); unit.map=board; unit._engine=engine
        unit.status|=S.UNDERSPECIAL|S.UNDERVACUUM
        with patch('systems.damage._kill_mech_contents'),patch('systems.damage.destroy_mech'):
            self.assertTrue(breach_location(unit,unit,L.HEAD))
        self.assertIn('Your Head has been breached!',unit.movement_messages)
        self.assertIn('You are exposed to vacuum!',unit.movement_messages)

    def test_last_jet_uses_speed_and_passes_engine_to_fall(self):
        engine,board=fixture(); unit=Mech.create_test_mech(); unit.map=board; unit._engine=engine
        unit.jump_mp=4; unit.jump_speed=1; unit.status|=S.JUMPING
        unit.sections[L.LTORSO].criticals[0].type=i2special(Special.JUMP_JET)
        with patch('physics.jump.mech_falls') as fall:
            destroy_parts(unit,unit,L.LTORSO,engine)
        self.assertTrue(fall.called)
        self.assertIn('Losing your last Jump Jet you fall from the sky!!!!!',unit.movement_messages)

    def test_reactor_supplies_engine_for_all_section_destruction(self):
        engine,board=fixture(); unit=Mech.create_test_mech(); unit.map=board; unit._engine=engine
        with patch('systems.damage.destroy_section') as destroy,patch('systems.damage.blast_hit_hexes_f'),patch('systems.piloting.head_hit_mw_damage'),patch('systems.sensors.scramble_infra_and_liteamp'):
            reactor_explosion(unit,unit,engine)
        self.assertEqual([L.CTORSO,L.LTORSO,L.RTORSO,L.LLEG,L.RLEG,L.HEAD],[call.args[2] for call in destroy.call_args_list])
        self.assertTrue(all(call.args[3] is engine for call in destroy.call_args_list))
