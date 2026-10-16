# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.tech.c
#   btech/mech.tech.commands.c

"""Technician access, source parsers, skill rolls and absolute work timestamps."""
from dataclasses import dataclass
import math
import random
import re
from core.events import EventType
from core.randomness import draw,roll
from entities.mech import UnitType as U
from entities.crittypes import crits_in_loc
from systems.damage_commands import armor_section_from_string
from data.templates import parse_attributes
from systems.notifications import personal_notify


def atoi(text):
    """C decimal-byte prefix; keep other subsystems' diagnostic parsers intact."""
    match = re.match(r'[ \t\n\r\v\f]*([+-]?)([0-9]+)', str(text))
    if not match:
        return 0
    digits = match[2].lstrip('0') or '0'
    return (-1 if match[1] == '-' else 1) * int(digits)


def divide(a,b):
    if not b:raise ValueError('Invalid zero divisor')
    return (abs(a)//abs(b))*(-1 if (a<0)!=(b<0) else 1)


def pack(actor,loc,pos=0,extra=0):
    if not (0<=actor<=32767 and 0<=loc<16 and 0<=pos<16 and 0<=extra<256):raise ValueError('Repair payload outside supported integer range')
    return actor*65536+loc+pos*16+extra*256


def unpack(value):
    if type(value) is not int or not 0<=value<=2147483647:raise ValueError('Repair payload outside supported integer range')
    return value//65536,value%16,(value//16)%16,(value//256)%256


def parse_part(unit,text,*,position=True,extra=False,rear=False):
    args=parse_attributes(text,4);argc=len(args)
    if not argc or argc>2+bool(extra):return -1,0,0,0
    if not rear:
        required=1+bool(position)
        if argc<required or argc>required+bool(extra):return -1,0,0,0
    elif argc==2 and args[1][0].upper()!='R':return -1,0,0,0
    loc=armor_section_from_string(unit,args[0])
    if loc<0:return -1,0,0,0
    if rear and argc==2:loc+=8
    pos=atoi(args[1])-1 if position and argc>1 else 0
    if position and (argc<2 or not 0<=pos<crits_in_loc(unit,loc%8)):return -2,loc,pos,0
    return 0,loc,pos,args[2][0] if extra and argc>2 else 0


def parse_gun(unit,text,catalog,*,brand=False):
    from systems.weapon_inventory import numbered_weapon
    from data.construction_catalog import source_id
    args=parse_attributes(text,3);argc=len(args)
    if not 1<=argc<=2+bool(brand):return -1,0,0,0
    if argc==2+bool(brand) or brand and argc==2 and atoi(args[1]):
        loc=armor_section_from_string(unit,args[0]);pos=atoi(args[1])-1
        if loc<0:return -1,0,0,0
        if not 0<=pos<crits_in_loc(unit,loc):return -4,loc,pos,0
    else:
        if not '0'<=args[0][0]<='9':return -1,0,0,0
        run=numbered_weapon(unit,atoi(args[0]))
        if run is None:return -1,0,0,0
        loc,pos=run.section,run.critical
    selected=unit.sections[loc].criticals[pos]
    result=selected.brand&15
    if brand and argc>1 and not atoi(args[-1]):
        match=catalog.match('long',args[-1],0)
        if match is None:return -2,loc,pos,0
        if match['source_part_id']!=source_id(selected.type):return -3,loc,pos,0
        result=match['brand']
    return 0,loc,pos,result


def valid_gun_position(unit,loc,pos):
    from systems.weapon_inventory import find_weapons
    return any(run.critical==pos for run in (find_weapons(unit,loc) or []))


def variable_minutes(base,margin,enabled=False,modifier=0):
    if margin<0:return base*3//2
    if not enabled or margin==0:return base
    denominator=100-modifier*margin
    if denominator<=0:raise ValueError('Invalid variable-time divisor')
    inner=1000//denominator
    if not inner:raise ValueError('Invalid variable-time divisor')
    return base*10//inner


def weapon_difficulty(weapon):return int(math.sqrt(weapon.crits*1.5-1.1))


@dataclass
class Config:
    limitedrepairs:int=0
    maxtechtime:int=600
    variabletechtime:int=0
    techtime_mod:int=0


class Technician:
    def __init__(self,engine,inventory,config=None):
        self.engine=engine;self.inventory=inventory;self.config=config or Config()
        self.restart=0;self.messages=[];self.rolls=[]
        engine.technician=self

    def notice(self,actor,text):
        self.messages.append(dict(actor=actor._id,text=text));personal_notify(actor,text)

    def timestamp(self,actor):return max(self.engine.sim_now,atoi(str(self.inventory.get(actor._id,'TECHTIME','0'))))
    def pending(self,actor):return (self.timestamp(actor)-self.engine.sim_now)//60
    def lag(self):return divide(100*(self.engine.sim_now-self.restart),self.engine.tick)-100 if self.engine.tick else 0
    def lagged(self,seconds):return divide((100+self.lag())*seconds,100)

    def status(self,actor,data=0):
        end=data if data>0 else self.timestamp(actor);pending=end>self.engine.sim_now
        minutes=max(0,(end-self.engine.sim_now)//60);left=self.config.maxtechtime-minutes
        text=(f'You have {minutes} minute'+('' if minutes==1 else 's')+' of repairs pending'+
            (" and you're too tired to do more efficiently." if left<=0 else f" and you're ready to do at least {left} more minute"+('' if left==1 else 's')+' of work.')) if pending else 'You have no jobs pending!'
        self.notice(actor,text)
        return dict(pending=pending,minutes=minutes,remaining=left,tired=left<=0,message=text)

    def add_time(self,actor,minutes):
        end=self.timestamp(actor)+minutes*60
        if not self.inventory.put(actor._id,'TECHTIME',str(end)):raise ValueError('Technician identity unavailable')
        self.status(actor,end);return end-self.engine.sim_now

    def gate(self,actor,unit,kind='C'):
        if not getattr(actor,'tech',False):raise ValueError('Insufficient clearance to access the command.')
        if unit is None:raise ValueError('Error has occured in techcommand ; please contact a wiz')
        if getattr(actor,'wizard',False):return
        if self.engine.has_event(EventType.STARTUP,unit):raise ValueError("The mech's starting up! Please stop the sequence first.")
        if unit.is_started:raise ValueError("The mech's started up ; please shut it down first.")
        if (kind=='C' or self.config.limitedrepairs) and unit.unit_type not in (U.DS,U.SPHEROID_DS) and not getattr(unit,'repair_stall',False):raise ValueError("The 'mech isn't in a repair stall!")

    def fatigue(self,actor):
        if self.pending(actor)>=self.config.maxtechtime:raise ValueError("You're too tired to do that!")

    def roll(self,actor,unit,difficulty,weapons=False):
        from systems.characters import actor_advantage
        from systems.piloting import find_tech_skill,skill_target
        from systems.experience import tech
        if actor_advantage(actor,'Tech_Aptitude'):
            dice=[draw('tech_d6',1,6,lambda:random.randint(1,6)) for _ in range(3)]
            result=sum(dice)-min(dice)
        else:result=roll('tech_rolls')
        skill=skill_target(actor,'Technician-Weapons','technician_weapons',18) if weapons else find_tech_skill(actor,unit)
        target=skill+difficulty;margin=result-target
        message=f'BTH: {target} Roll: {result}'
        if getattr(actor,'wizard',False):
            message=f"{'Tech-W' if weapons else 'Tech'} - BTH: {target}(Base:{skill}, Mod:{difficulty}) Roll: {result}"
        self.notice(actor,message)
        self.rolls.append(dict(actor=actor._id,unit=unit._id,weapons=weapons,difficulty=difficulty,target=target,roll=result,margin=margin))
        if margin>=0 and unit.in_character:tech(actor,unit,max(1,min(target-7,max(2,1+difficulty))),weapons=weapons,now=self.engine.sim_now)
        return margin
