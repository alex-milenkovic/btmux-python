from . import step,base,eq,truth,draws,numbers,values
from data.character_values import code,XP_MAX
from data.characters import ALL,SKILLS
from systems import characters as c

@step(r'source character attributes Build5 Reflexes4 Intuition3 Learn2 Charisma1 unless overridden')
def fresh(w):base(w);values(w,Build=5,Reflexes=4,Intuition=3,Learn=2,Charisma=1)

@step(r'skill (.+) with raw level 2 and packed bonus 1')
def skill(w,name):
    w['skill']=name
    if code(name)<0:return
    s=w['store'].retrieve(101,ALL);s.set(name,2);s.xp[code(name)]=XP_MAX
    w['store'].store(101,s,ALL)

@step(r'target calculation uses XP (True|False) and modifier (-?\d+)')
def target(w,xp,modifier):w['result']=c.skill_target(w['store'],101,w['skill'],int(modifier),truth(xp))

@step(r'BTH is (-?\d+)')
def target_result(w,n):eq(w['result'],int(n))

@step(r'Number dice (.+)')
def dice(w,text):w['dice']=numbers(text)

@step(r'the character rolls (.+)')
def roll(w,kind):
    count=2
    if kind.startswith('d6-'):count=int(kind[3:].replace('minus','-'));kind='d6'
    w['result']=draws(w,w['dice'],c.roll_dice,kind,count)

@step(r'result is (-?\d+) with (\d+) Number calls and zero Roll statistics')
def rolled(w,result,count):eq(w['result'],int(result));eq(len(w['calls']),int(count));eq(w['random'].total_rolls,0)

@step(r'effective skill (-?\d+) with target (\d+) and dice (.+)')
def skill_fixture(w,level,target,dice):
    level,target=int(level),int(target);w['dice']=numbers(dice);w['skill']='Unknown' if level==-1 else 'Running'
    if level>=0:values(w,Build=18-target-level-1,Reflexes=1,Running=level)

@step(r'named skill success and margin are each evaluated in fresh identical state')
def successes(w):
    w['success']=draws(w,w['dice'],c.skill_success,w['store'],101,w['skill'])['success']
    w['margin']=draws(w,w['dice'],c.skill_margin,w['store'],101,w['skill'])

@step(r'success is (True|False) and margin is (-?\d+)')
def success_result(w,success,margin):eq(w['success'],truth(success));eq(w['margin'],int(margin))

@step(r'first margin (-?\d+) and second margin (-?\d+) from sequential source rolls')
def contest(w,first,second):
    values(w,Build=5,Reflexes=5,Running=1);w['store'].create(102,'Bob')
    for name,val in dict(Build=5,Reflexes=5,Running=1).items():c.set_value(w['store'],102,name,val)
    # Both targets are 7; independently choose two legal Number dice per margin.
    w['dice']=[3,4+int(first),3,4+int(second)]

@step(r'the two characters contest the skill')
def opposed(w):w['result']=draws(w,w['dice'],c.opposed,w['store'],101,'Running',102,'Running')

@step(r'the winner is (first|second|tie)')
def winner(w,result):eq(w['result'],{'first':101,'second':102,'tie':0}[result])

@step(r'attribute value (-?\d+) and a skilled roll of 7')
def attribute(w,val):
    w['attribute']='Unknown' if val=='-1' else 'Build'
    if val!='-1':values(w,Build=int(val))

@step(r'attribute saving target and success are computed')
def attribute_run(w):
    w['target']=c.attribute_target(w['store'],101,w['attribute'])
    w['result']=draws(w,[] if w['attribute']=='Unknown' else [2,5],c.attribute_success,w['store'],101,w['attribute'])

@step(r'target is (-?\d+) and success is (True|False|-1)')
def attribute_result(w,target,result):eq(w['target'],int(target));eq(w['result'],-1 if result=='-1' else truth(result))

@step(r'Toughness has value (\d+)')
def advantage(w,val):values(w,Toughness=int(val))

@step(r'the named Boolean advantage is queried')
def advantage_run(w):w['result']=c.has_advantage(w['store'],101,'Toughness')

@step(r'it is (True|False)')
def advantage_result(w,result):eq(w['result'],truth(result))
