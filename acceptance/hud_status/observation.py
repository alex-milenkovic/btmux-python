from . import *
from physics.hexmath import find_xy,hex_to_float,FORWARDARC,TURRETARC,LSIDEARC,RSIDEARC,REARARC
from entities.map_objects import add_object,MapObject
from entities.map import GameMap
from systems.observation import status_chars
from unittest.mock import patch
from core.events import EventType


def building(w,x=2,y=5):
    board=GameMap(20,20);board._id=300;board.name='building';board.cf=board.cfmax=100;board.enter_lock='true'
    w['s'].engine.register_entity(board);w['s'].maps['inside']=board
    add_object(u(w).map,4,MapObject(x=x,y=y,obj=board._id));add_object(board,6,MapObject(x=4,y=4,datac=ord('n')))
    w['building']=board;return board

def range_to(w,distance):
    target=t(w);distance=float(distance);target.set_hex_position(2,2+int(distance),0);target.fx,target.fy=find_xy(u(w).fx,u(w).fy,180,distance);visible(w)

@step(r'a visible enemy with name Atlas heat 2 status heated and NB (\S+)')
def hud_contact(w,nb):t(w).name='Atlas';t(w).heat=2;visible(w,truth(nb))
@step(r'its 19-field row name is (\S+) heat is 2 and status contains \+')
def hud_name(w,name):row=records(w)[0];eq(len(row),19);eq(row[4],name);eq(row[17],'2');assert '+'in row[18]
@step(r'contact rows retain map roster order')
def roster(w):eq([r[0] for r in records(w)],['TT'])
@step(r'contact sensor visibility is (\S+) and weapon arcs are (\S+)')
def sensor_arcs(w,sensors,arcs):
    visible(w,sensors={'primary':2,'secondary':4,'both':6,'none':0}[sensors]);w['arcs']=sum({'forward':FORWARDARC,'turret':TURRETARC,'left':LSIDEARC,'right':RSIDEARC,'rear':REARARC}.get(s,0) for s in arcs.split('-'))
@step(r'its sensor string is (\S+) and arc string is (\S+)')
def sensor_arc(w,sensor,arc):
    # Inject only the diagnostic arc flags; dispatch and CSV rendering remain real.
    if sensor=='omitted':eq(records(w),[])
    else:eq(records(w)[0][2],sensor);eq(records(w)[0][1],arc)
@step(r'a linked building with LOS (\S+) invisible (\S+) hidden (\S+) locked (\S+) and safe (\S+) CS (\S+)')
def building_flags(w,los,invisible,hidden,locked,safe,cs):
    b=building(w);b.buildflag=sum(bit for text,bit in [(invisible,16),(hidden,4),(safe,8),(cs,1)] if truth(text));b.enter_lock='false' if truth(locked) else 'true'
    if los=='blocked':u(w).map.set_elevation(2,3,9)
@step(r'the building result is (\S+)')
def building_result(w,expected):eq(records(w)[0][-1] if records(w) else 'omitted',expected)
@step(r'keyed HUD scan fixture range '+N+r' scanner 20 observer (\S+) NB (\S+) and target form (\S+)')
def hud_scan_setup(w,distance,observer,nb,kind):
    range_to(w,distance);u(w).scan_range=20
    if truth(observer):u(w).crit_status|=C.OBSERVATORIC
    form(t(w),kind);visible(w,truth(nb));mount(t(w));w['notices_before']=sum('being scanned' in line for line in getattr(t(w),'movement_messages',[]))
@step(r'keyed HUD asc and wsc target TT are requested separately')
def scans(w):
    w['notices_before']=sum('being scanned' in line for line in getattr(t(w),'movement_messages',[]));w['first']=hud(w,'asc TT');w['middle_notices']=sum('being scanned' in line for line in getattr(t(w),'movement_messages',[]));w['second']=hud(w,'wsc TT')
@step(r'each scan outcome is (.+) and each request produces (\d+) target scan notices')
def scan_outcome(w,outcome,count):
    for result in (w['first'],w['second']):
        if outcome=='list':eq(records(w,'D',result),[['Done']])
        else:eq(result['records'][0]['payload'],outcome)
    eq([w['middle_notices']-w['notices_before'],sum('being scanned' in line for line in getattr(t(w),'movement_messages',[]))-w['middle_notices']],[int(count)]*2)
@step(r'enemy front armor is (\d+) of 99 with intact original internal and a ready weapon with recycle data (\d+)')
def scan_reduction(w,armor,ticks):t(w).sections[0].armor_orig=99;t(w).sections[0].armor=int(armor);mount(t(w)).data=int(ticks)
@step(r'the armor front character is (\S+) and weapon scan status is (\S+)')
def reduced(w,armor,weapon):eq(records(w,result=w['first'])[0][1],armor);eq(records(w,result=w['second'])[0][-1],weapon)
@step(r'contacts near friendly range 2 far enemy range 8 wreck enemy range 1 and an accessible building range 3')
def contact_roster(w):
    t(w).name='near';t(w).team=u(w).team;t(w).set_hex_position(2,4,0)
    for name,y,dead in [('far',10,False),('wreck',3,True)]:
        other=w['s'].add_unit({'name':name,'at':[2,y,0],'team':2})
        if dead:other.status|=S.DESTROYED
        u(w).map.losinfo[u(w)._id,other._id]=7
    building(w)
@step(r'contacts brevity (\d+) filter (\S+) is requested')
def contact_request(w,brief,options):u(w).brief=int(brief);command(w,'contacts',options)
@step(r'the displayed ordered names are (\S+) and ordinary framing is (\S+)')
def contact_names(w,names,framing):eq([r['name'] for r in w['result']['contacts']],names.split(','));eq(w['result']['heading'],truth(framing))
@step(r'target diagnostic status combination (\S+) and viewer spinning (\S+)')
def status_setup(w,states,spin):
    target=t(w);target.status=0;target.status2=0;target.crit_status=0
    if 'started'in states.split('-'):target.status|=S.STARTED
    for word,flag in [('destroyed',S.DESTROYED),('jumping',S.JUMPING),('fallen',S.FALLEN),('hulldown',S.HULLDOWN)]:
        if word in states:target.status|=flag
    if 'swarming'in states:target.swarm_target=u(w)._id
    if 'towed'in states:target.towed_by=u(w)._id
    if 'carrying'in states:target.carrying=u(w)._id
    if 'heat'in states:target.heat=2
    if 'inferno'in states:target.crit_status|=C.JELLIED
    if 'light'in states:target.status2|=0x20
    if 'lit'in states:target.crit_status|=C.SLITE_LIT
    if 'ECM'in states:target.specials|=__import__('entities.mech',fromlist=['Specials']).Specials.ECM_TECH;target.status2|=1
    if 'ECCM'in states:target.status2|=2
    if 'NARC'in states:target.sections[0].specials|=1
    if 'staggering'in states:target.stagger_damage=20
    if 'starting'in states:w['s'].engine.schedule_event(30,EventType.STARTUP,lambda e:None,data=target)
    if 'target-spinning'in states:target.crit_status|=C.SPINNING
    if truth(spin):u(w).crit_status|=C.SPINNING
    visible(w)
@step(r'identified brief contacts are requested')
def brief_contacts(w):u(w).brief=2;command(w,'contacts')
@step(r'the five status columns with blanks encoded as underscores are (\S+)')
def compact(w,text):eq(w['result']['contacts'][0]['status'].replace(' ','_'),text)
@step(r'a same-team contact named LongVisibleName with two-character ID AB heat 2 and NB (\S+)')
def masked_setup(w,nb):t(w).name='LongVisibleName';t(w).contact_id='AB';t(w).team=u(w).team;t(w).heat=2;visible(w,truth(nb))
@step(r'brief legacy HUD contacts h is requested')
def legacy(w):u(w).brief=2;command(w,'contacts','h')
@step(r'legacy row relation is (\S+) displayed ID is (\S+) name field with trailing padding removed is (\S+) and compact status with blanks encoded as underscores is (\S+)')
def legacy_row(w,relation,ident,name,status):
    row=w['result']['lines'][1].split('#')[-1].split(',');w['legacy']=row
    eq(row[0],relation);eq(row[4],ident);eq(row[6].rstrip(),name);eq(row[-1].replace(' ','_'),status)
@step(r'the row contains primary secondary arc and movement columns in source order')
def legacy_order(w):row=w['legacy'];eq(len(row),15);eq(row[1:3],['P','S']);eq(len(row[3]),1);eq(len(row[5]),1)
@step(r'saved contact options are (\S+) and a ready enemy plus a wreck are visible')
def saved(w,options):
    u(w).contact_options=blank(options);t(w).name='enemy';other=w['s'].add_unit({'name':'wreck','at':[2,5,0],'team':2});other.status|=S.DESTROYED;u(w).map.losinfo[u(w)._id,other._id]=7
@step(r'contact brevity is zero and roster order is enemy then wreck')
def order(w):u(w).brief=0
@step(r'contacts plus is requested')
def plus(w):command(w,'contacts','+')
@step(r'included names are (\S+) and ignored option warnings are (\d+)')
def saved_result(w,names,count):eq([r['name'] for r in w['result']['contacts']],names.split(','));eq(sum(line.startswith('Ignoring') for line in w['result']['lines']),int(count))
@step(r'scanner range 20 and NB-visible target TT at range '+N)
def scan_range(w,distance):u(w).scan_range=20;range_to(w,distance);w['notices_before']=sum('being scanned' in line for line in getattr(t(w),'movement_messages',[]))
@step(r'pilot command (\w+) is issued for TT')
def scan_command(w,name):command(w,name,'TT')
@step(r'report outcome is (\S+) and scan notices total (\d+)')
def report_outcome(w,outcome,count):eq(w['result']['ok'],outcome=='success');eq(sum('being scanned' in line for line in getattr(t(w),'movement_messages',[]))-w['notices_before'],int(count))
@step(r'a visible target with front armor 44 of 99 and mounted weapon recycle 4')
def armor_scan(w):t(w).sections[0].armor=44;t(w).sections[0].armor_orig=99;mount(t(w)).data=4
@step(r'scan option (\S+) is requested by observer (\S+)')
def scan_option(w,option,observer):
    if truth(observer):u(w).crit_status|=C.OBSERVATORIC
    command(w,'scan','TT'+(' '+option if option!='all' else ''))
@step(r'report sections are (\S+) and armor representation is (\S+)')
def scan_sections(w,sections,armor):
    eq(w['result']['sections'],sections.split(','))
    if armor=='absent':assert 'armor_display'not in w['result']
    else:assert armor in w['result']['armor_display']['plain']
@step(r'the targeted hex has (\S+) with clear NB LOS and usable scanner')
def hex_objects(w,objects):
    if objects=='building-and-mine':building(w,4,4)
    if objects in ('building-and-mine','mine-only'):
        from systems.mines import Mine,MineType
        u(w).map.map_objects[3].append(Mine(4,4,MineType.STANDARD,5,0,1))
@step(r'scan coordinates option (\w) is issued')
def hex_scan(w,option):command(w,'scan','4 4 '+option)
@step(r'building query occurs and mine query occurs (\S+) without treating empty content as unavailable')
def hex_result(w,mine):eq(w['result']['ok'],True);eq(w['result']['building_queried'],True);eq(w['result']['mines_queried'],truth(mine));eq(w['result'].get('blocked',[]),[])
@step(r'observer at 2 2 elevation 0')
def origin(w):u(w).set_hex_position(2,2,0)
@step(r'vector coordinates 2 2 '+N+r' are requested')
def vector(w,z):command(w,'vector','2 2 '+z)
@step(r'range text is (\S+) and vertical mark is (\S+)')
def vector_text(w,distance,mark):assert distance+' hexes' in w['result']['message'];assert 'mark '+mark in w['result']['message']
@step(r'observer at 2 2 elevation 0 and destination 2 5 elevation 4 with dark map (\S+)')
def range_setup(w,dark):u(w).set_hex_position(2,2,0);u(w).map.set_elevation(2,5,4);u(w).map.dark=truth(dark)
@step(r'range coordinates 2 5 is requested')
def range_request(w):command(w,'range','2 5')
@step(r'displayed range is (\S+) and separate ground-range text is (\S+)')
def range_text(w,distance,ground):
    assert distance+' hexes' in w['result']['message']
    if ground=='absent':assert 'ground hexes'not in w['result']['message']
    else:assert ground+' ground hexes' in w['result']['message']
@step(r'visible locked target TT with markings (\S+) and one ready loaded weapon')
def sight_setup(w,markings):
    t(w).markings=blank(markings);u(w).facing=180;u(w).target=t(w)._id;mount(u(w));w['before']=sight_state(w)
def sight_state(w):return ([s.armor for s in t(w).sections],u(w).heat,[(s.data,s.firemode) for sec in u(w).sections for s in sec.criticals])
@step(r'view TT then sight weapon 0 are requested')
def sight(w):w['view']=command(w,'view','TT');w['sight']=command(w,'sight','0')
@step(r'view text is (.+) and sight reports the actual firing solution')
def sight_solution(w,text):eq(w['view']['message'],text);assert w['sight']['attack']['bth_breakdown'] is not None
@step(r'ammo heat target armor and weapon recycle are unchanged')
def no_changes(w):eq(sight_state(w),w['before'])
