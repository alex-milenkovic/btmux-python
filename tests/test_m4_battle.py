"""
M4 integration battle scenarios.

Four independent legs exercising the Wave 1-2 M4 systems end to end:

1. Blindfire crit-fishing — an LRM boat plain-locks a hex containing an
   enemy with an open (zero-armor) torso; the fire-time probe
   (find_mech_in_hex, mech.utils.c:2537-2567) engages the occupant, the
   shot takes the unstable-lock BTH term (mech.bth.c:270-273), reaches
   internal structure and produces criticals.  Companions: the explicit
   LOCK_HEX -4 "HexBonus" on an empty hex (mech.bth.c:292-295) and the
   BTH > 12 "Roll: Impossible!" refusal (mech.combat.c:961-966).
2. TIC alpha-strike into the hex (systems/tic.py, mech.tic.c).
3. AMS defender shaving an incoming LRM salvo
   (mech.combat.missile.c:325-357, 493-510, 551-552).  NOTE: depends on
   the AMS/cluster wiring into systems/combat.py.
4. Physical brawl with the 60-tick section recycle pacing
   (mech.physical.c:59-74, 1401; mech.update.c:1594-1626).

All dice are deterministic via explicit roll kwargs or @patch on the
owning module's rollers — the RNG is never seeded.
"""

import math
import unittest
from unittest.mock import patch

from core.game_loop import GameEngine
from data.templates import create_mech_from_template, get_template
from entities.crittypes import i2ammo, i2weapon
from entities.map import GameMap
from entities.mech import (
    FireMode, Location, MechStatus, Specials, WeaponState,
)
from entities.weapon import get_weapon
from systems.combat import WEAPON_TICK, fire_weapon_number
from systems.los import (
    MECHLOSFLAG_SEEC2, MECHLOSFLAG_SEEN, MECHLOSFLAG_SEESP,
)
from systems.physical import PHYSICAL_RECYCLE_TIME, mech_kick, mech_punch
from systems.piloting import PilotingResult
from systems.targeting import set_target, set_target_hex
from systems.tic import add_tic, fire_tic

SEES = MECHLOSFLAG_SEEN | MECHLOSFLAG_SEESP | MECHLOSFLAG_SEEC2

PSR_OK = PilotingResult(success=True)
PSR_FAIL = PilotingResult(success=False)


def total_armor(mech) -> int:
    """Front + rear armor over all sections (internals excluded)."""
    return sum(s.armor + s.rear for s in mech.sections)


def mount_ams(mech, rounds: int = 12):
    """
    Give a template mech a working IS AMS: crit + parallel WeaponState in
    the (template-empty) left torso, an ammo bin next to it, the
    IS_ANTI_MISSILE_TECH special and the AMS_ENABLED status.

    Returns (weapon_def, weapon_crit_slot, ammo_crit_slot, weapon_number).
    """
    ams = get_weapon("IS.Anti-MissileSystem")
    sec = Location.LTORSO
    slot = mech.sections[sec].criticals[0]
    assert slot.type == 0, "expected an empty LTORSO slot for the AMS"
    slot.type = i2weapon(ams.index)
    slot.data = 0
    slot.firemode = FireMode.NONE
    slot.ammomode = 0
    weapon_number = len(mech.weapons)
    mech.weapons.append(WeaponState(section=int(sec), critical=0,
                                    weapon_idx=ams.index))
    ammo = mech.sections[sec].criticals[1]
    assert ammo.type == 0, "expected an empty LTORSO slot for the AMS ammo"
    ammo.type = i2ammo(ams.index)
    ammo.data = rounds
    mech.specials |= Specials.IS_ANTI_MISSILE_TECH
    mech.set_status(MechStatus.AMS_ENABLED)
    return ams, slot, ammo, weapon_number


class M4MapFixture(unittest.TestCase):
    """A lit 30x30 map with hand-filled LOS caching, hexfire-style."""

    def setUp(self):
        self.engine = GameEngine()
        self.map = GameMap(30, 30)
        self.map._id = 1000
        self.engine.register_entity(self.map)
        self.map.mapvis = 30
        self.map.maplight = 2
        self.map.maxvis = 60
        self.map.losinfo = {}

    def add(self, template, name, x, y, facing=0):
        mech = create_mech_from_template(get_template(template), name=name)
        mech.set_hex_position(x, y)
        mech.facing = facing
        mech.set_status(MechStatus.STARTED)
        self.map.add_mech(mech)
        self.engine.register_entity(mech)
        return mech

    def see(self, looker, target, flag=SEES):
        self.map.losinfo[(looker._id, target._id)] = flag

    def lock_hex(self, mech, x, y, mode=None):
        ok, msg = set_target_hex(self.engine, mech, x, y, mode)
        self.assertTrue(ok, msg)


# =============================================================================
# Leg 1 — blindfire crit-fishing (probe + unstable lock + internal crit)
# =============================================================================

class TestBlindfireCritFishing(M4MapFixture):
    """An LRM boat plain-locks the victim's hex and fishes for crits
    through a zero-armor center torso."""

    def setUp(self):
        super().setUp()
        # AssaultMech weapon 3 = IS.LRM-10 (RTORSO, forward arc)
        self.att = self.add("AssaultMech", "Archer", 10, 10, facing=0)
        self.victim = self.add("TestMech", "Victim", 10, 3, facing=180)
        # Open torso: internal structure exposed (16 internal behind 0 armor)
        self.victim.sections[Location.CTORSO].armor = 0

    def test_plain_hex_lock_probe_crits_the_open_torso(self):
        # Plain coordinate lock on the OCCUPIED hex — no explicit hex mode,
        # so MechLockFire runs the find_mech_in_hex probe at fire time
        # (mech.combat.c:574-586).
        self.see(self.att, self.victim)
        self.lock_hex(self.att, 10, 3)
        internal_before = self.victim.sections[Location.CTORSO].internal

        # cluster_roll=10 -> MissileHitIndex row 8 -> 8 of 10 LRMs hit
        # (mech.combat.missile.c:325-330); the first 5-missile group lands
        # on the CT (location roll 2, an auto-crit table entry), the
        # 3-missile remainder on the left arm (roll 10).  roll_2d6=10
        # pins any remaining critical-count rolls at 2 crits; the
        # crit-slot pick is pinned to the first undamaged slot
        # (CT slot 0 = ENGINE).
        with patch('systems.combat.roll_2d6', return_value=10), \
                patch('systems.missile.roll_2d6', return_value=10), \
                patch('systems.criticals.random.choice',
                      side_effect=lambda seq: seq[0]):
            result = fire_weapon_number(self.engine, self.att, 3,
                                        to_hit_roll=12, cluster_roll=10,
                                        location_rolls=[2, 10],
                                        location_roll=2)

        self.assertTrue(result.hit)
        # Hex-found mech always takes the unstable-lock term
        # (MechTarget == -1 != temp->mynum, mech.bth.c:270-273)...
        self.assertEqual(result.bth_breakdown.unstable_lock_mod, 1)
        # ...and a probe HIT means no "HexBonus" (mech.bth.c:292-295)
        self.assertEqual(result.bth_breakdown.hex_mod, 0)
        self.assertIn("%cgThe swarm hits with 8 missiles!%c", result.messages)

        # First 5-missile group went through the open CT into structure
        self.assertEqual(self.victim.sections[Location.CTORSO].internal,
                         internal_before - 5)
        # Internal-structure damage rolls criticals (the C's DamageMech ->
        # HandleCritical bracket, mech.damage.c); the patched 2d6=10 is a
        # 2-crit row on the through-armor table
        self.assertGreater(result.criticals_rolled, 0)
        # The pinned pick damaged the first CT slot (ENGINE), not the mech
        slot0 = self.victim.sections[Location.CTORSO].criticals[0]
        self.assertTrue(slot0.firemode & (FireMode.DAMAGED_MODE |
                                          FireMode.DESTROYED_MODE))
        self.assertFalse(result.target_destroyed)

    def test_explicit_hex_lock_on_empty_hex_gets_minus_four(self):
        # LOCK_HEX mode on an EMPTY hex: the probe is skipped and the
        # empty-hex resolution takes the -4 HexBonus (mech.bth.c:292-295).
        self.lock_hex(self.att, 10, 7, 'H')     # empty hex due north
        result = fire_weapon_number(self.engine, self.att, 1,
                                    to_hit_roll=12)
        self.assertTrue(result.hit)
        self.assertEqual(result.bth_breakdown.hex_mod, -4)
        self.assertEqual(result.bth_breakdown.unstable_lock_mod, 0)

    def test_bth_over_12_hex_shot_is_refused_without_cost(self):
        # Impossible-roll gate follows the attack draw: no heat,
        # no ammo, no recycle, no FIRED.
        self.att.base_to_hit = 20
        self.lock_hex(self.att, 10, 7)          # plain lock, empty hex
        result = fire_weapon_number(self.engine, self.att, 1,
                                    to_hit_roll=12)
        self.assertTrue(result.roll_impossible)
        self.assertFalse(result.hit)
        self.assertEqual(result.roll, 12)
        self.assertEqual(
            result.messages,
            ["Fire %s at (%d,%d) - BTH: %d  Roll: Impossible!"
             % ("MediumLaser", 10, 7, result.bth)])
        self.assertEqual(self.att.weap_heat, 0.0)
        self.assertEqual(self.att.weapons[1].recycle, 0)
        self.assertFalse(self.att.has_status(MechStatus.FIRED))


# =============================================================================
# Leg 2 — TIC alpha-strike into the hex
# =============================================================================

class TestTicAlphaStrike(M4MapFixture):
    """firetic empties a whole trigger group at the hex lock, in ascending
    weapon order, with the full heat/ammo/recycle tail per weapon."""

    def setUp(self):
        super().setUp()
        # TestMech: weapons 0-1 = IS.MediumLaser (LARM), 2 = IS.AC/10
        # (RTORSO, 10-round bin in RTORSO slot 7)
        self.mech = self.add("TestMech", "Alpha", 10, 10, facing=0)
        self.ml = get_weapon("IS.MediumLaser")
        self.ac10 = get_weapon("IS.AC/10")
        self.ammo_bin = self.mech.sections[Location.RTORSO].criticals[7]
        self.assertEqual(self.ammo_bin.data, 10)    # template bin

    def test_tic_alpha_strike_fires_ascending_with_full_tail(self):
        msgs = add_tic(self.mech, 0, "0-2")
        self.assertNotIn("Invalid weapon number!", msgs)
        self.lock_hex(self.mech, 10, 7)             # plain lock, empty hex

        fired_order = []

        def spy(engine, mech, weapnum, **kwargs):
            fired_order.append(weapnum)
            return fire_weapon_number(engine, mech, weapnum, **kwargs)

        with patch('systems.tic.fire_weapon_number', side_effect=spy), \
                patch('systems.combat.roll_2d6', return_value=7):
            msgs = fire_tic(self.engine, self.mech, "0")

        self.assertIn("Firing weapons in tic #0!", msgs)
        # firetic walks the tic set in ascending weapon order
        self.assertEqual(fired_order, [0, 1, 2])

        # Heat tally: MechWeapHeat += weapon.heat per shot
        # (mech.combat.c:1379)
        self.assertEqual(self.mech.weap_heat,
                         float(2 * self.ml.heat + self.ac10.heat))
        # Ammo tally: one AC/10 round gone (mech.combat.c:1400-1401)
        self.assertEqual(self.ammo_bin.data, 9)
        # Recycle: WEAPON_TICK * vrt on every firing crit
        # (mech.combat.c:1353-1354)
        for wn, weapon in ((0, self.ml), (1, self.ml), (2, self.ac10)):
            ws = self.mech.weapons[wn]
            slot = self.mech.sections[ws.section].criticals[ws.critical]
            self.assertEqual(slot.data, WEAPON_TICK * weapon.vrt)
            self.assertEqual(ws.recycle, WEAPON_TICK * weapon.vrt)
        self.assertTrue(self.mech.has_status(MechStatus.FIRED))

    def test_empty_tic_clicks(self):
        self.lock_hex(self.mech, 10, 7)
        with patch('systems.tic.fire_weapon_number') as fwn:
            msgs = fire_tic(self.engine, self.mech, "3")
        fwn.assert_not_called()
        self.assertEqual(msgs, ["Firing weapons in tic #3!",
                                "*Click* (the tic contained no weapons)"])


# =============================================================================
# Leg 3 — AMS defender shaving incoming salvos
# =============================================================================
# Depends on the AMS/cluster wiring into systems/combat.py (Agent zeta).
# The C sequencing under test: the cluster roll decides missiles_hit FIRST,
# then AMSMissiles shaves it (mech.combat.missile.c:325-357); the AMS is
# charged heat + bare-vrt recycle at locate time (:551-552) and spends its
# 1d6 rounds even when the whole salvo misses (:493-510).

class TestAMSSalvoShaving(M4MapFixture):

    def setUp(self):
        super().setUp()
        # AssaultMech weapon 3 = IS.LRM-10; defender 7 hexes north
        self.att = self.add("AssaultMech", "Archer", 10, 10, facing=0)
        self.dfn = self.add("TestMech", "Shield", 10, 3, facing=180)
        self.ams, self.ams_slot, self.ams_ammo, self.ams_wn = \
            mount_ams(self.dfn, rounds=12)
        self.see(self.att, self.dfn)
        self.see(self.dfn, self.att)
        ok, msg = set_target(self.engine, self.att, self.dfn)
        self.assertTrue(ok, msg)

    def _fire(self, to_hit_roll):
        # cluster 2d6 = 7 -> 6 of 10 LRMs hit; AMS 1d6 = 4 shot down
        with patch('systems.combat.roll_2d6', return_value=7), \
                patch('systems.missile.roll_2d6', return_value=7), \
                patch('systems.missile.roll_1d6', return_value=4):
            return fire_weapon_number(self.engine, self.att, 3,
                                      to_hit_roll=to_hit_roll,
                                      location_roll=7)

    def test_ams_shaves_the_salvo_after_the_cluster_roll(self):
        armor_before = total_armor(self.dfn)
        result = self._fire(to_hit_roll=12)
        self.assertTrue(result.hit)

        # 6 hit (cluster roll 7 on a 10-rack) - 4 shot down = 2 land
        self.assertEqual(armor_before - total_armor(self.dfn), 2)
        # AMS ammo down by exactly the shot-down count
        # (mech.combat.missile.c:497-504)
        self.assertEqual(self.ams_ammo.data, 8)
        # AMS charged at locate time: heat and BARE vrt recycle
        # (mech.combat.missile.c:551-552)
        self.assertEqual(self.dfn.weap_heat, float(self.ams.heat))
        self.assertEqual(self.ams_slot.data, self.ams.vrt)
        self.assertEqual(self.dfn.weapons[self.ams_wn].recycle,
                         self.ams.vrt)

    def test_fired_salvo_miss_leaves_ams_unchanged(self):
        from systems.combat_ammunition import count_ammo
        launcher = get_weapon("IS.LRM-10")
        ammo_before = count_ammo(self.att, launcher.index)
        armor_before = total_armor(self.dfn)
        result = self._fire(to_hit_roll=2)      # BTH > 2: guaranteed miss
        self.assertFalse(result.hit)
        self.assertEqual(result.damage_dealt, 0)
        self.assertEqual(total_armor(self.dfn), armor_before)
        # HitTarget's caller guard precedes AMS (mech.combat.c:1730-1734).
        self.assertEqual(self.ams_ammo.data, 12)
        self.assertEqual(self.dfn.weap_heat, 0)
        self.assertEqual(self.ams_slot.data, 0)
        self.assertEqual(self.dfn.weapons[self.ams_wn].recycle, 0)
        self.assertFalse(any("Anti-Missile System activates" in text for text in result.messages))
        # FireWeapon still performs its ordinary launcher tail after the miss.
        self.assertEqual(count_ammo(self.att, launcher.index), ammo_before-1)
        self.assertEqual(self.att.weap_heat, float(launcher.heat))
        self.assertEqual(self.att.weapons[3].recycle, 2*launcher.vrt)
        self.assertEqual(self.att.shots_fired, 1)


# =============================================================================
# Leg 4 — physical brawl with recycle pacing
# =============================================================================

class TestPhysicalBrawl(unittest.TestCase):
    """Punch, get refused while the arm recovers, heartbeat past
    PHYSICAL_RECYCLE_TIME, punch again; plus the kick-miss PSR fall."""

    def _make_mech(self, name):
        mech = create_mech_from_template(get_template("TestMech"), name=name)
        mech.set_hex_position(50, 50)
        mech.set_status(MechStatus.STARTED)
        return mech

    def setUp(self):
        self.engine = GameEngine()
        self.att = self._make_mech("Brawler")
        self.tgt = self._make_mech("Punchbag")
        # Adjacent: 100 cartesian units (0.31 hex) due north, facing off
        self.att.facing = 0
        self.tgt.facing = 180
        self.tgt.fx = self.att.fx
        self.tgt.fy = self.att.fy - 100.0
        self.tgt.x, self.tgt.y = self.att.x, self.att.y
        self.tgt.z = self.att.z
        board = GameMap(100, 100)
        board._id = 1000
        board.mapvis, board.maxvis, board.maplight = 30, 60, 2
        self.engine.register_entity(board)
        for unit in (self.att, self.tgt):
            board.add_mech(unit)
            self.engine.register_entity(unit)
        board.losinfo[(self.att._id, self.tgt._id)] = SEES
        board.losinfo[(self.tgt._id, self.att._id)] = SEES

    @patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
    def test_punch_recycle_pacing(self, _psr):
        # 1: the punch lands and the arm starts its 60-tick recycle
        # (mech.physical.c:1401, btconfig.h PHYSICAL_RECYCLE_TIME)
        result = mech_punch(self.att, self.tgt, arm='R',
                            roll=12, location_roll=3)[0]
        self.assertTrue(result.hit)
        self.assertEqual(self.att.sections[Location.RARM].recycle,
                         PHYSICAL_RECYCLE_TIME)

        # 2: a second attempt is refused by all_limbs_recycled
        # (mech.physical.c:59-74)
        refused = mech_punch(self.att, self.tgt, arm='R', roll=12)[0]
        self.assertFalse(refused.success)
        self.assertIn("You still have arms recovering from another attack.",
                      refused.messages)

        # 3: heartbeat past the recycle window (mech.update.c:1594-1626)
        self.engine.run_ticks(PHYSICAL_RECYCLE_TIME + 1)
        self.assertEqual(self.att.sections[Location.RARM].recycle, 0)

        # 4: the arm has recovered — the punch is allowed again
        again = mech_punch(self.att, self.tgt, arm='R',
                           roll=12, location_roll=3)[0]
        self.assertTrue(again.success)
        self.assertTrue(again.hit)
        self.assertEqual(self.att.sections[Location.RARM].recycle,
                         PHYSICAL_RECYCLE_TIME)

    @patch('systems.physical.mech_falls')
    @patch('systems.physical.make_piloting_roll', return_value=PSR_FAIL)
    def test_kick_miss_forces_the_attacker_psr_fall(self, psr, falls):
        # A missed kick forces the attacker's PSR (mech.physical.c:1466-1480);
        # the failed roll drops the kicker.
        result = mech_kick(self.att, self.tgt, roll=2)
        self.assertTrue(result.success)         # the attack was attempted
        self.assertFalse(result.hit)
        psr.assert_called_once()
        falls.assert_called_once()
        self.assertIn("You lose your balance and fall down!",
                      result.messages)
        # The kicking leg still pays its recycle, hit or miss
        # (mech.physical.c:1401)
        self.assertEqual(self.att.sections[Location.RLEG].recycle,
                         PHYSICAL_RECYCLE_TIME)


if __name__ == '__main__':
    unittest.main()
