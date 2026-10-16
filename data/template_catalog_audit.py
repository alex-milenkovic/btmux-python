# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/src/btech/weapons.h
#   btech/template.c

"""Complete raw-catalog compatibility accounting through the production loader."""
from collections import Counter,defaultdict
from pathlib import Path
import re
from data.template_dependency import inventory,verify,sha
from data.template_directory import TemplateDirectory
from data.template_files import clear_mech,load_template,find_section,atof
from data import templates as t
from entities.mech import Mech


def declared(text,field):
    match=re.search(r'^\s*'+re.escape(field)+r'\s+\{\s*([^}\r\n]*?)\s*\}',text,re.M|re.I)
    return match[1] if match else None


def failure_detail(error,text):
    message=str(error)
    token=getattr(error,'template_command','')
    value=getattr(error,'template_value','')
    if message.startswith('Unable to find '):
        return {'classification':'unsupported-source-equipment','cause':message.removeprefix('Unable to find '),
                'authority':'weapons.h active weapon rows; template.c part-name lookup'}
    if 'bounds' in message:
        for match in re.finditer(r'CRIT_([+-]?\d+)(?:-([+-]?\d+))?',text):
            start=int(match[1]);end=int(match[2] or start)
            if not (1<=start<=12 and 1<=end<=12):
                return {'classification':'malformed-range','cause':match[0],
                        'authority':'accepted template critical slot bounds 1..12'}
    return {'classification':'malformed-input','cause':message+(f': {token} {value}' if token else ''),
            'authority':'template.c modern grammar and accepted loader validation'}


def state(unit):
    return {'reference':unit.template_ref,'name':unit.name,
            'class':t.MECH_TYPES[unit.unit_type] if 0<=unit.unit_type<len(t.MECH_TYPES) else None,
            'tonnage':unit.tonnage,'max_speed':unit.max_speed,'jump_speed':unit.jump_speed,
            'sinks':unit.real_num_sinks,'mounts':len(unit.weapons),
            'specials':int(unit.specials),'specials2':int(unit.specials2),
            'armor':[sec.armor for sec in unit.sections],
            'internals':[sec.internal for sec in unit.sections]}


def transformations(unit,text):
    notes=[]
    for field,attr in (('Jump_Speed','jump_speed'),('Heat_Sinks','real_num_sinks'),
                       ('Tac_Range','tac_range'),('Scan_Range','scan_range'),
                       ('LRS_Range','lrs_range'),('Radio_Range','radio_range')):
        value=declared(text,field);actual=getattr(unit,attr)
        from systems.damage_commands import atoi
        parsed=(atof(value) if field=='Jump_Speed' else atoi(value)) if value is not None else None
        if parsed!=actual:
            notes.append({'field':field,'declared':value,'final':actual,
                          'reason':'C2 shared jet cap' if field=='Jump_Speed' and unit.unit_type==0 else 'template.c finalization/defaults'})
    loc=None
    for line in text.replace('\r\n','\n').split('\n'):
        section=find_section(unit,line.strip())
        if section>=0:loc=section;continue
        if loc is None:continue
        internal=re.match(r'\s*Internals\s*\{\s*([+-]?\d+)',line,re.I)
        if internal and int(internal[1])!=unit.sections[loc].internal_orig:
            notes.append({'field':f'section{loc}.internals','declared':int(internal[1]),
                          'final':unit.sections[loc].internal_orig,'reason':'mech_int_check source internal table'})
        crit=re.match(r'\s*CRIT_([+-]?\d+)(?:-([+-]?\d+))?\s*\{\s*(\S+)\s+(\S+)\s+(\S+)(?:\s+(\S+))?',line)
        if crit:
            slot=unit.sections[loc].criticals[int(crit[1])-1]
            if crit[3].lower().startswith('ammo_') and crit[4].lstrip('+-').isdigit() and int(crit[4])!=slot.data:
                notes.append({'field':f'section{loc}.crit{crit[1]}.ammo','declared':int(crit[4]),
                              'final':slot.data,'reason':'template.c full_ammo / halfton normalization'})
            if slot.brand and (not crit[6] or not crit[6].lstrip('+-').isdigit() or int(crit[6])==0):
                notes.append({'field':f'section{loc}.crit{crit[1]}.brand','declared':crit[6],
                              'final':slot.brand,'reason':'template.c catalog brand or default3/5'})
    return notes


def audit(root,*,reverse=False):
    root=Path(root).resolve();paths,exclusions=inventory(root)
    verification=verify(root)
    directory=TemplateDirectory(root);directory.scan()
    visible={str(Path(row['directory'])/row['reference']) for row in directory.listing()}
    winners={};lookup_errors={}
    for relative in paths:
        name=Path(relative).name
        if name in winners:continue
        try:
            found=directory.lookup(name)
            winners[name]=found.relative_to(root).as_posix() if found else None
        except (ValueError,OSError) as error:
            winners[name]=None;lookup_errors[name]=str(error).replace(str(root),'<catalog>')
    groups=defaultdict(list)
    for path in paths:groups[Path(path).name[:24].lower()].append(path)
    collisions=[{'lookup_key':key,'members':members} for key,members in sorted(groups.items()) if len(members)>1]
    rows=[];types=Counter();manifest=[]
    for relative in reversed(paths) if reverse else paths:
        row={'path':relative,'lookup_key':Path(relative).name[:24].lower(),'origin':'upstream',
             'discoverable':relative in visible or winners[Path(relative).name]==relative,
             'lookup_error':lookup_errors.get(Path(relative).name),
             'reference_winner':winners[Path(relative).name],
             'selected_by_reference':winners[Path(relative).name]==relative,
             'declared_reference':None,'declared_type':None,
             'raw_sha256':None,'diagnostics':[],'transformations':[]}
        unit=Mech();unit._id=0;clear_mech(unit,True);text=''
        try:
            raw=(root/relative).read_bytes();row['raw_sha256']=sha(raw)
            manifest.append(relative+'\t'+sha(raw)+'\n')
            text=raw.decode('ascii');row['declared_reference']=declared(text,'Reference');row['declared_type']=declared(text,'Type')
            load_template(unit,root/relative,catalog=directory.catalog)
            row['outcome']='loaded';row['transformations']=transformations(unit,text)
        except (ValueError,OSError,UnicodeError,IndexError,OverflowError) as error:
            row['outcome']='failed';row['error']=str(error).replace(str(root),'<catalog>')
            row['failed_command']=getattr(error,'template_command',None)
            row['failed_value']=getattr(error,'template_value',None)
            detail=failure_detail(error,text);detail['cause']=detail['cause'].replace(str(root),'<catalog>')
            row.update(detail)
        types[row['declared_type'] if row['declared_type'] and row['declared_type'].lower() in {name.lower() for name in t.MECH_TYPES} else 'unknown']+=1
        row['state']=state(unit);row['final_class']=row['state']['class'] if row['outcome']=='loaded' else None
        row['diagnostics']=list(getattr(unit,'construction_messages',[]))
        rows.append(row)
    rows.sort(key=lambda row:row['path']);success=sum(row['outcome']=='loaded' for row in rows)
    return {'outcome':'complete-with-failures' if success<len(paths) else 'complete-success',
            'verified':verification['outcome'].startswith('verified'),'verification':verification,
            'candidates':len(paths),'successes':success,'failures':len(paths)-success,
            'by_declared_type':dict(sorted(types.items())),'ambiguities':collisions,
            'ambiguity_members':sum(len(group['members']) for group in collisions),'exclusions':exclusions,
            'manifest_sha256':sha(''.join(sorted(manifest)).encode()),
            'manifest_complete':all(row['raw_sha256'] is not None for row in rows),'files':rows,
            'discovery_policy':'discoverable means cache membership or successful basename fallback; reference_winner is the production lookup result',
            'normalization_authority':['template.c load order, internal_check, full_ammo, default brands/electronics, update_specials',
                                       'authorized C1 CRLF and C2 standard jump cap; no catalog compatibility aliases']}
