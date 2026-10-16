"""Procedure 12: contact-dispatched pickup, cable guards and real releases."""
from qa.repair_support import *
from qa.repair_inventory import damaged
TOWED=0x4000;FALLEN=0x80

def tow_doc(cables=False):
    u=unit(started=True,in_character=True,team=1)
    v=unit('v',11 if not cables else 12,character=201 if not cables else 202,in_character=True,team=1)
    units=[u,v];characters=[actor(),actor(201,11)]
    if cables:
        t=unit('t',11,character=201,started=True,in_character=True,team=1)
        units=[u,t,v];characters.append(actor(202,12))
    return doc(units=units,characters=characters)

def relation(c,tower='u',target='v',targetid=11):
    return c.expect(f'state.units.{tower}.repair.carrying',targetid).expect(f'state.units.{tower}.repair.towed_unit',targetid).expect(f'state.units.{target}.status',TOWED,'bit').expect(f'state.units.{target}.fallen',True).expect(f'state.units.{target}.started',False)

def towing():
    for i,(name,row) in enumerate(rows('towing',1),1):
        d=tow_doc();u,v=d['units'];acts=[];ci=0
        if i in (1,2):v['team']=2;v['started']=i==2
        if i==4:u['movement']='QUAD'
        if i==5:damaged(u,0)
        if i==6:
            for pos in (0,3):setslot(u,1,pos,firemode=1)
        if i==7:setslot(u,0,0,firemode=1);setslot(u,1,3,firemode=1)
        if i in (8,9):u['class']='VEH_GROUND';u['movement']='TRACK';u['specials']=4096 if i==9 else 0
        if i in (10,11):u['speed']=1 if i==10 else 1.01;u['vertical_speed']=-1 if i==10 else 0
        if i in (12,13,14,15):u['at'][2]={12:3,13:4,14:-2,15:-3}[i]
        if i==16:
            w=unit('w',12,kind='MW',character=202,in_character=True,team=1,tonnage=1,measured_mass=1024);d['units'].append(w);d['characters'].append(actor(202,12));acts=[cmd('pickup','01')];ci=1
        if i==17:v['team']=0
        if i==18:v['crit_status']=8
        if i==19:v['in_character']=False
        if i==20:
            w=unit('w',12,character=202,in_character=True,team=1);d['units'].append(w);d['characters'].append(actor(202,12));v['started']=True;acts=[cmd('pickup','02',unit='v')];ci=1
        acts +=[cmd('pickup','02' if i==16 else '01'),inspect()];d['actions']=acts;c=Case(name,d)
        refuse={1:'enemy',2:'enemy',4:'four left',5:'arm',7:'functioning arm',8:'salvage',11:'moving too fast',13:'high',15:'below',18:'hiding',19:'tow that'}
        if i in refuse:c.result(ci,ok=False).expect(f'results.{ci}.error',refuse[i],'contains').expect('state.units.u.repair.carrying',-1).expect('state.units.v.status',TOWED,'not_bit')
        elif i==16:c.result(ci,ok=True).expect('state.units.u.repair.carrying',11).expect('state.characters.202.location',10)
        else:
            c.result(ci,ok=True);relation(c)
            for field in ('at','fx','fy','fz'):c.expect('state.units.v.'+field,'state.units.u.'+field,'same_as')
            if i==20:c.expect('state.units.v.repair.carrying',-1).expect('state.units.w.status',TOWED,'not_bit')
        yield c
    for i,(name,row) in enumerate(rows('towing',2),1):
        d=tow_doc(True);u,t,v=d['units'];v['team']=2;acts=[];ci=0
        if i==2:t['class']='VEH_GROUND';t['movement']='TRACK';t['specials']=4096
        if i==3:t['in_character']=False;t['repair']['towable']=True
        if i==4:t['speed']=0.01
        if i==5:v['in_character']=False;v['repair']['towable']=True
        if i==6:v['started']=True
        if i==7:u['team']=3
        if i==8:u['cocoon']=1
        if i==9:u['at'][2]=1
        if i==10:t['aerospace']={'fx':1024.25,'fy':967.75};v['aerospace']={'fx':1024.5,'fy':967.25}
        if i>=11:
            if i==13:t['aerospace']={'carrying':99999}
            else:
                acts=[cmd('attachcables','01 02')];ci=1
                if i==11:
                    d['characters'].append(actor(1,1000));acts +=[repair('actor',actor=1,values={'god':True}),cmd('shutdown')];ci=3
                if i==12:acts +=[op('configure',unit='u',values={'team':3}),op('core',unit='t',values={'speed':5})];ci=3
                if i==14:
                    acts +=[op('aero_configure',unit='v',values={'z':3,'fz':192}),op('hex',value=dict(at=[3,3],terrain='CLEAR',elevation=2))];ci=3
            acts.append(cmd('detachcables','01',**({'actor':1} if i==11 else {})))
        else:acts=[cmd('attachcables','01 02')]
        acts.append(inspect());d['actions']=acts;c=Case(name,d)
        refuse={2:'salvage',3:'IC',4:'moving',6:'started enemy',7:'team',8:'OOD',9:'elevation',11:'online',13:'invalid'}
        if i in refuse:
            c.result(ci,ok=False).expect(f'results.{ci}.error',refuse[i],'contains')
            c.expect('state.units.t.repair.carrying',12 if i==11 else -1)
        elif i in (12,14):
            c.result(ci,ok=True).expect('state.units.t.repair.carrying',-1).expect('state.units.v.status',TOWED,'not_bit').expect('state.units.v.speed',0)
            if i==14:c.expect('state.units.v.at.2',2).expect('state.units.v.fz',192).expect('state.units.v.events',[])
        else:
            c.result(ci,ok=True);relation(c,'t','v',12)
            if i==10:c.expect('state.units.v.fx',1024.5).expect('state.units.v.fy',967.25).expect('state.units.t.fx',1024.25)
        yield c
    for i,(name,row) in enumerate(rows('towing',3),1):
        d=tow_doc();u,v=d['units'];acts=[];ci=0
        if i<=4:
            acts=[cmd('pickup','01')];ci=1
            if i in (1,2):acts.append(op('aero_configure',unit='v',values={'z':3 if i==1 else 2,'fz':192 if i==1 else 128}));ci+=1
            if i==2:acts +=[op('aero_configure',unit='u',values={'x':4,'y':3}),op('hex',value=dict(at=[4,3],terrain='CLEAR',elevation=1))];ci+=2
            if i==3:acts.append(op('hex',value=dict(at=[3,3],terrain='ICE',elevation=0)));ci+=1
        if i==5:u['aerospace']={'carrying':99999}
        acts.append(cmd('dropoff'));acts.append(inspect())
        if i==1:acts +=[advance(2),inspect(),advance(1),inspect()]
        d['actions']=acts;c=Case(name,d)
        if i>=5:c.result(ci,ok=False).expect(f'results.{ci}.error','invalid' if i==5 else 'not carrying','contains')
        else:c.result(ci,ok=True).expect('state.units.v.status',TOWED,'not_bit').expect('state.units.v.speed',0).expect('state.units.v.desired_speed',0).expect('state.units.v.fallen',True).expect('state.units.v.started',False)
        c.expect('state.units.u.repair.carrying',-1)
        if i==1:
            c.expect(f'results.{ci+1}.units.v.events',{'kind':'FALL','deadline':3,'data2':-1},'has').expect(f'results.{ci+3}.units.v.at.2',3).expect('state.units.v.at.2',3,'less')
        elif i<=4:c.expect('state.units.v.at.2',1 if i==2 else 0).expect('state.units.v.events',[])
        yield c
