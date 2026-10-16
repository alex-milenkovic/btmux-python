"""Technician gates, parsing, clocks and finite source dice."""
import re
from . import check,attempt,command,gun,skill,invoke,U,M,S,F,A,C,Specials,i2ammo,get_weapon,set_value
from core.events import EventType as E
from systems.technician import parse_part,parse_gun,valid_gun_position,weapon_difficulty
from systems.weapon_inventory import weapon_crits


def run(w,initial,operation):
    u=w['u'];actor=w['actor'];tech=w['tech'];jobs=w['jobs'];e=w['engine'];inv=w['inventory']
    if initial.startswith(('Tech ','IC ')):
        actor.tech='Tech false' not in initial;actor.wizard='Wiz true' in initial
        u.repair_stall='stall false' not in initial;u.in_character=initial.startswith('IC true')
        if 'DS ' in initial and 'nonDS' not in initial:u.unit_type=U.DS
        if 'startup true' in initial:e.schedule_event(60,E.STARTUP,lambda event:None,u)
        if 'started true' in initial:u.status|=S.STARTED
        if 'limitedrepairs 1' in initial:tech.config.limitedrepairs=1
        pending=re.search(r'pending minutes (\d+)',initial)
        if pending:inv.put(7,'TECHTIME',str(e.sim_now+int(pending[1])*60))
        match=re.search(r'pending minutes (\d+)',initial)
        if match:inv.put(7,'TECHTIME',str(e.sim_now+int(match[1])*60))
        if operation.startswith('toggletype'):
            slot=u.sections[4].criticals[0];slot.type=i2ammo(get_weapon('IS.LRM-15').index);slot.data=0
            command(w,'toggletype','CT 1 -')
            check(w,'refuse IC wizard gate','simpods' in w['error']);check(w,'fill valid ammo immediately',slot.data>0 and not w['error'])
        elif 'fatigue' in initial or 'pending minutes' in initial and operation.startswith('replacepart'):
            attempt(w,tech.fatigue,actor)
            check(w,'pass fatigue gate',not w['error']);check(w,'refuse fatigue','tired' in w['error'])
        elif operation in ('fixextra','magic'):
            u.sections[4].config|=C.SECTION_FLOODED
            command(w,operation)
            check(w,'immediate existing restoration without dice',not u.sections[4].config&C.SECTION_FLOODED and not w['draws'])
            check(w,'explicit template dependency without invented restoration',w['result'] is False and any('template' in str(x) for x in getattr(u,'external_effects',[])))
        else:
            before=len(inv.writes);attempt(w,tech.gate,actor,u,'D' if operation.startswith('reload') else 'C')
            for label,fragment in (('clearance','clearance'),('startup','starting up'),('started','started up'),('stall','stall')):
                check(w,'refuse '+label,fragment in w['error'])
            check(w,'refuse clearance before dice or writes','clearance' in w['error'] and not w['draws'] and len(inv.writes)==before)
            check(w,'pass shared C gate',not w['error']);check(w,'pass shared D gate',not w['error'])
        return True
    if operation.startswith(('parsepart ','parsegun ','validgun ')):
        if initial.startswith('AERO'):u.unit_type=U.AERO
        if operation.startswith('parsepart '):
            result=parse_part(u,operation[10:],position='rear-aware' not in initial,rear='rear-aware' in initial,extra='optional-extra' in initial)
            w['result']=result;error,loc,pos,extra=result
            check(w,f'location{loc} position{pos}',error==0);check(w,f'location{loc}',error==0)
            check(w,'extra c',extra=='c');check(w,'extra zero',extra==0)
            check(w,f'error {error}',error<0)
        else:
            pos=2 if 'slot3' in initial else 0;weapon=gun(w,2,pos=pos)
            if 'destroyed' in initial:u.sections[4].criticals[pos].firemode=F.DESTROYED_MODE
            if 'recycling' in initial:u.sections[4].criticals[pos].data=5
            if operation.startswith('validgun'):
                result=valid_gun_position(u,4,int(operation.split()[-1])-1);check(w,'true',result);check(w,'false',not result)
            else:
                argument=operation[9:]
                if argument.endswith('OtherPartBrand'):
                    other=next(entry.long for entry in inv.catalog.sorted['long'][1:] if entry.source_part_id!=u.sections[4].criticals[pos].type and ' ' not in entry.long)
                    argument=argument.replace('OtherPartBrand',other)
                result=parse_gun(u,argument,inv.catalog,brand='brand-enabled' in initial);w['result']=result
                check(w,f'error {result[0]}',result[0]<0)
                for label in ('destroyed','recycling'):check(w,'locate '+label+' mount',result[:3]==(0,4,0))
        return True
    match=re.fullmatch(r'now(\d+) TECHTIME (absent|\d+)',initial)
    if match:
        e.sim_now=int(match[1])
        if match[2]!='absent':inv.put(7,'TECHTIME',match[2])
        if operation=='status and pending':
            result=tech.status(actor);pending=tech.pending(actor);w['result']=result
            check(w,('pending' if result['pending'] else 'ready')+f' and {pending} '+('minute' if pending==1 else 'minutes'),True)
        else:
            seconds=tech.add_time(actor,2);w['result']=seconds
            check(w,f'TECHTIME{inv.get(7,"TECHTIME")} and delay{seconds} seconds',True)
        return True
    match=re.fullmatch(r'wall elapsed(\d+) tick(\d+)',initial)
    if match:
        e.sim_now=int(match[1]);e.events.set_tick(int(match[2]));lag=tech.lag();adjusted=tech.lagged(100)
        check(w,f'lag{lag} and adjusted{adjusted} seconds',True);return True
    match=re.fullmatch(r'pending59 seconds base(\d+) minutes success',initial)
    if match:
        inv.put(7,'TECHTIME','59');minutes=int(match[1]);event=w['work'].start(actor,u,43,4,minutes=minutes,explicit=operation.startswith('explicit'))
        check(w,f'updated TECHTIME plus{minutes*60} and due{event.tick} seconds',inv.get(7,'TECHTIME')==str(59+minutes*60));return True
    match=re.fullmatch(r'variable time enabled base(\d+) margin(\d+) mod(\d+)',initial)
    if match:
        base,margin,mod=map(int,match.groups());tech.config.variabletechtime=1;tech.config.techtime_mod=mod
        result=attempt(w,w['work'].variable,base,margin)
        check(w,f'{result} minutes',not w['error']);check(w,'bounded invalid-divisor diagnostic','divisor' in w['error']);return True
    match=re.fullmatch(r'(Mech|Ground|AERO|VTOL|BA|weapon) skill(\d+) diff(\d+) (.*)',initial)
    if match:
        family,target,diff,rest=match.groups();target=int(target);diff=int(diff)
        u.unit_type={'Mech':U.MECH,'Ground':U.VEH_GROUND,'AERO':U.AERO,'VTOL':U.VTOL,'BA':U.BSUIT,'weapon':U.MECH}[family]
        from systems.piloting import find_tech_skill_name
        name='Technician-Weapons' if family=='weapon' else find_tech_skill_name(u);skill(w,target,name)
        u.in_character=rest.endswith(' IC')
        dice=list(map(int,re.search(r'dice([\d,]+)',rest)[1].split(',')))
        if 'aptitude' in rest:set_value(w['characters'],7,'Tech_Aptitude',1);w['streams']['tech_d6']=list(dice)
        else:w['streams']['tech_rolls']=[sum(dice)]
        margin=invoke(w,tech.roll,actor,u,diff,weapons=family=='weapon');w['result']=margin
        xp=getattr(u,'xp_requests',[])
        check(w,'margin0 success and technician XP',margin==0 and bool(xp))
        check(w,'margin-1 failure and no XP',margin==-1 and not xp)
        check(w,'margin1 and aerospace technician XP',margin==1 and bool(xp) and xp[-1]['skill']=='Technician-Aerospace')
        check(w,'margin1 and no XP',margin==1 and not xp)
        check(w,'margin0 and BattleMech technician XP',margin==0 and bool(xp) and xp[-1]['skill']=='Technician-Battlemech')
        check(w,'margin0 from best two dice',margin==0 and [v for n,v in w['draws']]==dice)
        check(w,'margin-4 from both dice',margin==-4 and len(w['draws'])==1);return True
    match=re.fullmatch(r'catalog weapon width(\d+) (fighter|Mech) physical(\d+)( Clan)?',initial)
    if match:
        width,family,physical,clan=match.groups();u.unit_type=U.AERO if family=='fighter' else U.MECH
        weapon=gun(w,int(width));u.specials=Specials.CLAN_TECH if clan else 0
        physical_width=weapon_crits(u,weapon.index);minutes=60*max(1,physical_width//(2 if clan else 1))
        check(w,f'difficulty{weapon_difficulty(weapon)} and {minutes} minutes',physical_width==int(physical));return True
    return False
