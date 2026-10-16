"""Real catalog names and exact object attribute semantics."""
import re
from . import check,attempt,source_part,i2special,Special


def run(w,initial,operation):
    inv=w['inventory'];actor=w['actor'];actor.location=1000
    a=source_part('Ammo_IS.LRM-15');b=source_part('Electric');identity=1000
    def raw(text):return text.replace('idA',str(a)).replace('idB',str(b))
    if initial.startswith('[') or initial in ('invalid object','brand2 same catalog short name as brand0','brand2 distinct catalog short name','raw actuator count2'):
        if initial.startswith('['):inv.set_raw(identity,raw(initial))
        if initial=='invalid object':identity=999
        if initial=='brand2 distinct catalog short name':a=source_part('IS.SmallLaser')
        if initial=='raw actuator count2':
            a=i2special(Special.SHOULDER_OR_HIP);inv.set_raw(identity,f'[{a},0,2]')
        before=inv.raw(identity);writes=len(inv.writes)
        brand=int(re.search(r'brand(\d+)',operation)[1]) if 'brand' in operation else 0
        part=source_part('Actuator') if operation=='find standard actuator cargo' else a
        if operation.startswith('find '):result=inv.find(identity,part,brand);w['result']=result
        elif operation.startswith('remove '):inv.remove(identity,b if 'idB' in operation else part,brand)
        elif operation.startswith('set '):inv.set(identity,part,brand,int(re.search(r'to(\d+)',operation)[1]))
        else:
            value=int(re.search(r'(?:plus|minus)(\d+)',operation)[1])*(-1 if 'minus' in operation else 1)
            inv.change(identity,part,brand,value)
        for text in ('[idB,0,3],[idA,0,6]','[idA,0,5],[idA,0,3]','[idB,0,3]','[idB,0,3],[idA,0,5]','[idA,0,2]'):check(w,text,inv.raw(identity)==raw(text))
        check(w,'count2 without write',w.get('result')==2 and len(inv.writes)==writes)
        check(w,'count2 not7',w.get('result')==2)
        check(w,'identical raw storage without attribute write',inv.raw(identity)==before and len(inv.writes)==writes)
        check(w,'no write',len(inv.writes)==writes)
        check(w,'normalized brand0 count3',inv.raw(identity)==f'[{a},0,3]')
        check(w,'retained brand2 count3',inv.raw(identity)==f'[{a},2,3]')
        check(w,'actuator removed and standard actuator cargo plus3',inv.find(identity,a)==0 and inv.find(identity,source_part('Actuator'))==3)
        check(w,'count0 without alias lookup',w.get('result')==0 and len(inv.writes)==writes)
        check(w,'raw text unchanged',inv.raw(identity)==before);return True
    if operation=='manifest' and initial in ('duplicate idA counts2 and5','idA raw counts2 and-5','idA count2 one-ton item','actor room has inventory and unit differs','empty room inventory'):
        if initial!='empty room inventory':inv.set_raw(identity,f'[{a},0,2]'+(f',[{a},0,-5]' if 'and-5' in initial else f',[{a},0,5]' if 'and5' in initial else ''))
        result=w['cargo'].command(actor,w['u'],'manifest');w['result']=result;rows=result['rows']
        check(w,'aggregated count7',len(rows)==1 and rows[0]['count']==7)
        check(w,'displayed count-3',len(rows)==1 and rows[0]['count']==-3)
        check(w,'count2 weight2 tons',len(rows)==1 and (rows[0]['count'],rows[0]['weight'])==(2,2048))
        check(w,'actor-room inventory',len(rows)==1 and rows[0]['count']==2 and not inv.raw(w['u']._id))
        check(w,'empty footer',rows==[] and result['footer']=='None');return True
    if operation=='Rfixstuff':
        crap=i2special(Special.ENDO_STEEL)
        inv.set_raw(identity,f'[{a},0,2],[{a},0,5],[{crap},0,3],[{b},0,-2],[9999,0,5]')
        result=w['cargo'].command(actor,w['u'],'Rfixstuff')
        check(w,'aggregate valid positives only and canonical order',inv.raw(identity)==f'[{a},0,7]' and result['items']==7 and result['kinds']==1);return True
    if operation.startswith(('Raddstuff ','Rremovestuff ')):
        selector='Ag*' if 'matches20' in initial else 'R*' if 'matches21' in initial else 'ERPPC' if initial.startswith('selector matches') else inv.catalog.names(a,0)[0]
        matches=inv.matching(selector)
        count=operation.split()[-1];command=operation.split()[0]
        if 'nonGOD' not in initial and 'GOD' in initial:actor._id=1;inv.register(1,actor)
        if command=='Rremovestuff':
            for entry in matches:inv.set(identity,entry.source_part_id,entry.brand,5)
        before=inv.raw(identity);writes=len(inv.writes)
        result=attempt(w,w['cargo'].command,actor,w['u'],command,selector+' '+count)
        amounts=[inv.find(identity,v.source_part_id,v.brand) for v in matches]
        check(w,'short family only gains3 each',len(inv.matching(selector,('long',)))>len(matches) and amounts==[3]*len(matches))
        check(w,'all20 gain3',len(matches)==20 and amounts==[3]*20)
        check(w,'all21 gain3',len(matches)==21 and amounts==[3]*21)
        check(w,'refuse before any stock mutation',bool(w['error']) and inv.raw(identity)==before and len(inv.writes)==writes)
        check(w,'each match gains50000',bool(amounts) and amounts==[50000]*len(matches))
        check(w,'refuse positive-count requirement','amount' in w['error'].lower() and len(inv.writes)==writes)
        check(w,'remove3 by atoi prefix',amounts==[2]*len(matches));return True
    if operation=='Rresetstuff':
        inv.set(identity,a,0,2);w['cargo'].command(actor,w['u'],'Rresetstuff')
        check(w,'room storage empty and log request',not inv.raw(identity) and inv.external[-1]['action']=='reset' and not inv.external[-1]['delivered']);return True
    return False
