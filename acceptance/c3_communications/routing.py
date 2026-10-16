from . import step,unit,eq,quiet,inbox
from systems import communications as radio
from entities.mech import MechStatus as S,MoveType as M
from physics.hexmath import SCALEMAP


def position(u,x,y=0):u.fx=x*SCALEMAP;u.fy=y*SCALEMAP;u.fz=0

def chain(w,names='ABC',spacing=5):
    # Only listed units belong to this source-ordered routing map.
    peers=[unit(w,name) for name in names];w['map'].mechs_on_map[:]=peers
    for i,p in enumerate(peers):
        position(p,i*spacing);p.radio_range=spacing;p.freq=[17,0];p.freqmodes=[5,0];p.radio_type=114
    w['sender'],w['receiver']=peers[0],peers[-1]
    return peers

@step(r'relay state (.+)')
def relay(w,state):
    a,b,c=chain(w)
    if state=='enemy':b.team=2
    if 'stopped' in state:b.status&=~S.STARTED
    if 'stationary' in state:b.move_type=M.NONE
    if 'destroyed' in state:b.status|=S.DESTROYED
    if state=='no-relay-capability':b.radio_type=98
    if state=='matching-channel-without-relay-mode':b.freqmodes[0]=1
    if state=='wrong-frequency':b.freq[0]=18
    if state=='relay-ECM':b.status2|=4
    if state=='relay-muted':b.freqmodes[0]|=2
    if state=='relay-mode-without-digital-diagnostic':b.freqmodes[0]=4

@step(r'an out-of-direct-range digital message seeks its only possible relay')
def seek(w):w['result']=radio.find_comm_link(w['map'],w['sender'],w['receiver'],17)

@step(r'route exists is (True|False)')
def exists(w,value):eq(w['result'] is not None,value=='True')

@step(r'directed graph fixture (.+)')
def graph(w,text):w['graph']=text

@step(r'source route discovery executes')
def discover(w):
    text=w['graph'];w['assert_observation']=graph_result
    if text.startswith('A-range'):
        a,b,c=chain(w)
        if 'distance5.01' in text:position(b,5.01);b.radio_range=10
        if 'B-range1-' in text:b.radio_range=1
        if text.startswith('A-range10'):a.radio_range=10
        seek(w)
    elif text=='A-and-D-only-direct-helper':chain(w,'AD');seek(w)
    elif text=='A-B-D-B-two-matching-relay-channels':
        a,b,d=chain(w,'ABD');b.freq=[17,17];b.freqmodes=[5,5];seek(w)
    else:
        edges_by_name={
            'A-B-C-D-chain':('ABCD',('AB','BC','CD')),
            'A-B-D-and-A-C-D-equal':('ABCD',('AB','BD','AC','CD')),
            'A-B-C-D-and-A-E-D':('ABCED',('AB','BC','CD','AE','ED')),
            'A-B-cycle-no-target-edge':('ABD',('AB','BA')),
            'recursive-A-B-D':('ABD',('AB','BD'))}
        names,arcs=edges_by_name[text];w['names']=names
        graph=[[first+second in arcs for second in names] for first in names]
        w['result']=radio.route_graph(graph,recursive=text.startswith('recursive'))

def graph_result(w,expected):
    result=w['result']
    if expected.startswith(('no-route','false-')):eq(result,None);return
    if expected=='duplicate-candidates-retained':eq(result['candidates'],[unit(w,n)._id for n in 'ABBD']);return
    path=result['path']
    if 'names' in w:path=[w['names'][i] for i in path]
    else:path=[next(name for name,p in w['units'].items() if p._id==i) for i in path]
    expected_path={'A-path-C-direct':['A'],'A,B-path-C-recipient':['A','B'],'A,B,C-path-D-recipient':['A','B','C'],
                   'A,C-last-equal-route':['A','C'],'A,E-shorter-route':['A','E'],'source-dep1-path-A-only':['A']}
    eq(path,expected_path[expected])

@step(r'receiver mode (D|DI) and route (.+)')
def info(w,mode,route):
    peers=chain(w,route.replace('-direct','').replace('-',''))
    peers[-1].freqmodes=[9 if mode=='DI' else 1,0];peers[0].chantitle[0]='Ops'
    w['route']=route

@step(r'digital message with title Ops arrives')
def info_run(w):
    w['result']=quiet(w,radio.transmit,w['sender'],0,'hello');w['assert_observation']=info_result

def info_result(w,expected):
    text=inbox(w,w['route'].replace('-direct','').split('-')[-1])[-1]
    assert text.startswith('[A:270] '),text
    if expected.startswith('no-R-path'):eq(text,'[A:270] <Ops> hello%c')
    elif expected=='R-path-B-bearing-to-A-then-Ops-title':eq(text,'[A:270] {R-path:[BB]-h:270} <Ops> hello%c')
    elif expected=='R-path-B-then-D-bearing-to-D':eq(text,'[A:270] {R-path:[BB]-h:270/[DD]-h:270} <Ops> hello%c')
    else:raise AssertionError(expected)
