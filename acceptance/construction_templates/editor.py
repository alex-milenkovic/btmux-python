from data import templates as t
from entities.mech import Specials as S,FireMode as F,AmmoMode as A,SectionConfig as C
from systems.construction_editor import Editor
from systems.damage_commands import armor_section_from_string
from systems.parts import update_specials
from . import step,eq,text,unit,part,tech


def editor(w):
    if 'editor' not in w:
        e=Editor(70,{'u':w['unit']});e.target='u';w['editor']=e
    return w['editor']


@step(r'an editor has template privilege ([01]) allocated data ([01]) and target (valid|unset|missing)')
def guards(w,privilege,allocated,target):
    e=editor(w);e.allocated=bool(int(allocated));e.target={'valid':'u','unset':-1,'missing':'absent'}[target];w['privilege']=bool(int(privilege))


@step(r'resetcrits is requested')
def reset(w):w['result']=editor(w).execute('resetcrits',privilege=w['privilege'])


@step(r'its outcome is (permission-denied|three-data-errors|set-target-first|defaults-set)')
def guarded(w,outcome):
    result=w['result'];eq(result['ok'],outcome=='defaults-set')
    if outcome=='three-data-errors':eq(len(result['messages']),3)
    elif outcome=='permission-denied':eq(result['messages'],["I'm sorry Dave, can't do that."])
    elif outcome=='set-target-first':eq(result['messages'],['You must set a target first!'])
    else:eq(w['unit'].sections[7].criticals[2].type,part('Cockpit'))


@step(r'an editor targets a unit whose movement is Track')
def tracked(w):unit(w,move='Track');editor(w)


@step(r'(settype|setmove|setradio) receives (.+)')
def select(w,operation,args):w['result']=editor(w).execute(operation,text(args))


@step(r'type and movement become (.+) and (.+)')
def selected(w,kind,move):eq((w['unit'].unit_type,w['unit'].move_type),(t.name_index(t.MECH_TYPES,kind),t.name_index(t.MOVE_TYPES,move)))


@step(r'movement is (.+) and notification count is (\d+)')
def moved(w,move,messages):eq(w['unit'].move_type,t.name_index(t.MOVE_TYPES,move));eq(len(w['result']['messages']),int(messages))


@step(r'editor operation (\w+) receives (.+)')
def operate(w,operation,args):
    w['operation']=operation;w['arguments']=text(args);w['result']=editor(w).execute(operation,text(args))


@step(r'its stored value is (-?[\d.]+)')
def scalar(w,value):
    from systems.construction_editor import SCALARS
    eq(getattr(w['unit'],SCALARS[w['operation']][0]),float(value))


@step(r'an editor targets a Clan unit')
def clan(w):w['unit'].specials=S.CLAN_TECH;editor(w)


@step(r'radio level type and range are (\d+) (\d+) and (\d+)')
def radio(w,level,kind,distance):eq((w['unit'].radio,w['unit'].radio_type,w['unit'].radio_range),tuple(map(int,(level,kind,distance))))


@step(r'a mech center torso has original and current armor20 internal16 rear5')
def torso(w):
    e=editor(w);eq(e.execute('setarmor','CT 20 16 5')['ok'],True)


@step(r'current armor internal rear and original armor internal rear are (\d+) (\d+) (\d+) and (\d+) (\d+) (\d+)')
def torso_result(w,*values):
    sec=w['unit'].sections[4];eq(tuple(getattr(sec,k) for k in ('armor','internal','rear','armor_orig','internal_orig','rear_orig')),tuple(map(int,values)))


@step(r'an editor targets a unit with cargospace0 maxton1')
def cargo(w):w['unit'].car_max_ton=1;editor(w)


@step(r'setcargospace receives (-?\d+) and (-?\d+)')
def setcargo(w,cargo,maximum):w['result']=editor(w).execute('setcargospace',cargo+' '+maximum)


@step(r'accepted is ([01]) stored cargo is (\d+) and maxton is (\d+)')
def cargo_result(w,accepted,cargo,maximum):eq((w['result']['ok'],w['unit'].cargo_space,w['unit'].car_max_ton),(bool(int(accepted)),int(cargo),int(maximum)))


@step(r'an editor targets an intact mech left torso with each critical data7')
def equip(w):
    sec=w['unit'].sections[2];sec.internal=sec.internal_orig=12
    for slot in sec.criticals:slot.data=7
    editor(w)


@step(r'addweap receives (.+)')
def add(w,args):w['result']=editor(w).execute('addweap',text(args))


@step(r'outcome is (.+) and changed slots are (.+) with data7 retained')
def equipped(w,outcome,slots):
    actual=[str(i+1) for i,s in enumerate(w['unit'].sections[2].criticals) if s.type]
    eq(actual,[] if slots=='empty' else slots.split(','))
    eq(w['result']['ok'],outcome.startswith(('added','split')))
    for slot in w['unit'].sections[2].criticals:eq(slot.data,7)
    if outcome=='added-rear-TC-OS':eq(w['unit'].sections[2].criticals[0].firemode,32|16|256)
    if outcome=='split-needs8':assert '8 additional' in w['result']['messages'][0]
    if outcome=='not-enough':assert 'Not enough' in w['result']['messages'][0]
    if outcome=='too-many':assert 'Too many' in w['result']['messages'][0]
    if outcome=='bad-slot-after-writes':assert 'Bad critical' in w['result']['messages'][-1]


def firemask(value):return sum({'none':0,'Halfton':128,'OneShot':256,'RearMount':32,'Jettison':int(F.WILL_JETTISON_MODE)}[n] for n in value.split('+'))
def ammomask(value):return sum({'none':0,'AP':8192,'LBX':1,'Precision':65536,'Caseless':262144,'Smoke':32,'MML_LRM':int(A.MML_LRM_MODE)}[n] for n in value.split('+'))


@step(r'a mech slot contains an AC5 ammo bin with rounds2 fire mode (.+) and ammo mode (.+)')
def bin_setup(w,fire,ammo):
    slot=w['unit'].sections[2].criticals[0];slot.type=part('Ammo_IS.AC/5');slot.data=2;slot.firemode=firemask(fire);slot.ammomode=ammomask(ammo)
    w['slot']=slot;editor(w)


@step(r'editor (reload|restock) applies (.+)')
def reload(w,operation,flag):
    args=f'IS.AC/5 LT 1 {flag}' if operation=='reload' else 'LT 1';w['result']=editor(w).execute(operation,args)
    eq(w['result']['ok'],True)


@step(r'first-critical fire mode and ammo mode are (.+) and (.+)')
def modes(w,fire,ammo):eq((w['slot'].firemode,w['slot'].ammomode),(firemask(fire),ammomask(ammo)))


@step(r'ammunition rounds are (\d+)')
def rounds(w,value):eq(w['slot'].data,int(value))


@step(r'an ammo-using weapon starts with fire mode (.+) and ammo mode AP')
def firing_setup(w,fire):
    eq(editor(w).execute('addweap','IS.AC/5 LT 1 2 3 4')['ok'],True)
    w['slot']=w['unit'].sections[2].criticals[0];w['slot'].firemode=firemask(fire);w['slot'].ammomode=8192


@step(r'mechrep firemode selects (.+)')
def mode(w,flag):eq(editor(w).execute('firemode','0 '+flag)['ok'],True)


@step(r'an editor targets a (.+) and the chosen slot has fire7 ammo3')
def special_setup(w,kind):
    u=unit(w,kind);editor(w)
    for sec in u.sections:sec.criticals[0].firemode=7;sec.criticals[0].ammomode=3


@step(r'addspecial places (.+) in (.+) slot1 with data (-?\d+)')
def special(w,name,section,value):
    w['loc']=armor_section_from_string(w['unit'],section);w['part']=name
    w['result']=editor(w).execute('addspecial',f'{name} {section} 1 {value}')


@step(r'stored data is (-?\d+) and immediate consequence is (.+) with fire7 ammo3 retained')
def special_result(w,value,effect):
    eq(w['result']['ok'],True);u=w['unit'];s=u.sections[w['loc']].criticals[0]
    eq((s.data,s.firemode,s.ammomode),(int(value),7,3));eq(s.type,part(w['part']))
    if effect.endswith('CASE'):eq(bool(u.sections[3 if effect=='aft-CASE' else w['loc']].config&C.CASE_TECH),True)
    elif effect=='Artemis-tech':eq(bool(u.specials&S.ARTEMIS_IV_TECH),True)
    elif effect=='TC-tech':eq(bool(u.specials2&0x1000000),True)
    elif effect=='Angel-tech':eq(bool(u.specials2&0x1000),True)
    else:assert effect in ('type-empty','type-HeatSink','split-reference')


@step(r'a (.+) of50 tons with tech (.+) has (\d+) slots of (.+) with condition (intact|destroyed)')
def threshold(w,kind,base,count,name,condition):
    u=unit(w,kind);tech(u,base)
    from entities.crittypes import crits_in_loc
    slots=[s for loc,sec in enumerate(u.sections) for s in sec.criticals[:crits_in_loc(u,loc)]]
    for slot in slots[:int(count)]:slot.type=part(name);slot.firemode=F.DESTROYED_MODE if condition=='destroyed' else 0


@step(r'update_specials (?:runs|recomputes derived technology)')
def update(w):update_specials(w['unit'])


@step(r'the derived (.+) flag is ([01])')
def derived(w,name,enabled):
    flags={'FF':('specials',S.FF_TECH),'ES':('specials',S.ES_TECH),'MASC':('specials',S.MASC_TECH),
      'BAP':('specials',S.BEAGLE_PROBE_TECH),'ECM':('specials',S.ECM_TECH),'Angel':('specials2',0x1000),
      'Bloodhound':('specials2',0x800),'TC':('specials2',0x1000000),'TSM':('specials',S.TRIPLE_MYOMER_TECH)}
    field,flag=flags[name];eq(bool(getattr(w['unit'],field)&flag),bool(int(enabled)))


@step(r'an editor targets a (.+) with zero tech flags')
def tech_setup(w,kind):unit(w,kind);editor(w)


@step(r'outcome is (Clan-set|Angel-set|invalid-no-change|nothing-set|invalid-unit|swarm-set)')
def tech_result(w,outcome):
    u=w['unit'];eq(w['result']['ok'],not outcome.startswith('invalid'))
    eq((int(u.specials),int(u.specials2),u.infantry_specials),{'Clan-set':(32,0,0),'Angel-set':(0,4096,0),'swarm-set':(0,0,1)}.get(outcome,(0,0,0)))


@step(r'a mech has CASE TSM MASC ECM and infantry Swarm with corresponding slots storing data7')
def deletion(w):
    u=w['unit'];u.specials=S.TRIPLE_MYOMER_TECH|S.MASC_TECH|S.ECM_TECH;u.infantry_specials=1;u.sections[2].config=C.CASE_TECH
    for slot,name in zip(u.sections[2].criticals,('CASE','TripleStrengthMyomer','Masc','Ecm')):slot.type=part(name);slot.data=7
    editor(w)


@step(r'the remaining first-table tech and infantry tech are (.+) and Swarm while removed slots retain data7')
def deleted(w,value):
    eq(int(w['unit'].specials),sum({'none':0,'TSM':1,'MASC':16,'ECM':1024}[s] for s in value.split('+')))
    eq(w['unit'].infantry_specials,1)
    removed={'all':{'CASE','TripleStrengthMyomer','Masc'},'case':{'CASE'},'triplemyomertech':{'TripleStrengthMyomer'},'masc':{'Masc'}}.get(w['arguments'].lower(),set())
    for slot,name in zip(w['unit'].sections[2].criticals,('CASE','TripleStrengthMyomer','Masc','Ecm')):
        eq(slot.type,0 if name in removed else part(name));eq(slot.data,7)


@step(r'a mech has (.+) special criticals with ECM flag ([01])')
def distributed(w,layout,ecm):
    u=w['unit'];u.specials=S.ECM_TECH if ecm=='1' else 0
    nss='NSS' in layout;excluded={7} if nss else {4,7}
    if '-LA' in layout:excluded.add(0)
    for loc,sec in enumerate(u.sections):
        if loc in excluded:continue
        for slot in sec.criticals[:1 if nss else 2]:slot.type=part('NullSig_Device' if nss else 'StealthArmor')
    if 'with-ECM-slot' in layout:u.sections[4].criticals[0].type=part('Ecm')


@step(r'NSS and stealth armor are ([01]) and ([01])')
def distributed_result(w,nss,stealth):eq((bool(w['unit'].specials2&16),bool(w['unit'].specials2&1)),(bool(int(nss)),bool(int(stealth))))
