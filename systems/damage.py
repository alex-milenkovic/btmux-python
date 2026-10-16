# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# Host-derived portions also retain notices/TinyMUX.txt.
# General sources:
#   btech/artillery.c
#   btech/crit.c
#   btech/map.conditions.c
#   btech/mech.combat.misc.c
#   btech/mech.damage.c
#   btech/mech.move.c
#   btech/mech.pickup.c
#   btech/mech.startup.c
#   btech/mech.tech.commands.c
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/btech/mech.ecm.h
#   btech/src/btech/p.mech.utils.h
#   btech/src/include/btconfig.h
#   src/conf.c
# Historical Aerospace sources:
#   btech/aero.bomb.c
#   btech/mech.damage.c
#   src/hcode/btech/btmacros.h
#   src/hcode/btech/mech.ecm.h
#   src/hcode/btech/p.mech.utils.h
#   src/hcode/include/btconfig.h

"""
Section destruction and map condition damage for the BTMux port.

Local section, breach, disable, fall and reactor effects share the owning engine.
IC occupant transport and ejection use local Personnel and template services.

Reference:
- BTMux btech/src/btech/map.conditions.c lines 153-330 - DestroyParts
- BTMux btech/src/btech/mech.damage.c lines 922-1120 - DestroySection
"""
from core.randomness import record_critical_roll, roll as source_roll

from typing import Optional, TYPE_CHECKING

from entities.crittypes import (
    Special,
    crits_in_loc,
    is_ammo,
    is_special,
    special2i,
)
from entities.mech import (
    CritStatus,
    FireMode,
    Location,
    MechStatus,
    MoveType,
    SectionConfig, UnitType, VehicleLocation, AeroLocation, MechStatus2,
)
from physics.movement import MP1

if TYPE_CHECKING:
    from entities.mech import Mech
    from entities.weapon import Weapon


def destroy_parts(
    attacker: Optional['Mech'],
    wounded: 'Mech',
    hitloc: Location,
    engine=None,
    *, breach=False, disable=False,
) -> None:
    """
    Destroy every crit slot in a location and apply the side effects.

    Port of DestroyParts (map.conditions.c:153-330), including non-MECH
    state-only handling, breach/disable and mobility consequences.

    Reference: map.conditions.c lines 153-330
    """
    # Lazy imports: systems.criticals pulls in half of the systems package.
    from systems.criticals import _destroy_part
    from systems.heat import MP_PER_KPH
    engine=engine or getattr(wounded,'_engine',None)

    if wounded.unit_type not in (UnitType.MECH, UnitType.MW, UnitType.BSUIT):
        for crit in wounded.sections[hitloc].criticals[:crits_in_loc(wounded, hitloc)]:
            if crit.type and not crit.firemode & FireMode.DESTROYED_MODE:
                if disable:
                    crit.firemode |= FireMode.DISABLED_MODE
                else:
                    _destroy_part(crit)
        for ws in wounded.weapons:
            if ws.section == hitloc:
                slot=wounded.sections[hitloc].criticals[ws.critical]
                ws.destroyed=bool(slot.firemode & FireMode.DESTROYED_MODE)
                ws.disabled=bool(slot.firemode & FireMode.DISABLED_MODE)
        return

    # tIsLeg - legs, or the "arms" of a quad (map.conditions.c:163-167)
    t_is_leg = (hitloc in (Location.RLEG, Location.LLEG) or
                (hitloc in (Location.RARM, Location.LARM) and
                 wounded.move_type == MoveType.QUAD))

    # oldjs = MechJumpSpeed(wounded) - map.conditions.c:181
    oldjs = wounded.jump_speed

    # nhs - DHS crit-slot counter for this location (map.conditions.c:159)
    nhs = 0

    section = wounded.sections[hitloc]
    for i in range(crits_in_loc(wounded, hitloc)):
        crit = section.criticals[i]

        # if(!PartIsDestroyed(...)) - map.conditions.c:183
        if crit.firemode & FireMode.DESTROYED_MODE:
            continue

        # An already-disabled part is destroyed with *no* further side
        # effects - map.conditions.c:186-188
        if not disable and crit.firemode & FireMode.DISABLED_MODE:
            _destroy_part(crit)
            continue

        if disable:
            crit.firemode |= FireMode.DISABLED_MODE
        else:
            _destroy_part(crit)  # DestroyPart - map.conditions.c:190
        crit_type = crit.type

        # Ammo bins dump their rounds - map.conditions.c:193-195
        if is_ammo(crit_type):
            crit.data = 0

        if is_special(crit_type):
            special = special2i(crit_type)

            if special in (Special.UPPER_ACTUATOR, Special.LOWER_ACTUATOR,
                           Special.HAND_OR_FOOT_ACTUATOR):
                # tNormalizeLocCrits - actuator crit-slot normalization
                # (map.conditions.c:198-202, applied in the common tail).
                pass

            elif special == Special.SHOULDER_OR_HIP:
                # map.conditions.c:203-215
                if t_is_leg:
                    if not wounded.has_crit_status(CritStatus.HIP_DAMAGED):
                        wounded.set_crit_status(CritStatus.HIP_DAMAGED)
                    else:
                        if wounded.move_type != MoveType.QUAD:
                            wounded.set_crit_status(CritStatus.HIP_DESTROYED)
                # Arm shoulders only set an unused local normalization flag.

            elif special == Special.HEAT_SINK:
                # map.conditions.c:216-222.  Doubles occupy 3 slots per
                # sink; every third destroyed slot refunds one before the
                # per-slot decrement — the C's net loss is 2 numsinks per
                # 3-slot double sink.  Ported as written.
                from entities.mech import Specials
                lost_capacity = 1
                if wounded.specials & Specials.DOUBLE_HEAT_TECH:
                    if nhs % 3 == 2:
                        lost_capacity = 0
                    nhs += 1
                wounded.real_num_sinks -= lost_capacity

            elif special == Special.JUMP_JET:
                # map.conditions.c:223-235. The C only tracks jump speed
                # (MechJumpSpeed -= MP1); this port also carries jump_mp, so
                # both are decremented and the "last jet" test reads speed.
                wounded.jump_mp = max(0, wounded.jump_mp - 1)
                wounded.jump_speed -= MP1
                if wounded.jump_speed < 0:
                    wounded.jump_speed = 0
                if (attacker is not None and wounded.jump_speed == 0 and
                        wounded.has_status(MechStatus.JUMPING)):
                    # "Losing your last Jump Jet you fall from the sky!!!!!"
                    # MechFalls(wounded, (int)(oldjs * MP_PER_KPH), 0)
                    from physics.jump import mech_falls
                    from systems.sensors import los_broadcast
                    from physics.collision import domino_space
                    _notify(wounded,'Losing your last Jump Jet you fall from the sky!!!!!')
                    los_broadcast(wounded,'falls from the sky!')
                    mech_falls(wounded, levels=int(oldjs * MP_PER_KPH), notify_fall=False)
                    domino_space(wounded,2)

            elif special == Special.ENGINE:
                # map.conditions.c:236-273.  This section-destruction path
                # differs from the direct crit path (crit.c:1956-1977): only
                # THIS one checks stackpole and the XL torso-kill type.
                from entities.mech import Specials
                from systems.combat import roll_2d6
                wounded.engine_hits = getattr(wounded, 'engine_hits', 0) + 1
                if wounded.engine_heat < 10:
                    wounded.engine_heat += 5
                elif wounded.engine_heat < 15:
                    wounded.engine_heat = 15
                    if attacker is not None:
                        _notify(wounded, "Your engine is destroyed!!")
                        if wounded is not attacker:
                            _notify(attacker, "You destroy the engine!!")

                    # Stackpole (map.conditions.c:250-260): within
                    # MAX_BOOM_TIME of the first CT internal hit, 2d6 >=
                    # BOOM_BTH, and the reactor live.  Starting(a) counts
                    # pending EVENT_STARTUPs; the port's startup event
                    # carries the same type/data pair.
                    starting = False
                    if engine is not None:
                        from core.events import EventType
                        starting = engine.has_event(EventType.STARTUP,
                                                    wounded)
                    tick = engine.muxevent_tick if engine is not None else 0
                    if (getattr(engine, 'stackpole', BTECH_STACKPOLE) and
                            (wounded.boom_start + MAX_BOOM_TIME) >= tick and
                            source_roll('stackpole_rolls', roll_2d6) >= BOOM_BTH and
                            (wounded.has_status(MechStatus.STARTED) or
                             starting)):
                        # HexLOSBroadcast: "The hit destroys the last safety
                        # systems, releasing the fusion reaction!"
                        from systems.notifications import hex_broadcast
                        hex_broadcast(wounded.map,wounded.x,wounded.y,
                                      "%ch%crThe hit destroys the last safety systems, "
                                      "releasing the fusion reaction!%cn")
                        reactor_explosion(wounded, attacker, engine=engine)

                    # XL side-torso engine death carries its own kill type
                    # (map.conditions.c:262-272)
                    if (wounded.unit_type == UnitType.MECH and
                            hitloc in (Location.LTORSO, Location.RTORSO) and
                            (wounded.specials & Specials.XL_TECH)):
                        destroy_mech(
                            wounded, attacker, showboom=True,
                            reason=(KILL_TYPE_SELF_DESTRUCT
                                    if wounded is attacker
                                    else KILL_TYPE_XLENGINE),
                            engine=engine)
                    else:
                        destroy_mech(
                            wounded, attacker, showboom=True,
                            reason=(KILL_TYPE_SELF_DESTRUCT
                                    if wounded is attacker
                                    else KILL_TYPE_NORMAL),
                            engine=engine)

            elif special == Special.ECM:
                # map.conditions.c:275-283
                if not wounded.has_crit_status(CritStatus.ECM_DESTROYED):
                    from entities.mech import MechStatus2
                    from systems.ecm import check_ecm
                    wounded.set_crit_status(CritStatus.ECM_DESTROYED)
                    _notify(wounded, "Your ECM system has been destroyed!")
                    # DisableECM / DisableECCM (mech.ecm.h): drop the
                    # enable bits, then re-run the field pass
                    wounded.status2 &= ~int(
                        MechStatus2.ECM_ENABLED | MechStatus2.ECCM_ENABLED)
                    check_ecm(wounded)

            elif special == Special.TARGETING_COMPUTER:
                # map.conditions.c:284-291
                if not wounded.has_crit_status(CritStatus.TC_DESTROYED):
                    if attacker is not None:
                        _notify(wounded, 'Your Targeting Computer is Destroyed')
                    wounded.set_crit_status(CritStatus.TC_DESTROYED)

    # The C has no weapon list - the crit slots *are* the weapon and every
    # "can this fire" test walks them (PartIsNonfunctional, btmacros.h:324).
    # The port keeps a parallel WeaponState list, so it is kept in step.
    for ws in wounded.weapons:
        if ws.section == hitloc:
            if disable:
                ws.disabled = True
            else:
                ws.destroyed = True

    if wounded.unit_type not in (UnitType.MECH,UnitType.MW): return
    if breach and hitloc == Location.HEAD:
        _notify(wounded,'You are exposed to vacuum!' if wounded.has_status(MechStatus.UNDERVACUUM)
                else 'Water floods into your cockpit!')
        _kill_mech_contents(wounded)
        destroy_mech(wounded, attacker, showboom=False, reason=KILL_TYPE_FLOOD, engine=engine)
        return

    # Fall handling tail for mechs - map.conditions.c:313-330
    # Source biped arms return before the common normalization tail.
    if wounded.move_type != MoveType.QUAD:
        if hitloc in (Location.LARM, Location.RARM):
            return

    t_do_auto_fall = False
    if hitloc in (Location.RLEG, Location.LLEG, Location.LARM, Location.RARM):
        t_do_auto_fall = True

    from systems.criticals import recalculate_mech_stats
    if engine and t_do_auto_fall:
        from core.events import EventType
        engine.cancel_events_of_type(EventType.STAND, wounded)
        wounded._stand_event = None
    recalculate_mech_stats(wounded)

    if (t_is_leg and not wounded.has_status(MechStatus.FALLEN) and
            not wounded.has_status(MechStatus.JUMPING) and
            attacker is not None and not getattr(wounded, "cocoon", 0)):
        # OODing units are excluded by the nonzero cocoon guard above.
        if t_do_auto_fall:
            # "You realize remaining standing is no longer an option and
            # crash to the ground!" - MechFalls(wounded, 1, 0),
            # map.conditions.c:323-329
            from physics.jump import mech_falls
            _notify(wounded, "You realize remaining standing is no longer "
                             "an option and crash to the ground!")
            from systems.sensors import los_broadcast
            los_broadcast(wounded, 'crashes to the ground!')
            mech_falls(wounded, levels=1, notify_fall=False)
        else:
            # Quads keep standing on a made PSR when losing a front leg
            # ("arm") — map.conditions.c:330-335.  Bipeds never reach here:
            # their t_is_leg locations always set t_do_auto_fall.
            from physics.jump import mech_falls
            from systems.piloting import make_piloting_roll
            if not make_piloting_roll(wounded, 0).success:
                _notify(wounded, "You lose your balance and fall down!")
                from systems.sensors import los_broadcast
                los_broadcast(wounded, "loses balance and falls down!")
                mech_falls(wounded, levels=1, notify_fall=False)


def clear_radios(unit):
    unit.freq = [0] * 16
    unit.freqmodes = [0] * 16
    unit.chantitle = [''] * 16


def destroy_section(wounded, attacker, hitloc, engine=None, *, los=1):
    """DestroySection, with the recovered Aerospace control flow."""
    from core.effects import diagnostic
    from core.events import EventType
    from systems.occupants import discard_mw
    from systems.parts import armor_string
    from systems.sensors import los_broadcast
    engine = engine or wounded._engine
    saved_pilot = wounded.pilot
    section = wounded.sections[hitloc]
    aerospace = wounded.unit_type in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS)
    dropship = wounded.unit_type in (UnitType.DS, UnitType.SPHEROID_DS)
    if section_destroyed(wounded, hitloc):
        diagnostic(wounded, f'Double-desting section {int(hitloc)} on mech #{wounded._id}\n')
        if dropship or any(s.internal_orig and s.internal for s in wounded.sections):
            return
        if engine is not None and engine.has_event(EventType.NUKEMECH, wounded):
            diagnostic(wounded, 'And nuke event already existed.\n')
            return
        discard_mw(wounded)
        # The recovered historical body continues after its first discard.
        if not aerospace:
            return

    section.armor = section.internal = section.rear = 0
    from systems.construction_weight import invalidate
    invalidate(wounded)
    if not aerospace:
        section.config |= SectionConfig.SECTION_DESTROYED
    section.specials = 0
    from systems.physical import set_recycle_limb
    set_recycle_limb(wounded, hitloc, 0)
    if not aerospace and hitloc in (Location.LARM, Location.RARM) and wounded.carrying > 0:
        from systems.targeting import resolve_unit
        target = resolve_unit(wounded, wounded.carrying)
        if target is not None:
            _notify(target, 'Your tow lines go suddenly slack!')
            release_tow(wounded)
    if attacker is not None:
        name = armor_string(wounded, hitloc)
        if los >= 0:
            _notify(wounded, f'Your {name} has been destroyed!')
        los_broadcast(wounded, f"'s {name} has been destroyed!")
    destroy_parts(attacker, wounded, hitloc, engine=engine)
    from systems.ecm import check_ecm
    check_ecm(wounded)
    if (wounded.unit_type == UnitType.MECH and wounded.move_type == MoveType.QUAD
            and wounded.lateral and hitloc in (Location.LARM, Location.RARM, Location.LLEG, Location.RLEG)):
        wounded.lateral = 0
    survives = (any(s.internal != 0 for s in wounded.sections) if wounded.unit_type == UnitType.BSUIT
                else any(s.internal_orig and s.internal for s in wounded.sections))
    if not survives:
        if wounded.unit_type == UnitType.BSUIT and not wounded.is_destroyed:
            destroy_mech(wounded, attacker, True, KILL_TYPE_NORMAL, engine)
        if wounded.in_character:
            clear_radios(wounded)
            from core.randomness import draw
            import random
            escaped = (wounded.unit_type == UnitType.BSUIT and
                       draw('suit_ejection', 1, 100, lambda: random.randint(1, 100)) <= 25 and
                       bool(getattr(saved_pilot, '_id', saved_pilot)))
            if escaped:
                from systems.occupants import autoeject
                wounded.last_ejection = autoeject(wounded, saved_pilot, True)
            else:
                _kill_mech_contents(wounded)
            if not dropship:
                discard_mw(wounded)
        return
    if wounded.unit_type == UnitType.MW:
        from systems.piloting import mw_lethal_damage
        mw_lethal_damage(wounded, attacker, 4)
    if wounded.unit_type in (UnitType.MECH, UnitType.MW):
        if hitloc in (Location.LTORSO, Location.RTORSO):
            arm = Location.LARM if hitloc == Location.LTORSO else Location.RARM
            destroy_section(wounded, attacker, arm, engine=engine, los=los)
        elif hitloc in (Location.CTORSO, Location.HEAD):
            if not wounded.is_destroyed:
                reason = (KILL_TYPE_HEAD_TARGET if getattr(attacker, 'aim', -1) == int(Location.HEAD)
                          else KILL_TYPE_BEHEADED) if hitloc == Location.HEAD else KILL_TYPE_NORMAL
                destroy_mech(wounded, attacker, True, reason, engine)
            if hitloc == Location.HEAD or wounded.unit_type == UnitType.MW:
                if wounded.in_character:
                    clear_radios(wounded)
                    _kill_mech_contents(wounded)
            if wounded.unit_type == UnitType.MW:
                discard_mw(wounded)
        return
    if aerospace:
        # Historical COCKPIT is the special index 6, not AERO_COCKPIT (4).
        if wounded.unit_type == UnitType.AERO and hitloc == int(Special.COCKPIT):
            if not wounded.is_destroyed:
                destroy_mech(wounded, attacker, True, KILL_TYPE_NORMAL, engine)
            clear_radios(wounded)
            _kill_mech_contents(wounded)
        return
    if wounded.unit_type == UnitType.BSUIT:
        return
    if wounded.unit_type == UnitType.VEH_GROUND and hitloc == VehicleLocation.TURRET:
        wounded.status2 &= ~MechStatus2.AUTOTURN_TURRET
    elif wounded.unit_type == UnitType.VTOL and hitloc == VehicleLocation.ROTOR:
        from systems.vehicle_combat import start_vtol_crash
        start_vtol_crash(wounded)
    elif not wounded.is_destroyed:
        destroy_mech(wounded, attacker, True, KILL_TYPE_NORMAL, engine)


def _kill_mech_contents(wounded: 'Mech') -> None:
    """KillMechContentsIfIC: transport real IC occupants, with a non-IC no-op."""
    if not wounded.in_character:return
    from systems.occupants import kill_contents
    kill_contents(wounded)


# =============================================================================
# Unit destruction — DestroyMech and the reactor explosion
# =============================================================================

# Message hook, same pattern as systems.missile.NOTIFY_HOOK.
NOTIFY_HOOK = None


def _notify(mech: 'Mech', message: str) -> None:
    from systems.movement_commands import notify
    notify(mech, message)
    if NOTIFY_HOOK is not None:
        NOTIFY_HOOK(mech, message)


# Kill-type reason strings (p.mech.utils.h:18-36) — carried on the kill for
# messaging/audit; DestroyMech also branches on HEAD_TARGET (early return
# when already destroyed).
KILL_TYPE_SELF_DESTRUCT = "SELF-DESTRUCT"
KILL_TYPE_EJECT = "EJECT"
KILL_TYPE_FLOOD = "FLOOD"
KILL_TYPE_ICE = "FLOOD-ICE"
KILL_TYPE_HEAT = "HEAT"
KILL_TYPE_NORMAL = "DESTROYED"
KILL_TYPE_PILOT = "PILOT"
KILL_TYPE_MWDAMAGE = "MWDAMAGE"
KILL_TYPE_BEHEADED = "BEHEADED"
KILL_TYPE_XLENGINE = "XLENGINE"
KILL_TYPE_FUELTANK = "FUELTANK"
KILL_TYPE_COCKPIT = "COCKPIT"
KILL_TYPE_POWERPLANT = "POWERPLANT"
KILL_TYPE_SCHARGE = "SCHARGE"
KILL_TYPE_TRANSPORT = "TRANSPORT"
KILL_TYPE_ENGINE = "ENGINE"
KILL_TYPE_HEAD_TARGET = "HEAD-TARGET"

# mudconf switches (src/conf.c:86,90 — both default 1)
BTECH_STACKPOLE = 1
BTECH_EXPLODE_REACTOR = 1

# Stackpole window: engine death within MAX_BOOM_TIME seconds of the CT
# first taking internal damage, on 2d6 >= BOOM_BTH (btconfig.h:170-172).
MAX_BOOM_TIME = 30
BOOM_BTH = 9


def destroy_mech(
    target: 'Mech',
    attacker: Optional['Mech'],
    showboom: bool = True,
    reason: str = KILL_TYPE_NORMAL,
    engine=None,
) -> None:
    """
    Kill a unit outright, with the full shutdown/cleanup sequence.

    Port of DestroyMech (mech.combat.misc.c:264-350) plus the Destroy /
    DestroyAndDump macros it lands on (btmacros.h:512-565).  The MUX-side
    channel and attribute delivery remain explicit external effects. Local
    carried units, occupant movement, XP loss and delayed disposal use the
    personnel registry when present.

    Args:
        engine: GameEngine when available — used to purge the dead unit's
            pending events (muxevent_remove_data, btmacros.h:546).
    """
    from entities.mech import CritStatus, MechStatus, MechStatus2, UnitType
    engine = engine or target._engine

    # mech.combat.misc.c:273-280 — double-kill guard
    if target.has_status(MechStatus.DESTROYED):
        return

    from systems.occupants import ensure_personnel, kill_contents, tele_contents, discard_mw
    from systems.sensors import los_broadcast
    from systems.notifications import pair_los_broadcast
    from physics.collision import mech_rterrain, mech_upper_elevation, mechs_elevation
    from physics.hexmath import ZSCALE
    historical = target.unit_type in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS)
    world = ensure_personnel(target)
    # General source destroys transported IC units before all parent kill output.
    if not historical and getattr(engine,'transported_unit_death',True) and world is not None:
        from entities.mech import Mech
        from systems.occupants import unit_disembark
        for ident in world.contents(target._id):
            child = world.objects[ident]
            if isinstance(child,Mech) and child.in_character and getattr(child,'hardcode',False):
                _notify(child,"Due to your transport's destruction, your unit has been destroyed!")
                child.last_transport_exit = unit_disembark(child,child)
                destroy_mech(child,attacker,True,KILL_TYPE_TRANSPORT,engine)
    channel_emit_kill(target,attacker,reason)
    if attacker is not None:
        if not historical or showboom:
            if attacker is not target:
                _notify(attacker,'You destroyed the target!')
                pair_los_broadcast(target,attacker,'has been destroyed by %s!')
            else:los_broadcast(target,'has been destroyed!')
        if historical or showboom:
            for line in BOOM_ART:_notify(target,line)
        _notify(target,'You have been killed!' if target.unit_type in (UnitType.MW,UnitType.BSUIT) else 'You have been destroyed!')
        from entities.mech import Specials
        if target.map is not None and getattr(engine,'vtol_ice_causes_fire',True) and target.specials & Specials.ICE_TECH and target.unit_type == UnitType.VTOL:
            from physics.decorations import add_fire
            los_broadcast(target,'explodes in a ball of flames!')
            add_fire(engine,target.map,target.x,target.y)
        if target.carrying > 0:
            from systems.targeting import resolve_unit
            towed = resolve_unit(target,target.carrying)
            if towed is not None:
                _notify(towed,'Your tow lines go suddenly slack!')
                release_tow(target)
    destroy_state(target,engine,historical=historical)
    if attacker is not None:
        target.vertical_speed = 0.0
        terrain = mech_rterrain(target)
        if terrain in ('~','-'):target.z = -target.elev
        elif terrain == '/':
            target.z = mech_upper_elevation(target) if target.z >= mech_upper_elevation(target) else -1
        else:target.z = target.elev
        target.fz = ZSCALE * target.z
    target.kill_reason = reason
    if target.unit_type == UnitType.MW and target.in_character:
        if getattr(engine,'xploss_for_mw',True):kill_contents(target)
        elif world is not None:
            victims = world.contents(target._id)
            tele_contents(engine,target._id,world.afterlife,4)
            for ident in victims:
                obj = world.objects[ident]
                if not getattr(obj,'wizard',False):world.update(obj,alive=False)
        discard_mw(target)


# The showboom ASCII blast (mech.combat.misc.c:238-262), notified line by
# line to the dying unit.
BOOM_ART = [
    "                              ________________",
    "                         ____/ (  (    )   )  \\___",
    "                        /( (  (  )   _    ))  )   )\\",
    "                      ((     (   )(    )  )   (   )  )",
    "                    ((/  ( _(   )   (   _) ) (  () )  )",
    "                   ( (  ( (_)   ((    (   )  .((_ ) .  )_",
    "                  ( (  )    (      (  )    )   ) . ) (   )",
    "                 (  (   (  (   ) (  _  ( _) ).  ) . ) ) ( )",
    "                 ( (  (   ) (  )   (  ))     ) _)(   )  )  )",
    "                ( (  ( \\ ) (    (_  ( ) ( )  )   ) )  )) ( )",
    "                 (  (   (  (   (_ ( ) ( _    )  ) (  )  )   )",
    "                ( (  ( (  (  )     (_  )  ) )  _)   ) _( ( )",
    "                 ((  (   )(    (     _    )   _) _(_ (  (_ )",
    "                  (_((__(_(__(( ( ( |  ) ) ) )_))__))_)___)",
    "                  ((__)        \\\\||lll|l||///          \\_))",
    "                           (   /(/ (  )  ) )\\   )",
    "                         (    ( ( ( | | ) ) )\\   )",
    "                          (   /(| / ( )) ) ) )) )",
    "                        (     ( ((((_(|)_)))))     )",
    "                         (      ||\\(|(|)|/||     )",
    "                       (        |(||(||)||||        )",
    "                         (     //|/l|||)|\\\\ \\     )",
    "                       (/ / //  /|//||||\\\\  \\ \\  \\ _)",
    "----------------------------------------------------------------"
    "------------",
]


def cause_internal_damage(
    wounded: 'Mech',
    attacker: Optional['Mech'],
    hitloc: Location,
    int_damage: int,
    crits_already_rolled: bool = False,
    engine=None,
    *, los=1,
) -> int:
    """
    Apply damage to internal structure at one location: the crit roll, the
    roll-12 limb blow-off, the stackpole-window trigger, and the internal
    reduction / section destruction.

    Port of cause_internaldamage (mech.damage.c:249-331).  Returns
    (leftover internal damage, critical results) — the caller owns the
    transfer hop, as DamageMech does at :735-745 and :758-772.
    """
    from entities.mech import Location as Loc
    from entities.mech import Specials, UnitType
    from systems.combat import check_for_critical, roll_2d6

    crit_results: list = []
    from core.randomness import draw
    roll = source_roll('critical_rolls', roll_2d6)
    record_critical_roll(roll, wounded)

    # Reinforced internals halve, composite internals double
    # (mech.damage.c:262-266)
    if (wounded.specials & Specials.REINFI_TECH) and int_damage > 0:
        int_damage = (int_damage + 1) // 2
    elif wounded.specials & Specials.COMPI_TECH:
        int_damage = int_damage * 2

    # Critical hits? (mech.damage.c:268-313) — skipped when the armor-level
    # (iscritical / AP) roll already ran this DamageMech call (if(!(*crits)))
    if not crits_already_rolled:
        if roll in (8, 9):
            crit_results += check_for_critical(wounded, hitloc, 1,
                                               attacker, engine=engine, los=los)[1]
        elif roll in (10, 11):
            crit_results += check_for_critical(wounded, hitloc, 2,
                                               attacker, engine=engine, los=los)[1]
        elif roll == 12:
            if wounded.unit_type in (UnitType.MECH, UnitType.MW):
                if hitloc in (Loc.RARM, Loc.LARM, Loc.RLEG, Loc.LLEG,
                              Loc.HEAD):
                    # Limb blown off (mech.damage.c:286-303)
                    _notify(wounded, "%ch%cyCRITICAL HIT!!%c")
                    if not wounded.is_destroyed:
                        from systems.parts import armor_string
                        from systems.sensors import los_broadcast
                        los_broadcast(wounded, f"'s {armor_string(wounded, hitloc)} is blown off in a shower of sparks and smoke!")
                    destroy_section(wounded, attacker, hitloc,
                                    engine=engine, los=los)
                    if wounded.unit_type != UnitType.MW:
                        int_damage = 0
                else:
                    crit_results += check_for_critical(wounded, hitloc, 3,
                                                       attacker,
                                                       engine=engine, los=los)[1]
            else:
                crit_results += check_for_critical(wounded, hitloc, 3,
                                                   attacker,
                                                   engine=engine, los=los)[1]

    # Stackpole window opens on the first CT internal hit
    # (mech.damage.c:315-317)
    section = wounded.sections[hitloc]
    if (wounded.unit_type == UnitType.MECH and int_damage and
            hitloc == Loc.CTORSO and
            section.internal == section.internal_orig and engine is not None):
        wounded.boom_start = engine.muxevent_tick

    # Internal reduction / section death (mech.damage.c:319-330)
    if section.internal <= int_damage:
        int_damage -= section.internal
        destroy_section(wounded, attacker, hitloc, engine=engine, los=los)
        section.internal = 0
    else:
        section.internal -= int_damage
        int_damage = 0
    return int_damage, crit_results


def reactor_explosion(wounded: 'Mech', attacker: Optional['Mech'],
                      engine=None) -> None:
    """
    The stackpole: fusion containment lost, engine goes nova.

    Port of reactor_explosion (map.conditions.c:114-151). The absent MUX
    autoeject service is recorded before head destruction on surface maps.
    """
    from systems.piloting import head_hit_mw_damage
    from systems.sensors import scramble_infra_and_liteamp
    from entities.mech import Location as Loc

    engine=engine or wounded._engine
    z = wounded.z
    saved_pilot=wounded.pilot
    game_map = wounded.map

    destroy_section(wounded, attacker, Loc.CTORSO, engine)
    destroy_section(wounded, attacker, Loc.LTORSO, engine)
    destroy_section(wounded, attacker, Loc.RTORSO, engine)
    destroy_section(wounded, attacker, Loc.LLEG, engine)
    destroy_section(wounded, attacker, Loc.RLEG, engine)
    from entities.map import MAPFLAG_UNDERGROUND
    if game_map is not None and not game_map.flags & MAPFLAG_UNDERGROUND:
        from systems.occupants import autoeject
        wounded.last_ejection=autoeject(wounded,saved_pilot,False)
    destroy_section(wounded, attacker, Loc.HEAD, engine)

    wounded.z += 6
    dam = max(wounded.tonnage // 5, wounded.engine_size() // 10)

    scramble_infra_and_liteamp(
        wounded, 4, 0,
        "The searing blast of heat burns out your sensors!",
        "The blinding flash of light overloads your sensors!")

    if game_map is not None:
        blast_hit_hexes_f(
            game_map, dam, 3,
            max(wounded.tonnage // 10, wounded.engine_size() // 25),
            wounded.fx, wounded.fy, wounded.fx, wounded.fy,
            "%ch%crYou bear full brunt of the blast!%cn",
            "is hit badly by the blast!",
            "%ch%cyYou receive some damage from the blast!%cn",
            "is hit by the blast!",
            table=TABLE_PUNCH if getattr(engine,'explode_reactor',BTECH_EXPLODE_REACTOR)>1 else TABLE_GEN,
            safeup=3, safedown=5, isunderwater=True, doneighbors=2,
            engine=engine)
    wounded.z = z
    head_hit_mw_damage(wounded, attacker, 4)


# Blast hit tables (artillery.c:158-160)
TABLE_GEN = 0
TABLE_PUNCH = 1
TABLE_KICK = 2


def _blast_arc(fx: float, fy: float, mech: 'Mech'):
    """
    Facing-relative arc of a blast at (fx, fy) against a unit.

    Port of blast_arcf (artillery.c:127-141): bearing from the unit to the
    blast center, minus facing; >120..<240 = back, >300 or <60 = front,
    >180 = left, else right.
    """
    from physics.hexmath import find_bearing, normalize_heading
    from systems.combat import HitGroup

    bearing = find_bearing(mech.fx, mech.fy, fx, fy)
    direction = normalize_heading(bearing - mech.facing)
    if 120 < direction < 240:
        return HitGroup.BACK
    if direction > 300 or direction < 60:
        return HitGroup.FRONT
    if direction > 180:
        return HitGroup.LEFTSIDE
    return HitGroup.RIGHTSIDE


def blast_hit_hexf(
    game_map, dam: int, singlehitsize: int, heatdam: int,
    fx: float, fy: float, tfx: float, tfy: float,
    tomsg: str, otmsg: str, table: int,
    safeup: int, safedown: int, isunderwater: bool,
    engine=None,
) -> None:
    """
    Area damage against every unit in one hex, in singlehitsize clusters.

    Port of blast_hit_hexf (artillery.c:146-230) — the generic area-damage
    core shared by the reactor explosion, artillery, and bombs.
    """
    from physics.hexmath import float_to_hex
    from systems.combat import (HitGroup, apply_damage_with_transfer,
                                get_hit_location, get_kick_location,
                                get_punch_location)
    from systems.missile import heat_effect
    from entities.mech import UnitType

    if game_map is None:
        return
    tx, ty = float_to_hex(fx, fy)
    if tx < 0 or ty < 0 or tx >= game_map.map_width or ty >= game_map.map_height:
        return
    if tomsg is None or otmsg is None:
        return
    if singlehitsize <= 0:
        raise ValueError('Blast cluster size must be positive')
    if isunderwater:
        ground_zero = game_map.base_elevation(tx, ty)
    else:
        ground_zero = max(0, game_map.base_elevation(tx, ty))

    isrear = iscritical = False
    for temp_mech in list(game_map.mechs_on_map):
        if temp_mech is None or temp_mech.x != tx or temp_mech.y != ty:
            continue
        # Far too high / far too below (underwater, mostly)
        # (artillery.c:181-187)
        if temp_mech.z >= (safeup + ground_zero):
            continue
        if temp_mech.z <= (ground_zero - safedown):
            continue
        from systems.sensors import los_broadcast
        los_broadcast(temp_mech,otmsg)
        _notify(temp_mech, tomsg)
        arc = _blast_arc(tfx, tfy, temp_mech)
        isrear = isrear or arc == HitGroup.BACK

        damleft = dam
        while damleft > 0:
            ndam = singlehitsize if singlehitsize <= damleft else damleft
            damleft -= ndam
            if table == TABLE_PUNCH and temp_mech.unit_type == UnitType.MECH:
                hitloc = get_punch_location(temp_mech, arc)
            elif table == TABLE_KICK and temp_mech.unit_type == UnitType.MECH:
                hitloc = get_kick_location(temp_mech, arc)
            else:
                hitloc, iscritical = get_hit_location(temp_mech, arc, critical=iscritical)
            # DamageMech(tempMech, tempMech, 0, -1, hitloc, isrear,
            #            iscritical, ndam, 0, ...) — artillery.c:222-223
            apply_damage_with_transfer(
                temp_mech, hitloc, ndam, is_rear=isrear,
                attacker=temp_mech, is_critical=iscritical, engine=engine,
                attack_pilot=-1, los=0)
        heat_effect(engine, None, temp_mech, heatdam)


def blast_hit_hexes_f(
    game_map, dam: int, singlehitsize: int, heatdam: int,
    fx: float, fy: float, ftx: float, fty: float,
    tomsg: str, otmsg: str, tomsg1: str, otmsg1: str,
    table: int, safeup: int, safedown: int, isunderwater: bool,
    doneighbors: int = 0, engine=None,
) -> None:
    """
    Area damage over a hex and its neighbors, range-attenuated.

    Port of blast_hit_hexesf (artillery.c:243-301), including forest fire
    independently of the neighbor message gates on unit damage.
    """
    from physics.hexmath import (find_range, float_to_hex, my_hex_dist,
                                 hex_to_float)

    if game_map is None:
        return
    def divide(value, divisor):
        # C integer division truncates toward zero, including diagnostic
        # negative damage/heat; floor division would ignite zero-damage hexes.
        return (1 if value >= 0 else -1) * (abs(value) // divisor)

    t = find_range(fx, fy, ftx, fty)
    dm = max(1, int(t) + 1)
    blast_hit_hexf(game_map, divide(dam, dm), singlehitsize, divide(heatdam, dm),
                   fx, fy, ftx, fty, tomsg, otmsg, table,
                   safeup, safedown, isunderwater, engine=engine)
    if not doneighbors:
        return
    tx, ty = float_to_hex(fx, fy)
    for x1 in range(tx - doneighbors, tx + doneighbors + 1):
        for y1 in range(ty - doneighbors, ty + doneighbors + 1):
            dm = my_hex_dist(tx, ty, x1, y1, 0)
            if dm > doneighbors:
                continue
            if tx == x1 and ty == y1:
                continue
            x2 = max(0, min(x1, game_map.map_width - 1))
            y2 = max(0, min(y1, game_map.map_height - 1))
            if x1 != x2 or y1 != y2:
                continue
            spot = (x1 == tx and y1 == ty)
            hx, hy = hex_to_float(x1, y1)
            dm += 1
            if not (divide(dam, dm)):
                continue
            blast_hit_hexf(game_map, divide(dam, dm), singlehitsize, divide(heatdam, dm),
                           hx, hy, ftx, fty,
                           tomsg if spot else tomsg1,
                           otmsg if spot else otmsg1,
                           table, safeup, safedown, isunderwater,
                           engine=engine)
            from entities.map import LIGHT_FOREST, HEAVY_FOREST
            if (game_map.rterrain(x1, y1) in (LIGHT_FOREST, HEAVY_FOREST)
                    and (x1, y1) not in game_map.decorations):
                from physics.decorations import add_fire
                owner = engine or getattr(game_map, '_engine', None)
                if owner is not None:
                    add_fire(owner, game_map, x1, y1)


def blast_hit_hexes(
    game_map, dam: int, singlehitsize: int, heatdam: int,
    tx: int, ty: int,
    tomsg: str, otmsg: str, tomsg1: str, otmsg1: str,
    table: int, safeup: int, safedown: int, isunderwater: bool,
    doneighbors: int = 0, engine=None,
) -> None:
    """Hex-coordinate wrapper (artillery.c:303-313)."""
    from physics.hexmath import hex_to_float

    fx, fy = hex_to_float(tx, ty)
    blast_hit_hexes_f(game_map, dam, singlehitsize, heatdam, fx, fy, fx, fy,
                      tomsg, otmsg, tomsg1, otmsg1, table,
                      safeup, safedown, isunderwater, doneighbors,
                      engine=engine)


# =============================================================================
# Armor-piercing crit-through-armor (mech.damage.c:167-191)
# =============================================================================

# The C's weapon-size penalty on the AP critical roll (mech.damage.c:
# 176-190), keyed on &MechWeapons[wWeapIndx].name[3] — the "IS."/"CL."
# prefix is skipped, so the same table serves both tech bases.
AP_CRIT_ROLL_PENALTY = {
    "AC/2": -4,          # mech.damage.c:176-177
    "LightAC/2": -4,     # mech.damage.c:178-179
    "AC/5": -3,          # mech.damage.c:180-181
    "LightAC/5": -3,     # mech.damage.c:182-183
    "AC/10": -2,         # mech.damage.c:184-185
    "AC/20": -1,         # mech.damage.c:186-187
}
AP_CRIT_DEFAULT_PENALTY = -10    # mech.damage.c:188-190


def ap_crit_slots(weapon: 'Weapon', roll: Optional[int] = None) -> int:
    """
    Crit-slot count for an armor-piercing crit-through-armor roll.

    Port of the tAPCritical arm of mech.damage.c:171-191: r = Roll() minus
    the weapon-size penalty, then the standard through-armor crit-count
    brackets (the same table roll_critical_hits(through_armor=True) uses:
    <= 7 none, 8-9 one, 10-11 two, 12 three).

    Args:
        roll: optional pre-rolled 2d6 (before the penalty).
    """
    import random
    from core.randomness import draw
    if roll is None:
        roll = source_roll('critical_rolls', lambda: random.randint(1, 6) + random.randint(1, 6))
    roll += AP_CRIT_ROLL_PENALTY.get(weapon.name[3:],
                                     AP_CRIT_DEFAULT_PENALTY)
    if roll <= 7:
        return 0
    if roll <= 9:
        return 1
    if roll <= 11:
        return 2
    return 3


def check_ap_critical(
    target: 'Mech',
    location: Location,
    weapon: 'Weapon',
    ammo_mode: int,
    is_critical: bool,
    internal_damage: int,
    is_rear: bool = False,
    roll: Optional[int] = None,
) -> int:
    """
    Gate + roll for the armor-piercing crit-through-armor.

    Port of mech.damage.c:167-169:
        tAPCritical = !iscritical && (wAmmoMode & AC_AP_MODE) &&
                      (intDamage <= 0) && (wPercentLeft < 50)
    wPercentLeft is the hit side's remaining-armor percentage after the
    damage was applied (rear armor for a rear hit).  Returns the number of
    crit slots to check (0-3), 0 when the gate fails — no dice are
    consumed on a failed gate.
    """
    from entities.mech import AmmoMode

    if is_critical or internal_damage > 0:
        return 0
    if not (ammo_mode & AmmoMode.AC_AP_MODE):
        return 0

    section = target.sections[location]
    if target.unit_type == UnitType.MECH and is_rear and location in (2, 3, 4):
        armor, orig = section.rear, section.rear_orig
    else:
        armor, orig = section.armor, section.armor_orig
    if orig > 0 and int(armor * 100 / orig) >= 50:
        return 0

    if roll is None:
        from core.randomness import draw
        from systems.combat import roll_2d6
        roll = source_roll('critical_rolls', roll_2d6)
    record_critical_roll(roll, target)
    return ap_crit_slots(weapon, roll)


def explode_unit(wounded, attacker=None):
    """Resolve carried suits and occupants before original-live sections."""
    from systems.occupants import ensure_personnel
    world = ensure_personnel(wounded)
    if world is not None:
        from entities.mech import Mech
        from systems.occupants import discard_mw, kill_contents
        for ident in world.contents(wounded._id):
            child = world.objects[ident]
            if isinstance(child, Mech) and getattr(child, 'hardcode', False) and child.unit_type == UnitType.BSUIT:
                kill_contents(child)
                discard_mw(child)
    elif getattr(wounded, 'in_character', False):
        external_effect(wounded, 'Contents / Hardcode / getMech / discard_mw', 'embarked battlesuit destruction')
    _kill_mech_contents(wounded)
    for loc, section in enumerate(wounded.sections):
        if section.internal_orig and not wounded.is_section_destroyed(loc):
            destroy_section(wounded, attacker, loc, engine=wounded._engine,
                            los=0 if wounded is attacker else 1)


def heat_sink_size(unit):
    from entities.mech import Specials
    if unit.unit_type != UnitType.MECH: return 1
    return 2 if unit.specials & Specials.CLAN_TECH else 3 if unit.specials & Specials.DOUBLE_HEAT_TECH else 1


def destroy_heat_sink(unit, location):
    from entities.crittypes import Special, i2special
    from systems.combat import part_is_nonfunctional
    from systems.criticals import destroy_weapon
    from entities.mech import Specials
    kind = i2special(Special.HEAT_SINK)
    if any(c.type == kind and not part_is_nonfunctional(unit, location, i)
           for i, c in enumerate(unit.sections[location].criticals)):
        size = heat_sink_size(unit)
        destroy_weapon(unit, location, kind, 0, 1, size)
        unit.real_num_sinks -= max(size, 2)
        _notify(unit, 'The computer shows a heatsink died due to the impact.')
        return True
    return False


def armor_severity(value, original):
    if not original: return 0
    if not value: return 3
    if value < original // 4: return 2
    if value < original // 2: return 1
    return 0


def armor_warning(unit, location, before, after, original, rear=False, *, penetrated=False):
    severity = 3 if penetrated and before != 0 else armor_severity(after, original)
    if severity and severity != armor_severity(before, original) and getattr(unit, 'armor_warnings', False):
        from systems.damage_commands import short_section
        name = ('none', 'low', 'critical', 'breached')[severity]
        notices = getattr(unit, 'armor_notices', [])
        notices.append(dict(location=int(location), rear=rear, severity=name,
                            color=serious_color(severity), text=serious_message(severity)))
        unit.armor_notices = notices
        _notify(unit, f'{serious_color(severity)}WARNING: {short_section(unit, location)}' +
                (' (Rear)' if rear else '') + f' Armor {serious_message(severity)}')


def record_stat_hit(attacker, target, location, damage, internals, weapon, bth, rear):
    """Configured STATHIT delivery at the armor/internal boundary."""
    recipient = getattr(target._engine, 'statengine_obj', 0)
    if not recipient or recipient < 0 or weapon is None or weapon.index == -1:
        return
    from core.effects import notify_actor
    from systems.parts import armor_string
    pilot_id = lambda unit: getattr(unit.pilot, '_id', -1) if unit.pilot is not None else -1
    label = armor_string(target, location) if location != -1 else 'NONE'
    applied_internal = min(target.sections[location].internal, internals)
    text = (f'STATHIT|#{attacker.mapindex}|#{pilot_id(attacker)}|#{pilot_id(target)}|'
            f'{getattr(attacker, "template_ref", "")}|{getattr(target, "template_ref", "")}|'
            f'#{attacker._id}|#{target._id}|{bth}|{"Rear " if rear else ""}{label}|'
            f'{weapon.name}|{damage-internals}|{applied_internal}')
    request = notify_actor(target, recipient, text)
    request['cause'] = 1  # GOD, as in notify_with_cause.
    target.stat_hit_requests = getattr(target, 'stat_hit_requests', []) + [request]


def section_destroyed(unit, location):
    section = unit.sections[location]
    if unit.unit_type in (UnitType.DS, UnitType.SPHEROID_DS): return False
    return section.armor == 0 and (unit.unit_type == UnitType.AERO or section.internal == 0)


def unit_is_fixable(unit):
    for loc, section in enumerate(unit.sections):
        if not section.internal_orig or not section_destroyed(unit, loc): continue
        if unit.unit_type == UnitType.MECH and loc == 4: return False
        if unit.unit_type == UnitType.VTOL and loc != 5: return False
        if unit.unit_type == UnitType.VEH_GROUND and loc != 4: return False
    return True


def serious_color(index):
    return ('', '%ch%cg', '%ch%cy', '%cr')[index % 4]


def serious_message(index):
    return ('ERROR', 'low', 'critical', 'BREACHED')[index % 4]


def release_tow(unit):
    """The shared GOD dropoff body, preserving lookup and callback order."""
    from core.events import EventType
    from core.effects import send_debug
    from systems.vehicle_combat import correct_speed
    from physics.orbital import fall_event
    from entities.map import ICE
    from systems.notifications import mech_notify, MECHALL, pair_los_broadcast
    from systems.sensors import los_broadcast
    from systems.targeting import resolve_unit, indexed_map
    reference = unit.carrying
    unit.carrying = -1
    unit.towed_unit = None
    unit.clear_crit_status(CritStatus.LOAD_OK)
    target = resolve_unit(unit, reference)
    if target is None:
        return False
    target.clear_status(MechStatus.TOWED)
    mech_notify(unit, MECHALL, 'You drop the mech you were carrying.')
    mech_notify(target, MECHALL, 'You have been released from towing.')
    if target._engine:
        target._engine.cancel_events_of_type(EventType.MOVE, target)
    target.speed = target.desired_speed = 0
    board = indexed_map(target)
    if board is not None:
        pair_los_broadcast(unit, target, 'drops %s!')
        floor = board.base_elevation(target.x, target.y)
        if target.z > floor + 2 and target._engine:
            mech_notify(unit, MECHALL, 'Maybe you should have done this closer to the ground.')
            mech_notify(target, MECHALL, 'You wish he had done that a might bit closer to the ground.')
            los_broadcast(target, 'falls through the sky.')
            target._engine.events.schedule(3, EventType.FALL, fall_event, target, -1)
        else:
            target.z = 0 if board.terrain(unit.x, unit.y) == ICE else board.base_elevation(unit.x, unit.y)
    correct_speed(unit)
    send_debug(unit, f'#{unit._id} has dropped off #{target._id}')
    return True



def possibly_breach(unit, attacker, location):
    from systems.combat import roll_2d6
    from core.randomness import draw
    if not unit.has_status(MechStatus.UNDERSPECIAL): return False
    if source_roll('breach_rolls', roll_2d6) < 10: return False
    return breach_location(unit, attacker, location)


def breach_location(unit, attacker, location):
    if not unit.has_status(MechStatus.UNDERSPECIAL): return False
    if not unit.has_status(MechStatus.UNDERVACUUM): return False
    section = unit.sections[location]
    if section_destroyed(unit, location) or section.config & SectionConfig.SECTION_BREACHED: return False
    from systems.damage_commands import section_names
    _notify(unit, f'Your {section_names(unit)[location]} has been breached!')
    section.config |= SectionConfig.SECTION_BREACHED
    destroy_parts(attacker, unit, location, unit._engine, breach=True, disable=True)
    return True


def channel_emit_kill(unit, attacker=None, reason=None):
    """Local kill credit and profile-specific source channel/hook delivery."""
    from entities.mech import UnitType
    from core.effects import emit_channel, invoke_hook
    attacker = attacker or unit
    aerospace = unit.unit_type in (UnitType.AERO,UnitType.DS,UnitType.SPHEROID_DS)
    if aerospace:
        # aerospace_pre_at2_96f2131 has plain IDs and no reason arguments.
        text = f'#{unit._id} has been killed by #{attacker._id}'
        hook_args = []
        hook_allowed = unit._id > 0 and attacker._id > 0
    else:
        if attacker._id == unit._id and not getattr(unit,'valid_object',True): return
        suffix = f' ({reason})' if reason is not None else ''
        text = (f'#{unit._id} [{getattr(unit,"template_ref",unit.mech_type)}] has been killed by '
                f'#{attacker._id} [{getattr(attacker,"template_ref",attacker.mech_type)}]'+suffix)
        hook_args = [] if reason is None else [reason]
        hook_allowed = getattr(unit,'valid_object',True) and getattr(attacker,'valid_object',True)
    if attacker is not unit: attacker.units_killed += 1
    emit_channel(unit,'MechDebugInfo',text,label='debug')
    if not aerospace:
        emit_channel(unit,'MechDeaths',text,label='death')
    if unit.unit_type in (UnitType.DS,UnitType.SPHEROID_DS):
        emit_channel(unit,'DSInfo',text,label='dropship')
    if hook_allowed:
        request = invoke_hook(unit,'AMECHDEST',attacker,unit,hook_args)
        if not request['applied']:
            external_effect(unit,'MUX attribute execution','AMECHDEST')


def external_effect(unit, service, operation):
    """Expose a missing MUX service without fabricating its outcome."""
    effects = getattr(unit, 'external_effects', [])
    entry = dict(service=service, operation=operation, applied=False)
    if entry not in effects: effects.append(entry)
    unit.external_effects = effects


def destroy_state(target, engine=None, *, historical=False):
    """Destroy macro without DestroyMech notices, transport death or dump effects."""
    # --- Destroy(a), btmacros.h:531-550 ---
    if target.has_status(MechStatus.UNCONSCIOUS):
        target.clear_status(MechStatus.BLINDED)
        target.clear_status(MechStatus.UNCONSCIOUS)
        _notify(target, "The mech was destroyed while pilot was unconscious!")
    if not historical:
        target.clear_status(MechStatus.BLINDED)

    from systems.startup import shutdown_state
    shutdown_state(engine,target,historical=historical)

    # Destroy(a) tail, btmacros.h:531-550
    if not historical:
        from systems.stagger import stop_stagger_check
        from core.events import EventType
        if engine is not None:
            engine.cancel_events_of_type(EventType.INFERNO, target)
        stop_stagger_check(target)
        if target.has_crit_status(CritStatus.JELLIED):
            target.clear_crit_status(CritStatus.JELLIED)
            burn = getattr(target, '_burn_event', None)
            if burn is not None:
                burn.cancel()
                target._burn_event = None
    was_jumping = target.has_status(MechStatus.JUMPING)
    target.set_status(MechStatus.DESTROYED)
    target.clear_crit_status(CritStatus.MECH_STUNNED)
    from systems.swarm import detach_all
    detach_all(target,intentional=True,historical=historical)
    if engine is not None:
        # muxevent_remove_data((void *) a) — btmacros.h:546
        engine.cancel_events_for(target)
    from physics.collision import mech_upper_elevation
    if engine is not None and ((target.unit_type == UnitType.MECH and was_jumping) or
            target.unit_type != UnitType.MECH and target.z > mech_upper_elevation(target)):
        from core.events import EventType
        from physics.orbital import fall_event
        engine.events.schedule(3, EventType.FALL, fall_event, target, -1)
