# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.combat.c
#   btech/mech.notify.c
#   btech/mech.scan.c
# Historical Aerospace sources:
#   btech/ds.turret.c

"""Command-level firing guards and the three C target-selection branches."""
from entities.mech import MechStatus as S,MechStatus2 as S2,CritStatus,UnitType as U,MoveType as M,Location as L,VehicleLocation as V,FireMode as F
from entities.weapon import get_weapon_by_index,WeaponFlags as W,WeaponType as T
from core.events import EventType as E
from systems.combat_commands import command_guard
from systems.movement_commands import notify,mode_locked


def firing_feedback(unit,target,weapon,result,sight,ishex,x,y,is_artillery,los=None):
    """FireWeapon's crew emits, while any turret audience override is active."""
    from systems.notifications import mech_notify,MECHALL,MECHPILOT,identity
    from systems.targeting import _aim_section_name
    from systems.combat import hex_target_id
    from systems.los import in_line_of_sight_nb
    from entities.mech import NUM_SECTIONS
    name=weapon.name[3:]
    audience=MECHALL
    bth=result.bth
    if los is None:
        los = in_line_of_sight_nb(unit,target,x,y,0)
    roll=f'Roll: {result.roll} ' if los else ''
    if target is not None and not ishex:
        label=identity(unit,target)
        if unit.aim!=NUM_SECTIONS and unit.aim_type==target.unit_type and weapon.weapon_type!=T.TMISSILE:
            label+="'s "+_aim_section_name(target,unit.aim)
        cover='(Partial cover)' if target.status&S.PARTIAL_COVER else ''
        prefix=f'You aim {name}' if sight else f'Fire {name}' if bth>12 else f'You fire {name}'
        text=f'{prefix} at {label} - '
        if bth>=900:text+='Out of range.'
        elif sight:text+=f'BTH: {bth} {cover}'
        else:text+=f'BTH: {bth}  '+('Roll: Impossible! ' if bth>12 else roll)+cover
    elif sight:
        audience=MECHPILOT
        text=f'You aim your {name} at ({x},{y}) - '+('Out of Range.' if bth>900 else f'BTH: {bth}')
    elif not is_artillery and bth>12:
        text=f'Fire {name} at ({x},{y}) - BTH: {bth}  Roll: Impossible!'
    else:
        text=f'You fire {name} {hex_target_id(unit)} ({x},{y}) - BTH: {bth}  {roll}'
    mech_notify(unit,audience,text)
    return text


def swarm_id(unit):
    value=getattr(unit,'swarming',-1)
    if value>0:return value
    target=getattr(unit,'swarm_target',None)
    return getattr(target,'_id',target if isinstance(target,int) else -1)


def begin_shot(unit):
    """FireWeapon side effects after all failure gates and before impact."""
    from physics.collision import mech_elevation
    if unit.cocoon and unit.z>mech_elevation(unit):
        if unit.jump_speed>=10.75:
            notify(unit,'You initiate your jumpjets to compensate for the opened cocoon!')
            unit.cocoon=-1
        else:
            from physics.orbital import fall_event
            from systems.sensors import los_broadcast
            notify(unit,'Your action splits open the cocoon - have a nice fall!')
            los_broadcast(unit,'starts plummeting down, as the cocoon opens!.')
            unit.cocoon=0
            unit._engine.events.cancel_by_type_and_data(E.OOD,unit)
            unit._engine.events.schedule(3,E.FALL,fall_event,unit,-1)


def mount_guard(unit,number,sight,historical=None):
    from systems.combat import part_is_nonfunctional
    historical=unit.unit_type in (U.AERO,U.DS,U.SPHEROID_DS) if historical is None else historical
    from systems.physical import sect_has_busy_weap
    from systems.enhanced_crits import part_temp_nuke,FAIL_DESTROYED
    from systems.weapon_inventory import sync_weapon_states
    sync_weapon_states(unit)
    if number<0 or number>=len(unit.weapons):return "The weapons system chirps: 'Illegal Weapon Number!'"
    ws=unit.weapons[number]
    loc=ws.section
    sec=unit.sections[loc]
    slot=sec.criticals[ws.critical]
    weapon=get_weapon_by_index(ws.weapon_idx)
    from systems.weapon_modes import find_weapon_number_on_mech
    code, _, _ = find_weapon_number_on_mech(unit,number,sight)
    if not sight:
        if unit.crit_status&CritStatus.MECH_STUNNED:return 'You cannot take actions while stunned! That include finding the trigger.' if historical else 'You cannot take actions while stunned! That includes finding the trigger.'
        if part_temp_nuke(slot):return "The weapons system chirps: 'That Weapon is still unusable - please stand by.'" if historical else "The weapons system chirps: 'That weapon is still unusable - please stand by.'"
        if code in (-3,-4):return ("The weapon system chirps: 'That weapon is still " if historical else "The weapons system chirps: 'That weapon is still ") + ('recharging' if code == -4 else 'reloading') + "!'"
        if code == -5:
            from systems.parts import armor_string
            return ('Your ' if unit.unit_type != U.BSUIT else '') + armor_string(unit,loc) + ' is still recovering from a previous action!'
        if sec.specials&0x20:return "You're carrying a club in that arm."
        if unit.is_fallen and unit.unit_type==U.MECH:
            legs=[L.RLEG,L.LLEG]+([L.LARM,L.RARM] if unit.move_type==M.QUAD else [])
            dead=sum(unit.is_section_destroyed(i) for i in legs)
            if unit.move_type==M.QUAD and dead>2:return 'Quads need at least 3 legs to fire while prone.'
            if unit.move_type!=M.QUAD or dead:
                if loc in (L.RLEG,L.LLEG):return 'You cannot fire leg mounted weapons when prone.'
                def unavailable(i):return sect_has_busy_weap(unit,i) or unit.sections[i].recycle or unit.is_section_destroyed(i)
                if loc==L.RARM and unavailable(L.LARM):return "You currently can't use your Left Arm to prop yourself up."
                if loc==L.LARM and unavailable(L.RARM):return "Your currently can't use your Right Arm to prop yourself up."
                if loc not in (L.LARM,L.RARM) and unavailable(L.RARM) and unavailable(L.LARM):return "You currently don't have any arms to spare to prop yourself up."
    from systems.swarm import is_mounted
    mounted=is_mounted(unit) if historical else bool(unit.status2&S2.UNIT_MOUNTED)
    if mounted and loc in (L.CTORSO,L.RTORSO,L.LTORSO):
        return ('You can not fire torso mounted weapons while you have battlesuits on you!' if historical
                else 'You cannot fire torso-mounted weapons while you have battlesuits on you!')
    if (unit.dug_in or getattr(unit,'tank_crit_status',0)&4) and loc!=V.TURRET:return 'Only turret weapons are available while in cover.'
    if code == -2 or part_temp_nuke(slot)==FAIL_DESTROYED:
        return "The weapons system chirps: 'That Weapon has been destroyed!'" if historical else "The weapons system chirps: 'That weapon has been destroyed!'"
    if weapon.special&W.AMS:return 'That weapon is defensive only!'


def target_guard(engine,unit,target,weapon):
    from systems.targeting import locking
    from entities.map import MAPFLAG_NOFRIENDLYFIRE
    if target is None:return None
    if weapon.weapon_type==T.TARTILLERY:return 'You can only target hexes with this kind of artillery.'
    if swarm_id(target)==unit._id:return "You are unable to use your weapons against a 'swarmer!"
    if target.status2&S2.STH_ARMOR_ON and (unit.target!=target._id or locking(engine,unit)):
        return 'You need a stable lock to fire on that target!'
    if 'Coolant' not in weapon.name and target.team==unit.team:
        if unit.prefs&128:return "You can't fire on a teammate with FFSafeties on!"
        if unit.map.flags&MAPFLAG_NOFRIENDLYFIRE:return "Friendly Fire? I don't think so..."
    if target.unit_type==U.MW and unit.unit_type!=U.MW and not unit.prefs&1:
        return "That's a living, breathing person! Switch off the safety first, if you really want to assassinate the target."


def fire_number(engine,unit,number,target=None,**kwargs):
    from systems.combat import AttackResult,fire_weapon,is_in_weapon_arc,find_target_xy,mech_lock_fire,HEX_LOCK_MODES,TARGCOMP_MULTI,UNSTABLE_LOCK_HIPSHOT
    from systems.targeting import find_mech_in_hex,locking,find_range
    from systems.los import in_line_of_sight_nb
    from physics.hexmath import hex_to_float,ZSCALE,in_weapon_arc
    from entities.map import MAPFLAG_UNDERGROUND
    from systems.tic import _atoi
    sight=kwargs.get('sight',False)
    historical=kwargs.pop('historical',unit.unit_type in (U.AERO,U.DS,U.SPHEROID_DS))
    raw_args = kwargs.pop('raw_args',None)
    caller = kwargs.pop('caller',None)
    caller = unit.pilot if caller is None else caller
    wizard = kwargs.pop('wizard',False)
    guarded = kwargs.pop('_guarded',False)
    def fail(message,accepted=False):
        from core.effects import notify_actor
        if not getattr(message,'notified',False):notify_actor(unit,caller,message)
        return AttackResult(messages=[message],command_accepted=accepted)
    if not guarded:
        from systems.communications import common_checks,MECH_USUAL
        error=common_checks(unit,caller,MECH_USUAL) if sight else command_guard(unit,caller=caller,wizard=wizard)
        if error is not None:return fail(error)
        if not historical and not sight and unit.status2&S2.WEAPONS_HOLD:return fail('Currently in weapons hold. Unable to fire weapons.')
    if unit.unit_type==U.BSUIT:
        for i,sec in enumerate(unit.sections):
            if not unit.is_section_destroyed(i) and sec.recycle:return fail(f'Suit {i+1} is still recovering from attack.',True)
    if not sight:
        if unit.crit_status&CritStatus.HIDDEN:
            notify(unit,'You break out of your cover to initiate weapons fire!')
            from systems.sensors import los_broadcast
            los_broadcast(unit,'breaks out of its cover and begins firing rabidly!')
            unit.clear_crit_status(CritStatus.HIDDEN)
        engine.events.cancel_by_type_and_data(E.HIDE,unit)
    if mode_locked(unit):return fail('You cannot fire while using a special movement mode.')
    if unit.spotter>0 and unit.spotter==unit._id:return fail('You cannot fire while spotting.')
    error=mount_guard(unit,number,sight,historical)
    if error:return fail(error)
    if raw_args is not None and len(raw_args)>3:return fail('Invalid number of arguments!')
    ws=unit.weapons[number]
    slot=unit.sections[ws.section].criticals[ws.critical]
    weapon=get_weapon_by_index(ws.weapon_idx)
    is_idf=bool(weapon.special&W.IDF)
    is_arty=weapon.weapon_type==T.TARTILLERY
    if (is_idf and unit.spotter!=-1 and unit.target==-1
            and (not historical or unit.targ_x==unit.targ_y==-1)):
        from systems.spot import fire_spot
        result = fire_spot(engine,unit,number,**kwargs)
        if not historical or result.handled:
            result.command_accepted = True
            return result
    if not historical and unit.spotter!=-1 and not is_idf:return fail("The weapon system chirps: 'Somone is spotting for you. Remove your spotter to fire non-IDF weapons'")
    if raw_args is not None:
        if len(raw_args)==2:
            from systems.targeting import contact_target
            target=contact_target(unit,str(raw_args[1])[:2])
            if target is None:return fail('That target is not in your line of sight!')
        elif len(raw_args)==3:target=tuple(raw_args[1:3])
        else:target=None
    board=unit.map
    default=target is None
    explicit_hex=isinstance(target,(tuple,list))
    ishex=explicit_hex or default and unit.target==-1
    temp=None
    self_coolant=default and 'Coolant' in weapon.name and slot.firemode&F.HEAT_MODE
    los=1
    if self_coolant:
        temp=unit
        x,y=unit.x,unit.y
        distance=.2
        ishex=False
    else:
        if explicit_hex:
            if len(target)!=2:return fail('Invalid number of arguments!')
            x,y=map(_atoi,target)
            if not board.valid(x,y):return fail('Map coordinates out of range!')
        elif default:
            if find_target_xy(unit) is None:return fail('You do not have a default target set!')
            x,y=unit.targ_x,unit.targ_y
            if unit.target!=-1:
                temp=next((m for m in board.mechs_on_map if m is not None and m._id==unit.target),None)
                if temp is None:return fail('Error in FireWeaponNumber routine')
                x,y=temp.x,temp.y
        else:
            temp=target
            if temp not in board.mechs_on_map:return fail('That target is not in your line of sight!')
            x,y=temp.x,temp.y
        if ishex and not sight and not is_arty and (explicit_hex or mech_lock_fire(unit)):
            temp=find_mech_in_hex(unit,board,unit.targ_x,unit.targ_y,0)
            if temp is not None and not explicit_hex:x,y=temp.x,temp.y
        if temp is None:
            ex,ey=hex_to_float(x,y)
            unit.targ_z=board.base_elevation(x,y)
            ez=unit.targ_z*ZSCALE
        else:ex,ey,ez=temp.fx,temp.fy,temp.fz
        distance=find_range(unit.fx,unit.fy,unit.fz,ex,ey,ez)
        def arc_error():
            if unit.unit_type == U.BSUIT:return None
            unavailable = getattr(unit,'unusable_arcs',0)
            override = getattr(engine,'arc_override',0)
            arc = in_weapon_arc(unit,ex,ey)
            if unavailable and (unavailable&arc if not override else not override&arc):return "That arc's weapons aren't under your control!"
            if not is_in_weapon_arc(unit,ex,ey,ws.section,ws.critical):
                return 'Default target is not in your weapons arc!' if default else 'That hex target is not in your weapons arc!' if explicit_hex else 'That target is not in your weapons arc!'
        if explicit_hex:
            error=arc_error()
            if error:return fail(error)
        los=in_line_of_sight_nb(unit,temp,x,y,distance)
        if default:
            label='That hex target' if ishex else 'That target'
            underground='That target is not in your direct line of sight, and you cannot fire your IDF weapons underground!'
            if not ishex and (is_idf or is_arty) and board.flags&MAPFLAG_UNDERGROUND and not los:return fail(underground)
            if is_idf and unit.spotter==-1 and getattr(engine,'idf_requires_spotter',True) and not los:
                return fail(label+' is not in your direct line of sight and you do not have a spotter set!!')
            if not (is_idf or ishex and is_arty) and not los:return fail(label+' is not in your line of sight!')
            if ishex and (is_idf or is_arty) and board.flags&MAPFLAG_UNDERGROUND and not los:return fail(underground)
        elif not (explicit_hex and is_arty) and not los:
            return fail('That hex target is not in your line of sight!' if explicit_hex else 'That target is not in your line of sight!')
        if not explicit_hex:
            error=arc_error()
            if error:return fail(error)
    error=target_guard(engine,unit,temp,weapon)
    if error:return fail(error)
    unstable=unstable_arc(engine,unit,temp)
    kwargs.setdefault('engine',engine)
    kwargs.setdefault('los',los)
    result = fire_weapon(unit,temp,number,distance,unstable_lock_arc=unstable,
        hex_lock_modes=int(unit.status&HEX_LOCK_MODES),mapx=x,mapy=y,ishex=int(ishex),**kwargs)
    result.command_accepted = True
    return result


def announce_shot(unit,target,weapon,x,y,is_hit,artillery=False,ishex=False):
    """MechFireBroadcast visibility cases and the target's incoming-fire warning."""
    from systems.los import in_line_of_sight
    from systems.notifications import identity, mech_notify, MECHSTARTED, MECHALL
    from systems.targeting import fa_mech_range,find_range
    from systems.sensors import possibly_see_mech
    from physics.hexmath import hex_to_float,find_bearing,ZSCALE
    board=unit.map
    label=weapon.name[3:]
    def sees(viewer,other):
        return in_line_of_sight(viewer,other,other.x,other.y,fa_mech_range(viewer,other))
    if not artillery and board:
        recipient=target
        if ishex:target=None
        if target:
            field='shots_hit' if is_hit else 'shots_missed'
            setattr(unit,field,getattr(unit,field,0)+1)
        possibly_see_mech(unit)
        if target:possibly_see_mech(target)
        for viewer in board.mechs_on_map:
            if viewer is None or viewer is unit or viewer is target or not viewer.is_started:continue
            attack_seen=sees(viewer,unit)
            if target:
                defend_seen=sees(viewer,target)
                destination=identity(viewer,target) if defend_seen else 'something'
            else:
                fx,fy=hex_to_float(x,y)
                distance=find_range(viewer.fx,viewer.fy,viewer.fz,fx,fy,ZSCALE*board.base_elevation(x,y))
                defend_seen=in_line_of_sight(viewer,None,x,y,distance)
                destination=f'hex {x} {y}!'
            if not attack_seen and not defend_seen:continue
            source=identity(viewer,unit) if attack_seen else 'Something'
            if target and defend_seen:text=f'{source} {"hits" if is_hit else "misses"} {destination} with a {label}'
            else:text=f'{source} fires a {label} at {destination if defend_seen else "something!"}'
            mech_notify(viewer,MECHSTARTED,text)
        target=recipient
    if target:
        if sees(target,unit):text=f'{identity(target,unit)} has fired a {label} at you!'
        else:text=f'Something has fired a {label} at you from bearing {int(find_bearing(target.fx,target.fy,unit.fx,unit.fy))}!'
        mech_notify(target,MECHALL,text)


def fire_command(engine,unit,args,*,sight=False,caller=None,wizard=False,historical=None):
    from systems.combat import AttackResult
    if unit is None:
        return AttackResult()
    from core.effects import notify_actor
    from systems.tic import _atoi
    caller = unit.pilot if caller is None else caller
    historical=unit.unit_type in (U.AERO,U.DS,U.SPHEROID_DS) if historical is None else historical
    from systems.communications import common_checks,MECH_USUAL,MECH_USUALO
    error = common_checks(unit,caller,MECH_USUAL if sight else MECH_USUALO) if historical or sight else command_guard(unit,caller=caller,wizard=wizard)
    if not historical and error is None and not sight and unit.status2&S2.WEAPONS_HOLD:error='Currently in weapons hold. Unable to fire weapons.'
    if error is None and not args:error='Not enough arguments to the function'
    if error is not None:
        if not getattr(error,'notified',False):notify_actor(unit,caller,error)
        return AttackResult(messages=[error])
    return fire_number(engine,unit,_atoi(args[0]),raw_args=tuple(args),sight=sight,caller=caller,wizard=wizard,_guarded=True,historical=historical)


def unstable_arc(engine,unit,target):
    """FindNormalBTH's live lock input, also used for redirected host shots."""
    from systems.targeting import locking
    from systems.combat import find_target_xy,UNSTABLE_LOCK_HIPSHOT,TARGCOMP_MULTI
    from physics.hexmath import in_weapon_arc
    if not getattr(engine,'arc_override',0) and target is not None and (target._id!=unit.target or engine is not None and locking(engine,unit) and unit.targcomp!=TARGCOMP_MULTI):
        xyz=find_target_xy(unit)
        return int(in_weapon_arc(unit,xyz[0],xyz[1])) if xyz else UNSTABLE_LOCK_HIPSHOT
    return None


def record_attack_channels(unit,target,result,x,y,ishex):
    """Ordered SendAttacks/SendAttackEmits requests and configured local delivery."""
    from core.effects import emit_channel
    from systems.combat import short_hextarget
    if target is not None and not ishex:
        text=f'#{unit._id} attacks #{target._id} (weapon) ({result.bth}/{result.roll})'
        flagged=[target] if target.status2&S2.ATTACKEMIT_MECH else []
    else:
        text=f'#{unit._id} attacks {x},{y} ({short_hextarget(unit)}) (weapon) ({result.bth}/{result.roll})'
        # The source excludes only units whose BOTH coordinates differ.
        flagged=[other for other in unit.map.mechs_on_map if other is not None and other is not unit
                 and (other.x==x or other.y==y) and other.status2&S2.ATTACKEMIT_MECH] if unit.map else []
    emit_channel(unit,'MechAttacks',text)
    for other in flagged:
        request=emit_channel(unit,'MechAttackEmits',text)
        request['target']=other._id
