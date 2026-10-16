"""Exact source identities, mode priorities, flags and network display boundaries."""
from qa.communications.common import *

def modeword(text):
    text=text.replace('RAC_TWO','RAC_TWOSHOT').replace('RAC_FOUR','RAC_FOURSHOT').replace('RAC_SIX','RAC_SIXSHOT')
    if text=='none':return 0
    return sum(C[t+'_MODE'] for t in text.split('+'))

def run():
    a=Audit('displays')
    for ident,n,r,line in rows('displays'):
        u=unit('A',kind=None);units=[u];acts=[];expected=None
        if n==1:
            v=unit('Atlas',ident=20,kind=None,contact_id='AB',character=120);units.append(v)
            relation=r['relation'];v['team']=2 if relation=='enemy' else 1
            acts=[cache('A','Atlas','clear' if yes(r['visible']) else 'invisible')]
            kw={'null_viewer':True} if relation=='null-viewer' else {'source_id':-1} if relation=='invalid-target' else {}
            acts.append(diag('identity','Atlas' if relation=='self-GetMechID' else 'A',**({} if relation=='self-GetMechID' else {'target':'Atlas'}),**kw))
            expected='' if r['identity']=='empty' else r['identity']
        elif n==2:
            s=r['input']
            if s.startswith('MOVE_'):u['movement']=s[5:];acts=[diag('move-label')]
            else:
                cls,arc=s.split('-',1);u['class']=cls
                mask={'forward-and-right':1|4,'right':4,'left':2,'rear':8,'turret-only':16}[arc]
                acts=[diag('arc-label',arc=mask)]
            expected=r['label']
        elif n in (3,4):
            s=r['mode'];weapon='IS.NarcBeacon' if s=='NARC-on-NARC-weapon' else 'IS.LRM-10'
            mode=modeword('NARC' if s=='NARC-on-NARC-weapon' else s)
            u['weapons']=[dict(name=weapon,section=2,critical=0,ammo_mode=mode if n==3 else 0,fire_mode=mode if n==4 else 0)]
            acts=[diag('ammo',weapon=weapon,mode=mode) if n==3 else diag('fire-letter',mode=mode),diag('slot-letters',section=2,slot=0)]
        else:
            s=r['state'];spaces=0;level=0
            if s.startswith('fallen-'):u['fallen']=True;u['movement']=s[7:]
            elif s=='burning-and-jellied':u['crit_status']=C['JELLIED'];acts=[dict(op='schedule',unit='A',callback='vehicle_burn_event',delay=100)]
            elif s=='light-on-and-illuminated':u['status2']=C['SLITE_ON'];u['crit_status']=C['SLITE_LIT']
            elif 'ECM' in s:
                u['communications']['status2']=C['ECM_PROTECTED']|(C['ECM_DISTURBANCE'] if 'disturbed' in s else 0);level=1 if 'level1' in s else 0
            elif 'torso' in s:
                u['status']=C['TORSO_RIGHT']|(C['TORSO_LEFT'] if 'left' in s else 0)|(C['STARTED'] if 'shutdown' not in s else 0);level=1 if 'level1' in s else 0
            elif s=='level2-destroyed-shutdown':u.update(destroyed=True,started=False);level=2
            elif s=='indent3-combat-safe':u['status']=C['STARTED']|C['COMBAT_SAFE'];spaces=3
            if s.startswith('network-'):
                u=unit('A');v=unit('B');units=[u,v]
                for section in v['sections']:section.update(armor=0,armor_orig=0,rear=0,rear_orig=0,internal=0,internal_orig=0)
                if '33-of100' in s:v['sections'][0].update(armor=33,armor_orig=100,internal=2,internal_orig=3)
                acts=[command('c3i','B','AA'),diag('percentages','B'),command('c3inetwork')]
            elif s.startswith('contacts-'):
                units=[unit('A'),unit('B',at=[3,6,0]),unit('T',ident=30,kind=None,at=[3,3,0],character=130,team=2)]
                acts=[command('c3i','B','AA')]
                if 'live-ranges' in s:
                    units[0]['at']=[3,11,0];units[1]['at']=[3,8,0];units[2]['at']=[3,3,0]
                    units.append(unit('D',ident=40,kind=None,at=[3,10,0],character=140,destroyed=True))
                    acts += [cache('A','B'),cache('A','T'),cache('A','D')]
                else:
                    own='invisible' if 'own-unseen' in s else 'something';peer='clear' if s.endswith('network-clear') else 'invisible'
                    acts += [cache('A','T',own),cache('B','T',peer)]
                acts += [command('c3itargets')]
            elif s.startswith('status3'):
                units.append(unit('B',kind=None));u['crit_status']=C['SPINNING'];acts=[diag('status',target='B',index=3)]
            else:acts.append(diag('flags',spaces=spaces,level=level))
        o=runrow(a,ident,n,r,line,doc(acts,units=units),mode='source presentation and allocated-slot diagnostics; command reports')
        results=o['results'];last=results[-1]
        if n in (1,2):a.eq('exact source display',last,expected)
        elif n in (3,4):
            letter=' ' if r['letter']=='space' else r['letter']
            a.eq('real slot wrapper',last['ammo' if n==3 else 'fire'],letter)
            if n==3:
                description='' if r['description']=='empty' else r['description'].replace('leading-space:',' ')
                a.eq('description and model letter',results[-2],dict(description=description,letter=letter))
            else:a.eq('model fire letter',results[-2],letter)
        else:
            want=r['observation']
            if s.startswith('fallen-'):a.eq('exact fallen label',last,['%cr%ch'+want.replace('-',' ')+'%cn'])
            elif s=='burning-and-jellied':a.eq('one fire line',last,['%cr%chON FIRE%cn'])
            elif s=='light-on-and-illuminated':a.eq('light precedence',last,['%cg%chSEARCHLIGHT ON%cn'])
            elif s=='own-level0-ECM-protected-and-disturbed':a.eq('source private order',last,['%cg%chPROTECTED BY ECM%cn','%cy%chAFFECTED BY ECM%cn'])
            elif s in ('other-level1-ECM-protected','level2-destroyed-shutdown'):a.eq('level filter',last,[])
            elif s=='level0-torso-right-and-left':a.eq('both torso lines',last,['Torso is 60 degrees right','Torso is 60 degrees left'])
            elif s=='level1-torso-right-shutdown':a.eq('final shutdown flag',last,['SHUTDOWN'])
            elif s=='indent3-combat-safe':a.eq('source indentation',last,['   %cb%chCOMBAT SAFE%cn'])
            elif s.startswith('network-'):
                percentages=dict(armor=33,internal=66) if '33-of100' in s else dict(armor=0,internal=0)
                a.eq('float percentage truncation',results[-2],percentages);a.true('actual network report',last['ok'])
                a.true('report percentage fields',f'a: {percentages["armor"]:3d} i: {percentages["internal"]:3d}' in last['rows'][1])
            elif s.startswith('contacts-'):
                rowsout=last['rows'][1:-1];trows=[x for x in rowsout if '[TT]' in x or '[tt]' in x]
                if 'live-ranges' in s:a.eq('destroyed-first descending order',[re.search(r'\[([^]]+)\]',x)[1].lower() for x in rowsout],['dd','tt','bb'])
                elif 'own-unseen' in s:a.eq('unseen row omitted',trows,[])
                else:
                    a.eq('one target row',len(trows),1)
                    if s.endswith('network-clear'):a.true('network identifies target',' T ' in trows[0] and 'something' not in trows[0])
                    else:a.true('masked name and statuses','something' in trows[0] and 'S:     ' in trows[0])
            else:a.eq('viewer spinning quirk',last,'X')
    return a.save()

if __name__=='__main__':run()
