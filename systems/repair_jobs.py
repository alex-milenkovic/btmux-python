# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.tech.c
#   btech/mech.tech.commands.c
#   btech/mech.tech.events.c
#   btech/mech.tech.repairs.c
#   btech/mech.tech.saverepair.c

"""Technician jobs on the shared event queue, including source save/load quirks."""
import json
from core.events import SOURCE_EVENT_IDS, very_fake_func
from entities.mech import UnitType as U, FireMode as F, MechStatus as S
from entities.crittypes import weapon2i
from systems import repairs
from systems.technician import unpack, divide
from systems.damage_commands import short_section, section_names
from systems.enhanced_crits import get_split_data, set_part_temp_nuke, get_weap_data
from systems.weapon_inventory import weapon_crits

EVENT_TYPES={value:key for key,value in SOURCE_EVENT_IDS.items() if 43<=value<=58}
CALLBACKS=dict(zip(range(43,59),('repairpart','replacegun','reattach','reload','armor','internal',
    'removesection','removepart','removegun','repairgun','repairpart','mountbomb','unmountbomb',
    'reseal','replacesuit','repairenhcrit')))


def completely_intact_internal(unit):
    return all(section.internal or not section.internal_orig for section in unit.sections)


def gun_slots(unit,loc,pos):
    """Keep the C split-run upper bound, including its nonzero-start quirk."""
    width=weapon_crits(unit,weapon2i(unit.sections[loc].criticals[pos].type))
    primary=list(range(pos,min(12,pos+width)))
    result=[(loc,index) for index in primary]
    if len(primary)<width and unit.unit_type==U.MECH:
        split=get_split_data(unit,loc,pos)
        if split:
            other,start,_=split
            result.extend((other,index) for index in range(start,width-len(primary)))
    return result


def destroy_part(slot):
    slot.firemode=(int(slot.firemode)|int(F.DESTROYED_MODE))&~int(F.BROKEN_MODE|F.DISABLED_MODE|F.DAMAGED_MODE)
    slot.weap_damage_flags=0;set_part_temp_nuke(slot,0)


class RepairJobs:
    def __init__(self,engine,technician,inventory):
        self.engine=engine;self.tech=technician;self.inventory=inventory;self.messages=[]
        engine.repair_jobs=self

    def events(self,unit=None):
        return [event for event in self.engine.events.pending_events(data=unit)
                if event.event_type in EVENT_TYPES.values()]

    def schedule(self,kind,unit,payload,delay,*,callback=None,fake=False):
        unpack(payload)
        if kind not in EVENT_TYPES:raise ValueError('Unsupported repair event type')
        event=self.engine.events.schedule(delay,EVENT_TYPES[kind],very_fake_func if fake else self.execute,unit,payload)
        event.repair_fake=fake;event.repair_callback=callback or CALLBACKS[kind]
        return event

    def count(self,unit,kind,loc,pos=None):
        return sum(SOURCE_EVENT_IDS[e.event_type]==kind and e.data2%16==loc
            and (pos is None or (e.data2//16)%16==pos) for e in self.events(unit))

    def repairing(self,unit,loc,pos):return any(self.count(unit,k,loc,pos) for k in (43,44,46,52,53,54,58))
    def scrapping_part(self,unit,loc,pos):return any(self.count(unit,k,loc,pos) for k in (50,51,55))
    def fixing(self,unit,loc):return bool(self.count(unit,47,loc) or self.count(unit,48,loc))
    def can_scrap_part(self,unit,loc,pos):return not self.repairing(unit,loc,pos)
    def can_scrap_location(self,unit,loc):return not (self.count(unit,43,loc%8) or self.count(unit,46,loc%8) or self.fixing(unit,loc))

    def latest(self,unit):
        return latest_repair_time(self.engine, unit)

    def notice(self,unit,text,even_destroyed=True):
        from systems.notifications import mech_printf, MECHALL
        destroyed=int(unit.status)&int(S.DESTROYED)
        if even_destroyed:unit.status=int(unit.status)&~int(S.DESTROYED)
        try:
            if not (unit.is_unconscious or unit.has_status(S.BLINDED) or unit._id<0):
                self.messages.append(dict(unit=unit._id,text=text))
            mech_printf(unit,MECHALL,'%s',text)
        finally:
            if destroyed:unit.status=int(unit.status)|destroyed

    def execute(self,event):
        unit=event.data;actor,loc,pos,extra=unpack(event.data2);name=event.repair_callback
        if name in ('mountbomb','unmountbomb'):return
        if name in ('armor','internal'):
            section=unit.sections[loc%8];amount=(event.data2%65536//16)%256
            field='internal' if name=='internal' else 'rear' if loc>=8 else 'armor'
            value=getattr(section,field)+1
            if name=='internal':value&=255
            setattr(section,field,min(value,getattr(section,field+'_orig')))
            from systems.construction_weight import invalidate
            invalidate(unit)
            amount-=1
            if amount<0:return
            if amount:
                self.schedule(47 if name=='armor' else 48,unit,actor*65536+loc+amount*16,180 if name=='armor' else 540)
            else:
                label=('rear ' if loc>=8 else '')+('armor' if name=='armor' else 'internal')
                self.notice(unit,f"{section_names(unit)[loc%8]}'s {label} repairs have been finished.")
                if unit.unit_type!=U.MECH and completely_intact_internal(unit):repairs.magic(unit)
            return
        location=section_names(unit)[loc];slot=unit.sections[loc].criticals[pos]
        if name=='removesection':
            if extra<=0:raise ValueError('Invalid section salvage divisor')
            from systems.parts import proper_internal,proper_armor,cargo_part
            from data.construction_catalog import source_id
            sec=unit.sections[loc]
            for part,count in ((proper_internal(unit,complexrepair=False),2*sec.internal//extra),(proper_armor(unit),2*sec.armor//extra),(cargo_part('Electric'),sec.internal//extra)):
                self.inventory.change(self.store_for(unit),source_id(part),0,count)
            repairs.detach(unit,loc);self.notice(unit,f'{location} has been removed.');return
        if name in ('reattach','replacesuit','reseal'):
            if name=='reattach':
                repairs.reattach(unit,loc)
                if completely_intact_internal(unit):repairs.magic(unit)
            elif name=='replacesuit':repairs.replace_suit(unit,loc);repairs.magic(unit)
            else:repairs.reseal(unit,loc)
            verb={'reattach':'reattached','replacesuit':'replaced','reseal':'resealed'}[name]
            self.notice(unit,f'{location} has been {verb}.',name=='reattach');return
        if name in ('removegun','removepart'):
            for where,index in gun_slots(unit,loc,pos) if name=='removegun' else [(loc,pos)]:destroy_part(unit.sections[where].criticals[index])
            if name=='removepart' and unit.unit_type==U.MECH:repairs.magic(unit)
            if extra==2:self.credit_slot(unit,loc,pos)
            verb='removed' if extra==2 else 'removed and scrapped'
        elif name in ('replacegun','repairgun'):
            for where,index in gun_slots(unit,loc,pos):
                repairs.repair_part(unit,where,index)
                if name=='replacegun' and extra:unit.sections[where].criticals[index].brand=extra
            verb='replaced' if name=='replacegun' else 'repaired'
        elif name=='repairenhcrit':
            from systems.status_display import part_name
            self.notice(unit,f'{part_name(unit,loc,pos)} on {location} has been repaired.',False)
            slot.firemode=int(slot.firemode)&~int(F.DAMAGED_MODE);slot.weap_damage_flags=0;set_part_temp_nuke(slot,0)
            _,_,first=get_weap_data(unit,loc,pos)
            set_part_temp_nuke(unit.sections[loc].criticals[first],0);return
        elif name=='repairpart':repairs.repair_part(unit,loc,pos);verb='repaired'
        elif name=='reload':
            if extra:
                slot.data=0
                if extra>1:self.credit_slot(unit,loc,pos)
            else:repairs.fill_part_ammo(unit,loc,pos)
            verb='unloaded' if extra else 'reloaded'
        else:raise ValueError('Unsupported repair callback')
        from systems.status_display import part_name
        partname=part_name(unit,loc,pos)
        preposition='from' if name in ('removegun','removepart') else 'on'
        self.notice(unit,f'{partname} {preposition} {location} has been {verb}.')

    def store_for(self,unit):
        bays=getattr(unit,'aero_bays',[])
        return bays[0] if unit.unit_type in (U.DS,U.SPHEROID_DS) and bays else unit.location

    def credit_slot(self,unit,loc,pos):
        from systems.repair_materials import find_ammo_type,repair_alias
        slot=unit.sections[loc].criticals[pos]
        self.inventory.change(self.store_for(unit),repair_alias(unit,find_ammo_type(unit,loc,pos)),slot.brand&15,1)

    def describe(self,event):
        from systems.status_display import part_name
        actor,loc,pos,extra=unpack(event.data2);kind=SOURCE_EVENT_IDS[event.event_type]
        place=short_section(event.data,loc%8)+('(R)' if loc>=8 else '')
        fake=event.repair_fake
        descriptions={43:'Replacement',44:'Replacement',45:'Reattachment',46:'Unload' if extra else 'Reload',
            47:'Failed armor repair' if fake else 'Repair of armor - possibly next point',
            48:'Failed internal repair' if fake else 'Repair of internals - possibly next point',
            49:'Removal',50:'Scrapping',51:'Scrapping',52:'Repair',53:'Repair',54:'Mounting',55:'Removing',56:'Reseal',57:'Replacing suit',58:'Repair'}
        description=descriptions[kind]
        section_only=kind in (45,49,56,57)
        if not section_only and kind not in (47,48):
            description+=' of '+part_name(event.data,loc,pos)
        if fake and kind not in (47,48,49,50,51):description+=' (Failure)'
        if kind==57:description+=f'{place:>5} Reseal'+(' (Failure)' if fake else '')
        position=None if section_only else (0 if fake else pos) if kind in (47,48) else pos+1
        minutes=self.tech.lagged(divide(event.tick-self.engine.tick,60))
        location=f'{place:>5}'+('' if section_only else f':{position:<2}')
        text=f'{actor:<5} {minutes:<4} {location} {description}'
        return dict(type=kind,actor=actor,location=place,position=position,minutes=minutes,fake=fake,description=description,text=text)

    def report(self,unit):return [self.describe(e) for e in sorted(self.events(unit),key=lambda e:(SOURCE_EVENT_IDS[e.event_type],-e.event_id))]

    def show_report(self,actor,unit):
        from systems.status_display import menu_lines
        from systems.character_display import menu
        from systems.notifications import unit_identity
        if not self.latest(unit):raise ValueError("This 'mech has no repairs pending!")
        rows=self.report(unit)
        lines=menu_lines(f'Repairs/Scrapping in progress ({unit_identity(unit)})',[row['text'] for row in rows],
                         subtitle=f"{'Plr':<5} {'Time':<4} Location + Description")
        lines+=menu([('Note: Time = Time remaining in minutes. Plr = Tech\'s dbref',1),(None,1)])
        for line in lines:self.tech.notice(actor,line)
        return rows

    def save(self):
        """Stable local JSON lines; deliberately not the C ABI-dependent binary."""
        rows=[]
        for event in sorted(self.events(),key=lambda e:(SOURCE_EVENT_IDS[e.event_type],-e.event_id)):
            remaining=max(1,event.tick-self.engine.tick)*(-1 if event.repair_fake else 1)
            rows.append([event.data._id,SOURCE_EVENT_IDS[event.event_type],remaining,event.data2])
        return ''.join(json.dumps(row)+'\n' for row in rows+[[-1]])

    def load(self,text):
        from core.events import source_event_type
        from core.effects import diagnostic
        loaded=skipped=examined=0;error=None
        for line in text.splitlines():
            try:
                row=json.loads(line)
                if isinstance(row,list) and row and type(row[0]) is int and row[0]<=0:break
                if not isinstance(row,list) or len(row)!=4 or any(type(v) is not int for v in row):raise ValueError('Truncated or invalid repair record')
                identity,kind,remaining,payload=row;examined+=1;unpack(payload)
                unit=self.inventory.objects.get(identity)
                if unit is None or not hasattr(unit,'sections'):raise ValueError('Invalid repair unit reference')
                if remaining<0:
                    if kind in EVENT_TYPES:self.schedule(kind,unit,payload,abs(remaining),fake=True)
                    else:
                        event=self.engine.events.schedule(abs(remaining),source_event_type(kind),very_fake_func,unit,payload)
                        event.repair_fake=True;event.repair_callback=None
                    loaded+=1
                    continue
                if kind not in EVENT_TYPES or kind==56:skipped+=1;continue
                self.schedule(kind,unit,payload,remaining);loaded+=1
            except (ValueError,TypeError) as exc:
                error=str(exc);break
        if examined and error is None:diagnostic(self.engine,f'LOADED: {examined} tech events.\n')
        return dict(loaded=loaded,skipped=skipped,error=error)


def latest_repair_time(engine, unit):
    """figure_latest_tech_event, including restored events without a jobs adapter."""
    latest = 0
    for event in engine.events.pending_events(data=unit):
        kind = SOURCE_EVENT_IDS.get(event.event_type, -1)
        if not 43 <= kind <= 58:
            continue
        remaining = event.tick - engine.tick
        if kind in (47, 48):
            remaining += ((event.data2 % 65536) // 16 - 1) * (180 if kind == 47 else 540)
        latest = max(latest, remaining)
    return latest
