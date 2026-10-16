# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.c3.c
#   btech/mech.c3i.c
#   btech/mech.notify.c

"""C3 networks, radio and occupant inboxes; see docs/communications-cli.md."""
import argparse
from copy import deepcopy
import json
import sys

from tools.pilots import PilotsSession
from tools.construction_templates import text
from tools.core_simulation import serialized
from tools.combat_resolution import unique_fields, reject_constant
from tools.movement_inputs import fields, number, boolean, array
from systems import c3, communications as radio, notifications as notice, network_reports as reports

SCALARS = ('radio_type','radio_range','comm','comm_last','autopilot','last_use','specials','specials2','crit_status',
           'status','status2','working_c3_masters','total_c3_masters','mapindex','tank_crit_status','stagger_damage')


class CommunicationsSession(PilotsSession):
    def __init__(self, document):
        self.communication_inputs = {}
        super().__init__(document)
        for name, values in self.communication_inputs.items():
            self.configure_communications(self.units[name], values)

    def add_unit(self, record):
        record = deepcopy(record)
        values = record.pop('communications', {})
        unit = super().add_unit(record)
        self.communication_inputs[record['name']] = values
        return unit

    def configure_communications(self, unit, values):
        fields(values, SCALARS + ('freq','freqmodes','chantitle','c3_network','c3_network_size','c3i_network','c3i_network_size',
                                 'aero_turrets','allocated','faction','map_ic'))
        for key, value in values.items():
            if key in SCALARS or key.endswith('_size'):
                value = number(value, -2147483648, 2147483647, True)
            elif key in ('allocated','map_ic'):
                value = boolean(value)
            elif key == 'faction':
                value = text(value)
            elif key == 'chantitle':
                value = [text(v) for v in array(value)]
            else:
                value = [self.units[v]._id if isinstance(v,str) else number(v,integer=True) for v in array(value)]
            if key == 'aero_turrets' and len(value) > notice.NUM_TURRETS:
                raise ValueError('Aerospace supports exactly three turret slots')
            if key == 'map_ic':
                if unit.map is None:
                    raise ValueError('map_ic requires a map')
                unit.map.in_character = value
            else:
                setattr(unit,key,value)
        radio.channels(unit)

    def command(self, unit, name, args):
        name = name.lower()
        command_text = args if isinstance(args,str) else ' '.join(str(v) for v in array(args))
        actor = unit.command_actor
        if name == 'hulldown':
            from systems.movement_commands import hulldown
            accepted,message = hulldown(self.engine,unit,command_text,actor)
            return dict(accepted=accepted,message=message)
        network = {'c3':('join',True),'c3message':('message',True),'c3targets':('targets',True),'c3network':('network',True),
                   'c3i':('join',False),'c3imessage':('message',False),'c3itargets':('targets',False),'c3inetwork':('network',False)}
        if name in network:
            action,ordinary = network[name]
            return c3.command(unit,actor,action,command_text,ordinary)
        setters = {'setchannelfreq':radio.set_frequency,'setchanneltitle':radio.set_title,'setchannelmode':radio.set_mode}
        if name in setters:
            result = (radio.set_frequency(unit,command_text,actor) if name == 'setchannelfreq'
                      else setters[name](unit,command_text))
        elif name in ('listfreqs','listchannels'):
            rows = radio.list_frequencies(unit)
            for row in rows: notice.personal_notify(actor,row)
            return dict(ok=True,rows=rows)
        elif name == 'sendchannel':
            result = radio.send_channel(unit,actor,command_text)
        elif name == 'radio':
            result = radio.directed_radio(unit,actor,command_text)
        else:
            return super().command(unit,name,args)
        message = result.get('message',result.get('error'))
        if message and not result.get('notified',False):
            notice.personal_notify(actor,message)
        return result

    def action(self, action):
        if not isinstance(action,dict) or action.get('op') != 'communications_diagnose':
            return super().action(action)
        try:
            self.initialize_random()
            return serialized(self.invoke(self.diagnose,action))
        except (ValueError,TypeError,KeyError,IndexError,OSError,OverflowError) as error:
            return dict(ok=False,error=str(error))

    def diagnose(self, a):
        fields(a, ('op','kind','unit','target','ordinary','values','propagate','index','section','slot','message','audience',
                   'flags','actor','distance','reference','x','y','z','radius','dimensions','mode','weapon','spaces','level',
                   'sender_range','receiver_range','title','bth','ecm','digital','chance','edges','recursive','frequency','team','observer','check_ecm','check_started','check_unconscious','null_unit','null_viewer','null_target','arc','source_id','format_args'), ('op','kind'))
        kind = text(a['kind'])
        unit = self.unit(a)
        target = self.units[text(a['target'])] if 'target' in a else None
        ordinary = boolean(a.get('ordinary',True))
        message = text(a.get('message',''))
        def n(key, default=0):return number(a.get(key,default),integer=True)
        if kind == 'configure':
            self.configure_communications(unit,a['values'])
            return True
        if kind == 'network':
            return self.network_snapshot(unit,ordinary)
        if kind == 'validate':
            c3.validate(unit,ordinary)
            return self.network_snapshot(unit,ordinary)
        if kind == 'clear':
            c3.clear(unit,ordinary,boolean(a.get('propagate',True)))
            return self.network_snapshot(unit,ordinary)
        if kind == 'remove':c3.remove(unit,target._id,ordinary);return True
        if kind == 'replicate':c3.replicate(unit,target,ordinary);return True
        if kind == 'add':c3.add(unit,target,ordinary);return True
        if kind == 'free':return c3.free_position(unit,target,ordinary)
        if kind == 'temporary':return c3.temporary(unit,ordinary,boolean(a.get('check_ecm',True)),boolean(a.get('check_started',True)),boolean(a.get('check_unconscious',False)))
        if kind in ('temp-member','other-member'):
            peer = (c3.temp_member(unit,c3.slots(unit,ordinary),c3.network_size(unit,ordinary),n('index')) if kind == 'temp-member'
                    else c3.other(unit,n('index'),ordinary,boolean(a.get('check_ecm',False)),boolean(a.get('check_started',False)),boolean(a.get('check_unconscious',False))))
            return None if peer is None else peer._id
        if kind == 'move-label':return reports.move_type(unit.move_type)
        if kind == 'arc-label':return reports.arc_label(unit,n('arc'))
        if kind == 'slot-letters':return dict(ammo=reports.slot_ammo_letter(unit,n('section'),n('slot')),fire=reports.slot_fire_letter(unit,n('section'),n('slot')))
        if kind == 'percentages':return dict(armor=reports.remaining_percent(unit),internal=reports.remaining_percent(unit,False))
        if kind == 'masters':
            from systems.criticals import count_working_c3_masters,count_total_c3_masters
            return dict(working=count_working_c3_masters(unit),total=count_total_c3_masters(unit))
        if kind == 'master-window':return c3.part_of_working_master(unit,n('section'),n('slot'))
        if kind == 'range':
            return c3.range_query(unit,target,number(a['distance']),ordinary,n('reference',-1))
        if kind == 'network-visibility':return c3.seen_by_network(unit,target,ordinary)
        if kind == 'flags':return reports.show_flags(unit,n('spaces'),n('level'))
        if kind == 'status':return reports.status_char(unit,target,n('index',1))
        if kind == 'reports':return dict(targets=reports.targets(unit,ordinary),network=reports.network_data(unit,ordinary))
        if kind == 'identity':
            if boolean(a.get('null_viewer',False)) or boolean(a.get('null_target',False)):
                return notice.identity(None if a.get('null_viewer') else unit,None if a.get('null_target') else target)
            subject = target if target is not None else unit
            original = subject._id
            try:
                subject._id = n('source_id',original)
                return notice.identity(unit,target) if target else notice.unit_identity(unit)
            finally:
                subject._id = original
        if kind == 'color':return radio.color_code(unit,n('index'),boolean(a.get('observer',False)),n('team'))
        if kind in ('notify','printf'):
            original = unit._id
            try:
                unit._id = n('source_id',original)
                return (notice.mech_printf(unit,n('audience',2),message,*array(a.get('format_args',[]))) if kind == 'printf'
                        else notice.mech_notify(unit,n('audience',2),message))
            finally:
                unit._id = original
        if kind == 'map-broadcast':notice.map_broadcast(unit.map,message);return True
        if kind == 'mech-broadcast':notice.map_broadcast(unit.map,message,unit,target);return True
        if kind == 'limited-broadcast':return notice.limited_broadcast(unit.map,number(a['x']),number(a['y']),number(a.get('z',0)),number(a['radius']),message,n('dimensions',3))
        if kind == 'hex-broadcast':notice.hex_broadcast(unit.map,n('x'),n('y'),message);return True
        if kind == 'los-broadcast':
            from systems.sensors import los_broadcast
            los_broadcast(unit,message);return True
        if kind == 'pair-broadcast':notice.pair_los_broadcast(unit,target,message);return True
        if kind == 'common-checks':
            actor = self.characters.actor(n('actor')) if 'actor' in a else unit.command_actor
            return radio.common_checks(None if boolean(a.get('null_unit',False)) else unit,actor,n('flags'))
        if kind == 'route':return radio.find_comm_link(unit.map,unit,target,n('frequency'),boolean(a.get('recursive',False)))
        if kind == 'route-graph':return radio.route_graph(array(a['edges']),boolean(a.get('recursive',False)))
        if kind == 'scramble':return radio.scramble_message(message,n('distance'),n('sender_range'),n('receiver_range'),text(a.get('title','')),n('bth'),boolean(a.get('ecm',False)),n('digital'))
        if kind == 'scramble-bytes':return radio.do_scramble(message,n('chance'),n('bth'))
        if kind == 'transmit':return radio.transmit(unit,n('index'),message)
        if kind == 'ammo':
            from entities.weapon import get_weapon
            weapon = get_weapon(text(a['weapon']))
            if weapon is None:raise ValueError('Unknown weapon')
            return dict(description=reports.ammo_description(weapon,n('mode')),letter=reports.ammo_letter(weapon,n('mode')))
        if kind == 'fire-letter':return reports.fire_letter(n('mode'))
        if kind == 'debug':return c3.debug(message)
        raise ValueError('Unknown communications diagnostic')

    def network_snapshot(self, unit, ordinary):
        size = c3.network_size(unit,ordinary)
        return dict(size=size,slots=c3.slots(unit,ordinary),peers=c3.slots(unit,ordinary)[:max(0,size)])

    def _snapshot(self):
        state = super()._snapshot()
        state['external_notification_requests'] = [dict(request) for obj in self.personnel.objects.values()
                                                    for request in getattr(obj,'notification_requests',[])]
        state['inboxes'] = {str(i):list(getattr(obj,'inbox',[])) for i,obj in self.personnel.objects.items()}
        for name,unit in self.units.items():
            radio.channels(unit)
            state['units'][name]['communications'] = dict(c3=self.network_snapshot(unit,True),c3i=self.network_snapshot(unit,False),
                freq=list(unit.freq),freqmodes=list(unit.freqmodes),chantitle=list(unit.chantitle),radio_type=getattr(unit,'radio_type',0),
                comm=getattr(unit,'comm',0),comm_last=getattr(unit,'comm_last',0),autopilot=getattr(unit,'autopilot',-1))
        return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input')
    args = parser.parse_args(argv)
    try:
        with open(args.input) if args.input else sys.stdin as source:
            document = json.load(source,object_pairs_hook=unique_fields,parse_constant=reject_constant)
        session = CommunicationsSession(document)
        results = [session.action(a) for a in document['actions']]
        print(json.dumps(dict(results=results,state=session.snapshot(),draws=session.draws),allow_nan=False))
    except (ValueError,TypeError,KeyError,IndexError,OSError,OverflowError) as error:
        print(json.dumps(dict(ok=False,error=str(error))),file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
