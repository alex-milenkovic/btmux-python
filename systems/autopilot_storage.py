"""Versioned AUTO snapshots, following the map snapshot ownership convention.

Units, maps, clocks and randomness remain owned by their existing services.
Commands and scalar state persist; paths and profiles are rebuilt. Deadlines
are relative and replies retain the actual unit as their scheduler owner.
"""
import math
import re
from entities.autopilot import Autopilot
from entities.mech import Mech
from core.events import Event, EventType as E, SOURCE_EVENT_IDS
from systems.autopilot import auto_com_event, install_builtin_services
from systems.autopilot_core import auto_save_commands, auto_load_commands
from systems.communications import auto_reply_event
from systems import autopilot_commands as orders

CALLBACKS = {
    'service': (None,auto_com_event),
    'oldgoto': (E.AUTOGOTO,orders.auto_goto_event),
    'dumbgoto': (E.AUTOGOTO,orders.auto_dumbgoto_event),
    'goto': (E.AUTOGOTO,orders.auto_astar_goto_event),
    'follow': (E.AUTOFOLLOW,orders.auto_astar_follow_event),
    'dumbfollow': (E.AUTOFOLLOW,orders.auto_dumbfollow_event),
    'leave': (E.AUTOLEAVE,orders.auto_leave_event),
    'enter': (E.AUTOENTERBASE,orders.auto_enter_event),
    'roam': (E.AUTO_ROAM,orders.auto_astar_roam_event),
    'reply': (E.AUTO_REPLY,auto_reply_event)}
SERVICE_KINDS = (E.AUTOCOM,E.AUTO_PROFILE,E.AUTOGUN,E.AUTO_SENSOR)


def _callback_name(callback):
    return ((getattr(callback,'__module__',None) or type(callback).__module__)+'.'
            +(getattr(callback,'__qualname__',None) or type(callback).__qualname__))


def _slot(engine, event):
    return dict(id=event.event_id,remaining=event.tick-engine.tick,
                kind=event.event_type.name,owner=getattr(event.data,'_id',None),
                callback=_callback_name(event.callback),
                zombie=event.zombie)


def save_snapshot(engine, controllers=None):
    controllers = list(controllers) if controllers is not None else [o for o in engine.get_entities() if isinstance(o,Autopilot)]
    if len({a._id for a in controllers}) != len(controllers):
        raise ValueError('Duplicate controller identity')
    rows = []
    for a in controllers:
        if not a.allocated or a not in engine.get_entities():
            raise ValueError('Snapshot controller must be registered')
        rows.append(dict(id=a._id,name=a.name,values={k:getattr(a,k) for k in Autopilot.state_fields},
                         commands=auto_save_commands(a).hex(),linked=a.mymech is not None,
                         pilot=a.mymech is not None and a.mymech.pilot is a))
    units = {a.mymech._id:a.mymech for a in controllers if a.mymech is not None}
    events = []
    for event in engine.events.pending_events():
        owned = any(event.data is a for a in controllers)
        reply = event.event_type == E.AUTO_REPLY and any(event.data is u for u in units.values())
        if not (owned or reply):
            continue
        if not 23 <= SOURCE_EVENT_IDS.get(event.event_type,-1) <= 32:
            continue
        name = next((k for k,(_,cb) in CALLBACKS.items() if cb is event.callback),None)
        if name is None:
            raise ValueError('Unsupported AUTO callback in snapshot')
        events.append(dict(id=event.event_id,owner=event.data._id,kind=event.event_type.name,
                           callback=name,remaining=event.tick-engine.tick,data=event.data2))
    document = dict(version=2,controllers=rows,events=events,
                    layout=[_slot(engine,event) for event in engine.events.heap_events()])
    _candidates(engine,document)
    return document


def _fields(value, names):
    if not isinstance(value,dict) or set(value) != set(names):
        raise ValueError('Invalid AUTO snapshot fields')


def _integer(value):
    if isinstance(value,bool) or not isinstance(value,int):
        raise ValueError('AUTO snapshot requires integer')
    return value


def _layout_event_kind(name):
    # SourceEventType names are opaque world anchors, not AI callbacks to load.
    # Recognize their canonical nonnegative IDs without registering any types.
    return isinstance(name,str) and (name in E.__members__ or
        re.fullmatch(r'SOURCE_(?:0|[1-9][0-9]*)',name) is not None)


def _candidates(engine, document):
    if isinstance(document,dict) and document.get('version') != 2:
        raise ValueError('Unsupported AUTO snapshot version; save again with queue-order metadata')
    _fields(document,('version','controllers','events','layout'))
    if not isinstance(document['controllers'],list) or not isinstance(document['events'],list):
        raise ValueError('AUTO snapshot requires arrays')
    objects = {o._id:o for o in engine.get_entities() if hasattr(o,'_id')}
    people = getattr(engine,'personnel',None)
    candidates,units = {},{}
    for row in document['controllers']:
        _fields(row,('id','name','values','commands','linked','pilot'))
        ident = _integer(row['id'])
        if ident <= 0 or ident in candidates or ident in objects and not isinstance(objects[ident],Autopilot):
            raise ValueError('Duplicate or conflicting AUTO identity')
        if people is not None and ident in people.objects and not isinstance(people.objects[ident],Autopilot):
            raise ValueError('AUTO identity conflicts with personnel')
        if not isinstance(row['name'],str) or not isinstance(row['linked'],bool) or not isinstance(row['pilot'],bool):
            raise ValueError('Invalid AUTO metadata')
        _fields(row['values'],Autopilot.state_fields)
        a = Autopilot(ident)
        a.name = row['name']
        for key,value in row['values'].items():
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
                raise ValueError('Invalid AUTO scalar')
            if key not in ('b_msc','w_msc','b_bsc','w_bsc','b_dan','w_dan'):
                _integer(value)
            setattr(a,key,value)
        if not isinstance(row['commands'],str):
            raise ValueError('AUTO commands require hexadecimal text')
        auto_load_commands(a,bytes.fromhex(row['commands']))
        if row['linked']:
            unit = objects.get(a.mymechnum)
            if not isinstance(unit,Mech) or unit._id in units:
                raise ValueError('AUTO unit missing or attached more than once')
            a.mymech = unit
            units[unit._id] = unit
        elif row['pilot']:
            raise ValueError('Unlinked AUTO cannot own pilot')
        candidates[ident] = a
    for obj in objects.values():
        if isinstance(obj,Autopilot) and obj._id not in candidates and obj.mymech is not None and obj.mymech._id in units:
            raise ValueError('AUTO unit owned by a controller outside this snapshot')
    if not isinstance(document['layout'],list):
        raise ValueError('AUTO snapshot requires a queue layout')
    layout = {}
    for index,slot in enumerate(document['layout']):
        _fields(slot,('id','remaining','kind','owner','callback','zombie'))
        ident = _integer(slot['id'])
        remaining = _integer(slot['remaining'])
        if (ident < 0 or ident in layout or not -2147483648 <= remaining <= 2147483647
                or index and remaining < document['layout'][(index-1)//2]['remaining']
                or not _layout_event_kind(slot['kind']) or not isinstance(slot['callback'],str)
                or not isinstance(slot['zombie'],bool)):
            raise ValueError('Invalid AUTO queue layout')
        if slot['owner'] is not None:
            _integer(slot['owner'])
        layout[ident] = slot
    event_ids = set()
    for row in document['events']:
        _fields(row,('id','owner','kind','callback','remaining','data'))
        ident = _integer(row['id'])
        if ident in event_ids or ident not in layout:
            raise ValueError('Duplicate or missing AUTO event slot')
        event_ids.add(ident)
        owner = _integer(row['owner'])
        remaining = _integer(row['remaining'])
        if remaining < 1 or remaining > 2147483647:
            raise ValueError('Invalid remaining AUTO deadline')
        if row['callback'] not in CALLBACKS or row['kind'] not in E.__members__:
            raise ValueError('Unknown AUTO callback')
        expected,callback = CALLBACKS[row['callback']]
        slot = layout[ident]
        if (slot['zombie'] or slot['remaining'] != remaining or slot['owner'] != owner
                or slot['kind'] != row['kind']
                or slot['callback'] != _callback_name(callback)):
            raise ValueError('AUTO event does not match its queue slot')
        kind = E[row['kind']]
        if kind != expected and not (row['callback'] == 'service' and kind in SERVICE_KINDS):
            raise ValueError('AUTO callback type mismatch')
        if row['callback'] == 'reply':
            if owner not in units or not isinstance(row['data'],str):
                raise ValueError('Invalid AUTO reply owner/data')
        elif owner not in candidates or not isinstance(row['data'],int) or isinstance(row['data'],bool):
            raise ValueError('Invalid AUTO event owner/data')
    return candidates,units


def load_snapshot(engine, document, *, preflight=None):
    # Complete validation, including the caller's public index, precedes changes.
    candidates,units = _candidates(engine,document)
    if preflight is not None:
        preflight(candidates)
    ids = set(candidates)
    old = [o for o in engine.get_entities() if isinstance(o,Autopilot) and o._id in ids]
    people = getattr(engine,'personnel',None)
    current = {event.event_id:event for event in engine.events.heap_events()}
    removed = {ident for ident,event in current.items() if any(event.data is a for a in old)
               or event.event_type == E.AUTO_REPLY and any(event.data is u for u in units.values())}
    for a in old:
        engine.unregister_entity(a)
        a.allocated = False
        if a.mymech is not None and a.mymech.auto == a._id:
            a.mymech.auto = -1
        if a.mymech is not None and a.mymech.pilot is a:
            a.mymech.pilot = None
        if people is not None and people.objects.get(a._id) is a:
            if a.location != candidates[a._id].location:
                people._unlink(a._id)
                people.members.setdefault(candidates[a._id].location,[]).append(a._id)
            people.objects[a._id] = candidates[a._id]
    for unit in units.values():
        engine.cancel_events_of_type(E.AUTO_REPLY,unit)
    for row in document['controllers']:
        a = candidates[row['id']]
        engine.register_entity(a)
        if a.mymech is not None:
            a.mymech.auto = a._id
            if row['pilot']:
                a.mymech.pilot = a
        if people is not None:
            if a._id in people.objects:
                people.objects[a._id] = a
                people.update(a,location=a.location)
            else:
                people.add(a,a.location)
        registry = getattr(engine,'object_registry',None)
        if registry is not None:
            registry.register(a)
    restored_events = {}
    for row in document['events']:
        callback_name = row['callback']
        _,callback = CALLBACKS[callback_name]
        data = row['data']
        owner = units[row['owner']] if callback_name == 'reply' else candidates[row['owner']]
        if callback_name in ('goto','follow','roam'):
            data = 1  # Rebuild transient path at the saved next decision deadline.
        restored_events[row['id']] = Event(engine.tick+row['remaining'],row['id'],
                                           E[row['kind']],callback,data=owner,data2=data)
    slots = []
    for slot in document['layout']:
        event = restored_events.get(slot['id'])
        if event is None:
            anchor = current.get(slot['id'])
            if anchor is not None and anchor.event_id not in removed:
                metadata = _slot(engine,anchor)
                # Preserve a world callback's current cancellation state too.
                metadata['zombie'] = slot['zombie']
                if metadata == slot:
                    event = anchor
        slots.append((engine.tick+slot['remaining'],event))
    engine.events.restore_slots(slots,removed)
    install_builtin_services(engine)
    return candidates

