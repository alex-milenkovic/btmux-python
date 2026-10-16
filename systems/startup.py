# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.combat.misc.c
#   btech/mech.notify.c
#   btech/mech.startup.c
#   btech/mech.update.c
#   btech/src/btech/btmacros.h

"""Ordinary startup/shutdown commands from mech.startup.c and btmacros.h.

Player persistence and autonomous control are explicit service boundaries.
Boot stages use the dispatch queue; completion records the wall clock.
"""
from core.events import EventType as E
from entities.mech import MechStatus as S, MechStatus2 as S2, CritStatus, UnitType as U, MoveType as M, Location as L, Specials
from systems.movement_commands import notify
from systems.damage import external_effect


def starting(engine, unit):
    return engine.has_event(E.STARTUP, unit)


def startup(engine, unit, argument='', *, caller=None, wizard=False):
    from systems.combat_commands import command_guard
    error = command_guard(unit, started=False, pilot_only=False, caller=caller, wizard=wizard, check_blind=False)
    if error:
        return False, error
    actor = unit.pilot if caller is None else caller
    if (actor is None or not getattr(actor, 'valid', True) or not
            (getattr(actor, 'alive', True) or getattr(actor, 'robot', False) or getattr(actor, 'hardcode', False))):
        return False, 'That is not a valid player!'
    if unit.unit_type == U.MW and unit.is_started:
        return False, "You're up and about already!"
    if unit.has_status(S.TOWED):
        return False, "You're being towed! Wait for drop-off before starting again!"
    if unit.is_destroyed:
        return False, "This 'Mech is destroyed!"
    if unit.is_started:
        return False, "This 'Mech is already started!"
    if starting(engine, unit):
        return False, "This 'Mech is already starting!"
    if engine.has_event(E.VEHICLE_EXTINGUISH, unit):
        return False, "You're way too busy putting out fires!"
    from systems.repair_jobs import latest_repair_time
    jobs = getattr(engine, 'repair_jobs', None)
    remaining = jobs.latest(unit) if jobs is not None else latest_repair_time(engine, unit)
    if remaining:
        return False, "This 'Mech is still under repairs (see checkstatus for more info)"
    if unit.heat > 30:
        return False, "This 'Mech is too hot to start back up!"
    if unit.in_character and not (wizard or actor_authority(unit, actor)):
        if pilot_owner_id(unit) != getattr(actor, '_id', actor):
            return False, "This isn't your mech!"
    argument = argument.lstrip(' \t\n\r\v\f')
    override = bool(argument) and 'override'.startswith(argument.lower())
    if override and not (wizard or actor_authority(unit, actor, security=True)):
        return False, 'Insufficient access!'
    unit.pilot = actor
    from systems.piloting import fix_pilotdamage
    fix_pilotdamage(unit, actor)
    notify(unit, 'Startup Cycle commencing...')
    for loc in (L.RLEG, L.LLEG, L.RARM, L.LARM, L.RTORSO, L.LTORSO):
        unit.sections[loc].recycle = 0
    index = 5 if override or unit.unit_type == U.MW else 0
    unit._startup_event = engine.schedule_event(1 if index else stage_interval(unit), E.STARTUP,
                                               startup_event, data=unit, data2=index)
    return True, 'Startup Cycle commencing...'


def stage_interval(unit):
    return 1 if unit.unit_type == U.BSUIT else 5


def boot_table(unit):
    from physics.heights import AERO_TYPES
    if unit.unit_type in AERO_TYPES:
        return AERO_BOOTMSGS
    if unit.unit_type == U.BSUIT:
        return BSUIT_BOOTMSGS
    return {M.HOVER: HOVER_BOOTMSGS, M.TRACK: TRACK_BOOTMSGS, M.WHEEL: WHEEL_BOOTMSGS,
            M.VTOL: VTOL_BOOTMSGS, M.HULL: NAVAL_BOOTMSGS, M.FOIL: NAVAL_BOOTMSGS,
            M.SUB: NAVAL_BOOTMSGS}.get(unit.move_type, BOOTMSGS)


def startup_event(event):
    from physics.collision import mech_rterrain
    from entities.map import WATER, ICE, BRIDGE
    from systems.sensors import los_broadcast
    unit, index = event.data, event.data2
    if not isinstance(index, int) or not 0 <= index < 6:
        raise ValueError('startup boot index must be 0..5')
    unit._startup_event = None
    message = boot_table(unit)[index]
    unit.boot_messages.append(message)
    notify(unit, message)
    index += 1
    floodable = (U.VEH_GROUND, U.VTOL, U.BSUIT, U.AERO, U.DS)
    if (index >= 2 and mech_rterrain(unit) in (WATER, ICE, BRIDGE) and unit.z < 0
            and unit.unit_type in floodable and not unit.specials2 & 0x100000):
        from systems.damage import destroy_mech, KILL_TYPE_FLOOD
        notify(unit, 'Water floods your engine and your unit becomes inoperable.')
        los_broadcast(unit, 'emits some bubbles and flails their arms around as they sink to the bottom.'
                      if unit.unit_type == U.BSUIT else 'emits some bubbles as its engines are flooded.')
        destroy_mech(unit, unit, showboom=False, reason=KILL_TYPE_FLOOD)
        return
    if index < 6:
        unit._startup_event = unit._engine.schedule_event(stage_interval(unit), E.STARTUP,
                                                        startup_event, data=unit, data2=index)
        return
    complete_startup(unit._engine, unit)


def startup_state(engine,unit):
    """Startup macro only, shared by boot completion and MW template loading."""
    unit.set_status(S.STARTED)
    unit.turn_damage=0
    if engine is not None:
        from core.game_loop import update_recycling
        update_recycling(engine,unit)
    unit.num_seen=0
    if engine is not None:
        from core.game_loop import INITIAL_PLOS_TICK
        from core.events import EventType
        from systems.targeting import plos_event
        engine.schedule_event(INITIAL_PLOS_TICK,EventType.PLOS,plos_event,data=unit,data2=engine)


def complete_startup(engine, unit):
    from systems.ecm import mark_for_los_update
    from systems.sensors import los_broadcast
    from physics.heights import AERO_TYPES
    from physics.collision import mech_elevation
    from systems.targeting import indexed_map
    board = indexed_map(unit)
    if board is not None and board.losinfo is not None:
        for key in list(board.losinfo):
            if key[0] == unit._id:
                board.losinfo[key] = 0
    from systems.characters import attached, actor_value, skill_target
    from systems.personal_damage import initialize_pc
    initialize_pc(unit.pilot, unit, getattr(engine, 'part_catalog', None))
    startup_state(engine,unit)
    mark_for_los_update(unit)
    from systems.parts import set_cargo_weight
    set_cargo_weight(unit)
    unit.prefs &= ~1
    los_broadcast(unit, 'powers up!')
    unit.vertical_speed = 0
    actor = unit.pilot
    player = actor is not None and getattr(actor, 'is_player', True)
    from systems.characters import character_store_for, value
    store = character_store_for(unit, actor)
    ident = getattr(actor, '_character_id', getattr(actor, '_id', -1))
    sixth = value(store, ident, 'Sixth_Sense') if store is not None else getattr(actor,'skills',{}).get('Sixth_Sense',getattr(actor,'sixth_sense',False))
    if player and getattr(actor, "_id", -1) > 0 and sixth:
        unit.specials |= Specials.SS_ABILITY
    else:
        unit.specials = Specials(int(unit.specials) & ~int(Specials.SS_ABILITY))
    if (unit.unit_type in AERO_TYPES or unit.move_type == M.VTOL) and unit.z <= mech_elevation(unit):
        unit.set_status(S.LANDED)
    unit.comm = getattr(actor, 'skills', {}).get('Comm-Conventional', getattr(actor, 'comm', 6)) if player and not getattr(unit, 'quiet', False) else 6
    unit.per = getattr(actor, 'skills', {}).get('Perception', getattr(actor, 'perception', 6)) if player and not getattr(unit, 'quiet', False) else 6
    if player and store is not None and not getattr(unit,'quiet',False):
        unit.comm=skill_target(store,ident,'Comm-Conventional')
        unit.per=skill_target(store,ident,'Perception')
    unit.comm_last, unit.last_startup = 0, engine.sim_now
    if unit.unit_type in AERO_TYPES and not unit.has_status(S.LANDED):
        from systems.movement_commands import maybe_move
        unit.desired_angle = -90
        unit.start_fx = unit.start_fy = unit.start_fz = 0
        unit.desired_speed = unit.max_speed
        maybe_move(engine, unit)
    from systems.autopilot import un_zombify_mech
    un_zombify_mech(unit)


def shutdown(engine, unit, argument='', *, caller=None, wizard=False):
    from physics.heights import AERO_TYPES
    from physics.collision import mech_upper_elevation, domino_space
    from physics.jump import mech_falls
    from physics.orbital import fall_event
    from systems.sensors import los_broadcast
    if unit is None:
        from systems.notifications import personal_notify
        for message in ('There is a problem with that item.',
                        'The data is not properly allocated.',
                        'Please notify a director of this.'):
            personal_notify(caller, message)
        return False, ''
    if not unit.is_started and not starting(engine, unit):
        return False, "The 'mech hasn't been started yet!"
    if unit.unit_type == U.MW:
        return False, 'You snore for a while.. and then _start_ yourself back up.'
    if unit.unit_type in (U.DS, U.SPHEROID_DS) and not unit.has_status(S.LANDED) and not wizard:
        return False, 'No shutdowns in mid-air! Are you suicidal?'
    if unit.pilot is None:
        return False, ''
    if starting(engine, unit):
        message = notify(unit, 'The startup sequence has been aborted.')
        engine.cancel_events_of_type(E.STARTUP, unit)
        unit._startup_event = unit.pilot = None
        return True, message
    kind = ('Dropship' if unit.unit_type in (U.DS, U.SPHEROID_DS) else
            'Fighter' if unit.unit_type in AERO_TYPES else 'Suit' if unit.unit_type == U.BSUIT else
            'Vehicle' if unit.move_type in (M.HOVER, M.TRACK, M.WHEEL) else
            'VTOL' if unit.move_type == M.VTOL else 'Mech')
    text = notify(unit, kind + ' has been shutdown!')
    if unit.has_status2(S2.SLITE_ON):
        notify(unit, 'Your searchlight shuts off.')
        unit.clear_status2(S2.SLITE_ON)
        unit.clear_crit_status(CritStatus.SLITE_LIT)
    for flag in (S.TORSO_RIGHT, S.TORSO_LEFT):
        if unit.has_status(flag):
            notify(unit, 'Torso rotated back to center for shutdown', 1)
            unit.clear_status(flag)
    if (unit.move_type != M.NONE and unit.unit_type != U.VEH_NAVAL and
            ((unit.unit_type == U.MECH and unit.is_jumping) or
             (unit.unit_type != U.MECH and mech_upper_elevation(unit) < unit.z < 300))):
        notify(unit, 'You start free-fall.. Enjoy the ride!')
        engine.schedule_event(3, E.FALL, fall_event, data=unit, data2=-1)
    elif unit.speed > 10.75:
        notify(unit, 'Your systems stop in mid-motion!')
        if unit.unit_type == U.MECH:
            los_broadcast(unit, 'stops in mid-motion, and falls!')
        else:
            notify(unit, 'You tumble end over end and come to a crashing halt!')
            los_broadcast(unit, 'tumbles end over end and comes to a crashing halt!')
        mech_falls(unit, 1, notify_fall=False)
        domino_space(unit, 2)
    shutdown_state(engine, unit)
    return True, text


def shutdown_state(engine, unit, *, historical=None):
    """Shutdown macro, retaining source events outside its explicit stop list."""
    from systems.movement_commands import historical_aircraft
    if historical is None:historical=historical_aircraft(unit)
    from core.game_loop import update_recycling
    from systems.targeting import stop_tag
    from systems.swarm import detach
    from systems.damage import release_tow
    from systems.sensors import los_broadcast
    if not unit.is_destroyed:
        if engine is not None: update_recycling(engine, unit)
        unit.speed = unit.desired_speed = 0
        unit.clear_crit_status(CritStatus.HEATCUTOFF)
        unit.clear_status(S.STARTED | S.MASC_ENABLED)
        unit.clear_status2(S2.ECM_ENABLED | S2.ECCM_ENABLED | S2.PER_ECM_ENABLED | S2.PER_ECCM_ENABLED |
                           S2.ANGEL_ECM_ENABLED | S2.ANGEL_ECCM_ENABLED | S2.NULLSIGSYS_ON | S2.STH_ARMOR_ON)
    unit.pilot, unit.target = None, -1
    unit.clear_status2(S2.MOVE_MODES | (0 if historical else S2.SLITE_ON))
    if not historical:unit.clear_crit_status(CritStatus.SLITE_LIT)
    for kind in (E.STARTUP, E.MOVEMODE, E.JUMP, E.MOVE, E.AERO_MOVE, E.STAND, E.JUMPSTABIL,
                 E.TAKEOFF, E.HIDE, E.DIG, E.HULLDOWN):
        if engine is not None: engine.cancel_events_of_type(kind, unit)
    for handle in ('_startup_event', '_mode_event', '_stand_event', '_stabil_event', '_hulldown_event'):
        setattr(unit, handle, None)
    unit.masc_counter = 0
    from systems.combat_equipment import stop_digging
    stop_digging(unit)
    stop_tag(unit)
    if any(unit.sections[loc].specials & 0x20 for loc in (L.RARM, L.LARM)):
        for loc in (L.RARM, L.LARM): unit.sections[loc].specials &= ~0x20
        notify(unit, 'Your club falls to the ground and shatters.')
        los_broadcast(unit, "'s club falls to the ground and shatters.")
    if engine is not None: engine.cancel_events_of_type(E.MASC_FAIL, unit)
    unit.charge_target = -1
    detach(unit,historical=historical)
    unit.scharge_counter = 0
    if unit.carrying > 0:
        from systems.towing import dropoff
        dropoff(unit, 1)

BSUIT_BOOTMSGS = ('%cg->         Initializing powerpack       <-%c', '%cg->          Powerpack operational       <-%c', '%cg->             Suit sealed              <-%c', '%cg->  Computer system is now operational  <-%c', '%cg->         Air pressure steady          <-%c', '       %cg- %cr-=>%ch%cw All systems go!%c %cr<= %cg-%c')

AERO_BOOTMSGS = ('%cg->       Main reactor is now online    <-%c', '%cg->            Thrusters online         <-%c', '%cg->  Main computer system is now online <-%c', '%cg->     Scanners are now operational    <-%c', '%cg-> Targeting system is now operational <-%c', '       %cg- %cr-=>%ch%cw All systems go!%c %cr<= %cg-%c')

BOOTMSGS = ('%cg->       Main reactor is now online    <-%c', '%cg->         Gyros are now stable        <-%c', '%cg->  Main computer system is now online <-%c', '%cg->     Scanners are now operational    <-%c', '%cg-> Targeting system is now operational <-%c', '   %cg- %cr-=>%ch%cw All systems operational!%c %cr<=- %cg-%c')

HOVER_BOOTMSGS = ('%cg->  Powerplant initialized and online  <-%c', '%cg->   Checking plenum chamber status    <-%c', '%cg->         Verifying fan status        <-%c', '%cg->     Scanners are now operational    <-%c', '%cg-> Targeting system is now operational <-%c', '   %cg- %cr-=>%ch%cw All systems operational!%c %cr<=- %cg-%c')

TRACK_BOOTMSGS = ('%cg->  Powerplant initialized and online  <-%c', '%cg->      Auto-aligning drive wheels     <-%c', '%cg->       Adjusting track tension       <-%c', '%cg->     Scanners are now operational    <-%c', '%cg-> Targeting system is now operational <-%c', '   %cg- %cr-=>%ch%cw All systems operational!%c %cr<=- %cg-%c')

WHEEL_BOOTMSGS = ('%cg->  Powerplant initialized and online  <-%c', '%cg->  Performing steering system checks  <-%c', '%cg->        Checking wheel status        <-%c', '%cg->     Scanners are now operational    <-%c', '%cg-> Targeting system is now operational <-%c', '   %cg- %cr-=>%ch%cw All systems operational!%c %cr<=- %cg-%c')

VTOL_BOOTMSGS = ('%cg->     Initializing main powerplant    <-%c', '%cg-> Main turbine online and operational <-%c', '%cg->      Rotor transmission engaged     <-%c', '%cg->     Scanners are now operational    <-%c', '%cg-> Targeting system is now operational <-%c', '   %cg- %cr-=>%ch%cw All systems operational!%c %cr<=- %cg-%c')

NAVAL_BOOTMSGS = ('%cg->       Main reactor is now online    <-%c', '%cg->  Main computer system is now online <-%c', '%cg->   Hull integrity monitoring online  <-%c', '%cg-> Ballast and propulsion are nominal  <-%c', '%cg-> Targeting system is now operational <-%c', '   %cg- %cr-=>%ch%cw All systems operational!%c %cr<=- %cg-%c')


def actor_authority(unit, actor, *, security=False):
    """Wiz/WizP: owner authority and the source inheritance gate."""
    from systems.targeting import resolve_object
    ident = getattr(actor, '_id', actor)
    owner = getattr(actor, 'owner', ident)
    if isinstance(owner, int):
        owner = actor if owner == ident else resolve_object(unit, owner)
    if owner is None:
        return False
    inherits = (getattr(owner, '_id', owner) == ident or
                getattr(actor, 'inherit', False) or getattr(owner, 'inherit', False))
    wizard = getattr(owner, '_id', owner) == 1 or getattr(owner, 'wizard', False) or getattr(owner, 'god', False)
    privilege = wizard or security and (getattr(owner, 'royalty', False) or getattr(owner, 'security', False))
    return bool(inherits and privilege)


def pilot_owner_id(unit):
    from core.attributes import attributes_for
    from systems.characters import character_store_for
    text = attributes_for(unit).get(unit._id, 'A_PILOTNUM')
    if not text:
        owner = getattr(unit, 'pilot_owner', -1)
        return getattr(owner, '_id', owner)
    store = character_store_for(unit, unit.pilot)
    if store is not None:
        return store.lookup(1, text)
    from systems.targeting import resolve_object
    if text.lower() == 'me':
        return 1
    if text.startswith('#'):
        import re
        if not re.fullmatch(r'[+-]?[0-9]+', text[1:]):
            return -1
        obj = resolve_object(unit, int(text[1:]))
        return getattr(obj, '_id', -1) if getattr(obj, 'valid', True) else -1
    for actor in unit._engine.get_entities():
        if getattr(actor, 'is_player', False) and getattr(actor, 'valid', True) and actor.name.lower() == text.lower():
            return actor._id
    return -1
