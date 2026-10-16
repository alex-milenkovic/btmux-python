# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.c
#   btech/map.obj.c
#   btech/mech.notify.c

"""Source map administration and text files; filesystem paths are adapter inputs."""
import os
import re
from entities.map import GameMap, GRASSLAND, FIRE, SMOKE, get_terrain_name_base, make_bridges
from entities.map_objects import delete_objects, find_object


def arguments(text,limit):
    return [word for word in re.split('[ \t]+',text.strip(' \t')) if word][:limit]


def atoi(text):
    match=re.match(r'\s*([+-]?\d+)',text)
    return int(match[1]) if match else 0


def readnum(text):
    value=atoi(text)
    if value==0 and text!='0': raise ValueError('Invalid integer')
    return value


def scan_ints(text,count,pos=0):
    values=[]
    for _ in range(count):
        match=re.match(r'\s*([+-]?\d+)',text[pos:])
        if not match: break
        values.append(int(match[1])); pos+=match.end()
    return values,pos


def report(board,message,actor=1):
    from core.effects import notify_actor
    board.map_messages.append(message)
    notify_actor(board,actor,message)
    return message


def error(board,message,channel="MapErrors"):
    if not hasattr(board,'map_errors'): board.map_errors=[]
    board.map_errors.append(message)
    from core.effects import emit_channel
    emit_channel(board,channel,message)


def grid_header(text):
    dimensions,pos=scan_ints(text,2)
    if len(dimensions)==2:
        while pos<len(text) and text[pos].isspace(): pos+=1
    return dimensions,pos


def rows(text,pos,height):
    for _ in range(height):
        end=text.find('\n',pos,pos+2001)
        end=min(pos+2001,len(text)) if end<0 else end+1
        yield text[pos:end].split('\0',1)[0]
        pos=end
    # Expose the file cursor after the final fgets without re-scanning rows.
    return pos


def check_text(text,board=None,name=''):
    dimensions,pos=grid_header(text)
    if len(dimensions)!=2 or any(not 1<=d<=1000 for d in dimensions):
        if board is not None: error(board,f'Map #{board._id}: Invalid height and or/width on {name}')
        return -2
    width,height=dimensions
    if not all(len(row)>=2*width for row in rows(text,pos,height)):
        if board is not None: error(board,f'Map #{board._id}: Mapfile possibly corrupt and/or height/width flipped. Height != what was read in {name}')
        return -3
    return 1


def check_file(path,board=None):
    try:
        with open(path,encoding='latin1',newline='') as stream: return check_text(stream.read(),board,os.path.basename(path))
    except OSError: return -1


def load_text(board,text,name):
    from physics.environment import cancel,clear_layers
    cancel(board);clear_layers(board)
    delete_objects(board)
    board._grid_failed=True
    board._loaded_rows=0
    dimensions,pos=grid_header(text)
    if len(dimensions)!=2 or any(not 1<=d<=1000 for d in dimensions):
        error(board,f'Map #{board._id}: Invalid height and/or width')
        width,height=21,11
    else: width,height=dimensions
    board._terrain=[[GRASSLAND]*width for _ in range(height)]
    board._elev=[[0]*width for _ in range(height)]
    for y in range(height):
        end=text.find('\n',pos,pos+2001)
        end=min(pos+2001,len(text)) if end<0 else end+1
        row=text[pos:end].split('\0',1)[0]; pos=end
        if len(row)<2*width:
            error(board,f'Error: EOF reached prematurely. (x{width if y else 0} != {width} || y{y} != {height})')
            return -2
        for x in range(width):
            terrain,elevation=row[2*x],ord(row[2*x+1])-48
            if not 0<=elevation<=9: raise ValueError('Unsupported source coding elevation outside 0..9')
            if terrain==FIRE: board.flags|=8
            elif terrain in ('>',':','.'): terrain=GRASSLAND
            elif terrain=="'": terrain='`'
            if get_terrain_name_base(terrain)=='Unknown':
                error(board,f"Map #{board._id}: Invalid terrain at {x},{y}: '{terrain}'")
                terrain=GRASSLAND
            # Source SetMap writes packed grid data without UpdateMechsTerrain.
            board._terrain[y][x],board._elev[y][x]=terrain,elevation
        board._loaded_rows=y+1
    board.grav,board.temp=100,20
    trailer=re.match(r'\s*([+-]?\d+):',text[pos:])
    if trailer:
        values,_=scan_ints(text,2,pos+trailer.end())
        if len(values)==2:
            from entities.map_storage import source_int,signed_value
            flags,gravity,temperature=map(source_int,(int(trailer[1]),*values))
            board.flags,board.grav,board.temp=flags,gravity&255,signed_value(temperature,8)
    board.map_width,board.map_height=width,height
    board._grid_failed=False
    if not board.flags&128: make_bridges(board)
    board.name=str(name)[:30]
    from physics.environment import reset
    reset(board)
    return 0


def load_file(board,path):
    try:
        with open(path,encoding='latin1',newline='') as stream: text=stream.read()
    except OSError: return -1
    return load_text(board,text,os.path.basename(path))


def load_checked(board,path,player=1,fail_second_open=False,actor=None):
    actor=player if actor is None else actor
    report(board,f'Loading {os.path.basename(path)}',actor)
    result=check_file(path,board)
    errors={-1:'#-1 Map not found.',-2:'#-1 Map invalid - Bad Height/Width.',-3:'#-1 Map invalid - Height not loaded properly'}
    if result!=1:
        report(board,errors.get(result,'Unknown error while loading map!'),actor)
        return result
    result=-1 if fail_second_open else load_file(board,path)
    actor_id=actor if isinstance(actor,int) else getattr(actor,'_id',-1)
    if actor_id!=1:
        report(board,'Clearing Mechs off Newly Loaded Map',actor)
        clear(board,actor=actor)
        delete_objects(board)
    return result


def save_text(board):
    if board._grid_failed: raise ValueError('Map grid unavailable after failed load')
    if board._terrain is None: raise ValueError('Map grid has been freed')
    output=[f'{board.map_width} {board.map_height}\n']
    for y in range(board.map_height):
        row=[]
        for x in range(board.map_width):
            terrain=board.terrain(x,y)
            if terrain==' ': terrain='.'
            elif terrain==FIRE:
                if find_object(board,x,y,0): terrain='>'
                elif not board.flags&8:
                    board.set_terrain(x,y,' '); terrain='.'
                    error(board,f'[lost?] fire event noticed on map #{board._id} ({board.name}) at {x},{y}','EventInfo')
            elif terrain==SMOKE:
                terrain=board.rterrain(x,y)
                if terrain==' ': terrain='.'
                if terrain==SMOKE:
                    board.set_terrain(x,y,' '); terrain='.'
                    error(board,f'[lost?] smoke event noticed on map #{board._id} ({board.name}) at {x},{y}','EventInfo')
            row.append(terrain+chr(48+board.elevation(x,y)))
        output.append(''.join(row)+'\n')
    flags=board.flags&~1
    if flags: output.append(f'{flags}: {board.grav} {board.temp}\n')
    return ''.join(output)


def save_file(board,path,actor=1):
    report(board,f'Saving {os.path.basename(path)}',actor)
    try:
        with open(path,'w',encoding='latin1',newline='') as stream: stream.write(save_text(board))
        report(board,'Saving complete!',actor)
    except OSError as exc: raise ValueError('Unable to open the map file!') from exc


def resize(board,text,actor=1):
    if board.map_objects[8]: raise ValueError('Invalid map for size change, sorry.')
    args=arguments(text,4)
    if len(args)!=2: raise ValueError('Invalid number of arguments (X/Y expected)')
    width,height=map(atoi,args)
    if not 0<=width<=1000 or not 0<=height<=1000: raise ValueError('X,Y out of range!')
    terrain=[[' ']*width for _ in range(height)]; elevation=[[0]*width for _ in range(height)]
    for y in range(min(board.map_height,height)):
        for x in range(min(board.map_width,width)):
            terrain[y][x],elevation[y][x]=board.terrain(x,y),board.elevation(x,y)
    delete_objects(board)
    board._terrain,board._elev=terrain,elevation
    board.map_width,board.map_height=width,height
    board._loaded_rows=height
    from physics.environment import resized
    resized(board)
    return report(board,'Size set.',actor)


def clear(board,actor=1):
    from systems.startup import shutdown
    for unit in list(board.mechs_on_map):
        if unit is None: continue
        report(board,f'Shutting down Mech #{unit._id} and resetting map index to -1....',actor)
        shutdown(board._engine or unit._engine,unit,wizard=True)
        unit.x=unit.y=unit.last_x=unit.last_y=0
        board.remove_mech(unit)
    board.mechs_on_map.clear(); board.roster_ids.clear(); board.mechflags.clear(); board.slot_los.clear()
    report(board,'Map Cleared',actor)


def free(board):
    from physics.environment import cancel,clear_layers
    cancel(board);clear_layers(board)
    clear(board); delete_objects(board)
    board._terrain=board._elev=None


def initialize(identity,allocate=False):
    board=GameMap(21,11,'Default Map' if allocate else '')
    board._id=identity; board.movemod=0
    return board


def addhex(board,text,actor=1):
    args=arguments(text,4)
    if len(args)!=4: raise ValueError('Invalid number of arguments!')
    x,y=map(atoi,args[:2]); elevation=abs(atoi(args[3]))
    if not board.valid(x,y): raise ValueError('X,Y out of range!')
    if elevation>127: raise ValueError('Unsupported source char elevation narrowing')
    board.set_terrain(x,y,' ' if args[2][0]=='.' else args[2][0])
    board.set_elevation(x,y,min(elevation,9))
    return report(board,'Hex set!',actor)


def emit(board,text,actor=1):
    from systems.notifications import map_broadcast
    text=text.lstrip(' ')
    if not text: raise ValueError('What do you want to @mapemit?')
    map_broadcast(board,text)
    report(board,'Message sent!',actor)


def view(board,text,tacsize='',actor=1):
    if board is None: return
    args=arguments(text,2)
    if len(args)!=2: raise ValueError('Invalid number of parameters!')
    x,y=map(atoi,args)
    height,width=14,21
    if tacsize:
        values,_=scan_ints(tacsize,2)
        if len(values)==2 and 5<=values[0]<=24 and 5<=values[1]<=40: height,width=values
        else: report(board,"Illegal Tacsize attribute. Must be in format 'Height Width' . Height : 5-24 Width : 5-40",actor)
    from systems.map_display import sketch
    x,y=max(0,min(x,board.map_width-1)),max(0,min(y,board.map_height-1))
    rendered,_,_=sketch(None,x,y,min(width,board.map_width),min(height,board.map_height),board=board)
    for line in rendered: report(board,line,actor)
    return rendered


def delobj(board,text,actor=1):
    from entities.map_objects import TYPES,delete_object
    args=arguments(text,3)
    if not args: raise ValueError('Error: Invalid number of attributes to delobj command.')
    kind=None
    if len(args)!=2:
        try: kind=TYPES.index(args[0].upper())
        except ValueError: raise ValueError('Invalid type!') from None
    coordinate=tuple(map(atoi,args[-2:])) if len(args)>1 else None
    count=0; mine_deleted=kind==3 and coordinate is None
    for group in (range(10) if kind is None else (kind,)):
        for obj in list(board.map_objects[group]):
            if coordinate is None or (obj.x,obj.y)==coordinate:
                mine_deleted|=group==3
                delete_object(board,obj,group,1); count+=1
    if coordinate is None: message=f'{count} objects deleted!'
    elif kind is None: message=f'{count} objects at ({coordinate[0]},{coordinate[1]}) deleted.'
    else: message=f'{count} {TYPES[kind]} at ({coordinate[0]},{coordinate[1]}) deleted.'
    report(board,message,actor)
    if mine_deleted:
        from systems.mines import recalculate_minefields
        recalculate_minefields(board)
    return count


def decoration_command(board,text,kind,actor=1):
    from physics.decorations import add_fire,add_smoke
    name='fire' if kind==0 else 'smoke'
    args=arguments(text,3)
    if len(args)!=3: raise ValueError(f'Error: Invalid number of attributes to add{name} command.')
    x,y,duration=map(atoi,args)
    from entities.map_storage import source_int
    duration=source_int(duration)
    (add_fire if kind==0 else add_smoke)(board._engine,board,x,y,duration)
    return report(board,f'Added: {name.capitalize()} at ({x},{y}) with duration of {duration}s.',actor)


def list_objects(board,actor=1):
    from entities.map_objects import TYPES,object_values
    output=['X   Y   Type  obj   dc   ds     di','--------------------------------------------']
    for kind,group in enumerate(board.map_objects):
        for obj in group:
            if kind==8: output.append('--- MAP/HANGAR INFORMATION OBJECT ---')
            else:
                x,y,identity,_,dc,ds,di=object_values(obj,kind)
                output.append(f'{x:<3} {y:<3} {TYPES[kind]:<5} {identity:<5} {dc:<4} {ds:<6} {di}')
    output.append('--------------------------------------------')
    for line in output: report(board,line,actor)
    return output


def list_mechs(board,text,actor=1):
    from systems.map_membership import ensure_roster
    args=arguments(text,1)
    if not args: raise ValueError('Supply target type too!')
    if args[0].upper()=='OBJS': return list_objects(board,actor=actor)
    elif args[0].upper()=='MECHS':
        ensure_roster(board); output=['--- Mechs on Map ---']; count=0
        for identity,unit in zip(board.roster_ids,board.mechs_on_map):
            if identity==-1: continue
            count+=1
            from systems.parts import mech_ids
            label=mech_ids(unit)
            valid='Valid Data' if unit is not None else 'Invalid Object Data!  Remove this Mech!'
            output.append(f'Mech DB Number: {identity} : [{label}]\t{valid}')
        output.extend((f'{count} Mechs On Map',f'{250-count} positions open'))
        if count!=len(board.roster_ids): output.append(f'{len(board.roster_ids)} is first free slot, according to db.')
    else: raise ValueError(f'Invalid argument ({args[0]})!')
    for line in output: report(board,line,actor)
    return output


def debug_fix(board,records=None,actor=1):
    """Inspect the local object registry; explicit records supplement detached fixtures."""
    if board is None: return
    records=dict(records or {})
    engine=board._engine
    if engine is not None:
        world=getattr(engine,"personnel",None)
        objects=dict(getattr(world,"objects",{}))
        objects.update({obj._id:obj for obj in engine.get_entities() if hasattr(obj,"_id")})
        for identity,obj in objects.items():
            from entities.mech import Mech
            kind=getattr(obj,"xcode_type",None) or ("MECH" if isinstance(obj,Mech) else None)
            records[identity]=dict(location=getattr(obj,"location",None),hardcode=getattr(obj,"hardcode",True),
                type=kind,unit=obj if kind=="MECH" and hasattr(obj,"sections") else None)
    from systems.map_membership import ensure_roster,publish_los
    ensure_roster(board)
    report(board,f'Checking {len(board.roster_ids)} entries..',actor)
    for identity,record in records.items():
        unit=record.get('unit')
        if record.get('location')==board._id and record.get('hardcode') and record.get('type')=='MECH':
            if identity not in board.roster_ids and unit is not None: unit.mapindex=-1; unit.mapnumber=0; unit.map=None
    for index,identity in enumerate(board.roster_ids):
        if identity<0: continue
        record=records.get(identity,{})
        unit=record.get('unit')
        if record.get('type')!='MECH': message=f"Error: #{identity} isn't mech yet is in mapindex. Fixing.."
        elif unit is None: message=f'Error: #{identity} has no mech data. Removing..'
        elif unit.mapindex!=board._id: message=f"Error: #{identity} isn't really here! Removing.."
        else:
            if unit.mapnumber!=index: report(board,f'Error: #{identity} has invalid mapnumber (mn:{unit.mapnumber} <-> real:{index})..',actor)
            continue
        report(board,message,actor); board.roster_ids[index]=-1; board.mechs_on_map[index]=None
    publish_los(board)
    report(board,'Done.',actor)
