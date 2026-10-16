"""Persistent characters, personal combat and unit personnel JSON interface."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from tools.construction_templates import ConstructionSession,text
from tools.core_simulation import serialized
from tools.combat_resolution import unique_fields,reject_constant
from tools.movement_inputs import fields,number,boolean,array,string
from data.characters import CharacterStore,Stats,ALL,integer
from data.character_values import VALUES,code
from systems import characters as c
from systems.occupants import Personnel

CHARACTER_BOOLS=('is_player','valid','alive','connected','wizard','wiz_r','god','in_character','slave','robot','hardcode','quiet')
CHARACTER_TEXT=('name','faction','lock','pcequip','mwtemplate')
PERSONNEL_FIELDS=('location','official_pilot','enter_lock','lock_result','fail_message','location_ic','hardcode','opaque','going','dark','zombie')


class PilotsSession(ConstructionSession):
    def __init__(self,document):
        document=deepcopy(document)
        options=fields(document.pop('pilots',{}),('root','afterlife','used_store','xploss','in_character','pickup_action','radio_draws','xp','xploss_for_mw','transported_unit_death'))
        from systems.experience import Config
        xp=fields(options.pop('xp',{}),Config.__dataclass_fields__)
        defaults=Config()
        xp={key:(boolean(value) if isinstance(getattr(defaults,key),bool) else number(value,-2147483648,2147483647)) for key,value in xp.items()}
        death_options={key:boolean(options.pop(key,True)) for key in ('xploss_for_mw','transported_unit_death')}
        root=Path(text(options.get('root','./tmp/pilots_characters'))).resolve()
        from data.template_dependency import resolve_catalog
        upstream=resolve_catalog(document.get('construction',{}).get('catalog'))
        if upstream is not None and (root.is_relative_to(upstream.resolve()) or upstream.resolve().is_relative_to(root)):
            raise ValueError('Character storage and upstream template roots overlap')
        self.characters=CharacterStore(root)
        for record in array(document.pop('characters',[])):self.create_character(record)
        self.personnel_inputs={};self.character_inputs={}
        super().__init__(document)
        self.engine.xp_config=Config(**xp)
        for key,value in death_options.items():setattr(self.engine,key,value)
        self.personnel=Personnel(self.engine,self.characters,**{k:(boolean(v) if k=='in_character' else integer(v)) for k,v in options.items() if k not in ('root','radio_draws')})
        self.engine.template_directory=self.directory;self.engine.part_catalog=self.directory.catalog
        self.radio_draws=[integer(v) for v in array(options.get('radio_draws',[]))];self.radio_history=[]
        self.strict_radio='radio_draws' in options
        self.host_radio_source=self.personnel.radio_source
        self.personnel.radio_source=self.radio_source
        self.personnel.units=self.units
        for unit in self.units.values():
            inputs=self.personnel_inputs.get(unit._id,{})
            self.personnel.add(unit,inputs.get('location',unit.mapindex))
            self.configure_personnel(unit,inputs)
        for obj in self.objects.values():self.personnel.add(obj,getattr(obj,'location',-1))
        for ident in self.characters.records:
            actor=self.characters.actor(ident);self.personnel.add(actor,actor.location)
        for name,ident in self.character_inputs.items():self.attach(self.units[name],ident)

    def create_character(self,record):
        fields(record,('id','location','categories','values')+CHARACTER_BOOLS+CHARACTER_TEXT,('id','name'))
        ident=integer(record['id']);name=text(record['name']);metadata={}
        for key,value in record.items():
            if key in ('id','name','values'):continue
            if key in CHARACTER_BOOLS:value=boolean(value)
            elif key in CHARACTER_TEXT:value=text(value)
            elif key=='location':value=integer(value)
            elif key=='categories':value={k:text(v) for k,v in fields(value,('health','attrs','skills','advs')).items()}
            metadata[key]=value
        self.characters.create(ident,name,**metadata)
        for name,value in record.get('values',{}).items():c.set_value(self.characters,ident,name,integer(value))
        return ident

    def add_unit(self,record):
        record=deepcopy(record);personal=record.pop('personnel',{});ident=record.pop('character',None)
        unit=super().add_unit(record)
        self.personnel_inputs[unit._id]=personal
        if ident is not None:self.character_inputs[record['name']]=integer(ident)
        return unit

    def configure_personnel(self,unit,values):
        fields(values,PERSONNEL_FIELDS)
        for key,value in values.items():
            if key in ('location','official_pilot'):value=integer(value)
            elif key in ('enter_lock','fail_message'):value=text(value)
            elif key=='lock_result':
                if value is not None:value=boolean(value)
            else:value=boolean(value)
            if key=='location':self.personnel.move(unit._id,value)
            else:setattr(unit,key,value)

    def attach(self,unit,ident):
        actor=self.characters.actor(ident);unit.pilot=unit.command_actor=actor
        unit.pilot_owner=actor
        return actor

    def radio_source(self):
        if not self.strict_radio:
            channel=self.host_radio_source();self.radio_history.append({'channel':channel,'source':'host-independent'})
            return channel
        if not self.radio_draws:raise ValueError('Emergency radio host-random stream exhausted')
        raw=self.radio_draws.pop(0)
        if raw<0:raise ValueError('Emergency radio raw value must be nonnegative')
        result=raw%1000000;self.radio_history.append({'raw':raw,'channel':result});return result

    def command(self,unit,name,args):
        from systems import occupants as o
        from systems import swarm as b
        if name.lower() in ('swarm','attackleg','hide','jettison','eject','disembark','udisembark','embark','pickup'):
            if not isinstance(args,str):args=' '.join(text(value) for value in array(args))
        if name.lower() in ('swarm','attackleg','hide','jettison'):
            return getattr(b,name.lower())(unit,unit.command_actor,args)
        functions={'eject':o.eject,'disembark':o.disembark,'udisembark':o.unit_disembark,
                   'embark':o.embark,'pickup':o.pickup}
        if name.lower() in functions:
            fn=functions[name.lower()];actor=unit.command_actor
            return fn(unit,actor,args) if name.lower() in ('embark','pickup') else fn(unit,actor)
        return super().command(unit,name,args)

    def action(self,action):
        if not isinstance(action,dict):raise ValueError('action must be an object')
        op=action.get('op')
        try:
            self.initialize_random()
            if op=='pilot_diagnose':
                from tools.pilots_diagnostics import diagnose
                return serialized(self.invoke(diagnose,self,action))
            if op in ('character','character_diagnose','personnel','personal','experience'):
                return serialized(self.invoke(getattr(self,op+'_action'),action))
            if op=='command' and isinstance(action.get('actor'),int):
                action=deepcopy(action);unit=self.unit(action);actor=self.characters.actor(action.pop('actor'))
                previous=unit.command_actor;unit.command_actor=actor
                try:return super().action(action)
                finally:unit.command_actor=previous
            return super().action(action)
        except (ValueError,TypeError,KeyError,IndexError,OSError,OverflowError) as error:return {'ok':False,'error':str(error)}

    def character_action(self,a):
        fields(a,('op','kind','caller','player','target','name','amount','flag','modifier','use_xp','loud','override','promillage','other','other_skill','args','count','record'),('op','kind'))
        kind=a['kind'];caller=integer(a.get('caller',a.get('player',0)));player=integer(a.get('player',caller));name=a.get('name','')
        now=self.engine.sim_now
        if kind in ('get','set','status','clear'):
            return c.control(self.characters,caller,kind,target=a.get('target'),name=name,amount=integer(a.get('amount',0)),flag=integer(a.get('flag',0)),now=now)
        if kind=='create':
            ident=self.create_character(a['record']);self.personnel.add(self.characters.actor(ident),self.characters.actor(ident).location);return ident
        if kind=='reload':
            other=CharacterStore(self.characters.root)
            locations={ident:actor.location for ident,actor in self.characters.actors.items()}
            self.characters.records=other.records;self.characters.cache=None
            for ident in self.characters.records:
                actor=self.characters.actor(ident)
                if ident not in self.personnel.objects:self.personnel.add(actor,actor.location)
                elif locations.get(ident)!=actor.location:
                    previous=self.personnel.members.get(locations.get(ident),[])
                    if ident in previous:previous.remove(ident)
                    self.personnel.members.setdefault(actor.location,[]).append(ident)
            return True
        if kind=='save':
            for ident in self.characters.records:self.characters.persist(ident)
            return True
        if kind=='list':return c.char_list(self.characters,text(name),a.get('target',player if 'player' in a else None),caller=caller)
        if kind=='values':return c.list_values(integer(a.get('flag',-1)),store=self.characters,caller=caller)
        if kind=='lookup':return self.characters.lookup(caller,text(name))
        if kind=='duration':return c.duration(integer(a.get('amount',0)))
        if kind=='threshold':return c.threshold_control(self.characters,text(a.get('args','')),caller=caller)
        if kind=='getthreshold':return c.get_threshold(self.characters,name)
        if kind=='top':return c.xp_top(self.characters,text(name),caller=caller)
        if kind=='gain':return c.gain_xp(self.characters,player,name,integer(a.get('amount',0)),now=now,override=boolean(a.get('override',False)))
        if kind=='lower':return c.lower_xp(self.characters,player,integer(a.get('promillage',1000)))
        if kind=='next':return c.next_threshold(self.characters,player,name)
        if kind=='target':return c.skill_target(self.characters,player,name,integer(a.get('modifier',0)),boolean(a.get('use_xp',True)))
        if kind=='skill':return c.skill_success(self.characters,player,name,integer(a.get('modifier',0)),boolean(a.get('loud',True)))
        if kind=='margin':return c.skill_margin(self.characters,player,name,integer(a.get('modifier',0)))
        if kind=='opposed':return c.opposed(self.characters,player,name,integer(a['other']),a.get('other_skill',name))
        if kind=='attribute':return {'target':c.attribute_target(self.characters,player,name),'success':c.attribute_success(self.characters,player,name)}
        if kind=='advantage':return c.has_advantage(self.characters,player,name)
        if kind=='dice':return c.roll_dice(text(name),integer(a.get('count',2)))
        raise ValueError('Unknown character operation')

    def character_diagnose_action(self,a):
        fields(a,('op','kind','player','mask','values','xp','last_use','categories','name'),('op','kind','player'))
        ident=integer(a['player']);mask=number(a.get('mask',ALL),0,15,True);kind=a['kind']
        if kind=='categories':
            self.characters.records[ident]['categories'].update({k:text(v) for k,v in fields(a['categories'],('health','attrs','skills','advs')).items()})
            self.characters.persist(ident)
            return deepcopy(self.characters.records[ident]['categories'])
        stats=self.characters.retrieve(ident,mask)
        if kind=='store':
            for field in ('values','xp','last_use'):
                for name,val in a.get(field,{}).items():
                    index=code(name)
                    if index<0:raise ValueError('Unknown character value')
                    if field=='values':stats.set(index,integer(val))
                    else:getattr(stats,field)[index]=integer(val)
            self.characters.store(ident,stats,mask)
        elif kind=='pack':c.pack_xp(self.characters,ident,stats,code(a['name']));self.characters.store(ident,stats,mask)
        elif kind!='read':raise ValueError('Unknown character diagnostic')
        return dict(values=list(stats.values),xp=list(stats.xp),last_use=list(stats.last_use),dbref=stats.dbref,categories=deepcopy(self.characters.record(ident)['categories']),cache=self.characters.cache)

    def personnel_action(self,a):
        fields(a,('op','kind','unit','player','origin','destination','flags','values','amount'),('op','kind'))
        from systems.occupants import tele_contents,discard_mw,enter_mw_bay,kill_contents
        kind=a['kind']
        if kind=='transfer':return tele_contents(self.engine,integer(a['origin']),integer(a['destination']),integer(a.get('flags',0)))
        unit=self.unit(a);actor=self.characters.actor(integer(a['player'])) if 'player' in a else unit.pilot
        if kind=='attach':self.attach(unit,actor._id);return True
        if kind=='caller':unit.command_actor=actor;return True
        if kind=='configure':self.configure_personnel(unit,a['values']);return True
        if kind=='initialize':
            from systems.personal_damage import initialize_pc
            initialize_pc(actor,unit,self.directory.catalog);return True
        if kind=='discard':discard_mw(unit);return True
        if kind=='enter_bay':return enter_mw_bay(unit,integer(a['destination']))
        if kind=='kill_contents':return kill_contents(unit)
        from systems import piloting
        if kind=='fix_health':piloting.fix_pilotdamage(unit,actor);return unit.pilot_hits
        if kind=='consciousness_target':return piloting.mw_ic_bth(unit)
        if kind in ('head','lethal'):
            fn=piloting.head_hit_mw_damage if kind=='head' else piloting.mw_lethal_damage
            fn(unit,None,integer(a.get('amount',1)));return unit.pilot_hits
        raise ValueError('Unknown personnel operation')

    def personal_action(self,a):
        fields(a,('op','kind','unit','weapon','location','amount','id'),('op','kind','amount'))
        from entities.weapon import get_weapon
        from systems import personal_damage as p
        unit=self.unit(a);weapon=get_weapon(text(a['weapon'])) if a.get('weapon') else None
        if a.get('weapon') and weapon is None:raise ValueError('Unknown weapon')
        amount=integer(a['amount']);kind=a['kind']
        if kind=='to_normal':return p.personal_to_damage(unit,weapon,amount)
        if kind=='to_personal':return p.damage_to_personal(unit,weapon,amount)
        loc=number(a.get('location',4),0,7,True)
        if kind=='location':return p.personal_location(loc)
        if kind=='armor':return p.personal_armor_effect(unit,weapon,loc,amount,integer(a.get('id',-1)))
        raise ValueError('Unknown personal combat operation')

    def experience_action(self,a):
        fields(a,('op','kind','unit','target','player','reason','addanyway','modifier','weapon','damage','multiplier','bth','config','weapon_fields'),('op','kind'))
        from systems import experience as x
        from entities.weapon import get_weapon
        kind=text(a['kind'])
        if kind=='configure':
            values=fields(a['config'],x.Config.__dataclass_fields__)
            for key,value in values.items():
                setattr(self.engine.xp_config,key,boolean(value) if isinstance(getattr(x.Config(),key),bool) else number(value,-2147483648,2147483647))
            return dict(vars(self.engine.xp_config))
        unit=self.unit(a) if 'unit' in a else None
        actor=self.characters.actor(integer(a['player'])) if 'player' in a else unit.pilot if unit else None
        reason=integer(a.get('reason',1))
        if kind in ('tech','techweapons'):return x.tech(actor,unit,reason,weapons=kind=='techweapons',now=self.engine.sim_now)
        if kind=='computer':return x.computer(actor,unit,reason)
        if kind=='comm':return x.comm(actor,unit)
        if kind=='piloting':return x.piloting(actor,unit,reason,boolean(a.get('addanyway',False)))
        if kind=='perception':return x.perception(unit,integer(a.get('modifier',0)))
        if kind in ('spot','artillery','gun'):
            target=self.units[text(a['target'])]
            if kind!='gun':return getattr(x,kind)(actor,unit,target)
            weapon=get_weapon(text(a['weapon']))
            if weapon is None:raise ValueError('Unknown weapon')
            if 'weapon_fields' in a:
                from dataclasses import replace
                from entities.weapon import WeaponType
                inputs=fields(a['weapon_fields'],('bv','vrt','weapon_type'))
                values={key:(WeaponType(number(value,integer=True)) if key=='weapon_type' else
                        number(value,0,integer=key=='bv')) for key,value in inputs.items()}
                weapon=replace(weapon,**values)
            return x.gun(actor,unit,target,integer(a.get('damage',0)),integer(a.get('multiplier',1)),weapon,integer(a.get('bth',0)))
        raise ValueError('Unknown experience operation')

    def _snapshot(self):
        result=super()._snapshot()
        # Raw categories are observed without lazy retrieval or BTH-cache effects.
        result['characters']={str(i):deepcopy(rec) for i,rec in self.characters.records.items()}
        result['character_cache']=self.characters.cache
        result['character_external_effects']=deepcopy(getattr(self.characters,'external_effects',[]))
        result['personnel']={'contents':{str(k):list(v) for k,v in self.personnel.members.items()},'trace':deepcopy(self.personnel.trace),'radio':deepcopy(self.radio_history)}
        for name,unit in self.units.items():
            result['units'][name]['infantry_specials']=int(unit.infantry_specials)
            result['units'][name]['personnel']={k:getattr(unit,k,None) for k in PERSONNEL_FIELDS}
            result['units'][name]['xp_requests']=deepcopy(getattr(unit,'xp_requests',[]))
        return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input');args=parser.parse_args(argv)
    try:
        with open(args.input) if args.input else sys.stdin as source:document=json.load(source,object_pairs_hook=unique_fields,parse_constant=reject_constant)
        session=PilotsSession(document);results=[session.action(a) for a in document['actions']]
        print(json.dumps(dict(results=results,state=session.snapshot(),draws=session.draws),allow_nan=False))
    except (ValueError,TypeError,KeyError,IndexError,OSError,OverflowError) as error:
        print(json.dumps({'ok':False,'error':str(error)}),file=sys.stderr);return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
