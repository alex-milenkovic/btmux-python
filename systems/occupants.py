# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/eject.c
#   btech/mech.combat.misc.c
#   btech/mech.notify.c
#   btech/mech.pickup.c
# Historical Aerospace sources:
#   btech/aero.move.c

"""Ordered character transport, configured object actions and MW-shell disposal."""
from core.events import EventType as E
from systems.characters import attached,lower_xp
from systems.notifications import personal_notify,identity,unit_identity


class Personnel:
    def __init__(self,engine,characters,*,afterlife=900,used_store=901,xploss=666,in_character=True,pickup_action=1):
        self.engine=engine;self.characters=characters;self.afterlife=afterlife;self.used_store=used_store
        self.xploss=xploss;self.in_character=in_character;self.pickup_action=pickup_action
        self.objects={};self.members={};self.trace=[]
        import random
        self.radio_random=random.Random()
        self.radio_source=lambda:self.radio_random.randrange(1<<31)%1000000
        engine.personnel=self
        characters.effects=engine.effects

    def add(self,obj,location=-1):
        ident=obj._id
        if ident in self.objects and self.objects[ident] is not obj:raise ValueError('Duplicate personnel object identity')
        if ident in self.objects:self._unlink(ident)
        self.objects[ident]=obj;obj.location=location;obj._engine=self.engine
        self.members.setdefault(location,[]).append(ident)
        if not attached(obj):obj.hardcode=getattr(obj,'hardcode',True)
        self.update(obj,location=location)
        return obj

    def _unlink(self,ident):
        obj=self.objects[ident];old=self.members.get(getattr(obj,'location',-1),[])
        if ident in old:old.remove(ident)

    def contents(self,ident):return list(self.members.get(ident,[]))

    def update(self,obj,**values):
        for key,value in values.items():setattr(obj,key,value)
        registry=getattr(self.engine,'object_registry',None)
        if registry is not None:registry.register(obj)
        if attached(obj):
            self.characters.records[obj._id].update(values);self.characters.persist(obj._id)

    def move(self,ident,destination,loud=False):
        obj=self.objects[ident];origin=obj.location
        if loud:
            self.did_it(obj,obj,'A_OXTPORT',other_only=True)
            self.location_actions(obj,origin,destination,entering=False)
        self._unlink(ident)
        self.update(obj,location=destination);self.members.setdefault(destination,[]).append(ident)
        self.trace.append(dict(kind='move',id=ident,origin=origin,destination=destination,loud=loud))
        if loud:
            self.did_it(obj,obj,'A_TPORT','A_OTPORT','A_ATPORT')
            self.did_it(obj,obj,'A_MOVE','A_OMOVE','A_AMOVE')
            self.location_actions(obj,destination,origin,entering=True)

    def did_it(self,actor,target,what=None,owhat=None,awhat=None,*,default=None,other_only=False):
        from core.effects import did_it
        if other_only:what,owhat=None,what
        result=did_it(self.engine,actor,target,what,default,owhat,None,awhat)
        self.trace.append(dict(kind='action',**result))
        return result

    def location_actions(self,actor,location,other,*,entering):
        if location<0 or location==other:return
        target=self.objects.get(location)
        if target is None:
            target=next((obj for obj in self.engine.get_entities() if getattr(obj,'_id',None)==location),None)
        canhear=getattr(actor,'hearer',getattr(actor,'is_player',False))
        dark=getattr(actor,'dark',False);wizard=getattr(actor,'wizard',False)
        quiet=not (getattr(target,'wizard',False) or
                   not dark and not getattr(target,'dark',False) or canhear and not (wizard and dark))
        prefix='ENTER' if entering else 'LEAVE'
        personal=None if getattr(actor,'terse',False) and not getattr(self.engine,'terse_movemsg',False) else 'A_'+prefix
        self.did_it(actor,target if target is not None else location,personal,
                    None if quiet else 'A_O'+prefix,None if quiet else 'A_A'+prefix)
        if not quiet and other>=0:
            self.did_it(actor,other,'A_OXLEAVE' if entering else 'A_OXENTER',other_only=True)
        announce=(canhear and not (dark and wizard) if entering else
                  not dark and not getattr(target,'dark',False) or canhear and not (wizard and dark))
        if not quiet and announce:
            text=f'{getattr(actor,"object_name",actor.name)} has {"arrived" if entering else "left"}.'
            for ident in self.contents(location):
                if ident!=actor._id:personal_notify(self.objects[ident],text)

    def allocate(self):return max([0,*self.objects,*[o._id for o in self.engine.get_entities() if hasattr(o,'_id')]])+1


def tele_contents(engine,origin,destination,flags):
    world=engine.personnel;source=world.objects.get(origin);count=0
    for ident in world.contents(origin):
        obj=world.objects[ident];wizard=getattr(obj,'wizard',False)
        if not flags&1 and wizard:continue
        if flags&2 and not wizard:world.update(obj,slave=True,lock='')
        if flags&8 and not wizard and not getattr(source,'quiet',False) and attached(obj):
            lower_xp(world.characters,ident,world.xploss)
        world.move(ident,destination,bool(flags&4));count+=1
    return count


def ensure_personnel(unit):
    engine=unit._engine
    world=getattr(engine,'personnel',None)
    if world is None:
        if engine is None:
            from systems.damage import external_effect
            external_effect(unit,'local personnel registry','occupant effects require owning engine')
            return None
        from data.characters import CharacterStore
        pilot=unit.pilot
        world=Personnel(engine,getattr(pilot,'_character_store',None) or CharacterStore())
        for obj in engine.get_entities():
            if getattr(obj,'_id',-1)>=0:world.add(obj,getattr(obj,'location',-1))
        if unit._id not in world.objects:world.add(unit,getattr(unit,'location',unit.mapindex))
        if pilot is not None and getattr(pilot,'_id',0)>0 and pilot._id not in world.objects:
            world.add(pilot,getattr(pilot,'location',unit._id))
    return world


def kill_contents(unit):
    if not unit.in_character:return 0
    world=ensure_personnel(unit)
    if world is None:return 0
    victims=[i for i in world.contents(unit._id) if not getattr(world.objects[i],'wizard',False)]
    flags=4|(8 if world.in_character and world.xploss<1000 else 0)
    count=tele_contents(unit._engine,unit._id,world.afterlife,flags)
    for ident in victims:world.update(world.objects[ident],alive=False)
    return count


def discard_event(event):
    unit=event.data;world=unit._engine.personnel
    world.trace.append(dict(kind='leave',id=unit._id,origin=unit.location))
    world.did_it(unit,unit.location,'A_LEAVE','A_OLEAVE','A_ALEAVE')
    unit.hardcode=False
    if unit.map is not None:unit.map.remove_mech(unit)
    from systems.autopilot import dispose_mech_autopilot
    dispose_mech_autopilot(unit)
    unit._engine.unregister_entity(unit,cancel_events=True)
    unit.going=unit.dark=unit.zombie=True
    world.move(unit._id,world.used_store)
    world.trace.append(dict(kind='discard',id=unit._id))


def discard_mw(unit):
    if not unit.in_character:return
    if ensure_personnel(unit) is None:return
    unit._engine.schedule_event(10,E.NUKEMECH,discard_event,data=unit)


def enter_mw_bay(unit,bay):
    count=tele_contents(unit._engine,unit._id,bay,1);discard_mw(unit);return count


def _failure(actor,message,unit=None):
    if not getattr(message,'notified',False):
        if unit is None:personal_notify(actor,message)
        else:
            from systems.movement_commands import notify
            notify(unit,message)
    from systems.combat_commands import NotifiedError
    return {'ok':False,'error':NotifiedError(message)}


def _notice(unit,personal,broadcast):
    from systems.movement_commands import notify
    from systems.sensors import los_broadcast
    notify(unit,personal)
    los_broadcast(unit,broadcast)



def _ic_error(unit):
    world=unit._engine.personnel
    if not unit.in_character:return "This unit isn't in character!"
    if not world.in_character:return "This MUX isn't in character!"
    if not getattr(unit,'location_ic',getattr(unit.map,'in_character',True)):return "Your location isn't in character!"


def create_mw(unit,actor,kind):
    from entities.mech import Mech
    from systems.personal_damage import initialize_pc
    from systems.sensors import los_broadcast
    from systems.map_transitions import transfer,set_xy,set_team
    from core.effects import send_error
    world=unit._engine.personnel;directory=getattr(unit._engine,'template_directory',None)
    if not attached(actor) or actor._id not in world.objects:
        return _failure(actor,'Local character required for ejection')
    template=world.characters.record(actor._id).get('mwtemplate','')
    reference=template if template and template!='#-1' else 'MechWarrior'
    mw=Mech();mw._id=world.allocate();mw._engine=unit._engine
    mw.object_name=f'MechWarrior - {actor.name}'
    if directory is None or not directory.loadnew(mw,reference,wrapper=True):
        operation='disembarkation' if kind=='disembark' else 'ejection'
        send_error(unit,f"Unable to load mechwarrior template for #{actor._id}'s {operation}. ({template or 'Default template'})")
        return _failure(actor,"Sorry, something serious went wrong, contact a Wizard (can't load MWTemplate)")
    if unit.map is None:return _failure(actor,'Ejection map unavailable')
    mw.name='MechWarrior';mw.team=unit.team
    if kind=='disembark':mw.opaque=True
    unit._engine.register_entity(mw);world.add(mw,-1)
    transfer(mw,unit.mapindex,actor=1)
    set_xy(mw,unit.x,unit.y,actor=1)
    if kind=='disembark':mw.z=unit.z
    set_team(mw,unit.team,actor=1)
    world.move(mw._id,unit.mapindex)
    world.move(actor._id,mw._id)
    if kind=='eject':los_broadcast(mw,f'ejected from {unit_identity(unit)}!')
    mw.in_character=True
    initialize_pc(actor,mw,directory.catalog)
    mw.pilot=mw.command_actor=mw.pilot_owner=actor
    if kind in ('eject','disembark'):mw.official_pilot=actor._id
    mw.team=unit.team
    # Host radio randomness observes the already transferred and initialized pilot.
    channel=world.radio_source()
    mw.freq[0]=channel;personal_notify(actor,f'Emergency radio channel set to {channel}.')
    if hasattr(world,'units'):world.units[f'mw{mw._id}']=mw
    world.trace.append(dict(kind='create_mw',id=mw._id,player=actor._id,source=unit._id,template=reference,mode=kind))
    return {'ok':True,'unit':mw._id}


def eject(unit,actor):
    from entities.mech import UnitType as U,MechStatus as S,Location as L,FireMode as F
    from systems.combat_commands import command_guard
    from systems.combat import part_is_nonfunctional
    from systems.damage import destroy_mech,KILL_TYPE_EJECT
    error=command_guard(unit,started=False,pilot_only=False,caller=actor,wizard=getattr(actor,'wizard',False))
    if error:return _failure(actor,error)
    if unit.unit_type in (U.DS,U.SPHEROID_DS):return _failure(actor,'Dropships do not support ejection.')
    if unit.unit_type not in (U.MECH,U.VTOL,U.VEH_GROUND):return _failure(actor,'This unit has no ejection seat!')
    from systems.map_transitions import flying_type
    if flying_type(unit) and not unit.has_status(S.LANDED):return _failure(actor,'Regrettably, right now you can only eject when landed, sorry - no parachute :P')
    error=_ic_error(unit)
    if error:return _failure(actor,error)
    if unit.is_started and unit.pilot is not actor:return _failure(actor,"You aren't in da pilot's seat - no ejection for you!")
    if not unit.is_started and getattr(unit,'official_pilot',-1)!=actor._id:return _failure(actor,"You aren't the official pilot of this thing. Try 'disembark'")
    if unit.unit_type==U.MECH and part_is_nonfunctional(unit,L.HEAD,2):return _failure(actor,"The parts of cockpit that control ejection are already used. Try 'disembark'")
    result=create_mw(unit,actor,'eject')
    if not result['ok']:return result
    personal_notify(actor,'You eject from the unit!')
    if unit.unit_type==U.MECH:
        from systems.criticals import _destroy_part
        _destroy_part(unit.sections[L.HEAD].criticals[2])
    if not unit.is_destroyed:destroy_mech(unit,unit,False,KILL_TYPE_EJECT)
    return result


def disembark(unit,actor):
    from entities.mech import UnitType as U
    from systems.combat_commands import command_guard
    from systems.startup import starting
    error=command_guard(unit,started=False,pilot_only=False,caller=actor,wizard=getattr(actor,'wizard',False))
    if error:return _failure(actor,error)
    if unit.unit_type not in (U.MECH,U.VTOL,U.VEH_GROUND):return _failure(actor,"The door ! The door ? The Door ?!? Where's the exit in this damned thing ?")
    error=_ic_error(unit)
    if error:return _failure(actor,error)
    if (unit.is_started or starting(unit._engine,unit)) and unit.pilot is actor:return _failure(actor,"While it's running!? Don't be daft.")
    if abs(unit.speed)>25:return _failure(actor,'Are you suicidal ? That thing is moving too fast !')
    result=create_mw(unit,actor,'disembark')
    if not result['ok']:return result
    mw=unit._engine.personnel.objects[result['unit']]
    from systems.sensors import los_broadcast
    if mw.z>mw.map.elevation(mw.x,mw.y)+1 and mw.z>0:
        from physics.orbital import fall_event
        speed=int((unit.speed+unit.vertical_speed)/10.75/2+4)
        personal_notify(actor,'You open the hatch and climb out of the unit. Maybe you should have done this while the thing was closer to the ground...')
        los_broadcast(mw,f'jumps out of {unit_identity(unit)}... in mid air !')
        unit._engine.schedule_event(3,E.FALL,fall_event,data=mw,data2=-speed)
    else:
        los_broadcast(mw,f'climbs out of {unit_identity(unit)}!')
        personal_notify(actor,'You climb out of the unit.')
    return result


def autoeject(unit,actor,is_battlesuit=False):
    if actor is None or getattr(actor,'_id',0)==0 or not unit.in_character:return {'ok':False,'skipped':True}
    from systems.notifications import personal_notify,unit_identity
    from systems.sensors import los_broadcast
    from core.effects import send_error
    def failure(result):
        send_error(unit,f"Autoejection for #{actor._id} failed: {result['error']}")
        return result
    world=getattr(unit._engine,'personnel',None)
    if world is None:return failure(_failure(actor,'Local personnel registry unavailable'))
    if _ic_error(unit):return {'ok':False,'skipped':True}
    result=create_mw(unit,actor,'auto')
    if not result['ok']:return result
    mw=world.objects[result['unit']]
    if is_battlesuit:
        los_broadcast(mw,'climbs out of one of the destroyed suits!')
        personal_notify(actor,'You climb out of the unit!')
    else:
        from physics.orbital import initiate_ood
        los_broadcast(mw,f'ejected from {unit_identity(unit)}!')
        ok,message=initiate_ood(unit._engine,mw,f'{mw.x} {mw.y} 150',actor=actor)
        personal_notify(actor,'You eject from the unit!')
        if not ok:result['ood_error']=message
    return result


def _target(unit,reference):
    """Resolve a caller-validated contact token or object without reparsing it."""
    from systems.targeting import contact_target,fa_mech_range
    from systems.los import in_line_of_sight
    target=contact_target(unit,reference)
    if target is None or not in_line_of_sight(unit,target,target.x,target.y,fa_mech_range(unit,target)):return None
    return target


def _enter_lock(unit,target,actor):
    lock=getattr(target,'enter_lock','');response=getattr(target,'lock_result',None)
    if lock and response is None:return 'Enter lock service unavailable.'
    if response is False:
        from core.attributes import attributes_for
        from systems.combat_commands import NotifiedError
        attributes=attributes_for(target)
        default="That unit's bay doors are locked."
        message=attributes.get(target._id,'A_FAIL') or default
        unit._engine.personnel.did_it(actor,target,'A_FAIL',awhat='A_AFAIL',default=default)
        return NotifiedError(message)
    if not lock and unit.team!=target.team:return 'Locked. Damn !'


def _same_hex(unit,target):
    if unit.z>target.z+1:return 'You are too high above the target.'
    if unit.z<target.z-1:return "You can't reach that high !"
    if (unit.x,unit.y)!=(target.x,target.y):return 'You need to be in the same hex!'


def _recycle(unit):
    from systems.physical import sect_has_busy_weap
    for i,section in enumerate(unit.sections):
        if sect_has_busy_weap(unit,i):return 'You have weapons recycling!'
        if section.recycle>0:return 'You are still recovering from your previous action!'


def _unhide_carrier(unit,message):
    from entities.mech import CritStatus
    from systems.sensors import los_broadcast
    if unit.has_crit_status(CritStatus.HIDDEN):
        unit.clear_crit_status(CritStatus.HIDDEN);los_broadcast(unit,message)


def embark(unit,actor,reference):
    from entities.mech import UnitType as U,MechStatus as S,CritStatus,FireMode as F,Location as L
    from systems.combat_commands import command_guard
    from systems.combat import part_is_nonfunctional
    from systems.damage import unit_is_fixable
    from physics.cargo import cargo_max_speed
    from systems.ecm import mark_for_los_update
    from systems.startup import shutdown_state
    from systems.vehicle_combat import correct_speed
    if not getattr(actor,'god',False):
        error=command_guard(unit,caller=actor,pilot_only=False,wizard=getattr(actor,'wizard',False))
        if error:return _failure(actor,error)
    if isinstance(reference,str) and len(reference.split())!=1:return _failure(actor,'Invalid number of arguements.')
    target=_target(unit,reference)
    if target is None:return _failure(actor,'That target is not in your line of sight.')
    world=unit._engine.personnel
    if unit.unit_type==U.MW:
        if target.cocoon:return _failure(actor,'You should wait for your target to land first')
        error=_same_hex(unit,target)
        if error:return _failure(actor,error)
        if not unit.in_character or not target.in_character:return _failure(actor,"You don't really see a way to get in there.")
        if target.unit_type in (U.VEH_GROUND,U.VTOL) and not unit_is_fixable(target):return _failure(actor,"You can't find and entrance amid the mass of twisted metal.")
        error=_enter_lock(unit,target,actor)
        if error:return _failure(actor,error)
        if abs(target.speed)>15:return _failure(actor,'Are you suicidal ? That thing is moving too fast !')
        if target.unit_type==U.MECH:
            if not target.sections[L.HEAD].internal:return _failure(actor,'Okay, just climb up to-- Wait... where did the head go??')
            if target.sections[L.HEAD].criticals[2].firemode&F.DESTROYED_MODE:return _failure(actor,'Okay, just climb up and open-- WTF ? Someone stole the cockpit!')
            if part_is_nonfunctional(target,L.HEAD,2):return _failure(actor,"Okay, just climb up and open-- hey, this door won't budge!")
        _notice(unit,f'You climb into {unit_identity(target)}.',f'climbs into {unit_identity(target)}.')
        count=tele_contents(unit._engine,unit._id,target._id,1);discard_mw(unit)
        return {'ok':True,'count':count,'message':f'You climb into {unit_identity(target)}.'}
    if unit.carrying==target._id:return _failure(actor,'You cannot embark what your towing!')
    if unit.is_fallen or unit._engine.has_event(E.STAND,unit):return _failure(actor,"Help! I've fallen and I can't get up!")
    if not unit.is_started or unit.is_destroyed:return _failure(actor,'Ha Ha Ha.')
    if unit.is_jumping:return _failure(actor,'You cannot do that while jumping!')
    if target.is_jumping:return _failure(actor,'You cannot do that while it is jumping!')
    dropships=(U.DS,U.SPHEROID_DS)
    if unit.specials2&0x80000 and (unit.unit_type in dropships if target.unit_type in dropships else True):return _failure(actor,"You're a bit bulky to do that yourself.")
    if unit.has_crit_status(CritStatus.HIDDEN):return _failure(actor,'You cannot embark while hidden.')
    if unit.tonnage>getattr(target,'car_max_ton',0):return _failure(actor,'You are too large for that class of carrier.')
    if unit.unit_type!=U.BSUIT and not target.specials2&0x80000:return _failure(actor,"This unit can't handle your mass.")
    if cargo_max_speed(unit)<10.75:return _failure(actor,'You are to overloaded to enter.')
    error=_same_hex(unit,target) or _enter_lock(unit,target,actor)
    if error:return _failure(actor,error)
    if abs(target.speed)>0:return _failure(actor,'Are you suicidal ? That thing is moving too fast !')
    if not unit.in_character or not target.in_character:return _failure(actor,"You don't really see a way to get in there.")
    error=_recycle(unit)
    if error:return _failure(actor,error)
    if unit.tonnage*100>getattr(target,'cargo_space',0):return _failure(actor,'Not enough cargospace for you!')
    tow=None
    if unit.carrying>0:
        tow=world.objects.get(unit.carrying)
        if tow is None:return _failure(actor,'Internal error caused by towed unit! Contact a wizard!')
        if tow.tonnage>target.car_max_ton:return _failure(actor,'Your towed unit is  too large for that class of carrier.')
        if (unit.tonnage+tow.tonnage)*100>target.cargo_space:return _failure(actor,'Not enough cargospace for you and your towed unit!')
    if unit.unit_type==U.BSUIT:_notice(unit,f'You climb into {unit_identity(target)}.',f'climbs into {unit_identity(target)}.')
    else:
        _notice(unit,f'You climb up the entry ramp into {unit_identity(target)}.',f'climbs up the entry ramp into {unit_identity(target)}.')
        if tow is not None:_notice(tow,f'You are drug up the entry ramp into {unit_identity(target)}.',f'is drug up the entry ramp into {unit_identity(target)}.')
    mark_for_los_update(unit);mark_for_los_update(target);_unhide_carrier(target,'becomes visible as it is embarked into.')
    for child in ([tow] if tow is not None else [])+[unit]:
        mark_for_los_update(child)
        from systems.map_transitions import transfer,set_xy
        transfer(child,-1,actor=1);set_xy(child,0,0,actor=1)
        world.move(child._id,target._id,True);target.cargo_space-=child.tonnage*100
        shutdown_state(unit._engine,child)
        if child is tow:unit.carrying=-1;unit.towed_unit=None;child.clear_status(S.TOWED)
    correct_speed(target)
    return {'ok':True,'cargo_space':target.cargo_space}


def unit_disembark(unit,actor):
    from entities.mech import Mech,UnitType as U,MoveType as M,MechStatus as S,Specials
    from physics.cargo import cargo_max_speed
    from physics.hexmath import ZSCALE
    from systems.ecm import mark_for_los_update
    from systems.parts import set_cargo_weight
    from systems.vehicle_combat import correct_speed
    from systems.piloting import fix_pilotdamage
    from systems.characters import actor_value,skill_target
    world=unit._engine.personnel
    if unit.in_character and not getattr(actor,'wizard',False) and getattr(unit,'official_pilot',-1)!=actor._id:return _failure(actor,"This isn't your mech!")
    carrier=world.objects.get(getattr(unit,'location',-1))
    if carrier is None or not getattr(carrier,'hardcode',False):return _failure(actor,"You're not being carried!")
    if not isinstance(carrier,Mech):return _failure(actor,'Not being carried!')
    if carrier.mapindex==-1:return _failure(actor,'You are not on a map.')
    jobs=getattr(unit._engine,'repair_jobs',None)
    remaining=jobs.latest(unit) if jobs is not None else getattr(unit,'repair_remaining',0)
    if remaining:return _failure(actor,"This 'Mech is still under repairs (see checkstatus for more info)")
    if abs(carrier.speed)>cargo_max_speed(carrier)*2/3:return _failure(actor,'You cannot leave while the carrier is moving faster than walk speed!')
    from systems.map_transitions import transfer,set_xy,flying_type
    from systems.targeting import indexed_map
    transfer(unit,carrier.mapindex,actor=1);set_xy(unit,carrier.x,carrier.y,actor=1)
    unit.z=carrier.z;unit.fz=ZSCALE*unit.z
    board=indexed_map(unit)
    if board is None:return _failure(actor,'Major map error possible. Prolly should contact a wizard.')
    world.move(unit._id,unit.mapindex,True)
    if not unit.is_destroyed and actor.location==unit._id:
        unit.pilot=actor;unit.set_status(S.STARTED);unit.turn_damage=0
        from core.game_loop import update_recycling
        from systems.targeting import start_plos_event
        update_recycling(unit._engine,unit);unit.num_seen=0;start_plos_event(unit._engine,unit)
    mark_for_los_update(unit);set_cargo_weight(unit);unit.prefs&=~1
    from systems.sensors import los_broadcast
    los_broadcast(unit,'powers up!')
    if getattr(unit.pilot,'_id',-1)>0 and getattr(unit.pilot,'is_player',False) and actor_value(unit.pilot,'Sixth_Sense'):unit.specials|=Specials.SS_ABILITY
    else:unit.specials&=~Specials.SS_ABILITY
    if attached(unit.pilot) and getattr(unit.pilot,'is_player',True) and not getattr(unit,'quiet',False):
        unit.comm=skill_target(world.characters,unit.pilot._id,'Comm-Conventional');unit.per=skill_target(world.characters,unit.pilot._id,'Perception')
    else:unit.comm=unit.per=6
    unit.comm_last=0
    from systems.autopilot import un_zombify_mech
    un_zombify_mech(unit)
    carrier.cargo_space+=unit.tonnage*100;mark_for_los_update(carrier);_unhide_carrier(carrier,'becomes visible as it is disembarked from.')
    flying=flying_type(unit);floor=board.elevation(unit.x,unit.y)
    path='ramp';ood_error=None
    if not flying and unit.z>floor and unit.z>0:
        from physics.orbital import initiate_ood
        personal_notify(actor,'You open the hatch and drop out of the unit....')
        los_broadcast(unit,f'drops out of {unit_identity(carrier)} and begins falling to the ground.')
        ok,message=initiate_ood(unit._engine,unit,f'{unit.x} {unit.y} {unit.z}',actor=actor)
        if not ok:ood_error=message
        path='OOD'
    elif unit.unit_type==U.BSUIT:
        los_broadcast(unit,f'climbs out of {unit_identity(carrier)}!')
        personal_notify(actor,'You climb out of the unit.');path='climbout'
    elif carrier.is_destroyed or not carrier.is_started:
        from physics.jump import mech_falls
        los_broadcast(unit,f'smashes open the ramp door and emerges from {unit_identity(carrier)}!')
        personal_notify(actor,'You smash open the door and break out.')
        mech_falls(unit,4);path='breakout'
    else:
        los_broadcast(unit,f'emerges from the ramp out of {unit_identity(carrier)}!')
        personal_notify(actor,'You emerge from the unit loading ramp.')
        if unit.has_status(S.LANDED) and unit.z>floor and flying:unit.clear_status(S.LANDED)
    if unit.unit_type==U.BSUIT:
        from systems.swarm import start_recycle
        start_recycle(unit,20)
    elif unit.unit_type in (U.MECH,U.MW,U.VEH_GROUND,U.VTOL):
        from core.game_loop import update_recycling
        update_recycling(unit._engine,unit)
        for i,section in enumerate(unit.sections):
            if unit.unit_type in (U.MECH,U.MW) or i!=5:section.recycle=60
    fix_pilotdamage(unit,unit.pilot);correct_speed(carrier)
    result={'ok':True,'path':path,'cargo_space':carrier.cargo_space}
    if ood_error is not None:result['ood_error']=ood_error
    return result


def pickup(unit,actor,reference):
    from entities.mech import UnitType as U,MechStatus as S,MechStatus2 as S2,CritStatus,Specials,Location as L
    from systems.combat_commands import command_guard
    from entities.map import BRIDGE
    if not (getattr(actor,'_id',None)==1 or getattr(actor,'god',False)):
        error=command_guard(unit,caller=actor,pilot_only=False,wizard=getattr(actor,'wizard',False))
        if error:return _failure(actor,error)
    if unit.has_status2(S2.FORTIFIED):return _failure(actor,'You cannot tow while fortified.')
    from systems.movement_commands import mode_locked
    if mode_locked(unit):return _failure(actor,'You cannot tow currently in this movement mode!')
    if isinstance(reference,str):
        from data.templates import parse_attributes
        args=parse_attributes(reference,1)
        if not args:return _failure(actor,'Invalid number of arguments.')
        reference=args[0]
    target=_target(unit,reference)
    if target is None:return _failure(actor,'That target is not in your line of sight.')
    if target.has_status2(S2.FORTIFIED):return _failure(actor,'Your target is fortified and cannot be towed.')
    if target.specials2&0x80000 and not unit.specials2&0x80000:return _failure(actor,'You cannot handle the mass on that carrier.')
    if any(unit.sections[i].specials&0x20 for i in (L.RARM,L.LARM)):return _failure(actor,"You can't pickup while you're carrying a club!")
    if unit.is_jumping:return _failure(actor,"You can't pickup while jumping!")
    if target.is_jumping:return _failure(actor,'What are you going to do? Grab it from mid air?')
    if unit.is_fallen:return _failure(actor,'You are in no position to pick anything up!')
    if unit.z>target.z+3:return _failure(actor,'You are too high above the target.')
    if unit.z<target.z-2:return _failure(actor,'You are too far below the target.')
    if (unit.x,unit.y)!=(target.x,target.y):return _failure(actor,'You need to be in the same hex!')
    if target.z<=0 and target.terrain==BRIDGE and unit.z>0:return _failure(actor,'You need to be under the bridge to pick up this unit.')
    if target.has_status(S.TOWED):return _failure(actor,"That target's already being towed by someone!")
    if target.swarm_target==unit._id:return _failure(actor,"You can't grab hold!")
    if unit.tonnage<5 or not target.in_character and not getattr(target,'towable',False):return _failure(actor,"You can't tow that!")
    if target.has_crit_status(CritStatus.HIDDEN):return _failure(actor,'You cannot pickup hiding targets....')
    if getattr(target,'burn_recovery_countdown',0)>0:return _failure(actor,"You can't tow a burning unit!")
    if target.cocoon:return _failure(actor,"You can't tow a unit that is still OODing. Wait until it lands!")
    if target.unit_type!=U.MW:
        from systems.towing import pickup_unit
        return pickup_unit(unit,actor,target)
    if unit.unit_type not in (U.MECH,U.VEH_GROUND,U.VTOL) and not unit.specials&Specials.SALVAGE_TECH:return _failure(actor,"You can't pick up, period.",unit)
    world=unit._engine.personnel;flags=1|(4 if world.pickup_action else 2 if target.team!=unit.team else 0)
    if world.contents(target._id) and world.contents(target._id)[0]>0:
        from systems.notifications import personal_notify
        personal_notify(world.objects[world.contents(target._id)[0]],f'{identity(target,unit)} scoops you up and brings you into the cockpit.')
    from systems.sensors import los_broadcast
    from systems.movement_commands import notify
    los_broadcast(unit,f'picks up {unit_identity(target)}.')
    notify(unit,'You pick up the stray mechwarrior from the field.')
    count=tele_contents(unit._engine,target._id,unit._id,flags);discard_mw(target)
    return {'ok':True,'count':count,'message':'You pick up the stray mechwarrior from the field.'}
