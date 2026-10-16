"""Independent source CF lifecycle, Streak flag correction and queries."""
import re
from maps_environment_qa import ROOT, case,examples,check,D,M,F,I,A,V,C

def maps(cf=100,maximum=100,factor=1,flags=0,exterior=0):
    return [{'name':'main','id':10,'size':[9,9],'buildflag':exterior,'hexes':[{'at':[2,2],'terrain':'BUILDING','elevation':0}],
             'map_objects':[{'kind':'BUILDING','x':2,'y':2,'obj':20}]},
            {'name':'Depot','id':20,'size':[9,9],'cf':cf,'cfmax':maximum,'regen_factor':factor,'buildflag':flags}]
def units(**kw):return [{'name':'u','id':40,'at':[2,3,0],**kw}]
def build():
    for i,r in enumerate(examples('buildings',1)):
        deadline=[] if r['deadline']=='none' else [int(r['deadline'])]
        case('buildings',f'example-01-{i}',[D('hit_building',2,2,-999,int(r['damage']))],
             [check('state.maps.Depot.cf',int(r['remaining'])),check('state.events',deadline,where={'kind':'BREGEN'},project='deadline')],maps=maps(int(r['cf'])),units=units())
    for i,r in enumerate(examples('buildings',2)):
        case('buildings',f'example-02-{i}',[D('schedule_regen',120,map='Depot'),A(120)],
             [check('state.maps.Depot.cf',int(r['after'])),check('state.events',[] if r['deadline']=='none' else [int(r['deadline'])],where={'kind':'BREGEN'},project='deadline')],maps=maps(int(r['cf']),factor=int(r['factor'])))
    for i,r in enumerate(examples('buildings',3)):
        case('buildings',f'example-03-{i}',[D('rebuild',map='Depot')],[check('state.maps.Depot.cf',int(r['after'])),check('state.events',[])],maps=maps(int(r['cf']),int(r['maximum'])))
    for i,r in enumerate(examples('buildings',4)):
        def scratch(data,path,r=r):assert ('Your shot only scratches the paint!' in data['state']['units']['u']['messages'])==(r['scratch']=='present')
        case('buildings',f'example-04-{i}',[D('hit_building',2,2,-999,10)],[check('state.maps.Depot.cf',int(r['cf']))],checker=scratch,
             maps=maps(flags=int(r['interior']),exterior=int(r['exterior'])),units=units())
    for i,r in enumerate(examples('buildings',5)):
        case('buildings',f'example-05-{i}',[D('bits','set',2,2,2),D('step_building' if r['query']=='step' else 'scan_building',2,2)],
             [check('results.1',75 if r['visible']=='shown' else None)],maps=maps(75,flags=int(r['flags'])),units=units(in_character=True,pilot_details={'perception':2}),random={'streams':{'perception_rolls':[12]}})
    for streak in (False,True):
        name='IS.StreakSRM-6' if streak else 'IS.SRM-6'
        for angel in (False,True):
            for throw in (2,7,12):
                count=6 if streak and not angel else {2:2,7:4,12:6}[throw]
                draws=0 if streak and not angel else 2
                case('buildings',f'authorized-streak-{streak}-{angel}-{throw}',[D('building_missile_count',name),D('hit_building_weapon',2,2,name),I(),D('hit_building',2,2,-999,7)],
                     [check('results.0',count),check('results.1',2*count),check('results.2.maps.Depot.cf',100-2*count),check('state.maps.Depot.cf',93-2*count),check('draws',draws,where={'name':'building_cluster'},length=True)],
                     maps=maps(),units=units(status2=2048 if angel else 0),random={'streams':{'building_cluster':[throw,throw]}})
    for cf,maximum in ((0,0),(0,100),(10,0),(10,100)):
        case('buildings',f'cf-getter-{cf}-{maximum}',[D('cf',map='Depot')],[check('results.0',-1 if cf==0 and maximum<=0 else cf)],maps=maps(cf,maximum))
    case('buildings','negative-factor-zero-last-callback',[D('start_regen',map='Depot'),A(120),I(),A(120)],
         [check('results.2.maps.Depot.cf',0),check('results.2.events',[240],project='deadline'),check('state.maps.Depot.cf',0),check('state.events',[])],maps=maps(1,factor=-1))
    case('buildings','repeated-starters',[D('start_regen',map='Depot'),D('start_regen',map='Depot'),A(120)],
         [check('state.maps.Depot.cf',92),check('state.events',[240,240],project='deadline')],maps=maps(90))
    case('buildings','pending-regen-stops-after-destruction',[D('start_regen',map='Depot'),D('hit_building',2,2,-999,100),A(120)],
         [check('state.maps.Depot.cf',0),check('state.events',[],where={'kind':'BREGEN'})],maps=maps(90),units=units())
    for cf in (0,90,100):
        case('buildings',f'BUILD-load-starts-{cf}',[F('save_objects'),F('load_objects')],
             [check('state.events',[120] if cf==90 else [],project='deadline')],maps=maps(cf))
    for weapon,damage in (('IS.MediumLaser',5),('IS.PPC',10),('IS.NarcBeacon',4)):
        case('buildings','computed-'+weapon,[D('hit_building_weapon',2,2,weapon)],[check('results.0',damage),check('state.maps.Depot.cf',100-damage)],maps=maps(),units=units(),random={'streams':{'building_cluster':[7]}})
    for flag in (0,4,16):
        for ic in (False,True):
            for throw in (2,12):
                success=not(flag&16) and (not(flag&4) or (ic and throw==12))
                case('buildings',f'scan-guard-{flag}-{ic}-{throw}',[D('scan_building',2,2)],[check('results.0',100 if success else None),check('draws',int(flag==4 and ic),length=True)],
                     maps=maps(flags=flag),units=units(in_character=ic,pilot_details={'perception':6}),random={'streams':{'perception_rolls':[throw]}})

    source=(ROOT/'btmux/btmux/btech/src/btech/weapons.h').read_text().split('struct missile_hit_table_struct MissileHitTable[] = {',1)[1]
    rows={name:list(map(int,values.split(','))) for name,values in re.findall(r'\{"([^"\n]+)",\s*0,\s*\{([0-9, ]+)\}\}',source)}
    declarations=re.sub(r'/\*.*?\*/','',(ROOT/'btmux/btmux/btech/src/btech/weapons.h').read_text().split('struct missile_hit_table_struct')[0],flags=re.S)
    missile_names=re.findall(r'\{"([^"]+)",\s*\w+,\s*TMISSILE',declarations)
    available=set(re.findall(r'name="([^"]+)"',(ROOT/'entities/weapon.py').read_text()))
    for name in sorted(set(missile_names)&set(rows)&available):
        for throw in range(2,13):
            case('buildings',f'c-missile-{name}-{throw}',[D('building_missile_count',name)],[check('results.0',rows[name][throw-2])],maps=maps(),units=units(status2=2048),random={'streams':{'building_cluster':[throw]}})
    for name,throw,damage in (('IS.LRM-10',3,4),('IS.LRM-15',4,9),('CL.ATM-9',10,14)):
        case('buildings','ordinary-source-cluster-'+name,[C('lock',2,2,'B'),C('fire',0),I()],
             [check('results.1.accepted',True),check('state.maps.Depot.cf',100-damage),check('draws',0,where={'name':'building_cluster'},length=True)],
             maps=maps(),units=[{'name':'u','at':[2,5,0],'weapons':[name],'ammo':[{'weapon':name,'rounds':10}]}],
             random={'streams':{'attack_rolls':[12],'failure_weapon_chance':[4],'building_cluster':[throw],'missile_pre_roll':[3,3,3],'missile_cluster':[throw]}},mode='ordinary')
