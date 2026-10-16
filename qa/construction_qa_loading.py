"""Independent load/helper/mode boundaries, including the QA Clan case regression."""
from qa.construction_qa_common import *
from qa.construction_qa_numeric import CLASSES,MOVES,blank,table

def run(a):
    for outline in range(1,5):
        for line,r in examples('helpers',outline):
            if outline==1:
                value='' if r['text']=='empty' else r['text'].replace('/BAR/','|').replace('~',' ')
                d=a.run(f'helpers/{outline}-{line}',document([D('parse_bits',r['parser'],['Alpha','Beta','Gamma'],value)]));a.eq('strict/lenient C tokens',d['results'][0],int(r['value']))
            elif outline==2:
                d=a.run(f'helpers/{outline}-{line}',document([D('read_desc',r['text'].replace('~',' '))]));a.eq('C description bytes',d['results'][0],'' if r['value']=='empty' else r['value'])
            elif outline==3:
                u={'name':'u','scan_range':int(r['scan']),'tac_range':9,'lrs_range':9,'radio_range':9,'construction':{'computer':0,'radio':3}}
                d=a.run(f'helpers/{outline}-{line}',document([D('computer_conversion')],units=[u]));a.eq('source computer conversion',[d['results'][0][k] for k in ('computer','scan_range','tac_range','lrs_range','radio_range')],[int(r[k]) for k in ('computer','out_scan','tac','lrs','radio')])
            else:
                d=a.run(f'helpers/{outline}-{line}',document([T('load','FUEL'),R()],{'FUEL':field('Type',r['unit'])}));a.eq('type default fuel',d['state']['units']['u']['fuel'],int(r['fuel']))
    for outline in (1,2):
        for line,r in examples('modes',outline):
            value=r['text'].replace('/BAR/','|')
            if outline==2:
                d=a.run(f'modes/{outline}-{line}',document([D('parse_bits','delimited',r['table'],value)]));a.eq('strict helper preserved',d['results'][0],int(r['result']));continue
            item='IS.AC/5' if r['kind']=='weapon' else 'Ammo_IS.AC/5'
            quantity='-' if r['kind']=='weapon' else ('10' if r['fire']=='128' or r['ammo']=='65536' else '20')
            content='Left_Torso\n'+field('CRIT_1',f'{item} {quantity} {value} 4')
            u={'name':'u','sections':[{'index':2,'slots':[{'index':0,'firemode':128,'ammomode':8192,'brand':7,'data':7}]}]}
            d=a.run(f'modes/{outline}-{line}',document([D('load_fields','MODE'),R()],{'MODE':content},units=[u]));res,out=d['results'];s=out['slots'][2][0]
            a.eq('load outcome',res['ok'],r['outcome']=='success');a.eq('fire/ammo masks',[s['fire'],s['ammo']],[128,8192] if r['outcome']=='error' else [int(r['fire']),int(r['ammo'])])
            if r['outcome']=='error':
                a.eq('earlier type write',s['source_part_id'],96 if r['kind']=='weapon' else 288);a.eq('earlier brand write before failed masks',s['brand'],0)
    for name in ('CL.ERLargeLaser','cl.erlargelaser','cL.ERLARGELASER'):
        d=a.run('loading/clan-case-'+str(len(a.rows)),document([T('load','CLAN'),R()],{'CLAN':'Type { Vehicle }\nTons { 50 }\nFront_Side\nInternals { 5 }\n'+field('CRIT_1',f'{name} - - -')}))
        r=d['results'][1];a.eq('C case-insensitive Clan defaults',[r[k] for k in ('computer','radio','radio_type','scan_range','radio_range')],[5,5,27,35,140]);a.eq('Clan default brand',r['slots'][2][0]['brand'],5)
    for outline in range(1,7):
        for line,r in examples('loading',outline):
            content='';actions=None;u={'name':'u'}
            if outline==1:
                ref=r['filename'];content=''.join(field(k,'' if r[v]=='empty' else r[v]) for k,v in [('Reference','reference'),('Unit_Era','era'),('Unit_TRO','tro')]);actions=[T('load',ref),R()]
                want=[r['stored'],r['out_era'],r['out_tro']]
            elif outline==2:
                ref='F';content=''.join(field(*p.split(':')) for p in r['sequence'].split(','));actions=[T('load',ref),R()];want=int(r['fuel'])
            elif outline==3:
                ref='E';content=''.join(field(k,v) for k,v in [('Type','Vehicle'),('Specials','Clan' if r['clan_flag']=='1' else '-'),('Computer',r['computer']),('Radio',r['radio']),('Scan_Range',r['scan'])])+'Front_Side\n'+field('CRIT_1',r['item']+' - - -');actions=[T('load',ref),R()]
            elif outline==4:
                ref='A';sec='Suit_1' if r['unit']=='Battlesuit' else 'Left_Arm';content=field('Type',r['unit'])+sec+'\n'+field('CRIT_1',f"Ammo_IS.AC/5 {r['quantity']} {r['mode']} -");actions=[T('load',ref),R()]
            elif outline==5:
                ref='INVALID';u={'name':'u','construction':{'zeroed':True}};content=field(r['field'],r['value'].replace('~',' '));actions=[D('load_fields',ref),R()]
            else:
                ref='RANGE';content='Left_Torso\n'+field(r['range'],'HeatSink 7 - 3');actions=[D('load_fields',ref),R()]
            d=a.run(f'loading/{outline}-{line}',document(actions,{ref:content},units=[u]));res,out=d['results'];state=d['state']['units']['u']
            if outline==1:a.eq('normalization',[out[k] for k in ('template_ref','unit_era','unit_tro')],want)
            elif outline==2:a.eq('ordered fuel',[state['fuel'],out['fuel_orig']],[want,want])
            elif outline==3:a.eq('electronics',[out[k] for k in ('computer','radio','scan_range','tac_range','lrs_range','radio_range','radio_type')],[int(r[k]) for k in ('c','r','s','t','l','rr','rt')])
            elif outline==4:a.eq('capacity/halfton',[out['slots'][0][0]['data'],bool(out['slots'][0][0]['fire']&128)],[int(r['rounds']),r['half']=='1'])
            elif outline==5:
                outcome=r['outcome'];a.eq('defined outcome',res['ok'],outcome not in ('error','safe-bounds-error'))
                if outcome=='both-flags-set':a.eq('union tech',[state['specials'],state['specials2']],[32,4096])
                elif r['field']=='Tons':a.eq('atoi',out['tonnage'],int(outcome))
                elif outcome=='unchanged-no-error':a.eq('unchanged flags',[state['specials'],state['specials2']],[0,0])
                elif outcome=='zero':a.eq('config removes flags',state['sections'][0]['config'],0)
            else:
                expected=list(map(int,r['slots'].split(',')));a.eq('copied range',[s['slot'] for s in out['slots'][2] if s['source_part_id']==403],expected)
                a.eq('copied data/brand',[[out['slots'][2][p-1][k] for k in ('data','brand')] for p in expected],[[7,3]]*len(expected))

    # Every modern load_cmds member, immediate writes before post-load normalization.
    fieldspec={
      'Reference':('different','template_ref','FIELDS'),'Type':('AeroFighter','type',5),'Move_Type':('Foil','move',6),'Tons':('55suffix','tonnage',55),
      'Tac_Range':('17','tac_range',17),'LRS_Range':('37','lrs_range',37),'Radio_Range':('73','radio_range',73),'Scan_Range':('19','scan_range',19),
      'Heat_Sinks':('13','real_num_sinks',13),'Max_Speed':('64.5','max_speed',64.5),'Specials':('Clan AngelECM_Tech',None,None),
      'Armor':('21',None,None),'Internals':('9',None,None),'Rear':('7',None,None),'Config':('unknown',None,None),
      'Computer':('4','computer',4),'Name':('Independent Name','name','Independent Name'),'Jump_Speed':('21.5','jump_speed',21.5),
      'Radio':('4','radio',4),'SI':('23','si',23),'Fuel':('700','fuel_orig',700),'Comment':('independent comment','name',''),
      'RadioType':('21','radio_type',21),'Mech_BV':('2345','mech_bv',2345),'Cargo_Space':('1000','cargo_space',1000),'Max_Suits':('4','max_suits',4),
      'InfantrySpecials':('Swarm_Attack_Tech','infantry_specials',1),'Max_Ton':('75','car_max_ton',75),'HSEngOverRide':('5','hs_engine_override',5),
      'Unit_Era':('3067','unit_era','3067'),'Unit_TRO':('TRO3067','unit_tro','TRO3067')}
    assert set(fieldspec)==set(table('load_cmds'))
    for fieldname,(value,key,want) in fieldspec.items():
        d=a.run('loading/all-fields-'+fieldname,document([D('load_fields','FIELDS'),R(),I()],{'FIELDS':field(fieldname,value)},units=[{'name':'u','construction':{'zeroed':True}}]));res,out,state=d['results'];a.eq('known field applied',res['ok'],True)
        if key:a.eq('immediate field write',out[key],want)
        elif fieldname=='Specials':a.eq('two-table union',[state['units']['u']['specials'],state['units']['u']['specials2']],[32,4096])
        else:
            actual=state['units']['u']['sections'][0];name={'Armor':'armor','Internals':'internal','Rear':'rear','Config':'config'}[fieldname]
            a.eq('initial section field',actual[name],-4 if fieldname=='Config' else int(value))
            if fieldname!='Config':a.eq('original mirror',actual[name+'_orig'],int(value))
