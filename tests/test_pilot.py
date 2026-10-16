"""
Tests for the pilot entity and the FindPilot* skill resolution chain.

Tests cover:
- Pilot dataclass factory defaults (Python 4/5, C 6/6 - see test_constants.py)
- find_pilot_piloting / find_spilot_piloting / find_pilot_gunnery fallback steps
- Mech.pilot wiring into get_piloting_skill and piloting rolls
- Hot startup reading the pilot's piloting skill

Reference:
- BTMux btech/src/btech/mech.utils.c lines 580-629 - FindPilot* chain
- BTMux btech/src/btech/mech.h line 933 - dbref pilot
"""

import unittest
from unittest.mock import patch

from entities.mech import Mech, MechStatus, MoveType
from entities.pilot import Pilot
from entities.weapon import get_weapon
from systems.heat import attempt_startup, STARTUP_PILOTING_MODIFIER
from systems.piloting import (
    DEFAULT_GUNNERY, DEFAULT_PILOTING,
    find_pilot_gunnery, find_pilot_piloting, find_spilot_piloting,
    get_piloting_skill, make_piloting_roll,
)


class TestPilotDefaults(unittest.TestCase):
    """Test the Pilot dataclass itself."""

    def test_factory_defaults(self):
        """Test a fresh pilot is a 4/5 MechWarrior."""
        pilot = Pilot()
        self.assertEqual(pilot.name, "MechWarrior")
        self.assertEqual(pilot.gunnery, 4)
        self.assertEqual(pilot.piloting, 5)

    def test_explicit_pilot_values_differ_from_absent_fallbacks(self):
        """An explicit 4/5 pilot differs from source missing-pilot defaults 6/6."""
        pilot = Pilot()
        self.assertEqual((pilot.gunnery, DEFAULT_GUNNERY), (4, 6))
        self.assertEqual((pilot.piloting, DEFAULT_PILOTING), (5, 6))

    def test_named_pilot(self):
        """Test skills can be set per pilot."""
        pilot = Pilot(name="Natasha", gunnery=1, piloting=2)
        self.assertEqual(pilot.name, "Natasha")
        self.assertEqual(pilot.gunnery, 1)
        self.assertEqual(pilot.piloting, 2)

    def test_mech_has_no_pilot_by_default(self):
        """Test an empty machine has no pilot (C: MechPilot() invalid dbref)."""
        # mech.h:933 - dbref pilot; GotPilot() is false until someone climbs in
        # (btmacros.h:59-60)
        self.assertIsNone(Mech().pilot)


class TestFindPilotPiloting(unittest.TestCase):
    """Test find_pilot_piloting's three step fallback (mech.utils.c:580-590)."""

    def setUp(self):
        """Create a pilotless mech."""
        self.mech = Mech(name="Chain")

    def test_no_pilot_uses_default(self):
        """Test the config fallback (mech.utils.c:589)."""
        self.assertEqual(find_pilot_piloting(self.mech), DEFAULT_PILOTING)

    def test_pilot_skill_used(self):
        """Test the pilot's skill is read (mech.utils.c:586-588)."""
        self.mech.pilot = Pilot(piloting=3)
        self.assertEqual(find_pilot_piloting(self.mech), 3)

    def test_mech_override_beats_pilot(self):
        """Test the machine's skill override wins (mech.utils.c:585)."""
        # GENERIC_FIND_MECHSKILL returns before the pilot lookup
        # (mech.utils.c:574-578 then 585)
        self.mech.pilot = Pilot(piloting=3)
        self.mech.quiet, self.mech.mechskills = True, '2'
        self.assertEqual(find_pilot_piloting(self.mech), 2)

    def test_zero_mech_override_ignored(self):
        """Test a 0/absent override falls through to the pilot."""
        self.mech.pilot = Pilot(piloting=3)
        self.mech.pilot_skill = 0
        self.assertEqual(find_pilot_piloting(self.mech), 3)


class TestFindSPilotPiloting(unittest.TestCase):
    """Test find_spilot_piloting's quad bonus (mech.utils.c:592-595)."""

    def test_biped_unchanged(self):
        """Test bipeds get no adjustment."""
        mech = Mech(name="Biped", move_type=MoveType.BIPED)
        mech.pilot = Pilot(piloting=4)
        self.assertEqual(find_spilot_piloting(mech), 4)

    def test_quad_gets_minus_two(self):
        """Test quads get -2 (mech.utils.c:594)."""
        mech = Mech(name="Quad", move_type=MoveType.QUAD)
        mech.pilot = Pilot(piloting=4)
        self.assertEqual(find_spilot_piloting(mech), 2)

    def test_quad_with_no_pilot(self):
        """Test the quad bonus applies to the default fallback too."""
        mech = Mech(name="Quad", move_type=MoveType.QUAD)
        self.assertEqual(find_spilot_piloting(mech), DEFAULT_PILOTING - 2)


class TestFindPilotGunnery(unittest.TestCase):
    """Test find_pilot_gunnery's fallback (mech.utils.c:619-629)."""

    def setUp(self):
        """Create a pilotless mech."""
        self.mech = Mech(name="Gunner")

    def test_no_pilot_uses_default(self):
        """Test the config fallback (mech.utils.c:628)."""
        self.assertEqual(find_pilot_gunnery(self.mech), DEFAULT_GUNNERY)

    def test_pilot_gunnery_used(self):
        """Test the gun pilot's skill is read (mech.utils.c:625-627)."""
        self.mech.pilot = Pilot(gunnery=2)
        self.assertEqual(find_pilot_gunnery(self.mech), 2)

    def test_mech_override_beats_pilot(self):
        """Test the machine's skill override wins (mech.utils.c:624)."""
        self.mech.pilot = Pilot(gunnery=2)
        self.mech.quiet, self.mech.mechskills = True, '5 1'
        self.assertEqual(find_pilot_gunnery(self.mech), 1)

    def test_weapon_argument_accepted(self):
        """Test the weapindx analogue is accepted and (for now) ignored."""
        # Per-weapon-class gunnery is deferred; FindGunnerySkillName
        # (mech.utils.c:457-511) picks the skill name from the weapon in the C
        self.mech.pilot = Pilot(gunnery=2)
        weapon = get_weapon("IS.MediumLaser")
        self.assertEqual(find_pilot_gunnery(self.mech, weapon), 2)


class TestPilotInPilotingChecks(unittest.TestCase):
    """Test the pilot feeding the existing piloting machinery."""

    def setUp(self):
        """Create a started mech with a pilot."""
        self.mech = Mech(name="Roller")
        self.mech.set_status(MechStatus.STARTED)

    def test_get_piloting_skill_reads_pilot(self):
        """Test get_piloting_skill prefers the Pilot entity."""
        self.mech.pilot = Pilot(piloting=3)
        self.assertEqual(get_piloting_skill(self.mech), 3)

    def test_get_piloting_skill_without_pilot(self):
        """Test the legacy default survives."""
        self.assertEqual(get_piloting_skill(self.mech), DEFAULT_PILOTING)

    @patch('systems.piloting.random.randint')
    def test_piloting_roll_target_uses_pilot(self, mock_randint):
        """Test a good pilot lowers the roll target."""
        mock_randint.return_value = 2  # Roll 4
        self.mech.pilot = Pilot(piloting=3)
        result = make_piloting_roll(self.mech)
        self.assertEqual(result.target, 3)
        self.assertTrue(result.success)

    @patch('systems.piloting.random.randint')
    def test_piloting_roll_base_is_spilot_skill(self, mock_randint):
        """Test a quad's -2 reaches the roll target (mech.utils.c:668)."""
        # MechPilotSkillRoll_BTH is
        #   mods += FindSPilotPiloting(mech) + MechPilotSkillBase(mech)
        # (mech.utils.c:668), so the base carries the quad bonus from
        # FindSPilotPiloting (mech.utils.c:594), not bare FindPilotPiloting.
        mock_randint.return_value = 1  # Roll 2
        quad = Mech(name="Scorpion", move_type=MoveType.QUAD)
        quad.set_status(MechStatus.STARTED)
        quad.pilot = Pilot(piloting=4)
        result = make_piloting_roll(quad)
        self.assertEqual(result.target, 2)

    @patch('systems.piloting.random.randint')
    def test_piloting_roll_quad_bonus_stacks_with_modifier(self, mock_randint):
        """Test the situational modifier is the C's `mods` argument."""
        mock_randint.return_value = 1
        quad = Mech(name="Scorpion", move_type=MoveType.QUAD)
        quad.set_status(MechStatus.STARTED)
        quad.pilot = Pilot(piloting=4)
        result = make_piloting_roll(quad, modifier=3)
        self.assertEqual(result.target, 5)  # (4 - 2) + 3

    @patch('systems.piloting.random.randint')
    def test_piloting_roll_biped_has_no_bonus(self, mock_randint):
        """Test bipeds are unaffected by the FindSPilotPiloting branch."""
        mock_randint.return_value = 1
        biped = Mech(name="Biped", move_type=MoveType.BIPED)
        biped.set_status(MechStatus.STARTED)
        biped.pilot = Pilot(piloting=4)
        self.assertEqual(make_piloting_roll(biped).target, 4)

    @patch('systems.heat.roll_2d6')
    def test_hot_startup_target_uses_pilot(self, mock_roll):
        """Test the hot startup target reads the pilot's skill."""
        # heat.py routes through find_pilot_piloting (mech.utils.c:580-590)
        mock_roll.return_value = 12
        self.mech.clear_status(MechStatus.STARTED)
        self.mech.heat = 10.0
        self.mech.pilot = Pilot(piloting=3)
        result = attempt_startup(self.mech)
        self.assertTrue(result.piloting_required)
        self.assertEqual(result.piloting_target, 3 + STARTUP_PILOTING_MODIFIER)


if __name__ == '__main__':
    unittest.main()
