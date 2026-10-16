"""Twelve procedure families through fresh public CLI processes.

All network lists, audiences, routes, BTH, impacts, XP and event results are
produced by commands. Diagnostic supplements live in the separate row suites.
"""
from qa.communications.common import *
from qa.communications.routing import radios

class Scenario:
 def __init__(self):self.actions=[];self.labels={};self.rejections=set()
 def add(self,label,action,reject=False):
  self.labels[label]=len(self.actions);self.actions.append(action)
  if reject:self.rejections.add(label)
  return self
 def check(self,a,name,units,identity=None,**kw):
  streams=kw.pop('streams',{});d=doc(self.actions,units=units,streams=combat_streams(**streams),**kw)
  o=a.cli(name,d,identity=identity,mode='ordinary workflow');results={k:o['results'][i] for k,i in self.labels.items()}
  for label,i in self.labels.items():
   result=o['results'][i]
   if self.actions[i]['op']=='command' and isinstance(result,dict) and any(k in result for k in ('ok','accepted')):
    a.eq('command '+label,result.get('accepted',result.get('ok')),label not in self.rejections)
   elif isinstance(result,dict) and result.get('ok') is False:a.true('operation '+label+' '+str(result),False)
  return o,results

def joined(s,names='AB',kind='c3i'):
 for name in names[1:]:s.add('join-'+name,command(kind,name,names[0]*2))
 return s

def arm(u,weapon='IS.MediumLaser',critical=4,section=0):u.setdefault('weapons',[]).append(dict(name=weapon,section=section,critical=critical));return u

def c3units(names='ABCD'):
 return [unit(n,kind='C3',masters=int(n=='A'),at=[3,11 if n=='A' else 5 if n=='B' else 9,0]) for n in names]
def target():return unit('T',ident=90,character=190,kind=None,at=[3,3,0],team=2,facing=180)
def template(kind,reference='',name='A'):return dict(op='template',kind=kind,reference=reference,unit=name)
def attach(name='A',player=110):return dict(op='personnel',kind='attach',unit=name,player=player)
def xp(player=120):return dict(op='character',kind='get',caller=110,target=f'#{player}',name='Comm-Conventional',flag=2)
def snap_peers(s,name='A',kind='c3i'):return s['units'][name]['communications'][kind]['peers']
def mine_count(s):return sum(x['kind']=='MINE' for x in s['maps']['main']['objects'])
def notice_delta(before,after,who):return after['inboxes'][str(who)][len(before['inboxes'][str(who)]):]

def formation(a,name,identity):
 units=c3units('ABCDE');units.append(target());s=Scenario()
 s.add('catalog',template('load','WVR-6R')).add('pilot',attach())
 # Install the five physical master records on the loaded genuine catalog unit.
 s.add('physical-master',dict(op='section',unit='A',value=dict(index=2,slots=[dict(index=i,special='C3_MASTER') for i in range(5)])))
 s.add('recalculate',dict(op='command',unit='A',name='recalculate',args='')).add('startup',command('startup')).add('startup-clock',advance(40))
 joined(s,'ABCD','c3');s.add('full',inspect()).add('fifth',command('c3','E','AA'),True)
 s.add('sight',command('sight',args='1 TT')).add('shot',command('fire',args='1 TT')).add('impact',inspect())
 s.add('detach',command('c3','B','-')).add('recycle',advance(40)).add('second',command('fire',args='1 TT'))
 o,v=s.check(a,name,units,identity,construction={'catalog':True},config={'periodic_updates':True,'extended_gunnery':False,'extended_piloting':False})
 a.eq('four unit ordered owner',snap_peers(v['full'],'A','c3'),[20,30,40]);a.eq('source capacity',v['fifth'].get('ok'),False)
 a.eq('real shared SHORT',v['shot'].get('attack',{}).get('bth_breakdown',{}).get('range_bracket'),'SHORT');a.eq('real peer reference',v['shot'].get('attack',{}).get('bth_breakdown',{}).get('c3_ref'),20)
 a.true('actual damage',v['shot'].get('attack',{}).get('damage_dealt',0)>0);a.eq('detach recomputes MED',v['second'].get('attack',{}).get('bth_breakdown',{}).get('range_bracket'),'MED')
 for who in (110,120,130,140):a.true('real connect inbox '+str(who),any('connect' in x for x in v['full']['inboxes'][str(who)]))
 # Separate normal out-of-range shot; target remains at 3,3, shooter 3,15.
 units=c3units('AB');units[0]['at']=[3,15,0];arm(units[0]);units.append(target());s=joined(Scenario(),'AB','c3');s.add('too-far',command('fire',args='0 TT'),True)
 o,v=s.check(a,name+'-maximum',units);a.eq('real maximum unchanged',v['too-far']['attack']['bth_breakdown']['range_bracket'],'TOFAR')

def membership_loss(a,name,identity):
 units=[unit(n,at=[3,5,0]) for n in 'ABCDEFG'];t=arm(target());t['at']=[3,3,0];t['facing']=180;units.append(t);units[1]['sections'][2]['armor']=0;units[1]['facing']=0
 s=joined(Scenario(),'ABCDEF');s.add('six',inspect()).add('seventh',command('c3i','G','AA'),True)
 s.add('move',command('speed','C','walk')).add('motion',advance(12)).add('stop',command('speed','C','0')).add('moved',inspect())
 s.add('critical-shot',command('fire','T','0 BB')).add('loss',inspect()).add('replacement',command('c3i','G','AA'))
 o,v=s.check(a,name,units,identity,streams={'hit_location_rolls':[8],'critical_rolls':[8],'critical_slot':[0]},config={'periodic_updates':True,'extended_gunnery':False,'extended_piloting':False})
 for n in 'ABCDEF':a.eq('five peers '+n,len(snap_peers(v['six'],n)),5)
 a.true('ordinary movement',v['moved']['units']['C']['fy']!=v['six']['units']['C']['fy']);a.eq('movement keeps membership',snap_peers(v['moved'],'C'),snap_peers(v['six'],'C'))
 a.eq('real critical selected LT',v['critical-shot'].get('attack',{}).get('location'),2);a.true('C3i slot actually destroyed',bool(v['loss']['units']['B']['sections'][2]['slots'][0]['firemode']&C['DESTROYED_MODE']))
 for n in 'ACDEF':a.eq('reciprocal removal '+n,20 in snap_peers(v['loss'],n),False)
 a.eq('replacement now joined',len(peers(o)),5)

def availability(a,name,identity):
 for equipment,cmd in [('Guardian','ecm'),('Angel','angelecm')]:
  units=[arm(unit('A',at=[3,11,0])),unit('B',at=[3,5,0]),target(),unit('E',at=[4,5,0],kind=None,team=2,equipment=[equipment])]
  s=joined(Scenario());s.add('initial',command('sight',args='0 TT')).add('shutdown',command('shutdown','B')).add('stopped',command('sight',args='0 TT')).add('stored',inspect())
  s.add('restart',command('startup','B')).add('boot',advance(40)).add('returned',command('sight',args='0 TT'))
  s.add('ECM-on',command(cmd,'E')).add('ECM-time',advance(2)).add('jammed',command('sight',args='0 TT')).add('ECM-off',command(cmd,'E')).add('clear-time',advance(2)).add('restored',command('sight',args='0 TT'))
  o,v=s.check(a,name+'-'+cmd,units,identity if cmd=='ecm' else None,config={'periodic_updates':True,'extended_gunnery':False,'extended_piloting':False})
  a.eq('stored shutdown membership',snap_peers(v['stored']),[20])
  for label,ref in [('initial',20),('stopped',0),('returned',20),('jammed',-1),('restored',20)]:a.eq(label+' contributor',v[label].get('attack',{}).get('bth_breakdown',{}).get('c3_ref'),ref)
 units=[arm(unit('A',at=[3,11,0])),unit('B',at=[3,5,0]),arm(target())];units[-1]['facing']=180
 s=joined(Scenario());s.add('head-shot',command('fire','T','0 BB')).add('injury',inspect()).add('uncon-range',command('sight',args='0 TT')).add('message',command('c3imessage',args='hello-uncon'))
 s.add('pilot-rejected',command('c3imessage','B','reply'),True).add('recovery',advance(30)).add('awake',inspect()).add('message-after',command('c3imessage',args='hello-awake'))
 o,v=s.check(a,name+'-injury',units,streams={'hit_location_rolls':[12],'character_d6':[1,1,6,6]})
 a.true('real injury unconscious',bool(v['injury']['units']['B']['status']&C['UNCONSCIOUS']));a.eq('unconscious contributes',v['uncon-range']['attack']['bth_breakdown']['c3_ref'],20)
 a.eq('unconscious no inbox',any('hello-uncon' in t for t in inbox(o,120)),False);a.true('recovered inbox',any('hello-awake' in t for t in inbox(o,120)));a.eq('recovered status',state(o,'B')['status']&C['UNCONSCIOUS'],0)

def reports(a,name,identity):
 units=[unit('A',at=[3,11,0]),unit('B',at=[3,5,0],equipment=['Beagle'],sensors=['B','B']),unit('C',at=[4,11,0]),target()]
 # A and C cannot see target beyond weather visibility; B's probe sees through ridge.
 board={'size':[20,20],'mapvis':3,'hexes':[dict(at=[3,4],terrain='GRASSLAND',elevation=3)]}
 # Form while co-located, then move B by ordinary controls into probe range.
 units[1]['at']=[3,10,0]
 s=joined(Scenario(),'ACB');s.add('move-peer',command('speed','B','walk')).add('motion',advance(50)).add('stop',command('speed','B','0')).add('settle',advance(4)).add('before',inspect())
 s.add('network',command('c3inetwork')).add('targets',command('c3itargets')).add('message',command('c3imessage',args='   hello')).add('after',inspect())
 o,v=s.check(a,name,units,identity,map=board,config={'periodic_updates':True,'extended_gunnery':False,'extended_piloting':False})
 a.true('network rows',len(v['network'].get('rows',[]))>=4);a.eq('ordered owner peers',peers(o),[30,20])
 for who in (110,120,130):a.eq('exact once message '+str(who),sum('/You: hello%cn' in t or '/A [AA]: hello%cn' in t for t in inbox(o,who)),1)
 text='\n'.join(v['targets'].get('rows',[]));a.true('peer-only target present','something' in text);a.eq('masked name absent','T ' in text,False)

def channels(a,name,identity):
 units=[unit('A',kind=None),unit('B',kind=None)];s=Scenario()
 for who in 'AB':
  s.add('freq-'+who,command('setchannelfreq',who,'a=123')).add('mode-'+who,command('setchannelmode',who,'a=DIr'))
 s.add('title',command('setchanneltitle',args='a=Alpha')).add('list',command('listchannels')).add('send',command('sendchannel',args='a=hello'))
 s.add('numeric-prefix',command('setchannelfreq',args='a=123tail')).add('zero',command('setchannelfreq',args='a=0')).add('bad-zero',command('setchannelfreq',args='a=00'),True)
 s.add('max',command('setchannelfreq',args='a=999999')).add('overflow',command('setchannelfreq',args='a=1000000'),True).add('restore',command('setchannelfreq',args='a=123'))
 s.add('sixteen',command('setchanneltitle',args='a=1234567890123456')).add('stored-title',inspect()).add('clear-title',command('setchanneltitle',args='a='))
 s.add('analog',command('setchannelmode',args='a=')).add('unknown-prefix',command('setchannelmode',args='a=r?D')).add('A-reject',command('sendchannel',args='A=hello'),True).add('Z-send',command('sendchannel',args='Z=hello')).add('b-send',command('sendchannel',args='b=hello'))
 o,v=s.check(a,name,units,identity);a.eq('title storage15',v['stored-title']['units']['A']['communications']['chantitle'][0],'123456789012345');a.true('raw colored delivery',any(t.startswith('%cr[A:') and '<Alpha> hello%c' in t for t in inbox(o,120)));a.eq('prefix mode commits',comm(o)['freqmodes'][0],64)

def relay(a,name,identity):
 units=radios();s=Scenario();s.add('title',command('setchanneltitle',args='a=Ops')).add('info',command('setchannelmode','C','a=DI'))
 s.add('initial',command('sendchannel',args='a=first'));s.add('disable',command('setchannelmode','B','a=D'));s.add('lost',command('sendchannel',args='a=lost'))
 s.add('restore',command('setchannelmode','B','a=DE'));s.add('shutdown',command('shutdown','B'));s.add('stopped',command('sendchannel',args='a=stopped'));s.add('startup',command('startup','B'));s.add('wait',advance(40));s.add('returned',command('sendchannel',args='a=returned'))
 o,v=s.check(a,name,units,identity);a.eq('exact path-bearing delivery',[t for t in inbox(o,130) if t.startswith('[A:')],['[A:000] {R-path:[BB]-h:000} <Ops> first%c','[A:000] {R-path:[BB]-h:000} <Ops> returned%c']);a.eq('no scrambling draws',[d for d in o['draws'] if d['name'].startswith('radio_')],[])

def scan_xp(a,name,identity):
 units=[unit('A',kind=None),unit('B',kind=None)];units[0]['communications']['freq']=[1000,456];units[1]['communications'].update(freq=[900,456],freqmodes=[16,0]);s=Scenario();s.add('scan',command('sendchannel',args='a='+'m'*20));s.add('retuned',inspect())
 o,v=s.check(a,name+'-scan',units,identity,streams={'radio_number':[20,20]});a.eq('retune920',comm(o,'B')['freq'][0],920);a.eq('scan no payload',any('m'*20 in t for t in inbox(o,120)),False)
 units=[unit('A',kind=None,at=[3,3,0]),unit('B',kind=None,at=[3,103,0])];units[0]['communications']['radio_range']=50;units[1]['communications'].update(radio_range=100,comm=4)
 s=Scenario()
 for tick,delay in [(60,60),(61,1),(121,60),(122,1)]:s.add('clock'+str(tick),advance(delay)).add('send'+str(tick),command('sendchannel',args='a=A')).add('xp'+str(tick),xp()).add('state'+str(tick),inspect())
 s.add('save',dict(op='character',kind='save'))
 o,v=s.check(a,name,units,map={'size':[15,120]},streams={'radio_number':[51,1,3]*4,'radio_roll':[8]*4})
 a.eq('source boundary XP',[v['xp'+str(t)] for t in (60,61,121,122)],[0,1,1,2]);a.eq('source timestamps',[v['state'+str(t)]['units']['B']['communications']['comm_last'] for t in (60,61,121,122)],[0,61,61,122]);a.eq('actual scrambled inbox',inbox(o,120),['(A:000) >%c']*4)
 again=a.cli(name+'-reload',doc([xp()],units=[],characters=[]),storage=OUT/'workflows'/name/'storage',fresh=False,mode='fresh process durable read');a.eq('durable XP',again['results'][0],2)

def mines_recovery(a,name,identity):
 for variant in ('matched','unmatched','invalid','radio0','no-recipient'):
  u=unit('A',kind=None);u['communications']['freqmodes']=[2,2] if variant=='no-recipient' else [0,0]
  if variant=='radio0':u['communications']['radio_range']=0
  s=Scenario().add('before',inspect()).add('send',command('sendchannel',args='A=hello' if variant=='invalid' else 'a=hello'),variant in ('invalid','radio0')).add('after',inspect())
  board={'size':[15,15],'mines':[dict(x=5,y=5,type='COMMAND',strength=10,extra=124 if variant=='unmatched' else 123,creator=10)]}
  o,v=s.check(a,name+'-'+variant,[u],identity if variant=='matched' else None,map=board)
  explode=variant in ('matched','no-recipient');a.eq('actual mine removal',mine_count(o['state']),0 if explode else 1)
  before=sum(x['armor']+x['internal'] for x in v['before']['units']['A']['sections']);after=sum(x['armor']+x['internal'] for x in state(o)['sections']);a.eq('actual damage',after<before,explode)
 u=unit('A',kind=None,radio=1);s=Scenario().add('failure',dict(op='diagnose',unit='A',kind='generic-failure',options={'part_type':-2})).add('failed',inspect()).add('refused',command('sendchannel',args='a=x'),True).add('29',advance(29)).add('before-boundary',inspect()).add('30',advance(1)).add('send',command('sendchannel',args='a=recovered'))
 o,v=s.check(a,name+'-recovery',[u],streams={'failure_generic_chance':[42],'failure_reliability':[100],'failure_outcome':[5],'failure_recovery_upper':[40],'failure_recovery_delay':[30]})
 a.eq('source recovery event',[(e['kind'],e['deadline']) for e in v['failed']['events'] if e['kind']=='MRECOVERY'],[('MRECOVERY',30)]);a.eq('failed through29',v['before-boundary']['units']['A']['radio_range'],0);a.eq('restored30',state(o)['radio_range'],80)

def audiences(a,name,identity):
 units=[unit('A'),unit('B'),unit('C',kind=None)];chars=[character(110,10),character(111,10),character(120,20),character(130,30)];units[0]['communications']['aero_turrets']=['C']
 s=joined(Scenario());s.add('network',command('c3imessage',args='net'));s.add('channel',command('sendchannel',args='a=channel'));s.add('direct',command('radio',args='BB=direct'));s.add('before',inspect())
 s.add('occupants-out',dict(op='personnel',kind='transfer',origin=10,destination=999,flags=1));s.add('channel-again',command('sendchannel','B','a=after'));s.add('after',inspect())
 o,v=s.check(a,name,units,identity,characters=chars,config={'periodic_updates':False,'arc_override':1,'extended_gunnery':False,'extended_piloting':False})
 for who in (110,111,130):a.true('unit/turret initial audience '+str(who),any('channel%c' in t for t in v['before']['inboxes'][str(who)]))
 for who in (110,111):a.eq('moved occupant absent '+str(who),notice_delta(v['before'],v['after'],who),[])
 a.true('external notify explicitly unapplied',all(not x['applied'] for x in o['state']['external_notification_requests']))

def visibility(a,name,identity):
 for view in ('both','attacker','target','neither','unconscious','blinded','stopped'):
  u=arm(unit('A',kind=None,at=[3,5,0],equipment=['searchlight']));t=target();b=unit('B',kind=None,at={'attacker':[3,7,0],'target':[3,1,0],'neither':[7,4,0]}.get(view,[3,4,0]))
  if view=='unconscious':b['conscious']=False
  if view=='blinded':b['blinded']=True
  if view=='stopped':b['started']=False
  s=Scenario().add('before',inspect()).add('slite',command('slite')).add('slite-time',advance(1)).add('pre-shot',inspect()).add('shot',command('fire',args='0 TT')).add('post-shot',inspect())
  o,v=s.check(a,name+'-'+view,[u,b,t],identity if view=='both' else None,map={'size':[15,15],'mapvis':2})
  messages=[x for x in notice_delta(v['pre-shot'],v['post-shot'],120) if ' hits ' in x or ' fires ' in x]
  a.eq('shot counter exactly1',state(o)['shots_hit']+state(o)['shots_missed'],1)
  a.eq('real visibility audience',len(messages),0 if view in ('neither','unconscious','blinded','stopped') else 1)
  if view=='attacker':a.true('target masked',bool(messages) and 'at something!' in messages[0])
  if view=='target':a.true('attacker masked',bool(messages) and messages[0].startswith('Something'))
 # Real two-unit physical broadcast and real elevated hex fire.
 u=unit('A',kind=None,at=[3,4,0],real=[1024.0750732421875,1128.75,0]);t=target();b=unit('B',kind=None,at=[4,4,0]);s=Scenario().add('before',inspect()).add('punch',command('punch',args='r TT')).add('after',inspect())
 o,v=s.check(a,name+'-physical',[u,b,t]);a.true('physical attack resolved',bool(v['punch'].get('results')));a.true('physical observer text',bool(notice_delta(v['before'],v['after'],120)))
 u=arm(unit('A',kind=None,at=[3,5,0]));s=Scenario().add('lock',command('lock',args='3 3')).add('before',inspect()).add('hex-shot',command('fire',args='0')).add('after',inspect())
 o,v=s.check(a,name+'-hex',[u,b],map={'size':[15,15],'hexes':[dict(at=[3,3],terrain='GRASSLAND',elevation=3)]});a.eq('hex no unit shot counter',state(o)['shots_hit']+state(o)['shots_missed'],0);a.true('hex observer',any('fires' in x for x in notice_delta(v['before'],v['after'],120)))

def transfer_eject(a,name,identity):
 units=[unit('A',kind='C3',masters=1,at=[3,1,0],specials2=C['C3I_TECH'],core={'preferred_contact_id':'ZZ'}),unit('B',kind='C3',at=[3,2,0]),unit('C',at=[3,2,0])];units[0]['sections'][3]['slots']=[dict(index=0,special='C3I')]
 s=joined(Scenario(),'AB','c3');s.add('C3i-join',command('c3i','C','AA')).add('before',inspect()).add('move',command('speed',args='walk')).add('cross',advance(30)).add('after',inspect())
 dmaps=[dict(name='main',id=1000,size=[15,15],flags=1,cf=100,leave_target=1001),dict(name='outside',id=1001,size=[30,30],entrances=[dict(target=1000,x=5,y=10,name='QA hangar')])]
 # doc's default map is removed when explicit maps are supplied by the CLI schema.
 o,v=s.check(a,name,units,identity,maps=dmaps,config={'periodic_updates':True,'extended_gunnery':False,'extended_piloting':False})
 a.eq('ordinary crossed map',state(o)['mapindex'],1001)
 for n,k in [('A','c3'),('B','c3'),('A','c3i'),('C','c3i')]:a.eq('reciprocal boundary '+n+k,state(o,n)['communications'][k]['peers'],[])
 units=[unit('A',kind=None),unit('B',kind=None)];s=Scenario().add('catalog',template('load','WVR-6R')).add('pilot',attach()).add('official',dict(op='personnel',kind='configure',unit='A',values={'official_pilot':110})).add('eject',command('eject')).add('emergency',inspect()).add('tune',command('setchannelfreq','B','a=234567')).add('send',command('sendchannel','mw1001','a=emergency'))
 o,v=s.check(a,name+'-emergency',units,construction={'catalog':True},pilots={'radio_draws':[1234567]});a.eq('independent emergency channel',comm(o,'mw1001')['freq'][0],234567);a.true('actual emergency receiver',any('emergency%c' in t for t in inbox(o,120)))

def boundaries(a,name,identity):
 units=[unit('A',kind=None),unit('B',kind=None,team=2)];units[1]['communications'].update(radio_range=0,status2=C['ECM_DISTURBANCE'],autopilot=900)
 s=Scenario().add('direct',command('radio',args='BB=hello')).add('stopped',command('shutdown','B')).add('direct-stopped',command('radio',args='BB=stopped')).add('no-equals-channel',command('sendchannel',args='a ignored hello')).add('leading-space-channel',command('sendchannel',args=' a=hello'))
 o,v=s.check(a,name,units,identity);a.true('visible enemy radio0 actual delivery',any('radios you' in t and 'hello' in t for t in inbox(o,120)));a.eq('stopped target notice suppressed',any('radios you' in t and 'stopped' in t for t in inbox(o,120)),False);a.eq('unresolved AUTO reset',comm(o,'B')['autopilot'],-1)

RUNNERS=dict(zip(['c3-formation-and-fire','c3i-membership-and-loss','network-availability','network-reports-and-messages','channel-configuration','radio-relay','analog-scan-and-XP','channel-mines-and-recovery','notification-audiences','visibility-broadcasts','map-transfer-and-pilot-radio','presentation-and-boundaries'],[formation,membership_loss,availability,reports,channels,relay,scan_xp,mines_recovery,audiences,visibility,transfer_eject,boundaries]))
def run():
 a=Audit('workflows')
 for ident,n,r,line in rows('workflows'):
  name=r['procedure'];print('WORKFLOW',name,flush=True)
  try:RUNNERS[name](a,name,dict(outline=n,line=line,values=r))
  except Exception as error:
   import traceback
   traceback.print_exc();a.true('workflow completed: '+str(error),False)
 return a.save()
if __name__=='__main__':run()
