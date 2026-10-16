# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/bsuit.c
#   btech/mech.pickup.c
#   btech/mech.startup.c
# Historical Aerospace sources:
#   btech/bsuit.c

"""Battle armor actions, attachment, hiding and packs from bsuit.c."""
import random
from entities.mech import MechStatus2 as S2
from systems.notifications import identity, personal_notify


def swarmers(host):
    if host.map is None:
        return []
    return [unit for unit in host.map.mechs_on_map
            if unit is not None and unit is not host and getattr(unit,'_id',0)>0 and (getattr(unit, 'swarm_target', None) is host or
                                    getattr(unit, 'swarm_target', None) == host._id)]


def detach(unit, intentional=False, host=None, *, historical=False):
    from systems.movement_commands import notify, maybe_move
    from systems.piloting import make_piloting_roll
    from systems.combat import apply_damage_with_transfer
    from physics.movement import drop_set_elevation
    from physics.flooding import flood_unit
    target = unit.swarm_target
    if isinstance(target,int) and target<=0:return
    if target is not None and host is not None:target=host
    if isinstance(target, int):
        from systems.targeting import resolve_unit
        target = resolve_unit(unit,target)
    if target is None:
        return
    unit.swarm_target = -1
    target.swarmer = -1  # Cache only; swarm_target is the source relationship.
    if not historical:
        unit.clear_status2(S2.UNIT_MOUNTING)
        target.clear_status2(S2.UNIT_MOUNTED)
    if intentional:
        delay = 20
        notify(unit,"You let your hold loosen and you drop from the 'mech!")
        notify(target,f'{identity(target,unit)} lets go of you!')
        _broadcast(unit,target,'lets go of {}!')
    elif make_piloting_roll(unit, 4).success:
        delay = 30
        notify(unit,"The hold loosens and you drop from the 'mech!")
        _broadcast(unit,target,'jumps off of {}!')
        notify(target,f'{identity(target,unit)} jumps off!')
    else:
        delay = 45
        notify(unit,"You're suprised by the sudden action and find yourself rapidly approaching the ground!")
        _broadcast(unit,target,'falls off {}!')
        notify(target,f'{identity(target,unit)} falls off!')
        from core.randomness import draw
        apply_damage_with_transfer(unit, draw('suit_fall_location', 0, 7, lambda: random.randint(0, 7)), 11,
                                   attacker=unit, ignore_swarmers=True, los=1, attack_pilot=-1)
    start_recycle(unit,delay)
    unit.speed = 0
    if unit._engine is not None:
        maybe_move(unit._engine, unit)
    drop_set_elevation(unit, 0)
    flood_unit(unit)


def _broadcast(unit,target,text):
    from systems.physical import _physical_broadcast
    _physical_broadcast(unit,target,text)


def detach_all(host, intentional=False, *, historical=False):
    for suit in swarmers(host):
        detach(suit,intentional,host,historical=historical)


def members(unit):return sum(section.internal!=0 for section in unit.sections)


def suit_name(unit,lower=False):
    from entities.mech import Specials
    name='Point' if unit.specials&Specials.CLAN_TECH else 'Squad'
    return name.lower() if lower else name


def start_recycle(unit,delay):
    if not any(section.internal for section in unit.sections):return
    if unit._engine is not None:
        from core.game_loop import update_recycling
        update_recycling(unit._engine,unit)
    for section in unit.sections:
        if section.internal:section.recycle=delay


def is_swarmed(unit):return any(suit.team!=unit.team for suit in swarmers(unit))
def is_mounted(unit):return any(suit.team==unit.team for suit in swarmers(unit))
def count_swarmers(unit):return len(swarmers(unit))
def first_swarmer(unit):return next(iter(swarmers(unit)),None)


def mirror(host,suit,height=1):
    from physics.hexmath import ZSCALE
    from systems.ecm import mark_for_los_update
    from physics.flooding import flood_unit
    for name in ('fx','fy','x','y','last_x','last_y','terrain'):setattr(suit,name,getattr(host,name))
    suit.z=host.z+height;suit.elev=host.elev+height;suit.fz=host.fz+height*ZSCALE
    mark_for_los_update(suit);flood_unit(suit)


def mirror_all(host):
    for suit in swarmers(host):mirror(host,suit)


def common_checks(unit):
    from systems.movement_commands import mode_locked
    from systems.physical import sect_has_busy_weap
    from systems.combat_firing import swarm_id
    if unit.is_jumping:return 'Unavailable when jumping - sorry.'
    if swarm_id(unit)>0:return 'You are already busy with a special attack!'
    if mode_locked(unit):return 'Unavailable when performing movement modes - deal.'
    for i,section in enumerate(unit.sections):
        if not unit.is_section_destroyed(i) and section.recycle:return f'Suit {i+1} is still recovering from attack.'
        if sect_has_busy_weap(unit,i):return 'You have weapons recycling!'


def find_target(unit,argument):
    from systems.targeting import contact_target,fa_mech_range
    from systems.los import in_line_of_sight_nb
    from entities.mech import UnitType
    if isinstance(argument,str):
        args=argument.split()
        if len(args)>1:return None,'Invalid arguments!'
        if not args:
            if unit.target<=0:return None,'You do not have a default target set!'
            from systems.targeting import resolve_unit
            target=resolve_unit(unit,unit.target)
            if target is None:
                from systems.combat_commands import NotifiedError
                from systems.movement_commands import notify
                error=NotifiedError('Invalid default target!')
                notify(unit,error)
                unit.target=-1
                return None,error
        else:target=contact_target(unit,args[0])
    else:target=contact_target(unit,argument)
    if target is None or target._id<=0:return None,'Target is not in line of sight!'
    distance=fa_mech_range(unit,target)
    if not in_line_of_sight_nb(unit,target,target.x,target.y,distance):return None,'Target is not in line of sight!'
    if distance>=1:return None,'Target out of range!'
    if target.is_jumping:return None,"That target's unreachable right now!"
    if target.unit_type!=UnitType.MECH:return None,'That target is of invalid type.'
    if target.is_destroyed:return None,"A dead 'mech? C'mon :P"
    return target,None


def pending_packs(unit):
    from entities.mech import FireMode as F
    return [(i,j,slot) for i,section in enumerate(unit.sections) for j,slot in enumerate(section.criticals)
            if slot.firemode&F.WILL_JETTISON_MODE and not slot.firemode&F.IS_JETTISONED_MODE]


def jettison_checks(unit):
    pending=pending_packs(unit)
    if unit.infantry_specials&0x100 and pending:return f'Suit {pending[0][0]+1} can not perform this feat before it jettisons its backpack!'


def modifier(unit,target,leg=False):
    from entities.mech import CritStatus
    from systems.combat import is_target_immobile,calculate_target_movement_modifier
    count=members(unit)
    result=({1:7,2:5,3:2}.get(count,-1) if leg else 5 if 1<=count<=3 else 2)
    if not leg and unit.team==target.team:result-=4
    if unit.has_crit_status(CritStatus.HIDDEN):
        if is_target_immobile(target):result-=4
        if target.is_fallen:result-=2 if leg else 4
    else:
        result+=calculate_target_movement_modifier(target,0.0,attacker=unit)
        if not leg and target.is_fallen:result-=2
    return result


def _guard(unit,actor):
    from systems.combat_commands import command_guard
    return command_guard(unit,caller=actor,wizard=getattr(actor,'wizard',False))


def _failure(unit,actor,message,all_occupants=False):
    if getattr(message,'notified',False):pass
    elif all_occupants:
        from systems.movement_commands import notify
        notify(unit,message)
    else:personal_notify(actor,message)
    return {'ok':False,'error':message}


def stop_hiding(unit):
    from core.events import EventType
    if unit._engine is not None:unit._engine.cancel_events_of_type(EventType.HIDE,unit)


def swarm(unit,actor,argument=''):
    from entities.mech import CritStatus
    from systems.piloting import make_piloting_roll
    from systems.combat_firing import swarm_id
    error=_guard(unit,actor)
    if error:return _failure(unit,actor,error)
    if isinstance(argument,str) and argument.lstrip()=='-' and swarm_id(unit)>0:
        detach(unit,True);return {'ok':True,'detached':True}
    error=common_checks(unit)
    if error:return _failure(unit,actor,error)
    target,error=find_target(unit,argument)
    if error:return _failure(unit,actor,error,error=='Invalid default target!')
    if target.team==unit.team:
        if not unit.infantry_specials&2:return _failure(unit,actor,'These battlesuits are not capable of mounting mechs!',True)
    else:
        error=jettison_checks(unit)
        if error:return _failure(unit,actor,error,True)
        if not unit.infantry_specials&1:return _failure(unit,actor,'These battlesuits are not capable of performing swarm attacks!',True)
    if count_swarmers(unit):return _failure(unit,actor,"That target already have battlesuits crawling all over it! There's no room for you!",True)
    mod=modifier(unit,target);result=make_piloting_roll(unit,mod)
    from systems.movement_commands import notify
    action='mount' if unit.team==target.team else 'swarm'
    if result.success:
        notify(target,f'{identity(target,unit)} {action}s you!')
        notify(unit,f'You {action} {identity(unit,target)}!')
        unit.swarm_target=target._id;target.swarmer=unit._id
        unit.set_status2(S2.UNIT_MOUNTING);target.set_status2(S2.UNIT_MOUNTED)
        _broadcast(unit,target,action+'s {}!')
        unit.speed=unit.desired_speed=0;unit.facing=unit.desired_facing=270
        mirror(target,unit)
        from systems.targeting import stop_lock
        stop_lock(unit,unit._engine)
    else:
        notify(target,f'{identity(target,unit)} attempts to {action} you!')
        notify(unit,f"Nice try, but you don't succeed in your attempt at {action}ing {identity(unit,target)}!")
    if unit.has_crit_status(CritStatus.HIDDEN):
        from systems.sensors import los_broadcast
        notify(unit,'You move too much and break your cover!');los_broadcast(unit,'breaks from its cover.')
        unit.clear_crit_status(CritStatus.HIDDEN);stop_hiding(unit)
    start_recycle(unit,20)
    return {'ok':True,'success':result.success,'modifier':mod,'target':result.target,'roll':result.roll}


def attackleg(unit,actor,argument=''):
    from systems.piloting import make_piloting_roll
    from systems.parts import is_mech_legless
    from entities.mech import MoveType,Location as L
    from core.randomness import draw,roll
    error=_guard(unit,actor)
    if error:return _failure(unit,actor,error)
    if not unit.infantry_specials&4:return _failure(unit,actor,'These battlesuits are not capable of performing leg attacks!',True)
    error=common_checks(unit)
    if error:return _failure(unit,actor,error)
    error=jettison_checks(unit)
    if error:return _failure(unit,actor,error,True)
    target,error=find_target(unit,argument)
    if error:return _failure(unit,actor,error,error=='Invalid default target!')
    if is_mech_legless(unit):return _failure(unit,actor,'That mech has no legs to grab!')
    if unit.team==target.team:return _failure(unit,actor,"You can't attack the leg of a friendly mech!")
    mod=modifier(unit,target,True)
    if target.move_type==MoveType.QUAD:
        legs=(L.RLEG,L.LLEG,L.RARM,L.LARM)
        if not any(target.sections[i].internal for i in legs):raise ValueError('Unsupported quad leg-selection nontermination: no live legs')
        while True:
            location=legs[draw('leg_location',0,3,lambda:random.randint(0,3))]
            if target.sections[location].internal:break
    else:
        location=L.RLEG if draw('leg_location',0,1,lambda:random.randint(0,1)) else L.LLEG
        if not target.sections[location].internal:location=L.LLEG if location==L.RLEG else L.RLEG
    from systems.movement_commands import notify
    locname={L.LLEG:'Left Leg',L.RLEG:'Right Leg',L.LARM:'Left Arm',L.RARM:'Right Arm'}[location]
    notify(unit,f"You go for {identity(unit,target)}'s {locname}, placing explosives in the joints!")
    result=make_piloting_roll(unit,mod);effect='miss';critroll=None
    if result.success:
        notify(target,f'{identity(target,unit)} swarms your {locname} putting small packets of explosives all over it!')
        _broadcast(unit,target,"attacks {}'s legs!")
        critroll=roll('leg_critical',lambda:random.randint(1,6)+random.randint(1,6))
        if critroll<8:
            notify(target,f'The explosives explode on the surface of your {locname}!')
            from systems.combat import apply_damage_with_transfer
            apply_damage_with_transfer(target,location,4,attacker=unit,is_critical=True,ignore_swarmers=True)
            effect='damage4-with-critical-flag'
        else:
            notify(target,f'The explosives manage to rip into the internals of your {locname}!')
            from systems.criticals import check_and_apply_criticals
            count=1 if critroll<10 else 2 if critroll<12 else 3
            if critroll==12:
                from systems.damage import destroy_section
                from systems.sensors import los_broadcast
                notify(target,'%ch%cyCRITICAL HIT!!%c')
                los_broadcast(target,f"'s {locname} is blown off in a shower of sparks and smoke!")
                destroy_section(target,unit,location)
            check_and_apply_criticals(target,location,count,attacker=unit,engine=unit._engine)
            effect='destroy-leg-then-critical3' if critroll==12 else f'critical{count}'
    else:
        notify(target,f'{identity(target,unit)} attempts to attacks your legs, but misses miserably.')
        notify(unit,f"You realize that this is harder than it looks and fail in your attempt at hitting {identity(unit,target)}'s legs!")
        _broadcast(unit,target,"attempts to climb {}'s legs, but fails miserably!")
    start_recycle(unit,30)
    return {'ok':True,'success':result.success,'modifier':mod,'target':result.target,'roll':result.roll,'location':int(location),'critical_roll':critroll,'effect':effect}


def hide_event(event):
    from entities.mech import CritStatus as C
    from systems.los import in_line_of_sight
    from systems.targeting import fa_mech_range
    from physics.orbital import height_above_ground
    from systems.movement_commands import notify
    from core.events import EventType
    unit,tick=event.data,event.data2
    if unit.map is None:return
    fail=height_above_ground(unit)!=0
    for other in unit.map.mechs_on_map:
        if other is None or other._id<=0 or other.crit_status&(C.CLAIRVOYANT|C.OBSERVATORIC|C.INVISIBLE):continue
        if other.team==unit.team or not other.is_started or other.is_destroyed:continue
        if in_line_of_sight(other,unit,unit.x,unit.y,fa_mech_range(other,unit)):fail=True
    if fail:notify(unit,"Your spidey sense tingles, telling you this isn't going to work......");return
    if tick<hide_threshold(unit):unit._engine.schedule_event(1,EventType.HIDE,hide_event,data=unit,data2=tick+1)
    else:notify(unit,'You are now hidden!');unit.set_crit_status(C.HIDDEN)


def hide_threshold(unit):
    from entities.mech import UnitType as U
    return 10*{U.MW:1,U.BSUIT:3,U.VTOL:4}.get(unit.unit_type,5)*(1 if unit.specials2&0x40000 else 2)


def hide(unit,actor,argument=''):
    from entities.mech import UnitType as U,MoveType as M,MechStatus as S
    from entities.map import LIGHT_FOREST,HEAVY_FOREST,MOUNTAINS,ROUGH,BUILDING
    from systems.combat_firing import swarm_id
    from core.events import EventType
    error=_guard(unit,actor)
    if error:return _failure(unit,actor,error)
    if not unit.specials2&0x40000 and not getattr(actor,'wizard',False) and unit.unit_type not in (U.BSUIT,U.MW):return _failure(unit,actor,"You aren't capable of such curious things.")
    if unit.map is None:return _failure(unit,actor,'You are not on a map!',True)
    if unit.is_jumping or unit.cocoon:return _failure(unit,actor,'Hide where? Up here?')
    if abs(unit.speed)>10.75:return _failure(unit,actor,'Come to a complete stop first.')
    if unit._engine.has_event(EventType.HIDE,unit):return _failure(unit,actor,'You are looking for cover already!')
    if unit.move_type==M.VTOL and not unit.has_status(S.LANDED):return _failure(unit,actor,'You must be landed!')
    if swarm_id(unit)>1:return _failure(unit,actor,'Hide where? Not while on that!')
    terrain=unit.map.rterrain(unit.x,unit.y)
    from systems.movement_commands import notify
    messages={LIGHT_FOREST:'You start to hide amongst the trees...',
              HEAVY_FOREST:'You start to hide amongst the trees...',
              MOUNTAINS:'You start to hide behind some rocky outcroppings...',
              ROUGH:'You find some boulders to try to hide behind...'}
    if terrain==BUILDING and unit.unit_type==U.BSUIT:
        message='You break into a building and look for a spot to hide...'
    else:message=messages.get(terrain)
    if message is None:
        notify(unit,'You begin to hide in this terrain...')
        return _failure(unit,actor,"... then realize that just isn't going to work!",True)
    notify(unit,message)
    unit._engine.schedule_event(1,EventType.HIDE,hide_event,data=unit,data2=0)
    return {'ok':True,'message':message}


def jettison(unit,actor,argument=''):
    from entities.mech import FireMode as F
    from systems.weapon_inventory import sync_weapon_states
    error=_guard(unit,actor)
    if error:return _failure(unit,actor,error)
    if not unit.infantry_specials&0x200:return _failure(unit,actor,'You have no backpack that is capable of being jettisoned!')
    pending=pending_packs(unit)
    for i,j,slot in pending:slot.firemode=(slot.firemode|F.DESTROYED_MODE|F.IS_JETTISONED_MODE)&~(F.BROKEN_MODE|F.DISABLED_MODE)
    sync_weapon_states(unit)
    for weapon in unit.weapons:
        if any(weapon.section==i and weapon.critical==j for i,j,slot in pending):weapon.destroyed=True
    text=('The explosive bolts that hold the backpacks on blow, allowing them to drop to the ground.' if members(unit)>1 else
          'The explosive bolts that hold your backpack on blows, allowing it to drop to the ground.') if pending else 'You realize you have nothing to jettison. Maybe you already did it?'
    from systems.movement_commands import notify
    notify(unit,text)
    if pending:
        from systems.sensors import los_broadcast
        los_broadcast(unit,"'s backpacks blow off in a shower of small explosions!" if members(unit)>1 else "'s backpack blows off in a puff of grey smoke!")
    return {'ok':True,'count':len(pending),'message':text}
