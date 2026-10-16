# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mechrep.c
#   btech/src/btech/mech.h
#   btech/template.c
# Historical Aerospace sources:
#   btech/template.c
#   src/hcode/btech/mech.h

"""BTMux brace templates on live units (template.c / mechrep.c).

File IDs are translated through the construction catalog. Parsing deliberately
retains defined writes on failure. The only mode grammar correction is approved
D1: each pipe token may belong to either table, but all tokens must be known.
"""
import re
from copy import copy, deepcopy
from pathlib import Path
from core.randomness import float32
from data import templates as t
from data.construction_catalog import Catalog, identify, runtime_part, source_id
from entities.mech import Mech, Section, UnitType as U, Specials as S, FireMode as F, SectionConfig as C, MechStatus
from entities.crittypes import is_weapon, is_ammo, is_bomb, weapon2i, i2special, Special, crits_in_loc
from entities.weapon import get_weapon_by_index, WeaponType as WT, WeaponFlags as W
from systems.damage_commands import section_names, atoi
from systems.construction_weight import weight, invalidate, fingerprint
from systems.weapon_inventory import sync_weapon_states
from systems.combat_ammunition import full_ammo


def diagnostic(unit, text):
    if not hasattr(unit,'construction_messages'): unit.construction_messages=[]
    unit.construction_messages.append(text)


def server_diagnostic(unit,text):
    from core.effects import send_error
    diagnostic(unit,text)
    return send_error(unit,text)


class TemplateError(ValueError):
    def __init__(self,text,*,audience='server'):
        super().__init__(text)
        self.audience=audience;self.reported=False


def report_template_error(unit,error,notify=None):
    if getattr(error,'reported',False):return
    if getattr(error,'audience','server')=='caller':
        (notify or (lambda text:diagnostic(unit,text)))(str(error))
    else:server_diagnostic(unit,str(error))
    error.reported=True


def reference_effect(unit):
    from core.attributes import attributes_for
    attributes_for(unit).set(unit._id,'A_MECHREF',unit.template_ref)
    if not hasattr(unit,'construction_external_effects'):unit.construction_external_effects=[]
    unit.construction_external_effects.append({'service':'local object attributes',
        'attribute':'A_MECHREF','value':unit.template_ref,'delivered':True})


AEROSPACE_PROFILE='aerospace_pre_at2_96f2131'
AEROSPACE_TYPES=(U.AERO,U.DS,U.SPHEROID_DS)


def template_commands(text):
    """Shared source command/value reader for profile selection and live writes."""
    from io import StringIO
    stream=StringIO(text)
    while line:=stream.readline(511):
        line=line[:-1].lstrip()  # fgets's final byte is unconditionally deleted.
        delimiter=line.find(' ')
        if delimiter>=0:
            tab=line.find('\t')
            if 0<=tab<delimiter:delimiter=tab
            command,rest=line[:delimiter],line[delimiter+1:]
        else:command,rest=line,''
        key=command.lower();iscrit=key.startswith('crit_');value=None
        if (t.name_index(t.LOAD_COMMANDS,command)>=0 or iscrit) and key!='comment' and (
                not iscrit or re.match(r'^CRIT_\s*[+-]?\d+',command)):
            value=t.read_brace_block(stream,rest)
        yield command,key,iscrit,value


def template_profile(text,unit,profile=None):
    if profile is not None:return profile
    # Read the same values as the loader, without touching live state. A Type
    # inside another field's multiline value is not a command; text before a
    # field's first brace is legal. Selection precedes entry-time reference I/O.
    kind=unit.unit_type
    for command,key,iscrit,value in template_commands(text):
        if key=='type':
            kind=t.name_index(t.MECH_TYPES,value)
            break
    return AEROSPACE_PROFILE if kind in AEROSPACE_TYPES else 'checked_in_pipeline_2026_09_15'


def atof(text):
    if re.match(r'\s*[+-]?(?:inf|nan)',text,re.I):raise ValueError('nonfinite source float')
    match=re.match(r'\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)',text)
    value=float32(float(match[1])) if match else 0.0
    import math
    if not math.isfinite(value): raise ValueError('nonfinite source float')
    return value


# Explicit rd/ud reset: pd, sd, object identity, map and engine stay attached.
_ZERO_FIELDS='''unit_type move_type tonnage num_sinks max_speed walk_speed run_speed
 jump_mp tac_range lrs_range scan_range computer radio radio_range radio_type si si_orig
 fuel fuel_orig hs_engine_override engine_rating template_max_speed cargo_space car_max_ton
 max_suits mech_bv targcomp jump_top aim_type base_to_hit pilot_skill_base engine_heat
 masc_value masc_counter fire_adjustment vis_mod charge_timer charge_distance prefs stagger_stamp
 jump_length going_x going_y desired_facing angle desired_angle jump_heading targ_z turret_facing
 turn_damage lateral num_seen lx ly carrying heat weap_heat plus_heat minus_heat
 start_fx start_fy start_fz end_fz vertical_speed speed desired_speed jump_speed
 crit_status status status2 specials specials2 specials_status tank_crit_status
 last_weapon_recycle cargo_weight last_rnd_update rnd last_ds_msg boom_start maxfuel
 lastused cocoon comm comm_last original_sinks disabled_sinks autopilot_num heatboom_last
 sspin start_spin can_see rtons rcw rspd per wxf last_startup infantry_specials scharge_counter
 stagger_damage last_stagger_notify crit_status2 xp_mod shots_fired shots_hit shots_missed
 damage_taken damage_inflicted units_killed last_stagger_check engine_hits gyro_hits
 sensor_hits'''.split()


def clear_mech(unit, clear_channels):
    for field in ('_catalog_baseline','template_origin','template_source'):
        unit.__dict__.pop(field,None)
    for name in _ZERO_FIELDS: setattr(unit,name,0)
    unit.name=unit.mech_type=unit.template_ref=unit.unit_era=unit.unit_tro=''
    for field in ('crew_stunned','tail_rotor_destroyed'):
        setattr(unit,field,False)
    # Vehicles expose read-only turret properties backed by tank_crit_status;
    # plain Mechs use independent mirrors for the same two bits.
    for field in ('turret_jammed','turret_locked'):
        if not isinstance(getattr(type(unit),field,None),property):setattr(unit,field,False)
    unit._crew_stun_until=0
    unit.sections=[Section() for _ in range(8)]
    # Section() has useful simulator defaults; bzero has none of them.
    for sec in unit.sections:
        sec.armor=sec.armor_orig=sec.internal=sec.internal_orig=sec.rear=sec.rear_orig=sec.config=sec.recycle=0
        for slot in sec.criticals:slot.desired_ammo_loc=0
    unit.weapons=[];unit.sensor=[0,0];unit.stagger_damage_list=[];unit.brief=1
    unit.target=unit.charge_target=unit.dfa_target=unit.spotter=unit.swarmer=-1
    unit.swarm_target=None  # Python's target-object sentinel represents source -1.
    unit.targ_x=unit.targ_y=-1;unit.pilot=None;unit.aim=8
    unit.construction_managed=True
    engine=getattr(unit,'_engine',None)
    if engine:
        from core.events import EventType
        engine.events.cancel_by_type_and_data(EventType.VEHICLE_BURN,unit)
    from systems.ammo_dump import sync_dump_state
    sync_dump_state(unit)
    unit.unjamming=bool(engine and engine.events.has_event_type_data(EventType.UNJAM_AMMO,unit))
    if clear_channels:
        unit.tics=[set() for _ in range(4)]
        unit.freq=[0]*16;unit.freqmodes=[0]*16;unit.chantitle=['']*16
    invalidate(unit)


def mode_masks(text):
    if text=='-': return 0,0
    fire=ammo=0
    while text:
        token,text=t.next_arg_delim(text)
        f=t.name_index(t.CRIT_FIRE_MODES,token);a=t.name_index(t.CRIT_AMMO_MODES,token)
        if f<0 and a<0: raise ValueError('Invalid critical mode')
        if f>=0: fire|=1<<f
        if a>=0: ammo|=1<<a
    return fire,ammo


def find_section(unit, text):
    return t.name_index(section_names(unit) or (),text.replace('_',' '))


def _ams(unit, slot):
    if is_weapon(slot.type):
        weapon=get_weapon_by_index(weapon2i(slot.type))
        if weapon.special&W.AMS: unit.specials|=S.CL_ANTI_MISSILE_TECH if weapon.special&W.CLAT else S.IS_ANTI_MISSILE_TECH


def load_critical(unit, loc, command, value, catalog,*,filename=None,historical=None):
    match=re.match(r'^CRIT_\s*([+-]?\d+)(?:-\s*([+-]?\d+))?',command)
    if not match:return False
    if historical is None:historical=unit.unit_type in AEROSPACE_TYPES
    start=int(match[1])-1;end=int(match[2] or match[1])-1
    if not 0<=loc<8 or not (0<=start<12 and 0<=end<12): raise ValueError('Critical slot bounds error')
    item,rest=t.next_arg(value);found=catalog.match('vlong',item)
    if found is None: raise TemplateError(f'Unable to find {item}')
    slot=unit.sections[loc].criticals[start]
    slot.type=runtime_part(found['source_part_id']);slot.brand=found['brand']&15 if catalog.parts else 0
    slot.desired_ammo_loc=-1
    token,rest=t.next_arg(rest)
    if is_weapon(slot.type):
        _ams(unit,slot);slot.data=0
        modes,rest=t.next_arg(rest)
        try:slot.firemode,slot.ammomode=mode_masks(modes)
        except ValueError as error:raise TemplateError(f'Error while loading: Invalid crit modes for {"weapon" if is_weapon(slot.type) else "ammo"}: {modes}.') from error
        brand,_=t.next_arg(rest)
        if catalog.parts and atoi(brand):slot.brand=atoi(brand)&15
    elif is_ammo(slot.type):
        slot.data=atoi(token);modes,rest=t.next_arg(rest)
        try:slot.firemode,slot.ammomode=mode_masks(modes)
        except ValueError as error:raise TemplateError(f'Error while loading: Invalid crit modes for {"weapon" if is_weapon(slot.type) else "ammo"}: {modes}.') from error
        if slot.data<full_ammo(unit,loc,start):
            slot.firemode|=F.HALFTON_MODE
            if slot.data>full_ammo(unit,loc,start):slot.firemode&=~F.HALFTON_MODE
        capacity=full_ammo(unit,loc,start)
        if slot.data!=capacity and unit.unit_type not in (U.MW,U.BSUIT):
            weapon=get_weapon_by_index(slot.type-193)
            server_diagnostic(unit,f'Invalid ammo crit for {weapon.name} in #{unit._id} {filename or unit.template_ref} ({slot.data}/{capacity})')
            slot.data=capacity
    else:
        slot.data=0 if historical else atoi(token);slot.firemode=slot.ammomode=0
        _,rest=t.next_arg(rest);brand,_=t.next_arg(rest)
        if catalog.parts and atoi(brand):slot.brand=atoi(brand)&15
    for pos in range(start+1,end+1):
        other=unit.sections[loc].criticals[pos]
        for name in ('type','data','firemode','ammomode','brand'):setattr(other,name,getattr(slot,name))
    return item[:3].lower()=='cl.'


_SCALARS={'tons':'tonnage','tac_range':'tac_range','lrs_range':'lrs_range','radio_range':'radio_range',
 'scan_range':'scan_range','heat_sinks':'real_num_sinks','computer':'computer','radio':'radio',
 'radiotype':'radio_type','mech_bv':'mech_bv','cargo_space':'cargo_space','max_suits':'max_suits',
 'max_ton':'car_max_ton','hsengoverride':'hs_engine_override'}


def load_stream(unit, stream, filename, *, catalog=None, finalize=True,notify=None,source_profile=None):
    # C1: normalize only physical CRLF, before source line/value processing.
    # StringIO preserves interior CR and the unterminated final-byte quirk.
    text=stream.read().replace("\r\n", "\n")
    source_profile=template_profile(text,unit,source_profile)
    historical=source_profile==AEROSPACE_PROFILE
    catalog=catalog or Catalog()
    unit.template_ref=unit.mech_type=Path(filename).name[:14 if historical else 24]
    reference_effect(unit)
    unit.radio_type=0
    loc=0;ok_count=0;clan=False;finished=False
    try:
        for command,key,iscrit,value in template_commands(text):
            if t.name_index(t.LOAD_COMMANDS,command)<0 and not iscrit:
                loc=find_section(unit,command)
                if loc<0:
                    if not ok_count:raise TemplateError(f'New template loading system: {filename} is invalid template file.',audience='caller')
                    raise TemplateError(f'Error while loading: Section {command} not found.')
                unit.sections[loc].recycle=0;ok_count+=1
                continue
            ok_count+=1
            if value is None:continue
            if iscrit:clan=load_critical(unit,loc,command,value,catalog,filename=filename,historical=historical) or clan
            elif key=='reference':
                if value!=unit.template_ref:server_diagnostic(unit,f'Template {filename} has Reference <-> Filename mismatch : {value} <-> {unit.template_ref} - It is automatically fixed by saving again.')
                reference_effect(unit)
            elif key in ('type','move_type'):
                table=t.MECH_TYPES if key=='type' else t.MOVE_TYPES
                result=t.name_index(table,value)
                setattr(unit,'unit_type' if key=='type' else 'move_type',result)
                if result<0:raise TemplateError(f'Error while loading: Type {value} not found.')
                if key=='type':unit.fuel=unit.fuel_orig=t.default_fuel_by_type(unit)
            elif key in _SCALARS:setattr(unit,_SCALARS[key],atoi(value))
            elif key in ('max_speed','jump_speed'):
                setattr(unit,key,atof(value))
                if key=='max_speed':
                    from entities.mech import CritStatus
                    from systems.vehicle_combat import correct_speed
                    unit.crit_status&=~CritStatus.SPEED_OK
                    correct_speed(unit)
                    unit.template_max_speed=unit.max_speed
            elif key in ('name','unit_era','unit_tro'):
                # mech.h: mech_name[31], unit_era[25], unit_tro[25].
                # Reject C buffer-overflow domains before assigning this field.
                limit=30 if key=='name' else 24
                if len(value)>limit:raise ValueError(f'{command} exceeds source string bounds ({limit})')
                setattr(unit,key,'Undefined' if key!='name' and len(value)==1 else value)
            elif key in ('si','fuel'):setattr(unit,key,atoi(value));setattr(unit,key+'_orig',atoi(value))
            elif key=='specials':
                if t.check_specials_list(t.SPECIALS_NAMES,t.SPECIALS2_NAMES,value):
                    # C stores dissipation directly; Python stores physical sinks.
                    # A later tech flag must not reinterpret an earlier scalar.
                    capacity=unit.real_num_sinks
                    unit.specials|=t.parse_bit_vector_lenient(t.SPECIALS_NAMES,value)
                    unit.specials2|=t.parse_bit_vector_lenient(t.SPECIALS2_NAMES,value)
                    unit.real_num_sinks=capacity
                if unit.specials==-1:raise TemplateError(f'Error while loading: Invalid specials - {value}.')
            elif key=='infantryspecials':
                if t.check_specials_list(t.INFANTRY_SPECIALS_NAMES,None,value):unit.infantry_specials|=t.parse_bit_vector_lenient(t.INFANTRY_SPECIALS_NAMES,value)
            elif key in ('armor','internals','rear'):
                field='internal' if key=='internals' else key
                setattr(unit.sections[loc],field,atoi(value));setattr(unit.sections[loc],field+'_orig',atoi(value))
            elif key=='config':unit.sections[loc].config=t.parse_bit_vector(t.SECTION_CONFIGS,value)&~int(C.CASE_TECH|C.SECTION_DESTROYED)
        if finalize:finish_load(unit,clan,catalog.parts,historical=historical);finished=True
    except ValueError as error:
        # Preserve the public source message while exposing its failing token
        # to complete compatibility reports. Prior defined writes stay intact.
        error.template_command=locals().get('command','')
        error.template_value=locals().get('value','') or ''
        report_template_error(unit,error,notify)
        raise
    finally:
        unit.construction_managed=True
        sync_weapon_states(unit)
        if not finished:invalidate(unit)
    return unit


def finish_load(unit, clan=False, parts=True,*,historical=None):
    from systems.repairs import sub_magic
    from systems.parts import update_specials
    from systems.construction_weight import internal_check
    from systems.map_conditions import update_conditions
    if historical is None:historical=unit.unit_type in AEROSPACE_TYPES
    unit.engine_rating=0;unit.engine_rating=unit.engine_size()
    if not getattr(unit,'unit_era',''):unit.unit_era='Undefined'
    if not getattr(unit,'unit_tro',''):unit.unit_tro='Undefined'
    if not unit.specials&S.ICE_TECH and not unit.real_num_sinks:unit.real_num_sinks=10
    if unit.unit_type==U.MECH:sub_magic(unit,True)
    if unit.unit_type==U.MW:
        from systems.startup import startup_state
        sync_weapon_states(unit)
        startup_state(unit._engine,unit)
    if parts:
        for loc,sec in enumerate(unit.sections[:8 if unit.unit_type==U.MECH else 6]):
            for slot in sec.criticals[:crits_in_loc(unit,loc)]:
                if slot.type and not slot.brand and not is_ammo(slot.type) and not is_bomb(slot.type):slot.brand=5 if clan else 3
    if not unit.computer:unit.computer=5 if clan else 2
    if not unit.radio:unit.radio=5 if clan else 3
    if not unit.radio_type:unit.radio_type=t.generic_radio_type(unit.radio,clan)
    for field,fn in (('scan_range',t.computers_scan_range),('tac_range',t.computers_tac_range),('lrs_range',t.computers_lrs_range),('radio_range',t.computers_radio_range)):
        if not getattr(unit,field):setattr(unit,field,int(fn(unit)))
    unit.specials&=~S.FLIPABLE_ARMS
    if unit.unit_type==U.MECH and all(unit.sections[loc].criticals[pos].type!=i2special(kind)
       for loc in (0,1) for pos,kind in ((2,Special.LOWER_ACTUATOR),(3,Special.HAND_OR_FOOT_ACTUATOR))):unit.specials|=S.FLIPABLE_ARMS
    update_specials(unit);unit.xp_mod=1.0;unit.units_killed=0
    internal_check(unit,True)
    value=weight(unit,0)['total']
    mismatch=value-unit.tonnage*1024
    warn=abs(mismatch)>40 if historical else mismatch>40 and unit.unit_type!=U.BSUIT and unit.move_type!=10
    if warn:
        server_diagnostic(unit,f"Error in {unit.template_ref} template: {value/1024:.1f} tons of 'stuff', yet {unit.tonnage} ton frame.")
    t.update_oweight(unit,value)
    if unit.map is not None:update_conditions(unit,unit.map)
    if not historical:
        for sec in unit.sections:
            if not sec.internal_orig:sec.config|=C.SECTION_DESTROYED
    unit._construction_weight_state=(getattr(unit,'construction_dynspeed',True),fingerprint(unit))


def load_template(unit, filename, **options):
    with open(filename,encoding='ascii',newline='') as stream:return load_stream(unit,stream,filename,**options)


def tc_able(part):
    weapon=get_weapon_by_index(weapon2i(part))
    return (weapon.weapon_type in (WT.TBEAM,WT.TAMMO) and weapon.name[3:] not in ('Flamer','MachineGun','LightMachineGun','HeavyMachineGun')
            and not weapon.special&(W.PC_IMPA|W.PC_SHAR|W.PC_HEAT))


def dump_item(stream,unit,loc,pos,*,catalog=None):
    catalog=catalog or Catalog();slots=unit.sections[loc].criticals;slot=slots[pos]
    if not slot.type or unit.unit_type!=U.MECH and t.invalid_vehicle_item(unit,loc,pos):return 1
    fields=('type','data','firemode','ammomode')+(('brand',) if catalog.parts else ())
    end=pos+1
    while end<12 and all(getattr(slots[end],n)==getattr(slot,n) for n in fields):end+=1
    fire=slot.firemode
    if is_weapon(slot.type):
        from systems.weapon_inventory import weapon_crits
        end=min(end,pos+weapon_crits(unit,weapon2i(slot.type)))
        if not tc_able(slot.type):fire&=~F.ON_TC
    command=f'CRIT_{pos+1}'+(f'-{end}' if end>pos+1 else '')
    name=catalog.names(source_id(slot.type))[2]
    if name is None:raise ValueError('Unsupported part in save')
    modes=t.bit_names_delim2(t.CRIT_FIRE_MODES,t.CRIT_AMMO_MODES,fire,slot.ammomode) if fire or slot.ammomode else '-'
    brand=f'{slot.brand&15} ' if catalog.parts else ''
    if is_weapon(slot.type):value=f'{name} - {modes} {brand}'
    elif is_ammo(slot.type):value=f'{name} {full_ammo(unit,loc,pos)} {modes} - '
    elif is_bomb(slot.type):value=f'{name} - - - '
    else:value=f'{name} {slot.data or "-"} - {brand}'
    stream.write(f'    {command}\t\t  {{ {value}}}\n')
    return end-pos


def dump_locations(stream,unit,*,catalog=None):
    catalog=catalog or Catalog()
    for loc,name in enumerate(section_names(unit)):
        sec=unit.sections[loc]
        if not sec.internal_orig:continue
        stream.write(name.replace(' ','_')+'\n')
        for label,field in (('Armor','armor_orig'),('Internals','internal_orig'),('Rear','rear_orig')):
            if getattr(sec,field):stream.write(f'  {label:<16} {{ {getattr(sec,field)} }}\n')
        config=int(sec.config)&~int(C.CASE_TECH)
        if config:stream.write(f'  Config           {{ {t.bit_names(t.SECTION_CONFIGS,config)} }}\n')
        pos=0
        while pos<crits_in_loc(unit,loc):pos+=dump_item(stream,unit,loc,pos,catalog=catalog)


def saved_specials(unit):
    first=int(unit.specials)&~sum(1<<i for i in (0,1,2,4,7,8,9,10,11,15,18,19,20))
    if unit.unit_type==U.MECH:first&=~sum(1<<i for i in (21,24,25,26))
    second=int(unit.specials2)&~sum(1<<i for i in (0,1,4,5,11,12,14,15,24))
    return first,second


def save_template(unit,reference,filename,*,catalog=None,caller='local',caller_id=0,clock=None):
    from datetime import datetime,timezone
    if not unit.computer:t.computer_conversion(unit)
    if not unit.name:unit.name=identify(reference) or ''
    clock=clock or datetime.now(timezone.utc)
    stamp=clock.ctime() if hasattr(clock,'ctime') else str(clock)
    with open(filename,'w',encoding='ascii',newline='') as stream:
        def emit(label,value):stream.write(f'{label:<16} {{ {value} }}\n')
        if unit.name:emit('Name',unit.name)
        emit('Reference',reference);emit('Type',t.MECH_TYPES[unit.unit_type])
        emit('Unit_Era',getattr(unit,'unit_era',''));emit('Unit_TRO',getattr(unit,'unit_tro',''))
        emit('Move_Type',t.MOVE_TYPES[unit.move_type]);emit('Tons',unit.tonnage)
        emit('Comment',f'Saved by: {caller}(#{caller_id}) at {stamp}')
        for label,field,fn,default in (('Tac_Range','tac_range',t.computers_tac_range,20),('LRS_Range','lrs_range',t.computers_lrs_range,40),
           ('Scan_Range','scan_range',t.computers_scan_range,20),('Radio_Range','radio_range',t.computers_radio_range,80)):
            value=getattr(unit,field)
            if value!=(fn(unit) if unit.computer else default):emit(label,value)
        defaults=(('Computer','computer',2),('Radio','radio',3),('HSEngOverRide','hs_engine_override',0),
          ('Heat_Sinks','real_num_sinks',0 if unit.specials&S.ICE_TECH else 10),
          ('RadioType','radio_type',t.generic_radio_type(unit.radio,bool(unit.specials&S.CLAN_TECH))),
          ('Mech_BV','mech_bv',2000),('Cargo_Space','cargo_space',2000),('Max_Ton','car_max_ton',0),
          ('Max_Suits','max_suits',2000),('SI','si_orig',0),('Fuel','fuel_orig',t.default_fuel_by_type(unit)))
        for label,field,default in defaults:
            value=getattr(unit,field,0)
            if value!=default:emit(label,value)
        emit('Max_Speed',f'{unit.max_speed:.2f}')
        if unit.jump_speed>0:emit('Jump_Speed',f'{unit.jump_speed:.2f}')
        first,second=saved_specials(unit)
        if first or second:emit('Specials',t.bit_names2(t.SPECIALS_NAMES,t.SPECIALS2_NAMES,first,second))
        if unit.infantry_specials:emit('InfantrySpecials',t.bit_names(t.INFANTRY_SPECIALS_NAMES,unit.infantry_specials))
        dump_locations(stream,unit,catalog=catalog)


def isolated_template(unit):
    baseline=copy(unit)
    # No deep-copy of engine/map graph or another live unit via targets.
    baseline._engine=baseline.map=baseline.pilot=None;baseline.mapindex=-1
    for name in ('_catalog_baseline','attribute_store','template_directory'):
        baseline.__dict__.pop(name,None)
    baseline.sections=deepcopy(unit.sections);baseline.weapons=deepcopy(unit.weapons)
    baseline.tics=deepcopy(unit.tics)
    for name in ('freq','freqmodes','chantitle','sensor','stagger_damage_list','construction_messages','construction_external_effects'):
        if hasattr(unit,name):setattr(baseline,name,deepcopy(getattr(unit,name)))
    return baseline
