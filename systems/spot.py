# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.bth.c
#   btech/mech.combat.c
#   btech/mech.spot.c
#   btech/mech.utils.c
#   btech/src/include/btconfig.h
#   btech/template.c

"""
Spotter / indirect-fire layer — port of mech.spot.c.

A unit sets ITSELF up as a spotter (`spot <own id>`); shooters then link to
it (`spot <spotter id>`) and their IDF weapons fire at whatever the spotter
has locked (mech or hex), with the spotter's skill and movement folded into
the BTH (FireSpot -> FireWeapon indirectFire, mech.spot.c:190-292).

Artillery datalinks are supported. Skill XP and artillery flight/area
damage remain external dependencies; see docs/sensors-los-completion.md.

Failure style: command-shaped entry points return (ok, message) tuples
(mech_spot) or AttackResults with the C's notify text as the single message
(fire_spot), matching fire_weapon_number; no exceptions.
"""

from core.events import EventType
from core.game_loop import SPOT_TICK
from entities.mech import MechStatus, UnitType
from physics.hexmath import ZSCALE, hex_to_float
from systems.los import in_line_of_sight, in_water
from systems.targeting import fa_mech_range, find_mech_in_hex, find_range, \
    fl_mech_range, locking

NOTIFY_HOOK = None


def _notify(mech, message: str) -> None:
    from systems.movement_commands import notify
    notify(mech, message)
    if NOTIFY_HOOK is not None:
        NOTIFY_HOOK(mech, message)


# ud.radio_range template fallback (template.c:2728, btconfig.h:188).
DEFAULT_RADIORANGE = 80


def clear_fire_adjustments(gamemap, mech_id) -> None:
    """
    Zero the artillery fire-adjustment counter of every unit spotting
    through mech_id.  Port of ClearFireAdjustments (mech.spot.c:90-104).
    """
    for m in gamemap.mechs_on_map:
        if m is None or m._id == mech_id:
            continue
        if m.spotter == mech_id:
            m.fire_adjustment = 0


def mech_full_no_recycle(mech) -> bool:
    from systems.physical import mech_full_no_recycle as busy
    return bool(busy(mech, 3))


def mech_spot(engine, mech, arg, caller=None) -> tuple:
    """
    The `spot` command, including delayed artillery links and movement gates.

    arg: "-" to clear, a two-character contact ID, or a Mech object.
    """
    from systems.movement_commands import mode_locked
    from systems.communications import common_checks, MECH_USUALO
    from systems.targeting import contact_target
    if mech is not None:
        mech._engine = engine
    actor = caller if caller is not None else getattr(mech, 'command_actor', getattr(mech, 'pilot', None))
    error = common_checks(mech, actor, MECH_USUALO)
    if error is not None:
        return False, error
    if getattr(engine, 'movement_modes', True) and mode_locked(mech):
        return False, 'You cannot spot while using a special movement mode.'
    if isinstance(arg,str):
        args = arg.split()
        if len(args) != 1:
            return False, "You may only use mech ID's to set spotter!"
        arg = args[0]
    gamemap = mech.map

    # DOCHECK(MechType(mech) == CLASS_MW, ...) (mech.spot.c:126-127)
    if mech.unit_type == UnitType.MW:
        return (False, "Spot ? You ? What with, your pretty blue eyes ? "
                       "Hah!")

    # '-' clears (mech.spot.c:132-141)
    if arg == '-':
        if mech.spotter == mech._id:
            message = "You spot no longer."
            _notify(mech, message)
            if gamemap is not None:
                clear_fire_adjustments(gamemap, mech._id)
        else:
            message = "You disable the datalink to spotter."
            _notify(mech, message)
        mech.spotter = -1
        return (True, message)

    if isinstance(arg, str):
        arg = contact_target(mech, arg)

    # Self-arg: become a spotter (mech.spot.c:142-147)
    if arg is mech:
        if mech_full_no_recycle(mech):
            return (False, "You have weapons recycling!")
        mech.spotter = mech._id
        _notify(mech, "You are now set as a spotter.")
        return (True, "You are now set as a spotter.")

    target = arg
    # FindTargetDBREFFromMapNumber resolves same-map contacts only; the
    # team gate shares the not-found text so enemies stay hidden
    # (mech.spot.c:153-155).
    if (target is None or gamemap is None or
            target not in gamemap.mechs_on_map or
            target.team != mech.team):
        return (False, "That target does not exist!")

    # LOS computed before the gates (mech.spot.c:149-152)
    los = in_line_of_sight(mech, target, target.x, target.y,
                           fl_mech_range(gamemap, mech, target))

    if target.unit_type == UnitType.MW:
        return (False, "Spot ? That puny being ?! What with, those clear "
                       "brown eyes ? Hah!")
    if target.spotter != target._id:
        return (False, "That 'mech is not set up as spotter!")

    if is_artillery_mech(mech) and not los:
        _notify(target, 'Someone is trying to establish a data link with you!')
        _notify(mech, 'You attempt to establish a data link..... please stand by.')
        distance = fl_mech_range(gamemap,mech,target)
        if distance > 2 * getattr(target,'radio_range',DEFAULT_RADIORANGE):
            _notify(mech, 'That target is our of data link range!')
            return False, 'That target is our of data link range!'
        engine.schedule_event(2*(int(distance)//10+5),EventType.SPOT_LOCK,spot_lock_event,
                              data=mech,data2=(engine,target,(mech.fx,mech.fy,target.fx,target.fy)))
        return True, ''

    if not los:
        return (False, "You do not have LOS to that target!")

    mech.spotter = target._id
    mech.fire_adjustment = 0            # MechFireAdjustment (mech.spot.c:185)
    from systems.notifications import identity
    message = f'{identity(mech, target)} set as spotter.'
    _notify(mech, message)
    return True, message


def spot_check_event(event) -> None:
    """
    EVENT_SPOT_CHECK watchdog: drop the spotter link when the spotter is
    gone, out of data-link range (2 * MechRadioRange, mech.spot.c:54-55),
    no longer a spotter, or on a different map; else re-arm at SPOT_TICK.
    Port of mech_check_range (mech.spot.c:38-62).
    """
    mech = event.data
    engine, spotter = event.data2

    if mech is None:
        return
    if mech.spotter == -1:              # mech.spot.c:46-47
        return
    if spotter is None:
        _notify(mech, "You have lost link with your spotter!")
        mech.spotter = -1               # mech.spot.c:49-53
        return
    rng = fl_mech_range(mech.map, mech, spotter)     # mech.spot.c:54
    if (rng > 2 * getattr(spotter, 'radio_range', DEFAULT_RADIORANGE)
            or spotter.spotter == -1 or spotter.map is not mech.map):
        _notify(mech, "You have lost link with your spotter!")
        mech.spotter = -1               # mech.spot.c:54-60
        return
    # Re-arm (mech.spot.c:61)
    engine.schedule_event(SPOT_TICK, EventType.SPOT_CHECK, spot_check_event,
                          data=mech, data2=(engine, spotter))


def fire_spot(engine, mech, weapon_number: int, **kwargs):
    """
    Fire an IDF weapon through the mech's spotter.  Port of FireSpot
    (mech.spot.c:190-292).  Reached from fire_weapon_number's hand-off
    (mech.combat.c:514-519): IDF weapon, spotter set, no mech lock.

    The spotter's own lock decides the target: a locked mech is attacked
    directly (spotter terrain + movement folded into indirectFire,
    mech.spot.c:221-253); a locked hex is probed with find_mech_in_hex and
    otherwise hit as a hex (mech.spot.c:254-291, NO AddTerrainMod).

    Source spotting/artillery awards precede actual indirect fire.
    """
    from systems.combat import (
        AttackResult, TARGCOMP_MULTI, calculate_attacker_movement_modifier,
        fire_weapon,
    )
    from systems.los import add_terrain_mod

    from systems.notifications import mech_notify, MECHPILOT, MECHALL

    def _fail(message: str, audience=None, *, handled=True) -> AttackResult:
        result = AttackResult(handled=handled)
        result.messages.append(message)
        if audience is not None:
            mech_notify(mech, audience, message)
        return result

    gamemap = mech.map

    # spotter = getMech(MechSpotter(mech)) (mech.spot.c:209-210; typo
    # verbatim). Resolve globally through the owning engine registry.
    from entities.weapon import WeaponFlags, WeaponType, get_weapon_by_index
    from systems.targeting import resolve_unit
    if not 0 <= weapon_number < len(mech.weapons):
        return _fail('Illegal Weapon Number!')
    weapon = get_weapon_by_index(mech.weapons[weapon_number].weapon_idx)
    if mech.spotter == -1 or not weapon.special & WeaponFlags.IDF:
        return AttackResult(handled=False)
    artillery = weapon.weapon_type == WeaponType.TARTILLERY
    kwargs.setdefault('engine', engine)
    kwargs['los'] = 0  # Both C FireSpot branches pass literal LOS=0.
    spotter = resolve_unit(mech, mech.spotter, engine)
    if spotter is None:
        return _fail("There is no spotter avilable to IDF with!", MECHPILOT)

    if spotter.spotter != spotter._id:      # mech.spot.c:212-216
        result = _fail("You do not have a spotter!", MECHALL)
        mech.spotter = -1
        return result
    if spotter.is_unconscious:              # mech.spot.c:217
        return _fail("Your spotter is unconscious!", MECHPILOT)
    if spotter.has_status(MechStatus.BLINDED):      # mech.spot.c:218
        return _fail("Your spotter can't see a thing!", MECHPILOT)

    # Locking(spotter) with a non-MULTI targeting computer adds 2
    # (mech.spot.c:238-241, 286-287)
    locking_penalty = 2 if (locking(engine, spotter) and
                            spotter.targcomp != TARGCOMP_MULTI) else 0

    # --- Spotter locked a mech (mech.spot.c:221-253) ---------------------
    if spotter.target != -1:
        target = resolve_unit(mech, spotter.target, engine)
        if target is None:
            return _fail("Your spotter has invalid target!", MECHPILOT)
        mapx, mapy = target.x, target.y
        spot_range = fa_mech_range(spotter, target)
        if not in_line_of_sight(spotter, target, mapx, mapy, spot_range):
            # Typo verbatim (mech.spot.c:228)
            return _fail("You spotter does not have a target in LOS!", MECHPILOT)
        distance = fa_mech_range(mech, target)
        if in_water(target) and not in_water(mech):     # mech.spot.c:230
            return _fail("You can't fire into water with that weapon from "
                         "here.", handled=False)

        if artillery:
            return _fail('You can only target hexes with this kind of artillery.')
        # Non-artillery spotTerrain (mech.spot.c:232-241).
        spot_terrain = (1 + add_terrain_mod(spotter, target, gamemap,
                                            spot_range, 0) +
                        calculate_attacker_movement_modifier(spotter) +
                        locking_penalty)

        if not kwargs.get('sight', False):
            from systems.experience import spot, artillery as award_artillery
            spot(spotter.pilot, spotter, target)
            award_artillery(mech.pilot, mech, target)
        # FireWeapon(..., LOS=0, indirectFire=spotTerrain, ishex=2)
        # (mech.spot.c:249-251).  No unstable-lock term when a spotter is
        # set (mech.bth.c:270) — unstable_lock_arc stays None.
        return fire_weapon(mech, target, weapon_number, distance,
                           indirect_fire=spot_terrain, spotter=spotter,
                           ishex=2, mapx=mapx, mapy=mapy, **kwargs)

    # --- Spotter locked a hex (mech.spot.c:254-291) ----------------------
    if not (spotter.targ_x >= 0 and spotter.targ_y >= 0):
        return _fail("Your spotter has no target set!")

    # Artillery never probes the target hex for a unit (mech.spot.c:258).
    target = None if artillery else find_mech_in_hex(mech, gamemap, spotter.targ_x,
                              spotter.targ_y, 0)
    if target is not None:
        enemy_x, enemy_y, enemy_z = target.fx, target.fy, target.fz
        mapx, mapy = target.x, target.y
    else:
        mapx, mapy = spotter.targ_x, spotter.targ_y     # mech.spot.c:269-275
        enemy_z = ZSCALE * spotter.targ_z
        enemy_x, enemy_y = hex_to_float(mapx, mapy)

    spot_range = find_range(spotter.fx, spotter.fy, spotter.fz,
                            enemy_x, enemy_y, enemy_z)  # mech.spot.c:276-278
    if not in_line_of_sight(spotter, target, mapx, mapy, spot_range):
        return _fail("That target is not in your spotters line of sight!", handled=False)
    distance = find_range(mech.fx, mech.fy, mech.fz,
                          enemy_x, enemy_y, enemy_z)    # mech.spot.c:281-283

    # spotTerrain for the hex case: NO AddTerrainMod (mech.spot.c:284-287)
    spot_terrain = 2 if artillery else (1 + calculate_attacker_movement_modifier(spotter) +
                    locking_penalty)

    return fire_weapon(mech, target, weapon_number, distance,
                       indirect_fire=spot_terrain, spotter=spotter,
                       ishex=2, mapx=mapx, mapy=mapy, **kwargs)


def is_artillery_mech(mech):
    from entities.weapon import get_weapon_by_index,WeaponType
    return any(get_weapon_by_index(ws.weapon_idx).weapon_type == WeaponType.TARTILLERY for ws in mech.weapons)


def spot_lock_event(event):
    mech=event.data
    engine,target,saved=event.data2
    if all(a != b for a,b in zip((mech.fx,mech.fy,target.fx,target.fy),saved)):
        for unit in (target,mech):
            _notify(unit,'The data link was not established due to movement!')
        return
    from systems.notifications import identity
    # Both source messages intentionally use the observer's identity of shooter.
    name = identity(target, mech)
    _notify(target,f'Data link established with {name}.')
    _notify(mech,f'Data link established with {name}, you now have a forward observer.')
    mech.spotter=target._id
    engine.schedule_event(SPOT_TICK,EventType.SPOT_CHECK,spot_check_event,data=mech,data2=(engine,target))
