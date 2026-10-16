"""Source-directed relay edges, ordered route search and actual INFO reception."""
from qa.communications.common import *

def radios(names='ABC',step=5):
    result=[unit(name,kind=None,at=[3,3+i*step,0]) for i,name in enumerate(names)]
    for i,u in enumerate(result):u['communications'].update(radio_range=5,freqmodes=[5 if 0<i<len(result)-1 else 1,0])
    result[-1]['communications']['radio_range']=1
    return result

def run():
    a=Audit('routing')
    for ident,n,r,line in rows('routing'):
        units=radios();acts=[];expected=[10,20];target='C';graph=False
        if n==1:
            s=r['state'];b=units[1]
            if s=='enemy':b['team']=2
            elif s in ('movable-stopped','stationary-stopped-intact'):b['started']=False
            if s.startswith('stationary'):b['movement']='NONE'
            if s=='stationary-destroyed':b['destroyed']=True
            if s=='no-relay-capability':b['communications']['radio_type']=98
            if s=='matching-channel-without-relay-mode':b['communications']['freqmodes']=[1,0]
            if s=='wrong-frequency':b['communications']['freq']=[999,456]
            if s=='relay-ECM':b['communications']['status2']=C['ECM_DISTURBANCE']
            if s=='relay-muted':b['communications']['freqmodes']=[7,0]
            if s=='relay-mode-without-digital-diagnostic':b['communications']['freqmodes']=[4,0]
            acts=[diag('route',target='C',frequency=123),command('sendchannel',args='a=hello')]
        elif n==2:
            s=r['graph']
            if s.startswith('A-range'):
                if s.startswith('A-range10'):units[0]['communications']['radio_range']=10;expected=[10]
                if 'B-distance5.01' in s:units[1]['real']=[1000,8.01*322.5,0];units[0]['real']=[1000,3*322.5,0];units[2]['real']=[1000,13*322.5,0];expected=None
                if 'B-range1-' in s:units[1]['communications']['radio_range']=1;expected=[10] if s.startswith('A-range10') else None
                acts=[diag('route',target=target,frequency=123)]
            elif s=='A-and-D-only-direct-helper':
                units=radios('AD',1);target='D';expected=None;acts=[diag('route',target=target,frequency=123)]
            elif s=='A-B-D-B-two-matching-relay-channels':
                units=radios('ABD');target='D';units[1]['communications'].update(freq=[123,123],freqmodes=[5,5]);acts=[diag('route',target=target,frequency=123)]
            else:
                graph=True
                names,edges={'A-B-C-D-chain':('ABCD',[(0,1),(1,2),(2,3)]),
                    'A-B-D-and-A-C-D-equal':('ABCD',[(0,1),(1,3),(0,2),(2,3)]),
                    'A-B-C-D-and-A-E-D':('ABCED',[(0,1),(1,2),(2,4),(0,3),(3,4)]),
                    'A-B-cycle-no-target-edge':('ABD',[(0,1),(1,0)]),
                    'recursive-A-B-D':('ABD',[(0,1),(1,2)])}[s]
                matrix=[[int((i,j) in edges) for j in range(len(names))] for i in range(len(names))]
                expected={'A-B-C-D-chain':[0,1,2],'A-B-D-and-A-C-D-equal':[0,2],'A-B-C-D-and-A-E-D':[0,3],'A-B-cycle-no-target-edge':None,'recursive-A-B-D':[0]}[s]
                acts=[diag('route-graph',edges=matrix,recursive=s.startswith('recursive'))]
        else:
            s=r['route'];names={'A-B-C':'ABC','A-B-D-C':'ABDC','A-C-direct':'AC'}[s]
            units=radios(names);target=names[-1]
            units[-1]['communications']['freqmodes']=[9 if r['mode']=='DI' else 1,0]
            acts=[command('setchanneltitle',args='a=Ops'),command('sendchannel',args='a=hello')]
        o=runrow(a,ident,n,r,line,doc(acts,units=units),mode='ordinary transmission; explicit route/graph diagnostics')
        if n==1:
            route=o['results'][0];a.eq('route eligibility',route is not None,yes(r['exists']))
            delivered=any('hello%c' in t for t in inbox(o,130));a.eq('actual distant receiver',delivered,yes(r['exists']))
            if route:a.eq('origin-directed path',route['path'],[10,20])
        elif n==2:
            result=o['results'][0]
            a.eq('source route path',None if result is None else result['path'],expected)
            if result:
                a.eq('stored path depth',result['best'],len(expected))
                a.true('bounded traversal',0<result['iterations']<=100001)
            if s=='A-B-D-B-two-matching-relay-channels':a.eq('duplicate candidates retained',result['candidates'],[10,20,20,40])
        else:
            targetid=units[-1]['character'];expectedheader=''
            if r['mode']=='DI' and len(units)>2:expectedheader='{R-path:'+'/'.join(f'[{u["contact_id"]}]-h:000' for u in units[1:-1])+'} '
            a.eq('exact delivered route/bearing/title',inbox(o,targetid),['[A:000] '+expectedheader+'<Ops> hello%c'])
            a.true('ordinary send succeeds',o['results'][-1]['ok'])
    return a.save()

if __name__=='__main__':run()
