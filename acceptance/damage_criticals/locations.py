from . import *
from systems import hit_locations as hl
from systems.combat import HitGroup as H

def side(name):return H[{'LEFT':'LEFTSIDE','RIGHT':'RIGHTSIDE'}.get(name,name)]

@step(r'a MECH using FASA hit locations from (\w+) with exile stun disabled')
def mech_table(w,group):w['table_fixture']=('MECH',group,'FASA',10)

@step(r'advanced (\w+) locations from (\w+) with turret internal (\d+) and every crittable check failing')
def advanced_table(w,kind,group,turret):w['table_fixture']=(kind,group,'advanced',int(turret))

@step(r'hit-location rolls two through twelve are evaluated on independent fixtures')
def vector(w):
    kind,group,profile,turret=w['table_fixture'];results=[]
    for roll in range(2,13):
        fixture={};fresh(fixture);u=setup(fixture,kind);u.sections[4].internal=turret
        for s in u.sections:s.armor=s.armor_orig=100
        draw(fixture,'crittable_chance',[1]*20);draw(fixture,'motive_rolls',[2]*10)
        results.append(call(fixture,hl.find_hit_location,u,side(group),roll,profile=profile))
    w['locations']=[int(r[0]) for r in results];w['criticals']=[bool(r[1]) for r in results]
    setup(w,kind)

@step(r'ordered locations are ([\w,]+) and (only roll two marks a critical|no output critical is set)')
def vector_result(w,locations,criticals):
    eq(w['locations'],[loc(w,name) for name in locations.split(',')]);eq(w['criticals'],[criticals.startswith('only')]+[False]*10)

@step(r'a (biped|quad) target viewed from (\w+)')
def physical_fixture(w,chassis,group):unit(w).move_type=M.QUAD if chassis=='quad' else M.BIPED;w['side']=side(group)

@step(r'(punch|kick) location rolls one through six are evaluated')
def physical_vector(w,attack):w['locations']=[call(w,hl.physical_location,unit(w),w['side'],attack,i) for i in range(1,7)]

@step(r'ordered locations are ([\w,]+)')
def physical_result(w,locations):eq(w['locations'],[loc(w,name) for name in locations.split(',')])

@step(r'a BA unit swarming a MECH without partial cover')
def swarming(w):
    attacker=session(w).units['enemy'];attacker.unit_type=U.BSUIT;attacker.swarm_target=unit(w)

@step(r'the swarm location roll is (\d+)')
def swarm(w,roll):w['selected']=call(w,hl.target_hit_location,session(w).units['enemy'],unit(w),H.FRONT,int(roll))

@step(r'the hit location is (\w+) rear flag is (True|False) and critical flag is True')
def swarm_result(w,name,rear):eq(w['selected'],(loc(w,name),truth(rear),True))

@step(r'a BA unit with live member indices ([\w,]+)')
def members(w,indices):
    setup(w,'BSUIT');live=[] if indices=='none' else list(map(int,indices.split(',')))
    for i,s in enumerate(unit(w).sections):s.internal=10 if i in live else 0

@step(r'the live-member helper uses choice zero and the FASA front table uses roll seven')
def member_select(w):
    draw(w,'suit_choice',[0,0]);draw(w,'empty_suit_location',[0])
    w['helper']=call(w,hl.live_suit_hit_location,unit(w));w['selected']=call(w,hl.find_hit_location,unit(w),H.FRONT,7,profile='FASA')[0]

@step(r'helper location is (-?\d+) and FASA location index is (\d+)')
def member_result(w,helper,table):eq(w['helper'],int(helper));eq(w['selected'],int(table))

@step(r'an attacker of class (\w+) and target MECH with cover (True|False) swarmed (True|False) and attacker height difference (-?\d+)')
def selection_fixture(w,kind,cover,swarmed,height):
    a=session(w).units['enemy'];a.unit_type=U[kind];a.z=unit(w).z+int(height);a.swarm_target=unit(w) if truth(swarmed) else None
    if truth(cover):unit(w).status|=S.PARTIAL_COVER

@step(r'a front hit uses physical location roll one and normal location roll seven')
def selection(w):
    draw(w,'physical_location',[1]);draw(w,'hit_location_rolls',[7]);draw(w,'swarm_location',[7])
    start=len(session(w).draws);w['selected']=call(w,hl.target_hit_location,session(w).units['enemy'],unit(w),H.FRONT)
    names=[d['name'] for d in session(w).draws[start:]]
    if 'physical_location' in names:w['table']='punch' if unit(w).has_status(S.PARTIAL_COVER) else 'kick'
    else:w['table']='swarm' if 'swarm_location' in names else 'normal'

@step(r'selected location is (\w+) and selected table is (\w+)')
def selection_result(w,name,table):eq(w['selected'][0],loc(w,name));eq(w['table'],table)

@step(r'a rear NARC hit initially selects (\w+) on class (\w+) with dead sections ([\w,]+)')
def narc_fixture(w,name,kind,dead):
    setup(w,kind);w['narc_loc']=loc(w,name)
    if dead!='none':
        for section in dead.split(','):unit(w).sections[loc(w,section)].internal=0

@step(r'the pod resolves its attachment location')
def narc(w):w['selected']=call(w,hl.narc_hit_location,session(w).units['enemy'],unit(w),w['narc_loc'],True)

@step(r'attachment location is (\w+) and rear marker is (True|False)')
def narc_result(w,name,rear):eq(w['selected'],(-1 if name=='none' else loc(w,name),truth(rear)))

@step(r'a started MECH moving above walking speed and exile mode (\d+)')
def head_fixture(w,mode):unit(w).speed=unit(w).max_speed;session(w).engine.exile_stun_code=int(mode)

@step(r'a front head hit rerolls punch location (\d+) and time advances (\d+) ticks')
def head(w,roll,time):
    draw(w,'physical_location',[int(roll)]);w['selected']=call(w,hl.find_hit_location,unit(w),H.FRONT,12)[0];call(w,session(w).engine.run_ticks,int(time))

@step(r'replacement location is (\w+) and MECH stunned is (True|False)')
def head_result(w,name,stunned):eq(w['selected'],loc(w,name));eq(bool(unit(w).crit_status&C.MECH_STUNNED),truth(stunned))

@step(r'class (\w+) movement (\w+) critproof (True|False) vehicle-critical setting (\d+) original armor (\d+) and current armor (\d+)')
def eligible_fixture(w,kind,movement,proof,vcrit,original,current):
    setup(w,kind,move_type=M[movement]);u=unit(w);session(w).engine.vcrit=int(vcrit)
    if truth(proof):u.specials|=Specials.CRITPROOF_TECH
    u.sections[4].armor_orig=int(original);u.sections[4].armor=int(current)

@step(r'crittable is checked at threshold (\d+) with bounded chance draw (\d+)')
def eligible(w,threshold,roll):draw(w,'crittable_chance',[int(roll)]);w['eligible']=call(w,hl.crittable,unit(w),4,int(threshold))

@step(r'eligibility is (True|False)')
def eligible_result(w,value):eq(w['eligible'],truth(value))

@step(r'a dug-in ground vehicle with original turret internal (\d+) current turret internal (\d+) and profile (\w+)')
def dug_fixture(w,original,current,profile):
    u=setup(w,'GROUND');u.tank_crit_status=4;u.sections[4].internal_orig=int(original);u.sections[4].internal=int(current);w['profile']=profile

@step(r'normal front location roll seven and dug-in draw (\d+) are supplied')
def dug(w,roll):
    draw(w,'dug_in',[int(roll)]);draw(w,'hit_location_rolls',[7,7]);draw(w,'crittable_chance',[1])
    session(w).engine.fasaadvvhlcrit=int(w['profile']=='advanced')
    w['selected']=call(w,hl.find_hit_location,unit(w),H.FRONT)[0]

@step(r'selected location is (\w+)')
def location_result(w,name):eq(w['selected'],loc(w,name))

@step(r'a (\w+) under (\w+) viewed from (\w+) with live turret and no successful incidental TAC')
def class_table(w,kind,profile,group):
    setup(w,kind);w['profile']=profile;w['side']=side(group);draw(w,'crittable_chance',[1]*10)

@step(r'selected table roll is (\d+)')
def class_select(w,roll):w['selected']=call(w,hl.find_hit_location,unit(w),w['side'],int(roll),profile=w['profile'])[0]

@step(r'selected location index is (\d+)')
def class_result(w,index):eq(w['selected'],int(index))
