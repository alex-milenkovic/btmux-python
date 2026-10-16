# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.pickup.c

"""Non-personnel towing; carrying/towed_unit are the engine's shared relation."""
from core.events import EventType as E
from entities.mech import UnitType as U,MoveType as M,MechStatus as S,Specials,Location as L
from systems.combat_commands import command_guard
from data.templates import parse_attributes
from systems.occupants import _target,_failure
from systems.combat import part_is_nonfunctional
from systems.damage import release_tow,external_effect
from systems.vehicle_combat import correct_speed
from systems.startup import shutdown_state
from systems.swarm import mirror


def _notice(unit,text,broadcast=None):
    from systems.notifications import mech_notify,MECHALL
    from systems.sensors import los_broadcast
    mech_notify(unit,MECHALL,text)
    if broadcast:los_broadcast(unit,broadcast)


def god(actor):return actor==1 or getattr(actor,'_id',None)==1 or getattr(actor,'god',False)


def stop_target(target):
    engine=target._engine
    if engine.has_event(E.MOVE,target) and not engine.has_event(E.FALL,target) and not target.cocoon:engine.cancel_events_of_type(E.MOVE,target)
    return not engine.has_event(E.MOVE,target)


def attach_relation(tower,target):
    tower.carrying=target._id;tower.towed_unit=target;target.swarm_target=-1
    from entities.mech import CritStatus
    tower.crit_status=int(tower.crit_status)&~int(CritStatus.LOAD_OK)
    if target.unit_type==U.MECH:
        target.status|=S.FALLEN;target.status=int(target.status)&~int(S.TORSO_LEFT|S.TORSO_RIGHT)
        target._engine.cancel_events_of_type(E.STAND,target);target._stand_event=None
    target.status|=S.TOWED;target.status=int(target.status)&~int(S.HULLDOWN);target.tank_crit_status=getattr(target,'tank_crit_status',0)&~4


def pickup_unit(unit,actor,target):
    """Called after the existing pickup's contact and general guard sequence."""
    if unit.unit_type==U.MECH:
        if unit.move_type==M.QUAD:return _failure(actor,"You've got four left feet, you can't tow!",unit)
        if unit.is_section_destroyed(L.LARM):return _failure(actor,"Your left arm is destroyed, you can't pick up anything.",unit)
        if unit.is_section_destroyed(L.RARM):return _failure(actor,"Your right arm is destroyed, you can't pick up anything.",unit)
        from entities.crittypes import i2special,Special
        def arm_ok(loc):
            return all(unit.sections[loc].criticals[pos].type==i2special(kind) and not part_is_nonfunctional(unit,loc,pos)
                for pos,kind in ((0,Special.SHOULDER_OR_HIP),(3,Special.HAND_OR_FOOT_ACTUATOR)))
        if not any(arm_ok(loc) for loc in (L.LARM,L.RARM)):return _failure(actor,'You need functioning arm to pick things up!',unit)
    elif not unit.specials&Specials.SALVAGE_TECH:return _failure(actor,'This unit requires salvage equipment.')
    if unit.carrying>0:return _failure(actor,'You are already carrying a Mech')
    if abs(unit.speed)>1 or abs(unit.vertical_speed)>1:return _failure(actor,'You are moving too fast to attempt a pickup.')
    if target.unit_type in (U.DS,U.SPHEROID_DS) or target.move_type==M.NONE:return _failure(actor,'That target cannot be towed.')
    if unit.team!=target.team and (target.is_started or not target.is_destroyed and target.team!=0):return _failure(actor,'You cannot pick up that enemy unit.')
    if not stop_target(target):return _failure(actor,'You cannot pick up a moving target!')
    _notice(target,f'{unit.name} attaches his tow lines to you.')
    _notice(unit,f'You attach your tow lines to {target.name}.')
    if target.carrying>0:release_with_debug(target)
    from systems.sensors import los_broadcast
    los_broadcast(unit,f'picks up {target.name}!')
    attach_relation(unit,target)
    from entities.map import ICE
    through_ice=target.terrain==ICE and unit.z>=0 and target.z<0
    mirror(unit,target,height=0)
    if through_ice:
        from physics.movement import drop_thru_ice,break_thru_ice
        (drop_thru_ice if unit.z==0 and unit.move_type!=M.HOVER else break_thru_ice)(unit)
    if not target.is_destroyed:shutdown_state(target._engine,target)
    correct_speed(unit);external_effect(unit,'MUX debug',f'#{unit._id} has picked up #{target._id}')
    return dict(ok=True,target=target._id,message='Tow lines attached.')


def attach_cables(unit,actor,argument):
    if not god(actor):
        error=command_guard(unit,caller=actor,pilot_only=False,wizard=getattr(actor,'wizard',False))
        if error:return _failure(actor,error)
    args=parse_attributes(argument,2)
    if len(args)!=2:return _failure(actor,'Invalid number of arguments.')
    if unit.cocoon:return _failure(actor,'You cannot attach cables while OODing.')
    tower=_target(unit,args[0])
    if tower is None:return _failure(actor,'Towing unit is not in line of sight.')
    if (unit.x,unit.y)!=(tower.x,tower.y):return _failure(actor,'You need the same hex as the towing unit.')
    if tower.is_jumping:return _failure(actor,'That towing unit is currently flying through the air!')
    if unit.z!=tower.z:return _failure(actor,'You must be on the same elevation as the towing unit!')
    if tower.carrying>0:return _failure(actor,'That towing unit is towing someone else!')
    if tower.has_status(S.TOWED):return _failure(actor,'That towing unit is already being towed by someone!')
    if tower.unit_type==U.MW or tower.move_type==M.NONE or tower.tonnage<5:return _failure(actor,'That unit can not tow!')
    if tower.is_destroyed:return _failure(actor,'Destroyed units can not tow!')
    if not tower.in_character:return _failure(actor,'That unit can not tow!')
    if getattr(tower,'burn_recovery_countdown',0):return _failure(actor,'Cannot attach cables to a burning unit.')
    if tower.specials&Specials.SALVAGE_TECH:return _failure(actor,'Dedicated salvage unit must pick up the load itself.')
    if tower.speed or tower.vertical_speed:return _failure(actor,'Towing unit is moving too fast.')
    if tower.team!=unit.team:return _failure(actor,'You cannot grab cables from that team.')
    if tower.unit_type not in (U.MECH,U.VEH_GROUND):return _failure(actor,'That unit can not tow!')
    target=_target(unit,args[1])
    if target is None:return _failure(actor,'Target is not in line of sight.')
    if (unit.x,unit.y)!=(target.x,target.y):return _failure(actor,'You need the same hex as the target.')
    if target.is_jumping:return _failure(actor,'That target is currently flying through the air!')
    if unit.z!=target.z:return _failure(actor,'You must be on the same elevation as the target!')
    if target.carrying>0:return _failure(actor,'That target is towing someone else!')
    if target.has_status(S.TOWED):return _failure(actor,'That target is already being towed by someone!')
    if not target.in_character and not getattr(target,'towable',False):return _failure(actor,'Target is not towable.')
    if target.unit_type in (U.MW,U.DS,U.SPHEROID_DS) or target.move_type==M.NONE:return _failure(actor,'Target cannot be towed.')
    if getattr(target,'burn_recovery_countdown',0):return _failure(actor,'Cannot attach cables to a burning target.')
    if target.speed or target.vertical_speed:return _failure(actor,'Target is moving too fast.')
    if target.team!=unit.team and target.is_started:return _failure(actor,'Cannot tow a started enemy.')
    if not stop_target(target):return _failure(actor,'Target is still moving.')
    _notice(target,f'{unit.name} attaches tow lines from {tower.name} to you.')
    _notice(tower,f'{unit.name} attaches your tow lines to {target.name}.')
    _notice(unit,f"You attach {tower.name}'s tow lines to {target.name}.",f'attaches tow cables from {tower.name} to {target.name}!')
    attach_relation(tower,target)
    if not target.is_destroyed:shutdown_state(target._engine,target)
    correct_speed(tower);return dict(ok=True,target=target._id,tower=tower._id)


def detach_cables(unit,actor,argument):
    error=command_guard(unit,caller=actor,pilot_only=False,wizard=getattr(actor,'wizard',False))
    if error:return _failure(actor,error)
    args=parse_attributes(argument,1)
    if not args:return _failure(actor,'Invalid number of arguments.')
    tower=_target(unit,args[0])
    if tower is None:return _failure(actor,'Towing unit is not in line of sight.')
    if (unit.x,unit.y)!=(tower.x,tower.y):return _failure(actor,'You need the same hex as the towing unit.')
    if unit.z!=tower.z:return _failure(actor,'You need the same elevation as the towing unit.')
    if tower.carrying<=0:return _failure(actor,'That unit is not towing anyone!')
    target=getattr(tower,'towed_unit',None) or next((u for u in tower.map.mechs_on_map if u and u._id==tower.carrying),None)
    tower.carrying=-1;tower.towed_unit=None
    from entities.mech import CritStatus
    tower.crit_status=int(tower.crit_status)&~int(CritStatus.LOAD_OK)
    if target is None:return _failure(actor,'The towed unit was invalid!')
    target.status=int(target.status)&~int(S.TOWED);target._engine.cancel_events_of_type(E.MOVE,target)
    target.speed=target.desired_speed=0
    _notice(unit,f"You detach {tower.name}'s tow lines from {target.name}.",f"detaches {tower.name}'s tow cables from {target.name}!")
    _notice(tower,f'{unit.name} detaches your tow lines from {target.name}.');_notice(target,'You have been released from towing.')
    if target.map:target.z=target.map.base_elevation(tower.x,tower.y)
    correct_speed(tower);return dict(ok=True,target=target._id)


def release_with_debug(unit):
    return release_tow(unit)


def dropoff(unit,actor,argument=''):
    if not god(actor):
        error=command_guard(unit,caller=actor,pilot_only=False,wizard=getattr(actor,'wizard',False))
        if error:return _failure(actor,error)
    if unit.carrying<=0:return _failure(actor,'You are not carrying a mech!')
    target=unit.carrying
    if not release_with_debug(unit):return _failure(actor,'You were towing invalid target!')
    return dict(ok=True,target=target)


def follow_tower(unit):
    from systems.targeting import resolve_unit
    if unit.carrying <= 0:
        return
    target = resolve_unit(unit, unit.carrying)
    if target is not None and target.mapindex == unit.mapindex:
        mirror(unit, target, height=0)
        target.facing = unit.facing
        target.facing_fraction = unit.facing_fraction
