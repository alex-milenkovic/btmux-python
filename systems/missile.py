# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.bth.c
#   btech/mech.combat.c
#   btech/mech.combat.misc.c
#   btech/mech.combat.missile.c
#   btech/mech.fire.c
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/mech.combat.h
#   btech/src/btech/mech.h
# Historical Aerospace sources:
#   btech/mech.bth.c
#   btech/mech.combat.misc.c
#   src/hcode/btech/btmacros.h
#   src/hcode/btech/mech.combat.c
#   src/hcode/btech/mech.combat.h
#   src/hcode/btech/mech.h

"""
Missile combat mechanics: cluster rolls, AMS, inferno burn, NARC pods.

Standalone port of the missile arm of the BTMux combat path.  The fire-path
wiring into systems/combat.py happens in a later wave; this module exposes
the pieces plus their integration contract.

C references:
- mech.combat.missile.c:31-118   Missile_Hit (grouped damage application)
- mech.combat.missile.c:119-189  MissileHitIndex (cluster-table row index)
- mech.combat.missile.c:212-371  NARC pod attach + AMS application to a salvo
- mech.combat.missile.c:474-558  AMSMissiles / LocateAMSDefenses
- mech.combat.misc.c:160-206     heat_effect / Inferno_Hit
- mech.fire.c:20-42, 146-170     inferno_burn / water_extinguish_inferno
- mech.utils.c:2447-2457         checkAllSections

Integration contract for the wiring wave (fire path, systems/combat.py):

AMS (mech.combat.missile.c:231-260, 325-360):
- AMS is skipped when the incoming salvo's ammo mode has SWARM_MODE,
  SWARM1_MODE or MINE_MODE set (:232-234; design comment :474-481 - never
  used against Arrow IV / Thunder / Flare / Swarm / Swarm-1).  Use
  ams_defends_against().
- AMS has NO arc check: a functional, enabled, loaded AMS defends against
  any incoming missile salvo regardless of direction (:525-535).
- Call order: locate_ams_defenses(target) then ams_missiles(...) BEFORE the
  to-hit result is consulted - the AMS charges heat and starts its recycle
  even when the incoming salvo misses (:551-552).  The shot-down count is
  applied AFTER the cluster-table roll: hit = max(0, hit - shot_down)
  (:325-357); use apply_ams_to_salvo().
- NARC/iNARC pods count as incoming=1 (:236-238) and are wholly stopped if
  anything is shot down (:243-253); pass ams_shot_down into narc_attach().

NARC BTH terms (later-wave combat.py wiring, NOT implemented here):
- Attacker with an iNARC haywire pod attached: +1 BTH (mech.bth.c:224-225).
- Firing NARC_MODE homing missiles at a target carrying a NARC/iNARC homing
  pod: -1 BTH (mech.bth.c:227-230).

The glancing-blow hook: MissileHitIndex is called with glance=1 when
mudconf.btech_glancing_blows is on and the player's roll exactly equals the
to-hit (mech.combat.missile.c:331); a -1 return means "hit with exactly one
missile" (:181-183, consumed at :332-333 as hit = MIN(incoming, 1)).
"""
from core.randomness import roll as source_roll

import random
from core.randomness import draw
from dataclasses import dataclass, field
from typing import Callable, Optional, TYPE_CHECKING

from core.events import EventType
from entities.crittypes import is_weapon, weapon2i
from entities.map import HEAVY_FOREST, LIGHT_FOREST, WATER
from entities.mech import (
    AmmoMode,
    CritStatus,
    FireMode,
    Location,
    MechStatus,
    NUM_CRITICALS,
    NUM_SECTIONS,
    SectionConfig,
    Specials,
    UnitType,
    MoveType,
)
from entities.weapon import (
    Weapon,
    WeaponFlags,
    WeaponType,
    get_weapon_by_index,
)
from systems.combat import (
    HitGroup,
    apply_damage_with_transfer,
    determine_hit_group,
    find_ammo_for_weapon,
    get_hit_location,
    part_is_nonfunctional,
)
from systems.ecm import (
    INARC_ECM_ATTACHED,
    angel_ecm_disturbed,
    angel_ecm_protected,
    any_ecm_disturbed,
    check_ecm,
    ecm_protected,
)
from systems.physical import LOCATION_NAMES

if TYPE_CHECKING:
    from entities.mech import Mech


# =============================================================================
# Per-section special bits (attached pods)
# =============================================================================

# Section.specials bits (mech.h:703-704).  Module constants per the
# systems/ecm.py:48 pattern - deliberately NOT in entities/mech.py.
NARC_ATTACHED = 0x00000001
INARC_HOMING_ATTACHED = 0x00000002
# Haywire follows the mech.h run; systems/ecm.py:48 already pins
# INARC_ECM_ATTACHED = 0x8, fixing haywire's slot at 0x4.
INARC_HAYWIRE_ATTACHED = 0x00000004
INARC_NEMESIS_ATTACHED = 0x00000010
# INARC_ECM_ATTACHED (0x8) is imported from systems/ecm.py:48.

# mudconf.btech_fasaadvvhlfire (heat_effect's vehicle-fire arm,
# mech.combat.misc.c:167-172).  TODO (named): vehicle_start_burn /
# checkVehicleInFire when the FASA advanced vehicle fire rules land.
# Default 0 per VERIFY-1.
BTECH_FASAADVVHLFIRE = 0

# Ammo modes AMS never defends against (mech.combat.missile.c:232-234;
# design comment :474-481).
AMS_IMMUNE_AMMO_MODES = (AmmoMode.SWARM_MODE | AmmoMode.SWARM1_MODE |
                         AmmoMode.MINE_MODE)


# =============================================================================
# Message plumbing
# =============================================================================

@dataclass
class MessageLog:
    """Player-visible strings a call produced, split by audience."""
    attacker: list = field(default_factory=list)
    target: list = field(default_factory=list)
    broadcast: list = field(default_factory=list)   # MechLOSBroadcast
    ordered: list = field(default_factory=list)


def emit_notice(log,audience,unit,text):
    getattr(log,audience).append(text)
    log.ordered.append((audience,text))
    if unit is not None:_notify(unit,text)


# Wiring hook for messages produced inside event callbacks (which have no
# result object to carry them).  The game layer may replace this.
NOTIFY_HOOK: Optional[Callable[['Mech', str], None]] = None


def _notify(mech: 'Mech', message: str) -> None:
    from systems.movement_commands import notify
    notify(mech, message)
    if NOTIFY_HOOK is not None:
        NOTIFY_HOOK(mech, message)


# =============================================================================
# Dice
# =============================================================================

def roll_1d6() -> int:
    from core.randomness import number
    return number(1, 6)


def roll_2d6() -> int:
    return source_roll()


# =============================================================================
# Small ports
# =============================================================================

def check_all_sections(mech: 'Mech', special_bit: int) -> bool:
    """
    Does any non-destroyed section carry the given specials bit?

    Port of checkAllSections (mech.utils.c:2447-2457); the per-section
    check (checkSectionForSpecial) skips destroyed sections.
    """
    from systems.parts import check_all_sections as shared_check
    return shared_check(mech, special_bit)


def hot_loading(weapon: 'Weapon', firemode: int) -> bool:
    """
    Is this launcher being hotloaded?

    Port of HotLoading (btmacros.h:634-635): an IDF-flagged weapon whose
    crit firemode has HOTLOAD_MODE set.
    """
    return bool(weapon.special & WeaponFlags.IDF) and \
        bool(firemode & FireMode.HOTLOAD_MODE)


def clustersize(weapon: 'Weapon') -> int:
    """
    Salvo grouping size for Missile_Hit.

    Port of Clustersize (mech.combat.h:17): 5 iff the weapon has any of
    IDF|MRM|ROCKET set AND its per-missile damage is 1, else 1.  LRMs
    cluster in 5s; SRMs (damage 2) roll a location per missile; LBX
    pellets (no missile flags) go one per pellet.
    """
    if (weapon.special & (WeaponFlags.IDF | WeaponFlags.MRM |
                          WeaponFlags.ROCKET)) and weapon.damage == 1:
        return 5
    return 1


# =============================================================================
# E.3.1 - MissileHitIndex
# =============================================================================

def missile_hit_index(
    mech: 'Mech',
    weapon: 'Weapon',
    w_section: int,
    w_crit: int,
    target: Optional['Mech'],
    glance: bool = False,
    dice: Optional[tuple] = None,
    fresh_roll: Optional[int] = None,
) -> int:
    """
    Cluster-table row index (0..10) for a missile salvo, or -1 for the
    glancing "exactly one missile" case.

    Port of MissileHitIndex (mech.combat.missile.c:119-189).  The return
    value is the row consumed by entities.weapon.get_missiles_hit.

    - Artemis bonus: the firing crit's ammomode has ARTEMIS_MODE
      (:127-128).  Artemis linkage is enforced at mode-set time
      (FindArtemisForWeapon, mech.utils.c:1417-1447), not here.
    - NARC bonus: ammomode has NARC_MODE and the target carries a NARC or
      iNARC homing pod on any non-destroyed section (:137-142).
    - Both bonuses are negated when the target is ECM/Angel-ECM protected
      (:132-135) or the attacker is ECM-disturbed (:144-147).
    - roll_inc = +2 if the weapon is a missile and either bonus applies -
      ONE non-stacking bonus (:152-153).  No IDF restriction.
    - Dice: three d6 are rolled and sorted; a hotloading launcher uses the
      two lowest - 2, otherwise a FRESH 2d6 - 2 is used (:155-167).
    - Streak vs a non-Angel-protected target (attacker not
      Angel-disturbed) returns 10 outright (:169-172).
    - Glancing: -4 on the table; below 0 returns -1, meaning the caller
      hits with exactly one missile (:174-183).
    - Result clamped to 0..10 (:185-187).

    Args:
        dice: optional (d6, d6, d6) for the hotload triple.
        fresh_roll: optional pre-rolled 2d6 for the non-hotload path.
    """
    slot = mech.sections[w_section].criticals[w_crit]
    hotloading = hot_loading(weapon, slot.firemode)

    use_artemis = bool(slot.ammomode & AmmoMode.ARTEMIS_MODE)
    use_narc = False

    if target is not None:
        if ecm_protected(target) or angel_ecm_protected(target):
            # mech.combat.missile.c:132-135
            use_artemis = False
            use_narc = False
        else:
            # mech.combat.missile.c:137-142
            use_narc = bool(slot.ammomode & AmmoMode.NARC_MODE) and (
                check_all_sections(target, NARC_ATTACHED) or
                check_all_sections(target, INARC_HOMING_ATTACHED))

    if any_ecm_disturbed(mech):
        # mech.combat.missile.c:144-147
        use_artemis = False
        use_narc = False

    roll_inc = 0
    # One non-stacking +2 (mech.combat.missile.c:152-153)
    if weapon.weapon_type == WeaponType.TMISSILE and (use_artemis or use_narc):
        roll_inc = 2

    # Roll 3 times... if we're hotloading, we'll use the 2 lowest
    # (mech.combat.missile.c:155-163)
    r1, r2, r3 = dice if dice is not None else (
        draw("missile_pre_roll", 1, 6, roll_1d6),
        draw("missile_pre_roll", 1, 6, roll_1d6),
        draw("missile_pre_roll", 1, 6, roll_1d6))
    r1, r2, r3 = sorted((r1, r2, r3))

    if hotloading:
        hit_roll = r1 + r2 - 2
    else:
        # Fresh 2d6 (Roll()), NOT the three dice above
        # (mech.combat.missile.c:165-167)
        hit_roll = (fresh_roll if fresh_roll is not None
                    else source_roll("missile_cluster", roll_2d6)) - 2

    # Streak auto-max (mech.combat.missile.c:169-172)
    if ((target is None or not angel_ecm_protected(target)) and
            not angel_ecm_disturbed(mech) and
            (weapon.special & WeaponFlags.STREAK)):
        return 10

    # Glancing, per max tech, is -4 off the missile hit table (:174-179)
    if glance:
        roll_inc += -4
    if roll_inc:
        hit_roll = hit_roll + roll_inc
    # Below 0 while glancing: hit with one missile (:181-183)
    if glance and hit_roll < 0:
        return -1

    return max(min(hit_roll, 10), 0)


# =============================================================================
# E.3.3 - Missile_Hit
# =============================================================================

@dataclass
class MissileHitResult:
    """Outcome of missile_hit."""
    total_damage: int = 0
    # (Location, damage, is_rear) per applied group
    groups: list = field(default_factory=list)
    missiles_applied: int = 0
    missiles_absorbed: int = 0      # eaten by woods
    messages: MessageLog = field(default_factory=MessageLog)


def missile_hit(
    attacker: 'Mech',
    target: 'Mech',
    weapon: 'Weapon',
    missiles_hit: int,
    damage_each: int,
    salvo_size: int,
    fire_mode: int = 0,
    ammo_mode: int = 0,
    mod_damage_with_woods: Optional[bool] = None,
    location_rolls: Optional[list] = None,
    damage_func=None,
    hit_x=-1,hit_y=-1,los=1,bth=0,swarm_attack=False,
) -> MissileHitResult:
    """
    Apply a missile salvo's damage in groups of salvo_size.

    Port of Missile_Hit (mech.combat.missile.c:31-118), mech-target arm.
    Each group rolls its own hit location (FindTargetHitLoc, :105) and
    applies this_time * damage_each through the normal damage-transfer
    path (DamageMech, :107-111).  salvo_size comes from clustersize().

    Woods absorption (mech.combat.missile.c:55-99): when
    mod_damage_with_woods (mudconf.btech_moddamagewithwoods) is on, the
    target stands in a forest hex, fire_mode > -1 and ammo_mode > -1, and
    (MechZ - 2) <= hex elevation, the salvo's total damage loses 2 in
    light forest / 4 in heavy forest before grouping; the missile count is
    rebuilt as total_damage // damage (:69-73).
    TODO (hex-fire wave): possibly_ignite_or_clear (:75-76).
    TODO (MW wave): pc_to_dam_conversion (:108) - mech targets pass
    damage through unchanged.

    Args:
        location_rolls: optional list of pre-rolled 2d6 location rolls,
            consumed one per group.
        damage_func: optional
            (location, damage, is_rear, is_critical) -> dealt
            callable standing in for the C's DamageMech
            (mech.combat.missile.c:107-111) — each group's damage MUST run
            the caller's full damage path, whose internal-damage arm rolls
            criticals (HandleCritical).  None keeps the bare
            armor/transfer application (no crit rolls) for standalone
            callers.
    """
    result = MessageLog()
    out = MissileHitResult(messages=result)
    orig_num_missiles = missiles_hit
    total_damage = missiles_hit * damage_each

    from systems.combat_ranges import config
    if mod_damage_with_woods is None:
        mod_damage_with_woods=config(attacker,'moddamagewithwoods',0)
    terrain=target.map.rterrain(target.x,target.y) if target is not None and target.map else getattr(target,'terrain',None)
    elevation=target.map.base_elevation(target.x,target.y) if target is not None and target.map else getattr(target,'elev',0)
    if (target is not None and mod_damage_with_woods and terrain in (LIGHT_FOREST,HEAVY_FOREST)
            and fire_mode>-1 and ammo_mode>-1 and target.z-2<=elevation):
        from systems.combat import possibly_ignite_or_clear
        clear_damage=total_damage
        total_damage-=2 if terrain==LIGHT_FOREST else 4
        if attacker.map:
            possibly_ignite_or_clear(attacker,weapon.index,ammo_mode,clear_damage,target.x,target.y,1)

        if total_damage <= 0:                       # :68-72
            missiles_hit = 0
        else:
            missiles_hit = total_damage // damage_each

        # Word choice (mech.combat.missile.c:78-89)
        if weapon.weapon_type == WeaponType.TMISSILE:
            buf = "missile" + ("s" if orig_num_missiles > 1 else "")
        elif ammo_mode & AmmoMode.LBX_MODE:
            buf = "pellet" + ("s" if orig_num_missiles > 1 else "")
        elif (fire_mode & FireMode.ULTRA_MODE) or \
                (fire_mode & FireMode.RFAC_MODE) or \
                (fire_mode & FireMode.RAC_MODES):
            buf = "slug" + ("s" if orig_num_missiles > 1 else "")
        else:
            buf = "damage"

        # mech.combat.missile.c:91-98
        emit_notice(result,"attacker",attacker,"%s %s %s absorbed by the trees!" % (
            "The" if orig_num_missiles == 1 else
            ("All of the" if missiles_hit == 0 else "Some of the"),
            buf,
            "is" if orig_num_missiles == 1 else "are"))
        emit_notice(result,"target",target,"The trees absorb %s %s" % (
            "the" if (orig_num_missiles == 1 or missiles_hit == 0)
            else "some of the", buf))

        out.missiles_absorbed = orig_num_missiles - missiles_hit

    rolls = list(location_rolls) if location_rolls else []

    # Grouped application loop (mech.combat.missile.c:100-117)
    while missiles_hit:
        this_time = min(salvo_size, missiles_hit)
        this_damage = this_time * damage_each

        if target is None:
            from systems.combat import hex_hit
            hex_hit(attacker,hit_x,hit_y,weapon.index,ammo_mode,this_damage,1)
            out.total_damage+=this_damage
            out.missiles_applied+=this_time
            missiles_hit-=this_time
            continue

        # FindTargetHitLoc analogue: hit group from attack geometry, rear
        # when the back table is used.
        hit_group = determine_hit_group(attacker, target)
        is_rear = (hit_group == HitGroup.BACK)
        roll = rolls.pop(0) if rolls else None
        from systems.hit_locations import target_hit_location
        location, is_rear, is_critical = target_hit_location(attacker, target, hit_group, roll)

        if damage_func is not None:
            # DamageMech routing (mech.combat.missile.c:107-111): the
            # caller's damage path owns transfer AND the critical rolls.
            dealt = damage_func(location, this_damage, is_rear,
                                is_critical)
        else:
            from systems.personal_damage import personal_to_damage
            dealt = apply_damage_with_transfer(target,location,
                personal_to_damage(target,weapon,this_damage),is_rear,attacker,is_critical,
                weapon,ammo_mode,getattr(attacker,'_engine',None),bth=bth,los=los,
                ignore_swarmers=swarm_attack)

        out.groups.append((location, this_damage, is_rear))
        out.total_damage += dealt
        out.missiles_applied += this_time
        missiles_hit -= this_time

    return out


# =============================================================================
# E.3.2 - AMS
# =============================================================================

@dataclass
class AMSDefense:
    """A located, charged AMS - LocateAMSDefenses' out-params."""
    weapon: 'Weapon'         # the AMS weapon (AMStype)
    section: int             # AMS mount section
    critical: int            # AMS crit slot
    ammo_section: int        # ammoLoc
    ammo_critical: int       # ammoCrit


def ams_defends_against(ammo_mode: int) -> bool:
    """
    May AMS engage a salvo carrying this ammo mode?

    mech.combat.missile.c:232-234 skips SWARM/SWARM1/MINE modes; the
    design comment at :474-481 adds Arrow IV / Thunder / Flare, which are
    those same modes plus artillery (never IsMissile, so never reaches
    the AMS block).
    """
    return not (ammo_mode & AMS_IMMUNE_AMMO_MODES)


def locate_ams_defenses(target: 'Mech') -> Optional[AMSDefense]:
    """
    Find, charge and recycle the target's AMS, if any.

    Port of LocateAMSDefenses (mech.combat.missile.c:515-558):
    - Gate: AMS tech special, started, and MechStatus.AMS_ENABLED
      (:522-525).
    - Scan all sections x crits for an AMS-flagged weapon that is
      functional and not recycling; FIRST match wins and there is NO arc
      check - the AMS defends regardless of the salvo's direction
      (:527-535).
    - Its ammo bin is found through the normal FindAmmoForWeapon search
      order and must have rounds (:545-549).
    - On success the AMS recycle and heat are applied IMMEDIATELY
      (:551-552), before the incoming salvo's to-hit result is consulted:
      the AMS fires even at salvos that miss.

    NB recycle asymmetry: the C sets the AMS recycle with BARE vrt
    (SetRecyclePart(..., MechWeapons[w].vrt), :551), NOT the fire path's
    usual WEAPON_TICK * vrt (mech.combat.c:1353-1354).  Copied verbatim.
    """
    if not (target.specials & (Specials.IS_ANTI_MISSILE_TECH |
                               Specials.CL_ANTI_MISSILE_TECH)):
        return None
    if not target.is_started or \
            not target.has_status(MechStatus.AMS_ENABLED):
        return None

    ams_weapon = None
    ams_section = -1
    ams_critical = -1
    for i in range(NUM_SECTIONS):
        for j in range(NUM_CRITICALS):
            crit = target.sections[i].criticals[j]
            if not is_weapon(crit.type):
                continue
            weapon = get_weapon_by_index(weapon2i(crit.type))
            if weapon is None or not (weapon.special & WeaponFlags.AMS):
                continue
            # WpnIsRecycling: the crit data byte is the recycle countdown
            from systems.parts import weapon_is_recycling
            if part_is_nonfunctional(target, i, j) or weapon_is_recycling(target,i,j):
                continue
            ams_weapon = weapon
            ams_section, ams_critical = i, j
            break
        if ams_weapon is not None:
            break

    if ams_weapon is None:
        return None

    from systems.combat_ammunition import find_normal_ammo_for_weapon
    found = find_normal_ammo_for_weapon(target, ams_weapon.index, ams_section)
    if found is None:
        return None
    ammo_loc, ammo_crit = found
    if target.sections[ammo_loc].criticals[ammo_crit].data <= 0:
        return None

    if target._engine:
        from core.game_loop import update_recycling
        update_recycling(target._engine,target)
    # SetRecyclePart with BARE vrt (mech.combat.missile.c:551) - see the
    # asymmetry note in the docstring.
    target.sections[ams_section].criticals[ams_critical].data = \
        ams_weapon.vrt
    for ws in target.weapons:
        if ws.section == ams_section and ws.critical == ams_critical:
            ws.recycle = ams_weapon.vrt

    # MechWeapHeat += heat (mech.combat.missile.c:552)
    target.weap_heat += float(ams_weapon.heat)

    return AMSDefense(
        weapon=ams_weapon,
        section=ams_section,
        critical=ams_critical,
        ammo_section=int(ammo_loc),
        ammo_critical=ammo_crit,
    )


@dataclass
class AMSFireResult:
    """Outcome of ams_missiles."""
    shot_down: int = 0
    messages: MessageLog = field(default_factory=MessageLog)


def ams_missiles(
    attacker: 'Mech',
    target: 'Mech',
    incoming: int,
    ams_weapon: 'Weapon',
    ammo_section: int,
    ammo_critical: int,
    los: int,
    missiles_did_hit: bool,
    shots_roll: Optional[int] = None,
) -> AMSFireResult:
    """
    Fire the AMS at an incoming salvo.

    Port of AMSMissiles (mech.combat.missile.c:486-513):
    - Clan AMS (CLAT flag) shoots down 2d6, IS 1d6 (:493-496).
    - Capped at the incoming count (:498-499).
    - Ammo consumed = missiles shot down, floored at 0 rounds
      (:501-504); the RETURN VALUE IS NOT RE-CAPPED against the rounds
      actually in the bin - verbatim C behavior.
    - If the salvo missed anyway, the target still sees the flavor
      message and 0 is returned (:506-510) - ammo and heat were already
      spent.

    Args:
        shots_roll: optional pre-rolled shot-down count (the 1d6/2d6).
    """
    result = AMSFireResult()

    if shots_roll is not None:
        shot_down = shots_roll
    elif ams_weapon.special & WeaponFlags.CLAT:
        shot_down = source_roll("ams_rolls", roll_2d6)
    else:
        shot_down = draw("ams_rolls",1,6,roll_1d6)

    if shot_down > incoming:
        shot_down = incoming

    bin_ = target.sections[ammo_section].criticals[ammo_critical]
    if shot_down >= bin_.data:
        bin_.data = 0
    else:
        bin_.data -= shot_down

    if not missiles_did_hit:
        emit_notice(result.messages,'target',target,
            "Your Anti-Missile System activates and shoots at the "
            "incoming missiles!")
        result.shot_down = 0
        return result

    result.shot_down = shot_down
    return result


def apply_ams_to_salvo(hit: int, shot_down: int, los: int, *, attacker=None,target=None) -> tuple:
    """
    Subtract AMS kills from a cluster-rolled hit count, with messages.

    Port of the salvo arm at mech.combat.missile.c:325-360: applied AFTER
    the cluster-table roll; hit = max(0, hit - shot_down).  The
    all-shot-down attacker message is LOS-gated, the partial pair is not -
    verbatim.

    Returns (new_hit, MessageLog).
    """
    messages = MessageLog()

    if shot_down > 0:
        if shot_down >= hit:
            if los:
                emit_notice(messages,'attacker',attacker,
                    "All of your missiles are shot down by the target!")
            emit_notice(messages,'target',target,
                "Your Anti-Missile System activates and shoots all the "
                "incoming missiles!")
        else:
            emit_notice(messages,'attacker',attacker,
                "The target shoots down %d of your missiles!" % shot_down)
            emit_notice(messages,'target',target,
                "Your Anti-Missile System activates and shoots down %d "
                "incoming missiles!" % shot_down)

    return (max(0, hit - shot_down), messages)


# =============================================================================
# E.3.4 - Inferno
# =============================================================================

@dataclass
class HeatEffectResult:
    """Outcome of heat_effect."""
    exploded: bool = False
    burn_time: int = 0
    messages: MessageLog = field(default_factory=MessageLog)


@dataclass
class InfernoHitResult:
    """Outcome of inferno_hit."""
    burn_time: int = 0
    extinguished: bool = False
    messages: MessageLog = field(default_factory=MessageLog)


def _inferno_end_event(event) -> None:
    """
    Burn timer expiry: clear JELLIED.

    Port of inferno_end_event (mech.fire.c:20-27); the C notifies "You
    feel suddenly far cooler as the fires finally die."
    """
    mech = event.data
    mech.clear_crit_status(CritStatus.JELLIED)
    mech._burn_event = None
    _notify(mech, "You feel suddenly far cooler as the fires finally die.")


def inferno_burn(engine, mech: 'Mech', time: int) -> None:
    """
    Start (or extend) the timed JELLIED burn.

    Port of inferno_burn (mech.fire.c:29-42): a fresh burn sets JELLIED
    and schedules the end event `time` seconds out; RE-JELLYING ADDS the
    new time onto the burn's REMAINING time (muxevent_last_type_data +
    time, :39-41) and reschedules.
    """
    engine = engine or getattr(mech, "_engine", None)
    if engine is None:
        # Retain duration until entity registration supplies an event clock.
        # No secondary heat/piloting countdown consumes this detached duration.
        if not mech.has_crit_status(CritStatus.JELLIED):
            mech.set_crit_status(CritStatus.JELLIED)
            mech.burn_recovery_countdown = max(1, time)
        else:
            mech.burn_recovery_countdown = (
                max(0, getattr(mech, 'burn_recovery_countdown', 0)) + time)
        return

    mech._engine = engine
    if not mech.has_crit_status(CritStatus.JELLIED):
        mech.set_crit_status(CritStatus.JELLIED)
        mech._burn_event = engine.schedule_event(
            time, EventType.INFERNO, _inferno_end_event, data=mech)
        return

    # Re-jelly: remaining + time (mech.fire.c:39-41)
    old = getattr(mech, '_burn_event', None)
    remaining = max(0, getattr(mech, 'burn_recovery_countdown', 0))
    mech.burn_recovery_countdown = 0
    if old is not None and not old.zombie:
        remaining = max(0, old.tick - engine.tick)
        old.cancel()
    mech._burn_event = engine.schedule_event(
        remaining + time, EventType.INFERNO, _inferno_end_event, data=mech)


def heat_effect(
    engine,
    attacker: Optional['Mech'],
    target: 'Mech',
    heatdam: int,
    from_inferno: bool = False,
    explosion_roll: Optional[int] = None,
) -> HeatEffectResult:
    """
    Route external heat onto a unit: burn for mechs, boom for vehicles.

    Port of heat_effect (mech.combat.misc.c:160-188):
    - Mobile non-mech units (not MECH/MW/BSUIT, not a DropShip, movement
      type not NONE) take the vehicle arm: with btech_fasaadvvhlfire off
      (default 0, VERIFY-1), 2d6 > 8 destroys the vehicle outright
      (:174-181).  TODO (named): the btech_fasaadvvhlfire arm
      (vehicle_start_burn / checkVehicleInFire, :167-172).
      TODO: explode_unit debris + kill channel (:180-181).
    - Everything else burns: inferno_burn(target, heatdam * 6)
      (:184-186), i.e. x6 of the heat damage in seconds.

    Args:
        explosion_roll: optional pre-rolled 2d6 for the vehicle arm.
    """
    result = HeatEffectResult()

    is_ds = target.unit_type in (UnitType.DS, UnitType.SPHEROID_DS)
    if (target.unit_type not in (UnitType.MECH, UnitType.MW,
                                 UnitType.BSUIT) and not is_ds and
            target.move_type != MoveType.NONE):
        if (target.unit_type in (UnitType.VEH_GROUND, UnitType.VTOL) and
                getattr(engine or target._engine, "advanced_vehicle_fire", BTECH_FASAADVVHLFIRE)):
            from systems.vehicle_fire import start_burn, check_vehicle_in_fire
            if from_inferno:
                start_burn(engine or target._engine, target, attacker)
            else:
                check_vehicle_in_fire(engine or target._engine, target, roll=explosion_roll)

        else:
            from core.randomness import draw
            roll = explosion_roll if explosion_roll is not None \
                else source_roll('fire_rolls', roll_2d6)
            if roll > 8:                            # :174
                from systems.damage import explode_unit,destroy_state,channel_emit_kill,KILL_TYPE_HEAT
                from systems.sensors import los_broadcast
                from systems.movement_commands import notify
                result.exploded = True
                result.messages.broadcast.append("explodes!")
                result.messages.target.append(
                    "The heat's too much for your vehicle! It blows up!")
                los_broadcast(target,'explodes!')
                notify(target,"The heat's too much for your vehicle! It blows up!")
                destroy_state(target,engine or target._engine,historical=target.unit_type==UnitType.AERO)
                target.kill_reason=KILL_TYPE_HEAT
                channel_emit_kill(target,attacker,KILL_TYPE_HEAT)
                explode_unit(target,attacker or target)
    else:
        if heatdam:                                 # :184-186
            result.burn_time = heatdam * 6
            inferno_burn(engine, target, result.burn_time)

    return result


def inferno_hit(
    engine,
    attacker: 'Mech',
    target: 'Mech',
    missiles: int,
    los: int,
) -> InfernoHitResult:
    """
    An inferno salvo splashes the target with burning jelly.

    Port of Inferno_Hit (mech.combat.misc.c:191-206):
    - hmod = (missiles + 1) / 2; heat_effect gets hmod * 30, which
      inferno_burn multiplies x6 - total burn hmod * 180 seconds
      ("3min for _each_ missile", :204).
    - NO normal damage is applied on an inferno hit - the caller returns
      right after Inferno_Hit (mech.combat.missile.c:362-371).
    - water_extinguish_inferno runs immediately: a target standing deep
      in water just wastes the shooter's missiles (:205).

    A live vehicle-burn event and an existing JELLIED effect share the repeat-hit message.
    """
    hmod = (missiles + 1) // 2
    result = InfernoHitResult()

    from entities.map import FIRE
    from systems.sensors import los_broadcast
    from systems.movement_commands import notify
    from core.events import EventType
    owner = engine or target._engine
    if target.has_crit_status(CritStatus.JELLIED) or owner is not None and owner.has_event(EventType.VEHICLE_BURN,target):
        # mech.combat.misc.c:195-198
        result.messages.broadcast.append("burns a bit more brightly.")
        result.messages.target.append(
            "%ch%crMore burning jelly joins the flames!%cn")
    else:
        # mech.combat.misc.c:199-202
        result.messages.broadcast.append("suddenly bursts into flames!")
        result.messages.target.append(
            "%ch%crYou are sprayed with burning jelly!%cn")

    for message in result.messages.broadcast:los_broadcast(target,message)
    for message in result.messages.target:notify(target,message)
    he = heat_effect(engine, attacker, target, hmod * 30,
                     from_inferno=True)
    result.burn_time = he.burn_time

    wr = water_extinguish_inferno(engine, target)
    result.extinguished = wr.extinguished
    result.messages.target.extend(wr.messages.target)
    result.messages.broadcast.extend(wr.messages.broadcast)

    return result


@dataclass
class WaterExtinguishResult:
    """Outcome of water_extinguish_inferno."""
    extinguished: bool = False
    messages: MessageLog = field(default_factory=MessageLog)


def water_extinguish_inferno(
    engine,
    mech: 'Mech',
    in_water: Optional[bool] = None,
) -> WaterExtinguishResult:
    """
    Deep water puts out the burning jelly.

    Port of water_extinguish_inferno (mech.fire.c:146-170): only a
    jellied CLASS_MECH in water is eligible, and a mech standing at
    depth -1 (elev == -1, not fallen) keeps burning.  On extinguish the
    burn event is removed and JELLIED cleared.
    Adds the source steam/smoke hex decoration (mech.fire.c:166-169).

    Args:
        in_water: override for InWater(mech); default derives it from the
            cached hex terrain (terrain == WATER and z < 0).
    """
    result = WaterExtinguishResult()

    if in_water is None:
        from systems.movement_commands import in_water as actual_in_water
        in_water = actual_in_water(mech)

    from physics.collision import mech_elevation
    elev = mech_elevation(mech)
    if (not in_water or mech.unit_type != UnitType.MECH or
            not mech.has_crit_status(CritStatus.JELLIED) or
            (elev == -1 and not mech.is_fallen)):
        return result

    owner = engine or mech._engine
    if owner is not None:
        owner.cancel_events_of_type(EventType.INFERNO, mech)
    old = getattr(mech, '_burn_event', None)
    if old is not None:
        old.cancel()
        mech._burn_event = None
    mech.clear_crit_status(CritStatus.JELLIED)

    mech.burn_recovery_countdown = 0
    from systems.movement_commands import notify
    notify(mech, 'The flames extinguish in a roar of steam!')
    from systems.sensors import los_broadcast
    los_broadcast(mech,'is surrounded by a plume of steam as the flames extinguish.')
    from physics.decorations import add_smoke
    if mech.map is not None:
        add_smoke(engine or mech._engine, mech.map, mech.x, mech.y)
    result.extinguished = True
    result.messages.target.append(
        "The flames extinguish in a roar of steam!")
    result.messages.broadcast.append(
        "is surrounded by a plume of steam as the flames extinguish.")
    return result


# =============================================================================
# E.3.4 - NARC pods
# =============================================================================

# Pod type codes (wNARCType, mech.combat.missile.c:213-229)
NARC_POD_NONE = 0
NARC_POD_NARC = 1
NARC_POD_INARC_HOMING = 2
NARC_POD_INARC_HAYWIRE = 3
NARC_POD_INARC_ECM = 4


def resolve_narc_pod_type(weapon: 'Weapon', ammomode: int) -> int:
    """
    Is this shot a pod, and which kind?

    Port of the pod-type resolution at mech.combat.missile.c:212-229:
    - A NARC launcher NOT set to NARC_MODE (explosive rounds) fires pods.
    - An iNARC launcher NOT set to INARC_EXPLO_MODE fires pods: haywire
      or ECM per the ammo mode, else homing.
    """
    if weapon.weapon_type != WeaponType.TMISSILE:
        return NARC_POD_NONE
    if (weapon.special & WeaponFlags.NARC) and \
            not (ammomode & AmmoMode.NARC_MODE):
        return NARC_POD_NARC
    if (weapon.special & WeaponFlags.INARC) and \
            not (ammomode & AmmoMode.INARC_EXPLO_MODE):
        if ammomode & AmmoMode.INARC_HAYWIRE_MODE:
            return NARC_POD_INARC_HAYWIRE
        if ammomode & AmmoMode.INARC_ECM_MODE:
            return NARC_POD_INARC_ECM
        return NARC_POD_INARC_HOMING
    return NARC_POD_NONE


@dataclass
class NarcAttachResult:
    """Outcome of narc_attach."""
    attached: bool = False
    location: Optional[int] = None
    is_rear: bool = False
    shot_down: bool = False
    messages: MessageLog = field(default_factory=MessageLog)


def narc_attach(attacker,target,pod_type,did_hit,los,ams_shot_down=0,location_roll=None):
    """Pod state and target-first attachment notices at their C call sites."""
    from systems.hit_locations import narc_hit_location
    from systems.parts import armor_string
    result=NarcAttachResult()
    def tell(audience,unit,text):emit_notice(result.messages,audience,unit,text)
    if not did_hit:
        tell('attacker',attacker,'Your NARC Beacon flies off into the distance.')
        return result
    if ams_shot_down>0:
        result.shot_down=True
        if los:tell('attacker',attacker,'The pod is shot down by the target!')
        tell('target',target,'Your Anti-Missile System activates and shoots down the incoming pod!')
        return result
    location,result.is_rear=narc_hit_location(attacker,target,roll=location_roll)
    if location<0:
        tell('attacker',attacker,'Your NARC Beacon attaches to the target!')
        return result
    result.location,result.attached=int(location),True
    name=armor_string(target,location)
    section=target.sections[location]
    section.specials|={NARC_POD_NARC:NARC_ATTACHED,NARC_POD_INARC_HOMING:INARC_HOMING_ATTACHED,
        NARC_POD_INARC_HAYWIRE:INARC_HAYWIRE_ATTACHED,NARC_POD_INARC_ECM:INARC_ECM_ATTACHED}[pod_type]
    if pod_type==NARC_POD_INARC_HAYWIRE:
        tell('target',target,'Your targetting system goes a bit haywire!')
    elif pod_type==NARC_POD_INARC_ECM:check_ecm(target)
    rear=' (Rear)' if result.is_rear else ''
    tell('target',target,f'A NARC Beacon has been attached to your {name}{rear}!')
    tell('attacker',attacker,f"Your NARC Beacon attaches to the target's {name}{rear}!")
    return result


def missile_hit_target(attacker,target,weapon,section,critical,bth,roll,incoming,player_roll,*,
                       hit_x=-1,hit_y=-1,los=1,cluster_roll=None,ams_roll=None,location_rolls=None,swarm_attack=False):
    """MissileHitTarget boundary: AMS also fires on a direct-call miss."""
    from systems.combat import AttackResult,_missile_weapon_hit
    from systems.combat_ranges import config
    slot=attacker.sections[section].criticals[critical]
    result=AttackResult(target_id=target._id if target is not None else None,
        hit=roll>=bth,bth=bth,impact_bth=bth,roll=player_roll,swarm_attack=swarm_attack,
        glancing=bool(config(attacker,'glancing_blows',1) and player_roll==bth))
    return _missile_weapon_hit(result,attacker,target,weapon,slot.firemode,slot.ammomode,section,
        critical,attacker._engine,cluster_roll,ams_roll,location_rolls,None,
        incoming=incoming,los=los,hit_x=hit_x,hit_y=hit_y)


def swarm_next_target(attacker,source,visited,fof):
    """First eligible roster entry within 1.9 hexes, preserving source order."""
    from systems.targeting import find_range
    from systems.los import in_line_of_sight_nb
    for candidate in attacker.map.mechs_on_map:
        if candidate is None or (fof and candidate.team==attacker.team):continue
        if candidate.status&MechStatus.COMBAT_SAFE or any(candidate is old for old in visited):continue
        distance=find_range(source.fx,source.fy,source.fz,candidate.fx,candidate.fy,candidate.fz)
        if distance<1.9 and in_line_of_sight_nb(source,candidate,source.x,source.y,distance):return candidate
    return None


def swarm_hit_target(attacker,target,weapon,section,critical,bth,roll,incoming,fof,player_roll,**kwargs):
    """SwarmHitTarget: cumulative flight distance, unchanged BTH, no revisits."""
    from systems.combat import AttackResult
    from systems.combat_ranges import extreme_range
    from systems.targeting import find_range
    from systems.los import in_line_of_sight_nb
    from systems.movement_commands import notify
    from systems.notifications import identity,pair_los_broadcast
    result=AttackResult(hit=True,bth=bth,roll=player_roll)
    from data.missile_clusters import missile_row
    row=missile_row(weapon,attacker)
    if row is None:return result
    missiles=row[10]  # The C ignores its incoming parameter.
    source=attacker
    flown=0
    visited=[]
    while missiles>0:
        flown+=find_range(source.fx,source.fy,source.fz,target.fx,target.fy,target.fz)
        if flown>extreme_range(attacker,weapon):
            notify(target,'Luckily, the missiles fall short of you!')
            result.missiles_remaining=missiles
            return result
        distance=find_range(attacker.fx,attacker.fy,attacker.fz,target.fx,target.fy,target.fz)
        los=(2 if visited else 1) if in_line_of_sight_nb(attacker,target,attacker.x,attacker.y,distance) else 0
        next_roll=source_roll('swarm_rolls', roll_2d6) if visited else roll
        hit=missile_hit_target(attacker,target,weapon,section,critical,bth,next_roll,missiles,player_roll,los=los,**kwargs)
        result.swarm_targets.append(target._id)
        result.messages.extend(hit.messages)
        result.message_audiences.extend(hit.message_audiences)
        for key in ('damage_dealt','armor_damage','internal_damage','criticals_rolled','ams_shot_down'):
            setattr(result,key,getattr(result,key)+getattr(hit,key))
        if result.location is None:
            result.location,result.is_rear,result.is_critical=hit.location,hit.is_rear,hit.is_critical
        missiles=result.missiles_remaining=hit.missiles_remaining
        if missiles<=0 or len(visited)==10:return result
        visited.append(target)
        source=target
        target=swarm_next_target(attacker,source,visited,fof)
        if target is None:return result
        if target is not attacker:notify(target,'The missile-swarm turns towards you!')
        if in_line_of_sight_nb(attacker,source,attacker.x,attacker.y,
                find_range(attacker.fx,attacker.fy,attacker.fz,source.fx,source.fy,source.fz)):
            notify(attacker,f'Your missile-swarm of {missiles} missile'+('s' if missiles>1 else '')+
                   f' targets {"YOU!!" if target is attacker else identity(attacker,target)}!')
        pair_los_broadcast(attacker,target,"'s missile-swarm targets %s!")
    return result
