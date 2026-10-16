"""Fighter critical consumers execute actual equipment and personnel effects."""
from tests.movement_fixture import MovementTestCase
from core.randomness import use_simulation
from data.characters import CharacterStore
from entities.mech import UnitType, MoveType, FireMode as F
from entities.crittypes import i2weapon, i2special, Special
from entities.weapon import get_weapon
from systems.occupants import Personnel
from systems.weapon_inventory import sync_weapon_states
from systems.damage_commands import lose_weapon
from systems.criticals import check_and_apply_criticals


class FighterCriticalTests(MovementTestCase):
    def setUp(self):
        super().setUp()
        self.unit.unit_type=UnitType.AERO;self.unit.move_type=MoveType.FLY
        for section in self.unit.sections:
            section.armor=section.armor_orig=30;section.internal=section.internal_orig=10
            for slot in section.criticals:slot.type=slot.data=slot.firemode=0

    def test_one_candidate_selects_and_destroys_first_duplicate(self):
        u=self.unit
        for slot in u.sections[0].criticals[:2]:slot.type=i2weapon(get_weapon('IS.MediumLaser').index)
        sync_weapon_states(u)
        with use_simulation(self.engine.randomness):lose_weapon(u,0)
        self.assertTrue(u.sections[0].criticals[0].firemode&F.DESTROYED_MODE)
        self.assertEqual(u.sections[0].criticals[1].firemode,0)

    def test_cockpit_critical_kills_actual_ic_contents(self):
        u=self.unit;u.in_character=True;store=CharacterStore()
        personnel=Personnel(self.engine,store)
        store.create(110,'pilot',location=u._id,connected=True)
        pilot=u.pilot=store.actor(110);personnel.add(pilot,u._id)
        u.sections[4].criticals[2].type=i2special(Special.COCKPIT)
        check_and_apply_criticals(u,4,1)
        self.assertTrue(u.is_destroyed);self.assertIsNone(u.pilot)
        self.assertFalse(pilot.alive)
        self.assertEqual(pilot.location,personnel.afterlife)
