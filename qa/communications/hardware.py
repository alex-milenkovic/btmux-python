"""Physical source critical groups, queried windows and lifecycle integration."""
from qa.communications.common import *

def run():
    a=Audit('hardware')
    for ident,n,r,line in rows('hardware'):
        u=unit(kind=None,**{'class':r.get('class','MECH')});units=[u];acts=[];kw={}
        if n==1:
            spec=r['slots'];body=re.sub(r'-(functional|slot\d+-(destroyed|disabled))$','',spec)
            for group in body.split(';'):
                loc,slots=group.split(':');indexes=[]
                for part in slots.split(','):
                    if '-' in part:
                        lo,hi=map(int,part.split('-'));indexes+=list(range(lo,hi+1))
                    else:indexes.append(int(part))
                u['sections'][LOC[loc]]['slots']=[dict(index=i,special='C3_MASTER') for i in indexes]
            bad=re.search(r'slot(\d+)-(destroyed|disabled)',spec)
            if bad:
                for slot in u['sections'][2]['slots']:
                    if slot['index']==int(bad[1]):slot['firemode']=C['DESTROYED_MODE' if bad[2]=='destroyed' else 'DISABLED_MODE']
            acts=[diag('masters')]
        elif n==2:
            s=r['layout'];loc=7 if 'HEAD' in s else 2;query=int(re.search(r'query(\d+)',s)[1]);starts=[]
            if 'no-master' not in s:starts=[4] if loc==7 else [0,1] if 'and1' in s else [0]
            slots=[dict(index=i,type=0) for i in range(12)]
            for i in starts:slots[i]=dict(index=i,special='C3_MASTER')
            bad=re.search(r'slot(\d+)-destroyed',s)
            if bad:slots[int(bad[1])]['firemode']=C['DESTROYED_MODE']
            u['sections'][loc]['slots']=slots;acts=[diag('master-window',section=loc,slot=query)]
        else:
            kind='C3i' if r['network'].startswith('C3i') else 'C3'
            masters=0 if kind=='C3i' or r['network']=='C3-slave' else 2 if 'two-separate' in r['network'] else 1
            units=[unit('A',kind=kind,masters=masters),unit('B',kind=kind,masters=1 if r['network']=='C3-slave' else 0)]
            acts=[command(kind.lower(),'B','AA')]
            if r['network']=='C3-slave':acts=[command('c3','A','BB')]
            if r['action']=='cross-map':
                acts.append(dict(op='map_command',map='other',name='transfer',args='A'))
                kw['maps']=[dict(name='main',id=1000,size=[15,15]),dict(name='other',id=1001,size=[15,15])]
                units[0]['core']={'preferred_contact_id':'ZZ'}
            else:acts.append(dict(op='diagnose',unit='A',kind='slot',options=dict(section=2,slot=0)))
            acts += [diag('validate','A',ordinary=kind=='C3'),diag('validate','B',ordinary=kind=='C3'),diag('masters','A')]
        d=doc(acts,units=units,**kw)
        if 'maps' in kw:d.pop('map',None)
        o=runrow(a,ident,n,r,line,d,mode='physical hardware and explicit critical/map boundary diagnostics')
        if n==1:a.eq('source group count',o['results'][0],dict(total=int(r['total']),working=int(r['working'])))
        elif n==2:a.eq('allocated queried window',o['results'][0],yes(r['result']))
        else:
            a.true('real join accepted',o['results'][0].get('ok'))
            if 'two-separate' in r['network']:
                a.eq('one working master retained',o['results'][-1]['working'],1);a.eq('approved first-hit cache update',state(o)['working_c3_masters'],1);a.eq('remaining connected',peers(o,'A',kind),[20])
            else:
                a.eq('owner detached',peers(o,'A',kind),[]);a.eq('peer detached',peers(o,'B',kind),[])
                if r['action']=='cross-map':a.eq('new map',state(o)['mapindex'],1001)
                else:a.true('source system flag',state(o)['crit_status'] & C['C3_DESTROYED' if kind=='C3' else 'C3I_DESTROYED'])
    return a.save()

if __name__=='__main__':run()
