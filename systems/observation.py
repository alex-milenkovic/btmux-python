# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.c3.misc.c
#   btech/mech.contacts.c
#   btech/mech.scan.c
#   btech/mech.utils.c
# Historical Aerospace sources:
#   btech/ds.turret.c

"""Pilot contact, scan, report and navigation readouts (mech.contacts/scan.c)."""
import math
import re
from physics.hexmath import virtual_facing,acceptable_degree
from systems.parts import mech_ids
from core.events import EventType
from entities.mech import MechStatus as S, CritStatus as C, UnitType, MoveType, VehicleLocation, Location, FireMode
from physics.hexmath import in_weapon_arc, find_bearing, hex_to_float, ZSCALE, FORWARDARC, TURRETARC, RSIDEARC, LSIDEARC, REARARC
from systems.targeting import contact_target, resolve_unit, fa_mech_range, find_range, find_mech_in_hex, list_contacts
from systems.los import in_line_of_sight, in_line_of_sight_nb
from systems.movement_commands import notify, pending, c_number
from core.attributes import player_preference


def guard(unit,caller=None):
    from systems.communications import common_checks,MECH_USUAL
    caller=caller if caller is not None else getattr(unit,'command_actor',getattr(unit,'pilot',None))
    return common_checks(unit,caller,MECH_USUAL)


def response(ok=True,message='',**fields):
    return dict(ok=ok,message=message,**fields)


def brief(mech, text=''):
    from systems.communications import common_checks,MECH_USUALSM
    error=common_checks(mech,getattr(mech,'command_actor',getattr(mech,'pilot',None)),MECH_USUALSM)
    if error is not None:return response(False,error)
    ac=['0 - See enemies and friends, long text, color','1 - See enemies and friends, short text, color','2 - See enemies only, long text, color','3 - See enemies only, short text, color','4 - See enemies and friends, short text, no color','5 - See enemies only, short text, no color','6 - Disabled']
    descriptions=['0 - Very verbose','1 - Short form, the usual one','2 - Short form, the usual one, but do not see buildings','3 - Shorter form']
    if not text.strip():
        lines=[f'Brief status for {mech.name} [{mech.contact_id.lower()}]:',f'    (A)utocontacts: {ac[mech.brief//4]}',f'    (C)ontacts:     {descriptions[mech.brief%4]}']
        return response(message='\n'.join(lines),lines=lines,autocontacts=mech.brief//4,contacts=mech.brief%4)
    text=text.lstrip();field=text[0].upper();value=text[1:].lstrip()
    if not value:return response(False,'Argument missing!')
    parsed=int(c_number(value,True))
    if not parsed and value!='0':return response(False,'Invalid number!')
    value=parsed
    if field not in ('A','C'):return response(brief=mech.brief)
    if not 0<=value<=(6 if field=='A' else 3):return response(False,'Number out of range!')
    mech.brief=mech.brief%4+4*value if field=='A' else (mech.brief//4)*4+value
    message=('Autocontact' if field=='A' else 'Contact')+' brevity set to '+(ac if field=='A' else descriptions)[value]+'.'
    notify(mech,message)
    return response(message=message,brief=mech.brief,notified=True)



def weapon_arc(arc):
    return next((char for bit,char in [(FORWARDARC,'*'),(TURRETARC,'t'),(RSIDEARC,'r'),(LSIDEARC,'l'),(REARARC,'v')] if arc & bit),'?')


def _event(mech,kind):
    return mech._engine is not None and mech._engine.has_event(kind,mech)


def _statuses(mech):
    from systems.ecm import check_all_sections,ecm_active,per_ecm_active,angel_ecm_active,ecm_countered,ecm_protected,angel_ecm_protected,any_ecm_disturbed
    swarm=getattr(mech.swarm_target,'_id',mech.swarm_target) or -1
    return dict(destroyed=mech.is_destroyed,starting=_event(mech,EventType.STARTUP),
                stopped=not mech.is_started,standing=pending(mech,'_stand_event'),fallen=mech.is_fallen,
                changing=pending(mech,'_hulldown_event'),hulldown=mech.has_status(S.HULLDOWN),
                towed=bool(getattr(mech,'towed_by',None)) or mech.has_status(S.TOWED),carrying=mech.carrying>0,
                jumping=mech.is_jumping,ood=bool(mech.cocoon),heat=bool(mech.heat),
                jellied=bool(mech.crit_status & C.JELLIED),burning=_event(mech,EventType.VEHICLE_BURN),
                light=bool(mech.status2 & 0x20),lit=bool(mech.crit_status & C.SLITE_LIT),swarm=swarm>0,
                club=bool(mech.sections[Location.LARM].specials & 0x20 or mech.sections[Location.RARM].specials & 0x20),narc=bool(check_all_sections(mech,1|2)),
                eccm=bool(mech.status2 & (2|0x200)),
                ecm=ecm_active(mech) or angel_ecm_active(mech),
                protected=ecm_protected(mech) or angel_ecm_protected(mech),disturbed=any_ecm_disturbed(mech),
                spinning=bool(mech.crit_status & C.SPINNING),sprinting=bool(getattr(mech._engine,'movement_modes',True) and mech.status2 & 0x10000),
                evading=bool(getattr(mech._engine,'movement_modes',True) and mech.status2 & 0x20000),staggering=mech.stagger_damage//20>0)


def status_string(target,who=1):
    s=_statuses(target)
    groups=[('destroyed','D'),('starting','s'),('stopped','S'),('standing','f'),('fallen','F'),
            ('changing','h'),('hulldown','H'),('towed','T'),('carrying','t'),('jumping','J'),('ood','O'),
            ('heat','+'),('jellied','I'),('burning','B'),('light','L'),('lit','l'),('swarm','W'),('club','C'),
            ('narc','N' if who==1 else 'n'),('eccm','P'),('ecm','E'),('protected','p'),('disturbed','e'),
            ('spinning','X'),('sprinting','M'),('evading','m')]
    for first,second in [('starting','stopped'),('standing','fallen'),('changing','hulldown'),('towed','carrying')]:
        if s[first]: s[second]=False
    return ''.join(char for key,char in groups if s[key])


def status_chars(viewer,target):
    s=_statuses(target)
    s['spinning']=bool(viewer.crit_status & C.SPINNING)
    groups=[[('swarm','W'),('towed','T'),('carrying','t'),('club','C'),('sprinting','M'),('evading','m')],
            [('destroyed','D'),('light','L'),('lit','l')],
            [('jumping','J'),('ood','O'),('fallen','F'),('standing','f'),('changing','h'),('hulldown','H'),('spinning','X')],
            [('staggering','G'),('starting','s'),('stopped','S')] if not target.is_started else [('heat','+'),('jellied','I'),('burning','B')],
            [('narc','n' if viewer.team==target.team else 'N'),('eccm','P'),('ecm','E'),('protected','p'),('disturbed','e')]]
    return ''.join(next((char for key,char in group if s[key]),' ') for group in groups)


def contacts(mech,options='',caller=None):
    error=guard(mech,caller)
    if error is not None: return response(False,error)
    from systems.combat_commands import parse_attributes
    options=next(iter(parse_attributes(options,1)),'')
    brevity=mech.brief%4
    hud=options.startswith('h')
    mask=31 if not options or hud else 32 if brevity==1 else 0
    if not options and brevity==1: mask|=32
    ignored=[]
    if options and not hud:
        text=(player_preference(mech,caller,'A_CONTACTOPT','contact_options') or '!db') if options.startswith('+') else options.split()[0]
        for char in text[:49]:
            bit={'d':1,'s':2,'a':4,'e':8,'t':16,'b':32}.get(char)
            if char=='!': mask=128|31
            elif bit: mask=mask & ~bit if mask & 128 else mask|bit
            else: ignored.append(f'Ignoring {char} as contact option.')
    rows=[]
    for contact in list_contacts(mech):
        target=contact['mech']
        friend=contact['identified'] and target.team==mech.team
        selected=mask & 16 and target._id==mech.target
        if options:
            if not (mask & (4 if friend else 8) or selected): continue
            if not (mask & 2 or target.is_started or target.is_destroyed or selected): continue
            if not (mask & 1 or not target.is_destroyed or selected): continue
        row={k:v for k,v in contact.items() if k!='mech'}
        row.update(name=target.name if contact['identified'] else 'something',friend=friend,
                   contact_id=mech_ids(target, friend),arcs=contact['arc'],jump_heading=getattr(target,'jump_heading',0),
                   status=status_chars(mech,target) if contact['identified'] else '     ',
                   arc=weapon_arc(contact['arc']),tonnage=target.tonnage,heat=target.heat,
                   full_status=status_string(target,0 if friend else 1) if contact['identified'] else '')
        rows.append(row)
    from systems.display_contacts import building_contacts,contact_lines
    blocked=[]
    if mask & 32:
        buildings,blocked=building_contacts(mech);rows.extend(buildings)
    if brevity:
        # Source selection swaps reverse equal-key runs when a later maximum moves.
        for i in range(len(rows)-1):
            for j in range(i+1,len(rows)):
                if rows[j]['sort_range']>rows[i]['sort_range']:rows[i],rows[j]=rows[j],rows[i]
    heading=hud or brevity<=2
    lines=ignored+(['#HUDINFO:CON#Line of Sight Contacts:' if hud else 'Line of Sight Contacts:'] if heading else [])
    for row in rows:
        if not brevity and row.get('building'):continue
        lines.extend(contact_lines(mech,row,hud,brevity))
    if heading:lines.append('#HUDINFO:CON#End Contact List' if hud else 'End Contact List')
    return response(message='\n'.join(lines),lines=lines,contacts=rows,heading=heading,hud=hud,blocked=blocked)



def turret_facing(target):
    if target.unit_type in (UnitType.MECH,UnitType.BSUIT,UnitType.MW,UnitType.AERO,UnitType.DS,UnitType.SPHEROID_DS) or not target.sections[VehicleLocation.TURRET].internal:
        return None
    offset=acceptable_degree(getattr(target,'turret_facing',0))
    if offset>180: offset-=360
    return dict(facing=acceptable_degree(target.facing+getattr(target,'turret_facing',0)),offset=offset if target.move_type!=MoveType.NONE else 0)


def unit_report(viewer,target,distance):
    return dict(name=target.name,contact_id=target.contact_id,tonnage=target.tonnage,
                position=[target.x,target.y,target.z],range=distance,bearing=find_bearing(viewer.fx,viewer.fy,target.fx,target.fy),
                speed=target.speed,heading=virtual_facing(target),vertical_speed=getattr(target,'vertical_speed',0),
                heat=target.heat*10,lateral=target.lateral,turret=turret_facing(target),
                type=getattr(UnitType._value2member_map_.get(target.unit_type),'name',str(target.unit_type)),movement=getattr(MoveType._value2member_map_.get(target.move_type),'name',str(target.move_type)),
                arc=weapon_arc(in_weapon_arc(viewer,target.fx,target.fy)),status=status_string(target))


def weapon_report(target,owner=False):
    from entities.weapon import get_weapon_by_index
    from systems.ecm import section_destroyed
    result=[]
    for index,ws in enumerate(target.weapons):
        if section_destroyed(target,ws.section): continue
        crit=target.sections[ws.section].criticals[ws.critical]
        broken=ws.destroyed or crit.firemode & (FireMode.DESTROYED_MODE|FireMode.DISABLED_MODE)
        row=dict(number=index,name=get_weapon_by_index(ws.weapon_idx).name,section=ws.section,
                 status='*****' if broken else '-----' if ws.recycle or crit.data else 'Ready')
        if owner: row.update(recycle=ws.recycle,firemode=int(crit.firemode),ammomode=int(crit.ammomode))
        result.append(row)
    return result


def scan(mech,argument='',report=False,caller=None,historical=None):
    caller=caller if caller is not None else getattr(mech,'command_actor',mech.pilot)
    error=guard(mech,caller)
    if error is not None: return response(False,error)
    from systems.combat_commands import parse_attributes
    args=parse_attributes(argument,3 if report else 4) if isinstance(argument,str) else [argument]
    if len(args)>(2 if report else 3): return response(False,'Wrong number of arguments to '+('report' if report else 'scan')+'!')
    if not mech.scan_range: return response(False,'Your system seems to be inoperational.')
    option='all'
    pending_option=None
    target=None
    coordinate=False
    default_hex_report=False
    special=None
    if not report and len(args)==1 and isinstance(args[0],str) and len(args[0])==1:
        option=args.pop().upper()
        if option not in ('A','I','W'): return response(False,'Truly odd option!')
    if not args:
        target=resolve_unit(mech,mech.target)
        if target is None:
            from systems.combat import find_target_xy
            if (report or not mech.has_status(S.LOCK_BUILDING)) and find_target_xy(mech) is None:
                return response(False,'No default target set!')
            if report:
                # mech_report case 0 retains its initialized coordinates
                # and range; it does not enter the coordinate range gates.
                target=find_mech_in_hex(mech,mech.map,0,0,1)
                if target is None: return response(False,"You don't see a thing.")
                default_hex_report=True
            else:
                x,y=mech.targ_x,mech.targ_y
                coordinate=True
                special='B' if mech.has_status(S.LOCK_BUILDING) else 'H' if mech.has_status(S.LOCK_HEX) else None
    elif len(args)==1 or (not report and len(args)==2 and isinstance(args[0],str)
                         and int(c_number(args[0],True))==0 and args[0]!='0'):
        target=contact_target(mech,args[0])
        if target is None: return response(False,'Target is not in line of sight!')
        if len(args)==2:
            pending_option=args[1]
    else:
        x,y=int(c_number(args[0],True)),int(c_number(args[1],True))
        coordinate=True
        if len(args)==3:
            if not mech.map.valid(x,y): return response(False,'Those coordinates are out of scanner range.')
            special=args[2][0].upper()
            if special not in ('B','H'): return response(False,'Invalid 3rd argument!')
    observer=bool(mech.crit_status & C.OBSERVATORIC) or getattr(mech,'is_observator',False)
    if coordinate:
        if not mech.map.valid(x,y): return response(False,'Those coordinates are out of scanner range.')
        fx,fy=hex_to_float(x,y)
        z=mech.map.base_elevation(x,y)*ZSCALE if special or not args and not report else 0
        distance=find_range(mech.fx,mech.fy,mech.fz,fx,fy,z)
        if int(distance)>mech.scan_range and (report or len(args)==3 or not observer):
            return response(False,'Those coordinates are out of scanner range.')
        if not args and not report:
            if not in_line_of_sight_nb(mech,None,x,y,distance):return response(False,'Target hex is not in line of sight!')
        elif not in_line_of_sight(mech,None,x,y,distance): return response(False,'Coordinates are not in line of sight!')
        if report and not in_line_of_sight_nb(mech,None,x,y,distance):return response(False,"That target isn't seen well enough by the scanners for a report!")
        if special:
            from systems.buildings import query
            cf=query(mech,x,y)
            result=response(building_cf=cf,building_queried=True,mines_queried=special=='H')
            if special=='H':
                from systems.mines import show_mines_in_hex
                result['mines_found']=show_mines_in_hex(mech,distance,x,y,caller=caller)
            return result
        target=find_mech_in_hex(mech,mech.map,x,y,1)
        if target is None: return response(False,'No target found.' if report else 'You see nobody in the hex!')
    else:
        distance=0 if default_hex_report else fa_mech_range(mech,target)
        if not args and not report and not observer and int(distance)>mech.scan_range:return response(False,'Target is out of scanner range.')
        if not in_line_of_sight(mech,target,target.x,target.y,distance): return response(False,"You don't see a thing." if default_hex_report else 'Target is not in line of sight!')
        if not report and len(args)==1 and not in_line_of_sight_nb(mech,target,target.x,target.y,distance):return response(False,"That target isn't seen well enough by the scanners for scanning!")
        if not report and not observer and int(distance)>mech.scan_range: return response(False,'Target is out of scanner range.')
    if pending_option is not None:
        option=pending_option[:1].upper()
        if option not in ('A','I','W'):return response(False,'Truly odd option!')
    if not default_hex_report and not (report and coordinate) and not in_line_of_sight_nb(mech,target,target.x,target.y,distance):
        detail='a report' if report else 'scanning' if not coordinate and not args else 'report'
        return response(False,"That target isn't seen well enough by the scanners for "+detail+'!')
    if not report and target.unit_type==UnitType.MW: return response(False,'Your scanners cannot give you precise information on targets that small!')
    from systems.armor_display import armor_display,armor_field
    from systems.status_display import weapon_display
    from systems.damage_commands import section_names
    from core.effects import notify_actor
    lines=[]
    def emit(component):
        for line in component:
            lines.append(line);notify_actor(mech,caller,line)
    result=response(report=unit_report(mech,target,distance),sections=['base'],blocked=[])
    emit(report_lines(mech,target,distance))
    if not report:
        if option in ('all','A'):
            result['sections'].append('armor');result['armor_display']=armor_display(target,observer,caller=caller,historical=historical)
            result['armor']=[dict(section=i,**dict(armor=s.armor,rear=s.rear,internal=s.internal)) if observer else dict(section=i,front=armor_field(target,i),rear=armor_field(target,i,'rear'),internal=armor_field(target,i,'internal')) for i,s in enumerate(target.sections[:len(section_names(target))])]
            emit(result['armor_display']['lines'])
        if option in ('all','I'):
            result['sections'].append('info');result['info']=dict(torso=int(target.status & (S.TORSO_LEFT|S.TORSO_RIGHT)),carrying=target.carrying)
            if target.status&S.TORSO_RIGHT:emit(['Torso is 60 degrees right'])
            if target.status&S.TORSO_LEFT:emit(['Torso is 60 degrees left'])
            carried=resolve_unit(target,target.carrying)
            if carried:
                from systems.notifications import identity
                emit(['Towing '+identity(target,carried)+'.'])
            emit([' '])
        if option in ('all','W'):
            result['sections'].append('weapons');display=weapon_display(target,observer);result['weapons']=display['weapons'];emit(display['lines'])
    # Source evaluates the observer flag again after requester notifications.
    if not report and not (mech.crit_status & C.OBSERVATORIC or getattr(mech,'is_observator',False)):
        result['blocked'].extend(scan_effects(mech,target))
    result.update(message='\n'.join(lines),lines=lines,effects_complete=not result['blocked'],notified=True)
    return result


def report_lines(viewer,target,distance):
    from systems.network_reports import show_flags,arc_label
    ident=mech_ids(target, target.team==viewer.team and in_line_of_sight_nb(viewer,target,0,0,0))
    lines=[f'[{ident}]  {target.name:25.25s} Tonnage: {target.tonnage}',f'      Range: {distance:.1f} hex\t\tBearing: {find_bearing(viewer.fx,viewer.fy,target.fx,target.fy)} degrees',f'      Speed: {target.speed:.1f} KPH\t\tHeading: {virtual_facing(target)} degrees']
    lines=[line[:99] for line in lines]
    if target.unit_type in (UnitType.VTOL,UnitType.AERO,UnitType.DS,UnitType.SPHEROID_DS):lines.append(f'      Vertical speed: {target.vertical_speed:.1f} KPH')
    lines.append(f'      X, Y, Z: {target.x:3d}, {target.y:3d}, {target.z:3d}\tHeat: {10*target.heat:.0f} deg C.'[:99])
    if target.lateral:
        from systems.status_display import lateral_description
        lines.append('      Mech is moving laterally '+lateral_description(target))
    turret=turret_facing(target)
    if turret:lines.append(f"      Turret Facing: {turret['facing']} degrees"+(f" ({turret['offset']} offset from heading)" if turret['offset'] else ''))
    descriptions={MoveType.NONE:'INSTALLATION',MoveType.BIPED:{UnitType.MW:'MECHWARRIOR         Movement: BIPED',UnitType.BSUIT:'BATTLESUIT(S)       Movement: BIPED'}.get(target.unit_type,'MECH                Movement: BIPED' if target.unit_type==UnitType.MECH else None),MoveType.QUAD:'MECH                Movement: QUAD',MoveType.TRACK:'VEHICLE             Movement: TRACKED',MoveType.WHEEL:'VEHICLE             Movement: WHEELED',MoveType.HOVER:'VEHICLE             Movement: HOVER',MoveType.VTOL:'VTOL                Movement: VTOL',MoveType.FLY:f'{"AEROSPACE" if target.unit_type==UnitType.AERO else "DROPSHIP":9s}             Movement: FLIGHT',MoveType.HULL:'NAVAL               Movement: HULL',MoveType.SUB:'NAVAL               Movement: SUBMARINE',MoveType.FOIL:'NAVAL               Movement: HYDROFOIL'}
    if descriptions.get(target.move_type) is not None:lines.append('      Type: '+descriptions[target.move_type])
    arc=in_weapon_arc(viewer,target.fx,target.fy)
    if arc&TURRETARC:lines.append('      In Turret Arc')
    lines.append('      In '+arc_label(viewer,arc&~TURRETARC)+' Weapons Arc');lines.extend(show_flags(target,6,1))
    if target.is_jumping:lines.append(f'      Mech is Jumping!\tJump Heading: {target.jump_heading}')
    return lines+[' ']



def view(mech,text='',caller=None):
    error=guard(mech,caller)
    if error is not None:return response(False,error)
    from systems.combat_commands import parse_attributes
    from systems.notifications import MECHALL,MECHPILOT
    def refusal(message,audience):
        notify(mech,message,audience=audience)
        return response(False,message,notified=True)
    args=parse_attributes(text,2)
    if len(args)>1: return response(False,'Invalid number of arguments to function.')
    if not args and mech.target==-1:return refusal('You do not have a default target set!',MECHALL)
    target=contact_target(mech,args[0]) if args else resolve_unit(mech,mech.target)
    if target is not None and args and not in_line_of_sight(mech,target,target.x,target.y,fa_mech_range(mech,target)):
        return refusal('Target is not in line of sight!',MECHPILOT)
    if target is None:
        result=refusal('Invalid default target!' if not args else 'Target is not in line of sight!',MECHALL if not args else MECHPILOT)
        if not args: mech.target=-1
        return result
    if not in_line_of_sight_nb(mech,target,target.x,target.y,fa_mech_range(mech,target)):
        return response(False,"That target isn't seen well enough by the "+('scanners' if args else 'scannfers')+' for viewing!')
    return response(message=target.markings or 'That target has no markings.')


def navigation(mech,kind,text='',caller=None):
    error=guard(mech,caller)
    if error is not None: return response(False,error)
    from systems.combat_commands import parse_attributes
    args=parse_attributes(text,6 if kind=='vector' else 4)
    if len(args) not in ((0,2,4) if kind!='vector' else (0,2,3,4,6)):
        return response(False,f'Invalid number of attributes to {kind.title()} function!')
    origin=(mech.fx,mech.fy,mech.fz)
    dark=bool(getattr(mech.map,'dark',False) or mech.map.flags&32) and kind=='range'
    def point(values,first=False):
        x,y=(int(c_number(v,True)) for v in values[:2])
        four=len(args)==4 and kind in ('bearing','range')
        valid=(0<=x<=mech.map.map_width and 0<=y<mech.map.map_height) if four and first else (
            0<=x<mech.map.map_width and y>=0 and -1<mech.map.map_height
            if four and kind=='bearing' else mech.map.valid(x,y))
        if not valid: raise ValueError('Invalid map coordinates!')
        if kind=='bearing':z=0
        elif len(values)==3:z=int(c_number(values[2],True))
        elif dark:z=0
        else:
            if not mech.map.valid(x,y):raise ValueError('Coordinate requires undefined source map access.')
            z=mech.map.base_elevation(x,y)
        return (*hex_to_float(x,y),z*ZSCALE)
    try:
        if not args:
            target=resolve_unit(mech,mech.target)
            if target:
                if not in_line_of_sight(mech,target,target.x,target.y,fa_mech_range(mech,target)):
                    return response(False,'Target is not in line of sight!')
                destination=(target.fx,target.fy,target.fz)
            from systems.combat import find_target_xy
            destination=find_target_xy(mech)
            if destination is None:return response(False,'There is no default target!')
        elif len(args) in (2,3):
            destination=point(args)
            if dark: destination=(*destination[:2],mech.z*ZSCALE)
        else:
            half=len(args)//2
            origin,destination=point(args[:half],first=True),point(args[half:])
    except ValueError as error: return response(False,str(error))
    distance=find_range(*origin,*destination)
    ground=find_range(*origin[:2],0,*destination[:2],0)
    bearing=find_bearing(*origin[:2],*destination[:2])
    from physics.hexmath import find_z_bearing
    vertical=find_z_bearing(*origin, *destination)
    show_vertical=kind=='vector' and len(args) in (0,3,6)
    title=kind.title()
    if not args:prefix=f'{title} to default target is: '
    elif len(args) in (2,3):prefix=f'{title} to  '+','.join(str(int(c_number(v,True))) for v in args)+' is: '
    else:
        half=len(args)//2
        prefix=f'{title} to '+','.join(str(int(c_number(v,True))) for v in args[half:])+' from '+','.join(str(int(c_number(v,True))) for v in args[:half])+' is: '
    range_text=f'{distance:.1f} hexes'+(f' ({ground:.1f} ground hexes)' if f'{distance:.1f}'!=f'{ground:.1f}' else '')
    message=prefix+(f'{bearing} degrees.' if kind=='bearing' else range_text+'.' if kind=='range' else range_text+f' and {bearing} degrees'+(f" mark {'+' if destination[2]>origin[2] else '-' if destination[2]<origin[2] else ' '}{vertical}" if show_vertical else '')+'.')
    return response(message=message,
                    range=distance,ground_range=ground,bearing=bearing,
                    vertical_bearing=vertical if show_vertical else None)


def map_readout(unit,kind,argument='',caller=None,historical=None):
    from systems.map_display import tactical,lrs
    result=lrs(unit,argument,caller=caller) if kind=='lrs' else tactical(unit,argument,navigate=kind=='navigate',caller=caller,historical=historical)
    if result['ok']:
        result.update(position=[unit.x,unit.y,unit.z],speed=unit.speed,
                      vertical_speed=unit.vertical_speed,facing=unit.facing)
    return result


def own_readout(unit,kind,argument='',caller=None,historical=None):
    from systems.status_display import own_readout as display
    return display(unit,kind,argument,caller=caller,historical=historical)


def scan_effects(viewer,target):
    from systems.notifications import identity,MECHSTARTED
    who=identity(target,viewer)
    if target.is_started:notify(target,'You are being scanned by '+who,audience=MECHSTARTED)
    # GetMechToMechID is evaluated separately after the warning, before reply guards.
    who=identity(target,viewer)
    if not (getattr(target,'freq',[]) or [0])[0] or getattr(target,'autopilot',-1)<=0:return []
    callback=getattr(target,'autonomous_scan_reply',None)
    if callable(callback):callback(viewer);return []
    callback=getattr(target._engine,'auto_reply',None)
    if callable(callback):callback(target,who+' just scanned me.');return []
    from systems.communications import auto_reply
    auto_reply(target,who+' just scanned me.')
    return []
