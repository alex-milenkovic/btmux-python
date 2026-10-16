"""Historical fighter tables and the source armor chance boundaries."""
from unittest.mock import patch
from tests.movement_fixture import MovementTestCase
from entities.mech import UnitType as U,MoveType as M,CritStatus as C
from systems import hit_locations as h
from systems.combat import HitGroup as H


class FighterTableTests(MovementTestCase):
    def setUp(self):
        super().setUp();self.unit.unit_type=U.AERO;self.unit.move_type=M.FLY
        for sec in self.unit.sections:sec.armor=80;sec.armor_orig=100

    def test_critproof_table_has_six_locations_and_no_effects(self):
        with patch.object(h,'number',side_effect=AssertionError('unexpected chance draw')):
            self.assertEqual([h.find_hit_location(self.unit,H.FRONT,r,profile='critproof')[0] for r in range(2,13)],
                             [4,0,3,2,0,0,0,1,3,0,4])
            self.assertEqual([h.find_hit_location(self.unit,H.BACK,r,profile='critproof')[0] for r in range(2,13)],
                             [5,3,3,2,5,3,5,1,3,3,5])

    def test_armor_gate_guaranteed_and_conditional_bands(self):
        for armor,threshold,result,domain in [(89,90,True,None),(90,90,True,(1,11)),
                (94,90,True,(1,11)),(95,90,False,None),(99,99,True,(1,11)),(100,90,False,(1,71))]:
            with self.subTest(armor=armor,threshold=threshold),patch.object(h,'number',return_value=6) as dice:
                self.unit.sections[0].armor=armor
                self.assertEqual(h.crittable(self.unit,0,threshold),result)
                if domain:dice.assert_called_once_with('crittable_chance',*domain)
                else:dice.assert_not_called()

    def test_fasa_and_legacy_call_control_and_defer_engine_critical(self):
        for profile in ('legacy','FASA'):
            self.unit.clear_crit_status(C.SPINNING)
            self.assertEqual(h.find_hit_location(self.unit,H.BACK,3,profile=profile),(3,False))
            self.assertTrue(self.unit.has_crit_status(C.SPINNING))
            self.assertEqual(h.find_hit_location(self.unit,H.LEFTSIDE,12,profile=profile),(5,True))

    def test_empty_sections_route_only_to_fuselage(self):
        self.assertEqual([h.transfer_target(self.unit,i) for i in range(6)],[3,3,3,-1,3,3])
