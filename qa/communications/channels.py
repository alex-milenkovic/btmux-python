"""Channel parser, raw presentation and external-log source cases."""
from qa.communications.common import *

def run():
    a=Audit('channels')
    for ident,n,r,line in rows('channels'):
        u=unit(kind=None);units=[u];acts=[];expected=None
        if n==1:
            s=r['input'];s='' if s=='blank' else s
            if s.endswith('-no-map'):
                s=s[:-7];u['communications']['mapindex']=-1
            acts=[command('setchannelfreq',args=s)]
        elif n==2:
            s=r['value'];s='' if s=='empty' else ' Alpha' if s=='leading-space-Alpha' else s
            acts=[command('setchanneltitle',args='a='+s)]
        elif n==3:
            caps={'all':7,'NODIGITAL':15,'no-relay':6,'no-info':5,'no-scan':3}[r['capabilities']]
            u['communications'].update(radio_type=caps*16+2,freqmodes=[2,0])
            s='' if r['input']=='empty' else r['input'];acts=[command('setchannelmode',args='a='+s)]
        else:
            s=r['state']
            if s.startswith('set'):
                v=unit('B',kind=None,team=2);units.append(v)
                freq=0 if s.startswith('set0') else 17
                v['communications'].update(freq=[freq,freq],freqmodes=[16,16] if 'scan-only' in s else [0,0])
                acts=[command('setchannelfreq',args='a='+str(freq))]
            elif s.startswith(('ccode','observer')):
                if 'after-ccode-r' in s:acts=[command('setchannelmode',args='a=r'),diag('color')]
                elif s=='ccode-r':acts=[command('setchannelmode',args='a=r')]
                elif s=='ccode-bright-X':acts=[command('setchannelmode',args='a=X')]
                acts.append(diag('color',observer=s.startswith('observer'),team=int(re.search(r'team(\d+)',s)[1]) if 'team' in s else 0))
            else:
                mode={'DI-color-r-S':'DIrS','DI-color-r':'DIr','DI':'DI','DU':'DU'}[s]
                acts=[command('setchannelmode',args='a='+mode),command('listchannels')]
        o=runrow(a,ident,n,r,line,doc(acts,units=units),mode='ordinary settings; explicit color diagnostics')
        result=o['results'][-1];c=comm(o);want=r['observation'] if 'observation' in r else ''
        if n==1:
            if want.startswith(('A-frequency','B-frequency')):
                index=int(want[0]=='B');value=int(want.split('frequency')[1]);a.eq('actual frequency',c['freq'][index],value)
                a.eq('confirmation',result,dict(ok=True,message=f'Channel {want[0]} set to {value}.'))
            else:
                errors={'channel-error':'Invalid channel-letter!','invalid-frequency':'Invalid frequency!','negative-error':'Are you trying to kid me?','frequency-range-error':'Invalid frequency - range is from 0 to 999999.','missing-equals':'Missing =!','invalid-input':'Invalid input!'}
                a.error(result,errors[want]);a.eq('failed setter preserves settings',c['freq'],[123,456])
        elif n==2:
            title=s.lstrip();a.eq('stored title',c['chantitle'][0],title[:15]);a.eq('full response',result['message'],'Channel A title set to set to '+title+'.' if title else 'Channel A title cleared.')
        elif n==3:
            if 'retained' in want:
                a.eq('refused mode unchanged',c['freqmodes'][0],2);a.eq('refusal',result['ok'],False)
                if r['input']=='E':a.error(result,'digital transfer for relay')
                elif r['input']=='I':a.error(result,'digital transfer for transfer info')
                else:a.true('capability error',bool(result['error']))
            else:
                modes={'empty':0,'D':1,'DIUES':31,'Drg':97,'DX':289,'D?S':1,'?D':0,'s':16,'u':2}
                a.eq('source encoded mode',c['freqmodes'][0],modes[r['input']]);a.true('setting accepted',result['ok'])
                if r['input']=='DIUES':a.eq('flag order',result['message'],'Channel A <send> mode set to digital (flags:IUES).')
        else:
            if s.startswith('set'):
                requests=state(o).get('external_effects',[])
                logs=[v for v in requests if 'MechFreqs' in str(v)]
                a.eq('separate frequency logs',len(logs),2 if 'two-enemy' in s else 0)
                a.true('logs not delivered',all(v.get('applied') is False for v in logs))
            elif s.startswith(('ccode','observer')):a.eq('exact static color output',result,'' if want=='empty' else want)
            else:a.eq('listing priority',result['rows'][1].split()[1],want)
    return a.save()

if __name__=='__main__':run()
