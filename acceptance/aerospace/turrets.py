"""Real turret lifecycle, delegated commands and physical weapon isolation."""
from dataclasses import asdict
from unittest.mock import patch
from . import step,eq,near,invoke,position,make_unit,events,messages,check,U,M,S,C
from entities.mech import WeaponState
from entities.crittypes import i2weapon
from entities.weapon import get_weapon
from core.events import EventType as E
from systems import turrets as t
from systems.characters import set_value


def setup(w):
    u=w['u'];u.unit_type=U.DS;u.contact_id='DD';u.in_character=False
    w['target']=make_unit(w,'B');position(w['target'],10,9);w['target'].team=2
    w['parent_target']=make_unit(w,'C');position(w['parent_target'],11,9);w['parent_target'].contact_id='AA';w['parent_target'].team=2
    for peer in (w['target'],w['parent_target']):
        for section in peer.sections:section.armor=section.armor_orig=1000;section.internal=section.internal_orig=1000
    u.target=w['parent_target']._id;u.status|=S.LOCK_TARGET
    w['turret']=t.Turret(_id=40,parent=u._id,gunner=200,arcs=1,target=w['target']._id,lockmode=int(S.LOCK_TARGET))
    w['other_turret']=t.Turret(_id=41,parent=u._id,gunner=201,arcs=1,target=w['target']._id,lockmode=int(S.LOCK_TARGET))
    u.aero_turrets=[40,41]
    for turret in (w['turret'],w['other_turret']):
        w['engine'].register_entity(turret);w['personnel'].add(turret,u._id)
        w['store'].create(turret.gunner,'gunner'+str(turret.gunner),location=turret._id,connected=True)
        actor=w['store'].actor(turret.gunner);w['personnel'].add(actor,turret._id)
        for key,value in {'Build':5,'Reflexes':4,'Intuition':3,'Learn':2,'Gunnery-Laser':7}.items():set_value(w['store'],actor._id,key,value)
    w['actor']=w['store'].actor(200);w['second']=w['store'].actor(201)
    weapon=get_weapon('IS.MediumLaser');u.weapons=[WeaponState(weapon_idx=weapon.index,section=5,critical=0)]
    u.sections[5].criticals[0].type=i2weapon(weapon.index);u.sections[5].criticals[0].data=0
    w['streams']['attack_rolls']=[12]*4
    w['saved']=(u.status,u.target,u.targ_x,u.targ_y,u.targ_z)


def restored(w):
    u=w['u'];return (u.status,u.target,u.targ_x,u.targ_y,u.targ_z)==w['saved']


@step(r'turret fixture (.+)')
def fixture(w,text):
    setup(w);w['fixture']=text;tur=w['turret'];u=w['u'];actor=w['actor'];w['caller']=actor
    if text.startswith('allocate'):tur.gunner=7;tur.targ_z=9
    if 'old-gunner' in text:
        tur.gunner=201
        if 'same-room' in text:w['personnel'].move(201,40)
        if 'disconnected' in text:w['personnel'].update(w['second'],connected=False)
    if 'same-gunner' not in text and text.startswith('initialize') and 'old-gunner' not in text:tur.gunner=-1
    if 'other-caller' in text or 'caller-not-gunner' in text:w['caller']=w['second']
    if any(label in text for label in ('invalid-parent','parent-not-mech')):tur.parent=999
    if 'gunner-minus1' in text:tur.gunner=-1
    if 'gunner-is-parent-pilot' in text:tur.gunner=u.pilot._id;w['caller']=u.pilot


def failure_checks(w,r):
    w['result']=r;message=r.get('message','');ok=r['ok']
    for label,fragment in {'must-leave-or-disconnect':'leave or disconnect','grap-firmer-notice':'grap firmer','not-gunner-refusal':"aren't gunner",'unknown-parent-refusal':'parentage is unknown','not-initialized-refusal':"hasn't been initialized",'not-registered-gunner-refusal':"aren't the registered gunner",'pilot-and-gun-refusal':'pilot and gun','pilot-only-refusal':'only the pilot','arc-control-refusal':"aren't under your control"}.items():check(w,label,not ok and fragment in message)
    check(w,'parent-context-restored',restored(w))


@step(r'the lifecycle command executes')
def lifecycle(w):
    text=w['fixture'];tur=w['turret'];before=asdict(tur)
    if text.startswith(('allocate','free')):
        t.allocate(tur,40,1 if text.startswith('allocate') else 0)
        check(w,'id40',tur._id==40);check(w,'targetXY-minus1',tur.target==tur.targ_x==tur.targ_y==-1);check(w,'gunner7',tur.gunner==7);check(w,'targz9',tur.targ_z==9);check(w,'no-body-effect',asdict(tur)==before);return
    r=invoke(w,t.command,w['engine'],tur,w['caller'],'deinitialize' if text.startswith('deinitialize') else 'initialize');failure_checks(w,r)
    check(w,'new-gunner',tur.gunner==w['actor']._id);check(w,'unchanged',asdict(tur)==before);check(w,'gunner-minus1',tur.gunner==-1)
    check(w,'room-notice',any('initialized as gunner' in line for line in getattr(w['actor'],'inbox',[])))


@step(r'RANGE executes')
def range_run(w):
    r=invoke(w,t.command,w['engine'],w['turret'],w['caller'],'range');failure_checks(w,r)
    check(w,'real-range',r['ok'] and 'range' in r and r['range']>0)


@step(r'an authorized turret has its own target distinct from the parent')
def delegate_fixture(w):setup(w)


@step(r'turret command (\w+) executes through the real command service')
def delegate(w,command):
    w['command']=command;tur=w['turret']
    args={'FIRE':'0','SIGHT':'0','LOCK':'BB','LRS':'m','CRITSTATUS':'Nose'}.get(command,'')
    if command=='ETA':tur.target=-1;tur.targ_x=10;tur.targ_y=9
    w['result']=invoke(w,t.command,w['engine'],tur,w['actor'],command,args)
    r=w['result'];eq(r['ok'],True)
    check(w,'turret-target-bearing',r.get('bearing')==0)
    check(w,'turret-target-range','range' in r and r['range']>0)
    check(w,'turret-target-ETA','Range to hex (10,9)' in r.get('message','') and 'ETA:' in r['message'])
    check(w,'parent-position-center',(r.get('x'),r.get('y'),r.get('z'))==(10,10,0));check(w,'no-overrides',not getattr(w['engine'],'arc_override',0) and not getattr(w['engine'],'pilot_override',0))
    check(w,'real-shot-and-recycle-on-parent-mount',w['target'].damage_taken>0 and w['u'].weapons[0].recycle>0)
    check(w,'turret-target-updated',tur.target==w['target']._id);check(w,'parent-target-retained',w['u'].target==w['parent_target']._id)
    for label,kind in (('actual-long-range-map','lrs'),('actual-surrounding-hex-map','navigate'),('actual-tactical-map','tactical')):check(w,label,r.get('kind')==kind and r.get('cells') and r.get('rows'))
    check(w,'actual-gunner-BTH',r.get('attack',{}).get('bth_breakdown',{}).get('base')==4);check(w,'no-shot',not w['target'].damage_taken and not w['u'].weapons[0].recycle)
    check(w,'actual-parent-sensor-contacts',bool(r.get('contacts',r.get('rows'))))
    check(w,'actual-parent-critical-slots',len(r.get('slots',[]))==12 and r['slots'][0]['number']==1 and 'MediumLaser' in r['slots'][0]['name'] and 'Nose Criticals' in r['message'])
    for label in ('turret-target-report','turret-target-scan'):check(w,label,'BB' in str(r) and w['target'].name in str(r))
    check(w,'actual-parent-status-and-weapons',r.get('status')==int(w['u'].status) and len(r.get('weapons',[]))==1)
    check(w,'actual-parent-weapon-specifications',len(r.get('weapons',[]))==1 and r['weapons'][0].get('spec',{}).get('name')=='IS.MediumLaser')


@step(r'the turret action returns')
def context_run(w):
    text=w['fixture'];u=w['u'];tur=w['turret'];e=w['engine'];actor=w['actor']
    if 'hex-lock' in text:
        r=invoke(w,t.command,e,tur,actor,'lock','12 12 h')
        check(w,'A-XYZ-and-lockmode-updated',tur.target==-1 and (tur.targ_x,tur.targ_y,tur.targ_z)==(12,12,0) and tur.lockmode&S.LOCK_HEX)
    elif 'lock-BB' in text:r=invoke(w,t.command,e,tur,actor,'lock','BB')
    elif 'delegate-error' in text:
        def error(*args):u.target=999;u.status|=S.FIRED;raise ValueError('diagnostic delegate failure')
        caught=False
        try:
            with patch.object(t,'delegate',side_effect=error):invoke(w,t.command,e,tur,actor,'range')
        except ValueError as exc:caught='diagnostic delegate failure' in str(exc)
        r=dict(ok=False,message='delegate failure');check(w,'exception-reported',caught)
    else:
        if 'IC-' in text:
            u.in_character=True
            if 'wizard' in text and 'nonwizard' not in text:
                w['personnel'].update(actor,wizard=True)
                set_value(w['store'],actor._id,'Gunnery-Laser',9);set_value(w['store'],u.pilot._id,'Gunnery-Laser',4)
                w['target'].in_character=True
        if 'invalid-target' in text:tur.target=999
        if 'arcs-exclude' in text:tur.arcs=8;u.unusable_arcs=1
        r=invoke(w,t.command,e,tur,actor,'fire','0')
        if 'same-mount' in text:
            damage=w['target'].damage_taken
            second=invoke(w,t.command,e,w['other_turret'],w['second'],'fire','0')
            check(w,'second-shot-recycle-refusal',not second['ok'] and 'recharg' in second['message'].lower() and w['target'].damage_taken==damage)
            check(w,'B-lock-retained',w['other_turret'].target==w['target']._id)
        if 'parent-fire-after' in text:
            invoke(w,e.run_ticks,int(u.weapons[0].recycle)+2)
            from systems.combat import fire_weapon_number
            shot=invoke(w,fire_weapon_number,e,u,0)
            check(w,'parent-uses-own-lock-and-pilot',shot.bth_breakdown is not None and shot.bth_breakdown.base==4 and w['parent_target'].damage_taken>0)
        check(w,'BTH-uses-gunner2',(r.get('attack',{}).get('bth_breakdown') or {}).get('base')==2)
        check(w,'real-effects-persist',w['target'].damage_taken>0 and u.weapons[0].recycle>0 and u.weap_heat>0)
        check(w,'refusal',not r['ok'])
        check(w,'source-audiences-receive-once',all(sum('You fire ' in msg for msg in getattr(p,'inbox',[]))==1 for p in (u.pilot,actor,w['second'])))
        check(w,'real-shot-count1',w['target'].damage_taken==5)
    failure_checks(w,r)
    check(w,'A-target-BB',tur.target==w['target']._id);check(w,'parent-AA',u.target==w['parent_target']._id);check(w,'no-LOCK-event',not events(w,E.LOCK))
    for label in ('parent-entire-context-restored','parent-status-restored','parent-and-overrides-restored'):
        check(w,label,restored(w))
    for label in ('both-overrides0','overrides-cleared','no-leaked-override'):check(w,label,e.arc_override==e.pilot_override==0)


@step(r'uninitialized turret with parent missing receives (\w+)')
def inactive(w,name):setup(w);w['turret'].parent=-1;w['turret'].gunner=-1;w['command']=name;w['before']=asdict(w['turret'])


@step(r'the registered inactive command executes')
def inactive_run(w):w['result']=invoke(w,t.command,w['engine'],w['turret'],w['actor'],w['command'])


@step(r'the observation is silent with no state or shot change')
def inactive_assert(w):eq(w['result'],dict(ok=True,messages=[]));eq(asdict(w['turret']),w['before']);eq(w['target'].damage_taken,0)
