# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/hudinfo.c
#   btech/mech.contacts.c

"""Source contact row formatting and visible local building records."""
from entities.map_objects import resolve_map
from systems.dropships import enter_lock
from systems.los import in_line_of_sight,MECHLOSFLAG_BLOCK,MECHLOSFLAG_SEESP,MECHLOSFLAG_SEESS
from systems.targeting import find_range
from physics.hexmath import hex_to_float,find_bearing,in_weapon_arc,ZSCALE
from systems.network_reports import move_type,arc_label
from systems.armor_display import plain


def building_contacts(unit):
    rows=[];blocked=[]
    if unit.map is None:return rows,blocked
    for obj in unit.map.map_objects[4]:
        board=resolve_map(unit.map,obj.obj)
        if board is None:continue
        fx,fy=hex_to_float(obj.x,obj.y);z=unit.map.base_elevation(obj.x,obj.y)
        distance=find_range(unit.fx,unit.fy,unit.fz,fx,fy,(z+1)*ZSCALE)
        los=in_line_of_sight(unit,None,obj.x,obj.y,distance)
        if not los or los&MECHLOSFLAG_BLOCK or board.buildflag&16:continue
        passed=enter_lock(unit,board)
        if passed is None:blocked.append(f'MUX LENTER lock for building #{board._id}');continue
        locked=not passed;hidden=bool(board.buildflag&(4|16));safe=bool(board.buildflag&8);cs=bool(board.buildflag&1)
        if locked and hidden:continue
        status=('X' if safe or locked and cs else 'x' if locked else 'C' if cs else ' ')+('H' if hidden else ' ')
        hud=('C' if cs else '')+('E' if locked else 'F')+('H' if hidden else '')+('X' if safe or locked and cs else 'x' if locked else '')
        rows.append(dict(building=True,id=board._id,name=getattr(board,'mech_name','') or plain(board.name) or '-',x=obj.x,y=obj.y,z=z,range=distance,bearing=find_bearing(unit.fx,unit.fy,fx,fy),arcs=in_weapon_arc(unit,fx,fy),cf=board.cf,max_cf=board.cfmax,status=status,hud_status=hud,locked=locked,sort_range=distance+20000,sees_primary=bool(los&MECHLOSFLAG_SEESP),sees_secondary=bool(los&MECHLOSFLAG_SEESS)))
    return rows,blocked


def _contact_lines(viewer,row,hud,brief):
    from systems.observation import weapon_arc
    if row.get('building'):
        r=row;ps=('P' if r['sees_primary'] else ' ');ss=('S' if r['sees_secondary'] else ' ');arc=weapon_arc(r['arcs'])
        if hud:return [f"#HUDINFO:CON#{'E' if r['locked'] else 'F'},{ps},{ss},{arc},{r['name']:21.21s},{r['x']:3d},{r['y']:3d},{r['z']:3d},{r['range']:4.1f},{r['bearing']:3d},{r['cf']:4d},{r['max_cf']:4d},{r['status']}"]
        return [(' %ch%cy' if r['locked'] else '').lstrip()+f"{ps}{ss}{arc} {r['name']:23.23s} x:{r['x']:3d} y:{r['y']:3d} z:{r['z']:2d} r:{r['range']:4.1f} b:{r['bearing']:3d} CF:{r['cf']:4d} /{r['max_cf']:4d} S:{r['status']}"+('%c' if r['locked'] else '')]
    r=row;ps='P' if r['sees_primary'] else ' ';ss='S' if r['sees_secondary'] else ' ';move=move_type(r['move_type'])
    if brief:
        if hud:return [f"#HUDINFO:CON#{'T' if r['locked_by_me'] else 'F' if r['friend'] else 'E'},{ps},{ss},{r['arc']},{r['contact_id']},{move[0]},{r['name']:12.12s},{r['x']:3d},{r['y']:3d},{r['z']:3d},{r['range']:4.1f},{r['bearing']:3d},{r['speed']:4.1f},{r['heading']:3d},{r['status']}"]
        prefix='%ch%cr' if r['locked_by_me'] else '%ch%cy' if not r['friend'] else ''
        return [prefix+f"{ps}{ss}{r['arc']}[{r['contact_id']}]{move[0]} {r['name']:12.12s} x:{r['x']:3d} y:{r['y']:3d} z:{r['z']:3d} r:{r['range']:4.1f} b:{r['bearing']:3d} s:{r['speed']:5.1f} h:{r['heading']:3d} S:{r['status']}"+('%c' if prefix else '')]
    lines=[f"[{r['contact_id']}] {r['name']:17s}  Tonnage: {r['tonnage']}",f"      Range: {r['range']:.1f} hex\tBearing: {r['bearing']} degrees",f"      Speed: {r['speed']:.1f} KPH\tHeading: {r['heading']} degrees",f"      X, Y: {r['x']:3d}, {r['y']:3d} \tHeat: {r['heat']:.0f} deg C.",f'      Movement Type: {move}',f"      Mech is in {arc_label(viewer,r['arcs'])} Arc"]
    if r['destroyed']:lines.append('      Mech Destroyed')
    if not r['started']:lines.append('      Mech Shutdown')
    if r['fallen']:lines.append('      Mech has Fallen!')
    if r['jumping']:lines.append(f"      Mech is Jumping!\tJump Heading: {r['jump_heading']}")
    return lines+[' ']

def contact_lines(viewer,row,hud,brief):
    lines=_contact_lines(viewer,row,hud,brief)
    return [line[:99] if row.get('building') or brief or i<5 else line for i,line in enumerate(lines)]
