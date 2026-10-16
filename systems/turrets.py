# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.maps.c
#   btech/mech.scan.c
# Historical Aerospace sources:
#   btech/ds.turret.c

"""Independent dropship gunner objects delegating to real unit commands."""
from dataclasses import dataclass,asdict
from entities.mech import Mech,MechStatus as S
from systems.communications import common_checks,MECH_USUAL,MECH_USUALO
from systems.notifications import personal_notify


@dataclass
class Turret:
    _id: int = 0
    parent: int = 0
    gunner: int = 0
    arcs: int = 0
    target: int = -1
    targ_x: int = -1
    targ_y: int = -1
    targ_z: int = 0
    lockmode: int = 0
    location: int = -1
    xcode_type: str = 'TURRET'


def allocate(turret,key,selector=1):
    if selector==1:
        turret._id=key
        turret.target=turret.targ_x=turret.targ_y=-1
    return turret


def parent(engine,turret):
    return next((obj for obj in engine.get_entities() if isinstance(obj,Mech) and obj._id==turret.parent),None)


def response(ok,message=''):
    return dict(ok=ok,message=message)


def room_notice(engine,turret,message):
    world=getattr(engine,'personnel',None)
    if world is not None:
        for ident in world.contents(turret._id): personal_notify(world.objects[ident],message)


def initialize(engine,turret,actor):
    if parent(engine,turret) is None: return response(False,"Error: Turret's parentage is unknown.")
    world=getattr(engine,'personnel',None)
    old=world.objects.get(turret.gunner) if world else None
    if actor._id!=turret.gunner and old is not None and getattr(old,'connected',False) and old.location==actor.location:
        return response(False,f'You need {old.name} to leave or disconnect first.')
    if actor._id==turret.gunner: return response(False,'You grap firmer hold on the joystick..')
    message=f'{actor.name} initialized as gunner.'
    room_notice(engine,turret,message);turret.gunner=actor._id
    return response(True,message)


def deinitialize(engine,turret,actor):
    if parent(engine,turret) is None: return response(False,"Error: Turret's parentage is unknown.")
    if actor._id!=turret.gunner: return response(False,"You aren't gunner!")
    message=f'{actor.name} deinitialized as gunner.'
    room_notice(engine,turret,message);turret.gunner=-1
    return response(True,message)


def command(engine,turret,actor,name,argument=''):
    name=name.lower()
    if name in ('addtic','deltic','listtic','cleartic','firetic'): return dict(ok=True,messages=[])
    if name=='initialize': return initialize(engine,turret,actor)
    if name=='deinitialize': return deinitialize(engine,turret,actor)
    unit=parent(engine,turret)
    if unit is None: return response(False,"Error: Turret's parentage is unknown.")
    if turret.gunner<0: return response(False,"The turret hasn't been initialized yet!")
    if actor._id!=turret.gunner: return response(False,"You aren't the registered gunner! Go 'way!")
    if getattr(unit.pilot,'_id',None)==actor._id: return response(False,"You'll pilot and gun at once? Yah right :P")
    if name=='findcenter': return delegate(unit,name,argument,actor)
    keys=('status','target','targ_x','targ_y','targ_z')
    saved={key:getattr(unit,key) for key in keys}
    gun_pilot=getattr(unit,'gun_pilot',None)
    try:
        engine.pilot_override=turret.gunner if turret.gunner>0 else 0
        engine.arc_override=turret.arcs
        if turret.gunner>0: unit.gun_pilot=actor
        unit.status=S((int(unit.status) & ~int(S.LOCK_MODES))|turret.lockmode)
        for key in keys[1:]: setattr(unit,key,getattr(turret,key))
        return delegate(unit,name,argument,actor)
    finally:
        for key in keys[1:]: setattr(turret,key,getattr(unit,key))
        turret.lockmode=int(unit.status&S.LOCK_MODES)
        for key,value in saved.items(): setattr(unit,key,value)
        unit.gun_pilot=gun_pilot
        engine.pilot_override=engine.arc_override=0


def delegate(unit,name,argument,actor):
    result=_delegate(unit,name,argument,actor)
    if result.get('ok') and not result.get('notified'):
        from core.effects import notify_actor
        for text in result.get('lines', [result['message']] if result.get('message') else []):
            notify_actor(unit,actor,text)
        result['notified']=True
    return result


def _delegate(unit,name,argument,actor):
    """Shared ordinary command bodies; FINDCENTER enters without lock overrides."""
    from systems import observation as o,targeting as targeting
    from systems.movement_commands import eta,c_number
    from physics.hexmath import hex_to_float,find_range,find_bearing
    engine=getattr(unit,'_engine',None)
    name={'fireweapon':'fire','settarget':'lock','lrsmap':'lrs','tacmap':'tactical'}.get(name,name)
    if name in ('fire','sight'):
        from systems.combat_firing import fire_command
        from systems.combat_commands import parse_attributes
        result=fire_command(engine,unit,parse_attributes(argument,5),sight=name=='sight',caller=actor,historical=True)
        return dict(ok=result.bth_breakdown is not None and not result.roll_impossible and not result.shot_aborted,message='\n'.join(result.messages),attack=asdict(result),notified=True)
    if name=='lock':
        ok,message=targeting.lock_command(engine,unit,str(argument),caller=actor,wizard=getattr(actor,'wizard',False),historical=True)
        return dict(ok=ok,message=message,notified=True)
    from systems.communications import MECH_USUALSM,MECH_CONSISTENT
    error=common_checks(unit,actor,MECH_CONSISTENT if name=="weaponspecs" else MECH_USUALSM if name in ("status","critstatus") else MECH_USUAL)
    if error is not None:return response(False,error)
    if name in ('bearing','range'): return o.navigation(unit,name,str(argument),caller=actor)
    if name=='eta':
        ok,message=eta(engine,unit,str(argument),actor)
        return dict(ok=ok,message=message,notified=ok or getattr(message,'notified',False))
    if name=='findcenter':
        fx,fy=hex_to_float(unit.x,unit.y)
        distance=find_range(fx,fy,unit.fx,unit.fy)
        bearing=find_bearing(unit.fx,unit.fy,fx,fy)
        return dict(ok=True,x=unit.x,y=unit.y,z=unit.z,range=distance,bearing=bearing,message=f'Current hex: ({unit.x},{unit.y},{unit.z})\tRange to center: {distance:.2f}\tBearing to center: {bearing}')
    if name=='contacts':return o.contacts(unit,str(argument),caller=actor)
    if name in ('report','scan'):return o.scan(unit,str(argument),report=name=='report',caller=actor,historical=True)
    if name in ('lrs','tactical','navigate'):return o.map_readout(unit,name,str(argument),caller=actor,historical=True)
    if name in ('critstatus','status','weaponspecs'):return o.own_readout(unit,name,str(argument),caller=actor,historical=True)
    raise ValueError('Unknown turret command: '+name)
