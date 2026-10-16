"""Procedure 11: ordinary hangar transfers and fixed-point cargo/speed rules."""
from qa.repair_support import *
from qa.repair_economy_cases import TWENTYONE
from qa.repair_access_time import source

def hangar():
    u=unit(started=True,specials=8192);d=doc(u,stock=stocks((517,0,5)));d['repair_economy']['objects'][0]['MECHSKILLS']='3 3 0';d['map'].update(flags=1,cf=100);return d

def cargo():
    for i,(name,row) in enumerate(rows('cargo',1),1):
        d=hangar();u=d['units'][0];a=d['characters'][0];room=d['repair_economy']['objects'][0];stock=room['ECONPARTS'];load=i not in (9,10,11)
        selector='Ammo_SRM';count=1 if i in (13,14,15) else 4 if i==12 else 3
        if i==2:u['started']=False
        if i==3:u['specials']=0
        if i in (4,5,9):u['speed']=0.1 if i in (4,9) else -0.1
        if i in (6,7,9):room['MECHSKILLS']='4 4 '+('1' if i==6 else '0')
        if i in (8,9):room['in_character']=True
        if i==9:u['started']=False
        if i==10:a['location']=1000
        if i==11:u['repair']['location']=1001;d['repair_economy']['objects'].append(dict(id=1001))
        if not load:room['ECONPARTS']='';d['repair_economy']['objects'].append(dict(id=10,ECONPARTS=stock))
        if i==12:room['ECONPARTS']=stocks((516,0,2),(517,0,5));selector='Ammo_?RM'
        if i==13:room['ECONPARTS']=stocks(*[(p,0,1) for p in TWENTYONE]);selector='R*'
        if i==14:room['MECHSKILLS']='99'
        if i==15:selector='MissingCargo';u['core']['carried_cargo']=1024
        d['actions']=[inspect(),cmd('loadcargo' if load else 'unloadcargo',f'{selector} {count}'),inspect()];c=Case(name,d)
        refuse={2:'online',3:'haul cargo',4:'moving',5:'moving',6:'cargo is',7:'cargo is',8:'hangar',10:'mech',11:'hangar',15:'matches'}
        if i in refuse:
            c.result(1,ok=False).expect('results.1.error',refuse[i],'contains').expect('state.economy.objects','results.0.economy.objects','same_as')
            if i==6:c.expect('results.1.error','4,4','contains')
            if i==7:c.expect('results.1.error','4,4','not_contains')
            if i==15:c.expect('state.units.u.carried_cargo',0)
        else:
            c.result(1,ok=True)
            if i==12:
                # Multiple long-name matches include empty MRM stock; only actual available items transfer.
                expectedroom=stocks((517,0,1));expectedunit=stocks((516,0,2),(517,0,4))
            elif i==13:expectedroom='';expectedunit=stocks(*[(p,0,1) for p in TWENTYONE])
            elif load:expectedroom=stocks((517,0,5-count));expectedunit=stocks((517,0,count))
            else:expectedroom=stocks((517,0,count));expectedunit=stocks((517,0,5-count))
            c.expect('state.economy.objects.1000.ECONPARTS',expectedroom).expect('state.economy.objects.10.ECONPARTS',expectedunit)
        yield c
    for i,(name,row) in enumerate(rows('cargo',2),1):
        u=unit(kind='AERO' if i in (2,3,5,7,8) else 'MECH');d=doc(u,actions=[diag('cargo_weight')]);c=Case(name,d);raw=''
        if i==1:raw=stocks((source('IS.AC/10')+192,1,1),(source('IS.AC/10')+192,2,1));u['crit_status']=4096
        if i in (2,3,4):setslot(u,0,4,type=422,firemode=1 if i==3 else 0);raw=stocks((422,0,2)) if i==2 else ''
        if i==5:setslot(u,7,11,type=385,firemode=1)
        if i==6:raw=stocks((385,0,2))
        if i in (7,8):u['core'].update(fuel_orig=100,fuel=150 if i==7 else 90)
        if i in (9,10):
            # 50t measured Mech with CargoTech: 25t cargo makes denominator75t.
            u['specials']=8192;raw=stocks((517,0,25));u['core'].update(carried_cargo=0,speed=55 if i==9 else -50,desired_speed=55 if i==9 else -50)
            d['actions']=[diag('correct_speed'),inspect(),diag('correct_speed'),inspect()] if i==9 else [diag('correct_speed')]
            c.result(speed=55 if i==9 else -40,desired=55 if i==9 else -40)
            if i==9:c.result(2,speed=40,desired=40)
            c.expect('state.units.u.carried_cargo',25600)
        d['repair_economy']['objects'].append(dict(id=10,ECONPARTS=raw))
        if i in (1,5,6,7,8):c.expect('results.0',{1:2048,5:1020,6:8160,7:50,8:0}[i])
        if i in (2,3):c.expect('state.units.u.fuel_max',7000 if i==2 else 3000)
        if i==4:c.expect('state.units.u.fuel_max',0).expect('results.0',0)
        c.expect('state.units.u.crit_status',4096,'not_bit');yield c
