# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.dynamic.c
# Historical Aerospace sources:
#   btech/mech.restrict.c

"""Map roster slots, source removal/consistency and shared directed LOS storage."""
from entities.mech import MechStatus as S, UnitType as U
from systems.movement_commands import notify


class LOSCache(dict):
    """Keep the existing ID-keyed sensor API backed by the persisted slot matrix."""
    def __init__(self,board,values=()):
        self.board=board
        super().__init__()
        self.update(values)

    def slot(self,key):
        try: return tuple(getattr(self.board,'roster_ids',[]).index(identity) for identity in key)
        except ValueError: return None

    def __setitem__(self,key,value):
        positions=self.slot(key)
        if positions is not None:
            i,j=positions
            if i<len(self.board.slot_los) and j<len(self.board.slot_los[i]): self.board.slot_los[i][j]=value
        super().__setitem__(key,value)

    def __getitem__(self,key):
        positions=self.slot(key)
        if positions is not None and key in self:
            i,j=positions
            if i<len(self.board.slot_los) and j<len(self.board.slot_los[i]): return self.board.slot_los[i][j]
        return super().__getitem__(key)

    def get(self,key,default=None):
        return self[key] if key in self else default

    def update(self,values=(),**kwargs):
        for key,value in dict(values,**kwargs).items(): self[key]=value


def publish_los(board):
    count=len(board.roster_ids)
    values={(a,b):board.slot_los[i][j] for i,a in enumerate(board.roster_ids)
            for j,b in enumerate(board.roster_ids) if a>=0 and b>=0 and i<count and j<count}
    board.losinfo=values


def ensure_roster(board):
    """Adopt older public fixtures that supply only runtime roster objects."""
    if len(board.roster_ids)==len(board.mechs_on_map): return
    values=dict(board.losinfo or {})
    board.roster_ids=[unit._id if unit is not None else -1 for unit in board.mechs_on_map]
    count=len(board.roster_ids)
    board.mechflags=[getattr(unit,'mapflag',0) if unit is not None else 0 for unit in board.mechs_on_map]
    board.slot_los=[[0]*count for _ in range(count)]
    for slot,unit in enumerate(board.mechs_on_map):
        if unit is not None: unit.mapnumber=slot
    board.losinfo=values


def add(board,unit):
    from systems.ecm import mark_for_los_update
    from systems.map_conditions import update_conditions
    ensure_roster(board)
    if unit._id in board.roster_ids: return False
    slot=next((i for i,identity in enumerate(board.roster_ids) if identity<0),len(board.roster_ids))
    if slot==len(board.roster_ids):
        count=slot+1
        if count>255: raise ValueError('Unsupported source roster count above 255')
        board.roster_ids.append(-1); board.mechs_on_map.append(None); board.mechflags.append(0)
        board.slot_los=[row[:slot]+[0] for row in board.slot_los[:slot]]+[[0]*count]
    unit.map,unit.mapindex,unit.mapnumber=board,board._id,slot
    board.roster_ids[slot],board.mechs_on_map[slot],board.mechflags[slot]=unit._id,unit,0
    from systems.map_autopilot import set_title,wake
    set_title(board,unit)
    if unit.has_status(S.TOWED) and not any(peer is not None and peer.carrying==unit._id for peer in board.mechs_on_map):
        unit.clear_status(S.TOWED)
    publish_los(board)
    mark_for_los_update(unit)
    wake(board,unit)
    update_conditions(unit,board)
    if unit.unit_type in (U.DS,U.SPHEROID_DS):
        from core.effects import emit_channel
        emit_channel(board,'DSInfo',f'DS #{unit._id} has entered map #{board._id}')
    return True


def clear_los(unit):
    board=unit.map
    if board is None: return
    ensure_roster(board)
    slot=getattr(unit,'mapnumber',0)
    if not 0<=slot<len(board.roster_ids):
        board.external_effects.append({'service':'clear_mech_from_LOS','applied':False,'reason':'source slot out of bounds'})
        return
    from systems.targeting import lose_lock
    for i,peer in enumerate(board.mechs_on_map):
        board.slot_los[slot][i]=board.slot_los[i][slot]=0
        if peer is not None and i!=slot and peer.has_status(S.LOCK_TARGET) and peer.target==unit._id:
            notify(peer,'Weapon system reports the lock has been lost.')
            lose_lock(peer,peer._engine)
    if unit.has_status(S.LOCK_MODES):
        notify(unit,'Weapon system reports the lock has been lost.')
        lose_lock(unit,unit._engine)
    publish_los(board)


def remove(board,unit):
    ensure_roster(board)
    clear_los(unit)
    unit.mapindex=-1
    slot=getattr(unit,'mapnumber',0)
    if not 0<=slot<len(board.roster_ids) or board.roster_ids[slot]!=unit._id:
        from core.effects import send_error
        identity=board.roster_ids[slot] if 0<=slot<len(board.roster_ids) else -1
        send_error(board,f'Map indexing error for mech #{unit._id}: Map index {slot} contains data for #{identity} instead.')
        slot=next((i for i,identity in enumerate(board.roster_ids) if identity==unit._id),None)
    unit.mapnumber=0
    if slot is not None:
        board.roster_ids[slot]=-1; board.mechflags[slot]=0; board.mechs_on_map[slot]=None
        if slot==len(board.roster_ids)-1:
            board.roster_ids.pop(); board.mechflags.pop(); board.mechs_on_map.pop()
    if unit.has_status(S.TOWED):
        for peer in board.mechs_on_map:
            if peer is not None and peer.carrying==unit._id:
                peer.carrying=-1; unit.clear_status(S.TOWED); break
    unit.num_seen=0
    unit.map=None
    publish_los(board)
    if unit.unit_type in (U.DS,U.SPHEROID_DS):
        from core.effects import emit_channel
        emit_channel(board,'DSInfo',f'DS #{unit._id} has left map #{board._id}')


def remove_from_all(unit,objects,except_id=None):
    for board in objects:
        if getattr(board,'xcode_type',None)!='MAP' or board._id==except_id: continue
        ensure_roster(board)
        for i,identity in enumerate(board.roster_ids):
            if identity==unit._id: board.roster_ids[i]=-1; board.mechs_on_map[i]=None
        publish_los(board)


def consistency(unit,objects):
    maps={board._id:board for board in objects if getattr(board,'xcode_type',None)=='MAP'}
    board=maps.get(getattr(unit,'mapindex',-1))
    from core.effects import diagnostic
    if board is None:
        if getattr(unit,'mapindex',-1)>0:
            unit.mapindex=-1; unit.map=None
            diagnostic(unit,f'#{unit._id} on nonexistent map - removing..')
        return
    ensure_roster(board)
    slot=getattr(unit,'mapnumber',0)
    if not 0<=slot<len(board.roster_ids):
        unit.mapindex=-1; unit.map=None
        remove_from_all(unit,objects)
        diagnostic(unit,f'#{unit._id} on invalid map - removing.. (#1)')
    elif board.roster_ids[slot]!=unit._id:
        diagnostic(unit,f'#{unit._id} on invalid map - removing .. (#2) -- mapindex: {unit.mapindex} mapnumber: {slot} mechsOnMap: {board.roster_ids[slot]}')
        unit.mapindex=-1; unit.map=None
        remove_from_all(unit,objects)
    else: remove_from_all(unit,objects,board._id)


def eliminate_empties(board):
    if board is None: return
    ensure_roster(board)
    last=next((i for i in range(len(board.roster_ids)-1,-1,-1) if board.roster_ids[i]>0),None)
    count=0 if last is None else last+1
    oldcount=len(board.roster_ids)
    if count==oldcount: return
    from core.effects import diagnostic,notify_actor
    diagnostic(board,f'Map #{board._id} contains empty entries ; removing {oldcount-count} ({oldcount}->{count})')
    if last is None: return
    board.roster_ids=board.roster_ids[:count]; board.mechs_on_map=board.mechs_on_map[:count]
    board.mechflags=board.mechflags[:count]; board.slot_los=board.slot_los[:count]
    publish_los(board)
    store=getattr(board,'inventory_store',None) or getattr(board._engine,'inventory_store',None)
    if store is None:
        from systems.economic_inventory import InventoryStore
        store=InventoryStore()
        if board._engine is not None:board._engine.inventory_store=store
    if board._id not in store.records:store.register(board._id,board,ECONPARTS=getattr(board,'econparts',''))
    result=store.cleanup(board._id)
    notify_actor(board,1,'Fixing done. Original length: {old_length}. New length: {new_length}. Items in new: {items}. Unique items in new: {kinds}.'.format(**result))
