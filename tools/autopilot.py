"""Built-in Battlesheep JSON/stdio session; see docs/autopilot-cli.md."""
import argparse
from copy import deepcopy
import json
import sys
from tools.hud_status import DisplaySession
from tools.core_simulation import serialized
from tools.combat_resolution import unique_fields, reject_constant
from tools.movement_inputs import fields, number, boolean, array, string
from entities.autopilot import Autopilot
from systems import autopilot_core as controller
from systems import autopilot_storage as storage

CONTROL_COMMANDS = {
    'aiaddcommand':controller.auto_addcommand,
    'aidelcommand':controller.auto_delcommand,
    'aiengage':controller.auto_engage,
    'aidisengage':controller.auto_disengage,
    'ailistcommands':controller.auto_listcommands,
    'aijump':controller.auto_jump,
    'aieventstats':controller.auto_eventstats}


class AutopilotSession(DisplaySession):
    def __init__(self,document):
        document = deepcopy(document)
        records = array(document.pop('autopilots',[]))
        self.autopilots = {}
        super().__init__(document)
        self.initialize_random()
        for record in records:
            fields(record,('name','id','unit','commands','engage'),('name','id','unit'))
            name = string(record['name'])
            ident = number(record['id'],1,2147483647,True)
            unit = self.units[string(record['unit'])]
            if (name in self.autopilots or name in self.objects or ident in self.personnel.objects
                or any(getattr(o,'_id',None) == ident for o in self.engine.get_entities())
                or any(a.location == unit._id for a in self.autopilots.values())):
                raise ValueError('Duplicate controller identity or attachment')
            commands = [string(s) for s in array(record.get('commands',[]))]
            a = controller.auto_newautopilot(self.engine,ident,unit)
            a.name = name
            self.autopilots[name] = a
            self.personnel.add(a,unit._id)
            for command in commands:
                result = self.invoke(controller.auto_addcommand,a,a,command)
                if not result['ok']:
                    raise ValueError(result['error'])
            if boolean(record.get('engage',True)):
                self.invoke(controller.auto_engage,a,a,'')

    def command(self,unit,name,args):
        name = name.lower()
        text = args if isinstance(args,str) else ' '.join(map(str,array(args)))
        if name in CONTROL_COMMANDS:
            a = next((a for a in self.autopilots.values() if a.location == unit._id and a.allocated),None)
            if a is None:
                return dict(ok=False,error='No controller attached to this unit')
            return CONTROL_COMMANDS[name](unit.command_actor,a,text)
        if name == 'snipe':
            from systems.autopilot_ai import mech_snipe
            return mech_snipe(unit.command_actor,unit,text)
        return super().command(unit,name,args)

    def action(self,action):
        if isinstance(action,dict) and action.get('op') in ('ai_save','ai_load'):
            try:
                fields(action,('op','file'),('op','file'))
                path = self.path(string(action['file']))
                if action['op'] == 'ai_save':
                    data = storage.save_snapshot(self.engine,list(self.autopilots.values()))
                    path.write_text(json.dumps(data,allow_nan=False,indent=2),encoding='utf-8')
                else:
                    data = json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique_fields,parse_constant=reject_constant)
                    prospective = {}
                    def preflight(candidates):
                        old_names = {a._id:name for name,a in self.autopilots.items()}
                        prospective.update((name,a) for name,a in self.autopilots.items()
                                           if a._id not in candidates)
                        for ident,a in candidates.items():
                            name = old_names.get(ident,a.name)
                            if name in prospective or name in self.objects:
                                raise ValueError('Duplicate public controller name: '+name)
                            prospective[name] = a
                    storage.load_snapshot(self.engine,data,preflight=preflight)
                    self.autopilots = prospective
                return dict(ok=True,controllers=len(data['controllers']),events=len(data['events']))
            except (ValueError,TypeError,KeyError,IndexError,OSError,OverflowError) as error:
                return dict(ok=False,error=str(error),error_kind='invalid-input')
        return super().action(action)

    def snapshot(self):
        result = super().snapshot()
        result['autopilots'] = {name:dict(
            id=a._id,unit=next((name for name,u in self.units.items() if u is a.mymech),None),
            values={key:getattr(a,key) for key in Autopilot.state_fields},
            commands=[list(node.args) for node in a.commands or ()],
            path=None if a.astar_path is None else [[node.x,node.y] for node in a.astar_path],
            weapons=None if a.weaplist is None else [dict(number=n.weapon_number,index=n.weapon_db_number,
                section=n.section,critical=n.critical,scores=list(n.range_scores)) for n in a.weaplist],
            profiles=[None if p is None else [[score,node.weapon_number] for score,node in sorted(p.items())] for p in a.profile],
            inbox=list(a.inbox),events=[dict(kind=e.event_type.name,deadline=e.tick,callback=e.callback.__name__,data=e.data2)
                                      for e in self.engine.events.pending_events(data=a)])
            for name,a in self.autopilots.items()}
        return serialized(result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input')
    args = parser.parse_args(argv)
    try:
        with open(args.input,encoding='utf-8-sig') if args.input else sys.stdin as source:
            document = json.load(source,object_pairs_hook=unique_fields,parse_constant=reject_constant)
        session = AutopilotSession(document)
        results = [session.action(action) for action in document['actions']]
        print(json.dumps(dict(results=results,state=session.snapshot(),draws=session.draws),allow_nan=False))
    except (ValueError,TypeError,KeyError,IndexError,OSError,OverflowError) as error:
        print(json.dumps(dict(ok=False,error=str(error),error_kind='invalid-input')),file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

