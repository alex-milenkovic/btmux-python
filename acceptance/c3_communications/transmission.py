import re
from . import step,unit,eq,quiet,draws,inbox
from .displays import view
from .routing import position
from systems import communications as radio,mines
from entities.mech import MechStatus as S,CritStatus as C
from core.events import EventType


def radios(w):
    a,b=unit(w),unit(w,'B');w['map'].mechs_on_map[:]=[a,b]
    for p in (a,b):p.radio_range=80;p.freq=[17,17];p.freqmodes=[0,0];p.comm=4
    position(a,0);position(b,1)
    return a,b


def stun(w,a):w['engine'].events.schedule(30,EventType.UNSTUN_CREW,lambda e:None,a)

@step(r'sendchannel request (.+)')
def send_fixture(w,text):
    a,b=radios(w);w['request']=text;request=text
    for suffix in ('-stopped','-destroyed','-radio-range0','-crew-stunned','-IC-frequency0'):request=request.removesuffix(suffix)
    if text.endswith('-stopped'):a.status&=~S.STARTED
    if text.endswith('-destroyed'):a.status|=S.DESTROYED
    if text.endswith('-radio-range0'):a.radio_range=0
    if text.endswith('-crew-stunned'):stun(w,a)
    if text.endswith('-IC-frequency0'):a.freq[0]=0;w['map'].in_character=True
    if request=='a=empty':request='a='
    if request=='a=byte10':request='a=\n'
    if request=='leading-space-a=hello':request=' a=hello'
    w['text']=request
    # Actual command mines are evidence that the send reaches its lifecycle call.
    w['mine']=mines.map_add_mine(w['map'],'90 25 COMMAND 1 '+str(a.freq[0]))

@step(r'the ordinary command executes')
def send_run(w):w['result']=quiet(w,radio.send_channel,unit(w),unit(w).pilot,w['text']);w['assert_observation']=send_result

def send_result(w,expected):
    r=w['result'];text=r.get('error','')
    errors={'format-error':'Invalid format!','gear-inoperative':'inoperative','stunned-error':'stunned','control-character-error-no-mine-check':'No control characters'}
    if expected in errors:
        eq(r['ok'],False);assert errors[expected] in text,text;assert w['mine'] in w['map'].mines;return
    eq(r['ok'],True);eq(r['mines'],1);assert w['mine'] not in w['map'].mines
    sent=r['deliveries'];assert sent,sent
    if expected=='channel1-send-and-mine-check':eq(sent[0]['channel'],0) # Reception picks the first matching channel, independently of send index.
    assert ('=hello' if 'equals-hello' in expected else 'hello') in sent[0]['text']
    if expected=='ZeroFrequencies-channel-and-send':assert any(e['service']=='ZeroFrequencies' and e['applied'] for e in unit(w).external_effects)

@step(r'transmission condition (.+)')
def transmission_fixture(w,text):
    a,b=radios(w);w['condition']=text
    if 'digital' in text:a.freqmodes[0]=1
    if text=='first-matching-muted-second-matching':b.freqmodes[0]=2
    if 'enemy' in text:b.team=2
    if 'stopped-receiver' in text:b.status&=~S.STARTED
    if 'unconscious' in text:b.status|=S.UNCONSCIOUS
    if 'blinded' in text:b.status|=S.BLINDED
    if 'destroyed' in text:b.status|=S.DESTROYED
    if 'ID2' in text:b._id=2
    if 'receiver-radio0' in text:b.radio_range=0
    if 'NODIGITAL' in text:b.radio_type=242
    distance=80.9 if 'range80.9' in text else 81 if 'range81' in text else 80 if 'range80-' in text else 50 if 'range50' in text else 999 if 'range999' in text else 1
    position(b,distance)
    if 'receiver-radio1-' in text:b.radio_range=1
    if 'receiver-AngelECM' in text:b.status2|=0x800
    if 'self-ECM' in text:a.status2|=4
    if text.startswith('observer'):
        b.crit_status|=C.OBSERVATORIC;b.freq=[999,998]
        if 'ECM' in text:b.status2|=4
        if 'muted' in text:b.freqmodes=[2,2]

@step(r'channel A sends hello')
def transmission_run(w):w['result']=quiet(w,radio.transmit,unit(w),0,'hello');w['assert_observation']=transmission_result

def transmission_result(w,expected):
    rows=[r for r in w['result'] if r['unit']==unit(w,'B')._id];messages=inbox(w,'B')
    if expected in ('skipped','no-normal-delivery','not-delivered','no-observer-message'):eq(rows,[]);eq(messages,[])
    elif expected=='inbox-suppressed':eq(len(rows),1);eq(rows[0]['recipients'],[]);eq(messages,[])
    elif expected=='self-echo':eq(len(inbox(w,'A')),1);eq(rows,[])
    else:
        eq(len(messages),1);eq(len(rows),1);assert 'hello' in messages[0],messages
        eq(rows[0]['channel'],1 if expected=='second-channel-only' else 0)
        if expected=='observer-message-once':eq(rows[0]['observer'],True);assert '<:AA:17>' in messages[0],messages

@step(r'analog message length (\d+) frequency (\d+) scanner (.+) and draws (.+)')
def scanner_fixture(w,length,frequency,scanner,stream):
    a,b=radios(w);a.freq[0]=int(frequency);b.freq=[int(re.search(r'(\d+)$',scanner)[1]),901];b.freqmodes=[16,0]
    if scanner.startswith('digital'):a.freqmodes[0]=1
    if scanner.startswith('out-of-range'):position(b,999);b.status2|=4
    w['text']='x'*int(length);w['stream']=[] if stream=='none' else list(map(int,stream.split(',')))

@step(r'an unmatched receiver scans')
def scanner_run(w):w['result']=draws(w,w['stream'],radio.transmit,unit(w),0,w['text']);w['assert_observation']=scanner_result

def scanner_result(w,expected):
    messages=inbox(w,'B')
    if expected in ('no-scan','unchanged-no-detection'):eq(messages,[]);eq(unit(w,'B').freq[0],900)
    else:
        frequency=int(re.search(r'frequency(\d+)',expected)[1]);eq(unit(w,'B').freq[0],frequency);eq(len(messages),2)
        accuracy=expected.split('-')[1];assert accuracy in messages[-1],messages
        eq([row for row in w['result'] if row['unit']==unit(w,'B')._id],[])

@step(r'message (.+) and scramble state (.+) with draws (.+)')
def scramble_fixture(w,message,state,stream):
    w['text']=' ' if message=='space' else message
    numbers=dict(re.findall(r'(range|send|recv|bth)(\d+)',state))
    w['arguments']=dict(distance=int(numbers.get('range',1)),sender_range=int(numbers.get('send',80)),receiver_range=int(numbers.get('recv',80)),bth=int(numbers.get('bth',0)),digital=int(state.startswith('digital')),under_ecm='ECM' in state)
    w['stream']=[] if stream=='none' else [100,9]*6 if stream=='percent100-roll9-for-each-byte-twice' else list(map(int,re.findall(r'\d+',stream)))

@step(r'source scrambling executes')
def scramble_run(w):w['result']=draws(w,w['stream'],radio.scramble_message,w['text'],**w['arguments'])

@step(r'text and XP marker are (.+)')
def scramble_result(w,text):
    message,xp=text.split(';xp');message={'greater-than-symbol':'>','exclamation':'!'}.get(message,message);eq(w['result'],(message,bool(int(xp))))

@step(r'radio workflow (.+)')
def workflow(w,text):
    a,b=radios(w);w['workflow']=text
    if text.startswith(('scrambled','clear')):
        a.radio_range=50;position(b,100 if text.startswith('scrambled') else 1)
        b.in_character='-OOC-' not in text;b.comm_last=int(re.search(r'last(\d+)',text)[1]);w['tick']=int(re.search(r'tick(\d+)',text)[1])
        w['before']=dict(w['store'].record(b.pilot._id)['categories'])
    elif 'command-mine' in text:w['mine']=mines.map_add_mine(w['map'],'3 3 COMMAND 2 '+('17' if text.startswith('channel-matching') else '18'));w['armor']=sum(sec.armor for sec in b.sections)
    elif 'autopilot' in text:
        b.autopilot=900
        if not text.startswith('missing'):
            w['store'].create(900,'AI object',location=b._id if text.startswith('valid') else a._id)
            w['world'].add(w['store'].actor(900),b._id if text.startswith('valid') else a._id)
    elif text=='radio-range-recovery':
        from systems.failures import schedule_recovery,radio_recovery
        a.radio_range=0;draws(w,[40,30],schedule_recovery,a,radio_recovery,80)

@step(r'ordinary transmission and time progression execute')
def workflow_run(w):
    a=unit(w);text=w['workflow']
    if 'tick' in w:
        for _ in range(w['tick']):quiet(w,w['engine'].process_tick)
    if text=='radio-range-recovery':
        w['before_send']=radio.send_channel(a,a.pilot,'a=hello')
        for _ in range(30):quiet(w,w['engine'].process_tick)
    w['result']=quiet(w,radio.send_channel,a,a.pilot,'a=hello');w['assert_observation']=workflow_result

def workflow_result(w,expected):
    a,b=unit(w),unit(w,'B');r=w['result']
    if 'XP-' in expected:
        eq(b.comm_last,int(re.search(r'last(\d+)',expected)[1]));changed=w['before']!=w['store'].record(b.pilot._id)['categories'];eq(changed,expected.startswith('CommXP'))
        requests=getattr(b,'xp_requests',[])
        if expected.startswith('CommXP'):assert requests and requests[-1]['applied'] and requests[-1]['producer']=='comm',requests
    elif expected=='actual-detonation-and-mine-state-change':eq(r['mines'],1);assert w['mine'] not in w['map'].mines;assert sum(sec.armor for sec in b.sections)<w['armor']
    elif expected=='mine-retained':eq(r['mines'],0);assert w['mine'] in w['map'].mines
    elif expected=='autopilot-reset-minus1':eq(b.autopilot,-1)
    elif expected=='executed-AI-channel':
        assert any(e['service']=='AI' and e['applied'] for e in b.external_effects)
        assert any(e['source_channel']=='MechAI' and e['applied'] for e in b.channel_requests)
    elif expected.startswith('unapplied'):
        service='AI' if 'AI' in expected else 'autopilot parser';assert any(e['service']==service and not e['applied'] for e in b.external_effects)
    elif expected=='subsequent-send-uses-restored-range':eq(w['before_send']['ok'],False);eq(a.radio_range,80);eq(r['ok'],True);assert inbox(w,'B')
    else:raise AssertionError(expected)

@step(r'direct radio condition (.+)')
def direct(w,text):
    a,b=radios(w);b.contact_id='AB';w['direct']=text;w['text']='AB=hello'
    if text=='visible-enemy-radio0-ECM':b.team=2;a.radio_range=b.radio_range=0;a.status2|=4;b.status2|=4
    if text=='visible-target-stopped':b.status&=~S.STARTED
    if text=='sender-stopped':a.status&=~S.STARTED
    if text=='sender-observer':a.crit_status|=C.OBSERVATORIC
    if text=='no-LOS':view(w,a,b,'invisible')
    if text=='wrong-separator':w['text']='AB x hello'
    if text=='one-letter-target':w['text']='A=hello'
    if text=='three-letter-target':w['text']='ABC=hello'
    if text=='sender-crew-stunned':stun(w,a)

@step(r'radio AB=hello executes')
def direct_run(w):w['result']=radio.directed_radio(unit(w),unit(w).pilot,w['text']);w['assert_observation']=direct_result

def direct_result(w,expected):
    r=w['result']
    if expected in ('reactor-error','observer-error','target-LOS-error','format-error'):
        eq(r['ok'],False);assert {'reactor-error':'Reactor','observer-error':"can't radio",'target-LOS-error':'line of sight','format-error':'Invalid format'}[expected] in r['error'];eq(inbox(w,'A'),[]);eq(inbox(w,'B'),[])
    else:
        eq(r['ok'],True);assert 'You radio' in inbox(w,'A')[-1]
        if expected=='sender-only-delivery-no-AUTO-reply':
            eq(inbox(w,'B'),[]);assert not w['engine'].has_event(EventType.AUTO_REPLY,unit(w,'B'))
        else:assert 'radios you' in inbox(w,'B')[-1]
