"""
Tests pinning the ported C constants.

Every assertion below cites the C file:line it was read from.  This module is
deliberately dumb: it exists so that a "harmless" tweak to a timing constant, a
speed threshold or a weapon recycle time fails loudly.  It also documents the
places where the port knowingly diverges from the C (the DEFAULT_* skills) and
the places where the same constant is currently defined more than once (which
Workstream B7 consolidates).

C sources:
- btech/src/include/btconfig.h - tick / timing constants, DEFAULT_* skills
- btech/src/btech/mech.h - TURN, KPH_PER_MP, SCALEMAP, MP1..MP9
- btech/src/btech/weapons.vrt.h - per-weapon recycle times (VRT)
- btech/src/btech/weapons.h - the MechWeapons table that picks a VRT per weapon
"""

import unittest

from core.game_loop import (
    HEAT_TICK, MOVE_TICK, LOS_TICK, WEAPON_TICK, JUMP_TICK, FALL_TICK,
    LOCK_TICK, PLOS_TICK, INITIAL_PLOS_TICK, SCHANGE_TICK, SPOT_TICK,
    HIDE_TICK, RANDOM_TICK, STARTUP_TIME, UNCONSCIOUS_TIME, LATERAL_TICK,
    MASC_TICK, DROP_TO_STAND_RECYCLE,
)
from entities.pilot import Pilot
from entities.weapon import get_weapon
from physics import jump as jump_module
from physics import movement as movement_module
from physics.hexmath import SCALEMAP
from physics.movement import MOVE_MOD, MP1, MP2, MP4, KPH_PER_MP, MP_PER_KPH
from systems import combat as combat_module
from systems.heat import TURN, WEAPON_RECYCLE_TIME
from systems.heat import HEAT_TICK as HEAT_HEAT_TICK
from systems.physical import PHYSICAL_RECYCLE_TIME
from systems.piloting import DEFAULT_GUNNERY, DEFAULT_PILOTING


# The C skill fallbacks, recorded for documentation only.  The port uses 4/5
# (see TestSkillDefaults) - btconfig.h:179 DEFAULT_GUNNERY 6,
# btconfig.h:180 DEFAULT_PILOTING 6.
C_DEFAULT_GUNNERY = 6
C_DEFAULT_PILOTING = 6


class TestTurnAndScale(unittest.TestCase):
    """Turn length and the hex/speed scale constants (mech.h:45-60)."""

    def test_turn(self):
        """Test a turn is 30 seconds."""
        self.assertEqual(TURN, 30)              # mech.h:45 - #define TURN 30

    def test_scalemap(self):
        """Test one hex is 322.5 cartesian units."""
        self.assertEqual(SCALEMAP, 322.5)       # mech.h:49 - #define SCALEMAP 322.5

    def test_move_mod(self):
        """Test the half-speed position multiplier."""
        self.assertEqual(MOVE_MOD, 0.5)         # btconfig.h:135 - #define MOVE_MOD .5
        # Duplicated in physics/jump.py until B7 consolidates the constants
        self.assertEqual(jump_module.MOVE_MOD, MOVE_MOD)

    def test_kph_per_mp(self):
        """Test 1 MP is 10.75 KPH."""
        self.assertEqual(KPH_PER_MP, 10.75)     # mech.h:46 - #define KPH_PER_MP 10.75
        self.assertEqual(MP1, 10.75)            # mech.h:54 - #define MP1 10.75
        self.assertEqual(MP_PER_KPH, 0.0930233)  # mech.h:47 - #define MP_PER_KPH 0.0930233

    def test_speed_thresholds(self):
        """Test the MP speed brackets used by the movement BTH cascade."""
        self.assertEqual(MP2, 21.50)            # mech.h:55 - #define MP2 21.50
        self.assertEqual(MP4, 43.00)            # mech.h:57 - #define MP4 43.00
        # MP6/MP9 are not module constants in the port yet (Workstream A6 adds
        # them next to the target-movement cascade); pin the C values off MP1.
        self.assertEqual(MP1 * 6, 64.50)        # mech.h:59 - #define MP6 64.50
        self.assertEqual(MP1 * 9, 96.75)        # mech.h:60 - #define MP9 96.75


class TestTickConstants(unittest.TestCase):
    """Event cadences from btconfig.h (btech/src/include/btconfig.h)."""

    def test_core_ticks(self):
        """Test the ticks the engine already runs on."""
        self.assertEqual(HEAT_TICK, 2)          # btconfig.h:132 - HEAT_TICK 2
        self.assertEqual(MOVE_TICK, 1)          # btconfig.h:134 - MOVE_TICK 1
        self.assertEqual(LOS_TICK, 1)           # btconfig.h:146 - LOS_TICK 1
        self.assertEqual(WEAPON_TICK, 2)        # btconfig.h:136 - WEAPON_TICK 2
        self.assertEqual(JUMP_TICK, 1)          # btconfig.h:133 - JUMP_TICK 1
        self.assertEqual(FALL_TICK, 3)          # btconfig.h:156 - FALL_TICK 3

    def test_duplicate_tick_definitions_agree(self):
        """Test the pre-B7 duplicates still match the core block."""
        self.assertEqual(movement_module.MOVE_TICK, MOVE_TICK)
        self.assertEqual(jump_module.JUMP_TICK, JUMP_TICK)
        self.assertEqual(HEAT_HEAT_TICK, HEAT_TICK)

    def test_sensor_ticks(self):
        """Test the LOS/sensor cadences (Workstream D consumes these)."""
        # The C constant is 8; the product default is 0 (instant locks) per
        # PLANNING_JULY_2026.md section 1.3 - this pins the ported C value.
        self.assertEqual(LOCK_TICK, 8)          # btconfig.h:210 - LOCK_TICK 8
        self.assertEqual(PLOS_TICK, 1)          # btconfig.h:148 - PLOS_TICK 1
        self.assertEqual(INITIAL_PLOS_TICK, 1)  # btconfig.h:145 - INITIAL_PLOS_TICK 1
        self.assertEqual(SCHANGE_TICK, 10)      # btconfig.h:149 - SCHANGE_TICK 10
        self.assertEqual(SPOT_TICK, 10)         # btconfig.h:150 - SPOT_TICK 10
        self.assertEqual(HIDE_TICK, 10)         # btconfig.h:147 - HIDE_TICK 10
        self.assertEqual(RANDOM_TICK, 6)        # btconfig.h:165 - RANDOM_TICK 6

    def test_unit_timers(self):
        """Test the remaining unit cadences."""
        self.assertEqual(STARTUP_TIME, 30)      # btconfig.h:153 - STARTUP_TIME 30
        self.assertEqual(UNCONSCIOUS_TIME, 30)  # btconfig.h:154 - UNCONSCIOUS_TIME 30
        self.assertEqual(LATERAL_TICK, 6)       # btconfig.h:131 - LATERAL_TICK 6
        self.assertEqual(MASC_TICK, 60)         # btconfig.h:163 - MASC_TICK 60
        # btconfig.h:142 - DROP_TO_STAND_RECYCLE (MOVE_TICK * 12)
        self.assertEqual(DROP_TO_STAND_RECYCLE, 12)
        self.assertEqual(DROP_TO_STAND_RECYCLE, MOVE_TICK * 12)


class TestRecycleConstants(unittest.TestCase):
    """Recycle durations, which are all expressed in WEAPON_TICKs."""

    def test_physical_recycle_time(self):
        """Test a physical attack recycles for 60 seconds."""
        # btconfig.h:152 - #define PHYSICAL_RECYCLE_TIME 30*WEAPON_TICK
        self.assertEqual(PHYSICAL_RECYCLE_TIME, 60)
        self.assertEqual(PHYSICAL_RECYCLE_TIME, 30 * WEAPON_TICK)

    def test_weapon_recycle_time(self):
        """Test the nominal weapon recycle is 30 weapon_ticks."""
        # btconfig.h:155 - #define WEAPON_RECYCLE_TIME 30 /* weapon_tick's */
        self.assertEqual(WEAPON_RECYCLE_TIME, 30)

    def test_ppc_recycle_is_one_turn_of_wall_clock(self):
        """Test WEAPON_TICK * vrt is the recycle duration (a PPC = 60s)."""
        # mech.combat.c:1353-1354 - SetRecyclePart(mech, section, critical,
        #     WEAPON_TICK * MechWeapons[weapindx].vrt)
        self.assertEqual(WEAPON_TICK * get_weapon("IS.PPC").vrt, 60)


class TestSkillDefaults(unittest.TestCase):
    """Source missing-pilot defaults and explicit local Pilot factory values."""

    def test_python_defaults(self):
        """Test the port's factory skills are gunnery 4 / piloting 5."""
        self.assertEqual(DEFAULT_GUNNERY, 6)
        self.assertEqual(DEFAULT_PILOTING, 6)
        self.assertEqual(Pilot().gunnery, 4)
        self.assertEqual(Pilot().piloting, 5)

    def test_c_defaults_documented(self):
        """Test the C fallbacks are recorded (documentation-assert)."""
        self.assertEqual(C_DEFAULT_GUNNERY, 6)   # btconfig.h:179 - DEFAULT_GUNNERY 6
        self.assertEqual(C_DEFAULT_PILOTING, 6)  # btconfig.h:180 - DEFAULT_PILOTING 6

    def test_source_fallbacks_match(self):
        """The runtime missing-pilot fallback agrees with btconfig.h."""
        self.assertEqual(DEFAULT_GUNNERY, C_DEFAULT_GUNNERY)
        self.assertEqual(DEFAULT_PILOTING, C_DEFAULT_PILOTING)

    def test_re_exports_are_the_same_objects(self):
        """Test the compatibility re-exports point at the single definition."""
        self.assertEqual(combat_module.DEFAULT_GUNNERY, DEFAULT_GUNNERY)
        self.assertEqual(combat_module.DEFAULT_PILOTING, DEFAULT_PILOTING)
        self.assertEqual(jump_module.DEFAULT_PILOTING, DEFAULT_PILOTING)


class TestWeaponVRT(unittest.TestCase):
    """VRT spot-checks against weapons.vrt.h."""

    def assert_vrt(self, name: str, vrt: int):
        """Assert a catalog weapon's recycle time."""
        weapon = get_weapon(name)
        self.assertIsNotNone(weapon, f"{name} missing from the catalog")
        self.assertEqual(weapon.vrt, vrt, name)

    def test_machine_gun(self):
        """Test the MG's 7s recycle (~4 bursts a turn - a balance signature)."""
        self.assert_vrt("IS.MachineGun", 7)     # weapons.vrt.h:51 - VRT_IS_MG 7

    def test_one_shot_per_turn_weapons(self):
        """Test the vrt-30 club: one shot per 30s turn."""
        self.assert_vrt("IS.PPC", 30)           # weapons.vrt.h:131 - VRT_IS_PPC 30
        self.assert_vrt("IS.GaussRifle", 30)    # weapons.vrt.h:40 - VRT_IS_GR 30
        self.assert_vrt("IS.AC/20", 30)         # weapons.vrt.h:36 - VRT_IS_AC20 30
        self.assert_vrt("IS.LRM-20", 30)        # weapons.vrt.h:44 - VRT_IS_LRM20 30

    def test_lasers_and_autocannons(self):
        """Test the mid-tier recycle times."""
        self.assert_vrt("IS.LargeLaser", 25)    # weapons.vrt.h:127 - VRT_IS_LL 25
        self.assert_vrt("IS.MediumLaser", 20)   # weapons.vrt.h:129 - VRT_IS_ML 20
        self.assert_vrt("IS.AC/5", 20)          # weapons.vrt.h:37 - VRT_IS_AC5 20
        self.assert_vrt("IS.AC/2", 12)          # weapons.vrt.h:35 - VRT_IS_AC2 12

    def test_artillery(self):
        """Test artillery fires once per two turns."""
        self.assert_vrt("IS.ArrowIVSystem", 60)  # weapons.vrt.h:39 - VRT_IS_ARROWIV 60
        self.assert_vrt("IS.LongTom", 60)        # weapons.vrt.h:50 - VRT_IS_LONGTOM 60
        self.assert_vrt("IS.Sniper", 60)         # weapons.vrt.h:56 - VRT_IS_SNIPER 60
        self.assert_vrt("IS.Thumper", 60)        # weapons.vrt.h:58 - VRT_IS_THUMPER 60

    def test_clan_lrm20_inherits_the_lrm10_recycle(self):
        """Test the C's CL.LRM-20 typo is ported, not fixed."""
        # weapons.h:206 - {"CL.LRM-20", VRT_CL_LRM10, ...} uses the LRM-10
        # recycle (weapons.vrt.h:16 - VRT_CL_LRM10 20), leaving VRT_CL_LRM20 30
        # (weapons.vrt.h:18) unused.  Prime directive: port the oddity.
        self.assert_vrt("CL.LRM-20", 20)

    def test_vrt_values_are_not_turn_quantised(self):
        """Test the coprime recycle times that make weapon cycles drift."""
        self.assert_vrt("CL.ERPPC", 25)         # weapons.vrt.h:111 - VRT_CL_ERPPC 25
        self.assert_vrt("CL.SmallPulseLaser", 13)  # weapons.vrt.h:120 - VRT_CL_SPL 13
        self.assert_vrt("CL.MediumPulseLaser", 18)  # weapons.vrt.h:117 - VRT_CL_MPL 18
        self.assert_vrt("IS.X-SmallPulseLaser", 17)  # weapons.vrt.h:141 - VRT_IS_XSPL 17
        self.assert_vrt("IS.X-LargePulseLaser", 27)  # weapons.vrt.h:139 - VRT_IS_XLPL 27


# =============================================================================
# M4 additions (charge, tics, mode bits, physical divisors, lateral, targcomp)
# =============================================================================

class TestChargeConstants(unittest.TestCase):
    """Charge trigger constants (btconfig.h:175-176), currently defined in
    both physics/movement.py and systems/physical.py."""

    def test_charge_dist_trigger(self):
        from physics.movement import CHARGE_DIST_TRIGGER
        from systems import physical as physical_module
        # btconfig.h:176 - #define CHARGE_DIST_TRIGGER 0.6
        self.assertEqual(CHARGE_DIST_TRIGGER, 0.6)
        self.assertEqual(physical_module.CHARGE_DIST_TRIGGER, 0.6)

    def test_charge_timer_limit(self):
        from physics.movement import CHARGE_TIMER_LIMIT
        from systems import physical as physical_module
        # btconfig.h:175 - #define CHARGE_TIMER_LIMIT 60
        self.assertEqual(CHARGE_TIMER_LIMIT, 60)
        self.assertEqual(physical_module.CHARGE_TIMER_LIMIT, 60)


class TestTicConstants(unittest.TestCase):
    """TIC dimensions (mech.h:593-596)."""

    def test_num_tics(self):
        from systems.tic import NUM_TICS
        self.assertEqual(NUM_TICS, 4)           # mech.h:593-596 - NUM_TICS 4

    def test_max_weapons_per_mech(self):
        from systems.tic import MAX_WEAPONS_PER_MECH
        # mech.h:593-596 - MAX_WEAPONS_PER_MECH 96
        self.assertEqual(MAX_WEAPONS_PER_MECH, 96)


class TestModeBits(unittest.TestCase):
    """Ammo / fire mode bit values (mech.h:611-666)."""

    def test_ammo_mode_bits(self):
        from entities.mech import AmmoMode
        self.assertEqual(AmmoMode.LBX_MODE, 0x1)            # mech.h:611-666
        self.assertEqual(AmmoMode.INFERNO_MODE, 0x40)       # mech.h:611-666
        self.assertEqual(AmmoMode.AC_AP_MODE, 0x2000)       # mech.h:611-666
        self.assertEqual(AmmoMode.AC_PRECISION_MODE, 0x10000)  # mech.h:611-666

    def test_fire_mode_on_tc(self):
        from entities.mech import FireMode
        self.assertEqual(FireMode.ON_TC, 0x10)              # mech.h:611-666


class TestPhysicalDamageDivisors(unittest.TestCase):
    """
    Physical damage divisors (mech.physical.c): punch tons/10, club/axe/kick
    tons/5, claw tons/7, mace tons/4, saw flat 7.  The divisors are not
    named constants in systems/physical.py — each command passes its
    damage_weight into physical_attack — so they are asserted by capturing
    that argument, plus a behavior check for the saw's flat 7.
    """

    def _mech(self, name="Alpha"):
        from data.templates import create_mech_from_template, get_template
        from entities.mech import MechStatus
        mech = create_mech_from_template(get_template("TestMech"), name=name)
        mech.set_hex_position(50, 50)
        mech.set_status(MechStatus.STARTED)
        return mech

    def _pair(self):
        a = self._mech("Alpha")
        t = self._mech("Target")
        a.facing = 0
        t.facing = 180
        t.fx, t.fy = a.fx, a.fy - 100.0
        t.x, t.y, t.z = a.x, a.y, a.z
        from core.game_loop import GameEngine
        from entities.map import GameMap
        engine = GameEngine()
        board = GameMap(100, 100)
        board._id = 1000
        engine.register_entity(board)
        for unit in (a, t):
            board.add_mech(unit)
            engine.register_entity(unit)
        return a, t

    def _add_special(self, mech, loc, special, count, start=4):
        from entities.crittypes import i2special
        for i in range(start, start + count):
            mech.sections[loc].criticals[i].type = i2special(special)

    def _captured_weight(self, command, setup=None, **cmd_kwargs):
        from unittest.mock import patch
        a, t = self._pair()
        if setup is not None:
            setup(a)
        with patch('systems.physical.physical_attack') as pa:
            command(a, t, **cmd_kwargs)
        self.assertTrue(pa.called)
        return pa.call_args[0][1]       # physical_attack(mech, damage_weight, ...)

    def test_punch_is_tons_over_10(self):
        from systems.physical import mech_punch
        # mech.physical.c:340-387 - punch damage tons/10
        self.assertEqual(self._captured_weight(mech_punch, arm='R'), 10)

    def test_club_is_tons_over_5(self):
        from entities.mech import Location
        from systems.physical import CARRYING_CLUB, mech_club

        def give_club(mech):
            mech.sections[Location.RARM].specials |= CARRYING_CLUB

        # mech.physical.c:392-446 - club damage tons/5
        self.assertEqual(self._captured_weight(mech_club, setup=give_club), 5)

    def test_axe_is_tons_over_5(self):
        from entities.crittypes import Special
        from entities.mech import Location
        from systems.physical import mech_axe

        def give_axe(mech):     # have_axe: >= tons/15 = 3 crits
            self._add_special(mech, Location.RARM, Special.AXE, 3)

        # mech.physical.c:478-522 - axe damage tons/5
        self.assertEqual(
            self._captured_weight(mech_axe, setup=give_axe, arm='R'), 5)

    def test_kick_is_tons_over_5(self):
        from systems.physical import mech_kick
        # mech.physical.c:791-865 - kick damage tons/5
        self.assertEqual(self._captured_weight(mech_kick), 5)

    def test_claw_is_tons_over_7(self):
        from entities.crittypes import Special
        from entities.mech import Location
        from systems.physical import mech_claw

        def give_claw(mech):    # have_claw: >= tons/15 = 3 crits
            self._add_special(mech, Location.LARM, Special.CLAW, 3)
            self._add_special(mech, Location.RARM, Special.CLAW, 3)

        # mech.physical.c:591-644 - claw damage tons/7
        self.assertEqual(
            self._captured_weight(mech_claw, setup=give_claw, arm='R'), 7)

    def test_mace_is_tons_over_4(self):
        from entities.crittypes import Special
        from entities.mech import Location
        from systems.physical import mech_mace

        def give_mace(mech):    # have_mace: >= tons/10 = 5 crits
            self._add_special(mech, Location.RARM, Special.MACE, 5)

        # mech.physical.c:673-716 - mace damage tons/4
        self.assertEqual(
            self._captured_weight(mech_mace, setup=give_mace, arm='R'), 4)

    def test_saw_is_flat_seven(self):
        from entities.crittypes import Special
        from entities.mech import Location
        from systems.physical import (
            PhysicalAttackType, mech_saw, physical_damage,
        )

        def give_saw(mech):     # have_saw: flat 7 crits
            self._add_special(mech, Location.RARM, Special.DUAL_SAW, 7)

        # The command still passes 7 (mech.physical.c:546-589)...
        self.assertEqual(
            self._captured_weight(mech_saw, setup=give_saw, arm='R'), 7)
        # ...but the formula ignores the divisor entirely: saws do a
        # constant 7 due to their mechanical nature (mech.physical.c:1533-1537)
        a, t = self._pair()
        result = physical_damage(a, t, 999, PhysicalAttackType.SAW,
                                 Location.RARM, location_roll=7)
        self.assertEqual(result.damage_dealt, 7)


class TestLateralOffsets(unittest.TestCase):
    """Lateral movement mode heading offsets (mech.move.c:39-103)."""

    def test_lateral_mode_offsets(self):
        from systems.maneuver import _LATERAL_ALIASES
        for key, offset in (('nw', 300), ('fl', 300),   # mech.move.c:39-103
                            ('ne', 60), ('fr', 60),
                            ('sw', 240), ('rl', 240),
                            ('se', 120), ('rr', 120)):
            self.assertEqual(_LATERAL_ALIASES[key], offset,
                             f"lateral mode {key!r}")


class TestTargcompConstants(unittest.TestCase):
    """Targeting-computer types TARGCOMP_* 0-4 (mech.h:1209-1214)."""

    def test_targcomp_values(self):
        # mech.h:1210-1214, one value per line: NORMAL 0, SHORT 1, LONG 2,
        # MULTI 3, AA 4
        for name, value in (('TARGCOMP_NORMAL', 0),
                            ('TARGCOMP_SHORT', 1),
                            ('TARGCOMP_LONG', 2),
                            ('TARGCOMP_MULTI', 3),
                            ('TARGCOMP_AA', 4)):
            self.assertEqual(getattr(combat_module, name, None), value,
                             f"{name} should be {value}")


if __name__ == '__main__':
    unittest.main()
