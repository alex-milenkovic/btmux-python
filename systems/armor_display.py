# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.status.c

"""Owner and scanner armor fields and source status-template interpretation."""
import re
from entities.mech import UnitType as U, MoveType as M
from data.armor_templates import TEMPLATES

class DisplayDependencyError(ValueError):
    def __init__(self,message,service):
        super().__init__(message);self.service=service


COLORS=('%ch%cg','%cg','%ch%cy','%cr','%ch%cx','%ch%cb')
GLYPHS='OoxX*?'
FIELDS={'front':'armor','rear':'rear','internal':'internal'}


def point_condition(value,original,repairing=False):
    if repairing:return 5
    if not value:return 4
    percent=int((value+1)*100/(original+1))
    return 3 if percent<=45 else 2 if percent<=70 else 1 if percent<=90 else 0


def plain(text):
    return re.sub(r'\x1b\[[0-9;]*m|%c[hHnNxXrRgGyYbBmMcCwWfFiI]?', '', text)


def condition(unit,loc,kind='front',*,legacy_si=False):
    section=unit.sections[loc]
    if kind not in FIELDS:return 5,-1
    field=FIELDS[kind]
    value,original=getattr(section,field),getattr(section,field+'_orig')
    if legacy_si and unit.unit_type==U.AERO and kind=='internal' and loc==0:
        if not hasattr(unit,'display_si') or not hasattr(unit,'display_si_orig'):
            raise DisplayDependencyError('Legacy Aero SI display input is unavailable; six-location fighters have armor-only durability','legacy-SI-display-input')
        value,original=unit.display_si,unit.display_si_orig
    jobs=None if legacy_si and unit.unit_type==U.AERO and kind=='internal' and loc==0 else getattr(unit._engine,'repair_jobs',None)
    repairing=jobs is not None and jobs.count(unit,48 if kind=='internal' else 47,loc+(8 if kind=='rear' else 0))
    return point_condition(value,original,repairing),value


def armor_field(unit,loc,kind='front',*,owner=False,width=2,divide=False,show_destroyed=False,legacy_si=False):
    if not 0<=loc<len(unit.sections):raise ValueError('Invalid armor location')
    level,value=condition(unit,loc,kind,legacy_si=legacy_si)
    return format_field(level,value,unit.sections[loc].internal,owner=owner,width=width,divide=divide,show_destroyed=show_destroyed)


def format_field(level,value,internal,*,owner=False,width=2,divide=False,show_destroyed=False):
    width=max(0,min(23,width))
    if not show_destroyed and not internal:return ' '*width
    if divide:value=int((value+9)/10)
    field=(str(value).rjust(width)[-width:] if width else '') if owner else GLYPHS[level]*width
    return COLORS[level]+field+'%c'


def armor_key(key,owner):
    if owner:return ''
    if key==1:return 'Key'
    if key>6:return '   '
    return COLORS[6-key]+GLYPHS[6-key]*2+' %c'


def render_template(unit,text,owner=False,*,divide=False,show_destroyed=False,legacy_si=False):
    # Saved literals and consumed input follow BTS_State, even after the output
    # fills. In particular START consumes its first character without rescanning.
    output=bytearray();saved=0;state='start';value1=value2=None
    text=text.split('\0',1)[0]
    def append(value):
        output.extend(value.encode('utf-8')[:max(0,16383-len(output))])
    def internal(loc):
        if not 0<=loc<len(unit.sections):raise ValueError('Invalid armor location')
        return unit.sections[loc].internal
    def commit(index):
        nonlocal saved
        append(text[saved:index]);saved=index
    for index,char in enumerate(text):
        next_state=state;offset=index-saved
        digit='0'<=char<='9'
        if state=='start':
            if '1'<=char<='7':
                commit(index);saved=index+1;append(armor_key(int(char),owner))
            next_state='normal'
        elif state=='normal':
            if char in '&@!':
                commit(index);next_state={'&':'armor','@':'unary','!':'binary'}[char]
        elif state=='armor':
            if offset==1:
                if char=='&':
                    saved=index+1;next_state='normal';append('&')
                elif char in '+:-' or digit:value1=char
                else:next_state='normal'
            elif offset in (2,3):
                substitute=True
                if offset==2:
                    if '0'<=value1<='9':
                        if char in '+:-':value2=char
                        else:next_state='normal'
                        value1=int(value1);substitute=False
                    else:value2=value1;value1=2
                if substitute:
                    append(armor_field(unit,ord(char)-48,{'+':'front','-':'rear',':':'internal'}.get(value2,'unknown'),
                        owner=owner,width=value1,divide=divide,show_destroyed=show_destroyed,legacy_si=legacy_si))
                    saved=index+1;next_state='normal'
        elif state in ('unary','binary'):
            if offset==1:
                if digit:value1=int(char)
                else:next_state='normal'
            elif state=='binary' and offset==2:
                if digit:value2=int(char)
                else:next_state='normal'
            elif offset==(2 if state=='unary' else 3):
                saved=index+1;next_state='normal'
                append(char if internal(value1) or state=='binary' and internal(value2) else ' ')
        if char=='\n':
            state='start';commit(index);append('\r')
        else:state=next_state
    commit(len(text))
    return output.decode('utf-8',errors='ignore')


def diagram_family(unit):
    if unit.unit_type==U.MECH:
        if unit.move_type==M.QUAD:return 'quad'
        return next((name for weight,name in [(35,'light'),(55,'medium'),(75,'heavy')] if unit.tonnage<=weight),'assault')
    if unit.unit_type==U.VEH_GROUND:return 'turreted' if unit.sections[4].internal_orig else 'no-turret'
    if unit.unit_type==U.VEH_NAVAL:return {M.HULL:'ship',M.FOIL:'foil'}.get(unit.move_type,'sub')
    return {U.VTOL:'VTOL',U.MW:'MW',U.BSUIT:'squad',U.AERO:'six-location-fighter',U.DS:'aerodyne',U.SPHEROID_DS:'spheroid'}.get(unit.unit_type,'unknown')


FIGHTER='7                   / Nose &+0 \\\n1       Left Wing &+1 --- Fuselage &+3 --- Right Wing &+2\n2                   | Cockpit &+4 |\n3                   \\ Engine &+5 /'


def armor_display(unit,owner=False,caller=None,historical=None):
    from core.object_services import status_template
    family=diagram_family(unit)
    names=dict(light='lightmechdesc',medium='mediummechdesc',heavy='heavymechdesc',assault='assaultmechdesc',quad='quaddesc',turreted='vehdesc',**{'no-turret':'veh_not_desc'},VTOL='vtoldesc',MW='mwdesc',squad='bsuitdesc',ship='shipdesc',foil='foildesc',sub='subdesc',aerodyne='aerod_ds_desc',spheroid='spher_ds_desc')
    custom,text=status_template(unit,caller)
    if not custom:text=FIGHTER if family=='six-location-fighter' else TEMPLATES.get(names.get(family)," This 'toy' is of unknown type. It has yet to be templated\n for status.")
    from systems.movement_commands import historical_aircraft
    historical=historical_aircraft(unit) if historical is None else historical
    if historical:
        flags=0
        if custom:text+='\n0'
        else:
            from data.historical_armor_templates import TEMPLATES as historical_templates
            text=FIGHTER+'\n0' if family=='six-location-fighter' else historical_templates.get(names.get(family)," This 'toy' is of unknown type to me. It has yet to be templated\n for status.\n0")
            flags={U.MW:8|32,U.AERO:16,U.DS:64}.get(unit.unit_type,0)
        rows=historical_template_lines(unit,text,owner,flags=flags)
        rendered='\r\n'.join(rows)
    else:
        rendered=render_template(unit,text,owner,divide=unit.unit_type==U.MW,show_destroyed=unit.unit_type in (U.AERO,U.DS),legacy_si=False)
        rows=rendered.split('\r\n')
    return dict(family=family,text=rendered,lines=rows,plain=plain(rendered))


def historical_armor_field(unit,loc,kind,flags):
    """Recovered show_armor / PrintArmorDamageString, without newer SI."""
    if not 0<=loc<len(unit.sections):raise ValueError('Invalid armor location')
    if not unit.sections[loc].internal and not flags&64:
        return ' '*(1 if flags&32 else 3 if flags&128 else 2)
    level,value=condition(unit,loc,kind)
    if flags&1:
        width=1 if flags&8 else 3 if flags&128 else 2
        if flags&8 and flags&32:value=int((value+9)/10)
        text=str(value).rjust(width)
        if flags&16 and text.startswith(' '):text='0'+text[1:]
    else:text=GLYPHS[level]*(1 if flags&8 else 2)
    return COLORS[level]+text+'%c'


def render_historical_template(unit,text,owner=False,*,flags=0):
    return '\r\n'.join(historical_template_lines(unit,text,owner,flags=flags))


def historical_template_lines(unit,text,owner=False,*,flags=0):
    """Recovered line markers, strtok blanks, stop line and transient gflags."""
    rows=[]
    for line in text.split('\0',1)[0].split('\n'):
        if not line:continue
        if line.startswith('0'):break
        output=armor_key(int(line[0]),owner) if line[0] in '1234567' else ''
        i=1
        while i<len(line):
            char=line[i]
            if char=='@' and i+2<len(line) and line[i+1] in '01234567':
                output+=line[i+2] if unit.sections[int(line[i+1])].internal else ' '
                i+=3
            elif char=='!' and i+3<len(line) and all(c in '01234567' for c in line[i+1:i+3]):
                output+=line[i+3] if any(unit.sections[int(c)].internal for c in line[i+1:i+3]) else ' '
                i+=4
            elif char=='&' and i+2<len(line) and line[i+1] in '+:-()':
                modifier=False
                if line[i+1]=='(':
                    flags|=8;i+=1;modifier=True
                if i+1<len(line) and line[i+1]==')':
                    flags|=128;i+=1;modifier=True
                if i+2>=len(line):break
                kind={'+':'front','-':'rear',':':'internal'}.get(line[i+1],'front')
                output+=historical_armor_field(unit,ord(line[i+2])-48,kind,flags|int(owner))
                if modifier:flags=0
                i+=3
            else:
                output+=char;i+=1
        rows.append(output)
    return rows
