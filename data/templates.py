# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# Host-derived portions also retain notices/TinyMUX.txt.
# General sources:
#   btech/btpr/conf.c
#   btech/map.conditions.c
#   btech/mech.build.c
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/mech.h
#   btech/src/include/btconfig.h
#   btech/template.c
#   src/conf.c
# Historical Aerospace sources:
#   btech/mech.build.c
#   btech/mech.utils.c
#   btech/template.c
#   src/hcode/btech/btmacros.h
#   src/hcode/btech/map.conditions.c
#   src/hcode/btech/mech.h
#   src/hcode/include/btconfig.h

"""
Mech templates for BTMux Python reimplementation.

This module defines hardcoded mech templates that can be instantiated into
fully-configured Mech objects with weapons, armor, and equipment.

Phase 7 implements a simple TestMech template for integration testing.
"""

from dataclasses import dataclass, field
from typing import Optional
from core.randomness import float32

from entities.crittypes import (
    EMPTY,
    Special,
    crits_in_loc,
    i2ammo,
    i2special,
    i2weapon,
)
from entities.mech import (
    Mech,
    Location,
    MoveType,
    UnitType,
    NUM_CRITICALS,
    NUM_SECTIONS,
    Section,
    Specials,
    FireMode,
    WeaponState,
)
from entities.pilot import Pilot
from entities.weapon import Weapon, get_weapon
from systems.combat import WeaponSlot


# =============================================================================
# Armor Layout Dataclass
# =============================================================================

@dataclass
class ArmorLayout:
    """
    Defines armor distribution for a mech template.

    All values are points of armor/structure.
    """
    # Head
    head: int = 9

    # Torsos (front/rear/internal)
    ct_front: int = 16
    ct_rear: int = 5
    ct_internal: int = 16

    lt_front: int = 12
    lt_rear: int = 4
    lt_internal: int = 12

    rt_front: int = 12
    rt_rear: int = 4
    rt_internal: int = 12

    # Arms
    la_armor: int = 10
    la_internal: int = 8

    ra_armor: int = 10
    ra_internal: int = 8

    # Legs
    ll_armor: int = 12
    ll_internal: int = 12

    rl_armor: int = 12
    rl_internal: int = 12

    # Head internal is always 3 for mechs
    head_internal: int = 3


# =============================================================================
# Weapon Mount Dataclass
# =============================================================================

@dataclass
class WeaponMount:
    """
    Defines a weapon mount on a mech template.
    """
    weapon_name: str              # Weapon catalog name (e.g., "IS.MediumLaser")
    location: Location            # Where the weapon is mounted
    ammo: int = -1               # -1 = infinite (energy), else ammo count
    rear_mounted: bool = False   # Is this a rear-mounted weapon?


# =============================================================================
# Mech Template Dataclass
# =============================================================================

@dataclass
class MechTemplate:
    """
    A mech template that can be instantiated into a Mech object.

    Templates define the base stats, armor layout, and weapon loadout
    for a particular mech design.
    """
    # Identity
    name: str                          # Template name (e.g., "TestMech")
    mech_type: str                    # Mech reference/variant (e.g., "TST-1A")

    # Base stats
    tonnage: int = 50                 # Weight in tons

    # Movement (walking/running in hexes per turn)
    walk_mp: int = 4                  # Walking movement points
    run_mp: int = 6                   # Running movement points
    jump_mp: int = 0                  # Jump movement points

    move_type: MoveType = MoveType.BIPED
    unit_type: UnitType = UnitType.MECH

    # Heat management
    heat_sinks: int = 10              # Number of heat sinks
    double_heat_sinks: bool = False   # Use double heat sinks?

    # Technology
    clan_tech: bool = False           # Is this Clan tech?
    # Targeting computer: places a TARGETING_COMPUTER crit and flags every
    # TC-able weapon ON_TC at build time (template.c:2174-2181)
    targeting_computer: bool = False

    # Armor layout
    armor: ArmorLayout = field(default_factory=ArmorLayout)

    # Weapon loadout
    weapons: list[WeaponMount] = field(default_factory=list)

    # Sensor ranges (defaults)
    tac_range: int = 15
    lrs_range: int = 30
    scan_range: int = 20

    def calculate_max_speed(self) -> float:
        """
        Calculate max speed in KPH from running MP.

        BTMux formula: speed = MP * 10.75 (approximately)
        For a 6 run MP mech: 64.5 KPH
        """
        # Standard BattleTech: 1 hex = ~30m, 1 turn = 10s
        # BTMux uses continuous movement, so we convert MP to KPH
        # 6 MP running = 64.5 KPH is the standard reference
        return self.run_mp * 10.75


# =============================================================================
# Critical Slot Layout
# =============================================================================

# The first ten heat sinks are integral to the engine and occupy no crit slots;
# only the extras get placed. Reference: mech.build.c FillDefaultCriticals
# leaves no sink slots for mechs, and map.conditions.c:216-222 only ever
# decrements MechRealNumsinks for sinks that do have a slot.
ENGINE_INTEGRAL_HEAT_SINKS = 10

# Placement scan orders. These are a port-local invention: the C reads explicit
# CRIT_n lines out of the template file (template.c:2476-2497), which the
# Workstream C file loader will use. Until then our four invented templates get
# a deterministic rule - torsos before limbs for equipment, legs first for jets.
_AMMO_SEARCH_ORDER = (
    Location.LTORSO, Location.RTORSO, Location.CTORSO,
    Location.LLEG, Location.RLEG, Location.LARM, Location.RARM,
)
_HEAT_SINK_SEARCH_ORDER = _AMMO_SEARCH_ORDER
_JUMP_JET_SEARCH_ORDER = (
    Location.LLEG, Location.RLEG,
    Location.LTORSO, Location.RTORSO, Location.CTORSO,
)


def fill_default_criticals(mech: Mech) -> None:
    """
    Lay the fixed internals (actuators, engine, gyro, cockpit) into every
    section, blanking the slots first.

    Reference: mech.build.c lines 39-103 (FillDefaultCriticals), called per
    section from the template loader
    """
    for index in range(NUM_SECTIONS):
        fill_default_criticals_section(mech, index)


def fill_default_criticals_section(mech: Mech, index: int) -> None:
    """
    Blank one section's crit slots and write its default contents.

    CLASS_MECH layout, straight from the C:
    - HEAD: life support, sensors, cockpit, (free), sensors, life support
    - CTORSO: engine x3, gyro x4 (slots 3-6), engine x3 (slots 7-9), 2 free
    - LTORSO/RTORSO: all free
    - arms and legs: shoulder-or-hip, upper, lower, hand-or-foot, rest free

    Note the C blanks all NUM_CRITICALS slots even in locations that only have
    CritsInLoc() of them, and that the HEAD's slot 3 is deliberately left empty.

    Reference: mech.build.c lines 39-103 (FillDefaultCriticals)
    """
    criticals = mech.sections[index].criticals

    # mech.build.c:43-48
    for loop in range(NUM_CRITICALS):
        criticals[loop].type = EMPTY
        criticals[loop].data = 0
        criticals[loop].firemode = FireMode.NONE
        criticals[loop].ammomode = 0

    if mech.unit_type == UnitType.AERO:
        if index == 4:
            for slot, kind in zip(criticals, (Special.LIFE_SUPPORT, Special.SENSORS,
                    Special.COCKPIT, Special.SENSORS, Special.LIFE_SUPPORT)):
                slot.type = i2special(kind)
        elif index == 5:
            for loop, slot in enumerate(criticals):
                slot.type = i2special(Special.ENGINE if loop in (2, 10) else Special.HEAT_SINK)
    if mech.unit_type != UnitType.MECH:
        return

    if index == Location.HEAD:
        # mech.build.c:62-70
        criticals[0].type = i2special(Special.LIFE_SUPPORT)
        criticals[1].type = i2special(Special.SENSORS)
        criticals[2].type = i2special(Special.COCKPIT)
        criticals[4].type = i2special(Special.SENSORS)
        criticals[5].type = i2special(Special.LIFE_SUPPORT)
    elif index == Location.CTORSO:
        # mech.build.c:72-83
        criticals[0].type = i2special(Special.ENGINE)
        criticals[1].type = i2special(Special.ENGINE)
        criticals[2].type = i2special(Special.ENGINE)
        criticals[3].type = i2special(Special.GYRO)
        criticals[4].type = i2special(Special.GYRO)
        criticals[5].type = i2special(Special.GYRO)
        criticals[6].type = i2special(Special.GYRO)
        criticals[7].type = i2special(Special.ENGINE)
        criticals[8].type = i2special(Special.ENGINE)
        criticals[9].type = i2special(Special.ENGINE)
    elif index in (Location.RTORSO, Location.LTORSO):
        # mech.build.c:85-87 - side torsos carry nothing by default
        pass
    elif index in (Location.LARM, Location.RARM, Location.LLEG, Location.RLEG):
        # mech.build.c:89-101
        criticals[0].type = i2special(Special.SHOULDER_OR_HIP)
        criticals[1].type = i2special(Special.UPPER_ACTUATOR)
        criticals[2].type = i2special(Special.LOWER_ACTUATOR)
        criticals[3].type = i2special(Special.HAND_OR_FOOT_ACTUATOR)


def find_empty_crit_run(mech: Mech, loc: int, count: int) -> int:
    """
    First slot of the earliest run of `count` consecutive EMPTY slots in loc.

    Returns -1 if the run does not fit. Only slots that exist in this location
    are considered (CritsInLoc, mech.utils.c:151-166).
    """
    limit = crits_in_loc(mech, loc)
    criticals = mech.sections[loc].criticals

    for start in range(limit - count + 1):
        if all(criticals[start + i].type == EMPTY for i in range(count)):
            return start

    return -1


def _place_template_weapons(mech: Mech, template: MechTemplate) -> None:
    """
    Put each WeaponMount into crit slots and register it in mech.weapons.

    A weapon occupies `Weapon.crits` consecutive slots that all carry the same
    type byte, i2weapon(index) (mech.h:156); the run is what the C's
    FindWeapons walk rediscovers at runtime (mech.utils.c:1030-1066).
    """
    for mount in template.weapons:
        weapon = get_weapon(mount.weapon_name)
        if weapon is None:
            raise ValueError(f"Unknown weapon: {mount.weapon_name}")

        start = find_empty_crit_run(mech, mount.location, weapon.crits)
        if start < 0:
            raise ValueError(
                f"{weapon.name} needs {weapon.crits} free crit slots in "
                f"{Location(mount.location).name} on {template.name}"
            )

        crit_type = i2weapon(weapon.index)
        for i in range(weapon.crits):
            crit = mech.sections[mount.location].criticals[start + i]
            crit.type = crit_type
            if mount.rear_mounted:
                # REAR_MOUNT lives on the crit slot's firemode in the C too
                # (mech.h:616 REAR_MOUNT, set by the template loader).
                crit.firemode |= FireMode.REAR_MOUNT

        mech.weapons.append(WeaponState(
            section=mount.location,
            critical=start,
            weapon_idx=weapon.index,
        ))


def _place_template_ammo(mech: Mech, template: MechTemplate) -> None:
    """
    Give every ammo-using mount with `ammo > 0` one bin.

    The bin's type is i2ammo(weapon index) (mech.h:157) and its round count
    lives in the slot's data byte, which is what GetPartData means for an ammo
    slot (btmacros.h:311).
    """
    for mount in template.weapons:
        weapon = get_weapon(mount.weapon_name)
        if weapon is None:
            raise ValueError(f"Unknown weapon: {mount.weapon_name}")
        if mount.ammo <= 0 or not weapon.uses_ammo:
            continue

        for loc in (mount.location,) + _AMMO_SEARCH_ORDER:
            slot = find_empty_crit_run(mech, loc, 1)
            if slot >= 0:
                crit = mech.sections[loc].criticals[slot]
                crit.type = i2ammo(weapon.index)
                crit.data = mount.ammo
                break
        else:
            raise ValueError(
                f"No free crit slot for {weapon.name} ammo on {template.name}"
            )


def _place_template_heat_sinks(mech: Mech, template: MechTemplate) -> None:
    """
    Place the heat sinks that are not integral to the engine.

    Doubles occupy three HEAT_SINK slots each (the DHS crit-slot triple the
    destruction compensation in systems/damage.py walks — "if ((nhs++) % 3
    == 2) MechRealNumsinks++", map.conditions.c:216-222); singles one.
    """
    extras = max(0, template.heat_sinks - ENGINE_INTEGRAL_HEAT_SINKS)
    slots_per_sink = 3 if template.double_heat_sinks else 1

    for _ in range(extras):
        for loc in _HEAT_SINK_SEARCH_ORDER:
            slot = find_empty_crit_run(mech, loc, slots_per_sink)
            if slot >= 0:
                for i in range(slots_per_sink):
                    mech.sections[loc].criticals[slot + i].type = \
                        i2special(Special.HEAT_SINK)
                break
        else:
            raise ValueError(f"No free crit slot for a heat sink on {template.name}")


# The weapon names TCAble excludes, minus the "IS."/"CL." prefix
# (template.c:1539-1545 — strcmp on &MechWeapons[...].name[3]).
_NOT_TCABLE_NAMES = ("Flamer", "MachineGun", "LightMachineGun",
                     "HeavyMachineGun")

TCOMP_TECH = 0x1000000                     # mech.h:1192


def _place_targeting_computer(mech: Mech, template: MechTemplate) -> None:
    """
    Place a targeting computer crit and flag every TC-able weapon ON_TC.

    Port of the template loader's tc_count block (template.c:2174-2181):
    when a TC is mounted, every weapon crit whose weapon passes TCAble
    (template.c:1539-1545) gets ON_TC OR'd into its firemode.  TCAble =
    energy (TBEAM) or ballistic (TAMMO), name (past the tech prefix) not
    Flamer / MachineGun / LightMachineGun / HeavyMachineGun, and not
    PCOMBAT — the port's catalog carries no PCOMBAT weapons, so that
    clause has nothing to exclude.

    In the C the computer's crit count comes from the template file
    itself (the loader only counts what the file lists); no shipped
    template here mounts one, so a single slot is placed.
    """
    if not template.targeting_computer:
        return

    mech.specials2 |= TCOMP_TECH           # template.c:2175

    from entities.crittypes import is_weapon, weapon2i
    from entities.weapon import WeaponType, get_weapon_by_index

    for loc in _AMMO_SEARCH_ORDER:
        slot = find_empty_crit_run(mech, loc, 1)
        if slot >= 0:
            mech.sections[loc].criticals[slot].type = \
                i2special(Special.TARGETING_COMPUTER)
            break
    else:
        raise ValueError(
            f"No free crit slot for a targeting computer on {template.name}")

    # template.c:2176-2181 — every crit slot of every TCAble weapon
    for x in range(NUM_SECTIONS):
        for y in range(crits_in_loc(mech, x)):
            t = mech.sections[x].criticals[y].type
            if not is_weapon(t):
                continue
            weapon = get_weapon_by_index(weapon2i(t))
            if weapon is None:
                continue
            if weapon.weapon_type not in (WeaponType.TBEAM,
                                          WeaponType.TAMMO):
                continue
            if weapon.name[3:] in _NOT_TCABLE_NAMES:
                continue
            mech.sections[x].criticals[y].firemode |= FireMode.ON_TC


def _place_template_jump_jets(mech: Mech, template: MechTemplate) -> None:
    """
    One JUMP_JET crit per jump MP.

    Each jet is worth MP1 of jump speed when it dies
    (map.conditions.c:223-235), so the count has to be real.
    """
    for _ in range(template.jump_mp):
        for loc in _JUMP_JET_SEARCH_ORDER:
            slot = find_empty_crit_run(mech, loc, 1)
            if slot >= 0:
                mech.sections[loc].criticals[slot].type = i2special(Special.JUMP_JET)
                break
        else:
            raise ValueError(f"No free crit slot for a jump jet on {template.name}")


# =============================================================================
# Factory Function
# =============================================================================

def create_mech_from_template(
    template: MechTemplate,
    name: Optional[str] = None,
    pilot: Optional[Pilot] = None,
) -> Mech:
    """
    Create a fully-configured Mech from a template.

    Args:
        template: The MechTemplate to instantiate
        name: Optional custom name (defaults to template name)
        pilot: Optional Pilot; a default Pilot() is seated if omitted

    Returns:
        A new Mech object with all stats, armor, crit slots and weapons
        configured
    """
    # Determine specials flags
    specials = Specials.NONE
    if template.clan_tech:
        specials |= Specials.CLAN_TECH
    if template.double_heat_sinks:
        specials |= Specials.DOUBLE_HEAT_TECH

    # Create the mech
    mech = Mech(
        name=name or template.name,
        mech_type=template.mech_type,
        unit_type=template.unit_type,
        move_type=template.move_type,
        tonnage=template.tonnage,
        num_sinks=template.heat_sinks,
        max_speed=template.calculate_max_speed(),
        walk_speed=template.walk_mp,
        run_speed=template.run_mp,
        jump_mp=template.jump_mp,
        jump_speed=template.jump_mp * 10.75,
        tac_range=template.tac_range,
        lrs_range=template.lrs_range,
        scan_range=template.scan_range,
        specials=specials,
    )

    # Seat a pilot. The C keeps a dbref here and the skill chain falls back to
    # DEFAULT_* when it is invalid (mech.utils.c:580-590, 619-629); a spawned
    # mech in this port always has someone in it unless told otherwise.
    mech.pilot = pilot if pilot is not None else Pilot()

    # Apply armor layout
    armor = template.armor

    # Head
    mech.sections[Location.HEAD].armor = armor.head
    mech.sections[Location.HEAD].armor_orig = armor.head
    mech.sections[Location.HEAD].internal = armor.head_internal
    mech.sections[Location.HEAD].internal_orig = armor.head_internal

    # Center Torso
    mech.sections[Location.CTORSO].armor = armor.ct_front
    mech.sections[Location.CTORSO].armor_orig = armor.ct_front
    mech.sections[Location.CTORSO].rear = armor.ct_rear
    mech.sections[Location.CTORSO].rear_orig = armor.ct_rear
    mech.sections[Location.CTORSO].internal = armor.ct_internal
    mech.sections[Location.CTORSO].internal_orig = armor.ct_internal

    # Left Torso
    mech.sections[Location.LTORSO].armor = armor.lt_front
    mech.sections[Location.LTORSO].armor_orig = armor.lt_front
    mech.sections[Location.LTORSO].rear = armor.lt_rear
    mech.sections[Location.LTORSO].rear_orig = armor.lt_rear
    mech.sections[Location.LTORSO].internal = armor.lt_internal
    mech.sections[Location.LTORSO].internal_orig = armor.lt_internal

    # Right Torso
    mech.sections[Location.RTORSO].armor = armor.rt_front
    mech.sections[Location.RTORSO].armor_orig = armor.rt_front
    mech.sections[Location.RTORSO].rear = armor.rt_rear
    mech.sections[Location.RTORSO].rear_orig = armor.rt_rear
    mech.sections[Location.RTORSO].internal = armor.rt_internal
    mech.sections[Location.RTORSO].internal_orig = armor.rt_internal

    # Left Arm
    mech.sections[Location.LARM].armor = armor.la_armor
    mech.sections[Location.LARM].armor_orig = armor.la_armor
    mech.sections[Location.LARM].internal = armor.la_internal
    mech.sections[Location.LARM].internal_orig = armor.la_internal

    # Right Arm
    mech.sections[Location.RARM].armor = armor.ra_armor
    mech.sections[Location.RARM].armor_orig = armor.ra_armor
    mech.sections[Location.RARM].internal = armor.ra_internal
    mech.sections[Location.RARM].internal_orig = armor.ra_internal

    # Left Leg
    mech.sections[Location.LLEG].armor = armor.ll_armor
    mech.sections[Location.LLEG].armor_orig = armor.ll_armor
    mech.sections[Location.LLEG].internal = armor.ll_internal
    mech.sections[Location.LLEG].internal_orig = armor.ll_internal

    # Right Leg
    mech.sections[Location.RLEG].armor = armor.rl_armor
    mech.sections[Location.RLEG].armor_orig = armor.rl_armor
    mech.sections[Location.RLEG].internal = armor.rl_internal
    mech.sections[Location.RLEG].internal_orig = armor.rl_internal

    # Critical slots: fixed internals first, then the loadout on top of them.
    fill_default_criticals(mech)
    _place_template_weapons(mech, template)
    _place_template_ammo(mech, template)
    _place_template_heat_sinks(mech, template)
    _place_template_jump_jets(mech, template)
    _place_targeting_computer(mech, template)

    return mech


def create_weapon_slots_from_template(template: MechTemplate) -> list[WeaponSlot]:
    """
    Create WeaponSlot objects from a template's weapon loadout.

    This is separate from the mech creation because WeaponSlots are
    runtime combat state, not part of the base Mech structure.

    Args:
        template: The MechTemplate with weapon definitions

    Returns:
        List of WeaponSlot objects ready for combat
    """
    slots = []
    for mount in template.weapons:
        weapon = get_weapon(mount.weapon_name)
        if weapon is None:
            raise ValueError(f"Unknown weapon: {mount.weapon_name}")

        slot = WeaponSlot(
            weapon=weapon,
            section=mount.location,
            ammo_count=mount.ammo,
        )
        slots.append(slot)

    return slots


# =============================================================================
# Pre-Defined Templates
# =============================================================================

# TestMech - A basic 50-ton mech for testing
# Inspired by the Hunchback but simplified
TEST_MECH_TEMPLATE = MechTemplate(
    name="TestMech",
    mech_type="TST-1A",
    tonnage=50,
    walk_mp=4,
    run_mp=6,
    jump_mp=0,
    heat_sinks=10,
    double_heat_sinks=False,
    clan_tech=False,
    armor=ArmorLayout(
        # Head
        head=9,
        # Center Torso
        ct_front=21,
        ct_rear=7,
        ct_internal=16,
        # Side Torsos
        lt_front=16,
        lt_rear=6,
        lt_internal=12,
        rt_front=16,
        rt_rear=6,
        rt_internal=12,
        # Arms
        la_armor=12,
        la_internal=8,
        ra_armor=12,
        ra_internal=8,
        # Legs
        ll_armor=16,
        ll_internal=12,
        rl_armor=16,
        rl_internal=12,
    ),
    weapons=[
        # 2x Medium Lasers in left arm
        WeaponMount("IS.MediumLaser", Location.LARM),
        WeaponMount("IS.MediumLaser", Location.LARM),
        # 1x AC/10 in right torso (with ammo)
        WeaponMount("IS.AC/10", Location.RTORSO, ammo=10),
    ],
)


# Alternative: A heavier template for variety
ASSAULT_MECH_TEMPLATE = MechTemplate(
    name="AssaultMech",
    mech_type="AST-1A",
    tonnage=80,
    walk_mp=3,
    run_mp=5,
    jump_mp=0,
    heat_sinks=15,
    double_heat_sinks=False,
    clan_tech=False,
    armor=ArmorLayout(
        # Head
        head=9,
        # Center Torso - heavy armor
        ct_front=35,
        ct_rear=10,
        ct_internal=25,
        # Side Torsos
        lt_front=24,
        lt_rear=8,
        lt_internal=17,
        rt_front=24,
        rt_rear=8,
        rt_internal=17,
        # Arms
        la_armor=20,
        la_internal=13,
        ra_armor=20,
        ra_internal=13,
        # Legs
        ll_armor=26,
        ll_internal=17,
        rl_armor=26,
        rl_internal=17,
    ),
    weapons=[
        # PPC in right arm
        WeaponMount("IS.PPC", Location.RARM),
        # 2x Medium Lasers in left torso
        WeaponMount("IS.MediumLaser", Location.LTORSO),
        WeaponMount("IS.MediumLaser", Location.LTORSO),
        # LRM-10 in right torso
        WeaponMount("IS.LRM-10", Location.RTORSO, ammo=12),
    ],
)


# Light mech for movement testing
LIGHT_MECH_TEMPLATE = MechTemplate(
    name="LightMech",
    mech_type="LGT-1A",
    tonnage=35,
    walk_mp=6,
    run_mp=9,
    jump_mp=0,
    heat_sinks=10,
    double_heat_sinks=False,
    clan_tech=False,
    armor=ArmorLayout(
        # Head
        head=8,
        # Center Torso
        ct_front=12,
        ct_rear=4,
        ct_internal=11,
        # Side Torsos
        lt_front=10,
        lt_rear=3,
        lt_internal=8,
        rt_front=10,
        rt_rear=3,
        rt_internal=8,
        # Arms
        la_armor=6,
        la_internal=6,
        ra_armor=6,
        ra_internal=6,
        # Legs
        ll_armor=10,
        ll_internal=8,
        rl_armor=10,
        rl_internal=8,
    ),
    weapons=[
        # 2x Medium Lasers
        WeaponMount("IS.MediumLaser", Location.RARM),
        WeaponMount("IS.MediumLaser", Location.LARM),
        # SRM-6
        WeaponMount("IS.SRM-6", Location.CTORSO, ammo=15),
    ],
)


# Jump-capable mech for jump testing (inspired by Wolverine)
JUMP_MECH_TEMPLATE = MechTemplate(
    name="JumpMech",
    mech_type="JMP-1A",
    tonnage=55,
    walk_mp=5,
    run_mp=8,
    jump_mp=5,                    # 5 jump jets
    heat_sinks=12,
    double_heat_sinks=False,
    clan_tech=False,
    armor=ArmorLayout(
        # Head
        head=9,
        # Center Torso
        ct_front=18,
        ct_rear=6,
        ct_internal=18,
        # Side Torsos
        lt_front=14,
        lt_rear=5,
        lt_internal=13,
        rt_front=14,
        rt_rear=5,
        rt_internal=13,
        # Arms
        la_armor=12,
        la_internal=9,
        ra_armor=12,
        ra_internal=9,
        # Legs
        ll_armor=14,
        ll_internal=13,
        rl_armor=14,
        rl_internal=13,
    ),
    weapons=[
        # Medium Lasers in arms
        WeaponMount("IS.MediumLaser", Location.LARM),
        WeaponMount("IS.MediumLaser", Location.RARM),
        # SRM-6 in left torso
        WeaponMount("IS.SRM-6", Location.LTORSO, ammo=15),
    ],
)


# Template registry for easy lookup
MECH_TEMPLATES: dict[str, MechTemplate] = {
    "TestMech": TEST_MECH_TEMPLATE,
    "AssaultMech": ASSAULT_MECH_TEMPLATE,
    "LightMech": LIGHT_MECH_TEMPLATE,
    "JumpMech": JUMP_MECH_TEMPLATE,
}


def get_template(name: str) -> Optional[MechTemplate]:
    """
    Get a mech template by name.

    Args:
        name: Template name (e.g., "TestMech")

    Returns:
        The MechTemplate or None if not found
    """
    return MECH_TEMPLATES.get(name)


def list_templates() -> list[str]:
    """Get a list of all available template names."""
    return list(MECH_TEMPLATES.keys())


# =============================================================================
# Vehicle Templates
# =============================================================================

from dataclasses import dataclass, field as dataclass_field
from entities.mech import VehicleLocation
from entities.vehicle import Vehicle, VehicleSection


@dataclass
class VehicleArmorLayout:
    """
    Defines armor distribution for a vehicle template.

    Vehicles typically have:
    - Heavier front armor
    - Lighter rear armor
    - Turret armor (if equipped)
    - No internal structure except turret
    """
    front: int = 30
    left: int = 20
    right: int = 20
    rear: int = 15
    turret_armor: int = 0       # 0 = no turret
    turret_internal: int = 0
    rotor_armor: int = 0        # VTOLs only


@dataclass
class VehicleWeaponMount:
    """Defines a weapon mount on a vehicle template."""
    weapon_name: str
    location: VehicleLocation
    ammo: int = -1
    turret_mounted: bool = False


@dataclass
class VehicleTemplate:
    """
    A vehicle template that can be instantiated into a Vehicle object.
    """
    # Identity
    name: str
    vehicle_type: str

    # Base stats
    tonnage: int = 50

    # Movement
    cruise_mp: int = 4                  # Cruise movement points
    flank_mp: int = 6                   # Flank movement points
    move_type: MoveType = MoveType.TRACK
    unit_type: UnitType = UnitType.VEH_GROUND

    # Armor layout
    armor: VehicleArmorLayout = dataclass_field(default_factory=VehicleArmorLayout)

    # Weapon loadout
    weapons: list[VehicleWeaponMount] = dataclass_field(default_factory=list)

    # Sensor ranges
    tac_range: int = 15
    lrs_range: int = 30
    scan_range: int = 20

    # Special equipment
    has_turret: bool = True
    ice_engine: bool = False

    def calculate_cruise_speed(self) -> float:
        """Calculate cruise speed in KPH from cruise MP."""
        return self.cruise_mp * 10.75

    def calculate_flank_speed(self) -> float:
        """Calculate flank speed in KPH from flank MP."""
        return self.flank_mp * 10.75


def create_vehicle_from_template(template: VehicleTemplate, name: Optional[str] = None) -> Vehicle:
    """
    Create a fully-configured Vehicle from a template.

    Args:
        template: The VehicleTemplate to instantiate
        name: Optional custom name (defaults to template name)

    Returns:
        A new Vehicle object with all stats and armor configured
    """
    from entities.vehicle import Vehicle, TankCritStatus
    from entities.mech import Specials

    # Determine specials flags
    specials = Specials.NONE
    if template.ice_engine:
        specials |= Specials.ICE_TECH

    vehicle = Vehicle(
        name=name or template.name,
        vehicle_type=template.vehicle_type,
        unit_type=template.unit_type,
        move_type=template.move_type,
        tonnage=template.tonnage,
        cruise_speed=template.calculate_cruise_speed(),
        flank_speed=template.calculate_flank_speed(),
        max_speed=template.calculate_flank_speed(),
        tac_range=template.tac_range,
        lrs_range=template.lrs_range,
        scan_range=template.scan_range,
        specials=specials,
    )

    # Apply armor layout
    armor = template.armor

    # Front
    vehicle.sections[VehicleLocation.FSIDE].armor = armor.front
    vehicle.sections[VehicleLocation.FSIDE].armor_orig = armor.front

    # Left
    vehicle.sections[VehicleLocation.LSIDE].armor = armor.left
    vehicle.sections[VehicleLocation.LSIDE].armor_orig = armor.left

    # Right
    vehicle.sections[VehicleLocation.RSIDE].armor = armor.right
    vehicle.sections[VehicleLocation.RSIDE].armor_orig = armor.right

    # Rear
    vehicle.sections[VehicleLocation.BSIDE].armor = armor.rear
    vehicle.sections[VehicleLocation.BSIDE].armor_orig = armor.rear

    # Turret (if equipped)
    if template.has_turret and armor.turret_armor > 0:
        vehicle.sections[VehicleLocation.TURRET].armor = armor.turret_armor
        vehicle.sections[VehicleLocation.TURRET].armor_orig = armor.turret_armor
        vehicle.sections[VehicleLocation.TURRET].internal = armor.turret_internal
        vehicle.sections[VehicleLocation.TURRET].internal_orig = armor.turret_internal

    # Rotor (VTOL only)
    if template.unit_type == UnitType.VTOL and armor.rotor_armor > 0:
        vehicle.sections[VehicleLocation.ROTOR].armor = armor.rotor_armor
        vehicle.sections[VehicleLocation.ROTOR].armor_orig = armor.rotor_armor

    return vehicle


# =============================================================================
# Pre-Defined Vehicle Templates
# =============================================================================

# Light Tracked Tank - Scorpion-like
LIGHT_TANK_TEMPLATE = VehicleTemplate(
    name="LightTank",
    vehicle_type="SCR-1T",
    tonnage=25,
    cruise_mp=4,
    flank_mp=6,
    move_type=MoveType.TRACK,
    unit_type=UnitType.VEH_GROUND,
    has_turret=True,
    armor=VehicleArmorLayout(
        front=24,
        left=18,
        right=18,
        rear=12,
        turret_armor=18,
        turret_internal=6,
    ),
    weapons=[
        VehicleWeaponMount("IS.AC/5", VehicleLocation.TURRET, ammo=20, turret_mounted=True),
    ],
)

# Medium Tracked Tank - Bulldog-like
MEDIUM_TANK_TEMPLATE = VehicleTemplate(
    name="MediumTank",
    vehicle_type="BLD-1G",
    tonnage=60,
    cruise_mp=4,
    flank_mp=6,
    move_type=MoveType.TRACK,
    unit_type=UnitType.VEH_GROUND,
    has_turret=True,
    armor=VehicleArmorLayout(
        front=36,
        left=28,
        right=28,
        rear=20,
        turret_armor=28,
        turret_internal=10,
    ),
    weapons=[
        VehicleWeaponMount("IS.LargeLaser", VehicleLocation.TURRET, turret_mounted=True),
        VehicleWeaponMount("IS.SRM-4", VehicleLocation.FSIDE, ammo=25),
    ],
)

# Heavy Tracked Tank - Demolisher-like
HEAVY_TANK_TEMPLATE = VehicleTemplate(
    name="HeavyTank",
    vehicle_type="DEM-1D",
    tonnage=80,
    cruise_mp=3,
    flank_mp=5,
    move_type=MoveType.TRACK,
    unit_type=UnitType.VEH_GROUND,
    has_turret=True,
    armor=VehicleArmorLayout(
        front=56,
        left=40,
        right=40,
        rear=30,
        turret_armor=40,
        turret_internal=14,
    ),
    weapons=[
        VehicleWeaponMount("IS.AC/20", VehicleLocation.TURRET, ammo=10, turret_mounted=True),
        VehicleWeaponMount("IS.AC/20", VehicleLocation.TURRET, ammo=10, turret_mounted=True),
    ],
)

# Wheeled APC
WHEELED_APC_TEMPLATE = VehicleTemplate(
    name="WheeledAPC",
    vehicle_type="WHL-APC",
    tonnage=35,
    cruise_mp=5,
    flank_mp=8,
    move_type=MoveType.WHEEL,
    unit_type=UnitType.VEH_GROUND,
    has_turret=False,
    armor=VehicleArmorLayout(
        front=20,
        left=16,
        right=16,
        rear=10,
        turret_armor=0,
        turret_internal=0,
    ),
    weapons=[
        VehicleWeaponMount("IS.MachineGun", VehicleLocation.FSIDE, ammo=200),
    ],
)

# Hover Tank - Harasser-like
HOVER_TANK_TEMPLATE = VehicleTemplate(
    name="HoverTank",
    vehicle_type="HRS-1H",
    tonnage=25,
    cruise_mp=8,
    flank_mp=12,
    move_type=MoveType.HOVER,
    unit_type=UnitType.VEH_GROUND,
    has_turret=True,
    armor=VehicleArmorLayout(
        front=16,
        left=12,
        right=12,
        rear=8,
        turret_armor=12,
        turret_internal=4,
    ),
    weapons=[
        VehicleWeaponMount("IS.SRM-6", VehicleLocation.TURRET, ammo=15, turret_mounted=True),
    ],
)

# VTOL - Warrior-like
VTOL_TEMPLATE = VehicleTemplate(
    name="AttackVTOL",
    vehicle_type="WAR-1V",
    tonnage=21,
    cruise_mp=10,
    flank_mp=15,
    move_type=MoveType.VTOL,
    unit_type=UnitType.VTOL,
    has_turret=False,
    armor=VehicleArmorLayout(
        front=14,
        left=10,
        right=10,
        rear=8,
        turret_armor=0,
        turret_internal=0,
        rotor_armor=2,
    ),
    weapons=[
        VehicleWeaponMount("IS.SRM-2", VehicleLocation.FSIDE, ammo=50),
        VehicleWeaponMount("IS.MachineGun", VehicleLocation.FSIDE, ammo=100),
    ],
)


# Vehicle template registry
VEHICLE_TEMPLATES: dict[str, VehicleTemplate] = {
    "LightTank": LIGHT_TANK_TEMPLATE,
    "MediumTank": MEDIUM_TANK_TEMPLATE,
    "HeavyTank": HEAVY_TANK_TEMPLATE,
    "WheeledAPC": WHEELED_APC_TEMPLATE,
    "HoverTank": HOVER_TANK_TEMPLATE,
    "AttackVTOL": VTOL_TEMPLATE,
}


def get_vehicle_template(name: str) -> Optional[VehicleTemplate]:
    """
    Get a vehicle template by name.

    Args:
        name: Template name (e.g., "LightTank")

    Returns:
        The VehicleTemplate or None if not found
    """
    return VEHICLE_TEMPLATES.get(name)


def list_vehicle_templates() -> list[str]:
    """Get a list of all available vehicle template names."""
    return list(VEHICLE_TEMPLATES.keys())


# =============================================================================
# Template-file name tables and helpers (template.c)
# =============================================================================
# Port of template.c's file-scope tables and its self-contained functions.
# Build-flag facts baked in from the C checkout's config: BT_PART_WEIGHTS and
# CLAN_SUPPORT are defined (btconfig.h:29, 89); BT_COMPLEXREPAIRS and
# BT_ADVANCED_ECON are NOT, so the complex-repairs cargo entries
# (template.c:331-608) and the specialcost/ammocost/weapcost/cargocost/
# bombcost arrays (template.c:1053-1059) are compiled out and not ported.
# DumpMechSpecialObjects, dumpweapon_fun and DumpWeapons
# (template.c:2767-2802) are coolmenu display commands — pure MUX UI organs,
# no engine behavior; cited here, not ported.

from entities.mech import CritStatus, MechStatus, SectionConfig
from entities.weapon import WEAPON_INDEX

# btconfig.h:186-200
DEFAULT_TACRANGE = 20
DEFAULT_LRSRANGE = 40
DEFAULT_RADIORANGE = 80
DEFAULT_SCANRANGE = 20
DEFAULT_HEATSINKS = 10
DEFAULT_COMPUTER = 2
DEFAULT_RADIO = 3
DEFAULT_PART_LEVEL = 3
DEFAULT_CLCOMPUTER = 5
DEFAULT_CLRADIO = 5
DEFAULT_CLPART_LEVEL = 5

# mech.h:63-73
DEFAULT_FREQS = 5
FREQS = 16
RADIO_RELAY = 1

# mudconf.btech_dynspeed default (btpr/conf.c:41)
BTECH_DYNSPEED = 1

# template.c:52-61 — recognized template-file keywords, in selection order
LOAD_COMMANDS = (
    "Reference", "Type", "Move_Type", "Tons", "Tac_Range",
    "LRS_Range", "Radio_Range", "Scan_Range", "Heat_Sinks",
    "Max_Speed", "Specials", "Armor", "Internals", "Rear",
    "Config", "Computer", "Name", "Jump_Speed", "Radio",
    "SI", "Fuel", "Comment", "RadioType",
    "Mech_BV", "Cargo_Space", "Max_Suits", "InfantrySpecials",
    "Max_Ton", "HSEngOverRide", "Unit_Era", "Unit_TRO",
)

# template.c:63-117 — special-item names, positionally matched to the
# Special sub-indices (entities/crittypes.py)
INTERNALS = (
    "ShoulderOrHip",
    "UpperActuator",
    "LowerActuator",
    "HandOrFootActuator",
    "LifeSupport",
    "Sensors",
    "Cockpit",
    "Engine",
    "Gyro",
    "HeatSink",
    "JumpJet",
    "CASE",
    "FerroFibrous",
    "EndoSteel",
    "TripleStrengthMyomer",
    "TargetingComputer",
    "Masc",
    "C3Master",
    "C3Slave",
    "BeagleProbe",
    "ArtemisIV",
    "Ecm",
    "Axe",
    "Sword",
    "Mace",
    "Claw",
    "DSAeroDoor",
    "DSMechDoor",
    "Fuel_Tank",
    "TAG",
    "DSVehicleDoor",
    "DSCargoDoor",
    "LAM_Equipment",
    "CASE-II",
    "StealthArmor",
    "NullSig_Device",
    "C3i",
    "AngelEcm",
    "HvyFerroFibrous",
    "LtFerroFibrous",
    "BloodhoundProbe",
    "PurifierArmor",
    "KageStealthUnit",
    "AchileusStealthUnit",
    "InfiltratorStealthUnit",
    "InfiltratorIIStealthUnit",
    "SuperCharger",
    "Dual_Saw",
    "Light_BAP",
    "SplitCrit_Left",
    "SplitCrit_Right",
    "Hardpoint",
)

# template.c:120-169 (BT_PART_WEIGHTS) — per-item weights in 1/1024 tons.
# NB the C list is 48 entries against 52 internals: it has no SuperCharger
# row (Dual_Saw's 1024 sits at SuperCharger's index) and stops after
# Light_BAP.  Ported positionally, misalignment and all.
INTERNALS_WEIGHT = (
    102,    # ShoulderOrHip
    102,    # UpperActuator
    102,    # LowerActuator
    102,    # HandOrFootActuator
    204,    # LifeSupport
    102,    # Sensors
    512,    # Cockpit
    1024,   # Engine
    512,    # Gyro
    204,    # HeatSink
    204,    # JumpJet
    51,     # Case
    153,    # FerroFibrous
    153,    # EndoSteel
    51,     # TripleStrengthMyomer
    204,    # TargetingComputer
    51,     # Masc
    512,    # C3Master
    102,    # C3Slave
    102,    # BeagleProbe
    153,    # ArtemisIV
    204,    # Ecm
    51,     # Axe
    25,     # Sword
    102,    # Mace
    75,     # Claw
    1024,   # DSAeroDoor
    1024,   # DSMechDoor
    102,    # Fuel_Tank
    51,     # TAG
    1024,   # DSVehicleDoor
    1024,   # DSCargoDoor
    306,    # LAM_Equipment
    306,    # CaseII
    3,      # StealthArmor
    1024,   # NullSig_Device
    512,    # C3i
    204,    # AngelECM
    7,      # HvyFerroFibrous
    1,      # LtFerroFibrous
    102,    # BloodhoundProbe
    2,      # PurifierArmor
    102,    # KageStealthUnit
    102,    # AchileusStealthUnit
    102,    # InfiltratorStealthUnit
    102,    # InfiltratorIIStealthUnit
    1024,   # Dual_Saw
    512,    # Light_BAP
)

# template.c:172-330 — cargo names; the tuple position IS the cargo
# sub-index (Cargo2I).  "Steel" appears twice in the C; both kept.
CARGO = (
    "Ammo_LBX2",
    "Ammo_LBX5_LBX",
    "Ammo_LBX10_LBX",
    "Ammo_LBX20_LBX",
    "Ammo_LRM",
    "Ammo_SRM",
    "Ammo_SSRM",
    "Ammo_LRM_NARC",
    "Ammo_SRM_NARC",
    "Ammo_SSRM_NARC",
    "Ammo_LRM_Artemis",
    "Ammo_SRM_Artemis",
    "Ammo_SSRM_Artemis",
    "Petroleum",
    "Phosphorus",
    "Hydrogen",
    "Gold",
    "Natural_Extracts",
    "Marijuana",
    "Sulfur",
    "Sodium",
    "Plutonium",
    "Ore",
    "Steel",
    "Plastics",
    "Medical_Supplies",
    "Computers",
    "Explosives",
    "ES_Internal",
    "FF_Armor",
    "XL_Engine",
    "Double_HeatSink",
    "ICE_Engine",
    "Electric",
    "Internal",
    "Armor",
    "Actuator",
    "Aero_Fuel",
    "DS_Fuel",
    "VTOL_Fuel",
    "Ammo_LRM_Swarm",
    "Ammo_LRM_Swarm1",
    "Ammo_SRM_Inferno",
    "XXL_Engine",
    "Compact_Engine",
    "HD_Armor",
    "RE_Internals",
    "CO_Internals",
    "Ammo_MRM",
    "Light_Engine",
    "CASE-II",
    "STH_Armor",
    "NullSigSys",
    "Silicon",
    "HVY_FF_Armor",
    "LT_FF_Armor",
    "Ammo_iNARC_Explosive",
    "Ammo_iNARC_Haywire",
    "Ammo_iNARC_ECM",
    "Ammo_iNARC_Nemesis",
    "Ammo_AC2_Pierce",
    "Ammo_AC5_Pierce",
    "Ammo_AC10_Pierce",
    "Ammo_AC20_Pierce",
    "Ammo_LAC2_Pierce",
    "Ammo_LAC5_Pierce",
    "Ammo_AC2_Flechette",
    "Ammo_AC5_Flechette",
    "Ammo_AC10_Flechette",
    "Ammo_AC20_Flechette",
    "Ammo_LAC2_Flechette",
    "Ammo_LAC5_Flechette",
    "Ammo_AC2_Incendiary",
    "Ammo_AC5_Incendiary",
    "Ammo_AC10_Incendiary",
    "Ammo_AC20_Incendiary",
    "Ammo_LAC2_Incendiary",
    "Ammo_LAC5_Incendiary",
    "Ammo_AC2_Precision",
    "Ammo_AC5_Precision",
    "Ammo_AC10_Precision",
    "Ammo_AC20_Precision",
    "Ammo_LAC2_Precision",
    "Ammo_LAC5_Precision",
    "Ammo_LR_DFM",
    "Ammo_SR_DFM",
    "Ammo_SLRM",
    "Ammo_ELRM",
    "BSuit_Sensor",
    "BSuit_LifeSupport",
    "BSuit_Electronic",
    "Oil",
    "Water",
    "Earth",
    "Oxygen",
    "Nitrogen",
    "Nickel",
    "Steel",
    "Iron",
    "Brass",
    "Platinum",
    "Copper",
    "Aluminum",
    "Consumer_Good",
    "Machinery",
    "Slaves",
    "Timbiqui_Dark",
    "Cocaine",
    "Heroine",
    "Marble",
    "Glass",
    "Diamond",
    "Coal",
    "Food",
    "Zinc",
    "Fabric",
    "Clothing",
    "Wood",
    "Pulp",
    "Lumber",
    "Rubber",
    "Seeds",
    "Fertilizer",
    "Salt",
    "Lithium",
    "Helium",
    "Larium",
    "Uranium",
    "Iridium",
    "Titanium",
    "Concrete",
    "FerroCrete",
    "Building_Supplies",
    "Kevlar",
    "Waste",
    "Livestock",
    "Paper",
    "XL_Gyro",
    "HeavyDuty_Gyro",
    "Compact_Gyro",
    "Compact_HeatSink",
    "Ammo_LRM_Stinger",
    "Ammo_AC2_Caseless",
    "Ammo_AC5_Caseless",
    "Ammo_AC10_Caseless",
    "Ammo_AC20_Caseless",
    "Ammo_LAC2_Caseless",
    "Ammo_LAC5_Caseless",
    "Ammo_LRM_Sguided",
    "Ammo_ATM3_ER",
    "Ammo_ATM3_HE",
    "Ammo_ATM6_ER",
    "Ammo_ATM6_HE",
    "Ammo_ATM9_ER",
    "Ammo_ATM9_HE",
    "Ammo_ATM12_ER",
    "Ammo_ATM12_HE",
    "SearchLight",
)

# template.c:613-771 (BT_PART_WEIGHTS) — cargo weights in 1/1024 tons.
# NB the tail of the C list is misaligned against cargo[]: cargo[] puts
# SearchLight AFTER the eight ATM entries, this table puts 204 (labelled
# SearchLight) BEFORE them, and its last two labels are swapped
# (HE before ER).  Ported positionally, exactly as compiled.
CARGO_WEIGHT = (
    1024,   # Ammo_LBX2
    1024,   # Ammo_LBX5_LBX
    1024,   # Ammo_LBX10_LBX
    1024,   # Ammo_LBX20_LBX
    1024,   # Ammo_LRM
    1024,   # Ammo_SRM
    1024,   # Ammo_SSRM
    1024,   # Ammo_LRM_NARC
    1024,   # Ammo_SRM_NARC
    1024,   # Ammo_SSRM_NARC
    1024,   # Ammo_LRM_Artemis
    1024,   # Ammo_SRM_Artemis
    1024,   # Ammo_SSRM_Artemis
    102,    # Petroleum
    102,    # Phosphorus
    102,    # Hydrogen
    204,    # Gold
    51,     # Natural_Extracts
    10,     # Marijuana
    10,     # Sulfur
    10,     # Sodium
    306,    # Plutonium
    51,     # Ore
    204,    # Steel
    51,     # Plastics
    8,      # Medical_Supplies
    306,    # Computers
    204,    # Explosives
    32,     # ES_Internal
    57,     # FF_Armor
    512,    # XL_Engine
    342,    # Double_Heatsink
    512,    # ICE_Engine
    51,     # Electric
    64,     # Internal
    64,     # Armor
    102,    # Actuator
    10,     # Aero_Fuel
    20,     # DS_Fuel
    2,      # VTOL_Fuel
    1024,   # Ammo_LRM_Swarm
    1024,   # Ammo_LRM_Swarm1
    1024,   # Ammo_SRM_Inferno
    1024,   # XXL_Engine
    2048,   # Compact_Engine
    6,      # HD_Armor
    4,      # RE_Internals
    2,      # CO_Internals
    1024,   # Ammo_MRM
    512,    # Light_Engine
    62,     # CaseII
    3,      # STH_Armor
    1024,   # NullSigSys
    80,     # Silicon
    7,      # HVY_FF_Armor
    1,      # LT_FF_Armor
    1024,   # Ammo_iNARC_Explosive
    1024,   # Ammo_iNARC_Haywire
    1024,   # Ammo_iNARC_ECM
    1024,   # Ammo_iNARC_Nemesis
    1024,   # Ammo_AC2_AP
    1024,   # Ammo_AC5_AP
    1024,   # Ammo_AC10_AP
    1024,   # Ammo_AC20_AP
    1024,   # Ammo_LAC2_AP
    1024,   # Ammo_LAC5_AP
    1024,   # Ammo_AC2_Flechette
    1024,   # Ammo_AC5_Flechette
    1024,   # Ammo_AC10_Flechette
    1024,   # Ammo_AC20_Flechette
    1024,   # Ammo_LAC2_Flechette
    1024,   # Ammo_LAC5_Flechette
    1024,   # Ammo_AC2_Incendiary
    1024,   # Ammo_AC5_Incendiary
    1024,   # Ammo_AC10_Incendiary
    1024,   # Ammo_AC20_Incendiary
    1024,   # Ammo_LAC2_Incendiary
    1024,   # Ammo_LAC5_Incendiary
    1024,   # Ammo_AC2_Precision
    1024,   # Ammo_AC5_Precision
    1024,   # Ammo_AC10_Precision
    1024,   # Ammo_AC20_Precision
    1024,   # Ammo_LAC2_Precision
    1024,   # Ammo_LAC5_Precision
    1024,   # Ammo_LR_DFM
    1024,   # Ammo_SR_DFM
    1024,   # Ammo_SLRM
    1024,   # Ammo_ELRM
    102,    # BSuit_Sensor
    61,     # BSuit_LifeSupport
    10,     # BSuit_Electronic
    306,    # Oil
    102,    # Water
    204,    # Earth
    21,     # Oxygen
    102,    # Nitrogen
    102,    # Nickel
    204,    # Steel
    204,    # Iron
    204,    # Brass
    204,    # Platinum
    204,    # Copper
    204,    # Aluminum
    61,     # Consumer_Good
    312,    # Machinery
    102,    # Slaves
    21,     # Timbiqui_Dark
    10,     # Cocaine
    10,     # Heroine
    424,    # Marble
    408,    # Glass
    204,    # Diamond
    306,    # Coal
    204,    # Food
    102,    # Zinc
    204,    # Fabric
    204,    # Clothing
    408,    # Wood
    204,    # Pulp
    520,    # Lumber
    204,    # Rubber
    102,    # Seeds
    102,    # Fertilizer
    102,    # Salt
    204,    # Lithium
    102,    # Helium
    306,    # Larium
    306,    # Uranium
    306,    # Iridium
    408,    # Titanium
    306,    # Concrete
    204,    # FerroCrete
    204,    # Building_Supplies
    204,    # Kevlar
    204,    # Waste
    308,    # Livestock
    102,    # Paper
    1024,   # XL_Gyro
    2048,   # HeavyDuty_Gyro
    2048,   # Compact_Gyro
    2048,   # Compact_HeatSink
    1024,   # Ammo_LRM_Stinger
    1024,   # Ammo_AC2_Caseless
    1024,   # Ammo_AC5_Caseless
    1024,   # Ammo_AC10_Caseless
    1024,   # Ammo_AC20_Caseless
    1024,   # Ammo_LAC2_Caseless
    1024,   # Ammo_LAC5_Caseless
    1024,   # Ammo_LRM_Sguided
    204,    # SearchLight
    1024,   # ATM3 ER
    1024,   # ATM3 HE
    1024,   # ATM6 ER
    1024,   # ATM6 HE
    1024,   # ATM9 ER
    1024,   # ATM9 HE
    1024,   # ATM12 HE
    1024,   # ATM12 ER
)

# template.c:1433-1434
INTERNAL_COUNT = len(INTERNALS)
CARGO_COUNT = len(CARGO)

# template.c:1070-1085
SECTION_CONFIGS = ("Case", "Destroyed")

MOVE_TYPES = (
    "Biped", "Track", "Wheel", "Hover", "VTOL", "Hull", "Foil", "Fly",
    "Quad", "Sub", "None",
)

MECH_TYPES = (
    "Mech", "Vehicle", "VTOL", "Naval", "Spheroid_DropShip", "AeroFighter",
    "Mechwarrior", "Aerodyne_DropShip", "Battlesuit",
)

# template.c:1087-1135 — positionally matched to FireMode / AmmoMode bits
CRIT_FIRE_MODES = (
    "Destroyed",
    "Disabled",
    "Broken",
    "Damaged",
    "OnTC",
    "RearMount",
    "Hotload",
    "Halfton",
    "OneShot",
    "OneShot_Used",
    "UltraMode",
    "RapidFire",
    "Gattling",
    "Rotary_TwoShot",
    "Rotary_FourShot",
    "Rotary_SixShot",
    "Heat",
    "BackPack",
    "Jettisoned",
    "OmniBase",
)

CRIT_AMMO_MODES = (
    "LBX/Cluster",
    "Artemis/Mine",
    "Narc/Smoke",
    "Cluster",
    "Mine",
    "Smoke",
    "Inferno",
    "Swarm",
    "Swarm1",
    "iNarc_Explosive",
    "iNarc_Haywire",
    "iNarc_ECM",
    "iNarc_Nemesis",
    "AP",
    "Flechette",
    "Incendiary",
    "Precision",
    "Stinger",
    "Caseless",
    "Sguided",
    "ExtendedRange",
    "HighExplosive",
)

# template.c:1138-1179 — positionally matched to the Specials bits.
# The C marks this list "*full*": all 31 bits are taken.
SPECIALS_NAMES = (
    "TripleMyomerTech",
    "CL_AMS",
    "IS_AMS",
    "DoubleHS",
    "Masc",
    "Clan",
    "FlipArms",
    "C3MasterTech",
    "C3SlaveTech",
    "ArtemisIV",
    "ECM",
    "BeagleProbe",
    "SalvageTech",
    "CargoTech",
    "SearchLight",
    "LightBAP",
    "AntiAircraft",
    "NoSensors",
    "SS_Ability",
    "FerroFibrous_Tech",
    "EndoSteel_Tech",
    "XLEngine_Tech",
    "ICEEngine_Tech",
    "ForceSingleHS",
    "LightEngine_Tech",
    "XXL_Tech",
    "CompactEngine_Tech",
    "ReinforcedInternal_Tech",
    "CompositeInternal_Tech",
    "HardenedArmor_Tech",
    "CritProof_Tech",
)

SPECIALS_ABBREVS = (
    "TSM", "CLAMS", "ISAMS", "DHS", "MASC", "CLTECH", "FA", "C3M", "C3S",
    "AIV", "ECM", "BAP", "SAL", "CAR", "SL", "LBAP", "AA", "NOSEN", "SS",
    "FF", "ES", "XL", "ICE", "SHS", "LENG", "XXL", "CENG", "RINT", "CINT",
    "HARM", "CP",
)

# template.c:1182-1222 — positionally matched to the specials2 bits
SPECIALS2_NAMES = (
    "StealthArmor_Tech",
    "HvyFerroFibrous_Tech",
    "LaserRefArmor_Tech",
    "ReactiveArmor_Tech",
    "NullSigSys_Tech",
    "C3I_Tech",
    "SuperCharger_Tech",
    "ImprovedJJ_Tech",
    "MechanicalJJ_Tech",
    "CompactHS",
    "LaserHS_Tech",
    "BloodhoundProbe_Tech",
    "AngelECM_Tech",
    "WatchDog_Tech",
    "LtFerroFibrous_Tech",
    "TAG_Tech",
    "OmniMech_Tech",
    "ArtemisV_Tech",
    "Camo_Tech",
    "Carrier_Tech",
    "Waterproof_Tech",
    "XLGyro_Tech",
    "HDGyro_Tech",
    "CompactGyro_Tech",
    "TargComp_Tech",
    "SmallCockpit_Tech",
)

SPECIALS2_ABBREVS = (
    "STHA", "HFF", "LRARM", "REACTARM", "NULL", "C3I", "SCHARGE",
    "IJJ", "MJJ", "CHS", "LHS", "BLP", "AECM", "WDOG", "LFF",
    "TAG", "OMNI", "AV",
    "CAMO",
    "CART",
    "WPRF",
    "XLGYRO", "HDGYRO", "CGYRO",
    "TCOMP", "SMCPIT",
)

# template.c:1224-1250
INFANTRY_SPECIALS_NAMES = (
    "Swarm_Attack_Tech",
    "Mount_Friends_Tech",
    "AntiLeg_Attack_Tech",
    "CS_Purifier_Stealth_Tech",
    "DC_Kage_Stealth_Tech",
    "FWL_Achileus_Stealth_Tech",
    "FC_Infiltrator_Stealth_Tech",
    "FC_InfiltratorII_Stealth_Tech",
    "Must_Jettison_Pack_Tech",
    "Can_Jettison_Pack_Tech",
)

INF_SPECIALS_ABBREVS = (
    "SWARM",
    "MFRIEND",
    "ALEG",
    "PSTEALTH",
    "KSTEALTH",
    "ASTEALTH",
    "ISTEALTH",
    "2STEALTH",
    "MJPACK",
    "CJPACK",
)


def count_special_items() -> int:
    """Number of special-item names. Reference: template.c:1061-1068."""
    return len(INTERNALS)


def parse_attributes(buffer: str, maxargs: int) -> list[str]:
    """mech_parseattributes: only spaces/tabs delimit capped arguments."""
    import re
    return re.findall(r'[^ \t]+', buffer.split('\0',1)[0])[:maxargs]


def name_index(names, command: str) -> int:
    """
    Case-insensitive position of `command` in a name table, -1 if absent
    (or the table itself is empty/None).

    Reference: template.c:1253-1264 (compare_array)
    """
    if not names:
        return -1
    for x, name in enumerate(names):
        if name.lower() == command.lower():
            return x
    return -1


def next_arg(argument: str) -> tuple[str, str]:
    """
    Take one whitespace-delimited word off the front of `argument`.

    Returns (word, rest); rest still starts at the terminating whitespace,
    exactly where the C leaves its pointer.

    Reference: template.c:1266-1275 (one_arg)
    """
    i = 0
    if i < len(argument) and argument[i].isspace():
        i += 1
        while i < len(argument) and argument[i].isspace():
            i += 1
    start = i
    while i < len(argument) and not argument[i].isspace():
        i += 1
    return argument[start:i], argument[i:]


def next_arg_delim(argument: str) -> tuple[str, str]:
    """
    Take one '|'-delimited chunk off the front of `argument` (leading
    whitespace and '|' skipped; internal spaces kept).

    Reference: template.c:1277-1288 (one_arg_delim)
    """
    i = 0
    if i < len(argument) and (argument[i].isspace() or argument[i] == '|'):
        i += 1
        while i < len(argument) and (argument[i].isspace()
                                     or argument[i] == '|'):
            i += 1
    start = i
    while i < len(argument) and argument[i] != '|':
        i += 1
    return argument[start:i], argument[i:]


def bit_names(names, data: int) -> str:
    """
    Space-joined names of the set bits, by table position.

    Reference: template.c:1290-1307 (BuildBitString)
    """
    return " ".join(name for x, name in enumerate(names)
                    if int(data) & (1 << x))


def bit_names2(names, names2, data: int, data2: int) -> str:
    """Two-table variant. Reference: template.c:1309-1340 (BuildBitString2)."""
    parts = [name for x, name in enumerate(names) if int(data) & (1 << x)]
    parts += [name for x, name in enumerate(names2) if int(data2) & (1 << x)]
    return " ".join(parts)


def bit_names_delim2(names, names2, data: int, data2: int) -> str:
    """
    Two-table variant joined with '|'.

    Reference: template.c:1342-1373 (BuildBitStringwdelim2)
    """
    parts = [name for x, name in enumerate(names) if int(data) & (1 << x)]
    parts += [name for x, name in enumerate(names2) if int(data2) & (1 << x)]
    return "|".join(parts)


def bit_names3(names, names2, names3, data: int, data2: int,
               data3: int) -> str:
    """Three-table variant. Reference: template.c:1375-1412 (BuildBitString3)."""
    parts = [name for x, name in enumerate(names) if int(data) & (1 << x)]
    parts += [name for x, name in enumerate(names2) if int(data2) & (1 << x)]
    parts += [name for x, name in enumerate(names3) if int(data3) & (1 << x)]
    return " ".join(parts)


# The crit types a non-mech template never writes out (template.c:1414-1430)
_INVALID_VEHICLE_ITEMS = frozenset(i2special(s) for s in (
    Special.SHOULDER_OR_HIP,
    Special.UPPER_ACTUATOR,
    Special.LOWER_ACTUATOR,
    Special.HAND_OR_FOOT_ACTUATOR,
    Special.ENGINE,
    Special.GYRO,
    Special.JUMP_JET,
))


def invalid_vehicle_item(mech: Mech, x: int, y: int) -> bool:
    """
    Is this crit slot one of the mech-only internals a vehicle dump skips?

    Reference: template.c:1415-1430 (InvalidVehicleItem)
    """
    return mech.sections[x].criticals[y].type in _INVALID_VEHICLE_ITEMS


def short_form(name: str) -> Optional[str]:
    """
    Compressed display form of a part name: names of four characters or
    less with no '/' pass through; otherwise keep digits, uppercase and
    underscores, and pad a single-character result with the name's second
    character.

    Reference: template.c:1479-1497 (my_shortform)
    """
    if name is None:
        return None
    if len(name) <= 4 and '/' not in name:
        return name
    out = "".join(c for c in name
                  if c.isdigit() or c.isupper() or c == '_')
    if len(out) == 1:
        out += name[1:2]
    return out


def generic_computer_multiplier(mech: Mech) -> float:
    """Computer level -> range multiplier. Reference: template.c:1665-1680."""
    return float32({1: 0.8, 2: 1.0, 3: 1.25, 4: 1.5, 5: 1.75}.get(mech.computer, 0.0))


def generic_radio_type(i: int, is_clan: bool) -> int:
    """
    Frequency/flag word for a radio level.

    Reference: template.c:1682-1693 (generic_radio_type)
    """
    f = DEFAULT_FREQS
    if is_clan or i >= 4:
        f += FREQS * RADIO_RELAY
    if i < 3:
        f -= (3 - i) * 2 - 1    # 2 or 4
    else:
        f += (i - 3) * 3        # 5 / 8 / 11
    return f


def generic_radio_multiplier(mech: Mech) -> float:
    """Radio level -> range multiplier. Reference: template.c:1695-1710."""
    return float32({1: 0.8, 2: 1.0, 3: 1.25, 4: 1.5, 5: 1.75}.get(mech.radio, 0.0))


# template.c:1712-1722 (MechComputers*Range macros)
def computers_scan_range(mech: Mech) -> float:
    return float32(generic_computer_multiplier(mech) * DEFAULT_SCANRANGE)


def computers_lrs_range(mech: Mech) -> float:
    return float32(generic_computer_multiplier(mech) * DEFAULT_LRSRANGE)


def computers_tac_range(mech: Mech) -> float:
    return float32(generic_computer_multiplier(mech) * DEFAULT_TACRANGE)


def computers_radio_range(mech: Mech) -> float:
    return float32(DEFAULT_RADIORANGE * generic_radio_multiplier(mech))


def computer_conversion(mech: Mech) -> None:
    """
    Back-fill a computer level from a legacy scan range, then recompute
    every range from it.

    Reference: template.c:1724-1746 (computer_conversion)
    """
    level = {20: 2, 25: 3, 30: 4}.get(mech.scan_range, 0)
    if level:
        mech.computer = level
        mech.scan_range = int(computers_scan_range(mech))
        mech.tac_range = int(computers_tac_range(mech))
        mech.lrs_range = int(computers_lrs_range(mech))
        mech.radio_range = int(computers_radio_range(mech))


def default_fuel_by_type(mech: Mech) -> int:
    """Default fuel load by unit class. Reference: template.c:1756-1770."""
    mod = 2
    if mech.unit_type == UnitType.VTOL:
        return 2000 * mod
    if mech.unit_type == UnitType.AERO:
        return 1200 * mod
    if mech.unit_type in (UnitType.DS, UnitType.SPHEROID_DS):
        return 3600 * mod
    return 0


def _consume_stream_whitespace(fp) -> None:
    """The fscanf(fp, "\\n") calls: eat whitespace up to the next token."""
    while True:
        pos = fp.tell()
        ch = fp.read(1)
        if not ch:
            return
        if not ch.isspace():
            fp.seek(pos)
            return


def read_brace_block(fp, data: str) -> str:
    """
    Read a { ... } value: `data` is the rest of the current line, `fp` the
    open template file positioned after it.  Same-line values lose their
    final character (the C's single isspace check on '}' always backs up
    exactly one, template.c:1886-1890 — normally the space before '}');
    multi-line values join their lines with CRLF, each continuation line
    losing its last character.

    Reference: template.c:1874-1917 (read_desc)
    """
    brace = data.find('{')
    if brace < 0:
        return ""
    _consume_stream_whitespace(fp)
    j = brace + 1
    while j < len(data) and data[j].isspace():
        j += 1
    close = data.find('}', j)
    if close >= 0:
        if close - 1 >= j:
            return data[j:close - 1]
        # value began at the '}' itself: the chopped char sits before the
        # value, so everything from '}' on comes back (template.c:1888-1891)
        return data[j:]
    keep = data[j:] + "\r\n"
    while True:
        line = fp.readline(511)        # fgets(data, 512, fp)
        if not line:
            break
        _consume_stream_whitespace(fp)
        close = line.find('}')
        if close >= 0:
            keep += line[:close]
            break
        keep += line[:-1] + "\r\n"
    return keep


def parse_bit_vector(names, line: str) -> int:
    """
    Space-separated names -> bit vector by table position; "-" is 0 and
    any unknown word (including a trailing-space empty) is -1.

    Reference: template.c:1934-1950 (BuildBitVector)
    """
    if line == "-":
        return 0
    bv = 0
    while line:
        arg, line = next_arg(line)
        idx = name_index(names, arg)
        if idx == -1:
            return -1
        bv |= 1 << idx
    return bv


def parse_bit_vector_delim(names, line: str) -> int:
    """'|'-separated variant. Reference: template.c:1952-1971."""
    if line == "-":
        return 0
    bv = 0
    while line:
        arg, line = next_arg_delim(line)
        idx = name_index(names, arg)
        if idx == -1:
            return -1
        bv |= 1 << idx
    return bv


def parse_bit_vector_lenient(names, line: str) -> int:
    """
    Space-separated variant that silently drops unknown names.

    Reference: template.c:1973-1990 (BuildBitVectorNoErr)
    """
    if line == "-":
        return 0
    bv = 0
    while line:
        arg, line = next_arg(line)
        idx = name_index(names, arg)
        if idx != -1:
            bv |= 1 << idx
    return bv


def check_specials_list(specials_names, specials2_names, line: str) -> int:
    """
    1 if every word in `line` appears in at least one of the tables
    (either may be None), 0 otherwise; "-" is 0.

    Reference: template.c:1992-2014 (CheckSpecialsList)
    """
    w1 = -1
    w2 = -1
    if line == "-":
        return 0
    while line:
        arg, line = next_arg(line)
        if specials_names:
            w1 = name_index(specials_names, arg)
        if specials2_names:
            w2 = name_index(specials2_names, arg)
        if w1 == -1 and w2 == -1:
            return 0
    return 1


def weapon_crit_type_from_name(data: str) -> int:
    """
    Weapon name -> crit type (catalog index + 1, i.e. i2weapon), -1 if
    unknown.

    Reference: template.c:2016-2026 (WeaponIFromString)
    """
    for x, weapon in enumerate(WEAPON_INDEX):
        if weapon.name.lower() == data.lower():
            return x + 1        # weapons start at 1 not 0
    return -1


def ammo_crit_type_from_name(data: str) -> int:
    """
    "Ammo_<weapon>" name -> catalog index + 101, -1 if unknown.  The +101
    is the C's literal legacy ammo base (template.c:2039), NOT today's
    AMMO_BASE_INDEX (193) — ported as written.

    Reference: template.c:2028-2043 (AmmoIFromString)
    """
    rest = data.partition('_')[2]
    for x, weapon in enumerate(WEAPON_INDEX):
        if weapon.name.lower() == rest.lower():
            return x + 101
    return -1


def update_oweight(mech: Mech, value: int) -> int:
    """
    Cache the mech's computed weight (1/1024 tons) in mech.rtons, marking
    it valid; without dynspeed, or for the not-destroyed value-1 flag, the
    frame weight stands in.

    Reference: template.c:2311-2320 (update_oweight);
    mudconf.btech_dynspeed default btpr/conf.c:41
    """
    mech.crit_status |= CritStatus.OWEIGHT_OK
    if not getattr(mech,'construction_dynspeed',BTECH_DYNSPEED) or (value == 1
                              and not (mech.status & MechStatus.DESTROYED)):
        value = mech.tonnage * 1024
    mech.rtons = value
    return value


def tech_list(mech: Mech) -> str:
    """
    The unit's tech-abbreviation string: specials/specials2 (and infantry
    specials for battlesuits), a FUS tag when no engine tech names itself,
    physical-weapon and CASE tags from a full crit walk, INFC/VTOL tags,
    and MTOW towability.

    Reference: template.c:2804-2879 (techlist_func)
    """
    from systems.physical import okay_crit_sect

    bufa = bit_names(SPECIALS_ABBREVS, mech.specials)
    bufb = bit_names(SPECIALS2_ABBREVS, mech.specials2)
    if mech.unit_type == UnitType.BSUIT:
        bufc = bit_names(INF_SPECIALS_ABBREVS, mech.infantry_specials)
        buffer = f"{bufa} {bufb} {bufc}"
    else:
        buffer = f"{bufa} {bufb}"

    # NB strstr semantics: "XL" also matches inside XXL and XLGYRO, so an
    # XL-gyro unit never gets tagged FUS — the C does the same.
    if (not ("XL" in buffer or "XXL" in buffer or "LENG" in buffer
             or "ICE" in buffer or "CENG" in buffer)
            and mech.unit_type != UnitType.BSUIT):
        buffer += " FUS "

    axe = claw = mace = saw = sword = hascase = False
    for i in range(NUM_SECTIONS):
        for ii in range(NUM_CRITICALS):
            part = mech.sections[i].criticals[ii].type
            if part == i2special(Special.AXE) and not axe:
                axe = True
                buffer += " AXE"
            if part == i2special(Special.CLAW) and not claw:
                claw = True
                buffer += " CLAW"
            if part == i2special(Special.MACE) and not mace:
                mace = True
                buffer += " MACE"
            if part == i2special(Special.DUAL_SAW) and not saw:
                saw = True
                buffer += " DUAL_SAW"
            if part == i2special(Special.SWORD) and not sword:
                sword = True
                buffer += " SWORD"
            if (mech.sections[i].config & SectionConfig.CASE_TECH) \
                    and not hascase:
                hascase = True
                buffer += " CASE"

    if mech.cargo_space:
        buffer += " INFC"

    if mech.unit_type == UnitType.VTOL:
        buffer += " VTOL"

    if mech.unit_type == UnitType.MECH and mech.move_type != MoveType.QUAD:
        if ((okay_crit_sect(mech, Location.RARM, 3,
                            Special.HAND_OR_FOOT_ACTUATOR)
             and okay_crit_sect(mech, Location.RARM, 0,
                                Special.SHOULDER_OR_HIP))
                or (okay_crit_sect(mech, Location.LARM, 3,
                                   Special.HAND_OR_FOOT_ACTUATOR)
                    and okay_crit_sect(mech, Location.LARM, 0,
                                       Special.SHOULDER_OR_HIP))
                or (mech.specials & Specials.SALVAGE_TECH)):
            buffer += " MTOW"
    else:
        if mech.specials & Specials.SALVAGE_TECH:
            buffer += " MTOW"

    return buffer
