"""Fighter armor depletion and later routing are separate damage events."""
from unittest.mock import patch
from tests.movement_fixture import MovementTestCase
from entities.mech import UnitType as U, MoveType as M, MechStatus as S, SectionConfig
from entities.crittypes import i2weapon
from entities.weapon import get_weapon
from core.events import EventType as E
from systems.combat import apply_damage_with_transfer as hit


class FighterDamageTests(MovementTestCase):
    def setUp(self):
        super().setUp();u=self.unit;u.unit_type=U.AERO;u.move_type=M.FLY
        u.in_character=False;u.si=0;u.speed=u.max_speed=60;u.vertical_speed=5
        for s in u.sections:s.armor=s.armor_orig=30;s.internal=s.internal_orig=10
        u.sections[0].criticals[0].type=i2weapon(get_weapon('IS.MediumLaser').index)

    def test_first_wing_depletion_discards_excess_and_keeps_equipment(self):
        u=self.unit;u.sections[0].armor=3
        hit(u,0,8,engine=self.engine)
        self.assertEqual((u.sections[0].armor,u.sections[0].internal,u.sections[3].armor),(0,10,30))
        self.assertEqual(u.sections[0].criticals[0].firemode,0)
        self.assertFalse(u.is_destroyed)
        hit(u,0,8,engine=self.engine)
        self.assertEqual(u.sections[3].armor,22)

    def test_fuselage_survives_first_depletion_then_dies_even_with_si(self):
        u=self.unit;u.si=50;u.sections[3].armor=3
        hit(u,3,8,engine=self.engine);self.assertFalse(u.is_destroyed)
        hit(u,3,1,engine=self.engine);self.assertTrue(u.is_destroyed)

    def test_cockpit_injury_only_after_routing_and_exact_depletion_kills(self):
        u=self.unit;u.sections[4].armor=3
        with patch('systems.piloting.head_hit_mw_damage') as injury:
            hit(u,4,3,engine=self.engine)
            injury.assert_called_once_with(u,None,1)
        self.assertTrue(u.is_destroyed)
        u.clear_status(S.DESTROYED)
        with patch('systems.piloting.head_hit_mw_damage') as injury:
            hit(u,4,1,engine=self.engine);injury.assert_not_called()
        self.assertEqual(u.sections[3].armor,29)

    def test_engine_depletion_has_one_airborne_effect(self):
        u=self.unit;u.sections[5].armor=3
        hit(u,5,3,engine=self.engine)
        self.assertEqual((u.speed,u.max_speed,u.vertical_speed),(0,0,0))
        self.assertTrue(u.is_fallen);self.assertEqual(self.engine.events.count_type(E.FALL),1)
        hit(u,5,2,engine=self.engine)
        self.assertEqual(u.sections[3].armor,28)
        self.assertEqual(self.engine.events.count_type(E.FALL),1)

    def test_explicit_transfer_and_internal_containment(self):
        u=self.unit;u.sections[0].armor=3
        hit(u,0,8,engine=self.engine,transfer=True)
        self.assertEqual(u.sections[3].armor,25)
        u.sections[0].armor=3;u.sections[3].armor=30
        hit(u,0,8,engine=self.engine,internal=True)
        self.assertEqual(u.sections[3].armor,30)
        u.sections[0].armor=3;u.sections[0].config|=SectionConfig.CASE_TECH
        hit(u,0,8,engine=self.engine,internal=True,transfer=True)
        self.assertEqual(u.sections[3].armor,30)

    def test_shared_rear_remap_preserved(self):
        hit(self.unit,2,5,True,engine=self.engine)
        self.assertEqual((self.unit.sections[2].armor,self.unit.sections[3].armor),(30,25))

    def test_ammo_internal_entry_enables_fighter_transfer(self):
        from systems.criticals import apply_internal_damage_with_transfer
        u=self.unit;u.sections[0].armor=3
        apply_internal_damage_with_transfer(u,0,8,engine=self.engine)
        self.assertEqual((u.sections[0].armor,u.sections[3].armor),(0,25))
        self.assertEqual([s.internal for s in u.sections[:6]],[10]*6)
