# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/hudinfo.c
#   btech/mech.maps.c
# Historical Aerospace sources:
#   btech/ds.turret.c

"""Hex sketches, long-range paired rows and local navigation displays."""
import re
from entities.mech import UnitType as U, MoveType as M, CritStatus as C, MechStatus as S
from entities.map import get_terrain_name_base
from physics.hexmath import hex_to_float,find_xy,float_to_hex,find_bearing,ZSCALE
from systems.targeting import contact_target,fa_mech_range,find_range
from systems.los import in_line_of_sight,in_line_of_sight_nb,calculate_los_map
from systems.movement_commands import c_number,historical_aircraft
from systems.observation import guard
from core.attributes import player_preference
from core.effects import notify_actor
from systems.observation import response
from systems.armor_display import plain

DEFAULT_PALETTE='BbWXYyRWWWXGgbRhYRnGR'


def palette(text):
    warnings=[]
    if len(text)>21:warnings=['Invalid MAPCOLOR attribute!']
    else:
        invalid=next((c for c in text if c not in 'fFiIHxXrRgGyYbBmMcCwWhn'),None)
        if invalid:warnings=[f"Invalid character '{invalid}' in MAPCOLOR attribute!"]
    if warnings:warnings.append('Using default: '+DEFAULT_PALETTE);text=''
    return [c.replace('h','H').replace('n','') for c in text+DEFAULT_PALETTE[len(text):]],warnings


def terrain_color(terrain,elevation,colors):
    if terrain=='?':return colors[1]
    if terrain=='~':return colors[0 if elevation<2 else 1]
    index={'`':11,'"':12,'@':2,'#':3,'%':4,'^':5,'&':6,'-':7,'=':8,'+':9,':':10,'$':13,'}':4}.get(terrain)
    return colors[index] if index is not None else ''


def color_rows(rows,colors):
    result=[];current=''
    for row in rows:
        text=''
        for char in row:
            hacks={'¢':('~',colors[1]),'¡':('X',colors[20]),'\xa0':('O',colors[19]),'$':('X',colors[18]),'!':('/',colors[14]),'|':('\\',colors[14]),',':('_',colors[14])}
            if char in hacks:char,new=hacks[char]
            elif char=='?':new=colors[13]
            elif char=='*':new=colors[15]
            elif char.islower():new=colors[16]
            elif char.isupper():new=colors[17]
            elif char.isdigit():new=current
            else:new=terrain_color(char,0,colors)
            if new.isupper()!=current.isupper():
                if new.isupper():text+='%ch'
                else:text+='%cn';current=''
            if new.lower()!=current.lower():
                text+='%cn' if not new else '%cn%ch' if new=='H' else '%c'+new.lower()
                current=new
            text+=char
        if current:text+='%cn'
        result.append(text)
    return result


def forced_los(unit):return bool(getattr(unit.map,'dark',False) or unit.map.flags&32 or unit.unit_type==U.MW and getattr(unit._engine,'mw_losmap',False))


def select_center(unit,args,maximum):
    if not args:return unit.x,unit.y
    if len(args)==1:
        target=contact_target(unit,args[0])
        if target is None or not in_line_of_sight(unit,target,target.x,target.y,fa_mech_range(unit,target)):raise ValueError('No such target.')
        if abs(int(fa_mech_range(unit,target)))>maximum:raise ValueError('Target is out of scanner range.')
        return target.x,target.y
    if len(args)==2:
        bearing,distance=c_number(args[0],True),c_number(args[1])
        if not unit.crit_status&C.OBSERVATORIC and abs(int(distance))>maximum:raise ValueError('Those coordinates are out of sensor range!')
        return float_to_hex(*find_xy(unit.fx,unit.fy,bearing,distance))
    raise ValueError('Invalid number of parameters!')


def visible_units(unit):
    return [u for u in unit.map.mechs_on_map if hasattr(u,'sections') and getattr(u,'valid_object',True) and (u is unit or in_line_of_sight(unit,u,u.x,u.y,fa_mech_range(unit,u)))]


def los_rectangle(unit,sx,sy,width,height):
    result=calculate_los_map(unit.map,unit,sx,sy,width,height) if width>0 and height>0 else None
    for cell in getattr(unit,'display_los_cells',[]):
        if result and result.contains(cell['x'],cell['y']):result.cells[result.index(cell['x'],cell['y'])]=cell['flags']
    return result


def los_flag(los,x,y):return los.cells[los.index(x,y)] if los and los.contains(x,y) else 0 if los else 7


def hud_tactical(unit,text):
    from systems.combat_commands import parse_attributes
    board=unit.map;args=parse_attributes(text,4)
    if not unit.lrs_range:return response(False,'Your system seems to be inoperational')
    if board is None:return response(False,'You are on no map')
    if len(args) not in (1,3,4):return response(False,'Invalid arguments')
    if len(args)==4 and args[3]!='l':return response(False,'Invalid fourth argument')
    try:
        cx,cy=select_center(unit,args[1:3],unit.lrs_range) if len(args)>1 else (unit.x,unit.y)
    except ValueError:return response(False,'Out of range')
    height=int(c_number(args[0],True))
    if not 1<=height<=40:return response(False,'Invalid 1st argument')
    if not board.valid(cx,cy):return response(False,'Out of range')
    height=min(height,2*unit.lrs_range,board.map_height)
    sy,ey=max(0,cy-height//2),min(board.map_height,cy+height//2)
    sx,ex=max(0,cx-35),min(board.map_width,cx+35)
    los=los_rectangle(unit,sx,sy,ex-sx,ey-sy) if height>1 and (len(args)==4 or forced_los(unit)) else None
    show=getattr(unit._engine,'hudinfo_show_mapinfo',2)
    hidden=not show or show==1 and getattr(board,'in_character',False)
    start=[sx,sy,ex-1,ey-1,-1 if hidden else board._id,-1 if hidden else board.name,-1,board.map_width,board.map_height]
    rows=[]
    for y in range(sy,ey):
        line=''
        for x in range(sx,ex):
            flags=los_flag(los,x,y)
            line+=(board.terrain(x,y).replace(' ','.') if flags&2 else '?')+(chr(48+board.elevation(x,y)) if flags&4 else '?')
        rows.append(f'{y},'+line)
    return response(start=start,rows=rows)


def sketch(unit,cx,cy,width,height,mode='',navigate=False,dolos=False,color=False,*,board=None,labels=None):
    board=unit.map if board is None else board
    labels=(4 if navigate else 3) if labels is None else labels
    if labels&4:navigate=True;labels=0
    if not mode:mode=next((m for bit,m in ((8,'c'),(16,'t'),(32,'b'),(128,'m'),(64,'u')) if labels&bit),'')
    width=min(40,width);height=min(24,height)
    sx,sy=cx-width//2,cy-height//2
    if not navigate:
        sx=max(0,min(sx,board.map_width-width));sy=max(0,min(sy,board.map_height-height))
        width=min(width,board.map_width);height=min(height,board.map_height)
    odd=sx&1;left=4 if labels&1 else 0;top=odd if navigate else 3 if labels&2 else 0
    cols=width*3+1;stride=cols+left+(3 if labels&1 else 0)
    rows=[list(' '*(stride if i<top else cols+left)) for i in range(height*2+1+top)]
    for y in range(height*2+1):
        pattern='\\][/][' if (y+odd)%2==0 else '/][\\]['
        rows[y+top][left:left+cols]=list((pattern*(width+1))[:cols])
    def offset(x,y):return top+(y-sy)*2+1-(x&1),left+(x-sx)*3+1
    lx,ly=max(0,sx),max(0,sy);ex=min(board.map_width,sx+width);ey=min(board.map_height,sy+height)
    los=los_rectangle(unit,lx,ly,ex-lx,ey-ly) if dolos and unit is not None else None
    cells=[]
    for y in range(ly,ey):
        for x in range(lx,ex):
            flags=los_flag(los,x,y);terrain=board.terrain(x,y) if flags&2 else '$';elev=board.elevation(x,y) if flags&4 else 15
            if not flags&1:terrain='X';elev=40
            upper,lower={'~':('¢','¢') if color and elev>=2 else ('~','~'),'`':('`','`'),' ':(' ','_'),'?':('~','+'),'/':('#','+'),'$':('?','?')}.get(terrain,(terrain,terrain))
            from entities.map import FIRE,SMOKE
            if mode=='u' and terrain in (FIRE,SMOKE):lower=board.rterrain(x,y)
            ry,rx=offset(x,y)
            rows[ry][rx:rx+2]=[upper,upper];rows[ry+1][rx:rx+2]=[lower,chr(48+elev) if elev else lower]
            cells.append(dict(x=x,y=y,terrain=board.terrain(x,y) if flags&3==3 else None,
                elevation=board.elevation(x,y) if flags&5==5 else None,
                terrain_visible=flags&3==3,elevation_visible=flags&5==5,flags=flags,offset=[ry,rx]))
    if labels&1:
        for x in range(width):
            if not 0<=sx+x<=999:continue
            for i,char in enumerate(f'{sx+x:3d}'):
                if i<len(rows):rows[i][left+1+x*3]=char
    if labels&2:
        for y in range(height):
            if not 0<=sy+y<=999:continue
            row=top+1+y*2;rows[row][:4]=f'{sy+y:3d} '
            right=stride-3
            rows[row].extend(' '*max(0,right-len(rows[row])))
            rows[row][right:right+3]=f'{sy+y:3d}'
    if unit is not None and mode in ('c','t','b','m'):
        if sx<=unit.x<sx+width and sy<=unit.y<sy+height:
            ry,rx=offset(unit.x,unit.y);rows[ry][rx]='*'
    if mode in ('c','t','m','b') and (unit is not None or mode in ('c','t')):
        from systems.los import get_adj_hex
        for cell in cells:
            x,y=cell['x'],cell['y'];ry,rx=cell['offset']
            if mode=='b':
                from physics.aerospace import improper_lz
                bad=improper_lz(unit,x,y);rows[ry+1][rx]=('¡' if bad else '\xa0') if color else ('X' if bad else 'O')
                continue
            if rows[ry][rx]=='*':rows[ry][rx+1]='*'
            elif rows[ry+1][rx+1].isdigit():rows[ry][rx+1]=rows[ry+1][rx+1]
            if mode=='m':
                from entities.map_objects import first_object
                from systems.mines import MineType
                mine=next((m for m in board.map_objects[3] if (m.x,m.y)==(x,y)),None)
                fx,fy=hex_to_float(x,y);distance=find_range(unit.fx,unit.fy,unit.fz,fx,fy,board.base_elevation(x,y)*ZSCALE)
                marker=mine and mine.type!=MineType.TRIGGER and in_line_of_sight_nb(unit,None,x,y,distance)
                rows[ry+1][rx:rx+2]=list('<>' if marker else '  ')
            else:
                threshold=3 if mode=='c' else 2;elev=board.base_elevation(x,y)
                for direction,dy,dx,glyph in [(4,1,-1,'|'),(3,1,0,','),(2,1,2,'!')]:
                    nx,ny=get_adj_hex(x,y,direction)
                    valid=lx<=nx<ex and ly<=ny<ey
                    cliff=valid and abs(board.base_elevation(nx,ny)-elev)>=threshold
                    if direction==3:rows[ry+1][rx:rx+2]=list(',,' if cliff else '__')
                    elif cliff:rows[ry+dy][rx+dx]=glyph
    if unit is not None and mode not in ('c','t','b'):
        from physics.aerospace import is_ds,adjacent
        from systems.dropships import bearing_mod,bay_number
        from systems.hud import identity
        for other in visible_units(unit):
            x,y=other.x,other.y
            def ds_hex(tx,ty,glyph):
                if not sx<=tx<sx+width or not sy<=ty<sy+height:return
                ry,rx=offset(tx,ty)
                if not rows[ry][rx].isalpha() and rows[ry][rx]!='*':rows[ry][rx:rx+2]=[glyph,glyph]
                rows[ry+1][rx]=glyph
                if not rows[ry+1][rx+1].isdigit():rows[ry+1][rx+1]=glyph
            large=is_ds(other) and not other.specials2&0x80000 and (other.z>=300 and other is not unit or other.status&S.LANDED or not other.is_started)
            if large:
                for direction in range(6):
                    tx,ty=adjacent(x,y,direction);ds_hex(tx,ty,'@' if bay_number(other,(direction-bearing_mod(other))%6)>=0 else '=')
                ds_hex(x,y,'$' if color else 'X')
            if not sx<=x<sx+width or not sy<=y<sy+height:continue
            ry,rx=offset(x,y)
            if (large or other is unit) and rows[ry][rx].isalpha():continue
            friend=other.team==unit.team and in_line_of_sight_nb(unit,other,x,y,0)
            rows[ry][rx:rx+2]=list('**' if other is unit else identity(other,friend))
    if navigate:
        n=width//2
        if odd:rows.pop()
        for i in range(n):
            length=(n-i-1)*3+1;r=rows[i+1];r[:length]=' '*length;r[length:length+2]='__';r[cols-length-2:cols-length]='__';del r[cols-length:]
            r=rows[-i-1];length=(n-i)*3;r[:length]=' '*length;del r[cols-length:]
        rows[0]=list(' '*(n*3+1)+'__')
    return [''.join(r) for r in rows],cells,[sx,sy,width,height]


def tactical(unit,text='',navigate=False,caller=None,historical=None):
    caller=caller if caller is not None else getattr(unit,'command_actor',unit.pilot)
    historical=historical_aircraft(unit) if historical is None else historical
    error=guard(unit,caller)
    if error is not None:return response(False,error)
    if navigate and (unit.map.map_width<=0 or unit.map.map_height<=0):
        return response(False,'Nothing to see on this map, move along.')
    from systems.combat_commands import parse_attributes
    maximum=unit.tac_range;args=parse_attributes(text,4);mode=''
    if not navigate and not maximum:return response(False,'Your system seems to be inoperational.')
    if not navigate and args and len(args[0])==1 and args[0].isalpha():mode=args.pop(0).lower()
    if mode and mode not in (('c','t','l','b') if historical else ('c','t','l','b','u','m')):return response(False,'Invalid tactical map flag.')
    dolos=forced_los(unit) or mode=='l'
    if dolos and mode in ('c','t','b'):return response(False,"You can't see that much here!")
    try:cx,cy=select_center(unit,args,maximum)
    except ValueError as error:return response(False,str(error))
    warnings=[]
    width,height=21,14
    tacsize=player_preference(unit,caller,'A_TACSIZE','tacsize')
    if not navigate and tacsize:
        from systems.map_management import scan_ints
        values,_=scan_ints(str(tacsize),2)
        if len(values)==2 and 5<=values[0]<=24 and 5<=values[1]<=40:height,width=values
        else:
            warnings.append("Illegal Tacsize attribute. Must be in format 'Height Width' . Height : 5-24 Width : 5-40")
            notify_actor(unit,caller,warnings[-1])
    colors,color_warnings=palette(player_preference(unit,caller,'A_MAPCOLOR','mapcolor'));warnings.extend(color_warnings)
    for warning in color_warnings:notify_actor(unit,caller,warning)
    width,height=(5,5) if navigate else (min(width,2*maximum,unit.map.map_width),min(height,2*maximum,unit.map.map_height))
    color=bool(player_preference(unit,caller,'A_ANSIMAP','ansimap',False))
    rows,cells,window=sketch(unit,cx,cy,width,height,mode,navigate,dolos,color)
    if color:rows=color_rows(rows,colors)
    if navigate:
        headers=['              0','         ___________',f'        /           \\          Location:{unit.x:4d},{unit.y:4d}, {unit.z:3d}',f'  300  /             \\  60     Terrain: {get_terrain_name_base(unit.map.terrain(unit.x,unit.y)):>14}', '      /               \\','     /                 \\',f'270 (                   )  90  Speed:           {unit.speed:6.1f}',f'     \\                 /       Vertical Speed:  {unit.vertical_speed:6.1f}',f'      \\               /        Heading:           {unit.facing:4d}','  240  \\             /  120','        \\___________/']
        rows=[h.ljust(57)+r for h,r in zip(headers,rows)]+['                      ','             180']
        from systems.targeting import navigate_sketch_mechs
        rows=navigate_sketch_mechs(unit,unit.map,cx,cy,rows)
    for row in rows:notify_actor(unit,caller,row)
    return response(message='\n'.join(warnings+rows),rows=rows,lines=warnings+rows,cells=cells,window=window,center=[cx,cy],warnings=warnings,kind='navigate' if navigate else 'tactical',notified=True)


def lrs_glyph(viewer,other,friend):
    if viewer is other:return '*'
    char={M.FLY:'b',M.BIPED:'b',M.QUAD:'q',M.TRACK:'t',M.WHEEL:'w',M.HOVER:'h',M.VTOL:'v',M.HULL:'n',M.SUB:'s',M.FOIL:'f'}.get(other.move_type,'d' if other.unit_type in (U.DS,U.SPHEROID_DS) else 'u')
    return char if friend else char.upper()


def lrs(unit,text,caller=None):
    caller=caller if caller is not None else getattr(unit,'command_actor',unit.pilot)
    error=guard(unit,caller)
    if error is not None:return response(False,error)
    from systems.combat_commands import parse_attributes
    color_enabled=bool(player_preference(unit,caller,'A_ANSIMAP','ansimap',False))
    args=parse_attributes(text,4)
    if not unit.lrs_range:return response(False,'Your system seems to be inoperational.')
    if not args:return response(False,'Invalid number of parameters!')
    token=args.pop(0);mode=token[0].lower()
    try:cx,cy=select_center(unit,args,unit.lrs_range)
    except ValueError as error:return response(False,str(error))
    if mode not in 'mectl hs'.replace(' ',''):return response(False,f"Unknown LRS sensor type '{token}'!")
    warnings=[];height=11
    lrsheight=player_preference(unit,caller,'A_LRSHEIGHT','lrsheight')
    if lrsheight:
        height=int(c_number(str(lrsheight),True))
        if not 10<=height<=40:
            warnings.append('Illegal LRSHeight attribute.  Must be between 10 and 40')
            notify_actor(unit,caller,warnings[-1]);height=11
    board=unit.map;height=min(height,2*unit.lrs_range,board.map_height)
    if height%2==0:height+=1
    colors,color_warnings=palette(player_preference(unit,caller,'A_MAPCOLOR','mapcolor'));warnings.extend(color_warnings)
    for warning in color_warnings:notify_actor(unit,caller,warning)
    sx=max(0,cx-35);ex=sx+70
    if ex>=board.map_width:ex=board.map_width-1;sx=max(0,ex-70)
    sy=max(0,cy-height//2);ey=sy+height
    if ey>board.map_height:ey=board.map_height;sy=max(0,ey-height)
    los=los_rectangle(unit,sx,sy,ex-sx,ey-sy) if forced_los(unit) or mode in 'lhs' else None
    peers=[other for other in visible_units(unit) if other is unit or sx<=other.x<=ex and sy<=other.y<=ey] if mode in 'ms' else []
    for i in range(len(peers)-1):
        for j in range(i+1,len(peers)):
            if (peers[i].y,peers[i].x)>(peers[j].y,peers[j].x):peers[i],peers[j]=peers[j],peers[i]
    rows=['    '+''.join(f'{x:3d}'[i] for x in range(sx,ex+1)) for i in range(3)]
    cells=[]
    previous=['','']
    def glyph(x,y,line):
        other=next((u for u in peers if (u.x,u.y)==(x,y)),None)
        flag=los_flag(los,x,y)
        friend=other is not None and other.team==unit.team and bool(in_line_of_sight_nb(unit,other,x,y,0))
        if other:value=lrs_glyph(unit,other,friend)
        elif not flag&1:value='X'
        elif not flag&(4 if mode in 'ech' else 2):value='?'
        elif mode in 'ech':value=str(board.elevation(x,y)) if board.elevation(x,y) or mode=='c' else ' '
        else:value=board.terrain(x,y)
        cells.append(dict(x=x,y=y,glyph=value,terrain=board.terrain(x,y) if flag&3==3 else None,
            elevation=board.elevation(x,y) if flag&5==5 else None,
            terrain_visible=flag&3==3,elevation_visible=flag&5==5,flags=flag))
        color=''
        if other:
            if color_enabled:color=colors[15 if other is unit else 16 if friend else 17]
        elif not flag&1:color='R'
        elif not flag&(4 if mode in 'ech' else 2):color=colors[13]
        elif mode=='c' or mode not in 'eh' and color_enabled:color=terrain_color(board.terrain(x,y),board.elevation(x,y),colors)
        # Raw early returns preserve previous color and the shared buffer.
        raw=(other is not None and not color_enabled or other is None and flag&1 and flag&(4 if mode in 'ech' else 2) and
             (mode in 'ech' and mode!='c' or mode not in 'ech' and (not color_enabled or value in ('','\0',' '))))
        if raw:return value
        text,previous[line]=colored_character(value,color,previous[line])
        return text
    odd=sx&1
    for y in range(sy,ey):
        upper=f'{y:3d} ';lower='    '
        for x in range(sx,ex,2):
            a=glyph(x+1-odd,y,0);b=glyph(x+odd,y,1)
            upper+=a+' ' if odd else ' '+a;lower+=' '+b if odd else b+' '
        x=sx+2*((ex-sx+1)//2)
        if x==ex:
            if odd:upper+=glyph(x,y,0);lower+=' '
            else:lower+=glyph(x,y,1)
        if color_enabled or mode=='c':
            upper+=('%cn' if previous[0] else '');lower+=('%cn' if previous[1] else '');previous[:]=['','']
        lower+=f' {y:<3d}';rows.extend([upper,lower])
    for row in rows:notify_actor(unit,caller,row)
    return response(message='\n'.join(warnings+rows),lines=warnings+rows,rows=rows,cells=cells,window=[sx,sy,ex,ey],center=[cx,cy],warnings=warnings,kind='lrs',notified=True)


_lrs_color_buffer=''


def colored_character(char,new,previous):
    """Source add_color retains its nine-byte payload across same-case changes."""
    global _lrs_color_buffer
    if new==previous:
        _lrs_color_buffer=char
        return char,new
    if not new or previous.isupper() and not new.isupper() or new=='H' and previous:_lrs_color_buffer='%cn'
    elif new.isupper() and not previous.isupper():_lrs_color_buffer='%ch'
    _lrs_color_buffer=(_lrs_color_buffer+('%c'+new.lower() if new else '')+char)[:9]
    return _lrs_color_buffer,new
