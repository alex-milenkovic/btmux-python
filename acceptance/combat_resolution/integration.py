"""Complete combat workflows through commands, the event clock and real effects."""
from . import step,session,unit,eq
from tools.combat_resolution import CombatSession
from entities.mech import Location as L,FireMode as F,Specials


def command(w,name,args=(),who='u'):
    result=session(w).action(dict(op='command',unit=who,name=name,args=list(args)))
    w.setdefault('commands',[]).append(result)
    return result


def advance(w,seconds):session(w).action(dict(op='advance',seconds=seconds))


def ready(w,records=None,**extra):
    doc=dict(actions=[],units=records or [{'name':'u','at':[3,3,0]},{'name':'v','at':[3,2,0],'team':2}])
    doc.update(extra)
    w['combat_session']=CombatSession(doc)
    session(w).streams.update(attack_rolls=[12]*30,hit_location_rolls=[7]*500,physical_location=[3]*500,
        damage_entry=[7]*500,pilot_rolls=[12]*500,dfa_rolls=[12]*30,unjam_rolls=[12]*30,
        critical_rolls=[7]*100,crittable_chance=[1]*100,missile_pre_roll=[3]*100,missile_cluster=[12]*100)
    for u in session(w).units.values():
        for sec in u.sections:sec.armor=sec.armor_orig=sec.rear=sec.rear_orig=200;sec.internal=sec.internal_orig=100


def gun(name,section='CT',mode=0):return dict(name=name,section=section,fire_mode=mode,metadata={'crits':1})
def ammo(name):return [{'weapon':name,'rounds':30}]


@step(r'the documented end-to-end fixture for (\S+)')
def fixture(w,workflow):
    w['workflow']=workflow
    if workflow=='spotted-artillery':
        ready(w,[{'name':'u','at':[3,3,0],'artillery':0,'weapons':[gun('IS.Sniper')],'ammo':ammo('IS.Sniper')},
                 {'name':'v','at':[3,1,0],'team':2},{'name':'s','contact_id':'SS','at':[4,3,0]}])
    elif workflow=='TIC-artillery-coordinates':
        ready(w,[{'name':'u','at':[3,3,0],'artillery':0,'weapons':[gun('IS.Sniper'),gun('IS.Sniper','RT')],'ammo':ammo('IS.Sniper')},
                 {'name':'v','at':[3,1,0],'team':2}])
    elif workflow=='RAC-jam-unjam-fire':
        ready(w,[{'name':'u','at':[3,3,0],'gunnery':0,'weapons':[gun('IS.RotaryAC/5',mode=F.RAC_SIXSHOT_MODE)],'ammo':ammo('IS.RotaryAC/5')},
                 {'name':'v','at':[3,2,0],'team':2}])
        session(w).streams['attack_rolls']=[2,12]
    elif workflow=='stealth-enable-lock-fire':
        ready(w,[{'name':'u','at':[3,3,0],'gunnery':0,'weapons':[gun('IS.MediumLaser')]},
                 {'name':'v','at':[3,1,0],'team':2,'specials2':1,'equipment':['Guardian']}],config={'lock_tick':2})
    elif workflow=='jump-DFA':ready(w,[{'name':'u','at':[3,3,0],'jump_mp':3,'jump_speed':32.25},{'name':'v','at':[3,2,0],'team':2}])
    elif workflow=='movement-mine':ready(w,map={'mines':[{'x':3,'y':2,'type':'Standard','strength':8}]})
    elif workflow=='pod-ECM-remove':
        ready(w,[{'name':'u','class':'GROUND','at':[3,3,0],'sections':[{'index':'FSIDE','specials':8}]},
                 {'name':'v','at':[3,2,0],'team':2}])
    else:raise AssertionError(workflow)


@step(r'its user commands and normal event clock run')
def run(w):
    workflow=w['workflow']
    if workflow=='spotted-artillery':
        eq(command(w,'spot',['SS'],'s')['accepted'],True)
        eq(command(w,'lock',['3','1','H'],'s')['accepted'],True)
        eq(command(w,'lock',['-'])['accepted'],True)
        eq(command(w,'spot',['SS'])['accepted'],True)
        eq(command(w,'fire',['0'])['accepted'],True)
        eq(len(session(w).map.projectiles),1);eq(unit(w,'v').damage_taken,0)
        advance(w,10)
    elif workflow=='TIC-artillery-coordinates':
        command(w,'addtic',['0','0-1'])
        command(w,'firetic',['0','3','1'])
        eq(len(session(w).map.projectiles),2)
        advance(w,10)
    elif workflow=='movement-mine':
        eq(command(w,'speed',['32.25'])['accepted'],True)
        for _ in range(30):
            advance(w,1)
            if unit(w).damage_taken:break
        command(w,'speed',['0'])
    elif workflow=='jump-DFA':
        eq(command(w,'jump')['accepted'],True)
        for _ in range(40):
            advance(w,1)
            if not unit(w).is_jumping:break
    elif workflow=='RAC-jam-unjam-fire':
        eq(command(w,'fire',['0'])['accepted'],False)
        eq(unit(w).sections[L.CTORSO].criticals[0].brand>>4,6)
        eq(command(w,'unjamammo',['0'])['accepted'],True)
        advance(w,60)
        eq(unit(w).sections[L.CTORSO].criticals[0].brand>>4,0)
        eq(command(w,'rac',['0','1'])['accepted'],True)
        eq(command(w,'fire',['0'])['accepted'],True)
    elif workflow=='stealth-enable-lock-fire':
        eq(command(w,'stealtharmor',who='v')['accepted'],True)
        advance(w,30)
        command(w,'lock',['-'])
        eq(command(w,'fire',['0','01'])['accepted'],False)
        eq(command(w,'lock',['01'])['accepted'],True)
        eq(command(w,'fire',['0'])['accepted'],False)
        advance(w,2)
        eq(command(w,'fire',['0'])['accepted'],True)
    elif workflow=='pod-ECM-remove':
        from systems.ecm import any_ecm_disturbed
        advance(w,2);eq(any_ecm_disturbed(unit(w)),True)
        eq(command(w,'shutdown')['accepted'],True)
        eq(command(w,'removepods')['accepted'],True)
        advance(w,60)
        eq(command(w,'startup')['accepted'],True)
        advance(w,2)


@step(r'observable result is (\S+) with real damage heat and event observations')
def observed(w,result):
    u=unit(w);snap=session(w).snapshot()
    if result in ('delayed-area-impact','all-selected-shells-queued'):
        eq(len(snap['map']['projectiles']),0)
        eq(len(snap['map']['artillery_impacts']),2 if result=='all-selected-shells-queued' else 1)
        assert unit(w,'v').damage_taken>0
    elif result=='contact-damage':
        assert u.damage_taken>0
        eq(snap['map']['mines'][0]['strength'],5)
    elif result=='landing-impact-and-recycle':
        eq(u.is_jumping,False);eq(u.last_dfa_result.hit,True)
        assert unit(w,'v').damage_taken>0 and u.damage_taken>0
        assert u.sections[L.LLEG].recycle>0
    elif result in ('jam-cleared-then-shot','range-and-stable-lock-enforced'):
        eq(u.shots_fired,1);assert unit(w,'v').damage_taken>0
        assert u.weap_heat>0
    elif result=='field-recomputed-by-normal-update':
        from systems.ecm import any_ecm_disturbed
        eq(any_ecm_disturbed(u),False)
        eq(u.sections[2].specials&8,0)
    else:raise AssertionError(result)
    assert snap['time']>0 and session(w).draws


@step(r'a fixture requiring (\S+)')
def missing(w,dependency):
    w['dependency']=dependency
    records=[{'name':'u','at':[3,3,0],'in_character':True,'weapons':[gun('IS.MediumLaser')]},
             {'name':'v','at':[3,2,0],'team':2,'in_character':True}]
    ready(w,records)
    if dependency=='mine-object-script':command(w,'addmine',['3','3','Trigger','1','42'])


@step(r'the corresponding combat workflow reaches that dependency')
def blocked(w):
    dependency=w['dependency']
    if dependency=='persistent-occupant-transfer':session(w).action(dict(op='diagnose',unit='v',kind='destroy-section',options={'section':'HD'}))
    elif dependency=='persistent-character-XP':command(w,'fire',['0'])
    elif dependency=='mine-object-script':session(w).action(dict(op='diagnose',kind='mine-contact',options={'reason':'step'}))
    elif dependency=='building-object-damage':
        command(w,'lock',['3','1','B']);command(w,'fire',['0'])
    elif dependency=='unavailable-C3-network-formation':command(w,'c3connect',['01'])


@step(r'unavailable effect is explicitly not applied and workflow remains blocked')
def unavailable(w):
    needles={'persistent-occupant-transfer':'tele_contents','persistent-character-XP':'persistent character XP',
        'mine-object-script':'AMINETRIGGER','building-object-damage':'building objects','unavailable-C3-network-formation':'C3 network formation'}
    effects=[e for u in session(w).units.values() for e in getattr(u,'external_effects',[])]
    matching=[e for e in effects if needles[w['dependency']] in e['service']]
    assert matching,effects
    eq([e['applied'] for e in matching],[False]*len(matching))
    w['blocked_effects']=matching
