"""Actual personnel audiences and broadcasts, including real shot producers."""
from qa.communications.common import *

def run():
    a=Audit('notifications')
    for ident,n,r,line in rows('notifications'):
        u=unit('A',kind=None);units=[u];characters=None;acts=[];kw={};streams=combat_streams()
        if n==1:
            s=r['state'];audience={'ALL':2,'STARTED':1,'PILOT':0,'PRINTF':2}[r['type']]
            characters=[character(110,10),character(111,10)]
            if 'stopped' in s:u['started']=False
            if 'outside' in s:characters[0]['location']=999
            if 'destroyed' in s:u['destroyed']=True
            if s=='unconscious':u['conscious']=False
            if s=='blinded':u['blinded']=True
            if 'turrets' in s:
                units += [unit('B',kind=None),unit('C',kind=None)]
                characters += [character(120,20),character(130,30)]
                u['communications']['aero_turrets']=['B','C']
                kw['config']={'periodic_updates':False,'arc_override':0 if s.startswith('no-arc') else 1}
            args={'source_id':-1} if s=='negative-ID' else {}
            acts=[inspect(),diag('printf' if r['type']=='PRINTF' else 'notify',audience=audience,message='hello%d' if r['type']=='PRINTF' else 'hello',**({'format_args':[17]} if r['type']=='PRINTF' else {}),**args)]
        elif n==2:
            s=r['fixture'];message='test-broadcast'
            if s=='debug-C3-default':acts=[inspect(),diag('debug',message=message)]
            elif s.startswith(('map-','mech-')):
                units=[unit(x,kind=None) for x in ('ABCD' if 'C,D' in s else 'ABC' if 'B,C' in s else 'AB')]
                if s.startswith('map-'):units[1]['started']=False
                acts=[inspect(),diag('map-broadcast' if s.startswith('map-') else 'mech-broadcast',message=message,**({'target':'B'} if 'target-B' in s else {}))]
            else:
                distance=5.01 if '5.01' in s else 0 if 'XY0' in s else 5
                z=6 if 'Z6' in s else 10 if 'Z10' in s else 0
                u['real']=[1000,1000+distance*322.5,z*322.5]
                if 'unconscious' in s:u['conscious']=False
                if 'stopped-and-started' in s:units.append(unit('B',kind=None,real=[1000,1000,0],started=False))
                acts=[inspect(),diag('limited-broadcast',x=1000,y=1000,z=0,radius=5,dimensions=2 if s.startswith('2D') else 3,message=message)]
        elif n==3:
            s=r['state'];u=unit('Atlas',ident=10,kind=None,contact_id='AB',character=110);units=[u,unit('B',kind=None,contact_id='BB')]
            if s.startswith('single'):
                if s=='single-unseen':u['crit_status']=C['INVISIBLE']
                if 'NB-unseen' in s:
                    u['at']=[3,3,0];units[1]['at']=[3,7,0];units[1]['sensors']=['B','B'];units[1]['equipment']=['Beagle'];kw['map']={'size':[15,15],'hexes':[dict(at=[3,5],terrain='GRASSLAND',elevation=3)]}
                if 'enemy' in s:units[1]['team']=2
                visibility='invisible' if s=='single-unseen' else 'something' if 'NB-unseen' in s else 'clear'
                acts=[cache('B','Atlas',visibility),inspect(),diag('los-broadcast','Atlas',message="'s arm" if 'apostrophe' in s else 'moves')]
            elif s.startswith('pair'):
                units.append(unit('T',ident=30,kind=None,character=130,contact_id='TT'))
                kw['map']={'size':[15,15],'mapvis':2};u['at']=[3,5,0];units[-1]['at']=[3,3,0];units[1]['at']=[3,7,0] if 'only-attacker' in s else [3,1,0] if 'only-target' in s else [7,4,0] if 'neither' in s else [3,4,0]
                aseen='only-attacker' in s or 'both' in s;bseen='only-target' in s or 'both' in s
                acts=[cache('B','Atlas','clear' if aseen else 'invisible'),cache('B','T','clear' if bseen else 'invisible'),inspect(),diag('pair-broadcast','Atlas',target='T',message='hits %s')]
            else:
                units=[unit('A',kind=None,at=[3,4,0])];u=units[0]
                x,y=(3,4) if 'own' in s or s=='hex-height3' else (3,4)
                if 'other' in s:u['at']=[3,5,0]
                msg='$q$' if 'unknown' in s else '$H' if 'dollar-H' in s else '$h'
                if s=='hex-height3':kw['map']=dict(size=[15,15],hexes=[dict(at=[3,4],terrain='GRASSLAND',elevation=3)])
                acts=[inspect(),diag('hex-broadcast',x=x,y=y,message=msg)]
        elif n==4:
            s=r['fixture'];u=unit('A',kind=None,at=[3,5,0],weapons=[dict(name='IS.MediumLaser',section=0,critical=4)])
            b=unit('B',kind=None,at=[4,4,0]);t=unit('T',ident=30,kind=None,character=130,at=[3,3,0],team=2,facing=180)
            units=[u,b,t];kw['map']={'size':[15,15],'mapvis':2};b['at']=[3,7,0] if 'attacker-only' in s else [3,1,0] if 'defender-only' in s else [7,4,0] if 'neither' in s else [3,4,0];streams['attack_rolls']=[2 if 'miss' in s else 12]
            if 'unconscious' in s:b['conscious']=False
            avis='attacker-only' in s or 'both' in s or 'unconscious' in s
            tvis='defender-only' in s or 'both' in s or 'unconscious' in s
            acts=[cache('B','A','clear' if avis else 'invisible'),cache('B','T','clear' if tvis else 'invisible')]
            if s.startswith('hex-'):acts+=[command('lock',args='3 3')]
            acts += [inspect(),command('fire',args='0' if s.startswith('hex-') else '0 TT')]
        else:
            s=r['state'];flags=C['MECH_USUALO'] if 'USUALO' in s else C['MECH_USUALS'] if 'USUALS' in s else C['MECH_USUAL'] if 'USUAL' in s else 0
            characters=[character(110,10,wizard=False),character(111,10,wizard='wizard-nonpilot' in s and 'nonwizard' not in s)]
            if 'destroyed' in s:u['destroyed']=True
            if 'stopped' in s:u['started']=False
            if 'blinded' in s:u['blinded']=True
            if 'unconscious' in s:u['conscious']=False
            if s.startswith('OOC'):u['in_character']=False
            if 'negative-map' in s:u['communications']['mapindex']=-1
            if 'unresolved' in s:u['communications']['mapindex']=9999
            if 'last-use99' in s:u['communications']['last_use']=99
            acts=[diag('common-checks',flags=flags,actor=111 if 'passenger' in s or 'nonpilot' in s else 110,null_unit=s=='null-unit')]
        d=doc(acts,units=units,characters=characters,streams=streams,**kw)
        o=runrow(a,ident,n,r,line,d,mode='public notify/cache diagnostics; ordinary fire producer')
        last=o['results'][-1];want=r['observation']
        before=next((x for x in reversed(o['results'][:-1]) if isinstance(x,dict) and 'inboxes' in x),{}).get('inboxes',{})
        delta=lambda who:inbox(o,who)[len(before.get(str(who),[])):]
        if n==1:
            wanted={'both-occupants':[110,111],'none':[],'pilot-only':[110],'passenger-only-fallback':[111],'occupants':[110,111],'unit-and-both-turret-contents':[110,111,120,130],'unit-contents-only':[110,111],'same-gates-and-hello17':[110,111]}[want]
            a.eq('ordered real recipient IDs',last,wanted)
            for who in (110,111,120,130):a.eq('actual inbox '+str(who),delta(who),['hello17' if r['type']=='PRINTF' else 'hello'] if who in wanted else [])
        elif n==2:
            expected={'map-A-started-B-stopped':[110],'mech-source-A-target-B-observers-C,D':[130,140],'mech-source-A-no-target-observers-B,C':[120,130],
                '2D-radius5-unit-distance5-Z10':[110],'3D-radius5-unit-XY0-Z6-scaled':[],'2D-radius5-unit-distance5.01':[],
                '3D-radius5-unit-distance5-unconscious':[],'2D-radius5-stopped-and-started-inside':[110],'debug-C3-default':[]}[s]
            a.eq('actual broadcast recipients',[who for who in (110,120,130,140) if 'test-broadcast' in delta(who)],expected)
            if s.startswith(('2D','3D')):a.eq('geometric count independent of inbox',last,2 if 'count2' in want else 1 if 'count1' in want else 0)
            if s=='debug-C3-default':a.eq('no external debug action',state(o).get('external_effects',[]),[])
        elif n==3:
            if s.startswith('single'):a.eq('observer-specific identity/spacing',delta(120),[] if want=='no-delivery' else [want])
            elif s.startswith('pair'):
                expected=[] if 'neither' in s else [('Atlas [ab]' if aseen else 'Someone')+' hits '+('T [tt]' if bseen else 'someone')]
                a.eq('pair audience text',delta(120),expected);a.eq('source excluded',delta(110),[]);a.eq('target excluded',delta(130),[])
            else:a.eq('hex source substitutions',delta(110),['$q' if 'unknown' in s else 'your hex' if s=='hex-height3' else want])
        elif n==4:
            a.true('ordinary firing accepted',last.get('accepted'))
            shotmessages=[t for t in delta(120) if any(q in t for q in (' hits ',' misses ',' fires '))]
            if 'unconscious' in s or 'neither' in s:a.eq('suppressed observer',shotmessages,[])
            else:
                a.eq('one fire broadcast',len(shotmessages),1)
                fragment='Something misses T [TT]' if 'miss-defender' in s else 'A [aa] fires a MediumLaser at something!' if 'attacker-only' in s else 'Something fires' if 'defender-only' in s else 'A [aa] fires' if s.startswith('hex') else 'A [aa] hits T [TT]'
                a.true('actual visibility text',bool(shotmessages) and fragment in shotmessages[0])
            a.eq('counter exactly once',state(o)['shots_hit']+state(o)['shots_missed'],0 if s.startswith('hex') else 1)
        else:
            if want.startswith('eligible'):a.eq('eligible source branch',last,None)
            else:
                fragment={'rejected':'Invalid unit','destroyed-error':'destroyed','reactor-error':'Reactor','blinded-error':'blinded','unconscious-error':'unconscious','pilot-only-error':'only the pilot','no-map-error':'no map','invalid-map-shutdown-reset-minus1':'invalid map'}[want]
                a.true('exact eligibility rejection',isinstance(last,str) and fragment in last)
            if 'reset-minus1' in want:a.eq('actual shutdown',state(o)['started'],False);a.eq('reset invalid map',state(o)['mapindex'],-1)
            if 'last-use0' in want:a.eq('last-use cleared',state(o)['last_use'],0)
    return a.save()

if __name__=='__main__':run()
