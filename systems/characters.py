# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/btechstats.c

"""Source character skills, XP, and local player/administrator controls."""
from data.character_values import VALUES,SKILL,ADVANTAGE,ATTRIBUTE,ATHLETIC,PHYSICAL,MENTAL,SOCIAL,SK_XP,XP_MAX,code
from data.characters import Stats,ALL,HEALTH,ATTRS,ADVS,SKILLS,integer,divide,remainder


def value(store,player,name):return store.retrieve(player,ALL).get(name)


def set_value(store,player,name,new):
    stats=store.retrieve(player,ALL);stats.set(name,new);store.store(player,stats,ALL)


def target_base(store,player,stats,index,modifier=0,use_xp=True):
    index=code(index)
    if index<0 or VALUES[index].type!=SKILL:return 18
    if use_xp and store.cache is not None and store.cache[:2]==(player,index):return store.cache[2]+modifier
    flag=VALUES[index].flags
    pair=next((names for mask,names in ((ATHLETIC,('Build','Reflexes')),(PHYSICAL,('Reflexes','Intuition')),
         (MENTAL,('Intuition','Learn')),(SOCIAL,('Intuition','Charisma'))) if flag&mask),None)
    if pair is None:return 18
    skill=stats.get(index) if use_xp else stats.values[index]
    if skill==-1:return 18
    target=18-sum(stats.get(name) for name in pair)-skill
    if use_xp:store.cache=(player,index,target)
    return target+(modifier if use_xp else 0)


def skill_target(store,player,name,modifier=0,use_xp=True):
    return target_base(store,player,store.retrieve(player,ATTRS|SKILLS),code(name),modifier,use_xp)


def raw_xp(store,player,index):
    """char_getxpbycode includes valid non-skill codes in its domain."""
    index=code(index)
    if index<0:return 0
    return remainder(store.retrieve(player,SKILLS).xp[index],XP_MAX)


def scaled_threshold(store,player,stats,index):
    threshold=store.thresholds[index]
    if threshold<=0:return 0
    target=target_base(store,player,stats,index,use_xp=False)
    for _ in range(max(0,target-4)):threshold=divide(threshold,3)
    for _ in range(max(0,4-target)):threshold=integer(threshold*3)
    return max(1,threshold)


def pack_xp(store,player,stats,index):
    raw=remainder(integer(stats.xp[index]),XP_MAX)
    threshold=scaled_threshold(store,player,stats,index)
    remaining=raw;bonus=0
    if threshold:
        while remaining>threshold:
            remaining-=threshold;bonus+=1;threshold=integer(threshold*3)
    stats.xp[index]=integer(raw+XP_MAX*bonus)
    return bonus


def next_threshold(store,player,name):
    index=code(name)
    if index<0 or VALUES[index].type!=SKILL:return -1
    stats=store.retrieve(player,ATTRS|SKILLS)
    threshold=scaled_threshold(store,player,stats,index)
    if not threshold:return -1
    target=target_base(store,player,stats,index)
    start=target_base(store,player,stats,index,use_xp=False)
    total=1
    while target<=start:
        start-=1;total=integer(total+threshold);threshold=integer(threshold*3)
    return total


def gain_xp(store,player,name,amount,*,now,override=False):
    index=code(name)
    if index<0:return 0
    stats=store.retrieve(player,SKILLS|ATTRS)
    if not override and not (now>stats.last_use[index]+30 or VALUES[index].flags&SK_XP):return 0
    stats.last_use[index]=integer(now);stats.xp[index]=integer(stats.xp[index]+integer(amount))
    pack_xp(store,player,stats,index);store.store(player,stats,SKILLS)
    return 1


def lower_xp(store,player,promillage):
    stats=store.retrieve(player,ALL)
    for i,xp in enumerate(stats.xp):
        if not xp:continue
        if xp<0:stats.xp[i]=0;continue
        stats.xp[i]=divide(integer(remainder(xp,XP_MAX)*integer(promillage)),1000)
        pack_xp(store,player,stats,i)
    store.store(player,stats,ALL)


def has_advantage(store,player,name):
    return store.retrieve(player,ATTRS|ADVS|HEALTH).get(name)==1


def roll_dice(kind='skilled',count=2):
    from core.randomness import draw,number
    n=3 if kind in ('saving','unskilled') else 2 if kind=='skilled' else count
    if kind not in ('saving','unskilled','skilled','d6'):raise ValueError('Unknown character dice family')
    dice=[draw('character_d6',1,6,lambda:number(1,6)) for _ in range(max(0,integer(n)))]
    if kind=='saving':return sum(dice)-min(dice)
    if kind=='unskilled':return sum(dice)-max(dice)
    return sum(dice)


def skill_margin(store,player,name,modifier=0):
    target=skill_target(store,player,name,modifier)
    roll=roll_dice('unskilled' if value(store,player,name)==0 else 'skilled')
    return roll-target


def skill_success(store,player,name,modifier=0,loud=False):
    target=skill_target(store,player,name,modifier)
    roll=roll_dice('unskilled' if value(store,player,name)==0 else 'skilled')
    messages=[f'You make a {name} skill roll!',f'Modified skill BTH : {target} Roll : {roll}'] if loud else []
    from systems.character_display import notify_character
    notify_character(store,player,messages)
    return {'success':roll>=target,'target':target,'roll':roll,'margin':roll-target,'messages':messages}


def opposed(store,first,skill1,second,skill2):
    a=skill_margin(store,first,skill1);b=skill_margin(store,second,skill2)
    return first if a>b else second if b>a else 0


def attribute_target(store,player,name):
    val=value(store,player,name)
    return -1 if val==-1 else 0 if val>9 else 18-2*val


def attribute_success(store,player,name):
    target=attribute_target(store,player,name)
    return -1 if target==-1 else roll_dice()>=target


def duration(seconds):
    if seconds<=0:return '#-1 INVALID VALUE'
    parts=[]
    for divisor,label in ((31104000,'year'),(2592000,'month'),(86400,'day'),(3600,'hour'),(60,'minute'),(1,'second')):
        count,seconds=divmod(seconds,divisor)
        if count:parts.append(f'{count} {label}'+('s' if count>1 else ''))
    return ', '.join(parts[:-1])+' and '+parts[-1] if len(parts)>1 else parts[0]


def list_values(kind=-1,*,store=None,caller=None):
    if not -1<=kind<=3:raise ValueError('Invalid character value type')
    names=[r.name for r in VALUES if kind<0 or r.type==kind]
    heading='List of charvalues available:' if kind<0 else f"List of {('Char_value','Char_skill','Char_advantage','Char_attribute')[kind]} available:"
    lines=[heading]
    for i in range(0,len(names),3):lines.append((' ' if i else '')+''.join(f'{name:<23} ' for name in names[i:i+3]))
    lines+=[' ',f'Total of {len(names)} things found.']
    if store is not None:
        from systems.character_display import notify_character
        notify_character(store,caller,lines)
    return lines


def char_list(store,kind,player=None,*,caller=0):
    if player is not None:
        player=store.lookup(caller,f'#{player}' if isinstance(player,int) else player)
        if player==-1:raise ValueError('#-1 FUNCTION (BTCHARLIST) INVALID TARGET')
    types={'skills':SKILL,'advantages':ADVANTAGE,'attributes':ATTRIBUTE}
    if kind.lower() not in types:raise ValueError('#-1 FUNCTION (BTCHARLIST) INVALID VALUE')
    typ=types[kind.lower()];stats=store.retrieve(player,ALL) if player is not None else None
    return ' '.join(row.name for i,row in enumerate(VALUES) if row.type==typ and
            (stats is None or typ!=SKILL or stats.get(i)!=0 or raw_xp(store,player,i)!=0))


def status(store,player):
    rec=store.record(player);stats=store.retrieve(player,ALL)
    attrs={name:stats.get(name) for name in ('Build','Reflexes','Intuition','Learn','Charisma')}
    result={'lives':stats.get('Lives'),'attributes':attrs,
            'attribute_targets':{name:18-2*val for name,val in attrs.items()},
            'characteristics':{label:18-attrs[a]-attrs[b] for label,a,b in
                (('Athletic','Build','Reflexes'),('Physical','Reflexes','Intuition'),('Mental','Intuition','Learn'),('Social','Intuition','Charisma'))},
            'advantages':[],'advantage_groups':[],'skills':[]}
    if player:
        result.update(name=rec.get('name',''),id=player,bruise=stats.get('Bruise'),lethal=stats.get('Lethal'),maximum=10*attrs['Build'])
        if rec.get('faction'):result['faction']=rec['faction']
    for i,row in enumerate(VALUES):
        raw=stats.values[i]
        if not raw:continue
        if row.type==ADVANTAGE:
            start=len(result['advantages'])
            if row.flags==1:result['advantages'].append(row.name)
            elif row.flags==0:result['advantages'].append(f'{row.name}: {raw}')
            elif row.flags==2:
                result['advantages'].extend('Exceptional Attribute: '+name for bit,name in zip((1,2,4,8,16),attrs) if raw&bit)
            result['advantage_groups'].append(result['advantages'][start:])
        elif row.type==SKILL:result['skills'].append({'name':row.name,'level':raw,'target':skill_target(store,player,i)})
    if not result['skills']:result['skills']=['None']
    from systems.character_display import status_lines
    result['messages']=status_lines(result)
    return result


def threshold_control(store,args,caller=None):
    from systems.character_display import notify_character
    try:return _threshold_control(store,args,caller)
    except ValueError as exc:
        notify_character(store,caller,[str(exc)])
        raise


def _threshold_control(store,args,caller):
    from systems.combat_commands import read_number
    tokens=args.split()
    if len(tokens)!=2:raise ValueError('Invalid arguments!')
    try:threshold=integer(read_number(tokens[1]))
    except ValueError:raise ValueError('Invalid value!') from None
    if threshold<0:raise ValueError('Threshold needs to be >=0 (0 = no gains possible)')
    i=code(tokens[0])
    if i<0:raise ValueError("That isn't any charvalue!")
    if VALUES[i].type!=SKILL:raise ValueError("That isn't any skill!")
    store.thresholds[i]=threshold
    from core.effects import emit_log
    actor=f'#{caller}' if caller is not None else 'unspecified caller'
    emit_log(store,'LOG_WIZARD','WIZ','CHANGE',f'Exp threshold for {VALUES[i].name} changed to {threshold} by {actor}')
    return threshold


def get_threshold(store,name):
    i=code(name or '')
    return store.thresholds[i] if i>=0 and VALUES[i].type==SKILL else -1


def xp_top(store,name,*,caller=None):
    from systems.character_display import notify_character
    try:return _xp_top(store,name,caller)
    except ValueError as exc:
        if caller is not None:notify_character(store,caller,[str(exc)])
        raise


def _xp_top(store,name,caller):
    if not name.strip():raise ValueError('Invalid argument!')
    index=code(name.lstrip())
    if index<0:raise ValueError('Invalid value name!')
    if VALUES[index].type!=SKILL:raise ValueError('Only skills have XP (for now at least)')
    rows=[];total=0
    for ident,rec in sorted(store.records.items()):
        if not rec['is_player'] or rec.get('wizard'):continue
        xp=store.retrieve(ident,SKILLS).xp[index]
        if not xp:continue
        raw=remainder(xp,XP_MAX);total=integer(total+raw)
        rows.append({'id':ident,'name':rec['name'],'xp':raw})
    if len(rows)>=10000:raise ValueError('Unsupported XP leaderboard source array capacity')
    if rows and not total:raise ValueError('Unsupported zero-total XP percentage division')
    for i in range(len(rows)-1):
        for j in range(i+1,len(rows)):
            if rows[j]['xp']>rows[i]['xp']:rows[i],rows[j]=rows[j],rows[i]
    from systems.character_display import menu,notify_character
    result={'rows':[row|{'percent':100.0*row['xp']/total} for row in rows[:16]],'total':total}
    entries=[(None,1)]
    for rank,row in enumerate(result['rows'],1):
        entries.extend([(f"{rank:3d}. {row['name']}",2),(f"{row['xp']} ({row['percent']:.3f} %)",2)])
    entries.append((None,1))
    if total:entries.extend([(f'Grand total: {total} points',2),(None,1)])
    result['messages']=menu(entries)
    if caller is not None:notify_character(store,caller,result['messages'])
    return result


def control(store,caller,kind,*,target=None,name='',amount=0,flag=0,now=0):
    """Source permission/error order for ordinary character commands/functions."""
    from systems.character_display import notify_character
    try:
        result=_control(store,caller,kind,target=target,name=name,amount=amount,flag=flag,now=now)
    except ValueError as exc:
        if kind in ('clear','status'):notify_character(store,caller,[str(exc)])
        raise
    if kind=='clear':notify_character(store,caller,[result])
    elif kind=='status':notify_character(store,caller,result['messages'])
    return result


def _control(store,caller,kind,*,target=None,name='',amount=0,flag=0,now=0):
    rec=store.record(caller)
    if kind=='clear':
        if not rec.get('wiz_r'):raise ValueError('Sorry, only those with the real power may clear players stats')
        if not target:raise ValueError('Who do you want to clear the stats from?')
    ident=caller if target is None or target=='' else store.lookup(caller,target)
    if ident==-1:
        raise ValueError("I don't know who that is" if kind in ('clear','status') else '#-1 INVALID TARGET')
    if kind=='clear':store.clear_record(ident);return f'Player #{ident} stats cleared'
    if kind=='status':
        if ident!=caller and not rec.get('wiz_r'):raise ValueError('You do not have the authority to check that players stats')
        return status(store,ident)
    if kind not in ('get','set'):raise ValueError('Unknown character control')
    if not rec.get('wizard'):raise ValueError('#-1 PERMISSION DENIED!')
    from systems.combat_commands import read_number
    try:index=code(read_number(str(name)))
    except ValueError:index=code(name)
    if index<0:raise ValueError('#-1 INVALID VALUE')
    flag=int(flag)
    if kind=='get':
        if VALUES[index].type==SKILL:
            if flag==4:return next_threshold(store,ident,index)
            if flag==3:return store.retrieve(ident,SKILLS).values[index]
            if flag==2:return raw_xp(store,ident,index)
            if flag:return skill_target(store,ident,index)
        return value(store,ident,index)
    if flag and VALUES[index].type!=SKILL:raise ValueError('#-1 ONLY SKILLS CAN HAVE FLAG')
    if not flag:set_value(store,ident,index,amount)
    elif flag==1:
        set_value(store,ident,index,0)
        raw_value=skill_target(store,ident,index)-amount
        set_value(store,ident,index,max(0,raw_value))
    else:
        delta=amount-raw_xp(store,ident,index) if flag==3 else amount
        gain_xp(store,ident,index,delta,now=now,override=True)
    label=VALUES[index].name;person=store.record(ident)['name']
    if flag in (0,1):return f"{person}'s {label} set to {0 if flag==1 and raw_value<0 else value(store,ident,index)}"
    message=f"{person}'s {label} XP set to {amount}." if flag==3 else f'{person} gained {amount} more {label} XP.'
    from core.effects import emit_channel
    text=(f"{caller} set {ident}'s {label} XP to {amount}" if flag==3 else
          f'#{caller} added {amount} more {label} XP to #{ident}')
    emit_channel(store,'MechXP',text)
    return message


def attached(actor):
    return actor is not None and getattr(actor,'_character_store',None) is not None


def actor_value(actor,name,default=0):
    if attached(actor):return value(actor._character_store,actor._character_id,name)
    return getattr(actor,name.lower(),default) if actor is not None else default


def actor_advantage(actor,name):
    if attached(actor):return has_advantage(actor._character_store,actor._character_id,name)
    return actor_value(actor,name)==1


def character_store_for(owner, actor=None):
    """Use current configured character storage for source character consumers."""
    if attached(actor):
        return actor._character_store
    engine = getattr(owner, '_engine', None)
    return (getattr(engine, 'character_store', None) or
            getattr(getattr(engine, 'personnel', None), 'characters', None))


def source_stats(owner, actor, mask):
    from data.characters import Stats
    store = character_store_for(owner, actor)
    if store is not None:
        return store.retrieve(getattr(actor, '_character_id', getattr(actor, '_id', actor)), mask)
    stats = Stats.fresh()
    health = getattr(actor, 'health', {}) or {}
    skills = getattr(actor, 'skills', {}) or {}
    for name in ('Build', 'Reflexes', 'Running', 'Bruise', 'Lethal'):
        val = health.get(name.lower(), skills.get(name, getattr(actor, name.lower(), stats.get(name))))
        stats.set(name, int(val))
    return stats
