from . import step,base,eq,truth,values
from data.characters import ALL,SKILLS,divide
from data.character_values import code,XP_MAX
from systems import characters as c

@step(r'a source character with Gunnery-Battlemech raw BTH4 threshold3000 and XP_MAX16777216')
def fresh(w):
    base(w);values(w,Build=5,Reflexes=5,Intuition=5,Learn=5,Charisma=5)
    c.set_value(w['store'],101,'Gunnery-Battlemech',4);w['skill']='Gunnery-Battlemech'

def raw_xp(w,xp):
    s=w['store'].retrieve(101,ALL);s.xp[code(w['skill'])]=xp;w['store'].store(101,s,SKILLS)

@step(r'raw XP (\d+)')
def raw(w,n):raw_xp(w,int(n))

@step(r'the source bonus is recomputed and next level queried')
def recompute(w):
    s=w['store'].retrieve(101,ALL);w['bonus']=c.pack_xp(w['store'],101,s,code(w['skill']))
    w['packed']=s.xp[code(w['skill'])];w['store'].store(101,s,SKILLS);w['next']=c.next_threshold(w['store'],101,w['skill'])

@step(r'bonus is (\d+) packed XP is (\d+) and cumulative next threshold is (\d+)')
def recomputed(w,bonus,packed,nxt):eq((w['bonus'],w['packed'],w['next']),tuple(map(int,(bonus,packed,nxt))))

@step(r'raw BTH (\d+) and configured threshold (\d+)')
def threshold(w,bth,n):
    c.set_value(w['store'],101,w['skill'],0 if int(bth)>8 else 8-int(bth))
    if int(bth)>8:values(w,Reflexes=0,Intuition=0)
    w['store'].thresholds[code(w['skill'])]=int(n)
    eq(c.skill_target(w['store'],101,w['skill'],use_xp=False),int(bth))
    w['first']=c.next_threshold(w['store'],101,w['skill'])

@step(r'XP is (\d+) and bonus is recomputed')
def threshold_run(w,n):raw_xp(w,int(n));recompute(w)

@step(r'bonus is (\d+) and first cumulative threshold is (-?\d+)')
def threshold_result(w,bonus,first):eq((w['bonus'],w['first']),(int(bonus),int(first)))

@step(r'last use 100 with (.+) skill and current time (\d+)')
def cooldown(w,kind,now):
    w['skill']='Gunnery-Battlemech' if kind=='SK_XP' else 'Blade';w['now']=int(now)
    if kind=='ordinary-disconnected':w['store'].records[101]['connected']=False
    s=w['store'].retrieve(101,ALL);s.set(w['skill'],1);s.xp[code(w['skill'])]=1;s.last_use[code(w['skill'])]=100;w['store'].store(101,s,SKILLS)

@step(r'XP gain 1 requests override (True|False)')
def gain(w,override):w['result']=c.gain_xp(w['store'],101,w['skill'],1,now=w['now'],override=truth(override))

@step(r'accepted is (True|False) and last use becomes (\d+)')
def gained(w,accepted,last):eq(bool(w['result']),truth(accepted));eq(w['store'].retrieve(101,SKILLS).last_use[code(w['skill'])],int(last))

@step(r'packed XP (-?\d+)')
def packed(w,n):raw_xp(w,int(n))

@step(r'XP is changed with (.+)')
def change(w,operation):
    if operation.startswith('lower-'):c.lower_xp(w['store'],101,int(operation[6:]))
    else:c.gain_xp(w['store'],101,w['skill'],1,now=101,override=True)

@step(r'packed XP becomes (-?\d+)')
def changed(w,n):eq(w['store'].retrieve(101,SKILLS).xp[code(w['skill'])],int(n))

@step(r'Gunnery-Battlemech BTH4 raw level4 raw XP3001 and bonus1')
def admin(w):raw_xp(w,XP_MAX+3001);w['store'].records[101]['wizard']=True

@step(r'the administrator requests (.+)')
def admin_run(w,operation):
    w['admin_operation']=operation;w['error']=None
    import re
    if operation.startswith('get-'):w['result']=c.control(w['store'],101,'get',name=w['skill'],flag=int(operation[-1]))
    else:
        match=re.fullmatch(r'set-flag(\d+)-(?:XP|BTH)(\d+)',operation)
        assert match,operation
        w['result']=c.control(w['store'],101,'set',name=w['skill'],flag=int(match[1]),amount=int(match[2]),now=101)

@step(r'configuration request (.+)')
def request(w,request):w['experience_request']=request

@step(r'the ordinary XP control executes')
def xp_control(w):
    request=w['experience_request'];store=w['store'];w['error']=None
    try:
        if request.startswith('threshold-'):
            args={'threshold-empty':'','threshold-Running-minus1':'Running -1','threshold-Build-5':'Build 5','threshold-Running-0':'Running 0'}[request]
            w['result']=c.threshold_control(store,args)
        elif request=='getthreshold-unknown':w['result']=c.get_threshold(store,'Unknown')
        else:
            store.records.clear();store.cache=None
            if request=='top-A100-B100-C200':rows=[(101,'A',100,True,False),(102,'B',100,True,False),(103,'C',200,True,False)]
            elif request=='top-17-players':rows=[(i+101,str(i),1,True,False) for i in range(17)]
            else:rows=[(101,'nonplayer',100,False,False),(102,'wizard',100,True,True),(103,'player',50,True,False)]
            for ident,name,xp,is_player,wizard in rows:
                store.create(ident,name,is_player=True,wizard=wizard)
                s=store.retrieve(ident,ALL);s.xp[code('Gunnery-Battlemech')]=xp;store.store(ident,s,SKILLS)
                store.records[ident]['is_player']=is_player
            w['result']=c.xp_top(store,'Gunnery-Battlemech')
    except ValueError as error:w['error']=str(error)

def control_result(w,expected):
    errors={'invalid-arguments':'Invalid arguments','negative-error':'Threshold needs','not-skill':"isn't any skill"}
    if expected in errors:assert errors[expected] in (w['error'] or ''),(w['error'],expected);return
    eq(w['error'],None)
    if expected.startswith('rawXP'):
        import re
        match=re.fullmatch(r'rawXP(\d+)-bonus(\d+)',expected);assert match
        xp=w['store'].retrieve(101,SKILLS).xp[code(w['skill'])]
        eq((xp%XP_MAX,xp//XP_MAX),tuple(map(int,match.groups())))
    elif expected=='rawLevel0':eq(w['store'].retrieve(101,SKILLS).values[code(w['skill'])],0)
    elif expected=='threshold0':eq(w['store'].thresholds[code('Running')],0)
    elif expected=='excluded':eq([r['id'] for r in w['result']['rows']],[103])
    elif expected=='order-C-B-A-percent50-25-25-total400':
        eq([r['name'] for r in w['result']['rows']],['C','B','A']);eq([r['percent'] for r in w['result']['rows']],[50,25,25]);eq(w['result']['total'],400)
    elif expected=='top16-percent-against17':
        eq(len(w['result']['rows']),16);eq(w['result']['total'],17);eq([r['percent'] for r in w['result']['rows']],[100/17]*16)
    else:eq(w['result'],int(expected))
