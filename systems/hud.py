# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/hudinfo.c
#   btech/mech.utils.c

"""Connection-owned HUD 0.8 dispatch and exact CRLF/CSV exports."""
import math
import re
from entities.mech import UnitType as U, MoveType as M, MechStatus as S, CritStatus as C, Specials
from systems import equipment_display as equipment
from systems.damage_commands import short_section,section_names
from systems.armor_display import condition,GLYPHS
from systems.observation import status_string
from systems.targeting import list_contacts,contact_target,fa_mech_range,find_range
from systems.los import in_line_of_sight,in_line_of_sight_nb
from physics.hexmath import virtual_facing,acceptable_degree,hex_to_float,find_bearing,FORWARDARC,LSIDEARC,RSIDEARC,REARARC,TURRETARC

COMMANDS={'gs','we','wl','li','am','sgi','oas','as','c','cb','asc','wsc','t','con','co'}
ACTIVE={'c','cb','asc','wsc','t','con','co'}


def player_unit(personnel,identity):
    registry=getattr(personnel.engine,'object_registry',None)
    if registry is not None:
        obj=registry.resolve(identity)
        unit=registry.mech(identity)
        if unit is not None:return unit
        unit=registry.mech(getattr(obj,'location',-1))
        if unit is not None:return unit
        for ident in registry.contents(identity):
            unit=registry.mech(ident)
            if unit is not None:return unit
        return None
    obj=personnel.objects.get(identity)
    for ident in [identity,getattr(obj,'location',-1),*personnel.contents(identity)]:
        candidate=personnel.objects.get(ident)
        if candidate is not None and hasattr(candidate,'sections') and getattr(candidate,'hardcode',True) and not getattr(candidate,'zombie',False):return candidate
    return None


def type_char(unit):
    if unit.move_type==M.NONE:return 'i'
    if unit.unit_type==U.MECH:return 'Q' if unit.move_type==M.QUAD else 'B'
    from core.effects import send_error
    if unit.unit_type in (U.VEH_GROUND,U.VEH_NAVAL):
        char={M.TRACK:'T',M.WHEEL:'W',M.HOVER:'H',M.HULL:'N',M.FOIL:'Y',M.SUB:'U'}.get(unit.move_type)
        if char is not None:return char
        send_error(unit,f'Unknown movement type on vehicle #{unit._id}: {int(unit.move_type)}')
    else:
        char={U.VTOL:'V',U.AERO:'F',U.DS:'A',U.SPHEROID_DS:'D',U.MW:'I',U.BSUIT:'S'}.get(unit.unit_type)
        if char is not None:return char
        send_error(unit,f'Unknown unit type on unit #{unit._id}: {int(unit.unit_type)} (move {int(unit.move_type)})')
    return '?'


def center(unit):
    x,y=hex_to_float(unit.x,unit.y)
    return find_range(x,y,0,unit.fx,unit.fy,0),find_bearing(unit.fx,unit.fy,x,y)


def arcs(value):
    return ''.join(c for flag,c in [(FORWARDARC,'*'),(LSIDEARC,'l'),(RSIDEARC,'r'),(REARARC,'v'),(TURRETARC,'t')] if value&flag) or '-'


def identity(unit,friend):
    from systems.parts import mech_ids
    return mech_ids(unit, friend)


def advtech(unit):
    text=''
    for name,char in [('ECM','E'),('BEAGLE_PROBE','B'),('LIGHT_BAP','b'),('MASC','M'),('AA','R'),('SLITE','S'),('TRIPLE_MYOMER','t')]:
        if unit.specials&getattr(Specials,name+'_TECH'):text+=char
    for flag,char in [(0x1000,'A'),(0x10,'N'),(0x800,'b'),(1,'s')]:
        if unit.specials2&flag:text+=char
    for flag,char in [(0x80,'IP'),(0x200,'J'),(0x10,'K'),(4,'L'),(1,'W'),(0x20,'a'),(2,'f'),(0x40,'i'),(0x100,'j'),(8,'p')]:
        if unit.infantry_specials&flag:text+=char
    for field,flag,char in [('specials2',0x20,'C'),('specials2',0x8000,'T'),('specials',Specials.C3_SLAVE_TECH,'c'),('specials',Specials.C3_MASTER_TECH,'m')]:
        if getattr(unit,field)&flag or char=='T' and unit.specials&Specials.C3_MASTER_TECH:text+=char
    return text or '-'


def general(unit):
    from physics.heights import aero_free_fuel
    flying=unit.unit_type in (U.VTOL,U.AERO,U.DS,U.SPHEROID_DS)
    fuel=unit.fuel if flying and not aero_free_fuel(unit) else '-'
    torso='-'
    if unit.unit_type in (U.VEH_GROUND,U.VEH_NAVAL,U.VTOL) and unit.sections[4].internal_orig:torso=acceptable_degree(unit.turret_facing)-180
    elif unit.unit_type==U.MW or unit.unit_type==U.MECH and unit.move_type!=M.QUAD:torso=-60 if unit.status&S.TORSO_LEFT else 60 if unit.status&S.TORSO_RIGHT else 0
    rtc,btc=center(unit)
    return [unit.contact_id,unit.x,unit.y,unit.z,unit.facing,unit.desired_facing,f'{unit.speed:.2f}',f'{unit.desired_speed:.2f}',int(unit.plus_heat*10),int(unit.minus_heat*10),fuel,f'{unit.vertical_speed:.2f}',f'{unit.vertical_speed:.2f}',f'{rtc:.3f}',btc,torso,status_string(unit,2),getattr(unit,'going_x',0) if unit.is_jumping else '-',getattr(unit,'going_y',0) if unit.is_jumping else '-','-']


def template_info(unit):
    from physics.cargo import cargo_max_speed
    from physics.cargo import MP1
    from core.randomness import float32 as f32
    maximum=int(cargo_max_speed(unit));vertical=0
    if unit.move_type==M.VTOL:
        vertical=int(math.sqrt(max(0,f32(f32(f32(maximum)*maximum)-f32(f32(unit.desired_speed)*f32(unit.desired_speed))))))
        maximum=int(math.sqrt(max(0,f32(f32(f32(maximum)*maximum)-f32(f32(unit.vertical_speed)*f32(unit.vertical_speed))))))
    maximum=max(0,maximum)
    if unit.specials&Specials.TRIPLE_MYOMER_TECH and unit.heat>=9:maximum=int(math.ceil((round(maximum/1.5/MP1)+1)*1.5)*MP1)
    fuel=unit.fuel_orig if unit.unit_type in (U.VTOL,U.AERO,U.DS,U.SPHEROID_DS) and unit.fuel_orig else '-'
    return [type_char(unit),getattr(unit,'template_ref',''),getattr(unit,'template_name',unit.name),f'{maximum*2/3:.3f}',f'{maximum:.3f}',f'{-maximum*2/3:.3f}',f'{vertical:.3f}',fuel,unit.real_num_sinks,advtech(unit)]


class HudSession:
    def __init__(self,resolve):
        self.resolve=resolve;self.key=''

    def request(self,text,*,macro=False):
        records=[];wire=[];blocked=[]
        def emit(cls,kind,payload):
            payload=','.join(map(str,payload)) if isinstance(payload,(list,tuple)) else str(payload)
            records.append(dict(class_=cls,type=kind,payload=payload))
            records[-1]['class']=records[-1].pop('class_')
            wire.append(f'#HUD:{self.key or "???"}:{cls}:{kind}# {payload}\r\n' if cls else payload+'\r\n')
        def finish():return dict(ok=not macro and not any(r['type']=='E' for r in records),records=records,wire=''.join(wire),lines=[r['payload'] for r in records],blocked=blocked)
        text=text.lstrip()
        if macro:
            emit(None,None,'HUDINFO does not work from scode or macros.');return finish()
        if not text:
            emit(None,None,'#HUD hudinfo version 0.8');return finish()
        if text.startswith('key='):
            key=text[4:]
            if re.fullmatch('[a-zA-Z0-9]{0,20}',key) is None:emit('KEY','E','Invalid key')
            else:self.key=key;emit('KEY','R','Key set')
            return finish()
        if not self.key:emit('???','E','No session key set');return finish()
        cmd,*rest=text.split(maxsplit=1);arg=rest[0].lstrip() if rest else ''
        if not re.fullmatch('[a-zA-Z0-9]+',cmd):emit('???','E','Invalid subcommand');return finish()
        if cmd not in COMMANDS:emit('???','E',cmd+': subcommand not found');return finish()
        cls=cmd.upper()
        def error(message):emit(cls,'E',message);return finish()
        if cmd in ('asc','wsc','t'):
            if not arg:return error('Not enough arguments')
        elif arg:return error('Command takes no arguments')
        unit=self.resolve() if cmd!='wl' else None
        if cmd!='wl':
            if unit is None:return error('Not in a BattleTech unit')
            if cmd in ACTIVE:
                if unit.is_destroyed:return error('You are destroyed!')
                if not unit.is_started:return error('Reactor is not online')
            if unit.status&(S.UNCONSCIOUS|S.BLINDED):return error('You are unconscious....zzzzzzz')
        if cmd in ('gs','sgi'):
            emit(cls,'R',general(unit) if cmd=='gs' else template_info(unit));return finish()
        if cmd in ('con','co'):
            board=unit.map
            if board is not None and board.maplight not in (0,1,2):
                from core.effects import send_error
                send_error(unit,f'Unknown light type {board.maplight} on map #{board._id}')
            emit(cls,'R',[{0:'N',1:'T',2:'D'}.get(board.maplight,'?'),board.mapvis,board.grav,board.temp,''.join(c for flag,c in [(4,'V'),(16,'U'),(32,'D')] if board.flags&flag) or '-'] if board else '?,?,?,?,?')
            return finish()
        if cmd=='wl':
            for row in equipment.catalog_rows():emit(cls,'L',row)
        elif cmd in ('oas','as','asc'):
            if cmd=='asc':
                unit,message=self.scan_target(unit,arg,blocked)
                if message:return error(message)
            for loc in range(len(section_names(unit))):
                section=unit.sections[loc]
                if not section.internal_orig:continue
                if cmd=='asc':values=[GLYPHS[condition(unit,loc,k)[0]] if getattr(section,f+'_orig') else '-' for k,f in [('front','armor'),('rear','rear'),('internal','internal')]]
                else:values=[getattr(section,k+('_orig' if cmd=='oas' else '')) for k in ('armor','rear','internal')]
                emit(cls,'L',[short_section(unit,loc),*values])
        elif cmd in ('we','wsc','li'):
            if cmd=='wsc':
                unit,message=self.scan_target(unit,arg,blocked)
                if message:return error(message)
            equipment.refresh(unit)
            if cmd=='li':
                if unit.unit_type==U.MECH:
                    for loc in (0,1,5,6):
                        section=unit.sections[loc];emit(cls,'L',[short_section(unit,loc),'*' if unit.is_section_destroyed(loc) else str(section.recycle//2) if section.recycle else 'R'])
            else:
                runs=[r for r in equipment.weapon_runs(unit) if cmd=='we' or not unit.is_section_destroyed(r.section)]
                for number,run in enumerate(runs):
                    slot=unit.sections[run.section].criticals[run.critical];weapon=equipment.get_weapon_by_index(run.weapon_idx)
                    if cmd=='wsc':row=[number,equipment.catalog_index(run.weapon_idx),short_section(unit,run.section),'*' if equipment.part_is_nonfunctional(unit,run.section,run.critical) else '-' if run.data//2 else 'R']
                    else:row=[number,equipment.catalog_index(run.weapon_idx),slot.brand&15,short_section(unit,run.section)+('r' if slot.firemode&equipment.F.REAR_MOUNT else ''),equipment.weapon_status(unit,run.section,run.critical),equipment.fire_modes(unit,slot,weapon),equipment.ammo_modes(slot.ammomode)]
                    emit(cls,'L',row)
        elif cmd=='am':
            from systems.combat_ammunition import find_ammunition
            for index,g in enumerate(find_ammunition(unit,True)):emit(cls,'L',[index,equipment.catalog_index(g.weapon_idx),equipment.ammo_modes(g.mode),g.current,g.maximum])
        elif cmd=='c':
            if unit.map is None:return error('You are on no map')
            for row in list_contacts(unit):
                other=row['mech'];friend=row['identified'] and other.team==unit.team;rtc,btc=center(other)
                emit(cls,'L',[identity(other,friend),arcs(row['arc']),('P' if row['sees_primary'] else '')+('S' if row['sees_secondary'] else '') or '-',type_char(other),(other.name or '-') if row['identified'] else 'something',other.x,other.y,other.z,f"{row['range']:.3f}",row['bearing'],f'{other.speed:.3f}',f'{other.vertical_speed:.3f}',virtual_facing(other),getattr(other,'jump_heading',0) if other.is_jumping else '-',f'{rtc:.3f}',btc,other.tonnage,f'{other.heat:.0f}',status_string(other,0 if friend else 1) or '-'])
        elif cmd=='cb':
            if unit.map is None:return error('You are on no map')
            from systems.display_contacts import building_contacts
            rows,missing=building_contacts(unit);blocked.extend(missing)
            for row in rows:emit(cls,'L',[arcs(row['arcs']),row['name'],row['x'],row['y'],row['z']+1,f"{row['range']:.6f}",row['bearing'],row['cf'],row['max_cf'],row['hud_status']])
        elif cmd=='t':
            from systems.map_display import hud_tactical
            result=hud_tactical(unit,arg)
            if not result['ok']:return error(result['message'])
            emit(cls,'S',result['start'])
            for row in result['rows']:emit(cls,'L',row)
        emit(cls,'D','Done')
        return finish()

    @staticmethod
    def scan_target(unit,arg,blocked):
        if not unit.scan_range:return None,'Your system seems to be inoperational'
        target=contact_target(unit,arg) if len(arg)==2 else None
        if target is None:return None,'No such target'
        distance=fa_mech_range(unit,target)
        if not in_line_of_sight(unit,target,target.x,target.y,distance):return None,'No such target'
        observer=bool(unit.crit_status&C.OBSERVATORIC)
        if not observer and int(distance)>unit.scan_range:return None,'Out of range'
        if target.unit_type==U.MW or not in_line_of_sight_nb(unit,target,target.x,target.y,distance):return None,'Unable to scan target'
        if not observer:
            from systems.observation import scan_effects
            blocked.extend(scan_effects(unit,target))
        return target,None
