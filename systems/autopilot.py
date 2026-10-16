# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/autopilot_core.c
#   btech/mech.events.c
#   btech/src/btech/autopilot.h

"""Shared UnZombifyMech lifecycle with source-specific AUTO event restoration."""
from core.events import EventType
from entities.mech import UnitType

AUTOPILOT_AUTOGUN = 1
AUTOPILOT_GUNZOMBIE = 2
AUTOPILOT_PILZOMBIE = 4


def uses_event_autopilot(mech):
    """Recovered Aerospace AUTO services own their cadence through events."""
    return getattr(mech, 'unit_type', None) in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS)


def good_object(context, identity):
    """Good_obj metadata, separate from the IsMech/IsAuto type checks."""
    from systems.targeting import resolve_object
    obj = resolve_object(context,identity)
    return (obj is not None and getattr(obj,'valid',True)
            and getattr(obj,'valid_object',True))


def valid_special_objects(a):
    """Resolve the live Hardcode/A_XTYPE objects before an AI callback."""
    from entities.autopilot import Autopilot
    from entities.mech import Mech
    from systems.targeting import resolve_object, resolve_unit
    mech = getattr(a,'mymech',None)
    return (isinstance(a,Autopilot) and a.allocated and isinstance(mech,Mech)
            and resolve_object(a,a._id) is a and resolve_unit(a,mech._id) is mech
            and getattr(a,'hardcode',True) and getattr(a,'xcode_type','AUTO') == 'AUTO'
            and getattr(mech,'hardcode',True) and getattr(mech,'xcode_type','MECH') == 'MECH')


def auto_com_event(event):
    """Run an installed AUTO service at the restored source event deadline."""
    autopilot = event.data
    service = {
        EventType.AUTOCOM: 'command',
        EventType.AUTO_PROFILE: 'profile',
        EventType.AUTOGUN: 'gun',
        EventType.AUTO_SENSOR: 'sensor',
    }[event.event_type]
    callback = autopilot_service(autopilot._engine,service,autopilot)
    if callback is not None:
        from systems.autopilot_autogun import auto_sensor_event
        if callback is auto_sensor_event:
            callback(autopilot,event.data2 or 0)
        else:
            callback(autopilot)
    else:
        from systems.damage import external_effect
        external_effect(autopilot, 'autopilot gameplay', 'AUTO ' + service + ' callback')


def un_zombify_mech(mech):
    """Wake only enabled gunnery and suspended pilot commands.

    General autopilot.h uses heartbeat gunnery. The authoritative historical
    Aerospace variant also restores profile, gun and sensor events at +1.
    """
    from systems.targeting import resolve_object
    reference = getattr(mech, 'auto', -1)
    if reference <= 0:
        return
    owner = mech if getattr(mech, '_engine', None) else getattr(mech, 'map', mech)
    autopilot = resolve_object(owner, reference)
    if autopilot is None:
        return
    engine = getattr(owner, '_engine', None)
    flags = getattr(autopilot, 'flags', 0)
    pending = []
    if flags & AUTOPILOT_AUTOGUN and flags & AUTOPILOT_GUNZOMBIE:
        if uses_event_autopilot(mech):
            pending.extend((EventType.AUTO_PROFILE, EventType.AUTOGUN, EventType.AUTO_SENSOR))
        flags &= ~AUTOPILOT_GUNZOMBIE
    if flags & AUTOPILOT_PILZOMBIE:
        flags &= ~AUTOPILOT_PILZOMBIE
        pending.append(EventType.AUTOCOM)
    if pending and engine is None:
        raise ValueError('Autopilot wakeup requires an owning engine')
    autopilot.flags = flags
    if engine is not None:
        autopilot._engine = engine
        for kind in pending:
            engine.schedule_event(1, kind, auto_com_event, data=autopilot, data2=0)


def dispose_mech_autopilot(mech):
    """newfreemech SPECIAL_FREE: stop AUTO and release its owned state."""
    from systems.targeting import resolve_object
    reference=getattr(mech,'auto',-1)
    if reference<=0:return
    auto=resolve_object(mech,reference)
    if auto is not None:
        auto.flags=getattr(auto,'flags',0)&~(AUTOPILOT_AUTOGUN|AUTOPILOT_GUNZOMBIE|AUTOPILOT_PILZOMBIE)
        from core.events import SOURCE_EVENT_IDS
        for event in mech._engine.events.pending_events(data=auto):
            source_id=SOURCE_EVENT_IDS.get(event.event_type,-1)
            if 23<=source_id<=32:event.cancel()
        if mech.unit_type in (UnitType.AERO,UnitType.DS,UnitType.SPHEROID_DS):
            # Recovered SPECIAL_FREE stops AUTO but retains its owned lists.
            auto.mymechnum=0
            mech.auto=-1
            return
        for name in ('commands','astar_path','weaplist'):
            value=getattr(auto,name,None)
            if hasattr(value,'clear'):value.clear()
            setattr(auto,name,None)
        profile=getattr(auto,'profile',None)
        if isinstance(profile,list):
            for i,value in enumerate(profile):
                if hasattr(value,'clear'):value.clear()
                profile[i]=None
        elif hasattr(profile,'clear'):profile.clear()
        auto.mymechnum=-1
    mech.auto=-1


def autopilot_service(engine, name, controller):
    """Keep legacy AUTO adapters on their configured-service contract."""
    from entities.autopilot import Autopilot
    callback = engine.auto_services.get(name)
    if getattr(callback,'_builtin_auto_service',False) and not isinstance(controller,Autopilot):
        return None
    return callback


def install_builtin_services(engine):
    """Normal controller registration installs defaults, preserving overrides."""
    from types import SimpleNamespace
    from systems.autopilot_commands import auto_com_event as command_event
    from systems.autopilot_autogun import (auto_sensor_event, auto_gun_event,
                                         auto_update_profile_event)
    from systems.autopilot_radio import auto_parse_command
    def command(a):
        command_event(SimpleNamespace(data=a,data2=0,event_type=EventType.AUTOCOM))
    defaults = dict(command=command,sensor=auto_sensor_event,
                    profile=auto_update_profile_event,gun=auto_gun_event,
                    radio=auto_parse_command)
    for name,callback in defaults.items():
        callback._builtin_auto_service = True
        engine.auto_services.setdefault(name,callback)
