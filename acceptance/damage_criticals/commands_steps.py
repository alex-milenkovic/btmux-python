from . import *
from systems import enhanced_crits

@step(r'an intact MECH with enough armor and administrative damage argument (.+)')
def admin(w,arg):
    w['argument']=arg
    for s in unit(w).sections:s.armor=s.rear=100

@step(r'the damage command executes')
def run_admin(w):w['result']=call(w,commands.damage_command,unit(w),w['argument'])

@step(r'command accepted is (True|False) and total requested hit damage is (\d+)')
def admin_result(w,accepted,total):eq(w['result']['accepted'],truth(accepted));eq(sum(w['result']['sizes']),int(total))

@step(r'a MECH left arm armor (\d+) and dodamage direction zero')
def direct(w,armor):unit(w).sections[0].armor=int(armor)

@step(r'dodamage applies total (\d+) in clusters (\d+)')
def direct_hit(w,total,cluster):w['result']=call(w,commands.dodamage,unit(w),int(total),int(cluster),0)

@step(r'left arm armor is (\d+) and cluster sizes are ([\d,]+)')
def direct_result(w,armor,sizes):eq(unit(w).sections[0].armor,int(armor));eq(w['result']['sizes'],list(map(int,sizes.split(','))))

@step(r'an intact MECH left torso with front armor (\d+) rear armor (\d+)')
def section(w,front,rear):unit(w).sections[2].armor=int(front);unit(w).sections[2].rear=int(rear)

@step(r'damage-section receives argument (.+)')
def section_hit(w,arg):w['result']=call(w,commands.damage_command,unit(w),arg,True)

@step(r'command accepted is (True|False) front armor is (\d+) and rear armor is (\d+)')
def section_result(w,accepted,front,rear):
    eq(w['result']['accepted'],truth(accepted));eq((unit(w).sections[2].armor,unit(w).sections[2].rear),(int(front),int(rear)))

@step(r'an originally populated MECH left arm with armor (\d+) internal (\d+) rear (\d+)')
def raw(w,front,internal,rear):
    s=unit(w).sections[0];s.armor=int(front);s.internal=int(internal);s.rear=int(rear)

@step(r'setarmorstatus receives type (\d+) and value text (\S+)')
def raw_set(w,kind,value):w['reply']=commands.set_armor_status(unit(w),'LA',kind,value)

@step(r'reply is (.+) front armor is (\d+) internal is (\d+) rear armor is (\d+) and no destruction event is emitted')
def raw_result(w,reply,front,internal,rear):
    eq(w['reply'],reply);s=unit(w).sections[0];eq((s.armor,s.internal,s.rear),tuple(map(int,(front,internal,rear))));eq(bool(s.config & 0x80),False)

@step(r'one mounted weapon with state (\S+)')
def status_fixture(w,state):
    mount(w);slot=unit(w).sections[4].criticals[0]
    states={'operational':0,'damaged':F.DAMAGED_MODE,'disabled-and-damaged':F.DISABLED_MODE|F.DAMAGED_MODE,'broken-and-disabled':F.BROKEN_MODE|F.DISABLED_MODE}
    if state in states:slot.firemode=states[state]
    else:
        value={'destroyed':5,'jammed':1,'shorted':2,'empty':4,'dud':3,'ammojammed':6}[state.removeprefix('temporary-')]
        enhanced_crits.set_part_temp_nuke(slot,value)

@step(r'weaponstatus is requested')
def status(w):w['status']=enhanced_crits.weapon_status(unit(w))[0]

@step(r'displayed status is (\w+)')
def status_result(w,status):eq(w['status']['status'],status)

@step(r'section zero has two distinct mounted weapons in order laser then autocannon and section one has one missile weapon')
def enumeration(w):
    w['types']={}
    for name,category,section,critical in [('laser','energy',0,0),('autocannon','autocannon',0,1),('missile','missile',1,0)]:
        w['types'][name]=mount(w,category,section,critical).index

@step(r'section (\d+) weapon count and ordinal (\d+) type are requested')
def query(w,section,ordinal):
    w['count']=commands.count_weapons_in_location(unit(w),int(section));w['type']=commands.find_weapon_type_num_in_location(unit(w),int(section),int(ordinal))

@step(r'count is (\d+) and returned type is (\w+)')
def query_result(w,count,kind):eq(w['count'],int(count));eq(w['type'],-1 if kind=='none' else w['types'][kind])
