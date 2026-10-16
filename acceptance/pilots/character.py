from . import step,base,eq,truth,values
from data.characters import Stats,ALL,HEALTH,ATTRS,SKILLS,ADVS,generic_store,generic_retrieve
from data.character_values import VALUES,code,XP_MAX
from systems import characters as c

@step(r'an isolated character registry using the complete source value table and production storage')
def fresh(w):base(w)

@step(r'character value (.+) is assigned (-?\d+)')
def assignment(w,name,n):w['name']=name;c.set_value(w['store'],101,name,int(n))

@step(r'the value is retrieved by its canonical name')
def get(w):w['result']=c.value(w['store'],101,VALUES[code(w['name'])].name)

@step(r'its code is (\d+) and stored value is (\d+)')
def assigned(w,index,n):eq(code(w['name']),int(index));eq(w['result'],int(n))

@step(r'the stored categories contain (.+)')
def categories(w,state):
    cats=w['store'].records[101]['categories'];w['contents']=state
    if state=='absent':return
    cats.update(health='2,3',attrs='5,4,3,2,1',skills='Runni:4/',advs='Lives:1/')
    if state=='malformed-health-existing-build5':cats['health']='broken'
    if state=='malformed-attributes-existing-skill4':cats['attrs']='broken'
    if state.startswith('duplicate-'):cats['skills']=state[len('duplicate-'):]
    if state.startswith('Running:'):cats['skills']=state

@step(r'retrieval requests (\d+)')
def retrieve(w,mask):w['stats']=w['store'].retrieve(101,int(mask))

@step(r'the resulting category state is (.+)')
def category_result(w,state):
    s=w['stats']
    if state in ('attributes1-lives1-health0-skills0','all-defaults-persisted'):
        eq([s.get(n) for n in ('Build','Reflexes','Intuition','Learn','Charisma','Lives','Bruise','Lethal','Running')],[1,1,1,1,1,1,0,0,0])
        if state=='all-defaults-persisted':eq(w['store'].records[101]['categories'],{'health':'0,0','attrs':'1,1,1,1,1','skills':'','advs':'Lives:1/'})
    elif state=='build0-bruise2-lethal3':eq((s.get('Build'),s.get('Bruise'),s.get('Lethal')),(0,2,3))
    elif state=='all-zero':eq(s.values,[0]*119)
    elif state=='Running3-xp9-last40':eq((s.get('Running'),s.xp[code('Running')],s.last_use[code('Running')]),(3,9,40))
    elif state.startswith('Running2-Blade'):eq((s.get('Running'),s.get('Blade')),(2,int(state[-1])))
    else:raise AssertionError(state)

@step(r'raw stored state (.+)')
def raw(w,state):
    import re
    s=Stats();w['raw']=s
    if state=='all-zero':return
    m=re.fullmatch(r'Running(\d+)-xp(\d+)-last(\d+)',state)
    if m:
        val,xp,last=map(int,m.groups());s.set('Running',val);s.xp[code('Running')]=xp;s.last_use[code('Running')]=last
    elif state=='Lives1-Toughness1-Running2':s.set('Lives',1);s.set('Toughness',1);s.set('Running',2)
    elif state=='Technician-Battlesuit3-xp0':s.set('Technician-Battlesuit',3)
    else:raise AssertionError(state)

@step(r'the (skills|advantages) category is serialized and retrieved from fresh state')
def roundtrip(w,category):
    mask=SKILLS if category=='skills' else ADVS
    w['store'].store(101,w['raw'],mask)
    key='skills' if mask==SKILLS else 'advs';w['text']=w['store'].records[101]['categories'][key]
    from data.characters import CharacterStore
    w['stats']=CharacterStore(w['root']/'characters').retrieve(101,mask)

@step(r'exact text is (.+) and resulting state is (.+)')
def roundtripped(w,text,state):
    eq(w['text'],'' if text=='empty' else text);s=w['stats']
    if state=='all-zero':eq(s.values,[0]*119);return
    if state=='Technician-Battlemech3-Battlesuit0':eq((s.get(107),s.get(108)),(3,0));return
    import re
    m=re.fullmatch(r'Running(\d+)-xp(\d+)-last(\d+)',state)
    if m:
        # "Running2" denotes stored raw level when packed XP also has a bonus.
        eq((s.values[code('Running')],s.xp[code('Running')],s.last_use[code('Running')]),tuple(map(int,m.groups())));return
    m=re.fullmatch(r'Lives(\d+)-Toughness(\d+)-Running(\d+)',state)
    assert m,state;eq((s.get('Lives'),s.get('Toughness'),s.get('Running')),tuple(map(int,m.groups())))

@step(r'Lives is (\d+) and raw ShotsHit is (\d+)')
def coupling(w,lives,old):
    w['stats']=Stats();w['stats'].values[code('Lives')]=int(lives);w['stats'].values[11]=int(old)

@step(r'raw ShotsHit is set to (\d+) in the current stats structure')
def coupled(w,new):w['stats'].set(11,int(new))

@step(r'Lives is (\d+)')
def lives(w,n):eq(w['stats'].get('Lives'),int(n))

@step(r'a cached Running BTH of 7 and changed Build yielding a fresh BTH of 6')
def cache(w):
    values(w,Build=5,Reflexes=5,Running=1);eq(c.skill_target(w['store'],101,'Running'),7)
    w['stats']=w['store'].retrieve(101,ALL);w['stats'].set('Build',6)

@step(r'the operation is (.+)')
def cache_operation(w,operation):
    # The changed attribute has already been persisted without invalidating cache.
    w['store'].store(101,w['stats'],ATTRS)
    if operation=='public-set-value':c.set_value(w['store'],101,'Build',6)
    else:w['store'].store(101,w['stats'],{'store-attributes-only':ATTRS,'store-health-only':HEALTH,'store-skills':SKILLS,'store-advantages':ADVS}[operation])
    w['result']=c.skill_target(w['store'],101,'Running')

@step(r'the next Running BTH is (\d+)')
def cached(w,n):eq(w['result'],int(n))

@step(r'character request (.+) with (ordinary|WizR|Wiz)')
def request(w,request,authority):
    w['request']=request;w['store'].create(102,'Bob')
    w['store'].records[101].update(wizard=authority=='Wiz',wiz_r=authority=='WizR')
    if request=='status-Toughness2':values(w,Toughness=2)
    if request=='status-Contact7':values(w,Contact=7)
    if request=='status-Exceptional17':values(w,Exceptional_Attribute=17)
    if request=='status-rawRunning0-bonus1':
        s=w['store'].retrieve(101,ALL);s.xp[code('Running')]=XP_MAX;w['store'].store(101,s,ALL)

@step(r'the ordinary character control runs')
def run_request(w):
    req=w['request'];store=w['store'];w['error']=None
    try:
        if req.startswith('list-'):
            kind=req.split('-')[1];w['result']=c.char_list(store,kind,102)
        elif req.startswith('status-'):w['result']=c.control(store,101,'status',target='Bob' if req=='status-other' else None)
        elif req.startswith('clear-'):w['result']=c.control(store,101,'clear',target='Bob' if req=='clear-other' else None)
        elif req=='get-unknown-player':w['result']=c.control(store,101,'get',target='Nobody',name='Build')
        elif req.startswith('get-'):w['result']=c.control(store,101,'get',name='Unknown' if req=='get-unknown-value' else 'Build')
        elif req=='set-Build-flag1':w['result']=c.control(store,101,'set',name='Build',flag=1,amount=5)
        else:raise AssertionError(req)
    except ValueError as error:w['error']=str(error)

@step(r'the visible result is (.+)')
def visible(w,expected):
    # Reused result wording is routed by the active feature setup.
    if 'experience_request' in w or 'admin_operation' in w:
        from .experience import control_result
        return control_result(w,expected)
    errors={'authority-error':'authority','power-error':'real power','target-required':'Who do you want','invalid-target':'INVALID TARGET','permission-denied':'PERMISSION DENIED','invalid-value':'INVALID VALUE','only-skills-can-have-flag':'ONLY SKILLS'}
    if expected in errors:assert errors[expected].lower() in (w['error'] or '').lower(),(w['error'],expected);return
    eq(w['error'],None);result=w['result']
    if expected=='status':assert 'attributes' in result and 'skills' in result
    elif expected=='all-source-advantages':eq(result,[r.name for r in VALUES if r.type==2])
    elif expected=='all-five':eq(result,['Build','Reflexes','Intuition','Learn','Charisma'])
    elif expected=='empty':eq(result,[])
    elif expected=='advantage-name-shown':assert 'Toughness' in result['advantages']
    elif expected=='Contact-value7':assert 'Contact: 7' in result['advantages']
    elif expected=='Exceptional-Build-and-Charisma':eq(result['advantages'],['Exceptional Attribute: Build','Exceptional Attribute: Charisma'])
    elif expected=='no-listed-skills':eq(result['skills'],['None'])
    else:raise AssertionError(expected)

@step(r'an uptime of (\d+) seconds')
def uptime(w,n):w['seconds']=int(n)

@step(r'its public duration is requested')
def duration(w):w['result']=c.duration(w['seconds'])

@step(r'the rendered duration is (.+)')
def rendered(w,text):eq(w['result'],text)
