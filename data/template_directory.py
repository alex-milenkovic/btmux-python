# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mechrep.c
# Historical Aerospace sources:
#   btech/template.c

"""Local template discovery, legacy files, live replacement and intact baselines."""
import os
import re
from pathlib import Path
import stat
from core.attributes import AttributeStore,attributes_for
from data.template_files import (clear_mech,load_template,save_template,isolated_template,
                                 diagnostic,atof,_ams,TemplateError,report_template_error)
from data.construction_catalog import Catalog,runtime_part,source_id,valid_source_part
from data import templates as t
from entities.mech import Mech
from systems.weapon_inventory import sync_weapon_states
from systems.construction_weight import invalidate,weight

OLD_SUBDIRS=('3025','3050','3055','3058','3060','2750','Aero','MISC','Clan','ClanVehicles',
             'Clan2nd','ClanAero','Custom','Solaris','Vehicles','MFNA','Infantry')


class TemplateDirectory:
    def __init__(self,root,*,parts=True,clan=True,dynspeed=True,attributes=None):
        self.root=Path(root).resolve();self.catalog=Catalog(parts,clan);self.dynspeed=dynspeed
        self.entries=None;self.ambiguities=[];self.reference_key='';self.reference_unit=None
        self.attributes=attributes or AttributeStore(self.root/'.state'/'attributes.json',root=self.root)

    def _attributes_for(self,unit):
        return attributes_for(unit,self.attributes)

    def reset(self):
        self.entries=None;self.ambiguities=[]

    def path(self,name):
        path=(self.root/name).resolve()
        if not path.is_relative_to(self.root):raise ValueError('Template path leaves designated root')
        return path

    def scan(self):
        try:root_entries=sorted(self.root.iterdir(),key=lambda p:p.name)
        except OSError:return False
        entries=[];directories=[]
        def scan_entries(paths,parent):
            for p in paths:
                if len(os.fsencode(str(p.parent)))+1+len(os.fsencode(p.name))+1>1000:continue
                try:mode=p.stat().st_mode
                except OSError:continue
                if not parent and stat.S_ISDIR(mode) and not p.name.startswith('.') and len(os.fsencode(p.name))<=34:
                    directories.append(p)
                elif stat.S_ISREG(mode):entries.append((p.name[:34],parent))
        scan_entries(root_entries,'')
        for p in directories:
            try:scan_entries(sorted(p.iterdir(),key=lambda q:q.name),p.name)
            except OSError:pass
        # C specifies equivalence over 24 bytes, but no collision winner.
        # Stable root-before-subdirectory, bytewise name enumeration is local policy.
        self.entries=sorted(entries,key=lambda e:e[0][:24].lower())
        return True

    def _readable(self,path):
        try:
            with path.open('rb'):return True
        except OSError:return False

    def old_lookup(self,name):
        for prefix in ('',*OLD_SUBDIRS):
            path=self.path(str(Path(prefix)/name))
            if self._readable(path):return path
        return None

    def lookup(self,name):
        if '/' in name:return self.old_lookup(name)
        for retry in range(2):
            if self.entries is None and not self.scan():return self.old_lookup(name)
            matches=[e for e in self.entries if e[0][:24].lower()==name[:24].lower()]
            if not matches:return None
            self.ambiguities=[str(Path(parent)/filename) for filename,parent in matches] if len(matches)>1 else []
            filename,parent=matches[0];path=self.path(str(Path(parent)/filename))
            if self._readable(path):return path
            if not retry:self.reset()
        return self.old_lookup(name)

    def listing(self):
        if self.entries is None:self.scan()
        return [{'reference':name,'directory':parent} for name,parent in (self.entries or [])]

    def load_modern(self,unit,reference,*,notify=None):
        path=self.lookup(reference)
        if path is None:raise FileNotFoundError(reference)
        self._attributes_for(unit)
        return load_template(unit,path,catalog=self.catalog,notify=notify)

    def load_legacy(self,unit,reference):
        path=self.lookup(reference)
        try:
            if path is None:raise TemplateError(f"No matching file for '{reference}'.")
            try:stream=path.open(encoding='ascii')
            except OSError as error:raise TemplateError(f'Unable to open file {path} ({reference})!') from error
            with stream:return load_legacy_stream(unit,stream,reference)
        except ValueError as error:
            report_template_error(unit,error);raise

    def loadnew(self,unit,reference,*,wrapper=False,canonical_reference=None,notify=None):
        old=getattr(unit,'template_ref',unit.mech_type)
        clear_mech(unit,old!=(reference if canonical_reference is None else canonical_reference))
        self._attributes_for(unit)
        unit.construction_dynspeed=self.dynspeed
        try:
            try:self.load_modern(unit,reference,notify=notify)
            except (ValueError,OSError) as modern_error:
                self.load_legacy(unit,reference)
        except (ValueError,OSError) as error:
            report_template_error(unit,error,notify);return False
        finally:
            sync_weapon_states(unit)
        unit.construction_managed=True
        unit.construction_dynspeed=self.dynspeed
        unit.template_directory=self
        if not self.dynspeed:
            unit.rtons=unit.tonnage*1024
        unit._catalog_baseline=isolated_template(unit)
        engine=unit._engine
        if engine is not None:
            if not hasattr(engine,'templates'):engine.templates={}
            engine.templates[unit.template_ref]=isolated_template(unit)
            if wrapper:
                engine.events.cancel_by_data(unit)
                from systems.ammo_dump import sync_dump_state
                sync_dump_state(unit);unit.unjamming=False
                for field in ('_startup_event','_mode_event'):
                    if hasattr(unit,field):setattr(unit,field,None)
                from systems.map_membership import clear_los
                clear_los(unit)
        return True

    def restore(self,unit,*,notify=None):
        reference=self._attributes_for(unit).get(unit._id,'A_MECHREF')
        if not reference:raise ValueError("Sorry, I don't know what type of mech this is")
        return self.loadnew(unit,reference,notify=notify)

    def load_reference(self,reference):
        if self.reference_key==reference and self.reference_unit is not None:return isolated_template(self.reference_unit)
        unit=Mech()
        if not self.loadnew(unit,reference):self.reference_key='';return None
        self.reference_key=reference;self.reference_unit=isolated_template(unit)
        return isolated_template(self.reference_unit)

    def save(self,unit,arguments,*,legacy=False,notify=None,**options):
        self.reset()  # Source invalidates before argument validation.
        args=t.parse_attributes(arguments,1)
        if not args:raise ValueError('You must specify a template name!')
        reference=args[0]
        if '/' in reference:raise ValueError('Invalid file name!')
        emit=notify or (lambda message:diagnostic(unit,message))
        emit(f'Saving {reference}'+('...' if legacy else ''))
        try:
            path=self.path(reference)
            if legacy:save_legacy(unit,path)
            else:
                if weight(unit,-1)['total']>unit.tonnage*1024:emit('Warning: Template Overweight, see @weight.')
                save_template(unit,reference,path,catalog=self.catalog,**options)
        except OSError as error:
            raise ValueError('Unable to open/create mech file! Sorry.' if legacy else 'Error saving the template file!') from error
        return path


class _LegacyNumbers:
    def __init__(self,text):self.text=text;self.pos=0
    def number(self,floating=False):
        pattern=r'\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)' if floating else r'\s*([+-]?\d+)'
        match=re.match(pattern,self.text[self.pos:])
        if not match:raise ValueError('Insufficient numeric legacy template data')
        self.pos+=match.end()
        return atof(match[1]) if floating else int(match[1])


def load_legacy_stream(unit,stream,reference):
    numbers=_LegacyNumbers(stream.read());unit.template_ref=unit.mech_type=reference[:24]
    message=f'Old template loading system: {reference} is invalid template file.'
    try:
        values=[numbers.number() for _ in range(5)]
        unit.max_speed=numbers.number(True);unit.jump_speed=numbers.number(True)
        special=numbers.number()
        unit.tonnage,unit.tac_range,unit.lrs_range,unit.scan_range=values[:4];unit.real_num_sinks=values[4]
        unit.specials=special&~(32768|16384|8192|4196)
        # Keep source dissipation when adopting the header's technology flags.
        unit.real_num_sinks=values[4]
        for k in range(8):
            loc={3:4,4:5,5:3}.get(k,k) if unit.unit_type==4 else k
            message=f'Insufficient data reading section {loc}!'
            armor,internal,rear,config=[numbers.number() for _ in range(4)]
            sec=unit.sections[loc];sec.recycle=0;sec.armor=sec.armor_orig=armor
            sec.internal=sec.internal_orig=internal;sec.rear=sec.rear_orig=rear;sec.config=config&~4
            for pos,slot in enumerate(sec.criticals):
                message=f'Insufficient data reading critical {loc}/{pos}!'
                part,data,fire=[numbers.number() for _ in range(3)]
                raw=part&65535
                if not valid_source_part(raw):
                    # Preserve C's pre-validation write without aliasing a
                    # source weapon number to an unrelated live weapon.
                    slot.type=0;slot.invalid_source_type=raw
                    raise TemplateError(f'Invalid datatype at {loc}/{pos}!')
                slot.type=runtime_part(raw);slot.__dict__.pop('invalid_source_type',None)
                _ams(unit,slot);slot.data=data&255;slot.firemode=fire&0xffffffff
        try:kind=numbers.number();move=numbers.number()
        except ValueError:pass
        else:
            unit.unit_type=kind
            if not 0<=kind<len(t.MECH_TYPES):raise TemplateError("Invalid 'mech type!")
            unit.move_type=move
            if not 0<=move<len(t.MOVE_TYPES):raise TemplateError('Invalid movenement type!')
        try:unit.radio_range=numbers.number()
        except ValueError:unit.radio_range=80
    except ValueError as error:
        failure=error if isinstance(error,TemplateError) else TemplateError(message)
        report_template_error(unit,failure)
        if failure is error:raise
        raise failure from error
    finally:
        sync_weapon_states(unit);invalidate(unit);unit.construction_managed=True
    return unit


def save_legacy(unit,filename):
    with open(filename,'w',encoding='ascii') as stream:
        stream.write(f'{unit.tonnage} {unit.tac_range} {unit.lrs_range} {unit.scan_range} {unit.real_num_sinks} {unit.max_speed:.2f} {unit.jump_speed:.2f} {int(unit.specials)}\n')
        for sec in unit.sections:
            stream.write(f'{sec.armor} {sec.internal} {sec.rear} {int(sec.config)}\n')
            for slot in sec.criticals:
                part=getattr(slot,'invalid_source_type',0) if not slot.type else source_id(slot.type)
                stream.write(f'{part} {slot.data} {int(slot.firemode)}\n')
        stream.write(f'{int(unit.unit_type)} {int(unit.move_type)}\n{unit.radio_range}\n')
