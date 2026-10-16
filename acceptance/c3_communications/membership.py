"""Membership fixtures manipulate identities/flags, never computed eligibility."""
import re
from . import step,unit,eq,inbox
from systems import c3
from entities.mech import MechStatus as S, MechStatus2 as S2, CritStatus as C, Specials


@step(r'network kind (C3i?) has (\d+) working masters and target peer count (\d+)')
def capacity(w,kind,masters,peers):
    w['ordinary']=kind=='C3';a=unit(w);a.working_c3_masters=int(masters)
    for i in range(int(peers)):
        p=unit(w,'P'+str(i));p.contact_id='P'+chr(65+i)
        c3.add(a,p,w['ordinary'])
    w['joining']=unit(w,'J');w['joining'].contact_id='JJ'
    eq(c3.network_size(a,w['ordinary']),int(peers))

@step(r'another eligible unit tries to join')
def join(w):w['result']=c3.command(w['joining'],w['joining'].pilot,'join','AA',w['ordinary'])

@step(r'the join is (accepted|capacity-refusal)')
def joined(w,expected):
    eq(w['result']['ok'],expected=='accepted')
    if expected=='capacity-refusal':assert 'maximum capacity' in w['result']['error']

@step(r'network kind (C3i?) and join condition (.+)')
def gate(w,kind,condition):
    w.update(ordinary=kind=='C3',condition=condition,argument='AA')
    a,b=unit(w),unit(w,'B')
    if condition=='two-arguments':w['argument']='AA BB'
    elif condition=='empty-argument':w['argument']=''
    elif condition=='no-own-technology':b.specials=Specials.NONE
    elif condition=='own-system-destroyed':b.crit_status|=C.C3I_DESTROYED
    elif condition=='own-AngelECM':b.status2|=S2.ANGEL_ECM_DISTURBED
    elif condition in ('already-connected','connected-leave'):c3.add(a,b,w['ordinary'])
    elif condition=='target-no-LOS':a.crit_status|=C.INVISIBLE;w['map'].losinfo[b._id,a._id]=0
    elif condition=='enemy-target':a.team=2
    elif condition=='self-target':w['argument']='BB'
    elif condition=='destroyed-target':a.status|=S.DESTROYED
    elif condition=='stopped-target':a.status&=~S.STARTED
    elif condition=='target-only-C3':a.specials2=0
    elif condition=='intact-target-under-ECM':a.status2|=S2.ECM_DISTURBANCE
    elif condition=='destroyed-target-system':a.crit_status|=C.C3I_DESTROYED
    if condition.endswith('-leave'):w['argument']='-'

@step(r'the pilot issues the network join command')
def gate_run(w):
    b=unit(w,'B');w['result']=c3.command(b,b.pilot,'join',w['argument'],w['ordinary']);w['assert_observation']=gate_result

def gate_result(w,expected):
    errors={'argument-error':'Invalid number','technology-error':'not equipped','system-error':'system is destroyed',
            'operational-error':'not currently operational','already-connected-error':'already in',
            'targetID-error':'valid targetID','unfriendly-error':'unfriendly','self-error':'yourself',
            'target-destroyed-error':'unit is destroyed','target-not-started-error':'not started','target-technology-error':'appear to be equipped'}
    if expected in errors:
        eq(w['result']['ok'],False);assert errors[expected] in w['result']['error'];return
    eq(w['result']['ok'],True)
    if expected=='join-stored-target-temporarily-unusable':eq(unit(w,'B').c3i_network,[10]);eq(c3.temporary(unit(w,'B'),False),[])
    elif expected=='confirmation-then-source-validation-clears-connection':
        eq(unit(w).c3i_network,[]);eq(c3.network_size(unit(w,'B'),False),0);assert any('You connect' in t for t in inbox(w,'B'))
    elif expected=='not-connected-message':assert 'not connected' in inbox(w,'B')[-1]
    elif expected=='reciprocal-clear-and-disconnect-message':eq(unit(w).c3i_network,[]);assert 'disconnect' in inbox(w,'B')[-1]
    else:raise AssertionError(expected)

@step(r'network kind (C3i?) and sequence (.+)')
def sequence(w,kind,sequence):w.update(ordinary=kind=='C3',sequence=sequence)

@step(r'the joins and removals execute in that order')
def sequences(w):
    for operation in w['sequence'].split(';'):
        name=operation[0];u=unit(w,name)
        target='-' if operation.endswith('leaves') else operation[-1]*2
        result=c3.command(u,u.pilot,'join',target,w['ordinary']);eq(result['ok'],True)

@step(r'stored peer order is (.+)')
def ordered(w,expected):
    for field in expected.split(';'):
        name,peers=field.split(':')
        eq(getattr(unit(w,name),c3.network_name(w['ordinary'])),[] if peers=='empty' else [unit(w,p)._id for p in peers.split(',')])

@step(r'stored C3i peer state (.+)')
def state(w,state):
    a,b=unit(w),unit(w,'B');c3.write(a,[b._id],False)
    if state=='stopped':b.status&=~S.STARTED
    elif state=='unconscious':b.status|=S.UNCONSCIOUS
    elif state=='blinded':b.status|=S.BLINDED
    elif state=='ECM-disturbed':b.status2|=S2.ECM_DISTURBANCE
    elif state=='Angel-disturbed':b.status2|=S2.ANGEL_ECM_DISTURBED
    elif state=='destroyed':b.status|=S.DESTROYED
    elif state=='wrong-team':b.team=2
    elif state=='wrong-map':b.mapindex=99
    elif state=='missing':a.c3i_network=[999]
    elif state=='zero-ID':a.c3i_network=[0]
    elif state=='no-tech':b.specials2=0
    elif state=='system-destroyed':b.crit_status|=C.C3I_DESTROYED

@step(r'validation and targeting and messaging build their eligible lists')
def lists(w):
    a=unit(w);c3.validate(a,False)
    w['result']=(bool(a.c3i_network),bool(c3.temporary(a,False,True,True,False)),bool(c3.temporary(a,False,True,True,True)))

@step(r'stored targeting messaging inclusion is (.+)')
def inclusion(w,expected):eq(w['result'],tuple(v=='True' for v in expected.split(',')))

@step(r'diagnostic source network (.+)')
def array_state(w,state):w['array_state']=state

@step(r'the named storage operation runs')
def arrays(w):
    a=unit(w);state=w['array_state'];w['result']=None
    if state.startswith('C3-owner'):
        a.working_c3_masters=int(re.search(r'master(\d+)',state)[1])
        names=state.split('peers-')[1].split(';')[0].split(',')
        peers=[unit(w,name) for name in names]
        for peer,name in zip(peers,names):peer.working_c3_masters=1 if name.startswith('M') else 0
        a.c3_network=[p._id for p in peers]
        w['result']=c3.temporary(a) if state.endswith('temporary-trim') else c3.trim(a,a.c3_network)
    else:
        size=re.search(r'size-?(negative|\d+)',state)[1]
        names=re.search(r'slots-([^;]+)',state)
        values=[unit(w,name)._id if name!='-1' else -1 for name in names[1].split(',')] if names else [unit(w,'B')._id]
        for ident in values:
            if ident>0:c3.write(next(p for p in w['units'].values() if p._id==ident),[a._id],False)
        a.c3i_network=values;a.c3i_network_size=-1 if size=='negative' else int(size)
        operation=state.split(';')[-1]
        if operation=='validate':c3.validate(a,False)
        elif operation.startswith('free-'):w['result']=c3.free_position(a,unit(w,operation[5:]),False)
        elif operation=='clear-local':c3.clear(a,False,False)
        elif operation=='clear-B':c3.remove(a,unit(w,'B')._id,False)
        elif operation=='temp-index1':w['result']=c3.temp_member(a,c3.slots(a,False),a.c3i_network_size,1)
        elif operation=='other-index1':w['result']=c3.other(a,1,False)
    w['assert_observation']=arrays_result

def arrays_result(w,expected):
    a=unit(w)
    if expected=='owner-cleared-peer-entries-retained-negative-prefix':eq(a.c3i_network,[]);eq(unit(w,'B').c3i_network,[10])
    elif expected=='B-only-C-outside-prefix':eq(a.c3i_network,[11])
    elif expected=='B,C-compacted':eq(a.c3i_network,[11,12])
    elif expected=='duplicates-retained':eq(a.c3i_network,[11,11])
    elif expected in ('minus1','minus2','index1'):eq(w['result'],{'minus1':-1,'minus2':-2,'index1':1}[expected])
    elif expected=='owner-empty-peers-unchanged':eq(a.c3i_network,[]);eq(unit(w,'B').c3i_network,[10]);eq(unit(w,'C').c3i_network,[10])
    elif expected=='C-only':eq(a.c3i_network,[12])
    elif expected in ('M1,S1,S2','S1,S2'):eq(w['result'],[unit(w,n)._id for n in expected.split(',')])
    elif expected=='temporary-empty-stored-S1,S2':eq(w['result'],[]);eq(a.c3_network,[unit(w,'S1')._id,unit(w,'S2')._id])
    elif expected.startswith('null-'):eq(w['result'],None)
    else:raise AssertionError(expected)

@step(r'message condition (.+)')
def message_condition(w,condition):
    w['condition']=condition;w['ordinary']=not condition.startswith('C3i')
    a,b=unit(w),unit(w,'B')
    if 'empty-stored' not in condition:c3.add(a,b,w['ordinary'])
    if 'only-stopped' in condition:b.status&=~S.STARTED
    if 'only-unconscious' in condition:b.status|=S.UNCONSCIOUS
    if 'owner-slave' in condition:a.working_c3_masters=0;b.working_c3_masters=1;b.status2|=S2.ECM_DISTURBANCE
    for u in w['units'].values():u.pilot.inbox=[]

@step(r'the ordinary network message command runs')
def message_run(w):
    a=unit(w);w['result']=c3.command(a,a.pilot,'message','   ' if 'blank-message' in w['condition'] else '   hello',w['ordinary']);w['assert_observation']=message_result

def message_result(w,expected):
    if expected=='no-other-units-error':assert 'no other units' in w['result']['error'];return
    if expected=='what-to-send-error':assert 'What do you want' in w['result']['error'];return
    eq(w['result']['ok'],True);kind='C3' if w['ordinary'] else 'C3i'
    eq(inbox(w,'A'),[f'%ch{kind}/You: hello%cn'])
    eq(inbox(w,'B'),[f'%ch{kind}/A [AA]: hello%cn'] if expected.startswith('stripped') else [])
