"""Source XP arithmetic/eligibility; ordinary producers have separate workflows."""
from qa.pilots.common import *

def run_awards():
    a=Audit('awards')
    for case,n,r,line in rows('awards'):
        c=character();u=unit(character=101,tonnage=50,construction={'mech_bv':1000},max_speed=64.5);v=unit('v',20,tonnage=50,construction={'mech_bv':1000},max_speed=64.5);chars=[c];units=[u,v];actions=[dict(op='clock',name='skip_seconds',seconds=101)];options={'xp':{'oldxpsystem':False,'use_pilot_bv':False}};streams={'xp_old_gate':[1],'damage_entry':[7]*20,'critical_rolls':[2]*20}
        if n==1:
            kind=r['producer'];condition=r['condition'];act=dict(op='experience',kind=kind,player=101,reason=int(r['reason']))
            if condition!='no-unit':act['unit']='u'
            if kind in ('spot','artillery'):act['target']='v'
            if condition=='wrong-pilot':chars.append(character(102));act['player']=102
            if condition=='friendly':v['team']=1
            if condition=='disconnected':c['connected']=False
            if condition.startswith('sameXY'):
                u['at']=[0,0,0]
                if condition.endswith('addanyway'):act['addanyway']=True
            actions.extend([act,dg()])
        elif n==2:
            c['values']['Perception']=2;u['core']={'per':int(r['per'])};streams['perception_rolls']=[int(r['roll'])];actions.extend([dict(op='experience',kind='perception',unit='u',modifier=-2),dg()])
        elif n==3:
            options['xp']['oldxpsystem']=r['system']=='old';s=r['condition'];bth=13 if s=='BTH13' else 2 if s.startswith('BTH2') else 6
            options['xp']['bthmod']=s=='BTH2-bthmod-on'
            if s=='NoGunXP':v['status2']=0x1000000
            if s=='all-sections-destroyed':
                for sec in v['sections']:sec.update(armor=0,rear=0,internal=0)
            if s=='same-team':v['team']=1
            if s=='attacker-tons0':u['tonnage']=0
            if s=='MECH-shoots-MW':v['class']='MW'
            if s=='target-destroyed':v['destroyed']=True
            player=101
            if s=='wrong-gunpilot':chars.append(character(102));player=102
            actions.extend([dict(op='experience',kind='gun',unit='u',target='v',player=player,weapon='IS.MediumLaser',damage=10,multiplier=100,bth=bth),dg()])
        elif n==4:actions.append(dict(op='pilot_diagnose',kind='pilot-bv',gunnery=int(r['gunnery']),piloting=int(r['piloting'])))
        elif n==5:actions.append(dict(op='pilot_diagnose',kind='movement-value',speed=float(r['mp'])*10.75))
        elif n==6:
            options['xp'].update(defaultweapbv=100,defaultweapdam=10,xp_modifier=1,xpgain_cap=100,bthmod=False,missilemod=1,ammomod=1)
            s=r['config'];wf={'bv':100,'vrt':30,'weapon_type':0}
            if s=='missile-factor0.5':wf['weapon_type']=1;options['xp']['missilemod']=.5
            if s=='ammo-factor2':wf['weapon_type']=3;options['xp']['ammomod']=2
            if s=='vrt7.5-factor-on':wf['vrt']=7.5;options['xp']['vrtmod']=True
            if s=='perunit2':u['construction']['xp_mod']=2
            if s=='cap3':options['xp']['xpgain_cap']=3
            actions.extend([dict(op='experience',kind='gun',unit='u',target='v',weapon='IS.MediumLaser',damage=10,multiplier=100,bth=6,weapon_fields=wf),dg()])
        elif n==7:streams['xp_old_gate']=[int(r['draw'])];actions.append(dict(op='pilot_diagnose',kind='old-probability',difficulty=int(r['difficulty'])))
        else:
            s=r['mode'];phys=1 if s=='physical1' else 2 if s=='physical2' else 0
            if s=='recursive-transfer':v['sections'][0].update(armor=0,internal=0)
            if s=='rejected-safety':v['status']=0x8|0x400000
            actions.extend([dict(op='pilot_diagnose',kind='damage-entry',unit='u',target='v',section=0 if s=='recursive-transfer' else 4,weapon='IS.MediumLaser',amount=9,physical=phys,bth=6),dg()])
        out=a.cli(case,doc(actions,characters=chars,units=units,streams=streams,pilots=options),identity=dict(outline=n,line=line,values=r));last=out['results'][-1];req=out['state']['units']['u']['xp_requests']
        if n==1:
            if r['request']=='none':a.eq('no accepted gain',out['results'][1],False)
            else:
                name,num=r['request'].split(':');a.eq('durable XP',last['xp'][INDEX[name]]%XP_MAX,int(num));a.eq('actual gain accepted',out['results'][1],True)
        elif n==2:a.eq('perception return',out['results'][1],yes(r['success']));a.eq('cached MechPer',out['state']['units']['u']['per'],int(r['stored']));a.eq('durable perception XP',last['xp'][INDEX['Perception']]%XP_MAX,int(r['xp']))
        elif n==3:a.eq('gun eligibility',out['results'][1],r['outcome']=='accepted');a.eq('durable gain present',last['xp'][63]>0,r['outcome']=='accepted')
        elif n==4:a.near('pilot BV source float',last,float(r['factor']))
        elif n==5:a.eq('source move bin',last,int(r['value']))
        elif n==6:a.eq('durable arithmetic award',last['xp'][63]%XP_MAX,int(r['xp']));a.eq('new system no old draw',[d for d in out['draws'] if d['name']=='xp_old_gate'],[])
        elif n==7:a.eq('old probability equality/cap',last,int(r['award']));a.eq('source one draw',[d['value'] for d in out['draws'] if d['name']=='xp_old_gate'],[int(r['draw'])])
        else:
            route=r['route']
            if route=='none':a.eq('no XP',req,[])
            elif route=='piloting3':a.eq('one piloting gain',[(q['producer'],q['amount']) for q in req],[('piloting',3)])
            else:a.eq('one gun gain',len(req),1);a.eq('gun route',req[0]['producer'],'gun')
    return a.save()
