# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.tech.commands.c
#   btech/mech.utils.c

"""Repairs mutate slots; stat restoration replays an intact template in isolation."""
from entities.mech import UnitType as U, MechStatus as S, SectionConfig as C, FireMode as F, Specials
from entities.crittypes import Special, i2special, is_weapon, is_ammo, is_special, special2i, crits_in_loc
from entities.weapon import get_weapon_by_index
from systems.combat import part_is_nonfunctional
from systems.damage import external_effect
from core.randomness import float32

RECOMPUTE_PARTS = {
    Special.TARGETING_COMPUTER, Special.HEAT_SINK, Special.LIFE_SUPPORT, Special.COCKPIT,
    Special.SENSORS, Special.JUMP_JET, Special.ENGINE, Special.GYRO, Special.SHOULDER_OR_HIP,
    Special.LOWER_ACTUATOR, Special.UPPER_ACTUATOR, Special.HAND_OR_FOOT_ACTUATOR,
    Special.C3_MASTER, Special.C3_SLAVE, Special.C3I, Special.ECM, Special.ANGELECM,
    Special.NULL_SIGNATURE_SYSTEM, Special.BEAGLE_PROBE, Special.LIGHT_BAP,
    Special.ARTEMIS_IV, Special.TAG, Special.BLOODHOUND_PROBE,
}


def repair_part(unit, loc, pos):
    from systems.enhanced_crits import set_part_temp_nuke
    slot = unit.sections[loc].criticals[pos]
    slot.firemode = int(slot.firemode) & ~int(F.DESTROYED_MODE | F.HOTLOAD_MODE | F.DISABLED_MODE | F.BROKEN_MODE | F.DAMAGED_MODE)
    slot.weap_damage_flags = 0
    set_part_temp_nuke(slot, 0)
    if is_weapon(slot.type) or is_ammo(slot.type):
        slot.data = 0
        slot.firemode = int(slot.firemode) & ~int(F.OS_USED | F.IS_JETTISONED_MODE | F.ROCKET_FIRED)
        if is_weapon(slot.type):
            # C readiness reads the first critical; a prior live weapon hit also
            # marked this port's runtime mirror. Repair must restore both.
            for weapon in unit.weapons:
                if (weapon.section,weapon.critical) == (loc,pos):
                    weapon.destroyed = False
    elif is_special(slot.type) and special2i(slot.type) in RECOMPUTE_PARTS and unit.unit_type == U.MECH:
        return magic(unit)
    return True


def fill_part_ammo(unit, loc, pos):
    from entities.crittypes import ammo2weapon_i
    from systems.combat_ammunition import full_ammo
    slot = unit.sections[loc].criticals[pos]
    if not is_ammo(slot.type): return
    weapon = get_weapon_by_index(ammo2weapon_i(slot.type))
    if weapon is None: raise ValueError('Unsupported ammunition catalog index')
    if weapon.ammo_per_ton: slot.data = full_ammo(unit, loc, pos)


def no_locations_destroyed(unit):
    return all(not sec.internal_orig or not unit.is_section_destroyed(loc) for loc, sec in enumerate(unit.sections))


def reattach(unit, loc):
    if not unit.is_section_destroyed(loc): return
    sec = unit.sections[loc]
    sec.config = int(sec.config) & ~int(C.SECTION_DESTROYED | C.SECTION_FLOODED)
    from systems.construction_weight import invalidate
    invalidate(unit)
    sec.internal = 1 if unit.unit_type in (U.AERO, U.DS, U.SPHEROID_DS) else sec.internal_orig
    if unit.unit_type in (U.DS, U.SPHEROID_DS) and no_locations_destroyed(unit): unit.status = int(unit.status) & ~int(S.DESTROYED)


def replace_suit(unit, loc):
    if not unit.is_section_destroyed(loc): return
    sec = unit.sections[loc]
    sec.config = int(sec.config) & ~int(C.SECTION_DESTROYED)
    sec.internal = sec.internal_orig
    from systems.construction_weight import invalidate
    invalidate(unit)


def reseal(unit, loc):
    sec = unit.sections[loc]
    if unit.is_section_destroyed(loc) or not sec.config & C.SECTION_FLOODED: return
    sec.config = int(sec.config) & ~int(C.SECTION_FLOODED)
    from systems.construction_weight import invalidate
    invalidate(unit)
    for pos, slot in enumerate(sec.criticals[:crits_in_loc(unit, loc)]):
        if not slot.firemode & F.DISABLED_MODE: continue
        if slot.firemode & (F.DESTROYED_MODE | F.BROKEN_MODE | F.DAMAGED_MODE): slot.firemode = int(slot.firemode) & ~int(F.DISABLED_MODE)
        else: repair_part(unit, loc, pos)


def detach(unit, loc):
    if not unit.is_section_destroyed(loc):
        from systems.damage import destroy_section
        destroy_section(unit, None, loc, unit._engine)


def fixextra(unit):
    for loc, sec in enumerate(unit.sections):
        sec.config = int(sec.config) & ~int(C.SECTION_FLOODED)
        from systems.construction_weight import invalidate
        invalidate(unit)
        for pos, slot in enumerate(sec.criticals[:crits_in_loc(unit, loc)]):
            if is_ammo(slot.type):
                slot.firemode = int(slot.firemode) & ~int(F.DISABLED_MODE)
                fill_part_ammo(unit, loc, pos)
            else: repair_part(unit, loc, pos)


def sub_magic(unit, loud=False):
    from systems.damage import heat_sink_size
    from core.effects import send_error
    prefix = f'Error in #{unit._id} ({getattr(unit, "template_ref", unit.mech_type)}): '
    size = heat_sink_size(unit)
    efficiency = 2 if unit.specials & (Specials.CLAN_TECH | Specials.DOUBLE_HEAT_TECH) else 1
    from systems.parts import heatsinks_in_engine
    engine_sinks = 0 if unit.specials & Specials.ICE_TECH else heatsinks_in_engine(unit)
    if getattr(unit, 'hs_engine_override', 0): engine_sinks = unit.hs_engine_override
    jets = sinks = destroyed_sinks = 0
    for loc, sec in enumerate(unit.sections):
        for pos, slot in enumerate(sec.criticals[:crits_in_loc(unit, loc)]):
            if slot.type == i2special(Special.JUMP_JET): jets += 1
            if slot.type == i2special(Special.HEAT_SINK):
                sinks += 1
                destroyed_sinks += part_is_nonfunctional(unit, loc, pos)
    actual = int(unit.effective_heat_sinks)
    sinks += min(int(actual * size / efficiency), engine_sinks * size)
    improved = bool(unit.specials2 & 0x80)
    if improved: jets //= 2
    # Authorized catalog C2: correct the source integer (2 / 3) defect.
    maximum = int(float32(unit.max_speed) * (1 / 10.75) * (1 if improved else 2 / 3))
    if jets > maximum:
        if loud: send_error(unit, prefix + f'{jets} JJs, yet {maximum} maximum available (due to walk MPs)?')
        jets = maximum
    unit.jump_speed, unit.jump_mp = 10.75 * jets, jets
    full = int(sinks / size) * efficiency
    remaining = full - int(destroyed_sinks * efficiency / size)
    if remaining != actual and loud:
        remedy = 'add the extra HS critical(s)' if remaining < actual else 'fix the template'
        send_error(unit, prefix + f'Set HS: {actual}. Existing HS: {remaining}. Difference: {actual - remaining}. Please {remedy}.')
    else: unit.real_num_sinks = remaining
    unit.original_sinks = full
    if int(full * size / efficiency) - (0 if unit.specials & Specials.ICE_TECH else 10) * size < 0:
        send_error(unit, prefix + 'HS less then max possible in engine!')


def magic(unit):
    from core.events import EventType
    engine = unit._engine
    if engine is not None: engine.events.cancel_by_type_and_data(EventType.VEHICLE_BURN, unit)
    unit.status = int(unit.status) & ~int(S.PERFORMING_ACTION)
    name = getattr(unit, 'template_ref', unit.name)
    template = getattr(unit, '_catalog_baseline', None)
    if template is None: template = getattr(engine, 'templates', {}).get(name)
    if template is None:
        external_effect(unit, 'intact unit template', f'do_magic: {name}')
        return False
    return replay_template(unit, template)


def replay_template(unit, template):
    from copy import copy, deepcopy
    from core.game_loop import GameEngine
    from entities.crittypes import weapon2i
    from entities.weapon import WeaponFlags as W
    from systems.criticals import apply_critical_to_slot
    from systems.damage import destroy_section
    from systems.parts import update_specials
    # Do not copy engine, map, pilot, towing or target references into replay.
    scratch = copy(template)
    scratch.sections = deepcopy(template.sections)
    scratch.weapons = deepcopy(template.weapons)
    scratch._id, scratch.map, scratch.mapindex, scratch.pilot = -1, None, -1, None
    scratch._engine = GameEngine()
    from core.effects import effect_sink
    scratch._engine.effects = effect_sink(unit)
    scratch.effects = None
    scratch.channel_requests, scratch.hook_requests = [], []
    scratch.status = S.NONE
    scratch.crit_status = 0
    scratch.tank_crit_status = 0
    scratch.external_effects, scratch.movement_messages = [], []
    scratch.boot_messages, scratch.stagger_damage_list = [], []
    scratch.broadcasts, scratch.debug_messages = [], []
    scratch.carrying, scratch.towed_unit = -1, None
    scratch.template_max_speed = template.max_speed
    unit.engine_rating = template.derived_engine_size()
    for loc, section in enumerate(unit.sections):
        for pos, slot in enumerate(section.criticals[:crits_in_loc(unit, loc)]):
            target = scratch.sections[loc].criticals[pos]
            target.type, target.brand = slot.type, slot.brand & 15
            target.data, target.firemode, target.ammomode, target.weap_damage_flags = 0, F.NONE, 0, 0
    if unit.unit_type == U.MECH: sub_magic(scratch)
    unit.original_sinks = getattr(scratch, 'original_sinks', int(scratch.effective_heat_sinks))
    for loc, section in enumerate(unit.sections):
        for pos, slot in enumerate(section.criticals[:crits_in_loc(unit, loc)]):
            target = scratch.sections[loc].criticals[pos]
            if slot.firemode & F.DESTROYED_MODE:
                if not target.firemode & F.DESTROYED_MODE and is_special(slot.type) and unit.unit_type == U.MECH:
                    apply_critical_to_slot(scratch, loc, pos, None, scratch._engine)
            else:
                if is_weapon(slot.type):
                    weapon = get_weapon_by_index(weapon2i(slot.type))
                    if weapon and weapon.special & W.AMS:
                        unit.specials |= Specials.CL_ANTI_MISSILE_TECH if weapon.special & W.CLAT else Specials.IS_ANTI_MISSILE_TECH
                slot.firemode = int(slot.firemode) & ~int(F.OS_USED | F.ROCKET_FIRED | F.IS_JETTISONED_MODE)
        section.config = int(section.config) & ~int(C.STABILIZERS_DESTROYED)
        if unit.is_section_destroyed(loc): destroy_section(scratch, None, loc, scratch._engine)
        if getattr(unit, 'repair_stall', False):
            section.config = int(section.config) & ~int(C.SECTION_BREACHED)
            from systems.construction_weight import invalidate
            invalidate(unit)
    for name in ('jump_speed', 'jump_mp', 'max_speed', 'num_sinks', 'engine_heat', 'pilot_skill_base',
                 'lrs_range', 'tac_range', 'scan_range', 'base_to_hit', 'crit_status'):
        setattr(unit, name, getattr(scratch, name))
    preserved = 0x33 if unit.unit_type != U.MECH else 0
    unit.tank_crit_status = (getattr(unit, 'tank_crit_status', 0) & preserved) | (scratch.tank_crit_status & ~preserved)
    for actual, restored in zip(unit.sections, scratch.sections):
        actual.basetohit, actual.specials = restored.basetohit, restored.specials & ~0x1E
    unit.status = (unit.status | S.DESTROYED) if scratch.is_destroyed else (int(unit.status) & ~int(S.DESTROYED))
    if not unit.is_destroyed and unit.unit_type != U.MECH:
        unit.status = (unit.status | S.FALLEN) if scratch.is_fallen else (int(unit.status) & ~int(S.FALLEN))
    unit.channel_requests = getattr(unit, 'channel_requests', []) + scratch.channel_requests
    update_specials(unit)
    return True
