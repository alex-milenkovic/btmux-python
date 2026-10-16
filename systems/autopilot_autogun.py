# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/autopilot_autogun.c

"""Battlesheep sensor, target, profile and combat decisions.

The general source is heartbeat driven, even with AUTOGUN clear. Historical
Aerospace owns its gun/profile/sensor event chains and sensor-change delay.
"""
import math
from entities.autopilot import Autopilot, WeaponNode, TargetNode
from entities.mech import Mech, UnitType as U, MoveType as M, MechStatus as S, CritStatus as C, Specials, Location as L, FireMode
from entities.weapon import get_weapon_by_index, WeaponType, WeaponFlags, MISSILE_HIT_TABLE
from core.events import EventType as E
from core.randomness import float32 as f32
from systems.autopilot import uses_event_autopilot, good_object, valid_special_objects
from systems.autopilot_commands import stop_gun, zombify
from systems.autopilot_core import schedule
from systems.targeting import indexed_map, resolve_object, resolve_unit, fa_mech_range
from systems.los import mech_to_mech_los_flag, MECHLOSFLAG_SEEN, MECHLOSFLAG_BLOCK
from systems.weapon_inventory import weapon_runs, weapon_is_nonfunctional
from systems.heat import is_running
from physics.hexmath import (find_range, find_bearing, in_weapon_arc, FORWARDARC,
    LSIDEARC, RSIDEARC, REARARC, find_xy, float_to_hex, hex_to_float)


def _valid(a):
    return valid_special_objects(a)


def _flying(mech):
    return mech.unit_type in (U.VTOL,U.AERO,U.DS,U.SPHEROID_DS)


def _rearm(a, kind, delay):
    if uses_event_autopilot(a.mymech):
        a._engine.cancel_events_of_type(kind,a)
        schedule(a,delay,kind)


def SearchLightInRange(mech, board):
    if mech is None or board is None:
        return 0
    historical = uses_event_autopilot(mech)
    for target in board.mechs_on_map:
        if target is None or not target.specials & Specials.SLITE_TECH or mech.crit_status & C.SLITE_DEST:
            continue
        if fa_mech_range(target,mech) >= 30:
            continue
        # C reads the original status word here, despite SLITE_ON being a
        # status2 constant in the general source. Do not substitute status2.
        on = bool(int(target.status) & 0x20)
        arced = in_weapon_arc(target,mech.fx,mech.fy) & FORWARDARC
        blocked = bool(mech_to_mech_los_flag(board,target,mech) & MECHLOSFLAG_BLOCK)
        if on and arced:
            return 4 if blocked else 3
        # Recovered "!status & SLITE_ON" has the C precedence bug.
        if not on and arced and not historical:
            return 6 if blocked else 5
        return 1 if on else 2
    return 0


def PrefVisSens(mech, board, slite, target):
    if mech is None or board is None:
        return 0
    if int(mech.status) & 0x20 or mech.crit_status & C.SLITE_LIT:
        return 0
    if target is not None and target.crit_status & C.SLITE_LIT:
        return 0
    return 1 if board.maplight <= 1 and slite not in (3,5) else 0


def auto_sensor_event(a, flag=0):
    if (isinstance(a,Autopilot) and not uses_event_autopilot(a.mymech)
            and (not good_object(a,a.mymechnum) or not good_object(a,a._id))):
        return
    if not _valid(a):
        return
    mech = a.mymech
    if mech.is_destroyed:
        stop_gun(a)
        return
    if not mech.is_started:
        zombify(a)
        return
    if a.flags & 16:
        return
    board = indexed_map(mech)
    if board is None:
        zombify(a)
        return
    target = resolve_unit(mech,mech.target) if mech.target > 0 else None
    slite = SearchLightInRange(mech,board) if board.mapvis != 2 else 0
    rvis = board.mapvis if board.maplight else board.mapvis * (1 if slite else 3)
    pref = PrefVisSens(mech,board,slite,target)
    if target is None:
        wanted = [3,2] if rvis <= 15 else [pref,pref]
    else:
        distance = int(fa_mech_range(mech,target))
        if target.tonnage >= 60 and distance <= 20:
            wanted = [3,2]
        elif _flying(target) and not target.status & S.LANDED:
            wanted = [5,pref]
        elif distance <= 4 and mech.specials & Specials.BEAGLE_PROBE_TECH and not mech.crit_status & C.BEAGLE_DESTROYED:
            wanted = [6,6]
        elif distance <= 8 and mech.specials2 & 0x800 and not mech.crit_status & C.BLOODHOUND_DESTROYED:
            wanted = [7,7]
        else:
            wanted = [pref,3 if rvis <= 15 else pref]
    if list(mech.sensor) != wanted:
        if uses_event_autopilot(mech):
            from systems.targeting import set_sensors
            from systems.sensors import sensors
            set_sensors(a._engine,mech,' '.join(sensors[i].matchletter for i in wanted))
        else:
            from systems.movement_commands import notify
            from systems.ecm import mark_for_los_update
            mech.sensor[:] = wanted
            notify(mech,'As your sensors change, your lock clears.')
            mech.target = -1
            mark_for_los_update(mech)
    if not flag and uses_event_autopilot(mech):
        schedule(a,30,E.AUTO_SENSOR)


def auto_create_weapon_node(weapon_number, weapon_db_number, section, critical):
    return WeaponNode(weapon_number,weapon_db_number,section,critical)


def auto_destroy_weapon_node(victim):
    # References are owned by weaplist/profile; Python reclaims unlinked nodes.
    return None


def auto_create_target_node(target_score, target_dbref):
    return TargetNode(target_score,target_dbref)


def auto_destroy_target_node(victim):
    return None


def auto_destroy_weaplist(a):
    if a.weaplist is not None:
        a.weaplist.clear()
    a.weaplist = None


def auto_targets_callback(key, data, arg=None):
    auto_destroy_target_node(data)
    return 1


def auto_generic_compare(left, right, token=None):
    return (left > right) - (left < right)


def auto_calc_weapon_score(weapon_db_number, distance):
    weapon = get_weapon_by_index(weapon_db_number)
    if weapon is None or distance >= weapon.range_long:
        return 0
    range_score = 215 if distance >= weapon.range_medium else 390 if distance >= weapon.range_short else 500
    under = max(0,weapon.range_min-distance)
    min_score = int(-12.5*under*under-25.0*under)
    damage = weapon.damage
    if weapon.weapon_type == WeaponType.TMISSILE:
        from systems.ammo_dump import AMMO_FULL_SALVO
        from systems.buildings import SOURCE_CLUSTER_ROWS
        rack = AMMO_FULL_SALVO.get(weapon.name)
        hits = SOURCE_CLUSTER_ROWS[weapon.name][5] if weapon.name in SOURCE_CLUSTER_ROWS else (1 if rack == 1 else MISSILE_HIT_TABLE[7].get(rack,0))
        damage *= hits
    return range_score + min_score + 50*damage - 25*weapon.heat + 250


def auto_update_profile_event(a):
    if (isinstance(a,Autopilot) and not uses_event_autopilot(a.mymech)
            and not good_object(a,a.mymechnum)):
        stop_gun(a)
        return
    if not _valid(a) or a.mymech.is_destroyed:
        return
    mech = a.mymech
    a.profile = [None]*30
    auto_destroy_weaplist(a)
    a.weaplist = []
    a.mech_max_range = 0
    for number, run in enumerate(weapon_runs(mech)):
        weapon = get_weapon_by_index(run.weapon_idx)
        if weapon.special & WeaponFlags.AMS or weapon_is_nonfunctional(mech,run.section,run.critical) > 0:
            continue
        node = auto_create_weapon_node(number,run.weapon_idx,run.section,run.critical)
        a.weaplist.append(node)
        a.mech_max_range = max(a.mech_max_range,weapon.range_long)
        for distance in range(min(30,weapon.range_long)):
            if a.profile[distance] is None:
                a.profile[distance] = {}
            score = auto_calc_weapon_score(run.weapon_idx,distance)
            while score in a.profile[distance]:
                score += 1
            node.range_scores[distance] = score
            a.profile[distance][score] = node
    _rearm(a,E.AUTO_PROFILE,180)


def auto_calc_target_score(a, mech, target, board=None):
    board = board or indexed_map(mech)
    if target.is_destroyed or target.status & S.COMBAT_SAFE or target.team == mech.team:
        return 0
    distance = find_range(mech.fx,mech.fy,target.fx,target.fy)
    if distance >= 30:
        return 0
    armor = sum(s.armor+s.rear for s in target.sections)
    original_armor = sum(s.armor_orig+s.rear_orig for s in target.sections)
    internal = sum(s.internal for s in target.sections)
    original_internal = sum(s.internal_orig for s in target.sections)
    if not original_armor and not original_internal:
        return 0
    damage = 0.0
    if original_armor:
        damage += -3.0*f32(f32(armor)/f32(original_armor))+300.0
    if original_internal:
        damage += -2.0*f32(f32(internal)/f32(original_internal))+200.0
    status = (100.0 if not target.is_started else 0)+(100.0 if target.is_unconscious else 0)
    if mech_to_mech_los_flag(board,mech,target) & MECHLOSFLAG_SEEN:
        status += 500.0 if uses_event_autopilot(mech) else 2000.0
    range_score = f32(-10.0*distance+300.0)
    speed_score = f32(-2.0*target.speed+300.0)
    bv_score = f32(.05*getattr(target,'bv',0))
    return math.floor(f32(f32(f32(f32(range_score+speed_score)+bv_score)+f32(damage))+f32(status)))


def _limbs_recycling(mech):
    return any(mech.sections[i].recycle for i in (L.RARM,L.LARM,L.RLEG,L.LLEG))


def _kick_side(mech, right, left, right_busy, left_busy):
    from systems.physical import okay_crit_sect
    from entities.crittypes import Special
    def penalty(loc):
        return sum((3 if i == 0 else 1) for i in range(4) if not okay_crit_sect(mech,loc,i,Special(i)))
    rscore = 99 if right_busy else penalty(right)
    lscore = 0
    if left_busy:
        rscore = 99  # The source assigns rleg_bth in the left-busy branch.
    else:
        lscore = penalty(left)
    return 'r' if rscore <= lscore else 'l'


def _physical(a, target, board):
    mech = a.mymech
    distance = find_range(mech.fx,mech.fy,target.fx,target.fy)
    physical = target if distance < 1 else None
    if distance > 3:
        for other in board.mechs_on_map:
            if other is None or other is mech or other._id <= 0:
                continue
            target = other
            if other.is_destroyed or other.status & S.COMBAT_SAFE or other.team == mech.team:
                continue
            if find_range(mech.fx,mech.fy,other.fx,other.fy) < 1:
                physical = other
                break
    if physical is None or not mech_to_mech_los_flag(board,mech,physical) & MECHLOSFLAG_SEEN or mech.unit_type != U.MECH:
        return
    from systems.physical import sect_has_busy_weap, have_axe, have_sword, physical_command
    from systems.parts import mech_ids
    diff = mech.z-target.z
    def attack(name,side,victim=target):
        return physical_command(mech,name,side+' '+mech_ids(victim,True),caller=a)
    limbs = (L.RARM,L.LARM,L.RLEG,L.LLEG)
    if mech.move_type == M.BIPED:
        mech.status &= ~(S.TORSO_RIGHT|S.TORSO_LEFT)
        if mech.specials & Specials.FLIPABLE_ARMS:
            mech.status &= ~S.FLIPPED_ARMS
        arc = in_weapon_arc(mech,physical.fx,physical.fy)
        relative = mech.facing-find_bearing(mech.fx,mech.fy,physical.fx,physical.fy)
        if arc & LSIDEARC:
            mech.status |= S.TORSO_LEFT
        elif arc & RSIDEARC:
            mech.status |= S.TORSO_RIGHT
        elif arc & REARARC:
            if 120 < relative < 180:
                mech.status |= S.TORSO_RIGHT
            elif 180 < relative < 240:
                mech.status |= S.TORSO_LEFT
        new_arc = in_weapon_arc(mech,physical.fx,physical.fy)
        dead = [mech.is_section_destroyed(i) for i in limbs]
        busy = [sect_has_busy_weap(mech,i) for i in limbs]
        for index,side,sidearc in ((0,'r',RSIDEARC),(1,'l',LSIDEARC)):
            if not dead[index] and not busy[index] and not _limbs_recycling(mech) and new_arc & (FORWARDARC|sidearc) and diff in (0,-1):
                if have_axe(mech,limbs[index]):
                    attack('axe',side)
                elif have_sword(mech,limbs[index]):
                    attack('sword',side)
        if (not busy[2] or not busy[3]) and not dead[2] and not dead[3] and arc & FORWARDARC and not _limbs_recycling(mech) and diff in (0,1):
            attack('kick',_kick_side(mech,L.RLEG,L.LLEG,busy[2],busy[3]),physical)
        if ((not dead[0] and not busy[0]) or (not dead[1] and not busy[1])) and not _limbs_recycling(mech) and diff in (0,-1):
            right = not dead[0] and not busy[0] and new_arc & (FORWARDARC|RSIDEARC)
            left = not dead[1] and not busy[1] and new_arc & (FORWARDARC|LSIDEARC)
            attack('punch','b' if right and left else 'r' if right else 'l')
    elif mech.move_type == M.QUAD:
        arc = in_weapon_arc(mech,physical.fx,physical.fy)
        dead = [mech.is_section_destroyed(i) for i in limbs]
        right_busy,left_busy = (sect_has_busy_weap(mech,i) for i in limbs[:2])
        if not right_busy and not any(dead) and arc & FORWARDARC and not _limbs_recycling(mech) and diff in (0,1):
            attack('kick',_kick_side(mech,L.RARM,L.LARM,right_busy,left_busy),physical)


def _weapon_arc(a, target, node):
    mech = a.mymech
    section,critical = node.section,node.critical
    rear = mech.sections[section].criticals[critical].firemode & FireMode.REAR_MOUNT
    if mech.unit_type == U.MECH and mech.move_type == M.BIPED:
        mech.status &= ~(S.TORSO_RIGHT|S.TORSO_LEFT)
        if mech.specials & Specials.FLIPABLE_ARMS:
            mech.status &= ~S.FLIPPED_ARMS
        arc = in_weapon_arc(mech,target.fx,target.fy)
        if arc & REARARC:
            if section in (L.RARM,L.LARM):
                if mech.specials & Specials.FLIPABLE_ARMS:
                    mech.status |= S.FLIPPED_ARMS
                else:
                    relative = mech.facing-find_bearing(mech.fx,mech.fy,target.fx,target.fy)
                    if 120 < relative < 180 and section == L.RARM:
                        mech.status |= S.TORSO_RIGHT
                    elif 180 < relative < 240 and section == L.LARM:
                        mech.status |= S.TORSO_LEFT
                    else:
                        return False
            elif not rear:
                return False
        elif arc & (LSIDEARC|RSIDEARC):
            if section in (L.RLEG,L.LLEG):
                return False
            mech.status |= S.TORSO_LEFT if arc & LSIDEARC else S.TORSO_RIGHT
        elif arc & FORWARDARC and rear:
            return False
    elif mech.unit_type == U.MECH and mech.move_type == M.QUAD:
        arc = in_weapon_arc(mech,target.fx,target.fy)
        if arc & REARARC:
            return bool(rear)
        if arc & FORWARDARC:
            return not rear
        return False
    elif mech.unit_type in (U.VEH_GROUND,U.VEH_NAVAL):
        from systems.combat import is_in_weapon_arc
        from systems.maneuver import set_turret
        if mech.sections[4].internal and section == 4:
            bearing = find_bearing(mech.fx,mech.fy,target.fx,target.fy)
            if not mech.tank_crit_status & 3 and (mech.facing+mech.turret_facing)%360 != bearing:
                set_turret(a._engine,mech,str(bearing),caller=a)
        elif not is_in_weapon_arc(mech,target.fx,target.fy,section,critical):
            return False
    return True


def _chase(a, target, board):
    if not a.flags & 32:
        return False
    from systems.autopilot_core import (auto_get_command_enum, auto_disengage,
        auto_delcommand, auto_addcommand, auto_engage)
    if auto_get_command_enum(a,1) not in (-1,0):
        a.chase_target,a.chasetarg_update_tick,a.follow_update_tick = -10,30,10
        return False
    if a.target != a.chase_target or a.chasetarg_update_tick >= 30:
        a.chase_target,a.chasetarg_update_tick,a.follow_update_tick = a.target,0,10
        auto_disengage(a,a,'')
        auto_delcommand(a,a,'-1')
        gun = 'autogun target '+str(a.target) if a.flags & 256 and a.target != -1 else 'autogun on'
        auto_addcommand(a,a,gun)
        auto_addcommand(a,a,'chasetarget '+str(a.target))
        auto_engage(a,a,'')
        return True
    a.chasetarg_update_tick += 1
    if target is not None and not target.is_destroyed and target.mapindex == a.mymech.mapindex:
        x,y = float_to_hex(*find_xy(target.fx,target.fy,target.facing+a.ofsx,a.ofsy))
        if not board.valid(x,y):
            x,y = target.x,target.y
        mech = a.mymech
        if (mech.x,mech.y) == (x,y) and target.speed < .5:
            from systems.autopilot_ai import ai_set_heading
            ai_set_heading(mech,a,find_bearing(mech.fx,mech.fy,*hex_to_float(x,y)))
    return False


def auto_gun_event(a):
    if not _valid(a):
        return
    mech = a.mymech
    historical = uses_event_autopilot(mech)
    if mech.is_destroyed:
        stop_gun(a)
        return
    board = indexed_map(mech)
    if not mech.is_started or board is None:
        zombify(a)
        return
    if a.weaplist is None:
        if historical:
            schedule(a,1,E.AUTO_PROFILE)
            _rearm(a,E.AUTOGUN,1)
        return
    if mech.cocoon:
        _rearm(a,E.AUTOGUN,1)
        return
    if a.target > -1:
        target = resolve_unit(mech,a.target)
        if (target is None or target.is_destroyed or target.mapindex != mech.mapindex
            or not a.flags & 256 and find_range(mech.fx,mech.fy,target.fx,target.fy) >= 30):
            a.target,a.target_score = -1,0
    if a.flags & 256 and a.target == -1:
        a.flags &= ~256
    if a.target == -1 or a.target_update_tick >= 30 and not a.flags & 256:
        a.target_update_tick = 0
        targets = {}
        for other in board.mechs_on_map:
            if other is None or other is mech or other._id <= 0:
                continue
            score = auto_calc_target_score(a,mech,other,board)
            if a.target == other._id:
                a.target_score = score
            if score <= 0:
                continue
            while score in targets:
                score += 1
            targets[score] = auto_create_target_node(score,other._id)
        if not targets:
            a.target,a.target_score,a.target_update_tick = -1,0,0 if historical else 20
            _rearm(a,E.AUTOGUN,10)
            return
        best = targets[max(targets)]
        if a.target > -1 and a.target_score > 0:
            threshold = int(((100.0+a.target_threshold)/100.0)*a.target_score)
            if best.target_dbref != a.target and best.target_score > threshold:
                a.target,a.target_score = best.target_dbref,best.target_score
        else:
            a.target,a.target_score = best.target_dbref,best.target_score
    else:
        a.target_update_tick += 1
    target = resolve_unit(mech,a.target)
    if target is None:
        a.target,a.target_score = -1,0
        _rearm(a,E.AUTOGUN,1)
        return
    if mech.target != a.target:
        from systems.targeting import lock_command
        from systems.parts import mech_ids
        lock_command(a._engine,mech,mech_ids(target,True),caller=a)
    if not historical and not mech_to_mech_los_flag(board,mech,target) & MECHLOSFLAG_SEEN:
        a.target,a.target_update_tick = -1,25
        return
    _physical(a,target,board)
    target = resolve_unit(mech,a.target)
    if target is None or target.is_destroyed or target.mapindex != mech.mapindex:
        a.target,a.target_score = -1,0
        _rearm(a,E.AUTOGUN,1)
        return
    distance = find_range(mech.fx,mech.fy,target.fx,target.fy)
    if distance >= 30 and not a.flags & 256:
        a.target,a.target_score = -1,0
        _rearm(a,E.AUTOGUN,1)
        return
    if distance < 30 and a.profile[int(distance)]:
        from systems.combat import fire_weapon_number
        from systems.parts import weapon_is_recycling
        from physics.cargo import cargo_max_speed
        accumulated = int(mech.weap_heat)
        if mech.unit_type == U.MECH and abs(mech.speed) > 0:
            accumulated += 2 if is_running(mech.desired_speed,cargo_max_speed(mech)) else 1
        for score,node in sorted(a.profile[int(distance)].items(),reverse=True):
            weapon = get_weapon_by_index(node.weapon_db_number)
            slot = mech.sections[node.section].criticals[node.critical]
            if weapon_is_nonfunctional(mech,node.section,node.critical) > 0 or weapon_is_recycling(mech,node.section,node.critical) or weapon.special & WeaponFlags.AMS:
                continue
            if not historical and slot.ammomode & 0x20000 and not (target.is_jumping or target.cocoon or _flying(target) and not target.status & S.LANDED):
                continue
            if mech.unit_type == U.MECH and accumulated+weapon.heat-mech.minus_heat > 6:
                continue
            if not _weapon_arc(a,target,node):
                continue
            fire_weapon_number(a._engine,mech,node.weapon_number,caller=a)
            if weapon_is_recycling(mech,node.section,node.critical):
                accumulated += weapon.heat
    if _chase(a,target,board):
        return
    _rearm(a,E.AUTOGUN,1)

