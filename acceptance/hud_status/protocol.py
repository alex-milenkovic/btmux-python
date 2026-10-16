from . import *
from systems.hud import HudSession,player_unit
from types import SimpleNamespace
from physics.hexmath import hex_to_float,find_xy

@step(r'the HUD reply class is (\S+) type is (\S+) and payload is (.+)')
def reply(w,cls,kind,payload):
    eq(len(w['result']['records']),1);row=w['result']['records'][0]
    eq(row['class'],None if cls=='unframed' else cls);eq(row['type'],None if kind=='unframed' else kind);eq(row['payload'],payload)
    eq(w['result']['wire'],payload+'\r\n' if cls=='unframed' else f'#HUD:{w["s"].sessions["main"].key or "???"}:{cls}:{kind}# {payload}\r\n')
@step(r'the session key becomes (\S+)')
def new_key(w,key):eq(w['s'].sessions['main'].key,blank(key))
@step(r'no successful HUD list terminator is emitted')
def no_done(w):eq(records(w,'D'),[])
@step(r'session key is test and the associated unit state is (\S+)')
def state(w,state):
    key(w,'test')
    if state=='no-unit':w['s'].sessions['main'].resolve=lambda:None
    if state=='shutdown':u(w).status&=~S.STARTED
    for text,flag in [('destroyed',S.DESTROYED),('unconscious',S.UNCONSCIOUS),('blinded',S.BLINDED)]:
        if state==text:u(w).status|=flag
@step(r'the HUD result is (.+)')
def outcome(w,result):
    if result in ('catalog-list','weapon-list'):eq(records(w,'D'),[['Done']])
    elif result=='general-status':eq(len(records(w,'R')[0]),20)
    else:eq(w['result']['records'][0]['payload'],result)
@step(r'local player placement (\S+) with eligible self A location B and carried unit C as applicable')
def placement(w,where):
    from entities.mech import Mech
    p=w['s'].personnel
    for number,name in enumerate('ABC',500):
        obj=Mech.create_test_mech(name);obj._id=number;obj.contact_id=name;obj.hardcode=True;p.add(obj,-1)
    a,b,c=(p.objects[i] for i in (500,501,502));p.move(a._id,b._id);p.move(c._id,a._id)
    if where!='all':a.hardcode=False
    if where=='no-self-zombie-location':b.zombie=True
    if where=='none':b.hardcode=c.hardcode=False
    w['other']=HudSession(lambda:player_unit(p,500));w['other'].request('key=other')
@step(r'an independent keyed session requests HUD gs')
def independent(w):w['result']=w['other'].request('gs')
@step(r'the selected unit is (\S+)')
def selected(w,name):
    if name=='no-unit-error':eq(records(w,'E'),[['Not in a BattleTech unit']])
    else:eq(records(w,'R')[0][0],name)
@step(r'changing that session key does not change another session key')
def separate(w):
    original=w['s'].sessions['main'].key;w['other'].request('key=new');eq(w['s'].sessions['main'].key,original)
@step(r'unit speed '+N+r' desired speed '+N+r' plus heat '+N+r' minus heat '+N+r' and vertical speed '+N)
def scalar(w,*values):
    for name,value in zip(('speed','desired_speed','plus_heat','minus_heat','vertical_speed'),values):setattr(u(w),name,float(value))
@step(r'GS speed fields are (\S+) and (\S+) heat fields are (\S+) and (\S+) and both vertical fields are (\S+)')
def scalars(w,speed,desired,plus,minus,vertical):
    row=records(w,'R')[0];eq(row[6:10],[speed,desired,plus,minus]);eq(row[11:13],[vertical,vertical])
@step(r'GS has 20 fields with the final target field a dash')
def twenty(w):eq(len(records(w,'R')[0]),20);eq(records(w,'R')[0][-1],'-')
@step(r'unit form (\S+) with turret offset (\d+) torso (\S+) and jump state (\S+)')
def torso_setup(w,kind,offset,torso,jump):
    form(u(w),kind);u(w).turret_facing=int(offset)
    if torso in ('left','right'):u(w).status|=S.TORSO_LEFT if torso=='left' else S.TORSO_RIGHT
    if jump!='none':u(w).status|=S.JUMPING;u(w).going_x,u(w).going_y=map(int,jump.split(','))
@step(r'the torso field is (\S+) and jump destination fields are (\S+)')
def torso(w,field,destination):row=records(w,'R')[0];eq(row[15],field);eq(','.join(row[17:19]),destination)
@step(r'a section has original front (\d+) rear (\d+) internal (\d+) and current front (\d+) rear (\d+) internal (\d+)')
def armor_setup(w,*values):
    for name,value in zip(('armor_orig','rear_orig','internal_orig','armor','rear','internal'),values):setattr(u(w).sections[0],name,int(value))
@step(r'keyed HUD (\w+) and (\w+) are requested')
def double(w,a,b):w['first']=hud(w,a);w['second']=hud(w,b)
@step(r'the section original row is (\S+) and current row is (\S+)')
def armors(w,original,current):
    for result,expected in [(w['first'],original),(w['second'],current)]:
        rows=[r for r in records(w,result=result) if r[0]=='LA'];eq(','.join(rows[0][1:]) if rows else 'omitted',expected)
@step(r'map light (\S+) visibility 30 gravity 100 temperature 25 and flags (\S+)')
def conditions(w,light,flags):
    if light=='no-map':u(w).map=None;return
    b=u(w).map;b.maplight=int(light);b.mapvis=30;b.grav=100;b.temp=25;b.flags=sum(bit for name,bit in [('vacuum',4),('underground',16),('dark',32)] if name in flags)
@step(r'both condition payloads are (\S+) with their respective CON and CO classes')
def condition_rows(w,payload):
    for result,cls in [(w['first'],'CON'),(w['second'],'CO')]:eq(result['records'][0]['payload'],payload);eq(result['records'][0]['class'],cls)
@step(r'the unit class and movement are (\S+)')
def unit_form(w,kind):form(u(w),kind)
@step(r'its type field is (\S+) and all remaining template fields come from the loaded design')
def type_code(w,code):
    row=records(w,'R')[0];eq(row[0],code);eq(len(row),10);eq(row[1],u(w).template_ref);eq(row[2],u(w).name);eq(row[8],str(u(w).real_num_sinks))
@step(r'its weapon status is (\S+)')
def weapon_status(w,status):eq(records(w)[0][4],status)
@step(r'the diagnostic weapon has fire selection (\S+) ammo selection (\S+) and intact targeting computer')
def modes(w,fire,ammo):
    slot=mount(u(w),'IS.Anti-MissileSystem' if fire.startswith('AMS') else 'IS.MediumLaser')
    f={'RAC2':'RAC_TWOSHOT_MODE','RAC4':'RAC_FOURSHOT_MODE','RAC6':'RAC_SIXSHOT_MODE','TC':'ON_TC','OSUSED':'OS_USED'}
    if fire=='AMS-enabled':u(w).status|=S.AMS_ENABLED
    elif fire=='AMS-disabled':u(w).status&=~S.AMS_ENABLED
    elif fire!='none':
        for name in fire.split('-'):slot.firemode|=getattr(F,f.get(name,name+'_MODE'))
    if ammo!='none':
        for name in ammo.split('-'):slot.ammomode|=getattr(A,name+'_MODE')
@step(r'fire letters are (\S+) and ammo letters are (\S+)')
def mode_rows(w,fire,ammo):eq(records(w)[0][-2:],[fire,ammo])
@step(r'weapons are installed in section-slot order (\S+) with the first mount rear-mounted and brands alternating 1 and 2 in traversal order')
def mounts(w,mounts):
    for i,value in enumerate(mounts.split(',')):
        loc,pos=value.split(':');slot=mount(u(w),loc=0 if loc=='LARM' else 1,pos=int(pos));slot.brand=1+i%2
        if not i:slot.firemode|=F.REAR_MOUNT
@step(r'WE has (\d+) sequential zero-based weapon rows with source sections brands and rear suffix')
def traversed(w,count):
    rows=records(w,result=w['first']);eq(len(rows),int(count));eq([r[0] for r in rows],list(map(str,range(int(count)))));eq([r[2] for r in rows],[str(1+i%2) for i in range(int(count))]);eq(rows[0][3],'LAr')
@step(r'WL contains one row per non-personal-combat catalog type with all 18 source fields')
def catalog(w):
    from data.construction_catalog import SOURCE_WEAPON_NAMES
    rows=records(w,result=w['second']);eq([r[1] for r in rows],[name for name in SOURCE_WEAPON_NAMES if not name.startswith('PC.')]);eq(set(map(len,rows)),{18})
@step(r'unit form (\S+) left arm state (\S+) and recycle data (\d+)')
def limb(w,kind,state,ticks):form(u(w),kind);u(w).sections[0].armor=u(w).sections[0].internal=0 if state=='destroyed' else 10;u(w).sections[0].recycle=int(ticks)
@step(r'LI has (\d+) rows and first status (\S+) followed by one Done')
def limbs(w,count,status):eq(len(records(w)),int(count));eq(records(w)[0][1] if records(w) else 'absent',status);eq(records(w,'D'),[['Done']])
@step(r'two functional ammo bins of one weapon have modes (\S+) rounds 5 and 7 and capacities 20 and 20')
def ammo(w,modes):
    for pos,(mode,now) in enumerate(zip(modes.split('-'),(5,7))):
        slot=u(w).sections[0].criticals[pos];slot.type=i2ammo(get_weapon('IS.AC/5').index);slot.data=now;slot.ammomode=A.INFERNO_MODE if mode=='inferno' else 0
    w['ammo_weapon']=get_weapon('IS.AC/5')
@step(r'AM contains (\d+) groups with current amounts (\S+) and maximum amounts (\S+)')
def ammos(w,count,current,maximum):
    rows=records(w);eq(len(rows),int(count));eq(','.join(r[3] for r in rows),current);eq(','.join(r[4] for r in rows),maximum)
