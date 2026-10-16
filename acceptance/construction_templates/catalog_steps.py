from data.construction_catalog import identify,source_part,weapon_id,legacy_ammo_id
from data.template_files import find_section
from data import templates as t
from systems.damage_commands import armor_section_from_string,section_names,short_section
from systems.construction_editor import check_data
from . import step,eq,text,unit,part,catalog


@step(r'reference (.+) is identified with the source ordered table')
def identify_ref(w,reference):w['result']=identify(reference)


@step(r'its inferred name is (.+)')
def identified(w,name):eq(w['result'],None if name=='none' else name)


@step(r'source catalog parts policy is ([01]) with Clan support')
def policy(w,parts):w['catalog']=catalog(bool(int(parts)))


@step(r'the unbranded part (.+) is formatted')
def names(w,name):w['result']=w['catalog'].names(source_part(name))


@step(r'short long and very-long forms are (.+) (.+) and (.+)')
def forms(w,short,long,vlong):eq(w['result'],tuple(None if n=='none' else n for n in (short,long,vlong)))


@step(r'part (.+) requests brand (\d+)')
def brand(w,name,level):
    p=source_part(name);b=int(level);w['entry']=(p,b) in w['catalog'].entries;w['result']=w['catalog'].names(p,b)[2]


@step(r'a generated branded entry is ([01]) and get_parts_vlong_name returns (.+)')
def branded(w,entry,name):eq(w['entry'],bool(int(entry)));eq(w['result'],name)


@step(r'the catalog is initialized and the lookup cursor is (-?\d+)')
def cursor(w,cursor):w['cursor']=int(cursor)


@step(r'(short|long|vlong) lookup requests (.+)')
def match(w,form,query):w['result']=w['catalog'].match(form,query,w['cursor'])


@step(r'lookup success is ([01]) and the matched base part is (.+)')
def matched(w,success,name):
    eq(w['result'] is not None,bool(int(success)))
    if w['result'] is not None:eq(w['result']['source_part_id'],source_part(name))
    else:eq(name,'none')


@step(r'the source catalog is initialized')
def initialized(w):eq(bool(w['catalog'].entries),True)


@step(r'packed part (-?\d+) is requested with name selector (.+)')
def packed(w,number,selector):w['result']=w['catalog'].packed_name(int(number),selector)


ERRORS={'INVALID_PART_NUMBER':'#-1 INVALID PART NUMBER','INVALID_NAME_TYPE':'#-1 INVALID NAME TYPE',
        'INVALID_PARTNAME':'#-1 INVALID PARTNAME','PERMISSION_DENIED':'#-1 PERMISSION DENIED'}


@step(r'catalog text is (.+)')
@step(r'the result is (.+)')
@step(r'its result is (-?\d+)')
def catalog_result(w,value):eq(w['result'],int(value) if value.lstrip('-').isdigit() else ERRORS.get(value,value))


@step(r'source helper (.+) resolves (.+)')
def helper(w,helper,value):
    if helper=='FindSpecialItemCodeFromString':w['result']=w['catalog'].special_index(value)
    elif helper=='WeaponIndexFromString':w['result']=w['catalog'].weapon_index(value)
    else:
        w['result']=(legacy_ammo_id if helper=='AmmoIFromString' else weapon_id)(value)


@step(r'its numeric result is (-?\d+)')
def number(w,value):eq(w['result'],int(value))


@step(r'caller wizard is ([01])')
def wizard(w,value):w['wizard']=bool(int(value))


@step(r'catalog command (btpartname|btpartmatch) receives (.+)')
def command(w,name,value):
    if name=='btpartmatch':w['result']=w['catalog'].partmatch(value,w['wizard'])
    else:
        number,form=value.split('/');w['result']=w['catalog'].partname(number,form,w['wizard'])


@step(r'a (.+) unit with all12 slots in section (.+) containing junk type data firemode and ammomode')
def junk(w,kind,section):
    u=unit(w,kind);w['loc']=find_section(u,section)
    for slot in u.sections[w['loc']].criticals:slot.type=403;slot.data=7;slot.firemode=7;slot.ammomode=3


@step(r'default critical filling runs for that section')
def fill(w):t.fill_default_criticals_section(w['unit'],w['loc'])


@step(r'nonempty slot types are (.+) and every data firemode and ammomode is zero')
def layout(w,value):
    expected={} if value=='empty' else {int(pos)-1:part(name) for pos,name in (item.split(':') for item in value.split(','))}
    slots=w['unit'].sections[w['loc']].criticals
    eq({i:s.type for i,s in enumerate(slots) if s.type},expected)
    for slot in slots:eq((slot.data,slot.firemode,slot.ammomode),(0,0,0))


@step(r'a (.+) unit moving by (.+)')
def typed(w,kind,move):unit(w,kind,move)


@step(r'source section text (.+) is resolved')
def section(w,value):w['result']=armor_section_from_string(w['unit'],text(value).replace('_',' '))


@step(r'the zero-based location is (-?\d+)')
def location(w,value):eq(w['result'],int(value))


@step(r'location (\d+) is formatted as a short armor label')
def short(w,loc):w['result']=short_section(w['unit'],int(loc))


@step(r'the label is (.+)')
def label(w,value):eq(w['result'],value)


@step(r'construction data is (allocated|null)')
def data(w,value):w['data']=object() if value=='allocated' else None


@step(r'CheckData is requested')
def checked(w):w['messages']=[];w['result']=check_data(w['data'],w['messages'])


@step(r'success is ([01]) and notification count is (\d+)')
def allocated(w,success,count):eq(w['result'],bool(int(success)));eq(len(w['messages']),int(count))
