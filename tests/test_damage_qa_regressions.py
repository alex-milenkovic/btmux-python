"""Source discrepancies reproduced by independent damage CLI verification."""
from dataclasses import replace
import unittest
from unittest.mock import patch
from core.game_loop import GameEngine
from core.randomness import use_source
from entities.mech import Mech, Location, MechStatus, MoveType
from entities.crittypes import Special, i2special
from entities.weapon import get_weapon
from systems import combat, failures, damage_commands, physical
from tests.test_damage_failures import Draws

class DamageQARegressions(unittest.TestCase):
    def setUp(self):
        self.engine=GameEngine()
        self.attacker=Mech.create_test_mech();self.target=Mech.create_test_mech()
        for unit in (self.attacker,self.target):
            self.engine.register_entity(unit)
            for section in unit.sections:
                section.armor=section.armor_orig=100
                section.internal=section.internal_orig=100
                for slot in section.criticals:slot.type=0

    def test_normal_weapon_hit_uses_damage_entry_and_accounting(self):
        result=combat.AttackResult()
        draws=Draws(7)
        with use_source(draws):
            combat._apply_single_hit(result,self.attacker,self.target,get_weapon('IS.MediumLaser'),Location.CTORSO,False,False,5,0,self.engine)
        self.assertEqual((5,5,5),(result.damage_dealt,self.attacker.damage_inflicted,self.target.damage_taken))
        self.assertEqual(['damage_entry'],[d[0] for d in draws.calls])

    def test_classic_hit_arc_uses_owning_engine_configuration(self):
        self.engine.hit_arcs=1
        with patch('systems.combat.find_attack_direction',return_value=46):
            self.assertEqual(combat.HitGroup.RIGHTSIDE,combat.determine_hit_group(self.attacker,self.target))
        self.engine.hit_arcs=0
        with patch('systems.combat.find_attack_direction',return_value=46):
            self.assertEqual(combat.HitGroup.FRONT,combat.determine_hit_group(self.attacker,self.target))

    def test_dodamage_translates_all_c_table_direction_codes(self):
        expected=[combat.HitGroup.BACK,combat.HitGroup.LEFTSIDE,combat.HitGroup.RIGHTSIDE,combat.HitGroup.FRONT,combat.HitGroup.BACK,combat.HitGroup.LEFTSIDE]
        with patch('systems.combat.get_hit_location',return_value=(Location.CTORSO,False)) as location:
            with use_source(Draws(*([7]*9))):
                for direction in range(16,22):damage_commands.dodamage(self.target,1,1,direction)
        self.assertEqual(expected,[call.args[1] for call in location.call_args_list])

    def test_failure_range_uses_source_extension_and_submerged_section(self):
        weapon=replace(get_weapon('IS.MediumLaser'),range_long=15,range_medium=9,range_long_water=5,range_medium_water=3)
        self.assertEqual(9,failures.percentage_failure(weapon,'RANGE',50,self.target,4).modifier)
        self.engine.erange=0
        self.assertEqual(7,failures.percentage_failure(weapon,'RANGE',50,self.target,4).modifier)
        self.engine.erange=1;self.target.z=-1
        self.assertEqual(3,failures.percentage_failure(weapon,'RANGE',50,self.target,5).modifier)
        self.assertEqual(9,failures.percentage_failure(weapon,'RANGE',50,self.target,4).modifier)

    def test_physical_normal_location_preserves_critical_flag(self):
        self.attacker.move_type=MoveType.NONE
        # Non-mech physical location dispatch uses FindTargetHitLoc.
        from entities.mech import UnitType
        self.attacker.unit_type=UnitType.MW
        self.attacker.z=self.target.z+1
        self.target.sections[4].criticals[0].type=i2special(Special.LIFE_SUPPORT)
        with patch('systems.hit_locations.target_hit_location',return_value=(Location.CTORSO,False,True)):
            with use_source(Draws(7,8,0)):
                physical.physical_damage(self.attacker,self.target,10,physical.PhysicalAttackType.PUNCH,0)
        self.assertTrue(self.target.sections[4].criticals[0].firemode&1)
