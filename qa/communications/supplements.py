"""Source-derived procedure supplements through the public JSON command UI."""
from qa.communications.common import *
from qa.communications.workflows import Scenario, joined, arm, target
from qa.communications.routing import radios

PROCEDURES={
 'flags':'presentation-and-boundaries','statuses':'network-reports-and-messages',
 'colors':'channel-configuration','buffers':'presentation-and-boundaries',
 'reports':'network-reports-and-messages','relay':'radio-relay',
 'scan':'analog-scan-and-XP','passenger':'network-availability',
 'repair':'c3-formation-and-fire'}

def configure(name='A',**values):return dict(op='configure',unit=name,values=values)
def scheduled(callback,name='A'):return dict(op='schedule',unit=name,callback=callback,delay=100)
def bits(*names):return sum(C[n] for n in names)

def flags(a):
 u=unit(kind=None,started=False,fallen=True,hulldown=True)
 u['status']=bits('COMBAT_SAFE','FALLEN','HULLDOWN','TORSO_RIGHT','TORSO_LEFT')
 u['status2']=bits('FORTIFIED','WEAPONS_HOLD','DODGING','EVADING','SPRINTING','ECM_PROTECTED','ANGEL_ECM_PROTECTED','ECM_DISTURBANCE','ANGEL_ECM_DISTURBED','ECM_COUNTERED','STH_ARMOR_ON','NULLSIGSYS_ON','AUTOTURN_TURRET')
 u['crit_status']=bits('SLITE_DEST','SLITE_LIT','JELLIED','HIDDEN','MECH_STUNNED')
 u['communications'].update(tank_crit_status=bits('DUG_IN','DIGGING_IN'),stagger_damage=20)
 for loc in (0,1):u['sections'][loc]['specials']=C['CARRYING_CLUB']
 u['sections'][2]['specials']=bits('NARC_ATTACHED','INARC_HOMING_ATTACHED','INARC_HAYWIRE_ATTACHED','INARC_ECM_ATTACHED')
 acts=[scheduled('mech_movemode_event'),scheduled('mech_sideslip_event'),scheduled('vehicle_extinguish_event'),diag('flags',spaces=2),diag('flags',level=1),diag('flags',level=2)]
 o=a.cli('flags-order',doc(acts,units=[u]),mode='explicit combined source predicates')
 public=['%cb%chCOMBAT SAFE%cn','%ch%cgFORTIFIED%cn','%ch%crWEAPONS HOLD%cn','%cr%chFALLEN%cn','%cg%chHULLDOWN%cn','%cg%chDUG IN%cn','%cgDIGGING IN%cn','%cr%chSTAGGERING%cn','%cr%chSEARCHLIGHT DESTROYED%cn','%cg%chILLUMINATED%cn','%cr%chON FIRE%cn','%ch%cgHIDDEN%c','%ch%crDODGING%c','%ch%crEVADING%c','%ch%crSPRINTING%c','%ch%cyCHANGING MOVEMENT MODE%c','%ch%cySIDESLIPPING%c','%ch%crSTUNNED%c']
 private=['%cg%chPROTECTED BY ECM%cn','%cg%chPROTECTED BY ANGEL ECM%cn','%cy%chAFFECTED BY ECM%cn','%cy%chAFFECTED BY ANGEL ECM%cn','%cy%chCOUNTERED BY ECCM%cn','%cg%chSTEALTH ARMOR ACTIVE%cn','%cg%chNULL SIGNATURE SYSTEM ACTIVE%cn','%cy%chNARC POD ATTACHED%cn','%cy%chINARC HOMING POD ATTACHED%cn','%cy%chINARC HAYWIRE POD ATTACHED%cn','%cy%chINARC ECM POD ATTACHED%cn','%cy%chEXTINGUISHING FIRE%cn','%cg%chTURRET AUTO-TURN ENGAGED%cn','%cg%chCARRYING CLUB - RIGHT ARM%cn','%cg%chCARRYING CLUB - LEFT ARM%cn']
 a.eq('every public/private predicate in source order',o['results'][-3],['  '+v for v in public+private+['SHUTDOWN','Torso is 60 degrees right','Torso is 60 degrees left']])
 a.eq('level1 omits private additions',o['results'][-2],public+['SHUTDOWN']);a.eq('level2 omits final state table',o['results'][-1],public)
 # Swarm predicates resolve actual allocated BSUIT objects and their host IDs.
 units=[unit(kind=None),unit('B',kind=None,**{'class':'BSUIT'}),unit('C',kind=None,team=2,**{'class':'BSUIT'})]
 acts=[configure('B',swarm_target='A'),configure('C',swarm_target='A'),diag('flags'),diag('flags','B'),diag('flags','C')]
 o=a.cli('flags-swarm',doc(acts,units=units),mode='allocated suit/host relationship diagnostics')
 a.eq('enemy and friendly occupants',o['results'][2],['%cr%chSWARMED BY ENEMY SUITS%cn','%cr%chMOUNTED BY FRIENDLY SUITS%cn'])
 a.eq('friendly suit host',o['results'][3],['%cg%chMOUNTED ON FRIENDLY UNIT%cn']);a.eq('enemy suit host',o['results'][4],['%cg%chSWARMING ENEMY UNIT%cn'])


 for movement,label in [('QUAD','%cr%chFALLEN%cn'),('NONE','')]:
  o=a.cli('flags-fallen-'+movement,doc([diag('flags')],units=[unit(kind=None,movement=movement,fallen=True)]))
  a.eq('source fallen movement label',o['results'][0],[label])
 o=a.cli('flags-crew-stun',doc([setcomm(tank_crit_status=C['CREW_STUNNED']),diag('flags')],units=[unit(kind=None)]))
 a.eq('vehicle crew stun predicate',o['results'][-1],['%ch%crSTUNNED%c'])
 o=a.cli('flags-buffer-fit',doc([diag('flags',spaces=2047),configure(status=C['STARTED']|C['COMBAT_SAFE']),diag('flags',spaces=2047)],units=[unit(kind=None)]))
 a.eq('empty maximum indentation fits',o['results'][0],[]);a.true('text plus indentation overflow explicit',o['results'][-1].get('ok') is False)


 acts=[dict(op='schedule',unit='A',callback='vehicle_burn_event',delay=1),advance(1),inspect(),dict(op='schedule',unit='A',callback='vehicle_burn_event',delay=10),dict(op='schedule',unit='A',callback='vehicle_extinguish_event',delay=1),advance(1),advance(10),inspect()]
 o=a.cli('burn-extinguish-deadlines',doc(acts,units=[unit(kind=None)],streams=combat_streams(fire_damage=[1])),mode='real scheduled callbacks and clock; diagnostic ignition')
 for i in (1,5,6):a.true('event clock '+str(i),o['results'][i].get('ok') is not False)
 a.eq('burn callback actual damage',o['results'][2]['units']['A']['sections'][0]['armor'],99)
 a.eq('extinguish cancels subsequent side damage',state(o)['sections'][0]['armor'],99)
 a.eq('only one fire damage draw',[d['value'] for d in o['draws'] if d['name']=='fire_damage'],[1])
 a.eq('no lingering burn or extinguish event',[e for e in o['state']['events'] if e['kind'] in ('VEHICLE_BURN','VEHICLE_EXTINGUISH')],[])


def colors(a):
 acts=[];expected=[]
 for i,char in enumerate('xrgybmcwXRGYBMCW',1):
  acts += [command('setchannelmode',args='a='+char),diag('color')]
  expected.append('%c'+char if i<=8 else '%ch%c') # snprintf into six-byte static buffer
 acts += [command('setchannelmode',args='a='),diag('color')]
 for team in range(1,17):acts.append(diag('color',observer=True,team=team))
 acts += [diag('color',observer=True,team=0),diag('color',observer=True,team=-1),diag('color',observer=True,team=30)]
 o=a.cli('colors-all-static',doc(acts,units=[unit(kind=None)]))
 for i,value in enumerate(expected):a.eq('color '+str(i+1),o['results'][2*i+1],value)
 a.eq('reset ordinary static buffer',o['results'][33],'')
 observer=['%cw','%cc','%cm','%cb','%cy','%cg','%cr']+['%ch%c']*8+['%cw']
 a.eq('observer team table and modulo',o['results'][34:50],observer)
 a.eq('unmatched teams preserve last static value',o['results'][50:],['%cw']*3)


def statuses(a):
 # Each list is source priority order, asserted with all lower-priority flags set.
 specs=[
  (1,'W',dict(swarm_target=10,status=C['STARTED']|C['TOWED'],carrying=10,status2=C['SPRINTING']|C['EVADING']),True),
  (1,'T',dict(status=C['STARTED']|C['TOWED'],carrying=10,status2=C['SPRINTING']|C['EVADING']),True),
  (1,'t',dict(carrying=10,status2=C['SPRINTING']|C['EVADING']),True),
  (1,'C',dict(status2=C['SPRINTING']|C['EVADING']),True),
  (1,'M',dict(status2=C['SPRINTING']|C['EVADING']),False),(1,'m',dict(status2=C['EVADING']),False),
  (2,'D',dict(status=C['DESTROYED'],status2=C['SLITE_ON'],crit_status=C['SLITE_LIT']),False),
  (2,'L',dict(status2=C['SLITE_ON'],crit_status=C['SLITE_LIT']),False),(2,'l',dict(crit_status=C['SLITE_LIT']),False),
  (3,'J',dict(status=C['STARTED']|C['JUMPING']|C['FALLEN']|C['HULLDOWN'],cocoon=1),False),
  (3,'O',dict(status=C['STARTED']|C['FALLEN']|C['HULLDOWN'],cocoon=1),False),
  (3,'F',dict(status=C['STARTED']|C['FALLEN']|C['HULLDOWN']),False),
  (3,'H',dict(status=C['STARTED']|C['HULLDOWN']),False),
  (4,'+',dict(heat=1,crit_status=C['JELLIED']),False),(4,'I',dict(crit_status=C['JELLIED']),False),
  (4,'S',dict(status=0),False),
  (5,'P',dict(status2=bits('ECCM_ENABLED','ECM_ENABLED','ECM_PROTECTED','ECM_DISTURBANCE')),False),
  (5,'E',dict(status2=bits('ECM_ENABLED','ECM_PROTECTED','ECM_DISTURBANCE')),False),
  (5,'p',dict(status2=bits('ECM_PROTECTED','ECM_DISTURBANCE')),False),(5,'e',dict(status2=C['ECM_DISTURBANCE']),False)]
 # Independent reset between diagnostics in one process; no clock/event mutation.
 acts=[];expected=[]
 for col,char,values,club in specs:
  acts += [configure('B',status=C['STARTED'],status2=0,crit_status=0,swarm_target=-1,carrying=-1,cocoon=0,heat=0),dict(op='section',unit='B',value={'index':0,'specials':C['CARRYING_CLUB'] if club else 0}),configure('B',**values),diag('status',target='B',index=col)]
  expected.append(char)
 for team,char in [(1,'n'),(2,'N')]:
  acts += [configure('B',team=team,status2=bits('ECCM_ENABLED','ECM_ENABLED')),dict(op='section',unit='B',value={'index':2,'specials':C['NARC_ATTACHED']}),diag('status',target='B',index=5)]
 o=a.cli('status-precedence',doc(acts,units=[unit(kind=None),unit('B',kind=None,specials=C['ECM_TECH'])]))
 for i,(col,char,_,_) in enumerate(specs):a.eq('status '+str(col)+' priority '+char,o['results'][4*i+3],char)
 a.eq('friendly NARC overrides ECM',o['results'][-4],'n');a.eq('enemy NARC overrides ECM',o['results'][-1],'N')
 # Event-dependent status branches and the viewer-spinning quirk.
 for label,setup,want in [('standing',[command('stand','B')],'f'),('changing-hull',[command('hulldown','B')],'h'),('starting',[command('startup','B')],'s'),('stagger',[setcomm('B',stagger_damage=20)],'G'),('burn',[scheduled('vehicle_burn_event','B')],'B'),('viewer-spin',[configure(crit_status=C['SPINNING'])],'X')]:
  b=unit('B',kind=None,fallen=label=='standing',started=label not in ('starting','stagger'),movement='QUAD' if label=='changing-hull' else 'BIPED')
  col=3 if label in ('standing','changing-hull','viewer-spin') else 4
  o=a.cli('status-'+label,doc(setup+[diag('status',target='B',index=col)],units=[unit(kind=None),b],streams=combat_streams()))
  a.eq('source event status',o['results'][-1],want)


def buffers(a):
 # Widths come from C alloc.h and the explicit local char arrays at each producer.
 u=unit('A'*300,ident=10,character=110,kind=None,contact_id='AA');b=unit('B',kind=None)
 acts=[diag('identity',unit=u['name']),diag('printf',unit=u['name'],message='%s',format_args=['x'*17000]),diag('flags',unit=u['name'],spaces=2048),diag('flags',unit=u['name'],spaces=-1),diag('slot-letters',unit=u['name'],section=2,slot=0),diag('scramble',unit=u['name'],message='x',distance=1,sender_range=0,receiver_range=0),diag('identity',unit=u['name'],null_target=True),diag('color',unit=u['name'],index=2)]
 o=a.cli('buffers-invalid-domains',doc(acts,units=[u,b]))
 a.eq('identity SBUF255',o['results'][0],'A'*255);a.true('printf LBUF16383',('x'*16383) in inbox(o))
 for i in (2,3,4,5,7):a.true('explicit invalid diagnostic '+str(i),isinstance(o['results'][i],dict) and o['results'][i].get('ok') is False)
 a.eq('null target identity',o['results'][6],'')
 u=unit(kind=None);u['communications']['freqmodes']=[1,0];b['communications']['freqmodes']=[1,0]
 acts=[command('setchanneltitle',args='a='+'t'*17000),command('sendchannel',args='a='+'x'*16383),command('sendchannel',args='a='+'x'*16384)]
 o=a.cli('buffers-radio',doc(acts,units=[u,b]));a.eq('title reply LBUF16383',len(o['results'][0]['message']),16383)
 a.eq('delivered final wrapper LBUF16383',len(inbox(o,120)[-1]),16383);a.true('oversized input explicit rejection',o['results'][2].get('ok') is False)


def reports(a):
 units=[unit('A',at=[3,11,0]),unit('B-long-visible-name',ident=20,character=120,at=[3,5,0],contact_id='BB')]
 acts=[command('c3i','B-long-visible-name','AA'),command('c3inetwork'),command('c3itargets')]
 o=a.cli('report-exact-fields',doc(acts,units=units),mode='ordinary command report exact fields')
 row='%ch%cy[bb]B B-long-visib x:  3 y:  5 z:  0 r: 6.0 b:  0 s:  0.0 h:  0 a: 100 i: 100%cn'
 a.eq('network header/body/footer',o['results'][1]['rows'],['C3i Network Status:',row,'End C3i Network Status'])
 a.eq('exact contact fields and five statuses',o['results'][2]['rows'],['C3i Contacts:','PS*[bb]B B-long-visi x:  3 y:  5 z:  0 r: 6.0 c: 6.0 b:  0 s:  0.0 h:  0 S:     ','End C3i Contact List'])
 a.true('all five status characters present','S:     ' in o['results'][2]['rows'][1]);a.true('contact name width11','B-long-visi ' in o['results'][2]['rows'][1])

 # Explicit formatting diagnostic: expanded numeric fields overflow the 100-byte row.
 for section in units[1]['sections']:section.update(armor=255,armor_orig=1,rear=0,rear_orig=0,internal=255,internal_orig=1)
 acts=[command('c3i','B-long-visible-name','AA'),configure('B-long-visible-name',speed=1000000000),dict(op='core',unit='B-long-visible-name',values={'x':32767,'y':32767}),command('c3inetwork')]
 o=a.cli('report-buffer99',doc(acts,units=units),mode='numeric report-width diagnostic')
 expected='%ch%cy[bb]B B-long-visib x:32767 y:32767 z:  0 r: 6.0 b:  0 s:1000000000.0 h:  0 a: 25500 i: 25500%cn'
 a.true('fixture exceeds row buffer',len(expected)>99)
 a.eq('source snprintf row bytes',o['results'][-1]['rows'][1],expected[:99])

 # Natural peer-only clear visibility: weather hides T from A, B has ordinary visual LOS.
 units=[unit('A',at=[3,11,0]),unit('B',at=[3,9,0]),target()]
 s=joined(Scenario()).add('move',command('speed','B','walk')).add('clock',advance(50)).add('stop',command('speed','B','0')).add('sensors',advance(4)).add('targets',command('c3itargets'))
 o,v=s.check(a,'report-peer-only-clear',units,map={'size':[20,20],'mapvis':3},config={'periodic_updates':True})
 a.true('peer-only clear identifies T',any('[TT]' in row and ' T ' in row for row in v['targets']['rows']))


def relay(a):
 for variant in ('enemy','short-range','equal','shortest','stationary','duplicates','cycle'):
  units=radios('ABCD');units[-1]['communications']['freqmodes']=[9,0]
  units[1]['at']=[3,8,0];units[2]['at']=[3,8,0];units[-1]['at']=[3,13,0]
  if variant=='enemy':units[1]['team']=units[2]['team']=2
  if variant=='short-range':units[1]['communications']['radio_range']=units[2]['communications']['radio_range']=4
  if variant=='shortest':units[0]['communications']['radio_range']=10
  if variant=='stationary':units[1]['movement']='NONE';units[1]['started']=False;units[2]['communications']['freqmodes']=[1,0]
  if variant=='duplicates':units[1]['communications'].update(freq=[123,123],freqmodes=[5,5]);units[2]['communications']['freqmodes']=[1,0]
  if variant=='cycle':units[-1]['at']=[3,20,0]
  o=a.cli('relay-ordinary-'+variant,doc([command('sendchannel',args='a=route')],units=units),mode='ordinary transmission on real geometry')
  frames=[x for x in inbox(o,140) if 'route%c' in x]
  if variant in ('enemy','short-range','cycle'):a.eq('no reachable destination',frames,[])
  else:
   path='{R-path:[CC]-h:000} ' if variant=='equal' else '' if variant=='shortest' else '{R-path:[BB]-h:000} '
   a.eq('source route selection',frames,['[A:000] '+path+'route%c'])
 # An actual ECM field around each radio position, with no setup interference flags.
 for endpoint in ('A','B','C'):
  units=radios();units[-1]['communications']['freqmodes']=[9,0];j=unit('E',kind=None,team=2,at=[7 if endpoint=='B' else 4,dict(A=3,B=8,C=13)[endpoint],0],equipment=['Guardian']);units.append(j)
  # Side-offset jammer reaches B while both endpoints remain outside radius6.
  s=Scenario().add('ecm',command('ecm','E')).add('clock',advance(2)).add('send',command('sendchannel',args='a=ecm-route'))
  o,v=s.check(a,'relay-actual-ecm-'+endpoint,units,config={'periodic_updates':True})
  a.true('sender self echo survives',any('ecm-route%c' in x for x in inbox(o)))
  a.eq('only relay ECM is not an endpoint gate',any('ecm-route%c' in x for x in inbox(o,130)),endpoint=='B')


def scan(a):
 units=[unit('A',kind=None),unit('B',kind=None)];units[0]['communications']['freq']=[1000,456];units[1]['communications'].update(freq=[900,800],freqmodes=[16,16])
 o=a.cli('scan-multiple-channels',doc([command('sendchannel',args='a='+'m'*20)],units=units,streams={'radio_number':[20,20,20,20]}),mode='ordinary scanning send')
 a.eq('both scanning channels retuned',comm(o,'B')['freq'],[920,840]);a.eq('once-only scan notice',sum('You notice' in x for x in inbox(o,120)),1)
 a.eq('finite source draw order',[d['value'] for d in o['draws'] if d['name']=='radio_number'],[20,20,20,20])


 for reason in ('disconnected','outside'):
  units=[unit('A',kind=None,at=[3,3,0]),unit('B',kind=None,at=[3,103,0])]
  units[0]['communications']['radio_range']=50;units[1]['communications'].update(radio_range=100,comm=4)
  chars=[character(110,10),character(120,999 if reason=='outside' else 20,connected=reason!='disconnected')]
  acts=[advance(61),command('sendchannel',args='a=A'),dict(op='character',kind='get',caller=110,target='#120',name='Comm-Conventional',flag=2)]
  o=a.cli('XP-ineligible-'+reason,doc(acts,units=units,characters=chars,map={'size':[15,120]},streams={'radio_number':[51,1,3],'radio_roll':[8]}),mode='ordinary analog send; real ineligible character')
  a.eq('child XP remains zero',o['results'][-1],0);a.eq('enclosing radio timestamp still updated',comm(o,'B')['comm_last'],61)
  a.eq('radio Roll consumes exact legal dice',[(d['name'],d['value']) for d in o['draws'] if d['name'].startswith('radio_')],[('radio_number',51),('radio_roll',8),('radio_number',1),('radio_number',3)])


def passenger(a):
 units=[unit('A',conscious=False),unit('B')];chars=[character(110,10),character(111,10,wizard=False),character(120,20)]
 # Public personnel command caller selection retains the real official pilot.
 acts=[command('c3i','B','AA'),dict(op='personnel',kind='configure',unit='A',values={'official_pilot':110}),dict(op='personnel',kind='caller',unit='A',player=111),command('c3imessage',args='passenger'),command('sendchannel',args='a=passenger'),diag('common-checks',flags=C['MECH_USUAL'],actor=111)]
 o=a.cli('passenger-common-checks',doc(acts,units=units,characters=chars),mode='ordinary commands from actual passenger')
 a.eq('pilot-only network command rejects passenger',o['results'][3].get('ok'),False);a.eq('source common checks',o['results'][-1],None);a.true('passenger ordinary radio despite unconscious pilot',o['results'][4]['ok']);a.true('actual peer receives passenger radio',any('passenger%c' in t for t in inbox(o,120)))
 a.eq('pilot-only error is explicit',o['results'][3]['error'],'Now now, only the pilot can push that button.')


def repair(a):
 u=unit(kind=None)
 acts=[dict(op='template',kind='load',unit='A',reference='WVR-6R'),dict(op='section',unit='A',value={'index':2,'slots':[dict(index=i,special='C3_MASTER') for i in range(5)]}),command('recalculate'),dict(op='diagnose',unit='A',kind='slot',options={'section':'LT','slot':0}),diag('masters'),command('repair',args='LT 0'),diag('masters'),inspect()]
 o=a.cli('hardware-real-repair',doc(acts,units=[u],construction={'catalog':True}),mode='catalog load, physical master install, real critical dispatch and repair consumer')
 a.eq('physical before repair',o['results'][4],{'working':0,'total':1});a.true('ordinary repair accepted',o['results'][5].get('accepted'))
 a.eq('physical after repair',o['results'][6],{'working':1,'total':1});a.eq('repaired cached master',state(o)['working_c3_masters'],1)


def run():
 a=Audit('supplements');selected=os.environ.get('QA_COMMS_CASE')
 for name,procedure in PROCEDURES.items():
  if selected and selected not in (name,procedure):continue
  print('SUPPLEMENT',name,flush=True)
  before=len(a.records)
  try:globals()[name](a)
  except Exception as error:
   import traceback
   traceback.print_exc()
   if a.current is None:a.current={'id':name,'checks':[]};a.records.append(a.current)
   a.true('supplement completed '+str(error),False)
  for record in a.records[before:]:record['procedure']=procedure
 return a.save()
if __name__=='__main__':raise SystemExit(bool(run()['failures']))
