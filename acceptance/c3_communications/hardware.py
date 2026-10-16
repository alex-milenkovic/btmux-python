import re
from . import step,unit,eq,quiet
from systems import c3
from entities.mech import UnitType,Location,FireMode,CritStatus
from entities.crittypes import i2special,Special
from systems.criticals import count_total_c3_masters,count_working_c3_masters,apply_critical_to_slot,EquipmentType

LOC={'LT':Location.LTORSO,'RT':Location.RTORSO,'HEAD':Location.HEAD}

def reset(u,kind):
    u.unit_type=UnitType[kind]
    for sec in u.sections:
        for slot in sec.criticals:slot.type=slot.firemode=0

@step(r'class (\w+) and C3 master slots (.+)')
def grouping(w,kind,text):
    u=unit(w);reset(u,kind)
    body=re.sub(r'-(functional|slot\d+-(?:destroyed|disabled))$','',text)
    for section,positions in re.findall(r'(LT|RT):([\d,\-]+)',body):
        for value in positions.split(','):
            indexes=range(int(value.split('-')[0]),int(value.split('-')[1])+1) if '-' in value else [int(value)]
            for i in indexes:u.sections[LOC[section]].criticals[i].type=i2special(Special.C3_MASTER)
    match=re.search(r'slot(\d+)-(destroyed|disabled)',text)
    if match:u.sections[Location.LTORSO].criticals[int(match[1])].firemode=FireMode.DESTROYED_MODE if match[2]=='destroyed' else FireMode.DISABLED_MODE

@step(r'total and working masters are counted')
def counted(w):w['result']=(count_total_c3_masters(unit(w)),count_working_c3_masters(unit(w)))

@step(r'counts are (\d+) total and (\d+) working')
def counts(w,total,working):eq(w['result'],(int(total),int(working)))

@step(r'class (\w+) and source slot layout (.+)')
def window(w,kind,text):
    u=unit(w);reset(u,kind);loc=Location.HEAD if 'HEAD' in text else Location.LTORSO
    for i in ([0,1] if 'masters-at' in text else [] if 'no-master' in text else [4] if 'HEAD4' in text else [0]):
        u.sections[loc].criticals[i].type=i2special(Special.C3_MASTER)
    match=re.search(r'slot(\d+)-destroyed',text)
    if match:u.sections[loc].criticals[int(match[1])].firemode=FireMode.DESTROYED_MODE
    w['section']=loc;w['slot']=int(re.search(r'query(\d+)',text)[1])

@step(r'working-master membership checks the queried slot')
def query(w):w['result']=c3.part_of_working_master(unit(w),w['section'],w['slot'])

@step(r'the membership result is (True|False)')
def query_result(w,result):eq(w['result'],result=='True')

@step(r'formed network (.+) with action (.+)')
def lifecycle(w,network,action):
    w['network'],w['action']=network,action
    a,b=unit(w),unit(w,'B');ordinary=not network.startswith('C3i')
    if 'master' in network:
        reset(a,'MECH')
        from entities.mech import Specials
        a.specials=Specials.C3_MASTER_TECH
        for loc in ([Location.LTORSO,Location.RTORSO] if 'two-separate' in network else [Location.LTORSO]):
            for slot in a.sections[loc].criticals[:5]:slot.type=i2special(Special.C3_MASTER)
        a.working_c3_masters=count_working_c3_masters(a);a.total_c3_masters=count_total_c3_masters(a)
    if network=='C3-slave':a.working_c3_masters=0;b.working_c3_masters=1
    if action in ('destroy-slave','destroy-C3i-slot'):
        a.sections[Location.LTORSO].criticals[0].type=i2special(Special.C3_SLAVE if action=='destroy-slave' else Special.C3I)
    c3.add(a,b,ordinary)
    if action=='destroy-last-master':
        from systems.targeting import tag
        from physics.hexmath import SCALEMAP
        target=unit(w,'C');target.team=2
        assert tag(w['engine'],a,target.contact_id,a.pilot)[0]
        target.fx=a.fx+16*SCALEMAP

@step(r'ordinary damage or map transfer reaches its source lifecycle boundary')
def lifecycle_run(w):
    a=unit(w);action=w['action']
    if action=='cross-map':
        from systems.map_transitions import transfer
        from entities.map import GameMap
        board=GameMap(30,30);board._id=2000;w['engine'].register_entity(board)
        quiet(w,transfer,a,board)
    else:
        kind=EquipmentType.C3I if action=='destroy-C3i-slot' else EquipmentType.C3_SLAVE if action=='destroy-slave' else EquipmentType.C3_MASTER
        apply_critical_to_slot(a,Location.LTORSO,0,engine=w['engine'])
        if kind!=EquipmentType.C3I:c3.validate(unit(w,'B'))
    w['assert_observation']=lifecycle_result

def lifecycle_result(w,expected):
    a,b=unit(w),unit(w,'B')
    if expected=='one-working-master-retained-capacity-reduced-on-validation':
        eq(a.working_c3_masters,1);eq(c3.maximum(a,a.c3_network),3)
    elif expected=='destroyed-flag-TAG-check-and-no-shared-range':
        assert a.crit_status&CritStatus.C3_DESTROYED;eq(c3.range_query(a,b,10),(10,-1))
        eq(a.working_c3_masters,0);eq(a.tag_target,0);eq(unit(w,'C').tagged_by,0)
    elif expected=='destroyed-flag-and-removed-on-validation':
        assert a.crit_status&CritStatus.C3_DESTROYED;eq(b.c3_network,[])
    elif expected in ('reciprocal-detachment','owner-cleared-old-peers-detached'):
        ordinary=not w['network'].startswith('C3i');eq(c3.network_size(a,ordinary),0);eq(c3.network_size(b,ordinary),0)
    else:raise AssertionError(expected)
