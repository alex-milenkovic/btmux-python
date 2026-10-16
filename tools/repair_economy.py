"""Shared repair, inventory and towing JSON interface; docs/repair-economy-cli.md."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from core.events import Event,SOURCE_EVENT_IDS
from tools.aerospace import AerospaceSession
from tools.core_simulation import serialized
from tools.combat_resolution import unique_fields,reject_constant
from tools.movement_inputs import fields,number,boolean,array,string
from systems.economic_inventory import InventoryStore
from systems.technician import Technician,Config,parse_part,parse_gun,valid_gun_position,pack,unpack,variable_minutes
from systems.repair_jobs import RepairJobs,completely_intact_internal
from systems.repair_work import RepairWork,invalid_repair_path,invalid_scrap_path
from systems.repair_reports import RepairReports
from systems.cargo_commands import CargoCommands

TECH_COMMANDS=('removegun','removepart','removesection','replacegun','repairgun','fixenhcrit','replacepart','repairpart',
    'toggletype','reload','unload','fixarmor','fixinternal','reattach','replacesuit','reseal','fixextra','magic','checkstatus','repairs')
CARGO_COMMANDS=('manifest','stores','rfixstuff','raddstuff','rremovestuff','rresetstuff','loadcargo','unloadcargo')


def attribute_text(value):
    if not isinstance(value,str):raise ValueError('Expected text attribute')
    return value


class RepairEconomySession(AerospaceSession):
    def __init__(self,document):
        document=deepcopy(document);self.repair_inputs={}
        options=fields(document.pop('repair_economy',{}),('root','config','restart','objects'))
        root=Path(string(options.get('root','./tmp/repair_economy'))).resolve()
        from data.template_dependency import resolve_catalog
        upstream=resolve_catalog(document.get('construction',{}).get('catalog'))
        if upstream is not None and (root.is_relative_to(upstream.resolve()) or upstream.resolve().is_relative_to(root)):raise ValueError('Economy storage and upstream template roots overlap')
        super().__init__(document)
        self.economy_root=root;root.mkdir(parents=True,exist_ok=True)
        self.inventory=InventoryStore(self.directory.catalog,root/'objects.json')
        for obj in list(self.maps.values())+list(self.personnel.objects.values()):
            self.inventory.register(obj._id,obj)
        for board in self.maps.values():
            if self.inventory.get(board._id,'in_character') is None:self.inventory.put(board._id,'in_character',getattr(board,'in_character',False))
        for record in array(options.get('objects',[])):self.configure_inventory(record)
        config=fields(options.get('config',{}),Config.__dataclass_fields__)
        config={key:number(value,0,1000000,True) for key,value in config.items()}
        self.technician=Technician(self.engine,self.inventory,Config(**config));self.technician.restart=number(options.get('restart',0),integer=True)
        self.repair_jobs=RepairJobs(self.engine,self.technician,self.inventory)
        self.repair_work=RepairWork(self.repair_jobs);self.repair_reports=RepairReports(self.repair_work);self.cargo= CargoCommands(self.inventory)
        for name,values in self.repair_inputs.items():self.configure_repair_unit(self.units[name],values)

    def create_character(self,record):
        record=deepcopy(record);tech=record.pop('tech',False)
        identity=super().create_character(record)
        self.characters.records[identity]['tech']=boolean(tech);self.characters.persist(identity)
        return identity

    def add_unit(self,record):
        record=deepcopy(record);repair=record.pop('repair',{})
        unit=super().add_unit(record);self.repair_inputs[record['name']]=repair
        if hasattr(self,'inventory'):
            self.inventory.register(unit._id,unit);self.configure_repair_unit(unit,repair)
        return unit

    def configure_repair_unit(self,unit,values):
        fields(values,('stall','towable','location','max_suits','burn_recovery_countdown'))
        for key,value in values.items():
            if key=='location':self.personnel.move(unit._id,number(value,0,integer=True))
            elif key=='max_suits':unit.max_suits=number(value,0,8,True)
            elif key=='burn_recovery_countdown':unit.burn_recovery_countdown=number(value,0,1000000,True)
            else:setattr(unit,'repair_stall' if key=='stall' else key,boolean(value))

    def configure_inventory(self,record):
        fields(record,('id','ECONPARTS','TECHTIME','MECHSKILLS','in_character'),('id',))
        identity=number(record['id'],0,2147483647,True);self.inventory.register(identity)
        for key,value in record.items():
            if key!='id':self.inventory.put(identity,key,boolean(value) if key=='in_character' else attribute_text(value))

    def queue_row(self,event):
        actor,loc,pos,extra=unpack(event.data2)
        return dict(id=event.event_id,type=SOURCE_EVENT_IDS[event.event_type],unit=event.data._id,actor=actor,location=loc,
            position=pos,extra=extra,payload=event.data2,due=event.tick,remaining=event.tick-self.engine.tick,
            fake=event.repair_fake,callback=event.repair_callback)

    def command(self,unit,name,args):
        routed=name.lower() in TECH_COMMANDS+CARGO_COMMANDS+('techstatus','damages','fix','pickup','attachcables','detachcables','dropoff')
        try:result=self.repair_command(unit,name,args)
        except ValueError as error:
            if routed and not getattr(error.args[0] if error.args else '', 'notified',False):self.technician.notice(unit.command_actor,str(error))
            raise
        if routed and isinstance(result,dict) and not result.get('ok',True) and not getattr(result.get('error'),'notified',False):
            self.technician.notice(unit.command_actor,result.get('error','Command refused'))
        return result

    def repair_command(self,unit,name,args):
        name=name.lower();text=args if isinstance(args,str) else ' '.join(map(str,array(args)))
        actor=unit.command_actor
        if name in TECH_COMMANDS:result=self.repair_work.command(actor,unit,name,text)
        elif name=='techstatus':return self.technician.status(actor)
        elif name=='damages':return dict(ok=True,rows=self.repair_reports.human(actor,unit),machine=self.repair_reports.machine(unit),pristine=not self.repair_reports.table(unit))
        elif name=='fix':return dict(ok=True,rows=self.repair_reports.fix(actor,unit,text))
        elif name in CARGO_COMMANDS:result=self.cargo.command(actor,unit,name,text)
        elif name in ('attachcables','detachcables','dropoff'):
            from systems import towing
            return getattr(towing,{'attachcables':'attach_cables','detachcables':'detach_cables','dropoff':'dropoff'}[name])(unit,actor,text)
        else:return super().command(unit,name,args)
        if isinstance(result,Event):return dict(ok=True,job=self.queue_row(result))
        return dict(ok=True,result=serialized(result))

    def repair_path(self,name):
        path=(self.economy_root/string(name)).resolve()
        if not path.is_relative_to(self.economy_root) or path==self.economy_root:raise ValueError('Repair file outside local economy root')
        path.parent.mkdir(parents=True,exist_ok=True);return path

    def action(self,action):
        try:
            self.initialize_random()
            if action.get('op')=='repair':return serialized(self.invoke(self.repair_action,action))
            if action.get('op')=='repair_diagnose':return serialized(self.invoke(self.repair_diagnose,action))
            return super().action(action)
        except (ValueError,TypeError,KeyError,IndexError,OSError,OverflowError) as error:
            return dict(ok=False,error=str(error))

    def repair_action(self,a):
        fields(a,('op','kind','unit','actor','object','part','brand','count','attribute','value','file','text','values'),('op','kind'))
        kind=a['kind']
        if kind=='save':
            text=self.repair_jobs.save();self.repair_path(a.get('file','repairs.jsonl')).write_text(text)
            return dict(ok=True,text=text)
        if kind=='load':return self.repair_jobs.load(attribute_text(a['text']) if 'text' in a else self.repair_path(a.get('file','repairs.jsonl')).read_text())
        if kind=='objects':return deepcopy(self.inventory.records)
        if kind=='inventory':return self.inventory.listing(number(a['object'],0,integer=True))
        if kind=='configure':self.configure_repair_unit(self.unit(a),a['values']);return dict(ok=True)
        if kind=='configure_object':self.configure_inventory(a['values']);return dict(ok=True)
        if kind=='config':
            for key,value in fields(a['values'],Config.__dataclass_fields__).items():setattr(self.technician.config,key,number(value,0,1000000,True))
            return dict(vars(self.technician.config))
        if kind=='status':return self.technician.status(self.characters.actor(number(a['actor'],0,32767,True)))
        if kind=='actor':
            identity=number(a['actor'],0,32767,True)
            for key,value in fields(a['values'],('tech','wizard','god','location')).items():
                if key=='location':self.personnel.move(identity,number(value,0,integer=True))
                else:self.characters.records[identity][key]=boolean(value)
            self.characters.persist(identity);self.characters.actor(identity);return dict(ok=True)
        if kind=='attribute':
            attribute=string(a['attribute'])
            if attribute not in ('ECONPARTS','TECHTIME','MECHSKILLS'):raise ValueError('Unsupported repair attribute')
            identity=number(a['object'],0,integer=True)
            if 'value' in a:self.inventory.put(identity,attribute,attribute_text(a['value']))
            return self.inventory.get(identity,attribute,'')
        if kind in ('find','change','set','remove','add'):
            from data.construction_catalog import source_part
            part=source_part(a['part']) if isinstance(a['part'],str) else number(a['part'],0,1023,True)
            args=[number(a['object'],0,integer=True),part,number(a.get('brand',0),0,5,True)]
            if kind in ('change','set','add'):args.append(number(a['count'],-2147483648,2147483647,True))
            return getattr(self.inventory,kind)(*args)
        if kind=='persist':self.inventory.persist();return dict(ok=True)
        raise ValueError('Unknown repair operation')

    def repair_diagnose(self,a):
        fields(a,('op','kind','unit','actor','loc','pos','extra','type','payload','delay','fake','callback','argument','brand','rear','position','amount','helper','margin','minutes','part'),('op','kind'))
        kind=a['kind'];unit=self.unit(a)
        loc=number(a.get('loc',0),0,15,True);pos=number(a.get('pos',0),0,11,True)
        actor=self.characters.actor(number(a['actor'],0,32767,True)) if 'actor' in a else unit.command_actor
        if kind=='parsepart':return parse_part(unit,attribute_text(a['argument']),position=boolean(a.get('position',True)),rear=boolean(a.get('rear',False)),extra=boolean(a.get('extra',False)))
        if kind=='parsegun':return parse_gun(unit,attribute_text(a['argument']),self.inventory.catalog,brand=boolean(a.get('brand',False)))
        if kind=='validgun':return valid_gun_position(unit,loc,pos)
        if kind=='pack':return pack(actor._id,loc,pos,number(a.get('extra',0),0,255,True))
        if kind=='schedule':
            event=self.repair_jobs.schedule(number(a['type'],43,58,True),unit,number(a['payload'],0,2147483647,True),number(a.get('delay',1),0,integer=True),fake=boolean(a.get('fake',False)),callback=a.get('callback'))
            return self.queue_row(event)
        if kind=='count':return self.repair_jobs.count(unit,number(a['type'],43,58,True),loc,pos if 'pos' in a else None)
        if kind in ('repairing','scrapping_part','can_scrap_part'):return getattr(self.repair_jobs,kind)(unit,loc,pos)
        if kind in ('fixing','can_scrap_location'):return getattr(self.repair_jobs,kind)(unit,loc)
        if kind=='latest':return self.repair_jobs.latest(unit)
        if kind=='queue_tick':
            # Explicit clock fixture for overdue save boundaries; no dispatch.
            self.engine.events.set_tick(number(a['amount'],0,1000000,True))
            return self.engine.tick
        if kind=='intact_internal':return completely_intact_internal(unit)
        if kind=='fixable':
            from systems.damage import unit_is_fixable
            return unit_is_fixable(unit)
        if kind in ('damage_table','scrap_table','machine'):return getattr(self.repair_reports,kind)(unit)
        if kind=='repair_path':return invalid_repair_path(unit,loc)
        if kind=='scrap_path':return invalid_scrap_path(unit,loc)
        if kind=='economy':
            try:return self.repair_work.economy(string(a['helper']),unit,loc,pos,number(a.get('amount',0),integer=True))
            except ValueError as error:
                self.technician.notice(actor,str(error))
                raise
        if kind=='failure':return self.repair_work.failure(string(a['helper']),actor,unit,loc,pos,number(a.get('amount',0),integer=True))
        if kind=='success':return self.repair_work.success(string(a['helper']))
        if kind=='roll':return self.technician.roll(actor,unit,number(a.get('amount',0),integer=True),weapons=boolean(a.get('brand',False)))
        if kind=='add_time':return self.technician.add_time(actor,number(a['minutes'],integer=True))
        if kind=='lag':return dict(lag=self.technician.lag(),adjusted=self.technician.lagged(number(a.get('amount',0),integer=True)))
        if kind=='variable':return self.repair_work.variable(number(a['minutes'],0,integer=True),number(a['margin'],integer=True))
        if kind=='cargo_weight':
            from systems.parts import set_cargo_weight
            return set_cargo_weight(unit)
        if kind=='correct_speed':
            from systems.vehicle_combat import correct_speed
            correct_speed(unit);return dict(speed=unit.speed,desired=unit.desired_speed)
        if kind in ('proper_armor','proper_internal'):
            from systems import parts
            from data.construction_catalog import source_id
            return source_id(getattr(parts,kind)(unit))
        if kind=='alias_part':
            from systems.repair_materials import repair_alias
            from data.construction_catalog import source_part
            part=source_part(a['part']) if isinstance(a['part'],str) else number(a['part'],0,1023,True)
            return repair_alias(unit,part)
        if kind=='ammo_mode':
            from systems.repair_materials import valid_ammo_mode
            return valid_ammo_mode(unit,loc,pos,string(a['argument']))
        if kind=='ammo_type':
            from systems.repair_materials import find_ammo_type
            return find_ammo_type(unit,loc,pos)
        raise ValueError('Unknown repair diagnostic')

    def _snapshot(self):
        state=super()._snapshot()
        state['economy']=dict(objects=deepcopy(self.inventory.records),writes=deepcopy(self.inventory.writes),external=deepcopy(self.inventory.external))
        state['repair_jobs']=[self.queue_row(event) for event in self.repair_jobs.events()]
        state['technician']=dict(config=vars(self.technician.config).copy(),messages=deepcopy(self.technician.messages),rolls=deepcopy(self.technician.rolls))
        state['repair_messages']=deepcopy(self.repair_jobs.messages);state['cargo_messages']=deepcopy(self.cargo.messages)
        for name,unit in self.units.items():state['units'][name]['repair']=dict(stall=getattr(unit,'repair_stall',False),max_suits=getattr(unit,'max_suits',0),towable=getattr(unit,'towable',False),location=unit.location,swarm_target=getattr(unit.swarm_target,'_id',unit.swarm_target),burn_recovery_countdown=getattr(unit,'burn_recovery_countdown',0),carrying=unit.carrying,towed_unit=getattr(getattr(unit,'towed_unit',None),'_id',None))
        return state


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input');args=parser.parse_args(argv)
    try:
        with open(args.input) if args.input else sys.stdin as source:document=json.load(source,object_pairs_hook=unique_fields,parse_constant=reject_constant)
        session=RepairEconomySession(document);results=[session.action(action) for action in document['actions']]
        print(json.dumps(dict(results=results,state=session.snapshot(),draws=session.draws),allow_nan=False))
    except (ValueError,TypeError,KeyError,IndexError,OSError,OverflowError) as error:
        print(json.dumps(dict(ok=False,error=str(error))),file=sys.stderr);return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
