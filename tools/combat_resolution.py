# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.combat.c

"""Run combat commands and event workflows from JSON (--input FILE or stdin)."""
import argparse
from copy import deepcopy
from dataclasses import asdict
import json
import sys

from tools.damage_criticals import DamageSession
from tools.movement_inputs import fields,number,boolean,array
from entities.mech import Location as L,UnitType as U,MechStatus as S,MoveType as M
from entities.crittypes import Special,i2special
from systems import targeting,weapon_modes,combat_preferences as preferences,artillery,mines
from systems.combat_commands import command_guard

CONFIG=dict(phys_use_pskill=1,glancing_blows=1,fasaturn=1,extendedmovemod=1,
            newcharge=0,tl3_charge=0,dig_only_fs=0,digbonus=3,moddamagewithrange=0,
            hotloadaddshalfbthmod=0,explode_reactor=1,explode_ammo=1,explode_time=120,explode_stop=0,moddamagewithwoods=0,new_stagger=1,stagger_interval=5,
            stagger_tonnage=1,advanced_vehicle_fire=0,heatcutoff_enabled=1,idf_requires_spotter=1,arc_override=0)
EXTRA_FIELDS=('prefs','gunnery','artillery','spotting','masc_counter','scharge_counter',
              'digging','dug_in','melee_specialist','pilot_wizard','caller_is_pilot','caller_wizard',
              'charge_target','dfa_target','charge_timer','charge_distance','c3_network','desired_facing',
              'weap_heat','infantry_specials','unusable_arcs','tics','heat_state')


class CombatSession(DamageSession):
    def __init__(self,document):
        document=deepcopy(document)
        pending=document.pop('pending_events',[])
        config=document.setdefault('config',{})
        extra={key:config.pop(key,default) for key,default in CONFIG.items()}
        board=document.setdefault('map',{})
        board.setdefault('size',[12,12])
        wind={key:board.pop(key,0) for key in ('windspeed','winddir')}
        board_fields={key:board.pop(key,default) for key,default in (('flags',0),('gravity',100),('temperature',20))}
        map_mines=board.pop('mines',[])
        document.setdefault('units',[{'name':'u','at':[3,3,0]}, {'name':'v','at':[3,2,0],'team':2}])
        super().__init__(document)
        for key,value in extra.items():setattr(self.engine,key,number(value,0,10000,True))
        number(self.engine.glancing_blows,0,2,True)
        for key,value in wind.items():setattr(self.map,key,number(value,0,integer=True))
        for key,value in board_fields.items():
            value=number(value,integer=True)
            # Map objects created by initial overlays retain their presence bit.
            if key=='flags':value |= self.map.flags & 1
            setattr(self.map,{'gravity':'grav','temperature':'temp'}.get(key,key),value)
        for record in document['units']:
            unit=self.units[record['name']]
            for key in ('charge_target','dfa_target'):
                if key in record:setattr(unit,key,self.units[record[key]]._id if isinstance(record[key],str) else number(record[key],-1,integer=True))
            if 'c3_network' in record:unit.c3_network=[self.units[name] for name in array(record['c3_network'])]
        for record in array(pending):self.schedule_callback(record)
        for record in array(map_mines):
            fields(record,('x','y','type','strength','extra','creator'),('x','y','type','strength'))
            text=' '.join(str(record.get(key,0)) for key in ('x','y','type','strength','extra'))
            mines.map_add_mine(self.map,text,number(record.get('creator',0),integer=True))
        if 'u' in self.units and 'v' in self.units:
            self.acquire_contacts()
            u=self.units['u']
            original=next(r for r in document['units'] if r['name']=='u')
            if 'target' not in original:
                accepted,_=self.invoke(targeting.set_target,self.engine,u,self.units['v'])
                if accepted:
                    from core.events import EventType
                    self.engine.events.cancel_by_type_and_data(EventType.LOCK,u)

    def add_unit(self,value):
        value=deepcopy(value)
        extra={key:value.pop(key) for key in EXTRA_FIELDS if key in value}
        value.setdefault('at',[3,3,0])
        unit=super().add_unit(value)
        unit.desired_facing=unit.facing
        for key,val in extra.items():
            if key in ('charge_target','dfa_target','c3_network'):continue
            if key=='tics':
                for i,group in enumerate(array(val)):
                    if i>=len(unit.tics):raise ValueError('too many TICs')
                    unit.tics[i]=set(number(n,0,127,True) for n in array(group))
                continue
            if key=='heat_state':
                fields(val,('heat','plus_heat','minus_heat','weap_heat','engine_heat','num_sinks','disabled_sinks','heatboom_last','thermal_sinks'))
                for field,amount in val.items():setattr(unit,field,number(amount))
                continue
            if key in ('charge_distance','weap_heat'):
                setattr(unit,key,number(val,0));continue
            if key in ('melee_specialist','pilot_wizard'):
                enabled=boolean(val)
                if unit.pilot is None:raise ValueError('pilot advantage requires pilot')
                setattr(unit.pilot,'wizard' if key=='pilot_wizard' else key,enabled)
                continue
            if key in ('digging','dug_in','caller_is_pilot','caller_wizard'):
                setattr(unit,key,boolean(val))
            elif key in ('gunnery','artillery','spotting'):
                if unit.pilot is None:raise ValueError('skill requires pilot')
                setattr(unit.pilot,key,number(val,0,30,True))
            else:setattr(unit,key,number(val,0,integer=True))
        if 'real_mass' in value:unit.rtons=int(number(value['real_mass'],0)*1024)
        for name in preferences.PREFERENCES:preferences.sync_preference(unit,name)
        if unit.unit_type==U.MECH:
            parts=(Special.SHOULDER_OR_HIP,Special.UPPER_ACTUATOR,Special.LOWER_ACTUATOR,Special.HAND_OR_FOOT_ACTUATOR)
            # Default intact actuators occupy empty slots. Explicit section
            # fixtures are reapplied below so removal/failure stays possible.
            for loc in (L.LARM,L.RARM,L.LLEG,L.RLEG):
                for index,kind in enumerate(parts):
                    slot=unit.sections[loc].criticals[index]
                    if not slot.type:slot.type=i2special(kind)
            for section in value.get('sections',[]):self.configure_section(unit,section)
        self.command_actor(unit)
        return unit

    def command_actor(self,unit):
        """Keep one deliverable caller across direct/inherited commands and scans."""
        if getattr(unit,'caller_is_pilot',True):
            actor=unit.pilot
        else:
            actor=getattr(unit,'_nonpilot_command_actor',None)
            if actor is None:
                from types import SimpleNamespace
                # Like the default fixture pilot, this local actor has no
                # persistent DBref; object identity and its inbox are stable.
                actor=SimpleNamespace(name=f'{unit.name} command actor',inbox=[])
                unit._nonpilot_command_actor=actor
        unit.command_actor=actor
        return actor

    def acquire_contacts(self):
        from systems import sensors
        from core.events import EventType
        from types import SimpleNamespace
        self.invoke(sensors.update_los_info,self.map)
        for peer in self.units.values():
            self.engine.events.cancel_by_type_and_data(EventType.PLOS,peer)
            self.invoke(targeting.plos_event,SimpleNamespace(data=peer,data2=self.engine))

    def command(self,unit,name,args):
        raw_text=args if isinstance(args,str) else None
        args=args.split() if isinstance(args,str) else array(args)
        if any(not isinstance(a,(str,int,float)) or isinstance(a,bool) for a in args):
            raise ValueError('invalid command argument')
        for arg in args:
            if isinstance(arg,(int,float)):number(arg)
        name=name.lower()
        text=raw_text if raw_text is not None else ' '.join(map(str,args))
        actor=dict(caller=self.command_actor(unit),wizard=getattr(unit,'caller_wizard',False))
        if name in ('punch','kick','trip','axe','sword','mace','claw','saw','club','charge','grabclub'):
            from systems.physical import physical_command
            return physical_command(unit,name,text,**actor)
        if name=='jump':
            from systems.movement_commands import jump_command
            ok,message=jump_command(self.engine,unit,text,actor['caller'])
            return dict(accepted=ok,text=message)
        if name=='c3connect':
            from systems.damage import external_effect
            external_effect(unit,'persistent C3 network formation','form C3 network')
            return dict(accepted=False,applied=False,blocked='persistent C3 network formation')
        if name in ('lock','aim','target'):
            fn=targeting.lock_command if name=='lock' else targeting.aim_command
            ok,message=fn(self.engine,unit,text,**actor)
            return dict(accepted=ok,text=message)
        if name in weapon_modes._COMMANDS or name in ('rac','inarc','ams'):
            reply=weapon_modes.mode_command(unit,name,text,**actor)
            return dict(accepted=reply.accepted,text='\n'.join(reply.messages))
        if name=='mechprefs':return preferences.mechprefs(unit,text,**actor)
        if name=='safety':return preferences.safety(unit,text,**actor)
        if name=='heatcutoff':
            from systems.heat_control import heat_cutoff
            ok,message=heat_cutoff(self.engine,unit,actor['caller'])
            return dict(accepted=ok,text=message)
        if name=='autoturret':return preferences.auto_turret(unit,**actor)
        if name=='disableweap':return preferences.disable_weapon(unit,text,**actor)
        if name in ('shownarcpods','removepods'):
            from systems import combat_equipment as equipment
            from entities.mech import UnitType
            if name=='shownarcpods':return equipment.show_pods(unit,**actor)
            if unit.unit_type==UnitType.MECH:return equipment.remove_pods_mech(unit,text,**actor)
            return equipment.remove_pods_tank(unit,**actor)
        if name=='explode':
            from systems.combat_equipment import explode
            return explode(unit,text,**actor)
        if name=='unjamammo':
            from systems.combat_equipment import unjam_ammo
            return unjam_ammo(unit,text,**actor)
        if name=='usebin':
            from systems.combat_ammunition import usebin
            return usebin(unit,text,**actor)
        if name in ('stealtharmor','nullsig','dig','fixturret','fliparms','masc','scharge'):
            from systems import combat_equipment
            return combat_equipment.command(unit,name,**actor)
        if name in ('firetic','addtic','deltic','cleartic','listtic'):
            from systems.tic import tic_command
            reply=tic_command(self.engine,unit,name,text,**actor)
            messages=reply[1] if isinstance(reply,tuple) else reply
            return dict(accepted=messages.accepted,text='\n'.join(messages),result=reply)
        if name=='addmine':
            try:mine=mines.map_add_mine(self.map,text,getattr(actor['caller'],'_id',-1),caller=actor['caller'])
            except ValueError as error:return dict(accepted=False,text=str(error))
            return dict(accepted=True,mine=asdict(mine))
        if name=='detonatemines':
            from systems.tic import _atoi
            if len(args)!=1:return dict(accepted=False,text='Specify a channel.')
            return dict(accepted=True,count=mines.explode_mines(unit,_atoi(args[0])))
        if name in ('fire','sight'):
            from systems.combat_firing import fire_command
            result=fire_command(self.engine,unit,args,sight=name=='sight',**actor)
            return dict(accepted=result.command_accepted,text='\n'.join(result.messages),attack=asdict(result))
        result=super().command(unit,name,args)
        if isinstance(result,dict) and "ok" in result:
            result=dict(result,accepted=result["ok"],text=result.get("message",""))
        return result

    def configure(self,unit,values):
        if not isinstance(values,dict):raise ValueError('configuration must be an object')
        values=deepcopy(values)
        for key in ('charge_target','dfa_target'):
            if key in values:
                value=values.pop(key)
                setattr(unit,key,self.units[value]._id if isinstance(value,str) else number(value,-1,integer=True))
        for key in ('charge_distance','charge_timer','masc_counter','scharge_counter','desired_facing',
                    'gunnery','artillery','piloting','weap_heat','aim','aim_type','prefs'):
            if key not in values:continue
            value=number(values.pop(key),0,integer=key not in ('charge_distance','weap_heat'))
            if key=='aim':value=number(value,0,8,True)
            if key=='aim_type':value=int(U(value))
            setattr(unit.pilot if key in ('gunnery','artillery','piloting') else unit,key,value)
            if key=='prefs':
                for name in preferences.PREFERENCES:preferences.sync_preference(unit,name)
        super().configure(unit,values)

    def schedule_callback(self,record):
        from tools.combat_diagnostics import callback,callback_data
        fields(record,('unit','callback','delay','data'),('unit','callback','delay'))
        unit=self.units[record['unit']]
        name=record['callback'];kind,fn=callback(name)
        data=callback_data(name,record.get('data',0))
        if name.startswith('booster') and data=='scharge':
            from core.events import EventType
            kind=EventType.SCHARGE_REGEN if name=='booster-regen' else EventType.SCHARGE_FAIL
        if name=='signature' and data[0]=='nullsig':
            from core.events import EventType
            kind=EventType.NSS
        self.engine.events.schedule(number(record['delay'],1,100000,True),kind,fn,unit,data)

    def diagnose_damage(self,unit,kind,options):
        self.command_actor(unit)
        from tools import combat_diagnostics
        if kind in combat_diagnostics.SCHEMAS:return combat_diagnostics.diagnose(self,unit,kind,options)
        schemas={'mine-contact':('reason',),'artillery-flight':('range',),'artillery-direction':('bearing',),
                 'mine-discovery':('range','x','y')}
        if kind not in schemas:return super().diagnose_damage(unit,kind,options)
        fields(options,schemas[kind],schemas[kind])
        if kind=='mine-contact':
            if options['reason'] not in ('step','land','fall','drop'):raise ValueError('invalid mine reason')
            return dict(count=mines.possible_mine_poof(unit,options['reason']))
        if kind=='artillery-flight':return dict(delay=artillery.flight_time(number(options['range'],0)))
        if kind=='artillery-direction':return dict(direction=artillery.artillery_direction(number(options['bearing'],0,359,True)))
        return dict(found=mines.show_mines_in_hex(unit,number(options['range'],0),number(options['x'],0,self.map.map_width-1,True),number(options['y'],0,self.map.map_height-1,True),caller=getattr(unit,'command_actor',unit.pilot)))

    def _snapshot(self):
        snap=super()._snapshot()
        for name,unit in self.units.items():
            row=snap['units'][name]
            row.update(caller_messages=list(getattr(unit.command_actor,'inbox',[])),
                prefs=unit.prefs,targ_x=unit.targ_x,targ_y=unit.targ_y,targ_z=unit.targ_z,
                aim=unit.aim,aim_type=unit.aim_type,fire_adjustment=unit.fire_adjustment,
                tics=[sorted(group) for group in unit.tics],real_mass=unit.rtons/1024,
                preferences=[preferences.preference(unit,p) for p in preferences.PREFERENCES])
            for key in ('charge_target','dfa_target','charge_distance','charge_timer','masc_counter','scharge_counter',
                        'minus_heat','cocoon','shots_fired','shots_hit','shots_missed','digging','dug_in','facing','desired_facing','turret_facing','fx','fy','fz'):
                row[key]=getattr(unit,key,0)
            for key in ('last_charge_result','last_dfa_result'):
                if hasattr(unit,key):row[key]=asdict(getattr(unit,key))
        snap['map']=dict(size=[self.map.map_width,self.map.map_height],mines=[asdict(m) for m in self.map.mines],
            mine_hexes=sorted(self.map.mine_hexes),artillery_impacts=deepcopy(self.map.artillery_impacts),
            projectiles=[dict(from_x=s.from_x,from_y=s.from_y,to_x=s.to_x,to_y=s.to_y,weapon_index=s.weapon_index,
                             mode=int(s.mode),is_hit=s.is_hit,shooter_id=s.shooter_id) for s in self.map.projectiles],
            decorations=[dict(x=x,y=y,terrain=d['terrain'],underlying=d['underlying'],deadline=d['event'].tick if d['event'] is not None else None)
                         for (x,y),d in self.map.decorations.items()],messages=deepcopy(self.map.combat_messages))
        snap['events']=[dict(kind=e.event_type.name,deadline=e.tick) for e in self.engine.events._events.values() if not e.zombie]
        # Encoded countdown data is a public diagnostic observation. Avoid
        # serializing arbitrary callback objects or private engine references.
        from core.events import EventType
        snap['countdowns']=[dict(unit=next(name for name,u in self.units.items() if u is e.data),
            deadline=e.tick,data=e.data2) for e in self.engine.events._events.values()
            if not e.zombie and e.event_type==EventType.EXPLODE and any(u is e.data for u in self.units.values())]
        snap['map']['hexes']=self.map.hex_records()
        return snap


def unique_fields(items):
    result={}
    for key,value in items:
        if key in result:raise ValueError('duplicate JSON field: '+key)
        result[key]=value
    return result


def reject_constant(value):
    raise ValueError('nonfinite number: '+value)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',help='JSON workflow; defaults to standard input')
    args=parser.parse_args(argv)
    try:
        if args.input:
            with open(args.input) as source:document=json.load(source,object_pairs_hook=unique_fields,parse_constant=reject_constant)
        else:document=json.load(sys.stdin,object_pairs_hook=unique_fields,parse_constant=reject_constant)
        session=CombatSession(document)
        results=[session.action(action) for action in document['actions']]
        print(json.dumps(dict(results=results,state=session.snapshot(),draws=session.draws),allow_nan=False))
    except (ValueError,KeyError,TypeError,IndexError,OSError) as error:
        print(str(error),file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
