# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.partnames.c

"""Construction files and live editor CLI. See docs/construction-templates-cli.md."""
import argparse
from copy import deepcopy
import json
import sys
from pathlib import Path
from tools.maps_environment import MapsSession
from tools.core_simulation import serialized,actor_from
from tools.combat_resolution import unique_fields,reject_constant
from tools.movement_inputs import fields,number,string,boolean,array
from data.template_directory import TemplateDirectory
from data.template_files import clear_mech,load_template,find_section,mode_masks,finish_load
from data.construction_catalog import source_id,source_part,runtime_part,weapon_id,legacy_ammo_id
from data import templates as t
from systems.construction_editor import Editor,delinftech,show_tech
from systems.construction_weight import weight,get_weight,internal_check,engine_weight,crit_weight,suspension,ammo_weight,ammo_mod


EXTRA_INTS=('computer','radio','radio_type','si','si_orig','fuel_orig','mech_bv','cargo_space','max_suits','car_max_ton',
            'original_sinks','hs_engine_override','rtons','xp_mod','units_killed')
EXTRA_TEXT=('unit_era','unit_tro','template_ref','name')


def text(value):
    if not isinstance(value,str):raise ValueError('Expected text')
    return value


class ConstructionSession(MapsSession):
    def __init__(self,document):
        document=deepcopy(document)
        options=fields(document.pop('construction',{}),('root','files','parts','clan','dynspeed','create_root','catalog'))
        from data.template_dependency import resolve_catalog,require_verified
        from data.template_catalog import CatalogDirectory
        upstream=resolve_catalog(options.get('catalog'))
        if upstream is not None:
            require_verified(upstream)
            map_root=Path(document.get('file_root','./tmp/maps_environment_files')).resolve()
            protected=upstream.resolve()
            if map_root.is_relative_to(protected) or protected.is_relative_to(map_root):
                raise ValueError('Map storage and upstream template roots overlap')
        factory=(lambda root,**kw:CatalogDirectory(root,upstream,**kw)) if upstream is not None else TemplateDirectory
        self.directory=factory(string(options.get('root','./tmp/construction_templates_files')),
            parts=boolean(options.get('parts',True)),clan=boolean(options.get('clan',True)),dynspeed=boolean(options.get('dynspeed',True)))
        if boolean(options.get('create_root',True)):
            self.directory.root.mkdir(parents=True,exist_ok=True)
        self.template_files=set()
        if not isinstance(options.get('files',{}),dict):raise ValueError('Template files must be an object')
        for name,text in options.get('files',{}).items():
            path=self.directory.path(string(name));path.parent.mkdir(parents=True,exist_ok=True)
            if not isinstance(text,str):raise ValueError('Template file content must be text')
            path.write_text(text,encoding='ascii')
            self.template_files.add(name)
        editors=array(document.pop('editors',[{'name':'e','id':1}]))
        super().__init__(document)
        self.engine.parts=self.directory.catalog.parts
        for unit in self.units.values():unit.construction_dynspeed=self.directory.dynspeed
        self.editors={}
        for entry in editors:
            fields(entry,('name','id','allocated','target'),('name','id'))
            name=string(entry['name'])
            if name in self.editors:raise ValueError('Duplicate editor name')
            editor=Editor(number(entry['id'],integer=True),self.units,directory=self.directory,allocated=boolean(entry.get('allocated',True)))
            if 'target' in entry:editor.target=entry['target']
            self.editors[name]=editor

    def path(self,name):
        # The inherited map-file interface is also a writable session path.
        path=super().path(name)
        if hasattr(self.directory,'upstream') and path.resolve().is_relative_to(self.directory.upstream.root):
            raise ValueError('Upstream catalog is read-only')
        return path

    def add_unit(self,record):
        record=deepcopy(record);extras=record.pop('construction',{})
        unit=super().add_unit(record)
        self.configure_construction(unit,extras)
        return unit

    def configure_construction(self,unit,values):
        fields(values,EXTRA_INTS+EXTRA_TEXT+('zeroed','freq','freqmodes','chantitle'))
        if boolean(values.get('zeroed',False)):clear_mech(unit,True)
        for key,value in values.items():
            if key=='zeroed':continue
            if key in EXTRA_INTS:value=number(value,integer=True)
            elif key in EXTRA_TEXT:value=text(value)
            elif key=='chantitle':value=[string(item) for item in array(value,16)]
            else:value=[number(item,integer=True) for item in array(value,16)]
            setattr(unit,key,value)

    def unit(self,action):
        unit=self.units.get(action.get('unit','u'))
        if unit is None:raise ValueError('Unknown construction unit')
        return unit

    def action(self,action):
        if not isinstance(action,dict):raise ValueError('action must be an object')
        op=action.get('op')
        if op not in ('editor','template','catalog','construction_readout','construction_value','construction_diagnose','construction_validate','construction_pilot','delinftech'):
            return super().action(action)
        try:return serialized(self.invoke(self.construction_action,action))
        except (ValueError,TypeError,KeyError,IndexError,OSError,OverflowError) as error:return {'ok':False,'error':str(error)}

    def construction_action(self,action):
        op=action['op']
        if op=='editor':
            fields(action,('op','editor','name','args','privilege','caller','caller_id','clock'),('op','name'))
            editor=self.editors.get(action.get('editor','e'))
            if editor is None:raise ValueError('Unknown editor')
            options={k:action[k] for k in ('caller','caller_id','clock') if k in action}
            result=editor.execute(string(action['name']),text(action.get('args','')),privilege=boolean(action.get('privilege',True)),**options)
            if action['name'] in ('savetemp','savetemp2') and result['ok'] and result.get('result'):
                self.template_files.add(str(self.directory.path(result['result']).relative_to(self.directory.root)))
            return result
        if op=='template':
            fields(action,('op','unit','kind','reference','text','legacy','caller','caller_id','clock','origin'),('op','kind'))
            kind=action['kind'];reference=text(action.get('reference',''))
            catalog_mode=hasattr(self.directory,'upstream')
            origin=action.get('origin')
            if origin is not None and (not catalog_mode or origin not in ('custom','upstream')):raise ValueError('Invalid template origin')
            selection={'origin':origin} if catalog_mode else {}
            if kind=='list':return {'entries':self.directory.listing()}
            if kind=='reset':self.directory.reset();return {'ok':True}
            if kind=='lookup':
                path=self.directory.lookup(reference,**selection)
                if catalog_mode:return {'path':self.directory.selected['path'] if path else None,'selected':self.directory.selected,'ambiguities':self.directory.ambiguities}
                return {'path':str(path.relative_to(self.directory.root)) if path else None,'ambiguities':self.directory.ambiguities}
            if kind in ('write','read','delete'):
                if not reference:raise ValueError('File reference required')
                if catalog_mode and kind=='read':
                    path=self.directory.lookup(reference,**selection)
                    if path is None:raise ValueError('No matching template file')
                    return {'text':path.read_text(encoding='ascii'),'selected':self.directory.selected}
                path=self.directory.mutation_path(reference,origin) if catalog_mode else self.directory.path(reference)
                self.template_files.add(reference)
                if kind=='write':path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text(action.get('text','')),encoding='ascii')
                elif kind=='delete':path.unlink()
                else:return {'text':path.read_text(encoding='ascii')}
                return {'ok':True}
            unit=self.unit(action)
            if kind=='load':
                ok=self.directory.loadnew(unit,reference,wrapper=True,**selection)
                return {'ok':ok,**({'origin':getattr(unit,'template_origin',None),'source':getattr(unit,'template_source',None)} if catalog_mode else {})}
            if kind=='restore':return {'ok':self.directory.restore(unit)}
            if kind=='save':
                if catalog_mode:self.directory.mutation_path(reference,origin)
                path=self.directory.save(unit,reference,legacy=boolean(action.get('legacy',False)),**{k:action[k] for k in ('caller','caller_id','clock') if k in action})
                name=str(path.relative_to(self.directory.root));self.template_files.add(name);return {'ok':True,'file':name}
            raise ValueError('Unknown template operation')
        if op=='catalog':return self.catalog_action(action)
        if op=='construction_readout':
            fields(action,('op','unit'),('op',));return self.readout(self.unit(action))
        if op=='construction_value':
            fields(action,('op','unit','values'),('op','values'));self.configure_construction(self.unit(action),action['values']);return None
        if op=='construction_validate':
            fields(action,('op','unit','correct','interactive'),('op',));unit=self.unit(action)
            if boolean(action.get('correct',True)):internal_check(unit,True)
            return weight(unit,number(action.get('interactive',0),integer=True))
        if op=='construction_pilot':
            fields(action,('op','unit','actor'),('op',));unit=self.unit(action)
            unit.pilot=actor_from(action.get('actor',{}),unit);unit.command_actor=unit.pilot;return {'ok':True}
        if op=='delinftech':
            fields(action,('op','unit'),('op',));return {'ok':True,'messages':[delinftech(self.unit(action))]}
        if op=='construction_diagnose':
            fields(action,('op','unit','kind','args'),('op','kind'));unit=self.unit(action);args=array(action.get('args',[]));kind=action['kind']
            operations={'engine_weight':engine_weight,'crit_weight':crit_weight,'weight':weight,'ammo_weight':ammo_weight,
              'finish_load':finish_load,'find_section':find_section,'showtech':show_tech,'clear':clear_mech}
            if kind=='ammo_mod':
                loc,pos=array(args,2)
                return ammo_mod(unit.sections[number(loc,0,7,True)].criticals[number(pos,0,11,True)])
            if kind in operations:return operations[kind](unit,*args)
            if kind=='load_modern':self.directory.load_modern(unit,*args);return {'ok':True}
            if kind=='load_legacy':self.directory.load_legacy(unit,*args);return {'ok':True}
            if kind=='mode_masks':return mode_masks(*args)
            if kind=='parse_bits':
                parser,table,value=args
                tables={'fire':t.CRIT_FIRE_MODES,'ammo':t.CRIT_AMMO_MODES}
                names=tables[table] if isinstance(table,str) else [text(v) for v in array(table)]
                return {'strict':t.parse_bit_vector,'lenient':t.parse_bit_vector_lenient,
                        'delimited':t.parse_bit_vector_delim}[parser](names,text(value))
            if kind=='read_desc':
                from io import StringIO
                return t.read_brace_block(StringIO(text(args[1]) if len(args)>1 else ''),text(args[0]))
            if kind=='computer_conversion':t.computer_conversion(unit);return self.readout(unit)
            if kind=='section_index':
                from systems.damage_commands import armor_section_from_string
                return armor_section_from_string(unit,text(args[0]))
            if kind=='short_section':
                from systems.damage_commands import short_section
                return short_section(unit,number(args[0],0,7,True))
            if kind=='load_fields':
                from data.template_files import load_stream
                path=self.directory.lookup(text(args[0]))
                if path is None:raise ValueError('No matching template file')
                self.directory._attributes_for(unit)
                with path.open(encoding='ascii',newline='') as stream:
                    load_stream(unit,stream,path,catalog=self.directory.catalog,finalize=False)
                return {'ok':True}
            if kind=='load_reference':
                loaded=self.directory.load_reference(text(args[0]))
                return None if loaded is None else self.template_snapshot(loaded)
            if kind=='weight_cache':
                calls=0
                if len(args)>1:raise ValueError('Expected zero or one computed fixture value')
                fixture=number(args[0],integer=True) if args else None
                def compute():
                    nonlocal calls
                    calls+=1
                    return weight(unit,-1)['total'] if fixture is None else fixture
                value=get_weight(unit,dynspeed=self.directory.dynspeed,compute=compute)
                return {'value':value,'calls':calls,'fixture':fixture is not None}
            if kind=='suspension':return suspension(unit)
            if kind=='get_weight':return get_weight(unit,dynspeed=self.directory.dynspeed)
            raise ValueError('Unknown construction diagnostic')

    def catalog_action(self,action):
        fields(action,('op','kind','form','text','cursor','part','brand','wizard'),('op','kind'))
        catalog=self.directory.catalog;kind=action['kind'];text=action.get('text','')
        if not isinstance(text,str):raise ValueError('Catalog text must be text')
        if kind=='names':
            part=number(action.get('part',source_part(text)),integer=True);brand=number(action.get('brand',0),integer=True)
            before=len(catalog.messages)
            names=catalog.names(part,brand)
            return dict(source_part_id=part,runtime_part_id=runtime_part(part) if names[0] else None,short=names[0],long=names[1],vlong=names[2],messages=catalog.messages[before:])
        if kind=='match':return catalog.match_result(string(action.get('form','vlong')),text,number(action.get('cursor',-1),integer=True))
        if kind=='partmatch':return catalog.partmatch(text,boolean(action.get('wizard',True)))
        if kind=='partname':return catalog.partname(text,string(action.get('form','vlong')),boolean(action.get('wizard',True)))
        if kind=='list':
            form=string(action.get('form','short'))
            if form not in catalog.sorted:raise ValueError('Invalid name form')
            return catalog.list_forms(form)
        if kind=='weapons':return catalog.weapon_dump()
        if kind=='specials':return catalog.special_dump()
        if kind=='identify':
            from data.construction_catalog import identify
            return identify(text)
        if kind=='weapon_index':return catalog.weapon_index(text)
        if kind=='special_index':return catalog.special_index(text)
        if kind in ('weapon_id','legacy_ammo_id'):
            return (legacy_ammo_id if kind=='legacy_ammo_id' else weapon_id)(text)
        raise ValueError('Unknown catalog operation')

    def readout(self,unit):
        from systems.parts import payloadlist,partlist
        result={key:getattr(unit,key,0) for key in EXTRA_INTS}
        result.update({key:getattr(unit,key,'') for key in EXTRA_TEXT})
        if hasattr(unit,'template_origin'):
            result['template_origin']=unit.template_origin;result['template_source']=unit.template_source
        result['channels']={key:list(getattr(unit,key,[])) for key in ('freq','freqmodes','chantitle')}
        result['infantry_specials']=int(unit.infantry_specials)
        result.update(type=int(unit.unit_type),move=int(unit.move_type),tonnage=unit.tonnage,real_num_sinks=unit.real_num_sinks,
          current_weight=get_weight(unit,dynspeed=self.directory.dynspeed),design_weight=weight(unit,0),
          max_speed=unit.max_speed,jump_speed=unit.jump_speed,tac_range=unit.tac_range,lrs_range=unit.lrs_range,
          scan_range=unit.scan_range,radio_range=unit.radio_range,tech=show_tech(unit),payload=payloadlist(unit),partlist=partlist(unit),
          slots=[[dict(slot=pos+1,runtime_part_id=slot.type,source_part_id=source_id(slot.type),invalid_source_part_id=getattr(slot,'invalid_source_type',None) if not slot.type else None,data=slot.data,fire=int(slot.firemode),ammo=int(slot.ammomode),brand=slot.brand,
                       desired_ammo_location=slot.desired_ammo_loc) for pos,slot in enumerate(sec.criticals)] for sec in unit.sections])
        return result

    def _snapshot(self):
        result=super()._snapshot()
        result['construction']={'editors':{name:dict(id=e.identity,target=e.target,allocated=e.allocated) for name,e in self.editors.items()},
            'files':{name:self.directory.path(name).read_text(encoding='ascii') for name in sorted(self.template_files) if self.directory.path(name).is_file()},
            'cache':self.directory.entries,'ambiguities':self.directory.ambiguities}
        for name,unit in self.units.items():
            result['units'][name]['construction']={key:getattr(unit,key,0 if key in EXTRA_INTS else '') for key in EXTRA_INTS+EXTRA_TEXT}
            result['units'][name]['construction']['messages']=list(getattr(unit,'construction_messages',[]))
            result['units'][name]['construction']['external_effects']=list(getattr(unit,'construction_external_effects',[]))
        return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input');args=parser.parse_args(argv)
    try:
        with open(args.input) if args.input else sys.stdin as source:document=json.load(source,object_pairs_hook=unique_fields,parse_constant=reject_constant)
        session=ConstructionSession(document);results=[session.action(action) for action in document['actions']]
        print(json.dumps(dict(results=results,state=session.snapshot(),draws=session.draws),allow_nan=False))
    except (ValueError,TypeError,KeyError,IndexError,OSError,OverflowError) as error:
        print(json.dumps({'ok':False,'error':str(error)}),file=sys.stderr);return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
