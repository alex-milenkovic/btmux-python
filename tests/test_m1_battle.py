"""
M1 acceptance test: a scripted two-mech battle on the fully wired engine.

Bravo (AssaultMech: PPC RARM, 2x MediumLaser LTORSO, LRM-10 RTORSO with a
12-round bin) fights Alpha (TestMech) using the complete M1 stack:

- wire_standard_systems: MECH -> mech_update at HEAT_TICK on the dispatch
  clock (glue.c:56-68), heartbeat recycle on (tick.c:82-88)
- every order routes through engine.inject_command (clock 3)
- shots go through systems.combat.fire_weapon (mech.combat.c FireWeapon
  pipeline: gates, heat, ammo, recycle)

Determinism: attack and hit-location dice are pinned via fire_weapon's
to_hit_roll / location_roll kwargs; critical dice are pinned by patching the
module-path randoms (systems.combat.roll_critical_hits and
systems.criticals.random.choice), matching tests/test_fire_pipeline.py style.

Covers the M1 acceptance items:
(a) heat rises by weapon heat on fire and decays over ticks
(b) the LRM ammo bin depletes to dry; further fire fails "out of ammo"
(c) a forced through-armor critical lands on a real populated slot (engine)
    and applies its real effect (+5 engine heat, crit.c engine handler)
(d) a shot from behind a north-facing target classifies as BACK arc and
    damages rear armor (mech.hitloc.c:2833-2924 FindAreaHitGroup)
(e) a fired weapon cannot refire until WEAPON_TICK * vrt heartbeat-seconds
    elapse (mech.combat.c:1353-1354, mech.utils.c:1186-1190)
"""

import unittest
from unittest.mock import patch

from core.game_loop import GameEngine, wire_standard_systems
from data.templates import create_mech_from_template, get_template
from entities.crittypes import is_special, special2i
from entities.mech import FireMode, Location, MechStatus
from entities.weapon import get_weapon_by_index
from systems.combat import (
    WEAPON_TICK,
    HitGroup,
    determine_hit_group,
    find_ammo_for_weapon,
    fire_weapon,
)
from systems.criticals import ENGINE_HEAT_PER_HIT, EquipmentType

# AssaultMech weapon numbers (template mount order)
PPC = 0        # RARM,   heat 10, vrt 30
ML = 1         # LTORSO, heat 3,  vrt 20
ML2 = 2        # LTORSO, heat 3,  vrt 20
LRM10 = 3      # RTORSO, heat 4,  vrt 20, 12-round bin

SURE_HIT = dict(to_hit_roll=12, location_roll=7)   # 7 = CT on every table
SURE_MISS = dict(to_hit_roll=2, location_roll=7)


class M1BattleBase(unittest.TestCase):
    """Two template mechs on a wired engine, orders via inject_command."""

    def setUp(self):
        self.engine = GameEngine()
        wire_standard_systems(self.engine)

        # Bravo due NORTH of Alpha; Alpha faces north (0) - so by default
        # Bravo attacks into Alpha's FRONT arc.
        self.attacker = create_mech_from_template(
            get_template("AssaultMech"), name="Bravo")
        self.attacker.set_status(MechStatus.STARTED)
        self.attacker.set_hex_position(50, 47)
        self.attacker.facing = 180

        self.target = create_mech_from_template(
            get_template("TestMech"), name="Alpha")
        self.target.set_status(MechStatus.STARTED)
        self.target.set_hex_position(50, 50)
        self.target.facing = 0

        self.engine.register_entity(self.attacker)
        self.engine.register_entity(self.target)
        self.distance = 3.0

    def fire(self, weapon_number: int, distance: float = None, **rolls):
        """Fire one of Bravo's weapons as an injected player command."""
        d = self.distance if distance is None else distance
        return self.engine.inject_command(
            self.attacker.name,
            lambda: fire_weapon(self.attacker, self.target,
                                weapon_number, d, **rolls),
            f"fire {weapon_number}")

    def crit_slot(self, weapon_number: int):
        """The weapon's first crit slot (recycle countdown, mech.h:599-608)."""
        ws = self.attacker.weapons[weapon_number]
        return self.attacker.sections[ws.section].criticals[ws.critical]

    def recycle_seconds(self, weapon_number: int) -> int:
        """WEAPON_TICK * vrt (mech.combat.c:1353-1354)."""
        ws = self.attacker.weapons[weapon_number]
        return WEAPON_TICK * get_weapon_by_index(ws.weapon_idx).vrt


class TestM1HeatRiseAndDecay(M1BattleBase):
    """(a) Heat: weap_heat rises by exactly the weapons' heat and the heat
    system (mech_update -> full_heat_update at HEAT_TICK) burns it back
    down (mech.combat.c:1379, mech.update.c:2981-2982)."""

    def test_alpha_strike_heats_up_then_cools_down(self):
        # PPC 10 + ML 3 + ML 3 = 16 plus-heat vs 15 sinks: heat must rise.
        expected = sum(
            get_weapon_by_index(self.attacker.weapons[n].weapon_idx).heat
            for n in (PPC, ML, ML2))
        self.assertEqual(expected, 16)

        for n in (PPC, ML, ML2):
            self.fire(n, **SURE_MISS)   # heat applies hit or miss

        # weap_heat rose by exactly the fired weapons' heat
        self.assertEqual(self.attacker.weap_heat, float(expected))
        self.assertEqual(self.attacker.heat, 0.0)   # not integrated yet

        # One HEAT_TICK update: heat climbs above zero
        self.engine.run_ticks(2)
        self.assertGreater(self.attacker.heat, 0.0)
        peak_weap = self.attacker.weap_heat

        # And decays: weapon heat bleeds off each update until the mech is
        # cold again (decay_weapon_heat via update_heat).
        self.engine.run_ticks(38)
        self.assertEqual(self.attacker.heat, 0.0)
        self.assertLess(self.attacker.weap_heat, peak_weap)


class TestM1AmmoDepletion(M1BattleBase):
    """(b) Ammo: the LRM-10's 12-round bin runs dry through real fire
    commands; the 13th shot fails the FindAndCheckAmmo gate
    (mech.combat.c:845-849, mech.utils.c:2648)."""

    def test_lrm_bin_depletes_to_dry(self):
        ws = self.attacker.weapons[LRM10]
        loc, slot_idx = find_ammo_for_weapon(
            self.attacker, ws.weapon_idx, ws.section)
        bin_slot = self.attacker.sections[loc].criticals[slot_idx]
        self.assertEqual(bin_slot.data, 12)     # template loadout

        recycle = self.recycle_seconds(LRM10)
        for shot in range(12):
            result = self.fire(LRM10, distance=10.0, **SURE_MISS)
            self.assertNotIn("out of ammo", result.messages[0])
            self.assertEqual(bin_slot.data, 12 - (shot + 1))
            # Let the heartbeat count the launcher back to ready
            self.engine.run_ticks(recycle)

        self.assertEqual(bin_slot.data, 0)

        # Bone dry: the gate refuses before any costs are paid.
        heat_before = self.attacker.weap_heat
        result = self.fire(LRM10, distance=10.0, **SURE_MISS)
        self.assertFalse(result.hit)
        self.assertEqual("You don't have any ammo for that weapon stored on this mech!", result.messages[0])
        self.assertEqual(self.attacker.weap_heat, heat_before)
        self.assertEqual(self.crit_slot(LRM10).data, 0)  # no recycle started


class TestM1ThroughArmorCritical(M1BattleBase):
    """(c) A forced through-armor critical lands on a real populated slot
    and applies its real effect: an engine hit adds +5 heat per turn
    (crit.c HandleMechCrit -> engine handler, mech.update.c crit table)."""

    def test_engine_crit_through_bared_center_torso(self):
        ct = self.target.sections[Location.CTORSO]
        ct.armor = 0    # PPC hit goes straight to internals

        # Find a real engine slot in the CT crit table
        engine_slot = next(
            i for i, c in enumerate(ct.criticals)
            if c.type and is_special(c.type)
            and special2i(c.type) == EquipmentType.ENGINE)

        # Pin the crit dice: exactly one through-armor crit
        # (systems.combat.roll_critical_hits) landing on the engine slot
        # (crit.c:2419-2420 Number(0, count-1) -> random.choice).
        from core.randomness import use_source
        selected = []
        def draws(name, low, high, fallback):
            if name == "critical_slot":
                selected.append(name)
                return 0  # first live slot is the engine
            return fallback()
        with patch("systems.combat.roll_critical_hits", return_value=1), \
             use_source(draws):
            result = self.fire(PPC, **SURE_HIT)

        self.assertTrue(result.hit)
        self.assertEqual(result.location, Location.CTORSO)
        self.assertGreater(result.internal_damage, 0)
        self.assertEqual(result.criticals_rolled, 1)

        # Real effect on the mech: engine shielding hit, +5 heat per turn
        self.assertEqual(self.target.engine_heat, ENGINE_HEAT_PER_HIT)

        self.assertEqual(["critical_slot"], selected)
        # And the populated slot itself is destroyed
        self.assertTrue(
            ct.criticals[engine_slot].firemode & FireMode.DESTROYED_MODE)
        self.assertTrue(
            any("engine shielding" in m for m in result.messages))


class TestM1RearArc(M1BattleBase):
    """(d) A shot from directly behind a north-facing target classifies as
    BACK arc (FindAreaHitGroup, mech.hitloc.c:2833-2924) and lands on rear
    armor."""

    def test_shot_from_behind_hits_back_arc(self):
        # Reposition Bravo due SOUTH of Alpha; Alpha still faces north.
        self.attacker.set_hex_position(50, 53)

        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.BACK)

        ct = self.target.sections[Location.CTORSO]
        rear_before = ct.rear
        front_before = ct.armor

        # ML (5 damage < 7 rear armor): location roll 7 on the BACK table
        # is center torso (rear).
        result = self.fire(ML, **SURE_HIT)

        self.assertTrue(result.hit)
        self.assertTrue(result.is_rear)
        self.assertEqual(result.location, Location.CTORSO)
        self.assertEqual(ct.rear, rear_before - 5)     # rear armor took it
        self.assertEqual(ct.armor, front_before)       # front untouched


class TestM1RecycleGate(M1BattleBase):
    """(e) Recycle: a fired weapon refuses to refire until WEAPON_TICK * vrt
    heartbeat-seconds elapse (mech.combat.c:1353-1354; reloading gate at
    mech.utils.c:1186-1190), then fires again."""

    def test_no_refire_until_recycle_elapses(self):
        recycle = self.recycle_seconds(ML)
        slot = self.crit_slot(ML)

        first = self.fire(ML, **SURE_MISS)
        self.assertFalse(first.hit)                 # a miss still recycles
        self.assertEqual(slot.data, recycle)

        # Immediate second trigger-pull: blocked
        second = self.fire(ML, **SURE_HIT)
        self.assertFalse(second.hit)
        self.assertIn("still reloading", second.messages[0])

        # One second short: still blocked
        self.engine.run_ticks(recycle - 1)
        self.assertEqual(slot.data, 1)
        third = self.fire(ML, **SURE_HIT)
        self.assertIn("still reloading", third.messages[0])

        # The final heartbeat clears the countdown: fires again
        self.engine.run_ticks(1)
        self.assertEqual(slot.data, 0)
        fourth = self.fire(ML, **SURE_HIT)
        self.assertTrue(fourth.hit)
        self.assertEqual(slot.data, recycle)        # and recycles anew


if __name__ == "__main__":
    unittest.main()
