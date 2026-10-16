# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.combat.c
#   btech/mech.contacts.c
#   btech/mech.events.c
#   btech/mech.maps.c
#   btech/mech.notify.c
#   btech/mech.sensor.c
#   btech/mech.spot.c
#   btech/mech.startup.c
#   btech/mech.tag.c
#   btech/mech.utils.c
#   btech/src/btech/btmacros.h
#   btech/src/include/btconfig.h
# Historical Aerospace sources:
#   btech/ds.turret.c
#   src/hcode/btech/btmacros.h
#   src/hcode/btech/mech.spot.c
#   src/hcode/include/btconfig.h

"""
Targeting and locks — port of the BTMux lock layer (mech.combat.c settarget
path, mech.sensor.c sensor command, mech.events.c lock/PLOS events,
btmacros.h lock macros).

Lock timing follows the selected source profile: recovered Aerospace defaults
to an eight-tick settling event, including historical turret commands on other
parent classes. The general standalone default remains instantaneous. Explicit
engine.lock_tick values override either default, and a nonzero arc_override
suppresses the event. Lock lifetime is owned by the sensor layer
(contact loss -> lose_lock, mech.sensor.c:387-392).

Failure style: command-shaped entry points return (ok, message) tuples and
never raise, matching fire_weapon.  mech_notify texts the C sends
mid-function that are not the command's return value go through the
module NOTIFY_HOOK (_notify).
"""
from core.randomness import roll as source_roll

import math

from core.events import EventType
from entities.mech import (
    AeroLocation, Location, MechStatus, MoveType, NUM_SECTIONS, Specials,
    UnitType, VehicleLocation,
)
from physics.hexmath import SCALEMAP, ZSCALE, find_bearing
from systems.los import (
    MECHLOSFLAG_SEEN, MECHLOSFLAG_SEESP, MECHLOSFLAG_SEESS,
    in_line_of_sight, in_line_of_sight_nb, mech_to_mech_los_flag,
)

# --- Timing constants (btconfig.h) ---
INITIAL_PLOS_TICK = 1   # secs after startup before first PLOS (btconfig.h:145)
PLOS_TICK = 1           # seconds between PLOS checks (btconfig.h:148)
SCHANGE_TICK = 10       # sensor change delay (btconfig.h:149)
# LOCK_TICK (btconfig.h:210, value 8) documents the C checkout; the RUNTIME
# settling window uses the selected profile unless engine.lock_tick overrides it.

NOTIFY_HOOK = None


def _notify(mech, message: str) -> None:
    from systems.movement_commands import notify
    notify(mech, message)
    if NOTIFY_HOOK is not None:
        NOTIFY_HOOK(mech, message)


# =============================================================================
# Range macros
# =============================================================================

def fa_mech_range(mech, target) -> float:
    """
    3D float range between two units, in hexes.  Port of FaMechRange
    (btmacros.h:733-735) -> FindRange (mech.utils.c:749-758).
    """
    return find_range(mech.fx, mech.fy, mech.fz, target.fx, target.fy, target.fz)


def fl_mech_range(gamemap, mech, target) -> float:
    """
    FlMechRange (btmacros.h:655-656): "ancient remnant of pre-06061998
    rangecache-code" — just FaMechRange, the map argument is ignored.
    """
    return fa_mech_range(mech, target)


def find_range(x0: float, y0: float, z0: float,
               x1: float, y1: float, z1: float) -> float:
    """
    3D range between two cartesian float points, in hexes.  Port of
    FindRange (mech.utils.c:749-758), the primitive under FaMechRange —
    the hex-fire and spotter paths call it on mixed mech/hex-center
    coordinates (mech.combat.c:599-601, mech.spot.c:276-283).
    """
    from physics.hexmath import find_range3d
    return find_range3d(x0, y0, z0, x1, y1, z1)


def find_mech_in_hex(mech, gamemap, x: int, y: int, needlos: int):
    """
    First unit found in hex (x, y), scanning the map roster in order.
    Port of find_mech_in_hex (mech.utils.c:2537-2567).

    C shape kept 1:1: no random pick among multiple occupants, no
    elevation check, and with needlos == 0 no team filter — friendlies are
    found too.  Self is always skipped (mech.utils.c:2543).

    needlos bits:
      1 — the looker must have the unit in LOS (mech.utils.c:2551-2554)
      2 — position filter dropped; unit must be a TEAMMATE that sees the
          hex, and not the looker itself (mech.utils.c:2548, 2555-2562;
          MechSeesHex is the LOS layer's hex-sight predicate —
          in_line_of_sight with target None resolves hex visibility).

    Returns the first matching Mech, or None.
    """
    from physics.hexmath import hex_to_float
    for target in gamemap.mechs_on_map:
        if target is None or target is mech:                      # mechsOnMap[loop] != mynum
            continue
        if not (target.x == x and target.y == y) and not (needlos & 2):
            continue
        if needlos:
            if needlos & 1:
                if not in_line_of_sight(mech, target, x, y,
                                        fl_mech_range(gamemap, mech, target)):
                    continue
            if needlos & 2:
                if mech.team != target.team:
                    continue
                # MechSeesHex(target, mech_map, x, y) (mech.utils.c:2558)
                hx, hy = hex_to_float(x, y)
                if not in_line_of_sight(target, None, x, y,
                                        find_range(target.fx, target.fy,
                                                   target.fz, hx, hy, ZSCALE * gamemap.base_elevation(x, y))):
                    continue
                if mech is target:
                    continue
        return target
    return None


# =============================================================================
# Lock macros (btmacros.h)
# =============================================================================

def stop_lock(mech, engine=None) -> None:
    """
    Port of StopLock (btmacros.h:493-494): remove any pending EVENT_LOCK,
    clear LOCK_MODES, reset aim.

    engine is optional so pure state paths still work; without it the
    EVENT_LOCK removal is skipped (harmless when engine.lock_tick == 0:
    no lock event ever exists).
    """
    if engine is not None:
        engine.cancel_events_of_type(EventType.LOCK, mech)
    mech.clear_status(MechStatus.LOCK_MODES)
    # MechAim(a) = NUM_SECTIONS (btmacros.h:494)
    mech.aim = NUM_SECTIONS


def locking(engine, mech) -> bool:
    """
    Is a lock still settling?  Port of Locking() (btmacros.h:403):
    muxevent_count_type_data(EVENT_LOCK, mech).  Always False in the
    default instant-lock configuration (engine.lock_tick == 0 — no
    EVENT_LOCK is ever scheduled).
    """
    return engine.has_event(EventType.LOCK, mech)


def lose_lock(mech, engine=None) -> None:
    """
    Drop the mech's weapon lock.  Port of the LoseLock macro
    (btmacros.h:500): StopLock + MechTarget/-X/-Y = -1 + aim reset.
    """
    # C quirk preserved: LoseLock's "Location-specific targeting powers
    # down." notify (btmacros.h:500) is dead code — StopLock has already
    # reset MechAim to NUM_SECTIONS (btmacros.h:493-494), so its aim guard
    # never passes and the message never fires.
    stop_lock(mech, engine)                 # resets aim (btmacros.h:494)
    mech.aim = NUM_SECTIONS                 # LoseLock's own reset (btmacros.h:500)
    mech.target = -1
    mech.targ_x = -1
    mech.targ_y = -1


# =============================================================================
# Aimed shots — the `target` command (mech.combat.c:96-125)
# =============================================================================

def _aim_section_name(target, index: int) -> str:
    """
    Human name of a section index for the given target class — the data
    core of ArmorStringFromIndex (mech.combat.c:124 call site).
    """
    from systems.damage_commands import section_names
    names=section_names(target)
    return names[index] if 0<=index<len(names) else str(index)


def set_aim(engine, mech, section=None) -> tuple:
    """
    Aim at a body part of the locked target.  Port of mech_target
    (mech.combat.c:96-125).

    Engine-shaped parsing: `section` is a Location / VehicleLocation /
    AeroLocation member or int (the C parses a section string through
    ArmorSectionFromString against the target's type); None is the C's
    '-' disable argument.  `engine` is unused but kept for command-entry
    shape parity.

    C typos kept verbatim (double-t): "Targetting disabled."
    (mech.combat.c:110) and "%s targetted." (mech.combat.c:124).
    """
    if section is None:
        # The '-' branch works without a lock (mech.combat.c:108-112)
        mech.aim = NUM_SECTIONS
        return (True, "Targetting disabled.")

    # DOCHECK(MechTarget < 0 || !getMech, ...) (mech.combat.c:113-116)
    target = None
    if mech.target >= 0 and mech.map is not None:
        target = next((m for m in mech.map.mechs_on_map
                       if m is not None and m._id == mech.target), None)
    if target is None:
        return (False, "Error: You need to be locked onto something to "
                       "target its part!")

    # ArmorSectionFromString (mech.combat.c:117-121): a section index the
    # target does not have is invalid.
    try:
        index = int(section)
    except (TypeError, ValueError):
        return (False, "Invalid location!")
    from systems.damage_commands import section_names
    if not (0 <= index < len(section_names(target) or ())):
        return (False, "Invalid location!")

    mech.aim = index                            # mech.combat.c:122
    mech.aim_type = int(target.unit_type)       # mech.combat.c:123
    return (True, "%s targetted." % _aim_section_name(target, index))


# =============================================================================
# Lock settling event (mech.events.c:188-211)
# =============================================================================

def lock_event(event) -> None:
    """
    EVENT_LOCK callback — "just a 'toy' event" (mech.events.c:187): its
    only C effect is the stable-lock notification; the lock itself was
    already set by mech_settarget.  Port of mech_lock_event
    (mech.events.c:188-211).  Locking() reads this event's presence in
    the queue.
    """
    mech = event.data
    if mech.target >= 0:
        gamemap = mech.map
        target = resolve_object(mech, mech.target)
        if target is None:
            return
        if not in_line_of_sight(mech, target, target.x, target.y,
                                fl_mech_range(gamemap, mech, target)):
            return
        from systems.notifications import identity, mech_printf, MECHALL
        mech_printf(mech, MECHALL, "The sensors acquire a stable lock on %s.",
                    identity(mech, target))
    elif mech.targ_x >= 0 and mech.targ_y >= 0:
        # mech.events.c:205-208
        from systems.notifications import mech_printf, MECHALL
        mech_printf(mech, MECHALL, "The sensors acquire a stable lock on (%d,%d).",
                    mech.targ_x, mech.targ_y)


def _maybe_start_lock_event(engine, mech, *, historical=None) -> None:
    """
    The `#if LOCK_TICK > 0 / if(!arc_override) MECHEVENT(EVENT_LOCK, ...)`
    branch shared by all mech_settarget cases (mech.combat.c:237-240,
    :265-268, :332-335), with explicit engine.lock_tick taking precedence.
    The recovered profile defaults to eight ticks; the general default is zero.
    """
    from systems.movement_commands import historical_aircraft
    historical = historical_aircraft(mech) if historical is None else historical
    lock_tick = getattr(engine, 'lock_tick', 8 if historical else 0)
    if lock_tick > 0 and not getattr(engine,'arc_override',0):
        engine.schedule_event(lock_tick, EventType.LOCK, lock_event,
                              data=mech, data2=engine)


# =============================================================================
# sixth_sense_check (mech.combat.c:165-181)
# =============================================================================

SIXTH_SENSE_MESSAGES=(
    "You feel you'll have your hands full before too long..",
    'You have a bad feeling about this..',
    'You feel a homicidal maniac is about to pounce on you!',
    'You think something is amiss..',
    'You have a slightly bad feeling about this..',
    'You think someone thinks ill of you..',
    'Something makes you somewhat feel uneasy..',
    'Something makes you definitely feel uneasy..',
    'Something makes you feel out of your element..',
)


def sixth_sense_event(event):
    unit=event.data
    pilot=unit.pilot
    if unit.is_unconscious or pilot is None:
        return
    if getattr(pilot,'is_player',True) and not getattr(pilot,'connected',True):
        return
    if getattr(pilot,'_id',-1)<=0 or getattr(pilot,'location',-1)!=unit._id:
        return
    from systems.notifications import mech_notify,MECHPILOT
    mech_notify(unit,MECHPILOT,SIXTH_SENSE_MESSAGES[max(0,min(8,int(event.data2)))])


def sixth_sense_check(mech, target) -> None:
    """Schedule the warning from measured weight, range and source draws."""
    from entities.mech import CritStatus
    from core.randomness import draw
    import random
    if not (target.specials & Specials.SS_ABILITY) or mech.crit_status & CritStatus.OBSERVATORIC:
        return
    if target.has_status(MechStatus.DESTROYED):
        return
    from systems.combat import roll_2d6
    if source_roll('sixth_sense_rolls', roll_2d6) > 8:
        return
    r=fa_mech_range(mech,target)
    delta=int((mech.rtons-target.rtons)/1024)
    severity=3*(0 if r<9 else 1 if r<20 else 2)+(0 if delta<=-20 else 2 if delta>=20 else 1)
    delay=draw('sixth_sense_delay',1,3,lambda:random.randint(1,3))
    engine=target._engine or mech._engine
    if engine is None:
        raise ValueError('Sixth sense requires an owning event engine')
    engine.events.schedule(delay,EventType.SIXTH_SENSE,sixth_sense_event,target,severity)


# =============================================================================
# settarget (mech.combat.c:182-337)
# =============================================================================

def set_target(engine, mech, target, *, historical=None) -> tuple:
    """
    Lock a unit.  Port of the argc==1 mech-lock case of mech_settarget
    (mech.combat.c:194-244, minus the '-' clear branch — see clear_target).

    Gate: the target must be non-None and in (cached) line of sight
    (mech.combat.c:212-221); on failure no state changes.  Note the C
    leaves targ_x/targ_y untouched on a mech lock (only StopLock runs).
    """
    from systems.movement_commands import historical_aircraft
    historical = historical_aircraft(mech) if historical is None else historical
    gamemap = mech.map
    los = 0
    if target is not None:
        # InLineOfSight(mech, target, MechX/Y(target), FlMechRange)
        # (mech.combat.c:215-218) — reads the cached SEES bits.
        los = in_line_of_sight(mech, target, target.x, target.y,
                               fl_mech_range(gamemap, mech, target))
    if target is None or not los:
        return (False, "That is not a valid targetID. Try again.")

    # MechSwarmTarget gate (mech.combat.c:223-229), accepting object or ID.
    from systems.combat_firing import swarm_id
    swarm = swarm_id(mech)
    if swarm > 0 and swarm != target._id:
        from systems.combat_commands import NotifiedError
        word='to' if historical else 'too'
        message=NotifiedError(f"You're a bit {word} busy holding on for dear life to lock a target!")
        _notify(mech,message)
        return False,message

    # mech_printf "Target set to %s." (mech.combat.c:231-232) is the
    # command's result — returned below.  (GetMechToMechID two-letter IDs
    # are not ported; the target's name stands in.)
    from systems.notifications import identity
    message = 'Target set to %s.' % identity(mech,target)
    _notify(mech,message)
    stop_lock(mech, engine)
    mech.target = target._id
    mech.set_status(MechStatus.LOCK_TARGET)
    sixth_sense_check(mech, target)
    _maybe_start_lock_event(engine, mech, historical=historical)  # mech.combat.c:237-240
    return True,message


def set_target_hex(engine, mech, x, y, mode=None, *, caller=None, historical=None) -> tuple:
    """
    Lock a hex.  Port of the argc==2 case of mech_settarget
    (mech.combat.c:245-269, mode None -> LOCK_TARGET fire-at-coordinates)
    and the argc==3 case (:270-336, mode 'B'/'I'/'C'/'H' -> LOCK_BUILDING/
    LOCK_HEX_IGN/LOCK_HEX_CLR/LOCK_HEX).  Fire-at-hex resolution itself is
    a later workstream — only the lock state is set here.
    """
    from systems.movement_commands import historical_aircraft
    historical = historical_aircraft(mech) if historical is None else historical
    # Swarm gate (mech.combat.c:247-252 / :272-277)
    from systems.combat_firing import swarm_id
    if swarm_id(mech) > 0:
        from systems.combat_commands import NotifiedError
        word='to' if historical else 'too'
        message=NotifiedError(f"You're a bit {word} busy holding on for dear life to lock a target!")
        _notify(mech,message)
        return False,message

    if mode is None:
        status_mode = MechStatus.LOCK_TARGET    # mech.combat.c:264
        message = "Target coordinates set at (X,Y) %d, %d" % (x, y)
    else:
        # DOCHECK(strlen(args[2]) > 1, "Invalid lock mode!") (:279)
        if len(str(mode)) > 1:
            return (False, "Invalid lock mode!")
        modes = {                               # mech.combat.c:280-295
            'B': (MechStatus.LOCK_BUILDING,
                  "Target coordinates set to building at (X,Y) %d, %d"),
            'I': (MechStatus.LOCK_HEX_IGN,
                  "Target coordinates set to igniting hex at (X,Y) %d, %d"),
            'C': (MechStatus.LOCK_HEX_CLR,
                  "Target coordinates set to clearing hex at (X,Y) %d, %d"),
            'H': (MechStatus.LOCK_HEX,
                  "Target coordinates set to hex at (X,Y) %d, %d"),
        }
        entry = modes.get(str(mode).upper())
        if entry is None:
            return (False, "Invalid mode selected!")
        status_mode, message = entry[0], entry[1] % (x, y)

    gamemap = mech.map
    # ValidCoord (btmacros.h:649-654)
    if gamemap is None or not gamemap.valid(x, y):
        return (False, "Illegal coordinates!")

    mech.target = -1                            # mech.combat.c:246/300
    mech.targ_x = x
    mech.targ_y = y
    # MechFireAdjustment(mech) = 0 (mech.combat.c:249/303) — artillery
    # spotting not ported; getattr-guarded write.
    if hasattr(mech, 'fire_adjustment'):
        mech.fire_adjustment = 0
    if mech.spotter == mech._id:
        from systems.spot import clear_fire_adjustments
        clear_fire_adjustments(gamemap,mech._id)
    mech.targ_z = gamemap.base_elevation(x, y)
    from core.effects import notify_actor
    notify_actor(mech, mech.pilot if caller is None else caller, message)
    stop_lock(mech, engine)                     # mech.combat.c:263/330
    mech.set_status(status_mode)
    _maybe_start_lock_event(engine, mech, historical=historical)  # mech.combat.c:265-268/332-335
    return (True, message)


def clear_target(mech, engine=None) -> tuple:
    """
    `settarget -`: clear all locks.  Port of the '-' branch of
    mech_settarget (mech.combat.c:196-208).
    """
    mech.target = -1
    mech.targ_x = -1
    mech.targ_y = -1
    _notify(mech,'All locks cleared.')
    stop_lock(mech, engine)                     # StopLock (mech.combat.c:205)
    if mech.spotter == mech._id and mech.map is not None:
        from systems.spot import clear_fire_adjustments
        clear_fire_adjustments(mech.map,mech._id)
    return (True, "All locks cleared.")


def lock_command(engine, mech, text, *, historical=None, **actor):
    from systems.combat_commands import command_guard, parse_attributes
    from systems.tic import _atoi
    from core.effects import notify_actor
    caller = actor.get('caller',mech.pilot)
    from systems.movement_commands import historical_aircraft
    from systems.communications import common_checks, MECH_USUALO
    historical = historical_aircraft(mech) if historical is None else historical
    error = common_checks(mech,caller,MECH_USUALO) if historical else command_guard(mech,pilot_only=False,**actor)
    if error is not None:reply = False,error
    else:
        args = parse_attributes(text,5)
        if len(args) == 1:
            reply = clear_target(mech,engine) if args[0].startswith('-') else set_target(engine,mech,contact_target(mech,args[0][:2]),historical=historical)
        elif len(args) in (2,3):
            reply = set_target_hex(engine,mech,_atoi(args[0]),_atoi(args[1]),args[2] if len(args)==3 else None,caller=caller,historical=historical)
        else:return True,''  # Source switch has no branch and emits nothing.
    if not reply[0] and not getattr(reply[1],'notified',False):notify_actor(mech,caller,reply[1])
    return reply


def aim_command(engine, mech, text, **actor):
    from systems.combat_commands import command_guard
    from systems.damage_commands import armor_section_from_string
    from core.effects import notify_actor
    error = command_guard(mech,**actor)
    args = text.split()
    if error:reply = False,error
    elif len(args) != 1:reply = False,'Invalid number of arguments to function!'
    elif args[0] == '-':reply = set_aim(engine,mech,None)
    else:
        target = resolve_unit(mech,mech.target)
        reply = set_aim(engine,mech,armor_section_from_string(target,args[0]) if target is not None else -1)
    if not getattr(reply[1],'notified',False):notify_actor(mech,actor.get('caller',mech.pilot),reply[1])
    return reply


# =============================================================================
# Sensor command (mech.sensor.c:682-829)
# =============================================================================

def _row_field(row, name, default=None):
    """sensors[] rows may be objects or dicts; read a field either way."""
    if isinstance(row, dict):
        return row.get(name, default)
    return getattr(row, name, default)


def _sensor_letters(mech) -> str:
    """
    Current sensor letters, primary then secondary (the data core of
    show_sensor / sensor_info, mech.sensor.c:640-680).
    """
    from systems.sensors import sensors
    try:
        return (_row_field(sensors[mech.sensor[0]], 'matchletter')[0] +
                _row_field(sensors[mech.sensor[1]], 'matchletter')[0])
    except (IndexError, TypeError):
        return ""


def can_change_to(mech, s) -> tuple:
    """
    May this unit switch to sensor index s?  Port of CanChangeTo
    (mech.sensor.c:698-757).  Returns (ok, C notify text); the text is
    also delivered via _notify as the C's mid-function mech_notify, with
    the light-gate messages suppressed for destroyed/unstarted units
    (mech.sensor.c:729, :736).
    """
    from systems.sensors import sensors
    gamemap = mech.map
    if gamemap is None:
        msg = "Where are you? ;-)"              # mech.sensor.c:703-706
        _notify(mech, msg)
        return (False, msg)
    row = sensors[s]
    name = _row_field(row, 'sensorname', _row_field(row, 'name', '?'))

    # required_special gate (mech.sensor.c:708-726): < 0 means the bit
    # DENIES the sensor, > 0 means the bit is REQUIRED.
    i = _row_field(row, 'required_special', 0)
    if i:
        if _row_field(row, 'specials_set', 1) == 1:
            have = int(mech.specials) & abs(int(i))
        else:
            # MechSpecials2 (mech.sensor.c:719)
            have = int(mech.specials2) & abs(int(i))
        if (i > 0) == (not have):
            msg = "You lack the %s sensors!" % name
            _notify(mech, msg)
            return (False, msg)

    # Light-gate messages only reach live, started units
    # (mech.sensor.c:729, :736).
    can_hear = (not mech.has_status(MechStatus.DESTROYED) and
                mech.has_status(MechStatus.STARTED))

    # light gates (mech.sensor.c:728-742)
    min_light = _row_field(row, 'min_light', -1)
    if min_light is not None and min_light >= 0 and min_light > gamemap.maplight:
        msg = "It's now too dark to use %s!" % name
        if can_hear:
            _notify(mech, msg)
        return (False, msg)
    max_light = _row_field(row, 'max_light', -1)
    if max_light is not None and max_light >= 0 and max_light < gamemap.maplight:
        msg = "The light's kinda too bright now to use %s!" % name
        if can_hear:
            _notify(mech, msg)
        return (False, msg)

    # attributeCheck SENSOR_ATTR_SEISMIC gate (mech.sensor.c:744-755):
    # MW / battlesuit / naval / hover units can't use seismic.
    from systems.sensors import SENSOR_ATTR_SEISMIC
    attr_check = _row_field(row, 'attribute_check',
                            _row_field(row, 'attributeCheck', None))
    if attr_check == SENSOR_ATTR_SEISMIC:
        if mech.unit_type in (UnitType.MW, UnitType.BSUIT,
                              UnitType.VEH_NAVAL) or \
                mech.move_type == MoveType.HOVER:
            msg = "You lack the %s sensors!" % name
            _notify(mech, msg)
            return (False, msg)

    return (True, "")


def sensor_change_event(event) -> None:
    """
    EVENT_SCHANGE callback: apply the delayed sensor change and wipe the
    lock.  Port of mech_sensorchange_event (mech.sensor.c:682-696).

    C oddity kept: only MechTarget is cleared — targ_x/targ_y and the
    LOCK_MODES status bits are left alone (mech.sensor.c:694).
    """
    from systems.sensors import sensors
    mech = event.data
    d = int(event.data2)
    num = len(sensors)                  # NUM_SENSORS
    prim = d // num
    sec = d % num
    if not mech.has_status(MechStatus.STARTED):
        return
    mech.sensor[0] = prim
    mech.sensor[1] = sec
    _notify(mech, "As your sensors change, your lock clears.")
    mech.target = -1                    # mech.sensor.c:694
    from systems.ecm import mark_for_los_update
    mark_for_los_update(mech)           # mech.sensor.c:695


def set_sensors(engine, mech, spec) -> tuple:
    """
    Sensor command.  Port of mech_sensor (mech.sensor.c:801-829) +
    set_sensor (mech.sensor.c:774-798).

    spec: "" / one word -> show only (no change); two letters like "V I"
    -> request a change.  A real change is applied SCHANGE_TICK (10 s)
    later by sensor_change_event; requesting the current pair schedules
    nothing (the only immediate path in the C).  C oddities kept: a
    non-Started mech's request is silently ignored but still "succeeds";
    a CanChangeTo failure surfaces as the generic "Invalid arguments!"
    (the specific reason is a mid-function notify — see can_change_to).
    """
    if mech is None:
        return True, ""
    # DOCHECK(MechType == CLASS_MW, ...) (mech.sensor.c:808-809)
    if mech.unit_type == getattr(UnitType, 'MW', None):
        return (False, "You're using your eyes, and nothing you can do "
                       "changes that!")
    args = (spec or "").split()
    if len(args) > 2:                   # mech.sensor.c:811
        return (False, "Invalid number of arguments!")
    if len(args) < 2:
        # show_sensor path (mech.sensor.c:813-818): data API returns the
        # current letters.
        return (True, _sensor_letters(mech))

    # --- set_sensor(mech, ps, ss) (mech.sensor.c:774-798) ---
    if not mech.has_status(MechStatus.STARTED):     # mech.sensor.c:779-780
        return (True, _sensor_letters(mech))
    from systems.sensors import sensors, sensor_index_from_letter
    prim = sensor_index_from_letter(args[0][0].upper())
    sec = sensor_index_from_letter(args[1][0].upper())
    if prim is None or prim < 0 or sec is None or sec < 0:
        return (False, "Invalid arguments!")        # mech.sensor.c:786-787/820
    if prim != mech.sensor[0] or sec != mech.sensor[1]:
        if not can_change_to(mech, prim)[0]:        # mech.sensor.c:789-790
            return (False, "Invalid arguments!")
        if not can_change_to(mech, sec)[0]:         # mech.sensor.c:791-792
            return (False, "Invalid arguments!")
        # StopSensorChange + MECHEVENT(EVENT_SCHANGE, SCHANGE_TICK,
        # prim * NUM_SENSORS + sec) (mech.sensor.c:793-795)
        engine.cancel_events_of_type(EventType.SCHANGE, mech)
        engine.schedule_event(SCHANGE_TICK, EventType.SCHANGE,
                              sensor_change_event, data=mech,
                              data2=prim * len(sensors) + sec)
    return (True, _sensor_letters(mech))


# =============================================================================
# PLOS — the possible-line-of-sight sweep (mech.events.c:358-391)
# =============================================================================

def start_plos_event(engine, mech) -> None:
    """
    Arm the mech's EVENT_PLOS chain if not already pending.  This is the
    StartSeeing macro (btmacros.h:502-503): MECHEVENT(EVENT_PLOS,
    mech_plos_event, INITIAL_PLOS_TICK, 0), duplicate-guarded like
    start_move_event.
    """
    if engine.has_event(EventType.PLOS, mech):
        return
    engine.schedule_event(INITIAL_PLOS_TICK, EventType.PLOS, plos_event,
                          data=mech, data2=engine)


def plos_event(event) -> None:
    """
    Per-second sweep giving each not-yet-SEEN unit a chance to be noticed.
    Port of mech_plos_event (mech.events.c:358-391).

    C behavior kept 1:1: the event re-arms (at PLOS_TICK) BEFORE the
    pnum_seen early-out, so the chain ticks forever while the mech is
    started and mapped; it dies only on shutdown/map loss.
    """
    mech = event.data
    engine = mech._engine or event.data2
    if not mech.has_status(MechStatus.STARTED):
        return
    gamemap = indexed_map(mech)
    if gamemap is None:
        return
    # Re-arm (mech.events.c:368)
    engine.schedule_event(PLOS_TICK, EventType.PLOS, plos_event,
                          data=mech, data2=engine)
    # Early-out: nothing left to notice, and no AA radar (mech.events.c:369-370)
    if not mech.pnum_seen and not (mech.specials & Specials.AA_TECH):
        return
    mapvis = gamemap.mapvis
    maplight = gamemap.maplight
    mech.pnum_seen = 0
    from systems.sensors import sensor_do_we_see_now
    for target in gamemap.mechs_on_map:
        if target is None or target._id <= 0 or target._id == mech._id:
            continue
        flag = mech_to_mech_los_flag(gamemap, mech, target)
        if flag & MECHLOSFLAG_SEEN:
            continue
        rng = fl_mech_range(gamemap, mech, target)  # mech.events.c:383
        mech.pnum_seen += 1
        new_flag = sensor_do_we_see_now(mech, flag, rng, -1, -1, target,
                                        mapvis, maplight, gamemap.cloudbase,
                                        1, 0)
        # Writeback (the C passes &LOSinfo[...] by pointer,
        # mech.events.c:385-387)
        if gamemap.losinfo is None:
            gamemap.losinfo = {}
        gamemap.losinfo[(mech._id, target._id)] = new_flag


# =============================================================================
# Contacts (mech.contacts.c:255-...)
# =============================================================================

def list_contacts(mech) -> list:
    """
    The target-selection/derivation core of mech_contacts
    (mech.contacts.c:255, selection loop :360-441) as a data API — no
    contact-option filters, no ANSI/text formatting.

    A unit appears iff InLineOfSight() is nonzero for it, i.e. the cached
    flag carries SEESP/SEESS (mech.contacts.c:386-390).  Each dict carries
    the values the C derives per contact.
    """
    gamemap = mech.map
    if gamemap is None:
        return []
    contacts = []
    for temp in gamemap.mechs_on_map:
        if not hasattr(temp,'sections') or temp is mech or not getattr(temp,'valid_object',True):                        # mechsOnMap[loop] != mynum
            continue
        rng = fl_mech_range(gamemap, mech, temp)    # mech.contacts.c:385
        losflag = in_line_of_sight(mech, temp, temp.x, temp.y, rng)
        if not losflag:                         # mech.contacts.c:386-390
            continue
        # InLineOfSight_NB gate: sensor-only contacts show as "something"
        # (mech.contacts.c:392-401)
        identified = bool(in_line_of_sight_nb(mech, temp, temp.x, temp.y, 0.0))
        bearing = find_bearing(mech.fx, mech.fy, temp.fx, temp.fy)  # :402-404
        # InWeaponArc (mech.contacts.c:405-406) — added by a parallel wave;
        # None until physics.hexmath grows in_weapon_arc.
        arc = None
        try:
            from physics.hexmath import in_weapon_arc
            arc = in_weapon_arc(mech, temp.fx, temp.fy)
        except ImportError:
            pass
        destroyed = temp.has_status(MechStatus.DESTROYED)
        contacts.append({
            'mech': temp,
            'id': temp._id,
            'x': temp.x, 'y': temp.y, 'z': temp.z,     # MechX/Y/Z
            'range': rng,
            'bearing': bearing,
            'arc': arc,
            'losflag': losflag,
            'sees_primary': bool(losflag & MECHLOSFLAG_SEESP),
            'sees_secondary': bool(losflag & MECHLOSFLAG_SEESS),
            'identified': identified,
            'locked_by_me': temp._id == mech.target,    # MechTarget compare
            'friend': temp.team == mech.team,   # MechSeemsFriend core
            'speed': temp.speed,                # MechSpeed
            'heading': (temp.facing + temp.lateral) % 360,  # MechVFacing
            'move_type': temp.move_type,        # GetMoveTypeID source
            'destroyed': destroyed,             # getStatusChar 'D'
            'started': temp.has_status(MechStatus.STARTED),
            'fallen': temp.has_status(MechStatus.FALLEN),
            'jumping': temp.has_status(MechStatus.JUMPING),
            # rangelist sort key: destroyed units pushed 10000 hexes out
            # (mech.contacts.c:448-450)
            'sort_range': rng + (10000 if destroyed else 0),
        })
    return contacts


# TAG designation (mech.tag.c). The event encodes stabilization vs cooldown.
def resolve_unit(mech, reference, engine=None):
    engine = engine or getattr(mech, '_engine', None)
    roster = engine.get_entities() if engine else (mech.map.mechs_on_map if mech.map else [])
    from entities.mech import Mech
    return next((u for u in roster if isinstance(u,Mech)
                 and getattr(u, '_id', None) == reference), None)


def resolve_object(unit, reference):
    engine = getattr(unit, '_engine', None)
    if engine is not None:
        obj = next((obj for obj in engine.get_entities() if getattr(obj, '_id', None) == reference), None)
        if obj is not None: return obj
        world = getattr(engine, 'personnel', None)
        return world.objects.get(reference) if world is not None else None
    board = getattr(unit, 'map', None)
    return board if board is not None and board._id == reference else None


def indexed_map(unit):
    from entities.map import GameMap
    if unit.mapindex == -1: return None
    board = resolve_object(unit, unit.mapindex)
    return board if isinstance(board, GameMap) else None


def find_mech_on_map(board, token):
    from systems.parts import source_text, mech_ids
    if board is None: return None
    if not isinstance(token, str):
        return token if any(u is token for u in board.mechs_on_map) else None
    token = source_text(token)[:2].lower()
    return next((u for u in board.mechs_on_map if u is not None and
                 mech_ids(u, True) == token), None)


def contact_target(mech, token):
    if mech.mapindex == -1: return None
    board = indexed_map(mech)
    if board is None:
        from core.effects import send_error
        send_error(mech, f'FTDBREFFMN:invalid map:Mech: {mech._id}  Index: {mech.mapindex}')
        mech.mapindex = -1
        return None
    return find_mech_on_map(board, token)


def map_record(unit, reference):
    if isinstance(reference, dict): return reference
    obj = resolve_object(unit, reference) if isinstance(reference, int) else reference
    if obj is None: return None
    return dict(valid=getattr(obj, 'valid_object', getattr(obj, 'valid', True)),
                xtype=getattr(obj, 'xtype', getattr(obj, 'xcode_type', '')),
                object=obj if getattr(obj, 'allocated', True) else None)


def valid_map(record, actor=None):
    """Validate local object metadata in ValidMap's source order, then notify."""
    from entities.map import GameMap
    from systems.notifications import personal_notify
    error = ''
    if record is None or not record.get('valid', True):
        error = 'Index out of range!'
    elif not record.get('xtype'):
        error = 'That is not a valid map! (no XTYPE!)'
    elif record['xtype'] != 'MAP':
        error = 'That is not a valid map!'
    elif not isinstance(record.get('object'), GameMap):
        error = 'The map has not been allocated!!'
    if error:
        personal_notify(actor, error)
        return None, error
    return record['object'], ''


def navigate_sketch_mechs(mech, board, x, y, rows):
    """Overlay source navigate markers onto a caller-supplied canvas copy."""
    from physics.hexmath import hex_to_float, ALPHA, HALF_Y, FULL_Y
    from core.randomness import float32
    canvas = [list(row) for row in rows]
    corner_x, corner_y = hex_to_float(x, y)
    corner_x, corner_y = float32(corner_x - 2 * ALPHA), float32(corner_y - HALF_Y)
    def paint(unit, char):
        column = int(float32(unit.fx - corner_x) / (4 * ALPHA / 21.0) + 4)
        row = int(float32(unit.fy - corner_y) / (FULL_Y / 9.0) + 2)
        if not 0 <= column <= 27 or not 0 <= row <= 13:
            return
        if row >= len(canvas) or column >= len(canvas[row]):
            raise ValueError('navigate canvas cannot contain source marker coordinate')
        canvas[row][column] = char
    for other in board.mechs_on_map:
        if other is None or other is mech or getattr(other, '_id', -1) < 0:
            continue
        if (other.x, other.y) != (x, y) or not in_line_of_sight(mech, other, x, y, .5):
            continue
        paint(other, 'x' if mech.team == other.team and in_line_of_sight_nb(mech, other, 0, 0, 0) else 'X')
    paint(mech, '*')
    return [''.join(row) for row in canvas]


def is_tag_destroyed(mech):
    from entities.mech import CritStatus
    return bool((mech.specials2 & 0x8000 and mech.crit_status & CritStatus.TAG_DESTROYED) or
                (mech.specials & Specials.C3_MASTER_TECH and mech.crit_status & CritStatus.C3_DESTROYED))


def tag_recycling(engine, mech):
    return engine.has_event(EventType.TAG_RECYCLE, mech)


def tag_recycle_event(event):
    mech = event.data
    if is_tag_destroyed(mech):
        return
    if not event.data2:
        _notify(mech, '%cgYour TAG system has finished recycling.%cn')
        return
    target = resolve_unit(mech, mech.tag_target)
    if target is not None and target.tagged_by == mech._id:
        _notify(mech, '%cgYour TAG system has achieved a stable lock.%cn')


def stop_tag(mech, engine=None):
    engine = engine or mech._engine
    target = resolve_unit(mech, mech.tag_target, engine)
    if target is not None and target.tagged_by == mech._id:
        target.tagged_by = 0
    if mech.tag_target > 0:
        mech.tag_target = 0
        _notify(mech, 'Your TAG connection has been broken.')
        if engine is not None:
            engine.schedule_event(30, EventType.TAG_RECYCLE, tag_recycle_event, data=mech, data2=0)


def check_tag(mech):
    if mech.tag_target <= 0:
        return
    target = resolve_unit(mech, mech.tag_target)
    if target is None or target.tagged_by != mech._id or fa_mech_range(mech, target) > 15 or not in_line_of_sight_nb(mech, target, target.x, target.y, fa_mech_range(mech, target)):
        stop_tag(mech)


def tag(engine, mech, argument, caller=None):
    from systems.communications import common_checks, MECH_USUALO
    # The engine owns all delayed state, including calls through the typed API.
    if mech is not None:
        mech._engine = engine
    actor = caller if caller is not None else getattr(mech, 'command_actor', getattr(mech, 'pilot', None))
    error = common_checks(mech, actor, MECH_USUALO)
    if error is not None:
        return False, error
    if not (mech.specials2 & 0x8000 or mech.specials & Specials.C3_MASTER_TECH):
        return False, 'This unit is not equipped with TAG!'
    if is_tag_destroyed(mech):
        return False, 'Your TAG system is destroyed!'
    if tag_recycling(engine, mech):
        return False, 'Your TAG system is recycling!'
    if isinstance(argument, str):
        args = argument.split()
        if len(args) != 1:
            return False, 'Invalid number of arguments to function!'
        argument = args[0]
    if argument == '-':
        if mech.tag_target <= 0:
            return False, 'You are not currently tagging anything!'
        stop_tag(mech, engine)
        return True, 'Your TAG connection has been broken.'
    target = contact_target(mech, argument)
    if target is None or target._id <= 0 or not in_line_of_sight_nb(mech, target, target.x, target.y, fa_mech_range(mech, target)):
        return False, 'That is not a valid TAG targetID. Try again.'
    if mech.team == target.team:
        return False, "You can't TAG friendly units!"
    if mech is target:
        return False, "You can't TAG yourself!"
    if fa_mech_range(mech, target) > 15:
        return False, 'Out of range! TAG ranges are 5/10/15'
    from systems.notifications import identity
    message = f'You light up {identity(mech, target)} with your TAG.'
    _notify(mech, message)
    target.tagged_by = mech._id
    mech.tag_target = target._id
    engine.schedule_event(30, EventType.TAG_RECYCLE, tag_recycle_event, data=mech, data2=1)
    return True, message


def sensor_check(engine, mech):
    """Decode the actual pending SCHANGE event without executing it."""
    from systems.sensors import sensors
    for event in engine.events._events.values():
        if not event.zombie and event.event_type == EventType.SCHANGE and event.data is mech:
            return divmod(int(event.data2),len(sensors))
    return None


def sensor_info(engine, mech):
    alphabet = 'vliesrbVLIESRB'
    indices = list(mech.sensor)
    wanted = sensor_check(engine,mech)
    if wanted:
        indices += [i+9 for i in wanted]
    if any(i < 0 or i >= len(alphabet) for i in indices):
        raise ValueError('Legacy sensor alphabet cannot encode this pending sensor pair.')
    return ''.join(alphabet[i] for i in indices)


def sensor_mode_name(mech, sn, full=False, verbose=False):
    from systems.sensors import sensors, sees360
    if not 0 <= sn < len(sensors):
        return 'None'
    row = sensors[sn]
    text = row.sensorname
    if not row.fullvision:
        text += ' in 360 degree scanning mode' if full or sees360(mech) else ' in 120 degree scanning mode (Forward arc)'
    text += ' '
    if verbose:
        text += f'\n\tRange:      {row.range_desc}\n\tBlocked by: {row.block_desc}'
        if row.special_desc:
            text += '\n\tNotes:      '+row.special_desc
    else:
        text += f'(R:{row.range_desc})'
    return text


def sensor_mode(mech, label, pair, verbose=False):
    p,s = pair
    if p == s:
        return label+': '+sensor_mode_name(mech,p,True,verbose)
    return label+'\n'+'-'*len(label)+'\nPrimary:   '+sensor_mode_name(mech,p,False,verbose)+'\nSecondary: '+sensor_mode_name(mech,s,False,verbose)


def show_sensor(engine, mech, verbose=False):
    text = sensor_mode(mech,'Sensors',mech.sensor,verbose)
    wanted = sensor_check(engine,mech)
    if wanted:
        text += '\n'+sensor_mode(mech,'Wanted',wanted)
    return text


def sensor_light_availability_check(mech):
    from systems.sensors import sensors
    p,s = mech.sensor
    for slot,sn in enumerate((p,s)):
        if slot and p == s:
            break
        row=sensors[sn]
        if (row.min_light >= 0 or row.max_light >= 0) and not can_change_to(mech,sn)[0]:
            mech.sensor[slot]=0
