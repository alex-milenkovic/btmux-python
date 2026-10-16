"""Independent editor, section and technology expectations from C/approved tables."""
from qa.construction_qa_common import *
from qa.construction_qa_numeric import blank,CLASSES,MOVES,table,tech

def run(a):
    names=table('mech_types');moves=table('move_types');parts=table('internals');fm=table('crit_fire_modes');am=table('crit_ammo_modes')
    for outline in (1,2,3,4):
        for line,r in examples('sections',outline):
            u=blank(r.get('unit','Mech'),r.get('move','Biped'))
            if outline==1:
                sections={'Head':7,'Center_Torso':4,'Left_Arm':0,'Left_Torso':2,'Aft_Side':3,'Nose':0,'Front_Side':2};loc=sections[r['section']]
                for slot in u['sections'][loc]['slots']:slot.update(type=403,data=7,firemode=7,ammomode=3,brand=7)
                action=E('resetcrits');expected={} if r['layout']=='empty' else {int(n):394+parts.index(p) for n,p in [v.split(':') for v in r['layout'].split(',')]}
            elif outline==2:action=D('section_index','' if r['text']=='empty' else r['text'].replace('_',' '));expected=int(r['location'])
            elif outline==3:action=D('short_section',int(r['location']));expected=r['label']
            else:action=E('resetcrits');expected=int(r['messages'])
            kw={'editors':[{'name':'e','id':1,'target':'u','allocated':r['state']=='allocated'}]} if outline==4 else {}
            d=a.run(f'sections/{outline}-{line}',document([action,R()],units=[u],**kw));res,out=d['results']
            if outline==1:
                actual={s['slot']:s['source_part_id'] for s in out['slots'][loc] if s['source_part_id']};a.eq('default types',actual,expected);a.eq('default zeroed data and modes',[[s[k] for k in ('data','fire','ammo')] for s in out['slots'][loc]],[[0,0,0]]*12);a.eq('unrelated brand retained',[s['brand'] for s in out['slots'][loc]],[7]*12)
            elif outline in (2,3):a.eq('source names',res,expected)
            else:a.eq('allocation guard messages',len(res['messages']) if r['state']=='null' else len(res['messages'])-1,expected)
    for outline in range(1,8):
        for line,r in examples('editor',outline):
            u=blank();kw={};actions=[]
            if outline==1:
                target={'valid':'u','unset':-1,'missing':999}[r['target']];kw={'editors':[{'name':'e','id':1,'allocated':r['allocated']=='1','target':target}]};action=E('resetcrits',privilege=r['privilege']=='1')
            elif outline in (2,3):u['movement']='TRACK';action=E('settype' if outline==2 else 'setmove',r['text'])
            elif outline==4:action=E(r['operation'],r['arguments'])
            elif outline==5:u['specials']=32;action=E('setradio',r['value'])
            elif outline==6:u['sections'][4].update(armor=20,armor_orig=20,internal=16,internal_orig=16,rear=5,rear_orig=5);action=E(r['operation'],r['arguments'].replace('~',' '))
            else:u['construction']={'cargo_space':0,'car_max_ton':1};action=E('setcargospace',r['cargo']+' '+r['maximum'])
            d=a.run(f'editor/{outline}-{line}',document([action,R(),I()],units=[u],**kw));res,out,state=d['results'];s=state['units']['u']
            if outline==1:
                expected={'permission-denied':["I'm sorry Dave, can't do that."],'set-target-first':['You must set a target first!'],'defaults-set':['Default criticals set!'],'three-data-errors':['There is a problem with that item.','The data is not properly allocated.','Please notify a director of this.']}[r['outcome']];a.eq('ordered guard messages',res['messages'],expected)
            elif outline==2:a.eq('class/movement',[out['type'],out['move']],[names.index(r['unit']),moves.index(r['move'])])
            elif outline==3:a.eq('movement fallthrough',out['move'],moves.index(r['move']));a.eq('movement notifications',len(res['messages']),int(r['messages']))
            elif outline==4:
                key={'setspeed':'max_speed','setjumpspeed':'jump_speed','settons':'tonnage','setheatsinks':'real_num_sinks','setlrsrange':'lrs_range','settacrange':'tac_range','setscanrange':'scan_range','setradiorange':'radio_range'}[r['operation']];a.eq('source scalar conversion',out[key],float(r['stored']))
            elif outline==5:a.eq('radio clamp and generic defaults',[out[k] for k in ('radio','radio_type','radio_range')],[int(r[k]) for k in ('level','type','range')])
            elif outline==6:a.eq('ordered armor writes',[s['sections'][4][k] for k in ('armor','internal','rear','armor_orig','internal_orig','rear_orig')],[int(r[k]) for k in ('a','i','r','oa','oi','orr')])
            else:a.eq('cargo result',[res['ok'],out['cargo_space'],out['car_max_ton']],[r['accepted']=='1',int(r['stored']),int(r['maxton'])])
    def mask(value,names):
        aliases={'LBX':'LBX/Cluster','AP':'AP','Jettison':'BackPack','MML_LRM':'MML_LRM'}
        return sum(1<<names.index(aliases.get(p,p)) for p in value.split('+') if p!='none') if value!='MML_LRM' else 1<<22
    for outline in (1,2,3):
        for line,r in examples('equipment',outline):
            u=blank();u['sections'][2].update(internal=12,internal_orig=12)
            if outline==1:
                for slot in u['sections'][2]['slots']:slot['data']=7
                action=E('addweap',r['arguments'].replace('~',' '))
            elif outline==2:
                u['sections'][2]['slots'][0].update(type=212,data=2,firemode=mask(r['fire'],fm),ammomode=mask(r['ammo'],am));action=E(r['operation'],'IS.AC/5 LT 1 '+r['flag'] if r['operation']=='reload' else 'LT 1')
            else:
                for slot in u['sections'][2]['slots'][:4]:slot.update(type=20,firemode=mask(r['fire'],fm),ammomode=8192)
                action=E('firemode','0 '+r['flag'])
            d=a.run(f'equipment/{outline}-{line}',document([action,R()],units=[u]));res,out=d['results'];slots=out['slots'][2]
            if outline==1:
                wanted=[] if r['slots']=='empty' else list(map(int,r['slots'].split(',')));a.eq('defined sequential placement',[s['slot'] for s in slots if s['source_part_id']],wanted);a.eq('data retained',[s['data'] for s in slots],[7]*12)
                if wanted:a.eq('placement flags',slots[wanted[0]-1]['fire'],304 if r['outcome']=='added-rear-TC-OS' else 0)
            else:
                a.eq('mode transition',[slots[0]['fire'],slots[0]['ammo']],[mask(r['out_fire'],fm),mask(r['out_ammo'],am)])
                if outline==2:a.eq('FullAmmo rounds',slots[0]['data'],int(r['rounds']))
    # Each switch character independently, on a fresh unit; expected macro masks
    # from mech.h and the two actual mechrep switches.
    chars={'#':1<<22,'W':128,'1':256,'I':64,'L':1,'A':2,'N':4,'C':8,'M':16,'S':32,'X':512,'Y':1024,'E':2048,'R':8192,'F':16384,'D':32768,'P':65536,'T':131072,'U':262144,'G':524288,'H':2097152,'V':1048576}
    for operation in ('reload','firemode'):
        for flag in [*chars,'-','+','Z','J']:
            u=blank();u['sections'][2].update(internal=12,internal_orig=12)
            if operation=='firemode':
                for slot in u['sections'][2]['slots'][:4]:slot.update(type=20)
            actions=[E(operation,'0 '+flag if operation=='firemode' else 'IS.AC/5 LT 1 '+flag),R()]
            d=a.run(f'equipment/flags-{operation}-{ord(flag)}',document(actions,units=[u]));slot=d['results'][1]['slots'][2][0]
            wantfire=128 if flag=='+' and operation=='reload' else 131072 if flag=='J' and operation=='firemode' else 0
            wantammo=chars.get(flag,4096 if flag=='Z' and operation=='reload' else 0)
            a.eq('source switch masks',[slot['fire'],slot['ammo']],[wantfire,wantammo])
