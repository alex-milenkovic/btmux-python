# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.move.c
#   btech/mech.notify.c
#   btech/mech.scan.c
#   btech/mech.status.c
# Historical Aerospace sources:
#   btech/ds.turret.c

"""Pilot status, weapon/critical displays and read-only status query surfaces."""
import re
from functools import lru_cache
from entities.mech import UnitType as U, MoveType as M, FireMode as F, Specials as SP, MechStatus as S, CritStatus as C, SectionConfig
from entities.crittypes import Special,is_weapon,is_ammo,is_actuator,is_cargo,i2special,weapon2i,ammo2weapon_i,crits_in_loc
from entities.weapon import get_weapon_by_index,WeaponFlags as W
from systems.damage_commands import section_names,armor_section_from_string
from systems.weapon_inventory import weapon_runs,weapon_crits
from systems.equipment_display import refresh
from systems.combat import part_is_nonfunctional
from systems.enhanced_crits import part_temp_nuke,count_damaged_slots_from_crit
from systems.network_reports import ammo_letter,fire_letter,ammo_description,show_flags
from systems.combat_ammunition import full_ammo,find_ammunition
from systems.armor_display import armor_display,plain
from systems.observation import response,status_string,turret_facing
from physics.hexmath import acceptable_degree


@lru_cache(maxsize=1)
def catalog():
    from data.construction_catalog import Catalog
    return Catalog()


def catalog_part_name(part,brand=0,*,long=False,owner=None,part_catalog=None):
    """Nullable generic C part_name/part_name_long, using source part IDs."""
    if not part:return 'Empty'
    names=part_catalog or catalog()
    try:entry=names.names(part,brand)
    except (ValueError,TypeError):
        entry=None
        names.messages.append(f'No index for {part}/0')
    text=entry[2 if long else 1] if entry else None
    if not text:
        if owner is not None:
            from core.effects import send_error
            send_error(owner,f'No index for {part}/0')
        return None
    text={'LifeSupport':'Life Support','TripleStrengthMyomer':'Triple Strength Myomer'}.get(text,text)
    if 'Actuator' in text and not text.startswith('Actuator'):text=text.split('Actuator')[0]+' Actuator'
    return text.replace('_',' ').replace('.',' ')


def part_name(unit,loc,pos,long=False,position=True,historical=None):
    from data.construction_catalog import source_id
    from systems.parts import reverse_split_crit_loc
    if position and not (0<=loc<8 and 0<=pos<12):
        from core.effects import send_error
        send_error(unit,f'INVALID: For mech #{unit._id}, {loc}/{pos} was requested.')
        return '--?LocationBug?--'
    slot=unit.sections[loc].criticals[pos];kind=slot.type
    if not kind:return 'Empty'
    from systems.movement_commands import historical_aircraft
    historical=historical_aircraft(unit) if historical is None else historical
    if position:
        leg=loc in (5,6) or unit.move_type==M.QUAD
        if kind==i2special(Special.SHOULDER_OR_HIP):return 'Hip' if leg else 'Shoulder'
        if kind==i2special(Special.HAND_OR_FOOT_ACTUATOR):return 'Foot Actuator' if leg else 'Hand Actuator'
    if position and not historical:
        if kind==i2special(Special.HEAT_SINK):return 'Double Heatsink' if unit.specials&(SP.DOUBLE_HEAT_TECH|SP.CLAN_TECH) else 'Heatsink'
        if kind in (i2special(Special.SPLIT_CRIT_LEFT),i2special(Special.SPLIT_CRIT_RIGHT)):
            other=reverse_split_crit_loc(unit,loc,pos)
            if other>=0 and 0<=slot.data<12:slot=unit.sections[other].criticals[slot.data];kind=slot.type
        if kind==i2special(Special.ENGINE):return 'Engine'+next((' ('+name+')' for flag,name in [(SP.LE_TECH,'Light'),(SP.CE_TECH,'Compact'),(SP.XXL_TECH,'XXL'),(SP.XL_TECH,'XL')] if unit.specials&flag),'')
        if kind==i2special(Special.JUMP_JET):return 'JumpJet (Improved)' if unit.specials2&0x80 else 'Jumpjet'
        if kind==i2special(Special.COCKPIT):return 'Small Cockpit' if unit.specials2&0x2000000 else 'Cockpit'
    try:part=source_id(kind)
    except ValueError:part=kind
    text=catalog_part_name(part,slot.brand&15,long=long,owner=unit)
    return text if text is not None or not position else '--?ErrorInTemplate?--'


def query(unit,kind,section=None,slot_number=None,flag=None):
    from data.construction_catalog import source_id
    from systems.economic_inventory import is_crap
    from systems.repair_materials import find_ammo_type,repair_alias
    loc=armor_section_from_string(unit,section or '')
    if kind=='armorstatus' and section=='all':
        sections=unit.sections[:len(section_names(unit))]
        return f'{sum(s.armor+s.rear for s in sections)}/{sum(s.armor_orig+s.rear_orig for s in sections)}|{sum(s.internal for s in sections)}/{sum(s.internal_orig for s in sections)}'
    if not(kind=='weaponstatus' and section is None):
        if loc<0 or kind!='sectstatus' and not unit.sections[loc].internal_orig:return '#-1 INVALID SECTION'
    if kind=='sectstatus':return str(-1 if unit.sections[loc].config&SectionConfig.SECTION_FLOODED else int(not unit.is_section_destroyed(loc)))
    if kind=='armorstatus':
        s=unit.sections[loc];return f'{s.armor}/{s.armor_orig}|{s.internal}/{s.internal_orig}|{s.rear}/{s.rear_orig}'
    if kind=='weaponstatus':
        rows=[]
        from systems.weapon_inventory import find_weapons
        for run in (weapon_runs(unit) if section is None else find_weapons(unit,loc) or []):
            slot=unit.sections[run.section].criticals[run.critical];w=get_weapon_by_index(run.weapon_idx);entry=catalog().names(source_id(slot.type),slot.brand&15)
            state=2 if part_is_nonfunctional(unit,run.section,run.critical) else int(bool(part_temp_nuke(slot)))
            rows.append('|'.join(map(str,[len(rows),entry[1] if entry else '',weapon_crits(unit,run.weapon_idx),slot.brand&15,w.vrt,run.data,int(w.weapon_type),state])))
        return ','.join(rows)
    if kind=='critstatus':
        rows=[]
        for pos,slot in enumerate(unit.sections[loc].criticals[:crits_in_loc(unit,loc)]):
            part=find_ammo_type(unit,loc,pos) if is_ammo(slot.type) else source_id(slot.type)
            entry=catalog().names(part,slot.brand&15)
            state=-1 if part_is_nonfunctional(unit,loc,pos) and part and (not is_crap(part) or unit.is_section_destroyed(loc)) else part_temp_nuke(slot)
            category=1 if is_weapon(part) else 2 if is_ammo(part) else 3 if is_actuator(part) else 4 if is_cargo(part) else 5 if is_crap(part) else 0
            rows.append(f'{pos+1}||{entry[1] if entry and entry[1] else "Empty"}|{state}|{category}')
        return ','.join(rows)
    if kind!='critslot':raise ValueError('Unknown status query')
    from systems.movement_commands import c_number
    pos=int(c_number(slot_number,True))-1
    if not 0<=pos<crits_in_loc(unit,loc):return '#-1 INVALID CRITICAL'
    slot=unit.sections[loc].criticals[pos];field=(flag or 'NAME').upper();part=slot.type
    if field=='STATUS':return 'Disabled' if slot.firemode&F.DISABLED_MODE else 'Destroyed' if slot.firemode&F.DESTROYED_MODE else 'Operational'
    if field=='DATA':return str(slot.data)
    if field in ('MAXAMMO','AMMOTYPE','HALFTON'):
        if not is_ammo(part):return '#-1 NOT AMMO'
        if field=='MAXAMMO':return str(full_ammo(unit,loc,pos))
        if field=='HALFTON':return str(int(bool(slot.firemode&F.HALFTON_MODE)))
        part=find_ammo_type(unit,loc,pos)
    elif field=='MODE':
        if not is_weapon(part):return '#-1 NOT AMMO OR WEAPON'
        return fire_letter(slot.firemode)+ammo_letter(get_weapon_by_index(weapon2i(part)),slot.ammomode)
    else:part=repair_alias(unit,source_id(part))
    if is_crap(part):return 'Empty'
    entry=catalog().names(part,slot.brand&15)
    return entry[2] if entry and entry[2] else 'Empty'


def critical_display(unit,loc,historical=None):
    slots=[];maximum=crits_in_loc(unit,loc)
    # Odd legal counts (fighter cockpit) retain every slot once.
    left=(maximum+1)//2
    order=[p for pair in zip(range(left),range(left,maximum)) for p in pair]
    if maximum%2:order.append(left-1)
    from systems.economic_inventory import is_crap
    for pos in order:
        slot=unit.sections[loc].criticals[pos];kind=slot.type
        if is_ammo(kind):
            w=get_weapon_by_index(ammo2weapon_i(kind));text=w.name[3:]+ammo_description(w,slot.ammomode)+' Ammo'
            if not part_is_nonfunctional(unit,loc,pos):text+=f' [{slot.data:03d}/{full_ammo(unit,loc,pos):03d}]'
        else:
            text=('OS ' if is_weapon(kind) and slot.firemode&F.OS_MODE else '')+part_name(unit,loc,pos,historical=historical)
            if is_weapon(kind) and (slot.firemode&F.OS_MODE and slot.firemode&F.OS_USED or slot.firemode&F.ROCKET_FIRED):text+=' (Empty)'
            if slot.firemode&F.WILL_JETTISON_MODE:text+=' (backpack)'
            if is_weapon(kind) and slot.firemode&F.REAR_MOUNT:text+=' (R)'
            if kind==i2special(Special.ARTEMIS_IV) and slot.data and not part_is_nonfunctional(unit,loc,pos):text+=f' [Controls Slot {slot.data}]'
        suffix=''
        if kind and slot.firemode&(F.DESTROYED_MODE|F.BROKEN_MODE) and (not is_crap(kind) or unit.is_section_destroyed(loc)):suffix='Destroyed' if slot.firemode&F.DESTROYED_MODE else 'Broken'
        elif kind and slot.firemode&F.DISABLED_MODE:suffix='Disabled'
        elif kind and slot.firemode&F.DAMAGED_MODE:suffix='Damaged'
        if suffix:text+=' ('+suffix+')'
        slots.append(dict(number=pos+1,name=part_name(unit,loc,pos,historical=historical),suffix=suffix,text=f'{pos+1:2d} '+text))
    lines=menu_lines(section_names(unit)[loc]+' Criticals',[row['text'] for row in slots],2)
    return response(message='\n'.join(lines),lines=lines,slots=slots)


def physical_present(unit,loc,name):
    special={'axe':Special.AXE,'sword':Special.SWORD,'mace':Special.MACE,'saw':Special.DUAL_SAW,'claw':Special.CLAW}.get(name)
    if special is None:return False
    return sum(s.type==i2special(special) for s in unit.sections[loc].criticals)>=(7 if name=='saw' else unit.tonnage//15)


def physical_usable(unit,loc,name):
    if name not in ('axe','sword','mace','saw','claw') or unit.is_section_destroyed(loc):return False
    if name=='claw':return True
    def okay(pos,kind):return unit.sections[loc].criticals[pos].type==i2special(kind) and not part_is_nonfunctional(unit,loc,pos)
    return okay(0,Special.SHOULDER_OR_HIP) and (name=='saw' or okay(3,Special.HAND_OR_FOOT_ACTUATOR))


def ammo_color(now,maximum):
    percent=now*100//maximum if maximum else 0
    return '%ch%cg' if percent>=50 else '%ch%cy' if percent>=25 else '%ch%cr'


def owner_weapon_state(unit,run):
    slot=unit.sections[run.section].criticals[run.critical];failure=part_temp_nuke(slot)
    if slot.firemode&(F.BROKEN_MODE|F.DESTROYED_MODE) or failure==5:return '*****','%ch%cx*****%c  || '
    if slot.firemode&F.DISABLED_MODE:return 'DISABLE','%crDISABLE%c|| '
    if failure in (1,2,3,4,6):
        text,field={1:('JAMMED','%crJAMMED%c || '),2:('SHORTED','%crSHORTED%c|| '),3:('DUD','%crDUD%c    || '),4:('EMPTY',' %crEMPTY%c || '),6:('AMMOJAM','%crAMMOJAM%c|| ')}[failure]
        return text,field
    if failure:return '', ''
    if slot.firemode&F.ROCKET_FIRED:return 'Empty','%ch%cxEmpty%c  || '
    if run.data:return str((run.data+1)//2),f' {(run.data+1)//2:2d}    || '
    if count_damaged_slots_from_crit(unit,run.section,run.critical):return 'DAMAGED','%crDAMAGED%c|| '
    return 'Ready','%cgReady%c  || '


def weapon_display(unit,owner=True,compact=False):
    refresh(unit);lines=[];physical=[]
    if owner:
        lines.extend(advanced_status(unit))
        if unit.unit_type==U.MECH and not compact:
            labels=('FLLEG','FRLEG','RLLEG','RRLEG') if unit.move_type==M.QUAD else ('LARM','RARM','LLEG','RLEG')
            for label,loc in zip(labels,(0,1,5,6)):
                s=unit.sections[loc];state='%ch%cx*****%c' if unit.is_section_destroyed(loc) else f'{(s.recycle+1)//2:<5}' if s.recycle else '%cgReady%c'
                physical.append(dict(name=label,section=loc,status=plain(state),text=state))
            line=''.join(f"{p['name']}: {p['text']} " for p in physical)
            for name in ('axe','sword','claw','mace','saw'):
                for loc in (0,1):
                    if physical_present(unit,loc,name):
                        state='XX' if not physical_usable(unit,loc,name) else str((unit.sections[loc].recycle+1)//2) if unit.sections[loc].recycle else 'Rdy'
                        label=name.title()+('[LA]' if loc==0 else '[RA]');physical.append(dict(name=label,section=loc,status=state));line+=f'{label}: '+('%ch%crXX%c' if state=='XX' else '%cgRdy%c' if state=='Rdy' else state.ljust(3))+' '
            lines.append(line[:159])
            if unit.status&S.FLIPPED_ARMS:lines.append('*** Mech arms are flipped into the rear arc ***')
        elif unit.unit_type==U.BSUIT and not compact:
            section=next((s for s in unit.sections if s.internal),None)
            if section:lines.append('Team status (special attacks): '+(f'{(section.recycle+1)//2:<5}' if section.recycle else '%cgReady%c'))
        elif unit.unit_type in (U.VEH_GROUND,U.VTOL) and not compact and unit.sections[2].recycle:
            lines.append('Vehicle status (charge): '+('%ch%cx*****%c' if unit.is_section_destroyed(2) else f'{(unit.sections[2].recycle+1)//2:<5}'))
    if not compact:lines.extend(['==================WEAPON SYSTEMS===========================AMMUNITION========','------ Weapon --------- [##] '+('Holder' if unit.unit_type==U.BSUIT else 'Location')+(' ------ Status' if unit.unit_type==U.BSUIT else ' ---- Status')+' ||--- Ammo Type ---- Rounds'] if owner else ['================WEAPON SYSTEMS================','----- Weapon ------ [##]  '+('Holder ------ Status' if unit.unit_type==U.BSUIT else 'Location ---- Status')])
    groups=find_ammunition(unit,False) if owner else [];weapons=[];ammunition=[]
    for g in groups:
        w=get_weapon_by_index(g.weapon_idx);text=f'{w.name[3:]:16.16s} {ammo_letter(w,g.mode)}  {ammo_color(g.current,g.maximum)}{g.current:3d}%cn'
        ammunition.append(dict(weapon_idx=g.weapon_idx,current=g.current,maximum=g.maximum,mode=g.mode,color=ammo_color(g.current,g.maximum),text=text))
    for run in weapon_runs(unit):
        if not owner and unit.is_section_destroyed(run.section):continue
        number=len(weapons);slot=unit.sections[run.section].criticals[run.critical];w=get_weapon_by_index(run.weapon_idx);location=section_names(unit)[run.section]
        if owner:
            state,field=owner_weapon_state(unit,run)
            if w.special&W.AMS:markers='  ON ' if unit.status&S.AMS_ENABLED else ' OFF '
            else:markers=('R' if slot.firemode&F.REAR_MOUNT else ' ')+('-' if slot.firemode&(F.OS_USED|F.ROCKET_FIRED) else 'O' if slot.firemode&F.OS_MODE else ' ')+ammo_letter(w,slot.ammomode)+fire_letter(slot.firemode)+('T' if slot.firemode&F.ON_TC and not unit.crit_status&C.TC_DESTROYED else 'J' if slot.firemode&F.IS_JETTISONED_MODE else 'P' if slot.firemode&F.WILL_JETTISON_MODE else ' ')
            name=('OS ' if slot.firemode&F.OS_MODE and not w.special&W.AMS else '')+w.name[3:]
            text=f' {name:16.16s} {markers} [{number:2d}] {location:14.14s}'+field+(ammunition[number]['text'] if number<len(ammunition) else '   ')
        else:
            state='*****' if part_is_nonfunctional(unit,run.section,run.critical) else '-----' if run.data else 'Ready'
            field='%ch%cx*****%c' if state=='*****' else '%cgReady%c' if state=='Ready' else state
            text=f' {w.name[3:]:18.18s} [{number:2d}]  {location:14.14s}'+field
        weapons.append(dict(number=number,weapon_idx=run.weapon_idx,name=w.name,section=run.section,status=state,text=text))
        if not compact:lines.append(text)
    for row in ammunition[len(weapons):]:lines.append('                                                  || '+row['text'])
    return response(message='\n'.join(lines),lines=lines,weapons=weapons,ammunition=ammunition,physical=physical)


def advanced_status(unit):
    from systems import ecm,c3
    from systems.targeting import resolve_unit,is_tag_destroyed,tag_recycling
    from systems.notifications import identity
    entries=[];lines=[]
    def suite(name,destroyed,enabled,active,counter):
        value='%ch%crXX%cn' if destroyed else ('%ch%cgECM%cn' if active else '%ch%crECM%cn') if enabled else '%ch%cgECCM%cn' if counter else '%crOff%cn' if ecm.ecm_countered(unit) else '%cgOff%cn'
        entries.append(name+'('+value+')  ')
    if unit.specials&SP.ECM_TECH:suite('ECM',bool(unit.crit_status&C.ECM_DESTROYED),ecm.ecm_enabled(unit),ecm.ecm_active(unit),ecm.eccm_enabled(unit))
    if unit.specials2&0x1000:suite('AngelECM',bool(unit.crit_status&C.ANGEL_ECM_DESTROYED),ecm.angel_ecm_enabled(unit),ecm.angel_ecm_active(unit),ecm.angel_eccm_enabled(unit))
    if unit.infantry_specials&128:suite('PersonalECM',False,ecm.per_ecm_enabled(unit),ecm.per_ecm_active(unit),ecm.per_eccm_enabled(unit))
    for word,bit,name,damage,active,ready in [('specials2',1,'SthArmor',C.ECM_DESTROYED,0x40,'Rdy'),('specials2',0x10,'NullSigSys',C.NSS_DESTROYED,0x80,'Rdy'),('specials',SP.SLITE_TECH,'SLITE',C.SLITE_DEST,0x20,'Off')]:
        if getattr(unit,word)&bit:
            value=('%cr%chXX%cn' if name=='SLITE' else '%ch%crXX%cn') if unit.crit_status&damage else '%ch%cgOn%cn' if unit.status2&active else '%cg'+ready+'%cn'
            entries.append(name+'('+value+')  ')
    for word,bit,name,ordinary in [('specials',SP.C3_MASTER_TECH,'C3M',True),('specials',SP.C3_SLAVE_TECH,'C3S',True),('specials2',0x20,'C3i',False)]:
        if getattr(unit,word)&bit:
            color='%cr' if c3.disabled(unit,ordinary) else '%cy' if ecm.any_ecm_disturbed(unit) else '%cg%ch' if c3.network_size(unit,ordinary)>0 else '%cg'
            entries.append(color+name+'%cn  ')
    if unit.specials&SP.TRIPLE_MYOMER_TECH:entries.append('TSM('+('%ch%cgOn%cn' if unit.heat>=9 else '%cgOff%cn')+')  ')
    if unit.specials2&0x8000 or unit.specials&SP.C3_MASTER_TECH:
        target=resolve_unit(unit,getattr(unit,'tag_target',-1));recycling=bool(unit._engine and tag_recycling(unit._engine,unit))
        value='%cr%chXX%cn' if is_tag_destroyed(unit) else (('%cy%ch' if recycling else '%ch')+identity(unit,target)+'%cn') if target and target.tagged_by==unit._id else '%cy%chNot Rdy%cn' if recycling else '%cgRdy%cn'
        entries.append('TAG('+value+')  ')
    for word,bit,name,counter,enabled in [('specials2',0x40000,'SCHARGE','scharge_counter',S.SCHARGE_ENABLED),('specials',SP.MASC_TECH,'MASC','masc_counter',S.MASC_ENABLED)]:
        if getattr(unit,word)&bit:
            value=getattr(unit,counter,0);entries.append(f'{name}: '+('%ch%cr' if value>3 else '%ch%cy' if value>0 else '%cg')+str(value)+f'%cn ({"On" if unit.status&enabled else "Off"})')
    if entries:lines.append(('AdvTech: '+''.join(entries))[:159])
    if unit.specials2&0x80000:lines.append(f'Carrier: {int(getattr(unit,"cargo_space",0)/100)} tons free, {getattr(unit,"car_max_ton",0)} tons max unit size')
    sensors=[name for word,bit,name in [('specials',SP.AA_TECH,'Radar'),('specials',SP.BEAGLE_PROBE_TECH,'BeagleProbe'),('specials2',0x800,'BloodhoundProbe')] if getattr(unit,word)&bit]
    if sensors:lines.append('AdvSensors:'+' '.join(['',*sensors]))
    items=[name for bit,name in [(8,'PurifierStealth'),(16,'KageStealth'),(32,'AchileusStealth'),(64,'InfiltratorStealth'),(128,'InfiltratorIIStealth')] if unit.infantry_specials&bit]
    if items:lines.append('AdvItems: '+' '.join(items))
    actions=[name for bit,name in [(2,'MountFriends'),(1,'SwarmAttack'),(4,'AntiLegAttack'),(512,'BackPackJettison')] if unit.infantry_specials&bit]
    if actions:lines.append('Special Actions: '+' '.join(actions))
    if unit.infantry_specials&256:lines.append('Requirements: Must jettison backpack before using special abilities or jumping')
    return lines


def heat_bar(unit,caller=None):
    from core.attributes import player_preference
    preference=str(player_preference(unit,caller,'A_HEATCHARS','heatchars')).split('\0',1)[0]
    if preference and (not preference.startswith('[') or len(preference)<9):return None
    # sscanf returns eight assignments even if the following ']' is absent.
    fillchars=preference[1:9] if preference else '.:::::::'
    plus,minus=int(unit.plus_heat),int(unit.minus_heat);start=max(0,minus-27);remaining=max(0,plus-start)
    text='%cx%ch'+('<' if start else ' ')+'%cx%ch';counter=start
    for state,(end,prefix) in enumerate([(minus,''),(minus+7,'%cg%ch|%c%cg'),(minus+13,'%ch'),(minus+16,'%c%cy%ch|%c%cy'),(minus+18,'%ch'),(minus+24,'%c%cr%ch|%c%cr'),(minus+40,'%ch')],1):
        text+=prefix
        while counter<end:
            text+=fillchars[state if remaining else 0];remaining=max(0,remaining-1);counter+=1
    return dict(text='Temp:'+text+'%cw%ch|%c',start=start,indicator='<' if start else ' ')


def selected_components(argument):
    flags=set('AIWH') if not argument else set()
    i=0
    while i<len(argument):
        char=argument[i].upper()
        if char in 'RAWINSH':flags.add(char)
        if char=='R':flags.update('AIWH')
        if char in 'AIW' and argument[i+1:i+2].upper()=={'A':'R','I':'N','W':'E'}[char]:
            while i+1<len(argument) and argument[i+1]!=' ':i+=1
        i+=1
    if 'S' in flags:return ['short','target']
    if 'N' in flags:
        return ['compact-template']+(['armor'] if 'A' in flags else [])+(['heat'] if 'H' in flags and 'I' not in flags else [])+(['weapons'] if 'W' in flags else [])
    result=[]
    if 'H' not in flags or flags&set('AIW'):result.append('template-generic' if 'R' in flags else 'generic')
    for char,name in [('A','armor'),('I','info')]:
        if char in flags:result.append(name)
    if flags&set('IH'):result.append('heat')
    if 'W' in flags:result.append('weapons')
    return result


def target_lines(unit):
    from systems.targeting import resolve_unit,fa_mech_range
    from systems.los import in_line_of_sight
    from physics.hexmath import find_bearing,in_weapon_arc,TURRETARC
    from systems.network_reports import arc_label
    from systems.notifications import identity
    lines=[];target=resolve_unit(unit,unit.target)
    if target:
        distance=fa_mech_range(unit,target)
        if not in_line_of_sight(unit,target,target.x,target.y,distance):lines.append('Target: NOT in line of sight!\n')
        else:
            lines.append(f'Target: {identity(unit,target)}\t   Range: {distance:.1f} hexes   Bearing: {find_bearing(unit.fx,unit.fy,target.fx,target.fy)} deg\n'[:99])
            arc=in_weapon_arc(unit,target.fx,target.fy);aim=getattr(unit,'aim',8);aimtype=getattr(unit,'aim_type',-1)
            location=section_names(target)[aim] if aimtype==target.unit_type and 0<=aim<len(section_names(target)) else 'None'
            lines.append(f'Target in {"Turret" if arc&TURRETARC else arc_label(unit,arc)} Weapons Arc\t   Aimed Shot Location: {location}')
    elif unit.target!=-1:lines.append('')
    elif unit.targ_x!=-1 and unit.targ_y!=-1:
        prefix='Building at ' if unit.status&S.LOCK_BUILDING else 'Hex ' if unit.status&S.LOCK_HEX else ''
        lines.append(f'Target: {prefix}{unit.targ_x} {unit.targ_y}\n')
    if unit.prefs&1:lines.append('Weapon Safeties are %ch%crOFF%cn.\n')
    from systems.characters import actor_advantage
    if unit.pilot and actor_advantage(unit.pilot,'maneuvering_ace'):lines.append('Turn Mode: '+('TIGHT' if unit.prefs&256 else 'NORMAL'))
    charge=resolve_unit(unit,getattr(unit,'charge_target',-1))
    if charge and getattr(unit._engine,'newcharge',True):
        timer=getattr(unit,'charge_timer',0)//2
        lines.append(f'ChargeTarget: {identity(unit,charge)}\t  ChargeTimer: {timer}\n' if in_line_of_sight(unit,charge,charge.x,charge.y,fa_mech_range(unit,charge)) else f'ChargeTarget: NOT in line of sight!\t Timer: {timer}\n')
    return lines


def generic_lines(unit,template=False,caller=None):
    from physics.cargo import cargo_max_speed
    from physics.collision import jump_speed_mp
    from systems.hud import identity
    name=getattr(unit,'template_name',unit.name) if template else unit.name;ref=getattr(unit,'template_ref','') if template else getattr(unit,'mech_ref',getattr(unit,'template_ref',''))
    speed=int(cargo_max_speed(unit));pilot=unit.pilot;lines=[]
    if unit.unit_type==U.MW:
        actor=caller if caller is not None else getattr(unit,'command_actor',unit.pilot)
        if isinstance(actor,int):
            from systems.targeting import resolve_object
            actor=resolve_object(unit,actor)
        return [f'MechWarrior: {getattr(actor,"name",""):18.18s} ID:[{identity(unit,False)}]',f'MaxSpeed: {speed:3d}']
    if unit.unit_type in (U.MECH,U.BSUIT):
        label='Mech' if unit.unit_type==U.MECH else 'Point' if unit.specials&SP.CLAN_TECH else 'Squad'
        lines=[f'{label} Name: {name:18.18s}  ID:[{identity(unit,False)}]   {label} Reference: {ref}']
        lines.append(f'Tonnage:   {unit.tonnage:3d}     MaxSpeed: {speed:3d}       JumpRange: {jump_speed_mp(unit,unit.map)}' if unit.unit_type==U.MECH else f'MaxSpeed: {speed:3d}                  JumpRange: {jump_speed_mp(unit,unit.map)}')
    elif unit.move_type==M.NONE:lines=[f'Name: {name:15.15s}  ID:[{identity(unit,False)}]   Reference: {ref}']
    else:
        movement={M.TRACK:'Tracked',M.WHEEL:'Wheeled',M.HOVER:'Hover',M.VTOL:'VTOL',M.FLY:'Flight',M.HULL:'Displacement Hull',M.SUB:'Submarine',M.FOIL:'Hydrofoil'}.get(unit.move_type,'Magic')
        lines=[f'Vehicle Name: {name:15.15s}  ID:[{identity(unit,False)}]   Vehicle Reference: {ref}',f'Tonnage:   {unit.tonnage:3d}      {"Max thrust" if unit.unit_type in (U.AERO,U.DS,U.SPHEROID_DS) else "FlankSpeed"}: {speed:3d}       Movement Type: {movement}']
    if unit.unit_type==U.BSUIT:
        lines.append(f'{label} Leader Name: {pilot.name:16.16s} {label} Leader injury: {getattr(unit,"pilot_status",0)}' if pilot else 'Leader: NONE')
    elif unit.unit_type==U.MECH or unit.move_type!=M.NONE:
        lines.append(f'Pilot Name: {pilot.name:28.28s} Pilot Injury: {getattr(unit,"pilot_status",0)}' if pilot else 'Pilot: NONE')
    if unit.unit_type==U.BSUIT:lines.append(f'Max Suits: {getattr(unit,"max_suits",0)}')
    if unit.unit_type in (U.VEH_GROUND,U.VEH_NAVAL) and unit.sections[4].internal:
        from entities.vehicle import TankCritStatus
        if getattr(unit,'tank_crit_status',0)&TankCritStatus.TURRET_JAMMED:lines.append('     TURRET JAMMED')
        elif getattr(unit,'tank_crit_status',0)&TankCritStatus.TURRET_LOCKED:lines.append('     TURRET LOCKED')
    if unit.status&S.LANDED and unit.unit_type in (U.VTOL,U.AERO,U.DS,U.SPHEROID_DS):lines.append('LANDED')
    lines.extend(show_flags(unit))
    from systems.targeting import resolve_unit
    from systems.notifications import identity as visible_identity
    if unit.unit_type==U.MECH and not unit.is_jumping and not unit.is_fallen and unit.is_started:
        charge=resolve_unit(unit,getattr(unit,'charge_target',-1))
        if charge:lines.append('CHARGING --> '+visible_identity(unit,charge))
    if unit.is_jumping and unit.unit_type in (U.MECH,U.BSUIT):
        line=f'JUMPING --> {getattr(unit,"going_x",0):3d},{getattr(unit,"going_y",0):3d}'
        target=resolve_unit(unit,getattr(unit,'dfa_target',-1))
        if unit.status&S.DFA_ATTACK and target:line+='  Death From Above Target: '+visible_identity(unit,target)
        lines.append(line)
    bounded=('Mech Name:','Squad Name:','Point Name:','Vehicle Name:','Name:','Pilot Name:','Squad Leader','Point Leader','Max Suits:','CHARGING','JUMPING')
    return [line[:255] if line.startswith(bounded) or unit.unit_type not in (U.MECH,U.BSUIT) and line.startswith('Tonnage:') else line for line in lines]


def info_lines(unit):
    sinks=unit.real_num_sinks-unit.disabled_sinks;lines=[]
    if unit.unit_type==U.MECH:
        lines=[f'X, Y, Z:{unit.x:3d},{unit.y:3d},{unit.z:3d}  Excess Heat:  {int(unit.heat*10):3d} deg C.  Heat Production:  {int(unit.plus_heat*10):3d} deg C.',f'Speed:      %ch%cg{int(unit.speed):3d}%cn KPH  Heading:      %ch%cg{unit.facing:3d}%cn deg     Heat Sinks:       {sinks:3d}',f'Des. Speed: {int(unit.desired_speed):3d} KPH  Des. Heading: {unit.desired_facing:3d} deg     Heat Dissipation: {int(unit.minus_heat*10):3d} deg C.']
        if unit.lateral:lines.append('You are moving laterally '+lateral_description(unit))
    elif unit.unit_type in (U.MW,U.BSUIT):
        lines=[f'X, Y, Z:{unit.x:3d},{unit.y:3d},{unit.z:3d}  Speed:      %ch%cg{int(unit.speed):3d}%cn KPH  Heading:      %ch%cg{unit.facing:3d}%cn deg',f'                     Des. Speed: {int(unit.desired_speed):3d} KPH  Des. Heading: {unit.desired_facing:3d} deg']
    else:
        aero=unit.unit_type in (U.AERO,U.DS,U.SPHEROID_DS);flying=aero or unit.unit_type==U.VTOL;angle=getattr(unit,'desired_angle',0)
        lines=[f'X, Y, Z:{unit.x:3d},{unit.y:3d},{unit.z:3d}  Heat Sinks:          {sinks:3d}       '+(f'{"Climbing" if angle>=0 else "Diving"} angle: %ch%cg{abs(angle)}%cn' if aero else '')]
        if flying or unit.move_type==M.SUB:
            lines.append(f'Speed:      %ch%cg{int(unit.speed):3d}%cn KPH  Vertical Speed:      %ch%cg{int(unit.vertical_speed):3d}%cn KPH   Des. Speed {int(unit.desired_speed):3d} KPH')
            if unit.move_type==M.SUB:lines.append(f'Heading: {unit.facing:3d} KPH  Des. Heading: {unit.desired_facing:3d} deg')
            else:
                from physics.heights import aero_free_fuel
                percentage=100*max(0,unit.fuel)/unit.fuel_orig if unit.fuel_orig else float('inf') if unit.fuel>0 else float('nan')
                fuel='Unlimited' if aero_free_fuel(unit) else f'{max(0,unit.fuel)} ({percentage:.2f} %)'
                lines.append(f'Heading:    %ch%cg{unit.facing:3d}%cn deg  Des. Heading:        {unit.desired_facing:3d} deg   Fuel: '+fuel)
        elif unit.move_type!=M.NONE:
            lines.extend([f'Speed:      %ch%cg{int(unit.speed):3d}%cn KPH  Heading:      %ch%cg{unit.facing:3d}%cn deg',f'Des. Speed: {int(unit.desired_speed):3d} KPH  Des. Heading: {unit.desired_facing:3d} deg'])
        if aero:lines.append(f'Excess Heat:{int(unit.heat*10):3d} deg  Heat Production:     {int(unit.plus_heat*10):3d} deg   Heat Dissipation: {int(unit.minus_heat*10):3d} deg')
    turret=turret_facing(unit)
    if turret:lines.append(f"      Turret Facing: {turret['facing']} degrees"+(f" ({turret['offset']} offset from heading)" if turret['offset'] else ''))
    return lines


def status(unit,argument='',caller=None,historical=None):
    from systems.communications import common_checks,MECH_USUALSM
    caller=caller if caller is not None else getattr(unit,'command_actor',getattr(unit,'pilot',None))
    error=common_checks(unit,caller,MECH_USUALSM)
    if error is not None:return response(False,error)
    from systems.observation import unit_report
    from systems.movement_commands import historical_aircraft
    from core.effects import notify_actor
    historical=historical_aircraft(unit) if historical is None else historical
    components=selected_components(argument);lines=[]
    def emit(component):
        for line in component:
            lines.append(line);notify_actor(unit,caller,line)
    result=response(components=components,unit=unit_report(unit,unit,0),status=int(unit.status),
                    heat=unit.heat,fuel=unit.fuel,position=[unit.x,unit.y,unit.z],
                    speed=unit.speed,desired_speed=unit.desired_speed,facing=unit.facing)
    if 'short'in components:
        specific='';sinks=unit.real_num_sinks-unit.disabled_sinks
        if unit.unit_type==U.MECH:specific=f' HT: {int(unit.plus_heat*10):3d}/{int(sinks*10):3d}/{int(unit.minus_heat*10):<3d} '
        elif unit.unit_type==U.VTOL:specific=f' VSPD: {unit.vertical_speed:3.1f} '
        elif unit.unit_type in (U.AERO,U.DS,U.SPHEROID_DS):specific=f' VSPD: {unit.vertical_speed:3.1f}  ANG: {getattr(unit,"desired_angle",0):2d}  HT: {int(unit.plus_heat*10):3d}/{int(sinks*10):3d} '
        elif unit.unit_type in (U.VEH_GROUND,U.VEH_NAVAL) and unit.sections[4].internal_orig:specific=f' TUR: {acceptable_degree(unit.turret_facing+unit.facing):3d} '
        emit([f'LOC: {unit.x:3d},{unit.y:3d},{unit.z:3d}  HD: {unit.facing:3d}/{unit.desired_facing:3d}  SP: {unit.speed:3.1f}/{unit.desired_speed:3.1f} {specific} ST:{status_string(unit,2)}'[:99]])
        emit(target_lines(unit))
    elif 'compact-template'in components:
        from physics.cargo import MP1
        line=f'{getattr(unit,"template_ref","")} {getattr(unit,"template_name",unit.name)} {unit.tonnage} {int(unit.max_speed/MP1)*2//3}/{int(unit.max_speed/MP1)}/{int(unit.jump_speed/MP1)} {unit.real_num_sinks-unit.disabled_sinks} '
        if 'armor'in components:
            line+=''.join(f'{s.armor_orig}|{s.internal_orig}'+(f'|{s.rear_orig}' if s.rear_orig else '')+' ' for s in unit.sections if s.armor_orig)
        if 'heat' in components and unit.unit_type==U.MECH:
            scale=heat_bar(unit,caller)
            if scale is not None:
                result['heat_scale']=scale
                if historical:line=scale['text']  # Recovered buf and weirdbuf alias.
                emit([scale['text']])
        if 'weapons'in components:
            refresh(unit);ammunition=find_ammunition(unit,False)
            for i,run in enumerate(weapon_runs(unit)):
                line+=get_weapon_by_index(run.weapon_idx).name[3:]+'|'+section_names(unit)[run.section].replace(' ','_',1)
                if i<len(ammunition):
                    ammo=ammunition[i];weapon=get_weapon_by_index(ammo.weapon_idx);mode=ammo_letter(weapon,ammo.mode)
                    line+='|'+weapon.name[3:]+'|'+str(ammo.current)+('|' +mode if mode.strip() else '')
                line+=' '
        if 'weapons' in components:emit(weapon_display(unit,compact=True)['lines'])
        emit([line[:16383]])
    else:
        if components and components[0] in ('generic','template-generic'):emit(generic_lines(unit,components[0]=='template-generic',caller=caller))
        if 'armor'in components:
            result['armor']=armor_display(unit,True,caller=caller,historical=historical)
            emit(result['armor']['lines']);emit([' '])
        if 'info'in components:emit(info_lines(unit))
        if 'heat'in components and unit.unit_type==U.MECH:
            scale=heat_bar(unit,caller)
            if scale is not None:result['heat_scale']=scale;emit([scale['text']])
        if 'info'in components:
            emit(['  ']);emit(target_lines(unit))
        if 'info'in components:
            from systems.targeting import resolve_unit
            from systems.notifications import identity
            tow=resolve_unit(unit,unit.carrying) if unit.carrying>0 else None
            if tow:emit(['Towing '+identity(unit,tow)+'.'])
        if 'weapons'in components:
            equipment=weapon_display(unit);result.update({k:v for k,v in equipment.items() if k in ('weapons','ammunition','physical')});emit(equipment['lines'])
    result.update(lines=lines,message='\n'.join(lines),notified=True);return result


def own_readout(unit,kind,argument='',caller=None,historical=None):
    if kind=='status':return status(unit,argument,caller=caller,historical=historical)
    if kind=='critstatus':
        from systems.communications import common_checks,MECH_USUALSM
        caller=caller if caller is not None else getattr(unit,'command_actor',getattr(unit,'pilot',None))
        error=common_checks(unit,caller,MECH_USUALSM)
        if error is not None:return response(False,error)
        if unit.unit_type==U.MW:return response(False,'Huh?')
        from systems.combat_commands import parse_attributes
        args=parse_attributes(argument,1)
        if not args:return response(False,'You must specify a section to list the criticals for!')
        loc=armor_section_from_string(unit,args[0])
        if loc<0 or not unit.sections[loc].internal_orig:return response(False,'Invalid section!')
        return critical_display(unit,loc,historical=historical)
    indices=list(dict.fromkeys(r.weapon_idx for r in weapon_runs(unit)))
    if not indices:return response(False,'You have no weapons!')
    name=getattr(unit,'template_name',unit.name);ref=getattr(unit,'template_ref','');lines=['Weapons statistics for '+(name+': '+ref if name!=ref else ref)]
    extended=getattr(unit._engine,'btech_erange',False)
    lines.append('%cgWeapon Name             Heat  Damage  Range: Min Short Med Long Ext VRT' if extended else '%cgWeapon Name             Heat  Damage  Range: Min  Short  Med  Long  VRT')
    weapons=[]
    from dataclasses import asdict
    for index in indices:
        w=get_weapon_by_index(index);long=w.range_long*(20 if w.weapon_type==2 else 1)
        text=f'{w.name:24s} {w.heat:2d}     {w.damage:2d}           {w.range_min:2d}  {w.range_short:2d}    {w.range_medium:2d}  {long:3d}  {max(w.range_medium*2,long):3d} {w.vrt:2d}' if extended else f'{w.name:24s} {w.heat:2d}     {w.damage:2d}           {w.range_min:2d}    {w.range_short:2d}     {w.range_medium:2d}  {long:3d}   {w.vrt:2d}'
        weapons.append(dict(weapon_idx=index,name=w.name,spec=asdict(w)));lines.append(text)
    lines=menu_lines(lines[0],lines[2:],1,lines[1])
    return response(lines=lines,message='\n'.join(lines),weapons=weapons)


def lateral_description(unit):
    return {300:'Front/Left',60:'Front/Right',240:'Rear/Left',120:'Rear/Right',0:'None'}.get(unit.lateral,'Unknown')


def menu_lines(title,entries,columns=1,subtitle=None):
    """The source coolmenu string layout has 78 visible columns."""
    def field(value,width):
        pieces=re.findall(r'%c[A-Za-z]?|[^%]|%(?!c)',value);text='';visible=0
        for piece in pieces:
            if piece.startswith('%c'):text+=piece
            elif visible<width-1:text+=piece;visible+=1
        return text+' '*(width-visible)
    rule='%cb'+'-'*78+'%c';offset=max(0,39-len(title)//2)
    heading=' '*offset+'%ch%cb'+title[:max(0,77-offset)]+'%c'
    heading+=' '*max(0,78-len(plain(heading)))
    rows=[rule,heading]
    if subtitle is not None:rows.append(field(subtitle,78))
    rows.append(rule)
    for i in range(0,len(entries),columns):rows.append(''.join(field(text,78//columns) for text in entries[i:i+columns]))
    return rows+[rule]
