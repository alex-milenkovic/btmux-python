"""Procedure 10: exact raw ECONPARTS and ordinary room administration."""
from qa.repair_support import *
from qa.repair_access_time import source
# Verified public catalog selectors; fixed identities make match regressions visible.
TWENTY=[159,83,84,82,85,94,175,78,86,170,93,79,87,77,80,88,92,89,90,91]
TWENTYONE=[880,889,881,882,883,884,885,886,887,888,558,146,147,148,166,109,164,167,110,165,632]

def economy():
    A=HEATSINK;B=404
    for i,(name,row) in enumerate(rows('economy',1),1):
        part=A;brand=0;identity=1000;kind='find' if i in (1,2,14) else 'set' if i in (8,9) else 'remove' if i>=15 else 'change';raw=stocks((A,0,2),(B,0,3))
        if i in (2,4):raw=stocks((A,0,2),(A,0,5))
        if i==7:raw=stocks((B,0,3))
        if i in (11,12):brand=2;raw='';part=A if i==11 else source('IS.SRM-6')
        if i in (13,14):raw=stocks((394,0,2));part=394 if i==13 else ACTUATOR
        if i==15:raw=f'[{A},0,2'
        if i==16:part=B
        if i==10:identity=999999
        counts={3:4,4:1,5:-2,6:-9,7:-1,8:2,9:5,10:3,11:3,12:3,13:1}
        d=doc(stock=raw,actions=[inspect(),repair(kind,object=identity,part=part,brand=brand,**({'count':counts[i]} if i in counts else {})),inspect()]);c=Case(name,d)
        expected={1:raw,2:raw,3:stocks((B,0,3),(A,0,6)),4:stocks((A,0,5),(A,0,3)),5:stocks((B,0,3)),6:stocks((B,0,3)),7:raw,8:raw,9:stocks((B,0,3),(A,0,5)),10:raw,11:stocks((A,0,3)),12:stocks((part,2,3)),13:stocks((ACTUATOR,0,3)),14:raw,15:raw,16:stocks((A,0,2)),17:stocks((B,0,3))}[i]
        c.expect('state.economy.objects.1000.ECONPARTS',expected)
        if i in (1,2,14):c.expect('results.1',0 if i==14 else 2)
        if i>=15:c.expect('results.1',i!=15)
        if i in (1,2,7,8,10,14,15):c.expect('state.economy.writes','results.0.economy.writes','same_as')
        c.expect('draws',[]);yield c
    for i,(name,row) in enumerate(rows('economy',2),1):
        A=517 if i==3 else HEATSINK
        a=actor(location=1000,ident=1 if i==9 else 200);u=unit(character=a['id']);raw=stocks((A,0,2),(A,0,5)) if i==1 else stocks((A,0,2),(A,0,-5)) if i==2 else stocks((A,0,2)) if i in (3,5,13) else stocks((A,0,5)) if i==12 else ''
        if i==4:raw=stocks((B,0,1),(A,0,2),(A,0,5),(407,0,3),(INTERNAL,0,-2),(1023,0,2))
        command='manifest' if i in (1,2,3,5,14) else 'Rfixstuff' if i==4 else 'Rresetstuff' if i==13 else 'Rremovestuff' if i==12 else 'Raddstuff'
        selector='ERPPC' if i==6 else 'Ag*' if i==7 else 'R*' if i in (8,9) else 'HeatSink'
        count='50001' if i==10 else '0' if i==11 else '3junk' if i==12 else '3';args='' if command in ('manifest','Rfixstuff','Rresetstuff') else selector+' '+count
        d=doc(u,characters=[a],stock=raw,actions=[inspect(),cmd(command,args),cmd('manifest')]);c=Case(name,d)
        if i in (8,11):c.result(1,ok=False).expect('results.1.error','20 different' if i==8 else 'amount','contains').expect('state.economy.writes','results.0.economy.writes','same_as')
        else:c.result(1,ok=True)
        if i<=3 or i==5:c.expect('results.1.result.rows.0.count',7 if i==1 else -3 if i==2 else 2)
        if i==3:c.expect('results.1.result.rows.0.weight',2048)
        expected=stocks((A,0,7),(B,0,1)) if i==4 else stocks((82,0,3)) if i==6 else stocks(*[(p,5,3) for p in TWENTY]) if i==7 else stocks(*[(p,0,3) for p in TWENTYONE]) if i==9 else stocks((A,0,50000)) if i==10 else stocks((A,0,2)) if i==12 else '' if i==13 else raw
        c.expect('state.economy.objects.1000.ECONPARTS',expected)
        if i in (7,9):c.expect('results.1.result',20 if i==7 else 21,'length').expect('results.2.result.rows',20 if i==7 else 21,'length')
        if i==13:c.expect('state.economy.external',dict(service='MUX economy log',delivered=False,action='reset',object=1000),'has')
        if i==14:c.expect('results.1.result.footer','None').expect('results.1.result.rows',[])
        yield c
