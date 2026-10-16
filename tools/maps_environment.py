# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.bits.c

"""Map administration and integrated simulation CLI."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from tools.core_simulation import CoreSession,serialized
from tools.combat_resolution import unique_fields,reject_constant
from tools.movement_inputs import fields,number,array,string
from entities.map_objects import TYPES,MapObject,add_object,bits_for,object_values,save_objects,load_objects
from entities.map_storage import Coding,save_dynamic,load_dynamic,source_sizes
from systems import map_management as maps,map_links as links,map_membership as membership,map_conditions,buildings


def visibility_text(value):
    if not isinstance(value,str): raise ValueError('visibility requires text')
    return value


class MapsSession(CoreSession):
    def __init__(self,document):
        document=deepcopy(document)
        self.file_root=Path(document.pop('file_root','./tmp/maps_environment_files'))
        self.file_root.mkdir(parents=True,exist_ok=True)
        initial_files=document.pop('files',{})
        self.exported_files=set()
        self.attributes={int(key):value for key,value in document.pop('attributes',{}).items()}
        self.coding=Coding()
        super().__init__(document)
        for board in self.maps.values():
            map_conditions.alter_conditions(board)
        for name,content in initial_files.items():
            fields(content,('text','hex'))
            if len(content)!=1: raise ValueError('file requires text or hex')
            self.path(name).write_bytes(content['text'].encode('latin1') if 'text' in content else bytes.fromhex(content['hex']))

    @staticmethod
    def map_fields(record):
        extra=CoreSession.map_fields(record)
        extra['environment']={key:record.pop(key) for key in ('cfmax','regen_factor','buildflag','flags','grav','temp',
            'winddir','windspeed','visibility','map_objects','layers','effects') if key in record}
        return extra

    def apply_map_fields(self,board,extra,default_name):
        environment=extra.pop('environment',{})
        super().apply_map_fields(board,extra,default_name)
        for key in ('cfmax','regen_factor','buildflag','flags','grav','temp','winddir','windspeed'):
            if key in environment: setattr(board,key,number(environment[key],integer=True))
        if 'visibility' in environment: board.visibility_config=visibility_text(environment['visibility'])
        board.weather_effects=deepcopy(environment.get('effects',{}))
        for value in array(environment.get('map_objects',[])):
            self.insert_object(board,value)
        for value in array(environment.get('layers',[])):
            fields(value,('at','layers','data'),('at','layers','data'))
            x,y=array(value['at'],2)
            from physics.environment import integer,names,LAYERS
            integer(x);integer(y);board.require_cell(x,y)
            board.layers[x,y]=names(value['layers'],LAYERS);board.layer_data[x,y]=integer(value['data'])

    @staticmethod
    def insert_object(board,value):
        fields(value,('kind','x','y','obj','datac','datas','datai','type'),('kind',))
        kind=TYPES.index(value['kind'].upper())
        if kind==8: raise ValueError('Use bit operations to create TBITS')
        values={key:number(item,integer=True) for key,item in value.items() if key!='kind'}
        return add_object(board,kind,MapObject(**values))

    def path(self,name):
        name=string(name)[:30]
        if not name or name in ('.','..') or Path(name).name!=name or '\\' in name: raise ValueError('map files require a plain filename')
        self.exported_files.add(name)
        return self.file_root/name

    def board(self,action):
        reference=action.get('map')
        if reference is None: return self.map
        if isinstance(reference,int):
            board=next((board for board in self.maps.values() if board._id==reference),None)
            if board is None: raise ValueError('unknown map ID')
            return board
        return self.maps[reference]

    def action(self,action):
        self.initialize_random()
        op=action.get('op')
        if op=='map_attempt':
            fields(action,('op','action'),('op','action'))
            nested=action['action']
            if not isinstance(nested,dict) or nested.get('op') not in ('map_command','map_file','map_diagnose'):
                raise ValueError('map_attempt requires a map command, file operation or diagnostic')
            try: return {'value':self.action(nested),'error':None}
            except (ValueError,OSError) as error: return {'error':str(error)}
        if op=='map_command':
            fields(action,('op','map','name','args','player','tacsize','fail_second_open'),('op','name'))
            board=self.board(action)
            if action['name'].startswith(('weather.','layer.','snow.','environment.')):
                return serialized(self.invoke(self.environment_command,board,action['name'],action.get('args',{})))
            text=action.get('args','')
            if isinstance(text,list): text=' '.join(map(str,text))
            if not isinstance(text,str): raise ValueError('map command arguments must be text or an array')
            return serialized(self.invoke(self.map_command,board,string(action['name']),text,action))
        if op=='map_file':
            fields(action,('op','map','kind','file','count'),('op','kind','file'))
            return self.invoke(self.map_file,self.board(action),action)
        if op=='map_diagnose':
            fields(action,('op','map','unit','kind','args','null_map'),('op','kind'))
            null_map=action.get('null_map',False)
            if not isinstance(null_map,bool):raise ValueError('null_map requires a boolean')
            if null_map and action['kind'] not in ('sizes','linked','cf','set_cf','start_regen','regen','rebuild','conditions','melt_snow','underlying','eliminate_empties','bits'):
                raise ValueError('diagnostic has no source null-map contract')
            return serialized(self.invoke(MapsSession.diagnose,self,None if null_map else self.board(action),self.units.get(action.get('unit','u')),action['kind'],action.get('args',[])))
        if op=='map_object':
            fields(action,('op','map','value'),('op','value'))
            obj=self.insert_object(self.board(action),action['value'])
            return dict(x=obj.x,y=obj.y)
        if op=='map_value':
            fields(action,('op','map','values'),('op','values'))
            values=fields(action['values'],('cf','cfmax','regen_factor','buildflag','visibility','effects','flags','grav','temp','winddir','windspeed'))
            board=self.board(action)
            for key,value in values.items():
                setattr(board,'visibility_config' if key=='visibility' else 'weather_effects' if key=='effects' else key,
                        visibility_text(value) if key=='visibility' else dict(value) if key=='effects' else number(value,integer=True))
            return None
        return super().action(action)

    def environment_command(self,board,name,values):
        from physics.environment import command,fields,integer
        from systems.environment_storage import save_snapshot,load_snapshot
        if name=='environment.save':
            fields(values,{'file','maps'})
            if not isinstance(values.get('maps'),list):raise ValueError('save requires complete map ID list')
            boards=[self.board({'map':integer(identity)}) for identity in values['maps']]
            document=save_snapshot(self.engine,boards)
            content=json.dumps(document,allow_nan=False,sort_keys=True)
            path=self.path(values['file']);path.write_text(content,encoding='utf8')
            return {'file':path.name,'maps':values['maps'],'version':1}
        if name=='environment.load':
            fields(values,{'file'})
            document=json.loads(self.path(values['file']).read_text(encoding='utf8'),object_pairs_hook=unique_fields,parse_constant=reject_constant)
            restored=load_snapshot(self.engine,document)
            for identity,value in restored.items():
                key=next((name for name,old in self.maps.items() if old._id==identity),None)
                if key is None:
                    key=value.name or str(identity)
                    if key in self.maps:key=str(identity)
                self.maps[key]=value
            return {'maps':list(restored),'version':1}
        return command(board,name,values)

    def map_command(self,board,name,text,action):
        try: return self._map_command(board,name,text,action)
        except ValueError as exc:
            maps.report(board,str(exc),action.get('player',1))
            raise

    def _map_command(self,board,name,text,action):
        actor=action.get('player',1)
        commands={'addhex':maps.addhex,'resize':maps.resize,'setmapsize':maps.resize,'mapemit':maps.emit,
                  'conditions':map_conditions.set_conditions,'delobj':maps.delobj,'list':maps.list_mechs}
        if name in commands: return commands[name](board,text,actor=actor)
        if name in ('addfire','addsmoke'): return maps.decoration_command(board,text,0 if name=='addfire' else 1,actor=actor)
        if name=='fixmap': return maps.debug_fix(board,actor=actor)
        if name=='view': return maps.view(board,text,action.get('tacsize',''),actor=actor)
        if name in ('register','unregister'):
            getattr(self.engine,name+'_entity')(board);return None
        if name=='clear': maps.clear(board,actor=actor); return None
        if name=='free': maps.free(board); return None
        if name=='linked': links.set_linked(board,actor=actor); return None
        if name=='block': links.block_lz(board,text,action.get('player',1)); return None
        if name=='updatelinks': return links.update_links(board,self.attributes,actor=actor)
        if name=='transfer':
            from systems.map_transitions import transfer
            args=maps.arguments(text,1)
            if not args: raise ValueError('transfer requires a registered unit name')
            return transfer(self.units[args[0]],board,actor=action.get('player',1))
        if name=='leave':
            from systems.map_transitions import leave_hangar
            args=maps.arguments(text,1)
            if not args: raise ValueError('leave requires a registered unit name')
            return leave_hangar(board,self.units[args[0]])
        if name in ('load','save','check'):
            args=maps.arguments(text,1)
            if not args: raise ValueError('Invalid number of arguments!')
            path=self.path(args[0])
            if name=='check': return maps.check_file(path,board)
            if name=='load': return maps.load_checked(board,path,action.get('player',1),action.get('fail_second_open',False))
            maps.save_file(board,path,actor=actor); return None
        raise ValueError('unknown map command '+name)

    def map_file(self,board,action):
        path=self.path(action['file']); kind=action['kind']
        if kind=='save_objects': path.write_bytes(save_objects(board))
        elif kind=='load_objects': load_objects(board,path.read_bytes())
        elif kind=='save_dynamic': path.write_bytes(save_dynamic(board))
        elif kind=='load_dynamic':
            if 'count' not in action: raise ValueError('dynamic restore requires external record count')
            load_dynamic(board,path.read_bytes(),number(action['count'],0,255,True),{unit._id:unit for unit in self.units.values()})
        elif kind=='load_direct': return maps.load_file(board,path)
        else: raise ValueError('unknown map file operation')
        return {'file':path.name,'bytes':path.stat().st_size}

    def diagnose(self,board,unit,kind,args):
        from physics import weather,decorations
        from core.events import EventType
        args=array(args)
        if kind=='decoration':
            x,y,group,terrain,duration=args
            obj=decorations.add_decoration(self.engine,board,x,y,terrain,duration,kind=group)
            return obj.event.tick if obj is not None and obj.event is not None else None
        if kind=='decoration_callback':
            group,index,name=args
            callback={'spread':decorations.spread_fire,'fire':decorations.expire_fire,'smoke':decorations.expire_smoke}[name]
            obj=board.map_objects[group][index]
            if obj.event is not None:obj.event.cancel()
            callback(SimpleNamespace(data=board,data2=obj,callback=callback))
            return None
        if kind=='initialize':
            fresh=maps.initialize(*args)
            return dict(id=fresh._id,name=fresh.name,size=[fresh.map_width,fresh.map_height],
                regen_factor=fresh.regen_factor,movemod=fresh.movemod,flags=fresh.flags,
                grav=fresh.grav,temp=fresh.temp,hexes=fresh.hex_records())
        if kind in ('object_find','object_first','object_next','object_delete','objects_delete'):
            from entities.map_objects import find_object,first_object,next_object,delete_object,delete_objects
            if kind=='object_find': obj=find_object(board,*args)
            elif kind=='object_first': obj=first_object(board,*args)
            elif kind=='object_next':
                group,index=args
                obj=next_object(board,group,board.map_objects[group][index])
            elif kind=='object_delete':
                group,index,zap=args
                return delete_object(board,board.map_objects[group][index],group,zap)
            else: delete_objects(board,*args); return None
            if obj is None:return None
            group=next(i for i,rows in enumerate(board.map_objects) if obj in rows)
            return dict(kind=TYPES[group],values=object_values(obj,group))
        if kind=='underlying':
            from entities.map_objects import underlying_terrain,mech_underlying_terrain
            return {'map':underlying_terrain(board,*args),'unit':mech_underlying_terrain(unit) if unit is not None else None}
        if kind=='membership_state':
            # Explicit corruption fixture for inspecting the C consistency guards.
            values=fields(args[0],('mapnumber','mapindex','num_seen'))
            for key,value in values.items():setattr(unit,key,number(value,integer=True))
            return None
        if kind=='weather_mapping': return weather.mapping_status()
        if kind=='debug_fix':
            records={}
            for identity,record in args[0].items():
                record=dict(record)
                if 'unit' in record: record['unit']=self.units[record['unit']]
                records[int(identity)]=record
            maps.debug_fix(board,records); return None
        if kind=='sizes': return source_sizes(board,*args)
        if kind=='coding_index': return self.coding.index(*args)
        if kind=='coding_inverse': return self.coding.inverse(*args)
        if kind=='coding_initialize': self.coding.initialize(); return None
        if kind=='bits':
            operation,*values=args
            if board is None:
                if operation!='query':raise ValueError('only bit queries accept a null map')
                return 0
            if operation in ('set','unset','query'):
                from entities.map_storage import BitTable
                if len(values)!=3:raise ValueError('bit operation requires x y selector')
                BitTable(board.map_width,board.map_height).position(*values[:2])
                if type(values[2]) is not int or values[2] not in (1,2):raise ValueError('bit selector requires 1 or 2')
            bits=bits_for(board,operation in ('set','unset','create'))
            if operation=='create': return None
            if operation=='query': return bits.query(*values) if bits is not None else 0
            if operation=='size': return bits.size() if bits is not None else 0
            if bits is None: return None
            if operation not in ('set','unset','clear'): raise ValueError('unknown bits operation')
            getattr(bits,operation)(*values)
            from entities.map_objects import publish_mine_bits
            publish_mine_bits(board)
            return None
        if kind=='linked': return links.linked(board)
        if kind=='entrance':
            obj=links.entrance(board,*args)
            return None if obj is None else {'x':obj.x,'y':obj.y,'direction':chr(obj.datac)}
        if kind=='parse_coord': return links.parse_coord(board,*args)
        if kind=='blocked_lz': return links.blocked_lz(unit,board,*args)
        if kind=='conditions': map_conditions.update_conditions(unit,board); return None
        if kind=='membership_add': membership.add(board,unit); return None
        if kind=='membership_remove': membership.remove(board,unit); return None
        if kind=='consistency': membership.consistency(unit,self.engine.get_entities()); return None
        if kind=='eliminate_empties': membership.eliminate_empties(board); return None
        if kind=='clear_los': membership.clear_los(unit); return None
        if kind=='cf': return buildings.get_cf(board)
        if kind=='set_cf': buildings.set_cf(board,*args); return None
        if kind=='start_regen':
            event=buildings.start_regen(board)
            return event.tick if event else None
        if kind in ('regen','rebuild'):
            getattr(buildings,kind)(SimpleNamespace(data=board)); return None
        if kind=='schedule_regen':
            return self.engine.events.schedule(*args,EventType.BREGEN,buildings.regen,board).tick
        if kind=='hit_building': return buildings.hit_building(unit,*args)
        if kind in ('hit_building_weapon','building_missile_count'):
            from entities.weapon import get_weapon
            name=args[2] if kind=='hit_building_weapon' else args[0]
            weapon=get_weapon(name)
            if weapon is None:raise ValueError('unknown building weapon')
            if kind=='building_missile_count':return buildings.missile_count(unit,weapon)
            return buildings.hit_building(unit,args[0],args[1],weapon.index,*args[3:])
        if kind in ('step_building','scan_building'): return buildings.query(unit,*args,step=kind=='step_building')
        if kind=='fire_hex':
            from systems.terrain_combat import fire_hex
            return fire_hex(unit,*args)
        if kind=='clear_hex':
            from systems.terrain_combat import clear_hex
            return clear_hex(unit,*args)
        if kind=='spread_coordinates': return decorations.spread_coordinates(board,*args)
        if kind=='validate_weather': return weather.validate_conditions(*args)
        if kind=='calc_weather': return weather.calc_effects(*args)
        if kind=='gun_weather': return weather.gun_effects(*args)
        if kind=='pilot_weather': return weather.pilot_effects(unit,*args)
        if kind=='heat_weather': return weather.heat_effects(board,unit,*args)
        if kind=='grow_snow': weather.grow(board,*args); return None
        if kind=='melt_snow':
            x,y,depth,options=args
            weather.melt(board,x,y,depth,**fields(options,('emit','steam','ice'))); return None
        raise ValueError('unknown map diagnostic '+kind)

    def _snapshot(self):
        result=super()._snapshot()
        for name,board in self.maps.items():
            row=result['maps'][name]
            row.update(flags=board.flags,grav=board.grav,temp=board.temp,cf=board.cf,cfmax=board.cfmax,
                name=board.name,
                regen_factor=board.regen_factor,buildflag=board.buildflag,onmap=board.onmap,
                first_free=board.first_free,roster_ids=list(board.roster_ids),slot_flags=list(board.mechflags),
                slot_los=[values[:board.first_free] for values in board.slot_los[:board.first_free]],
                mapvis=board.mapvis,maxvis=board.maxvis,light=board.maplight,winddir=board.winddir,windspeed=board.windspeed,
                cloudbase=board.cloudbase,objects=[],layers=[dict(at=list(xy),layers=sorted(layers),data=board.layer_data.get(xy,0)) for xy,layers in sorted(board.layers.items())],
                messages=list(board.map_messages),errors=list(getattr(board,'map_errors',[])),external_effects=deepcopy(board.external_effects),
                grid_allocated=board._terrain is not None)
            from physics.environment import show
            row['weather']=show(board)
            row['snow_validation_trace']=deepcopy(getattr(board,'snow_validation_trace',[]))
            row['partial_grid']=board._grid_failed
            row['hexes']=board.hex_records()
            for kind,group in enumerate(board.map_objects):
                for obj in group:
                    if kind==8:
                        row['objects'].append(dict(kind='TBITS',rows=[list(values) if values is not None else None for values in obj.bits.rows],attached=obj.bits.attached))
                    else:
                        x,y,identity,record_type,dc,ds,di=object_values(obj,kind)
                        row['objects'].append(dict(kind=TYPES[kind],x=x,y=y,obj=identity,type=record_type,datac=dc,datas=ds,datai=di,
                            deadline=obj.event.tick if getattr(obj,'event',None) is not None and not obj.event.zombie else None))
        for name,unit in self.units.items(): result['units'][name].update(mapnumber=getattr(unit,'mapnumber',0),cached_terrain=unit.terrain,cached_elevation=unit.elev)
        for row,event in zip(result['events'],self.engine.events.pending_events()):
            row['map']=next((name for name,board in self.maps.items() if event.data is board),None)
            if isinstance(event.data2,MapObject): row['object']={'x':event.data2.x,'y':event.data2.y}
        result['files']={name:{'hex':self.path(name).read_bytes().hex(),'text':self.path(name).read_bytes().decode('latin1')}
                         for name in sorted(self.exported_files) if self.path(name).is_file()}
        return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--input')
    args=parser.parse_args(argv)
    try:
        with open(args.input) if args.input else sys.stdin as source:
            document=json.load(source,object_pairs_hook=unique_fields,parse_constant=reject_constant)
        session=MapsSession(document)
        results=[session.action(action) for action in document['actions']]
        print(json.dumps(dict(results=results,state=session.snapshot(),draws=session.draws),allow_nan=False))
    except (ValueError,KeyError,TypeError,IndexError,OSError,OverflowError) as error:
        print(str(error),file=sys.stderr); return 1
    return 0


if __name__=='__main__': raise SystemExit(main())
