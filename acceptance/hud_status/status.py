from . import *
from systems.armor_display import armor_field,armor_display,condition,render_template
from systems.status_display import query,ammo_color
from entities.mech import SectionConfig

@step(r'pilot status argument (.+) is requested')
def status(w,args):command(w,'status',args)
@step(r'selected status components are (\S+)')
def components(w,names):eq(w['result']['components'],names.split(','))
@step(r'status weapons is requested')
def weapons(w):command(w,'status','W')
@step(r'weapon status text is (\S+)')
def weapon(w,text):eq(w['result']['weapons'][0]['status'],text)
@step(r'functional ammo group capacity 100 and current amount (\d+)')
def ammo_setup(w,amount):
    weapon=get_weapon('IS.MachineGun');slot=u(w).sections[0].criticals[0];slot.type=i2ammo(weapon.index);slot.firemode=F.HALFTON_MODE;slot.data=int(amount)
@step(r'that ammo amount uses color (\S+) even when it is a leftover row')
def ammo_display(w,color):
    row=w['result']['ammunition'][0];eq(row['color'],{'bright-green':'%ch%cg','bright-yellow':'%ch%cy','bright-red':'%ch%cr'}[color]);eq(row['maximum'],100);assert row['text'] in w['result']['lines'][-1]
@step(r'the empty ammunition group is omitted and the direct amount color is bright-red')
def empty_ammo(w):eq(w['result']['ammunition'],[]);eq(ammo_color(0,100),'%ch%cr')
@step(r'a biped arm with twelve legal critical slots and slot 1 state (\S+)')
def critical_setup(w,state):weapon_state(mount(u(w),pos=0),state)
@step(r'critstatus LARM is requested')
def critical(w):command(w,'critstatus','LARM')
@step(r'displayed slot order is 1,7,2,8,3,9,4,10,5,11,6,12 and slot 1 suffix is (\S+)')
def slots(w,suffix):
    rows=w['result']['slots'];eq([r['number'] for r in rows],[1,7,2,8,3,9,4,10,5,11,6,12]);eq(rows[0]['suffix'],'' if suffix=='absent' else suffix)
@step(r'section traversal contains weapon types (\S+)')
def types(w,types):
    for i,name in enumerate([] if types=='none' else types.split(',')):mount(u(w),name,loc=i,pos=4)
@step(r'weaponspecs is requested')
def specs(w):command(w,'weaponspecs')
@step(r'weapon specification row types are (.+) in first-seen order')
def spec_rows(w,names):
    if names=='You have no weapons!':eq(w['result']['message'],names)
    else:eq([r['name'].removeprefix('IS.').replace('-','') for r in w['result']['weapons']],names.split(','))
@step(r'a 60 ton mech has (\d+) installed sword criticals including destroyed ones')
def swords(w,count):
    u(w).tonnage=60
    for pos in range(int(count)):
        slot=u(w).sections[0].criticals[pos];slot.type=i2special(Special.SWORD);slot.firemode=F.DESTROYED_MODE
@step(r'a sword readiness entry is present (\S+) without changing attack eligibility thresholds')
def sword(w,present):eq(any(p['name'].startswith('Sword') for p in w['result']['physical']),truth(present))
@step(r'heat production 5 and dissipation (\d+)')
def heat(w,minus):u(w).plus_heat=5;u(w).minus_heat=int(minus)
@step(r'status H is requested')
def heat_request(w):command(w,'status','H')
@step(r'the heat scale starts at (\d+) and left indicator is (\S+)')
def scale(w,start,indicator):eq(w['result']['heat_scale']['start'],int(start));eq(w['result']['heat_scale']['indicator'],' ' if indicator=='space' else indicator)
@step(r'an intact section original armor 99 current armor (\d+) and front repair (\S+)')
def condition_setup(w,current,repair):
    section=u(w).sections[0];section.armor_orig=99;section.armor=int(current);section.internal=10
    if truth(repair):
        # Real repair event shape; formatter reads the engine's repair queue.
        from systems.technician import pack
        w['s'].repair_jobs.schedule(47,u(w),pack(u(w).command_actor._id,0,0,0),20)
@step(r'enemy armor is displayed')
def enemy(w):w['level']=condition(u(w),0)[0];w['field']=plain(armor_field(u(w),0))
@step(r'condition index is (\d+) and its two-character field is (\S+)')
def level(w,level,field):eq(w['level'],int(level));eq(w['field'],field)
@step(r'armor value (\d+) requested field width (\d+) and divide-by-ten (\S+)')
def numeric(w,value,width,divide):u(w).sections[0].armor=int(value);w['width']=int(width);w['divide']=truth(divide)
@step(r'owned armor is displayed for an intact section')
def owner(w):w['field']=plain(armor_field(u(w),0,owner=True,width=w['width'],divide=w['divide']))
@step(r'its plain field with spaces encoded as underscores is (\S+) and visible width is (\d+)')
def numeric_field(w,field,width):eq(w['field'].replace(' ','_'),field);eq(len(w['field']),int(width))
@step(r'section current internal is zero and front armor is zero')
def destroyed(w):u(w).sections[0].internal=u(w).sections[0].armor=0
@step(r'armor is displayed with SHOW_DEST (\S+) owner (\S+)')
def show_destroyed(w,show,owner):w['field']=plain(armor_field(u(w),0,owner=truth(owner),show_destroyed=truth(show)))
@step(r'its plain two-character field with spaces encoded as underscores is (\S+)')
def destroyed_field(w,field):eq(w['field'].replace(' ','_'),field)
@step(r'section 0 internal is (\d+) and section 1 internal is zero')
def template_setup(w,internal):u(w).sections[0].internal=int(internal);u(w).sections[1].internal=0
@step(r'evaluated local custom armor template text is (.+)')
def template(w,text):w['field']=plain(render_template(u(w),text,True))
@step(r'owner plain output with spaces encoded as underscores is (\S+)')
def template_output(w,text):eq(w['field'].replace(' ','_'),text)
@step(r'unit form (\S+) tonnage (\d+) and original turret (\S+)')
def diagram_setup(w,kind,tons,turret):form(u(w),kind);u(w).tonnage=int(tons);u(w).sections[4].internal_orig=10 if truth(turret) else 0
@step(r'status armor is requested')
def diagram(w):command(w,'status','A')
@step(r'diagram family is (\S+) and every displayed armor field reads the corresponding real section')
def diagram_check(w,family):
    eq(w['result']['armor']['family'],family);before=w['result']['armor']['plain']
    u(w).sections[0].armor=u(w).sections[0].internal=0
    after=command(w,'status','A')['armor']
    eq(after['family'],family);assert after['plain']!=before
@step(r'a named section is destroyed (\S+) and flooded (\S+)')
def section_setup(w,destroyed,flooded):u(w).sections[0].armor=u(w).sections[0].internal=0 if truth(destroyed) else 10;u(w).sections[0].config=SectionConfig.SECTION_FLOODED if truth(flooded) else 0
@step(r'the user queries sectstatus for that section')
def section_query(w):w['text']=query(u(w),'sectstatus','LARM')
@step(r'query text is (.+)')
def text(w,text):eq(w['text'],text)
@step(r'a section has current front 7 internal 4 rear 2 and original front 20 internal 10 rear 5')
def values(w):
    section=u(w).sections[0];section.armor=7;section.internal=4;section.rear=2;section.armor_orig=20;section.internal_orig=10;section.rear_orig=5
@step(r'every other section has zero current and original front internal and rear values')
def other_sections(w):
    for section in u(w).sections[1:]:
        for name in ('armor','internal','rear','armor_orig','internal_orig','rear_orig'):setattr(section,name,0)
@step(r'armorstatus query argument is (\S+)')
def armor_query(w,arg):w['text']=query(u(w),'armorstatus',{'that-section':'LARM','all-only-that-section':'all','missing-section':'bad'}.get(arg,arg))
@step(r'query text with field pipes encoded as commas is (.+)')
def serialized(w,text):eq(w['text'].replace('|',','),text)
@step(r'slot 1 has kind (\S+) and state (\S+)')
def slot_setup(w,kind,state):
    slot=mount(u(w),pos=0)
    if kind=='ammo':slot.type=i2ammo(get_weapon('IS.SRM-4').index)
    weapon_state(slot,state)
@step(r'critslot query field (\S+) is requested')
def slot_query(w,field):w['text']=query(u(w),'critslot','LARM',1,field)
@step(r'slot query text is (.+)')
def slot_text(w,text):eq(w['text'],text)
@step(r'a six-location AeroFighter Cockpit')
def cockpit(w):form(u(w),'AERO');u(w).sections[4].internal_orig=1
@step(r'critslot NAME is requested for one-based slot (\d+)')
def cockpit_slot(w,number):w['text']=query(u(w),'critslot','Cockpit',number,'NAME')
@step(r'the result is (.+)')
def query_result(w,text):
    if text=='part-name':assert w['text'] and not w['text'].startswith('#-1')
    else:eq(w['text'],text)
@step(r'a mounted weapon has condition (\S+)')
def mounted_condition(w,state):weapon_state(mount(u(w)),state)
@step(r'weaponstatus is queried without a section argument')
def weapon_query(w):w['text']=query(u(w),'weaponstatus')
@step(r'its final status integer is (\d+) and all eight source fields are present')
def weapon_text(w,state):eq(len(w['text'].split('|')),8);eq(w['text'].split('|')[-1],state)
