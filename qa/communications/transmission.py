"""Independent ordinary radio sends and source arithmetic boundary vectors."""
from qa.communications.common import *

def run():
 a=Audit('transmission')
 for ident,n,r,line in rows('transmission'):
  u=unit('A',kind=None,at=[3,3,0]);b=unit('B',kind=None,at=[3,4,0]);units=[u,b];acts=[];kw={};streams=combat_streams();expected=None
  if n==1:
   s=r['request'];arg=s
   if s=='a=empty':arg='a='
   if s=='a=byte10':arg='a=\n'
   if s=='leading-space-a=hello':arg=' a=hello'
   if s.startswith('a=hello-'):arg='a=hello'
   if s.endswith('stopped'):u['started']=False
   if s.endswith('destroyed'):u['destroyed']=True
   if s.endswith('range0'):u['communications']['radio_range']=0
   if s.endswith('stunned'):acts=[dict(op='schedule',unit='A',callback='unstun_crew_event',delay=30)]
   if s.endswith('frequency0'):u['communications'].update(freq=[0,456],map_ic=True)
   acts += [command('sendchannel',args=arg)]
  elif n==2:
   s=r['condition'];kw['map']={'size':[15,120]}
   if 'two-receiver' in s or 'second-matching' in s:b['communications']['freq']=[123,123]
   if 'first-matching-muted' in s:b['communications']['freqmodes']=[2,0]
   if 'enemy' in s:b['team']=2
   if 'stopped' in s:b['started']=False
   if 'unconscious' in s:b['conscious']=False
   if 'blinded' in s:b['blinded']=True
   if 'destroyed' in s:b['destroyed']=True
   if 'ID2' in s:b['id']=2
   if 'receiver-radio0' in s:b['communications']['radio_range']=0
   if s.startswith('sender-digital'):u['communications']['freqmodes']=[1,0]
   if 'NODIGITAL' in s:b['communications']['radio_type']=242
   distance=80.9 if '80.9' in s else 81 if 'range81' in s else 80 if 'range80-radio80' in s else 50 if 'range50' in s else 1
   b['real']=[1000,1000+distance*322.5,0];u['real']=[1000,1000,0]
   if 'receiver-radio1-' in s:b['communications']['radio_range']=1
   if 'AngelECM' in s:b['communications']['status2']=C['ANGEL_ECM_DISTURBED']
   if 'self-ECM' in s:u['communications']['status2']=C['ECM_DISTURBANCE'];units=[u]
   if s.startswith('observer'):
    u['communications']['freqmodes']=[1,0];b['observer']=True;b['communications'].update(freq=[999,998],status2=C['ECM_DISTURBANCE']);b['real']=[1000,1000,999*322.5]
    if 'muted' in s:b['communications']['freqmodes']=[2,2]
    streams['radio_number']=[1]*100
   acts=[command('sendchannel',args='a=hello')]
  elif n==3:
   kw['map']={'size':[15,120]};s=r['scanner'];freq=int(r['frequency']);length=int(r['length']);scan=int(re.search(r'(\d+)$',s)[1]);b['communications'].update(freq=[scan,456],freqmodes=[16,0]);u['communications']['freq']=[freq,456]
   if s.startswith('digital'):u['communications']['freqmodes']=[1,0]
   if s.startswith('out-of-range'):b['at']=[3,99,0];b['communications']['status2']=C['ECM_DISTURBANCE']
   streams['radio_number']=nums(r['draws']);acts=[command('sendchannel',args='a='+'m'*length)]
  elif n==4:
   s=r['state'];v=r['draws'];message=' ' if r['message']=='space' else r['message'];distance=int(re.search(r'range(\d+)',s)[1]);send=int(re.search(r'send(\d+)',s)[1]) if 'send' in s else 80;recv=int(re.search(r'recv(\d+)',s)[1]) if 'recv' in s else 80
   numbers=[];rolls=[]
   if v=='percent100-roll9-for-each-byte-twice':numbers=[100]*6;rolls=[9]*6
   elif v!='none':
    for token in v.split('-'):
     m=re.fullmatch(r'(chance|percent|sign|delta|roll)(\d+)',token)
     if m:(rolls if m[1]=='roll' else numbers).append(int(m[2]))
   streams.update(radio_number=numbers,radio_roll=rolls);acts=[diag('scramble',message=message,distance=distance,sender_range=send,receiver_range=recv,bth=4,ecm='ECM' in s,digital=int(s.startswith('digital')))]
  elif n==5:
   s=r['workflow']
   if 'tick' in s:
    tick=int(re.search(r'tick(\d+)',s)[1]);last=int(re.search(r'last(\d+)',s)[1]);u['communications']['radio_range']=50;b['communications'].update(radio_range=100,comm=4,comm_last=last);b['at']=[3,103,0];kw['map']={'size':[15,120]}
    if s.startswith('clear'):b['at']=[3,4,0]
    if '-OOC-' in s:b['in_character']=False
    streams.update(radio_number=[51,1,3],radio_roll=[8]);acts=[advance(tick),command('sendchannel',args='a=A'),dict(op='character',kind='save')]
   elif 'mine' in s:
    kw['map']={'size':[15,15],'mines':[dict(x=5,y=5,type='COMMAND',strength=10,extra=123 if 'matching-' in s and 'unmatched' not in s else 124,creator=10)]};units[0]['at']=[5,5,0];units[1]['at']=[6,5,0];acts=[inspect(),command('sendchannel',args='a=hello')]
   elif 'autopilot' in s:
    b['communications']['autopilot']=900
    if not s.startswith('missing'):kw['objects']=[dict(name='auto',id=900,type='AUTO')]
    if s.startswith('valid'):acts=[dict(op='personnel',kind='transfer',origin=-1,destination=20)]
    acts += [command('sendchannel',args='a=hello')]
   else:
    u['radio']=1;streams.update(failure_generic_chance=[42],failure_reliability=[100],failure_outcome=[5],failure_recovery_upper=[40],failure_recovery_delay=[30]);acts=[dict(op='diagnose',unit='A',kind='generic-failure',options={'part_type':-2}),inspect(),command('sendchannel',args='a=hello'),advance(29),inspect(),advance(1),command('sendchannel',args='a=hello')]
  else:
   s=r['condition'];arg='BB=hello'
   if s=='visible-enemy-radio0-ECM':b['team']=2;b['communications'].update(radio_range=0,status2=C['ECM_DISTURBANCE'])
   if s=='visible-target-stopped':b['started']=False
   if s=='sender-stopped':u['started']=False
   if s=='sender-observer':u['observer']=True
   if s=='sender-crew-stunned':acts=[dict(op='schedule',unit='A',callback='unstun_crew_event',delay=30)]
   if s=='no-LOS':acts=[cache('A','B','invisible')]
   if s=='wrong-separator':arg='BB hello'
   if s=='one-letter-target':arg='B=hello'
   if s=='three-letter-target':arg='BBB=hello'
   acts += [inspect(),command('radio',args=arg)]
  o=runrow(a,ident,n,r,line,doc(acts,units=units,streams=streams,**kw),mode='ordinary command' if n!=4 else 'source arithmetic diagnostic');last=o['results'][-1];want=r['observation']
  if n==1:
   allowed=any(t in want for t in ('send','allowed')) and not any(t in want for t in ('error','inoperative'))
   a.eq('source command gate',last.get('ok'),allowed)
   if allowed:
    a.true('mine consumer reached','mines' in last);a.true('actual self text',any(('=hello' if s=='leading-space-a=hello' else 'hello')+'%c' in t for t in inbox(o)))
   if 'Zero' in want:a.true('separate zero-frequency request',any(x['service']=='ZeroFrequencies' and x['applied'] for x in state(o)['external_effects']))
  elif n==2:
   a.true('sender accepted',last.get('ok'));who=110 if 'self-ECM' in s else 120
   received=[t for t in inbox(o,who) if 'hello%c' in t];allowed=want not in ('inbox-suppressed','skipped','no-normal-delivery','not-delivered','no-observer-message')
   a.eq('real recipient once',len(received),int(allowed))
   if allowed and 'second-channel' in want:a.true('selected second channel','(B:' in received[0])
   if allowed and want=='first-eligible-channel-only':a.true('selected first channel','(A:' in received[0])
   if 'observer-message-once'==want:a.true('observer header',any(':123>' in t for t in received))
  elif n==3:
   m=re.search(r'frequency(\d+)',want);expected=int(m[1]) if m else scan;a.eq('actual retuned frequency',comm(o,'B')['freq'][0],expected)
   a.eq('no payload on scanned send',any('m'*length in t for t in inbox(o,120)),False)
   a.eq('ordered source scan draws',[v['value'] for v in o['draws'] if v['name']=='radio_number'],nums(r['draws']))
   if m:a.true('accuracy notification',any(want.split('-')[1] in t for t in inbox(o,120)))
  elif n==4:
   text,xp=want.split(';');text={'greater-than-symbol':'>','exclamation':'!'}.get(text,text);a.eq('exact bytes and XP marker',last,[text,xp=='xp1']);a.eq('percentage/sign/delta order',[d['value'] for d in o['draws'] if d['name']=='radio_number'],numbers);a.eq('source Roll outcomes',[d['value'] for d in o['draws'] if d['name']=='radio_roll'],rolls)
  elif n==5:
   if 'tick' in s:
    granted=want.startswith('CommXP');a.eq('source timestamp',comm(o,'B')['comm_last'],tick if granted else int(re.search(r'last(\d+)',s)[1]));skills=o['state']['characters']['120']['categories']['skills'];a.eq('persisted real skill XP','ComCon:4,1' in skills,granted)
   elif 'mine' in s:
    before=[x for x in o['results'][0]['maps']['main']['objects'] if x['kind']=='MINE'];after=[x for x in o['state']['maps']['main']['objects'] if x['kind']=='MINE'];a.eq('mine consumed',len(after),0 if 'actual-' in want else len(before));a.eq('actual explosion callback',last['mines']>0,'actual-' in want)
   elif 'autopilot' in s:
    if s.startswith('missing'):a.eq('unresolved AUTO reset',comm(o,'B')['autopilot'],-1)
    else:a.true('channel executed or deferred parser explicit',any(x['service']==('AI' if s.startswith('wrong') else 'autopilot parser') and x['applied']==s.startswith('wrong') for x in state(o,'B')['external_effects']))
   else:
    a.eq('radio failed',o['results'][1]['units']['A']['radio_range'],0);a.eq('preboundary remains failed',o['results'][4]['units']['A']['radio_range'],0);a.error(o['results'][2],'inoperative');a.eq('restored source range',state(o)['radio_range'],80);a.true('postboundary send',last.get('ok'))
  else:
   allowed=want in ('sender-and-target-delivery','sender-only-delivery-no-AUTO-reply','send-allowed');a.eq('direct source gate',last.get('ok'),allowed)
   if allowed:
    a.true('sender real inbox',any("You radio" in t for t in inbox(o)));a.eq('target STARTED audience',any('radios you' in t for t in inbox(o,120)),s!='visible-target-stopped');a.eq('no reply without AUTO',events(state(o,'B'),'AUTO_REPLY'),[])
 return a.save()
if __name__=='__main__':run()
