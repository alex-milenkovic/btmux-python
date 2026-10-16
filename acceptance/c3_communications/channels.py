from . import step,unit,eq
from systems import communications as r


@step(r'frequency input (.+)')
def frequency_input(w,value):w['input']=value

@step(r'the frequency setter runs')
def frequency(w):
    value=w['input']
    if value.endswith('-no-map'):unit(w).map=None;value=value.removesuffix('-no-map')
    w['result']=r.set_frequency(unit(w),'' if value=='blank' else value)
    w['assert_observation']=frequency_result

def frequency_result(w,expected):
    if expected.startswith(('A-frequency','B-frequency')):
        eq(w['result']['ok'],True)
        eq(unit(w).freq[ord(expected[0])-65],int(expected.split('frequency')[1]))
    else:
        errors={'channel-error':'Invalid channel-letter!','invalid-frequency':'Invalid frequency!',
                'negative-error':'Are you trying to kid me?','frequency-range-error':'Invalid frequency - range is from 0 to 999999.',
                'missing-equals':'Missing =!','invalid-input':'Invalid input!'}
        eq(w['result'],dict(ok=False,error=errors[expected]))

@step(r'title value (.+)')
def title_input(w,value):w['input']=value

@step(r'the title setter writes channel A')
def title(w):
    value={'empty':'','leading-space-Alpha':'   Alpha'}.get(w['input'],w['input'])
    w['result']=r.set_title(unit(w),'a='+value)

@step(r'stored title and response are (.+)')
def title_result(w,expected):
    value={'Alpha-and-set-to-set-to-Alpha':'Alpha','all15-stored':'123456789012345',
           'first15-stored-full16-echoed':'1234567890123456','cleared':'','Alpha-leading-whitespace-stripped':'Alpha'}[expected]
    eq(unit(w).chantitle[0],value[:15]);eq(w['result']['ok'],True)
    eq(w['result']['message'],f'Channel A title set to set to {value}.' if value else 'Channel A title cleared.')

@step(r'mode input (.+) with capabilities (.+)')
def mode_input(w,value,capabilities):
    u=unit(w);u.radio_type=2+16*{'all':7,'NODIGITAL':8,'no-relay':6,'no-info':5,'no-scan':3}[capabilities]
    u.freqmodes[0]=2;w['input']=value

@step(r'channel A mode is set')
def mode(w):
    w['result']=r.set_mode(unit(w),'a='+('' if w['input']=='empty' else w['input']))
    w['assert_observation']=mode_result

def mode_result(w,expected):
    if expected.endswith('old-mode-retained'):
        eq(w['result']['ok'],False);eq(unit(w).freqmodes[0],2);return
    values={'analog0':0,'digital1':1,'mode31-flagsIUES':31,'mode97-color-g':97,'mode289-bright-x':289,
            'digital1-suffix-ignored':1,'scan16':16,'mute2':2}
    eq(w['result']['ok'],True);eq(unit(w).freqmodes[0],values[expected])
    if 'flagsIUES' in expected:assert '(flags:IUES)' in w['result']['message']

@step(r'radio display state (.+)')
def display_state(w,value):w['input']=value

@step(r'the source listing color helper or frequency setter runs')
def display(w):
    state=w['input'];u=unit(w)
    if state.startswith(('DI','DU')):
        value={'DI-color-r-S':'DIrS','DI-color-r':'DIr'}.get(state,state)
        r.set_mode(u,'a='+value);w['result']=r.list_frequencies(u)[1].split()[1]
    elif state.startswith('ccode-'):
        value={'ccode-none':'','ccode-r':'r','ccode-bright-X':'X'}[state]
        r.set_mode(u,'a='+value);w['result']=r.color_code(u,0)
    elif state.startswith('observer-team'):
        import re
        if state.endswith('-after-ccode-r'):r.set_mode(u,'a=r');r.color_code(u,0)
        w['result']=r.color_code(u,0,True,int(re.search(r'team(\d+)',state)[1]))
    else:
        peer=unit(w,'B');peer.team=2
        peer.freq=[17,17] if not state.startswith('set0') else [0,0]
        peer.freqmodes=[16,16] if 'scan-only' in state else [0,0]
        r.set_frequency(u,'a=0' if state.startswith('set0') else 'a=17')
        w['result']=len(getattr(u,'external_effects',[]))
    w['assert_observation']=display_result

def display_result(w,expected):
    value={'empty':'','two-MechFreqs-log-requests':2,'no-log-request':0}.get(expected,expected)
    eq(w['result'],value)
