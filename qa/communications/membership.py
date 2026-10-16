"""Independent ordered formation, source arrays and distinct availability gates."""
from qa.communications.common import *

def changed(peer,condition):
    values={}
    if condition in ('stopped','unconscious','blinded','destroyed'):
        values['status']={'stopped':0,'unconscious':C['STARTED']|C['UNCONSCIOUS'],'blinded':C['STARTED']|C['BLINDED'],'destroyed':C['STARTED']|C['DESTROYED']}[condition]
    elif condition in ('ECM-disturbed','Angel-disturbed'):values['status2']=C['ECM_DISTURBANCE' if condition=='ECM-disturbed' else 'ANGEL_ECM_DISTURBED']
    elif condition=='wrong-map':values['mapindex']=9999
    elif condition=='no-tech':values['specials2']=0;values['specials']=0
    elif condition=='system-destroyed':values['crit_status']=C['C3I_DESTROYED']
    if values:return [setcomm(peer,**values)]
    if condition=='wrong-team':return [dict(op='configure',unit=peer,values={'team':2})]
    return []

def run():
    a=Audit('membership')
    for ident,n,r,line in rows('membership'):
        kind=r.get('kind','C3i');cmd='c3' if kind=='C3' else 'c3i'
        units=[unit('A',kind=kind,masters=1 if kind=='C3' else 0),unit('B',kind=kind)]
        acts=[];meta={}
        if n==1:
            count=int(r['peers']);masters=int(r['masters'])
            units=[unit(chr(65+i),kind=kind,masters=masters if i==0 else 0) for i in range(count+2)]
            for u in units:u['character']=10000+u['id']
            acts=[command(cmd,chr(66+i),'AA') for i in range(count)]+[inspect(),command(cmd,chr(66+count),'AA')]
        elif n==2:
            cond=r['condition'];arg='AA';actor='B'
            if cond=='two-arguments':arg='AA BB'
            elif cond=='empty-argument':arg=''
            elif cond=='no-own-technology':acts=[setcomm('B',specials=0,specials2=0)]
            elif cond=='own-system-destroyed':acts=[setcomm('B',crit_status=C['C3I_DESTROYED'])]
            elif cond=='own-AngelECM':acts=[setcomm('B',status2=C['ANGEL_ECM_DISTURBED'])]
            elif cond=='already-connected':acts=[command(cmd,'B','AA')]
            elif cond=='target-no-LOS':acts=[dict(op='cache',unit='B',target='A',flags=0)]
            elif cond=='enemy-target':units[0]['team']=2
            elif cond=='self-target':arg='BB';acts=[cache('B','B')]
            elif cond=='destroyed-target':acts=changed('A','destroyed')
            elif cond=='stopped-target':acts=changed('A','stopped')
            elif cond=='target-only-C3':units[0]=unit('A',kind='C3',masters=1)
            elif cond=='intact-target-under-ECM':acts=changed('A','ECM-disturbed')
            elif cond=='destroyed-target-system':acts=changed('A','system-destroyed')
            elif cond.endswith('leave'):
                arg='-'
                if cond=='connected-leave':acts=[command(cmd,'B','AA')]
            acts.append(command(cmd,actor,arg))
            if cond=='intact-target-under-ECM':acts.append(diag('temporary','B',ordinary=False))
        elif n==3:
            units.append(unit('C',kind=kind));seq=r['sequence'].replace('master-','')
            for item in seq.split(';'):
                who=item[0]
                acts.append(command(cmd,who,'-' if item.endswith('leaves') else item[-1]*2))
        elif n==4:
            cond=r['state'];acts=[command('c3i','B','AA')]+changed('B',cond)
            if cond in ('missing','zero-ID'):acts.append(setcomm(c3i_network=[999 if cond=='missing' else 0],c3i_network_size=1))
            acts += [diag('validate',ordinary=False),diag('temporary',ordinary=False),diag('temporary',ordinary=False,check_unconscious=True)]
        elif n==5:
            s=r['state'];kind='C3' if s.startswith('C3-') else 'C3i';cmd=kind.lower()
            if kind=='C3':
                owner=int(re.search(r'master(\d)',s)[1]);names=s.split('peers-')[1].split(';')[0].split(',')
                units=[unit('A',kind='C3',masters=owner)]+[unit(name,ident=20+i*10,kind='C3',masters=1 if name[0]=='M' else 0,contact_id=f'{i+1:02}') for i,name in enumerate(names)]
                acts=[setcomm(c3_network=names,c3_network_size=len(names)),diag('temporary' if 'temporary-trim' in s else 'validate')]
                meta['ids']={u['name']:u['id'] for u in units}
            else:
                units=[unit(chr(65+i)) for i in range(7)]
                prefix,op=s.split(';')[-2:];size=-1 if 'size-negative' in s else int(re.search(r'size(\d+)',s)[1])
                names=['B','C'] if size<0 else prefix.removeprefix('slots-').split(',')
                values=[int(t) if t.lstrip('-').isdigit() else t for t in names]
                acts=[setcomm(c3i_network=values,c3i_network_size=size)]
                if size<0 or op=='clear-local':acts += [setcomm('B',c3i_network=['A'],c3i_network_size=1),setcomm('C',c3i_network=['A'],c3i_network_size=1)]
                if op.startswith('free-'):acts.append(diag('free',ordinary=False,target=op[-1]))
                elif op=='clear-local':acts.append(diag('clear',ordinary=False,propagate=False))
                elif op=='clear-B':acts.append(diag('remove',ordinary=False,target='B'))
                elif op.startswith(('temp-index','other-index')):acts.append(diag('temp-member' if op.startswith('temp') else 'other-member',ordinary=False,index=1))
                else:acts.append(diag('validate',ordinary=False))
        else:
            s=r['condition'];kind='C3i' if s.startswith('C3i') else 'C3';cmd=kind.lower()
            units=[unit('A',kind=kind,masters=1 if kind=='C3' else 0),unit('B',kind=kind)]
            if 'owner-slave' in s:units=[unit('A',kind='C3'),unit('B',kind='C3',masters=1)]
            if 'empty-stored' not in s:acts=[command(cmd,'A' if 'owner-slave' in s else 'B','BB' if 'owner-slave' in s else 'AA')]
            if 'stopped' in s:acts+=changed('B','stopped')
            if 'unconscious' in s:acts+=changed('B','unconscious')
            if 'peer-ECM' in s:acts+=changed('B','ECM-disturbed')
            acts += [inspect(),command(cmd+'message',args='   ' if 'blank-message' in s else '   hello')]
        o=runrow(a,ident,n,r,line,doc(acts,units=units),mode='ordinary joins/messages; explicitly named source-state diagnostics')
        last=o['results'][-1]
        if n==1:
            passed=r['result']=='accepted';a.eq('capacity decision',last.get('ok'),passed)
            if not passed:a.error(last,'maximum capacity')
            before=o['results'][-2]['units'];joiner=units[-1]['name']
            a.eq('final owner peer count',len(peers(o,'A',kind)),count+int(passed))
            a.eq('joiner peer count',len(peers(o,joiner,kind)),count+1 if passed else 0)
            for result in o['results'][:-2]:a.true('prior formation accepted',result.get('ok'))
        elif n==2:
            errors={'argument-error':'Invalid number','technology-error':'not equipped','system-error':'destroyed','operational-error':'not currently operational','already-connected-error':'already in','targetID-error':'valid targetID','unfriendly-error':'unfriendly','self-error':'yourself','target-destroyed-error':'unit is destroyed','target-not-started-error':'not started','target-technology-error':'equipped'}
            want=r['observation'];reply=o['results'][-2] if cond=='intact-target-under-ECM' else last
            if want in errors:a.error(reply,errors[want])
            else:
                a.true('command accepted',reply['ok'])
                if cond=='intact-target-under-ECM':a.eq('stored target',peers(o,'B',kind),[10]);a.eq('temporarily excluded',last,[])
                elif cond=='destroyed-target-system':a.eq('joiner cleaned',peers(o,'B',kind),[]);a.true('source confirmation retained',any('You connect to' in x for x in inbox(o,120)))
                else:a.eq('leave clears owner',peers(o,'B',kind),[]);a.true('leave notice',('not connected' if cond=='disconnected-leave' else 'disconnect') in str(inbox(o,120)))
        elif n==3:
            for part in r['order'].split(';'):
                name,others=part.split(':');want=[] if others=='empty' else [10*(ord(x)-64) for x in others.split(',')]
                a.eq(name+' exact ordered peers',peers(o,name,kind),want)
            a.true('all commands accepted',all(x.get('ok') for x in o['results']))
        elif n==4:
            actual=[20 in o['results'][-3]['peers'],20 in o['results'][-2],20 in last]
            a.eq('stored / targeting / messaging gates',actual,[yes(x) for x in r['inclusion'].split(',')])
        elif n==5:
            want=r['observation']
            if want in ('minus1','minus2','index1'):a.eq('free index',last,{'minus1':-1,'minus2':-2,'index1':1}[want])
            elif want.startswith('null-'):a.eq('source helper boundary',last,None)
            elif kind=='C3':
                expect=[] if 'temporary-empty' in want else [meta['ids'][x] for x in want.split(',')]
                a.eq('trim result',last if isinstance(last,list) else last['peers'],expect)
                if 'temporary-empty' in want:a.eq('stored untouched',peers(o,'A',kind),[20,30])
            else:
                expected={'owner-cleared-peer-entries-retained-negative-prefix':[],'B-only-C-outside-prefix':[20],'B,C-compacted':[20,30],'duplicates-retained':[20,20],'owner-empty-peers-unchanged':[],'C-only':[30]}[want]
                a.eq('source stored result',peers(o),expected)
                if 'peer' in want:
                    a.eq('peer B retained',peers(o,'B'),[10]);a.eq('peer C retained',peers(o,'C'),[10])
        else:
            if 'error' in r['observation']:a.error(last,'no other units' if 'empty-stored' in s else 'what do you want')
            else:
                before=o['results'][-2]['inboxes'];delta=lambda who:inbox(o,who)[len(before.get(str(who),[])):]
                a.eq('exact self echo',delta(110),[f'%ch{kind}/You: hello%cn'])
                a.eq('exact peer delivery',delta(120),[f'%ch{kind}/A [AA]: hello%cn'] if 'leading-spaces' in s else [])
                a.true('message accepted',last['ok'])
    return a.save()

if __name__=='__main__':run()
