# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.status.c

"""HUD connections and pilot displays; see docs/hud-status-cli.md."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from tools.repair_economy import RepairEconomySession
from tools.core_simulation import serialized
from tools.combat_resolution import unique_fields,reject_constant
from tools.movement_inputs import fields,number,boolean,array,string
from tools.construction_templates import text as text_value
from systems.hud import HudSession,player_unit
from systems.armor_display import plain,DisplayDependencyError

DISPLAY_TEXT=('mapcolor','tacsize','lrsheight','status_template','template_name','contact_options','markings','heatchars')
DISPLAY_BOOLS=('ansimap','hardcode','zombie','is_observator','pkiller')
DISPLAY_INTS=('brief','display_si','display_si_orig','aim','aim_type','turn_mode','masc_counter','scharge_counter')


class DisplaySession(RepairEconomySession):
    def __init__(self,document):
        document=deepcopy(document);options=fields(document.pop('hud_display',{}),('root','hudinfo_show_mapinfo','mw_losmap','btech_erange','map_in_character'))
        sessions=array(document.pop('sessions',[]));self.display_inputs={}
        root=Path(string(options.get('root','./tmp/hud_status')))
        for key,child in [('pilots','characters'),('repair_economy','economy'),('construction','templates')]:document.setdefault(key,{}).setdefault('root',str(root/child))
        document.setdefault('file_root',str(root/'maps'))
        super().__init__(document)
        for key,value in options.items():
            if key=='map_in_character':self.map.in_character=boolean(value)
            elif key!='root':setattr(self.engine,key,number(value,0,2,True) if key=='hudinfo_show_mapinfo' else boolean(value))
        for name,values in self.display_inputs.items():self.configure_display(self.units[name],values)
        # Actors supplied by the core schema participate in the same local registry.
        for unit in self.units.values():
            actor=unit.command_actor
            if actor is not None and actor._id not in self.personnel.objects:self.personnel.add(actor,getattr(actor,'location',unit._id))
        from core.object_services import ObjectRegistry
        from systems.targeting import resolve_object
        self.engine.object_registry=ObjectRegistry(root/'objects.json',
            resolve=lambda ident:self.personnel.objects.get(ident) or next((obj for obj in self.engine.get_entities() if getattr(obj,'_id',None)==ident),None))
        for obj in self.personnel.objects.values():self.engine.object_registry.register(obj)
        self.sessions={}
        for record in sessions:
            fields(record,('name','unit','player'),('name',))
            name=string(record['name'])
            if name in self.sessions:raise ValueError('Duplicate HUD session')
            if 'unit'in record and 'player'in record:raise ValueError('Specify unit or player for session')
            ident=self.units[record['unit']]._id if 'unit'in record else number(record.get('player',-1),integer=True)
            self.sessions[name]=HudSession(lambda ident=ident:player_unit(self.personnel,ident))

    def add_unit(self,record):
        record=deepcopy(record);display=record.pop('display',{})
        unit=super().add_unit(record);self.display_inputs[record['name']]=display
        return unit

    def configure_display(self,unit,values):
        for key,value in fields(values,DISPLAY_TEXT+DISPLAY_BOOLS+DISPLAY_INTS+('status_expression','display_los_cells')).items():
            if key=='display_los_cells':
                value=[{k:number(v,0,15 if k=='flags' else 199,True) for k,v in fields(cell,('x','y','flags'),('x','y','flags')).items()} for cell in array(value)]
            elif key in DISPLAY_TEXT:value=string(value) if value else ''
            elif key in DISPLAY_BOOLS or key=='status_expression':value=boolean(value)
            else:value=number(value,integer=True)
            if key in ('mapcolor','tacsize','lrsheight','heatchars','contact_options','ansimap'):
                setattr(unit.command_actor,key,value)
            else:setattr(unit,key,value)
        registry=getattr(self.engine,'object_registry',None)
        if registry is not None:registry.register(unit)

    def command(self,unit,name,args):
        if name.lower()=='enterbase':
            from systems.hangar import enter_base
            return enter_base(unit,args if isinstance(args,str) else ' '.join(map(str,args)),unit.command_actor)
        try:return super().command(unit,name,args)
        except DisplayDependencyError as error:return dict(ok=False,message=str(error),blocked=[error.service])

    def action(self,action):
        try:
            if action.get('op')=='display_diagnostic':
                fields(action,('op','kind','values'),('op','kind','values'))
                kind=string(action['kind'])
                if kind=='armor_field':
                    from systems.armor_display import point_condition,format_field
                    values=fields(action['values'],('current','original','internal','repairing','owner','width','divide','show_destroyed'),('current','original'))
                    current=number(values['current'],0,65535,True);original=number(values['original'],0,65535,True)
                    internal=number(values.get('internal',1),0,65535,True)
                    level=point_condition(current,original,boolean(values.get('repairing',False)))
                    text=format_field(level,current,internal,owner=boolean(values.get('owner',False)),
                        width=number(values.get('width',2),0,1000,True),divide=boolean(values.get('divide',False)),
                        show_destroyed=boolean(values.get('show_destroyed',False)))
                    result=dict(ok=True,diagnostic=True,level=level,text=text,plain=plain(text))
                elif kind=='ammo_color':
                    from systems.status_display import ammo_color
                    values=fields(action['values'],('current','maximum'),('current','maximum'))
                    result=dict(ok=True,diagnostic=True,color=ammo_color(number(values['current'],0,65535,True),number(values['maximum'],1,65535,True)))
                elif kind=='arc_string':
                    from systems.hud import arcs
                    values=fields(action['values'],('mask',),('mask',))
                    result=dict(ok=True,diagnostic=True,text=arcs(number(values['mask'],0,31,True)))
                else:raise ValueError('Unknown display diagnostic')
            elif action.get('op')=='hudinfo':
                fields(action,('op','session','text','macro'),('op','session'))
                result=self.invoke(self.sessions[string(action['session'])].request,text_value(action.get('text','')),macro=boolean(action.get('macro',False)))
            elif action.get('op')=='status_query':
                from systems.status_display import query
                fields(action,('op','unit','kind','section','slot','flag'),('op','unit','kind'))
                kind=string(action['kind'])
                if kind not in ('sectstatus','critstatus','armorstatus','weaponstatus','critslot'):raise ValueError('Unknown status query')
                section=text_value(action['section']) if 'section'in action else None
                flag=text_value(action['flag']) if 'flag'in action else None
                slot=action.get('slot')
                if slot is not None and not isinstance(slot,(str,int)):raise ValueError('Slot must be a one-based number or numeric text')
                text=self.invoke(query,self.unit(action),kind,section,slot,flag)
                result=dict(ok=not text.startswith('#-1'),text=text)
            elif action.get('op')=='display_configure':
                fields(action,('op','unit','values'),('op','unit','values'));self.configure_display(self.unit(action),action['values']);result=dict(ok=True)
            else:result=super().action(action)
            if isinstance(result,dict):
                if 'message'in result and 'lines'not in result:result['lines']=result['message'].splitlines()
                if 'lines'in result:result['plain']='\n'.join(plain(line) for line in result['lines'])
                if 'blocked'in result:
                    result['effects_complete']=not bool(result['blocked'])
                    result['outcome']='partial' if result.get('ok') and result['blocked'] else 'success' if result.get('ok') else 'refused'
            if isinstance(result,dict) and any(getattr(unit,'display_los_cells',[]) for unit in self.units.values()):result['diagnostic_los']=True
            return serialized(result)
        except DisplayDependencyError as error:return dict(ok=False,message=str(error),blocked=[error.service],effects_complete=False,outcome='refused')
        except (ValueError,TypeError,KeyError,IndexError,OSError,OverflowError) as error:return dict(ok=False,error=str(error),error_kind='invalid-input')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input');args=parser.parse_args(argv)
    try:
        with open(args.input) if args.input else sys.stdin as source:document=json.load(source,object_pairs_hook=unique_fields,parse_constant=reject_constant)
        session=DisplaySession(document);results=[session.action(a) for a in document['actions']]
        print(json.dumps(dict(results=results,state=session.snapshot(),draws=session.draws),allow_nan=False))
    except (ValueError,TypeError,KeyError,IndexError,OSError,OverflowError) as error:
        print(json.dumps(dict(ok=False,error=str(error),error_kind='invalid-input')),file=sys.stderr);return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
