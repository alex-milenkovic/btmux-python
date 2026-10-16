# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# Historical Aerospace sources:
#   btech/aero.move.c

"""Aerospace commands and simulation JSON interface; docs/aerospace-cli.md."""
import argparse
from copy import deepcopy
from dataclasses import asdict
import json
import sys
from tools.communications import CommunicationsSession
from tools.core_simulation import serialized
from tools.combat_resolution import unique_fields,reject_constant
from tools.movement_inputs import fields,number,boolean,array
from systems import turrets,bombing,dropships
from physics import aerospace
from entities.mech import MechStatus as S,CritStatus as C
from core.events import EventType

FLOATS=('start_fx','start_fy','start_fz','fx','fy','fz','speed','desired_speed','vertical_speed','max_speed')
INTS=('desired_angle','desired_facing','start_spin','fuel','fuel_orig','z','x','y','elev','targ_x','targ_y','targ_z','target','tac_range','lrs_range','carrying','last_dropship_notice')
BOOLS=('landed','spinning','zombie','free_fuel')


class AerospaceSession(CommunicationsSession):
    def __init__(self,document):
        document=deepcopy(document)
        turret_specs=document.pop('turrets',[])
        options=fields(document.pop('aerospace',{}),('blzmapmode',))
        self.aircraft_inputs={}
        self.bay_inputs={}
        super().__init__(document)
        self.engine.blzmapmode=number(options.get('blzmapmode',0),integer=True)
        self.engine.pilot_override=self.engine.arc_override=0
        for name,values in self.aircraft_inputs.items():self.configure_aircraft(self.units[name],values)
        for name,values in self.bay_inputs.items():self.configure_bay(self.maps[name],values)
        self.turrets={}
        for record in turret_specs:self.add_turret(record)

    @staticmethod
    def map_fields(record):
        bay=record.pop('bay',{})
        extra=CommunicationsSession.map_fields(record)
        extra['bay']=bay
        return extra

    def apply_map_fields(self,board,extra,default_name):
        bay=extra.pop('bay',{})
        super().apply_map_fields(board,extra,default_name)
        self.bay_inputs[board.name]=bay

    def add_unit(self,record):
        record=deepcopy(record)
        values=record.pop('aerospace',{})
        unit=super().add_unit(record)
        self.aircraft_inputs[record['name']]=values
        return unit

    def configure_aircraft(self,unit,values):
        fields(values,FLOATS+INTS+BOOLS+('bays',))
        for key,value in values.items():
            if key in BOOLS:
                value=boolean(value)
                if key=='landed':unit.set_status(S.LANDED) if value else unit.clear_status(S.LANDED)
                elif key=='spinning':unit.set_crit_status(C.SPINNING) if value else unit.clear_crit_status(C.SPINNING)
                else:setattr(unit,key,value)
            elif key=='bays':unit.aero_bays=[self.maps[v]._id if isinstance(v,str) else number(v,integer=True) for v in array(value,4)]
            else:setattr(unit,key,number(value,integer=key in INTS))

    def configure_bay(self,board,values):
        fields(values,('enter_lock','lock_result','fail_message','in_character','onmap'))
        for key,value in values.items():
            if key in ('lock_result','in_character'):value=boolean(value)
            elif key=='onmap':value=self.units[value]._id if isinstance(value,str) else number(value,integer=True)
            elif not isinstance(value,str):raise ValueError('Bay lock/message must be text')
            setattr(board,key,value)

    def add_turret(self,record):
        fields(record,('name','id','parent','gunner','arcs','target','targ_x','targ_y','targ_z','lockmode'),('name','id','parent'))
        identity=number(record['id'],1,integer=True)
        if record['name'] in self.turrets or identity in self.personnel.objects or any(o._id==identity for o in self.engine.get_entities()):raise ValueError('Duplicate turret identity')
        parent=record['parent'];parent=self.units[parent]._id if isinstance(parent,str) else number(parent,integer=True)
        owner=next((u for u in self.units.values() if u._id==parent),None)
        if owner is not None and len(getattr(owner,'aero_turrets',[])) >= 3:
            raise ValueError('Aerospace supports exactly three turret slots')
        turret=turrets.Turret(_id=identity,parent=parent)
        for key,value in record.items():
            if key in ('name','id','parent'):continue
            if key=='target' and isinstance(value,str):value=self.units[value]._id
            setattr(turret,key,number(value,integer=True))
        self.turrets[record['name']]=turret
        self.engine.register_entity(turret)
        self.personnel.add(turret,parent)
        owner=turrets.parent(self.engine,turret)
        if owner is not None:owner.aero_turrets=list(getattr(owner,'aero_turrets',[]))+[identity]
        return turret

    def command(self,unit,name,args):
        name=name.lower()
        text=args if isinstance(args,str) else ' '.join(map(str,array(args)))
        caller=unit.command_actor
        if name in ('takeoff','thrust'):result=getattr(aerospace,name)(self.engine,unit,text,caller)
        elif name=='land':
            from systems.movement_commands import land
            result=land(self.engine,unit,caller)
        elif name in ('climb','dive'):result=aerospace.vheading(unit,text,1 if name=='climb' else -1)
        elif name=='checklz':result=aerospace.checklz(unit,text,caller)
        elif name=='bomb':
            result=bombing.command(unit,text,caller)
            from systems.notifications import personal_notify
            for line in result.get('lines',[]):personal_notify(caller,line)
            if result.get('error'):personal_notify(caller,result['error'])
            return result
        elif name=='createbays':
            references=[self.maps[v]._id if v in self.maps else v for v in text.split()]
            result=dropships.create_bays(unit,references)
        elif name=='enterbay':result=dropships.enter_bay(unit,text,caller)
        elif name in ('vertical','eta','heading','speed'):
            from systems import movement_commands as movement
            result=getattr(movement,name)(self.engine,unit,text,caller)
        elif name in ('lrs','tactical','navigate','findcenter','critstatus','status','weaponspecs'):
            return turrets.delegate(unit,name,text,caller)
        else:return super().command(unit,name,args)
        from systems.notifications import personal_notify
        private_query=result[0] and (name=='createbays' or name in ('thrust','climb','dive') and not text.split())
        if (private_query or not result[0]) and result[1] and not getattr(result[1],'notified',False):
            personal_notify(caller,result[1])
        return dict(ok=result[0],accepted=result[0],message=result[1])

    def action(self,action):
        try:
            self.initialize_random()
            op=action.get('op')
            if op=='aero_configure':
                fields(action,('op','unit','values'),('op','unit','values'))
                self.configure_aircraft(self.unit(action),action['values']);return dict(ok=True)
            if op=='bay_configure':
                fields(action,('op','map','values'),('op','values'))
                self.configure_bay(self.board(action),action['values']);return dict(ok=True)
            if op=='turret':
                fields(action,('op','turret','actor','name','args'),('op','turret','actor','name'))
                turret=self.turrets[action['turret']]
                actor=self.personnel.objects[number(action['actor'],integer=True)]
                args=action.get('args','');args=args if isinstance(args,str) else ' '.join(map(str,array(args)))
                result=self.invoke(self.engine.inject_command,actor,lambda:turrets.command(self.engine,turret,actor,action['name'],args),action['name'])
                if result.get('message') and not result['ok'] and not result.get('notified') and not getattr(result['message'],'notified',False):
                    from systems.notifications import personal_notify
                    personal_notify(actor,result['message'])
                return serialized(result)
            if op=='turret_diagnose':
                fields(action,('op','turret','selector'),('op','turret','selector'))
                turret=self.turrets[action['turret']]
                selector=number(action['selector'],0,1,integer=True)
                turrets.allocate(turret,turret._id,selector)
                return asdict(turret)
            if op=='aero_diagnose':
                fields(action,('op','unit','kind','x','y','time','damage','count','severity','direction','reference','ship'),('op','unit','kind'))
                return serialized(self.invoke(self.aero_diagnose,action))
            return super().action(action)
        except (ValueError,TypeError,KeyError,IndexError,OSError,OverflowError) as error:return dict(ok=False,error=str(error))

    def aero_diagnose(self,a):
        unit=self.unit(a);kind=a['kind']
        if kind=='speed':aerospace.update_speed(unit)
        elif kind=='heading':aerospace.update_heading(unit)
        elif kind=='control':aerospace.control_effect(unit)
        elif kind=='update':
            from core.game_loop import mech_update
            mech_update(self.engine,unit)
        elif kind=='fuel':
            from physics.heights import fuel_check
            return dict(stop=fuel_check(unit),fuel=unit.fuel)
        elif kind=='bridge':
            from systems.hit_locations import bridge_hit
            bridge_hit(unit)
        elif kind=='exhaust':aerospace.exhaust(unit,number(a.get('damage',8),integer=True))
        elif kind=='warning':return aerospace.land_warning(unit,number(a.get('severity',0),integer=True))
        elif kind=='lz':return aerospace.improper_lz(unit,a.get('x'),a.get('y'))
        elif kind=='calc_dest':return bombing.calc_dest(unit)
        elif kind=='simulate_flight':return bombing.simulate_flight(unit,unit.map,number(a['x'],integer=True),number(a['y'],integer=True),number(a['time']))
        elif kind=='destroy_bomb':bombing.destroy_bomb(unit,number(a.get('direction',0),integer=True))
        elif kind=='takeoff_event':self.engine.schedule_event(1,EventType.TAKEOFF,aerospace.takeoff_event,data=unit,data2=number(a['count'],integer=True))
        elif kind=='edge':
            from systems.map_transitions import check_edge_of_map
            check_edge_of_map(unit)
        elif kind=='move':
            from physics.movement import start_move_event
            start_move_event(self.engine,unit)
        elif kind=='doors':
            ship=self.units[a['ship']]
            return dict(number=dropships.bay_number(ship,number(a.get('direction',0),integer=True)),direction=dropships.bay_direction(ship,number(a.get('reference',0),integer=True)),adjacent=dropships.adjacent_bay(unit,ship),open=dropships.bay_open(unit,ship,number(a.get('reference',0),integer=True)))
        else:raise ValueError('Unknown aerospace diagnostic: '+kind)
        return dict(ok=True)

    def _snapshot(self):
        state=super()._snapshot()
        state['turrets']={name:asdict(turret) for name,turret in self.turrets.items()}
        state['overrides']=dict(pilot=self.engine.pilot_override,arc=self.engine.arc_override)
        for name,unit in self.units.items():
            state['units'][name]['aerospace']={key:getattr(unit,key,0) for key in FLOATS+INTS}
            state['units'][name]['aerospace'].update(landed=unit.has_status(S.LANDED),spinning=unit.has_crit_status(C.SPINNING),bays=list(unit.aero_bays),payload=bombing.payload(unit))
        for row,event in zip(state['events'],self.engine.events.pending_events()):
            if isinstance(event.data,bombing.BombShot):
                row['bomb']=dict(map=event.data.board._id,x=event.data.x,y=event.data.y,index=event.data.index)
        return state


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input');args=parser.parse_args(argv)
    try:
        with open(args.input) if args.input else sys.stdin as source:document=json.load(source,object_pairs_hook=unique_fields,parse_constant=reject_constant)
        session=AerospaceSession(document)
        results=[session.action(action) for action in document['actions']]
        print(json.dumps(dict(results=results,state=session.snapshot(),draws=session.draws),allow_nan=False))
    except (ValueError,TypeError,KeyError,IndexError,OSError,OverflowError) as error:
        print(json.dumps(dict(ok=False,error=str(error))),file=sys.stderr);return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
