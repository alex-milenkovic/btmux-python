import re
from . import step,unit,eq,quiet
from systems import network_reports as report,c3,notifications as notify
from entities.mech import MoveType as M,UnitType as U,AmmoMode as A,FireMode as F,MechStatus as S,MechStatus2 as S2,CritStatus as C
from entities.weapon import get_weapon
from physics.hexmath import SCALEMAP,FORWARDARC,RSIDEARC,LSIDEARC,REARARC,TURRETARC
from systems.los import MECHLOSFLAG_SEESP,MECHLOSFLAG_SEESS,MECHLOSFLAG_BLOCK


def view(w,observer,target,kind):
    w['map'].losinfo[observer._id,target._id]=0 if kind in ('invisible','unseen') else MECHLOSFLAG_SEESP|MECHLOSFLAG_SEESS|(MECHLOSFLAG_BLOCK if kind=='something' else 0)

@step(r'viewer relation (.+) and NB visibility (True|False)')
def identity_fixture(w,relation,visible):
    a,b=unit(w),unit(w,'B');b.name='Atlas';b.contact_id='AB'
    b.team=2 if relation=='enemy' else 1
    if relation=='invalid-target':b.valid=False
    view(w,a,b,'clear' if visible=='True' else 'something')
    w['relation']=relation

@step(r'Atlas with contact ID AB is identified')
def identify(w):
    w['result']=notify.unit_identity(unit(w,'B')) if w['relation']=='self-GetMechID' else notify.identity(None if w['relation']=='null-viewer' else unit(w),unit(w,'B'))

@step(r'identity text is (.+)')
def identity_result(w,text):eq(w['result'],'' if text=='empty' else text)

@step(r'presentation input (.+)')
def label_fixture(w,text):w['input']=text

@step(r'the source display label is requested')
def label(w):
    text=w['input'];a=unit(w)
    if text.startswith('MOVE_'):w['result']=report.move_type(M[text[5:]])
    else:
        kind,arcs=text.split('-',1);a.unit_type=U[kind]
        flags={'forward':FORWARDARC,'right':RSIDEARC,'left':LSIDEARC,'rear':REARARC,'turret':TURRETARC}
        w['result']=report.arc_label(a,sum(flag for name,flag in flags.items() if name in arcs))

@step(r'label is (.+)')
def label_result(w,text):eq(w['result'],text)

@step(r'ammunition mode (.+)')
def ammo(w,text):
    w['weapon']=get_weapon('IS.NarcBeacon' if text=='NARC-on-NARC-weapon' else 'IS.MediumLaser')
    assert w['weapon'] is not None
    text=text.replace('-on-NARC-weapon','')
    mode=0 if text=='none' else sum(int(getattr(A,name+'_MODE')) for name in text.split('+'))
    slot=unit(w).sections[0].criticals[0];slot.type=w['weapon'].index+1;slot.ammomode=mode

@step(r'description and slot-wrapper ammo letter are displayed')
def ammo_run(w):
    slot=unit(w).sections[0].criticals[0]
    w['result']=(report.ammo_description(w['weapon'],slot.ammomode),report.slot_ammo_letter(unit(w),0,0))

@step(r'description token is (.+) and letter is (.+)')
def ammo_result(w,description,letter):eq(w['result'],('' if description=='empty' else description.replace('leading-space:',' '),' ' if letter=='space' else letter))

@step(r'fire mode (.+)')
def fire(w,text):
    w['mode']=0 if text=='none' else sum(int(getattr(F,(name+'SHOT' if name.startswith('RAC_') else name)+'_MODE')) for name in text.split('+'))
    unit(w).sections[0].criticals[0].firemode=w['mode']

@step(r'model and real slot wrapper are displayed')
def fire_run(w):w['result']=(report.fire_letter(w['mode']),report.slot_fire_letter(unit(w),0,0))

@step(r'letter is (.+)')
def fire_result(w,text):eq(w['result'],tuple([' ' if text=='space' else text]*2))

@step(r'display state (.+)')
def state(w,text):w['state']=text

@step(r'source flags or network report is shown')
def display(w):
    a,b=unit(w),unit(w,'B');s=w['state'];w['assert_observation']=display_result;w['level']=0
    if s.startswith('fallen-'):a.move_type=M[s[7:]];a.status|=S.FALLEN
    elif s=='burning-and-jellied':
        from core.events import EventType
        a.crit_status|=C.JELLIED;w['engine'].events.schedule(20,EventType.VEHICLE_BURN,lambda e:None,a)
    elif s=='light-on-and-illuminated':a.status2|=S2.SLITE_ON;a.crit_status|=C.SLITE_LIT
    elif 'ECM-protected' in s:a.status2|=8|(4 if 'disturbed' in s else 0);w['level']=1 if s.startswith('other') else 0
    elif 'torso' in s:a.status|=S.TORSO_RIGHT|(S.TORSO_LEFT if 'left' in s else 0);w['level']=int(s[5]);a.status&=~S.STARTED if 'shutdown' in s else ~S.NONE
    elif s=='level2-destroyed-shutdown':a.status=S.DESTROYED;w['level']=2
    elif s=='indent3-combat-safe':a.status|=S.COMBAT_SAFE
    elif s.startswith('network-'):
        c3.command(b,b.pilot,'join','AA',False)
        for sec in b.sections:
            for field in ('armor','armor_orig','rear','rear_orig','internal','internal_orig'):setattr(sec,field,0)
        if '33-of100' in s:b.sections[0].armor=33;b.sections[0].armor_orig=100;b.sections[0].internal=2;b.sections[0].internal_orig=3
        w['result']=report.network_data(a,False);return
    elif s.startswith('contacts-'):
        c3.command(b,b.pilot,'join','AA',False)
        # Keep only the relevant report targets; peer B remains a real registered member.
        t=unit(w,'T');t.name='Atlas';t.contact_id='AB';t.status|=S.FALLEN;t.team=2
        for peer in w['units'].values():view(w,a,peer,'invisible');view(w,b,peer,'invisible')
        if s=='contacts-live-ranges3,8-destroyed-range1':
            for name,distance,destroyed in [('T',3,False),('U',8,False),('V',1,True)]:
                peer=unit(w,name);peer.fx=a.fx+distance*SCALEMAP;peer.fy=a.fy;peer.fz=a.fz;peer.name=name;peer.contact_id=name*2
                if destroyed:peer.status|=S.DESTROYED
                view(w,a,peer,'clear')
            # Creating units extends fixture caches, so hide nonparticipants again.
            view(w,a,b,'invisible');view(w,a,unit(w,'C'),'invisible')
        else:
            view(w,a,t,'unseen' if 'own-unseen' in s else 'something')
            view(w,b,t,'clear' if 'network-clear' in s else 'invisible')
        w['result']=report.targets(a,False);return
    elif s=='status3-viewer-spinning-target-stationary':a.crit_status|=C.SPINNING;w['result']=report.status_char(a,b,3);return
    else:raise AssertionError(s)
    w['result']=report.show_flags(a,3 if s.startswith('indent') else 0,w['level'])

def display_result(w,expected):
    rows=w['result'];text='\n'.join(rows) if isinstance(rows,list) else rows
    if expected.endswith('DESTROYED') or expected=='FALLEN':eq(rows,['%cr%ch'+expected.replace('-',' ')+'%cn'])
    elif expected=='one-ON-FIRE-line':eq(rows,['%cr%chON FIRE%cn'])
    elif expected=='SEARCHLIGHT-ON-only':eq(rows,['%cg%chSEARCHLIGHT ON%cn'])
    elif expected=='both-lines-in-source-order':eq(rows,['%cg%chPROTECTED BY ECM%cn','%cy%chAFFECTED BY ECM%cn'])
    elif expected in ('no-private-ECM-line','neither-final-flag'):eq(rows,[])
    elif expected=='both-torso-lines':eq(rows,['Torso is 60 degrees right','Torso is 60 degrees left'])
    elif expected=='SHUTDOWN-without-torso':eq(rows,['SHUTDOWN'])
    elif expected=='three-leading-spaces-before-color':eq(rows,['   %cb%chCOMBAT SAFE%cn'])
    elif expected.startswith('armor'):
        armor,internal=map(int,re.findall(r'\d+',expected));assert f'a: {armor:3d} i: {internal:3d}' in text,text
    elif expected=='destroyed1,live8,live3':eq([re.search(r'\[([a-zA-Z]+)\]',row)[1][0].upper() for row in rows[1:-1]],['V','U','T'])
    elif expected=='identified-name-and-status':assert 'Atlas' in text and 'S:  F  ' in text,text
    elif expected=='something-and-five-blank-statuses':assert 'something' in text and 'S:     ' in text and 'Atlas' not in text,text
    elif expected=='row-omitted':assert '[ab]' not in text.lower(),text
    elif expected=='X':eq(rows,'X')
    else:raise AssertionError(expected)
