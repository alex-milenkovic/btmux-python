# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.obj.c
#   btech/mech.utils.c
#   btech/src/btech/weapons.h

"""Local registered building CF, repair callbacks and visible building queries."""
from core.events import EventType
from core.randomness import roll
from entities.map_objects import find_object, resolve_map, bits_for
from systems.movement_commands import notify
from systems.damage import external_effect

# weapons.h MissileHitTable is keyed by weapon identity, not only rack size.
# These source rows differ from the shared generic rack table. Keep the exact
# building-hit counts without changing the accepted ordinary missile resolver.
SOURCE_CLUSTER_ROWS={
    'CL.ATM-3': (1,1,1,1,2,2,2,2,3,3,3),
    'CL.ATM-9': (2,2,3,4,4,5,5,6,7,8,9),
    'IS.ELRM-10': (3,4,4,5,6,6,6,7,7,10,10),
    'IS.ELRM-15': (5,5,9,9,9,9,12,12,12,15,15),
    'IS.LR_DFM-10': (3,4,4,5,6,6,6,7,7,10,10),
    'IS.LR_DFM-15': (5,5,9,9,9,9,12,12,12,15,15),
    'IS.LRM-10': (3,4,4,5,6,6,6,8,8,10,10),
    'IS.LRM-15': (5,5,9,9,9,9,9,12,12,15,15),
    'IS.MRM-10': (2,3,4,5,6,6,6,8,8,10,10),
    'IS.RL-10': (3,4,4,5,6,6,6,8,8,10,10),
    'IS.RL-15': (5,5,9,9,9,9,9,12,12,15,15),
}


def get_building_cf(board): return (board.cf,board.cfmax) if board is not None else (0,0)
def get_regen_factor(board): return board.regen_factor if board is not None else 0
def get_cf(board):
    current,maximum=get_building_cf(board)
    return -1 if current==0 and maximum<=0 else current
def set_cf(board,current,maximum):
    if board is not None: board.cf,board.cfmax=current,maximum


def regen(event):
    board=event.data
    if board is None or not board.cf: return
    board.cf=min(board.cf+board.regen_factor,board.cfmax)
    if board.cf!=board.cfmax:
        if board._engine is None: raise ValueError('Building timer requires an owning engine')
        board._engine.events.schedule(120,EventType.BREGEN,regen,board)


def rebuild(event):
    board=event.data
    if board is not None and board.cf==0 and board.cfmax>0: board.cf=1


def start_regen(board):
    if board is None or not board.cf or board.cf==board.cfmax: return None
    if board._engine is None: raise ValueError('Building timer requires an owning engine')
    return board._engine.events.schedule(120,EventType.BREGEN,regen,board)


def structure_name(board,obj):
    interior=resolve_map(board,obj.obj)
    world=getattr(getattr(board,'_engine',None),'personnel',None)
    target=world.objects.get(obj.obj,interior) if world is not None else interior
    if target is None: return None
    name=getattr(target,'object_name',getattr(target,'name',''))
    from systems.notifications import MBUF_SIZE
    return ('the '+name).encode('utf8')[:MBUF_SIZE-1].decode('utf8',errors='ignore')


def damage_cf(unit,obj,current,maximum,damage):
    interior=resolve_map(unit.map,obj.obj)
    amount=min(current,damage)
    set_cf(interior,current-amount,maximum)
    name=structure_name(unit.map,obj)
    destroyed=amount==current
    ending=', destroying it!' if destroyed else '.'
    notify(unit,f'You hit {name} for {amount} points of damage{ending}')
    message=f'{name[0].upper()+name[1:]} is hit for {amount} '+('more ' if destroyed else '')+f'points of damage{ending}'
    from systems.notifications import room_notify
    room_notify(interior,message,exception=interior._id)
    if destroyed:
        from systems.sensors import los_broadcast
        los_broadcast(unit,f'hits {name}, destroying it!')
    if current==maximum or destroyed: start_regen(interior)
    return amount


def missile_count(unit,weapon):
    from entities.weapon import WeaponFlags,MISSILE_HIT_TABLE
    from systems.ecm import angel_ecm_disturbed
    from systems.ammo_dump import AMMO_FULL_SALVO
    rack=AMMO_FULL_SALVO.get(weapon.name)
    if rack is None: return None
    # STREAK is a special flag, so test special&STREAK instead of the
    # source's impossible weapon-type comparison.
    throw=12 if weapon.special&WeaponFlags.STREAK and not angel_ecm_disturbed(unit) else roll('building_cluster')
    if weapon.name in SOURCE_CLUSTER_ROWS: return SOURCE_CLUSTER_ROWS[weapon.name][throw-2]
    return 1 if rack==1 else MISSILE_HIT_TABLE.get(throw,{}).get(rack)


def hit_building(unit,x,y,weapon_idx,damage=0):
    board=unit.map
    if board is None or not board.valid(x,y): return 0
    obj=find_object(board,x,y,4)
    interior=resolve_map(board,obj.obj) if obj else None
    if interior is None: return 0
    if not damage:
        from entities.weapon import get_weapon_by_index,WeaponType
        weapon=get_weapon_by_index(weapon_idx)
        if weapon is None: raise ValueError('invalid building weapon index')
        damage=weapon.damage
        if weapon.weapon_type==WeaponType.TMISSILE:
            count=missile_count(unit,weapon)
            if count is None: return 0
            damage*=count
    if not damage: return 0
    if board.buildflag&2 or interior.buildflag&1:
        notify(unit,'Your shot only scratches the paint!')
        return 0
    if not interior.cf: return 0
    return damage_cf(unit,obj,interior.cf,interior.cfmax,damage)


def perception(unit,modifier):
    from systems.experience import perception as perceive
    return perceive(unit,modifier)


def query(unit,x,y,step=False):
    board=unit.map
    obj=find_object(board,x,y,4) if board is not None and board.valid(x,y) else None
    interior=resolve_map(board,obj.obj) if obj else None
    if step:
        bits=bits_for(board,False) if board is not None else None
        if interior is None or unit.z!=board.base_elevation(x,y) or bits is None or not bits.query(x,y,2) or interior.buildflag&4: return None
        if interior.buildflag&20 and not perception(unit,0): return None
    else:
        from physics.hexmath import find_range3d
        hidden=interior is None or interior.buildflag&16
        if not hidden and interior.buildflag&20:
            hidden=not perception(unit,int(find_range3d(unit.x,unit.y,unit.z,x,y,0)+.95))
        if hidden:
            notify(unit,'The sensors detect no building in the hex!')
            return None
    name=structure_name(board,obj)
    name=name[0].upper()+name[1:]
    notify(unit,f'{name} has CF of {interior.cf}.' if step else f"{name}'s CF is {interior.cf}.")
    return interior.cf
