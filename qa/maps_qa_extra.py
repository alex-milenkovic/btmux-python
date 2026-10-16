"""Additional source guard/boundary procedures beyond the feature tables."""
import itertools
from maps_environment_qa import case,check,D,M,F,I,A,V,C
from maps_qa_files import attempt
from maps_qa_storage import dynamic

def X(kind,**options):return dict(op='diagnose',kind=kind,options=options)
def build():
    for kind,args,expected in [('sizes',[],{'map':0,'mechs':0,'objects':0,'profile':'LP64'}),('linked',[],False),('cf',[],-1),('start_regen',[],None),('regen',[],None),('rebuild',[],None),('set_cf',[1,100],None),('melt_snow',[0,0,10,{}],None),('eliminate_empties',[],None),('bits',['query',99,99,1],0)]:
        case('boundaries','null-'+kind,[D(kind,*args,null_map=True)],[check('results.0',expected)])
    case('conditions','null-update-clears-status',[D('conditions',null_map=True)],[check('state.units.u.status',0,mask=0x78000000)],map={'flags':6,'grav':99,'temp':-40},units=[{'name':'u'}])
    for cls in ('MECH','MW','BSUIT','VEH_GROUND','VEH_NAVAL','AERO','VTOL'):
        mechlike=cls in ('MECH','MW','BSUIT')
        for disable in (False,True):
            slot=0 if cls=='MW' else 4
            case('conditions',f'parts-class-{cls}-{disable}',[X('destroy-parts',section=0,disable=disable,breach=True)],
                 [check(f'state.units.u.sections.0.slots.{slot}.firemode',2 if disable else 1,mask=3),check(f'state.units.u.sections.0.slots.{slot}.data',0 if mechlike else 17),check('state.units.u.destroyed',False)],
                 units=[{'name':'u','class':cls,'sections':[{'index':0,'internal':10,'slots':[{'index':slot,'ammo':'IS.AC/5','data':17}]}]}],random={'streams':{}})
    for disabled in (False,True):
        case('conditions',f'already-disabled-ammo-{disabled}',[X('destroy-parts',section=0)],
             [check('state.units.u.sections.0.slots.4.firemode',1,mask=1),check('state.units.u.sections.0.slots.4.data',17 if disabled else 0)],
             units=[{'name':'u','sections':[{'index':0,'slots':[{'index':4,'ammo':'IS.AC/5','data':17,'firemode':2 if disabled else 0}]}]}])
    for cls in ('MECH','MW','BSUIT','VEH_GROUND'):
        dies=cls in ('MECH','MW')
        case('conditions','head-class-'+cls,[X('destroy-parts',section=7,disable=True,breach=True)],
             [check('state.units.u.destroyed',dies),check('state.units.u.external_effects',int(dies),where={'service':'tele_contents / persistent character health'},length=True)],
             map={'flags':6},units=[{'name':'u','class':cls,'in_character':True,'sections':[{'index':7,'internal':10}]}],mode='blocked' if dies else 'diagnostic')
    for location in (0,4):
        case('conditions',f'normalization-order-{location}',[X('destroy-parts',section=location)],
             [check('state.units.u.pilot_skill_base',9 if location==0 else 0)],units=[{'name':'u','core':{'pilot_skill_base':9},'sections':[{'index':0,'basetohit':7}]}])
    for config,internal in ((4,10),(2,0),(0,10)):
        case('conditions',f'repeated-breach-guard-{config}-{internal}',[C('damage-section','LA',1,0,0)],
             [check('state.units.u.sections.0.config',config| (4 if internal else 0),mask=6),check('draws',1,where={'name':'breach_rolls'},length=True)],
             map={'flags':6},units=[{'name':'u','sections':[{'index':0,'armor':100,'internal':internal,'config':config}]}],random={'streams':{'damage_entry':[7,7],'breach_rolls':[10]}})
    # All numeric and parser boundaries are observed after refusal, not inferred from exit alone.
    for arg in ('00 20','+0 20','-0 20','abc 20','100 00','100 +0','100 20 00','100 20 0 00','100 20 0 -1'):
        case('conditions','parser-'+arg.replace(' ','_'),[I(),attempt(M('conditions',arg)),I()],
             [check('results.1.error',contains='Invalid'),check('results.2.maps.main.flags',same_as='results.0.maps.main.flags'),check('results.2.maps.main.grav',same_as='results.0.maps.main.grav'),check('results.2.maps.main.temp',same_as='results.0.maps.main.temp')],map={'flags':16})
    case('conditions','nonzero-prefix-and-maxargs',[M('conditions','120tail -40tail 1yes 1yes ignored')],
         [check('state.maps.main.flags',22),check('state.maps.main.grav',120),check('state.maps.main.temp',-40)])
    for tick in (24,25,26,50):
        case('visibility',f'event-boundary-{tick}',[A(tick)],
             [check('state.maps.main.mapvis',10 if tick<25 else 4),check('state.maps.main.cloudbase',0 if tick<25 else 80)],
             map={'mapvis':10,'visibility':'4+0-120+40+80 abcdef'},config={'periodic_updates':True},units=[])
    case('visibility','no-heartbeat-no-refresh',[A(50)],[check('state.maps.main.mapvis',10)],map={'mapvis':10,'visibility':'4 0 120 40 80'},units=[])
    for n in range(6):
        text=' '.join(['4','0','120','40','80'][:n])
        case('visibility',f'scanf-{n}',[A(25)],[check('state.maps.main.mapvis',4 if n>=4 else 30),check('state.maps.main.cloudbase',80 if n>=5 else 200)],map={'visibility':text},config={'periodic_updates':True})
    # Melting uses removed quantity, not requested depth, for steam.
    for data,depth in itertools.product((0,1,90,91,1000,1001),(0,1,99,1001)):
        remaining=max(0,data-depth) if depth>0 else data
        layer='deep_snow' if data>1000 else 'snow'
        expected=([layer,'mud'] if depth<=0 else (['deep_snow' if remaining>1000 else 'snow','mud'] if remaining else ['mud']))
        case('snow',f'melt-boundary-{data}-{depth}',[D('melt_snow',0,0,depth,{'ice':False,'steam':False,'emit':True})],
             [check('state.maps.main.layers.0.data',remaining),check('state.maps.main.layers.0.layers',sorted(expected)),check('draws',[])],map={'size':[1,1],'layers':[{'at':[0,0],'layers':[layer,'mud'],'data':data}]})
    for amount in (1,90,91,101):
        draw=amount//20
        expected=amount if amount<=90 else 90+draw
        case('snow',f'actual-removed-steam-{amount}',[D('melt_snow',0,0,10000,{'ice':False,'steam':True})],
             [check('state.maps.main.layers.0.data',0),check('state.maps.main.objects.0.deadline',expected),check('draws',int(amount>90),length=True)],map={'size':[1,1],'layers':[{'at':[0,0],'layers':['snow'],'data':amount}]},random={'streams':{'snow_steam':[draw]}})
    for elev,depth in itertools.product((0,1,2),(1,199,200,399,400)):
        # ICE elevation is signed water depth; the source threshold is negative.
        case('snow',f'ice-signed-threshold-{elev}-{depth}',[D('melt_snow',0,0,depth,{'ice':True,'steam':True})],
             [check('state.maps.main.hexes.0.terrain','~'),check('state.maps.main.hexes.0.elevation',elev),check('state.maps.main.external_effects',[]),check('state.maps.main.objects',[])],
             map={'size':[1,1],'default':['ICE',elev]})
    case('snow','ice-predicate-reconstructed',[D('melt_snow',0,0,1,{})],[check('state.maps.main.hexes.0.terrain','~'),check('state.maps.main.external_effects',[])],map={'size':[1,1],'default':['ICE',1]})
    for layers in ([],['mud'],['snow','mud'],['deep_snow','mud'],['snow','deep_snow','mud']):
        for delta in (-3,0,3):
            changed=bool(delta and (delta>0 or set(layers)&{'snow','deep_snow'}))
            expected=sorted(['snow'] if delta>0 and not {'snow','deep_snow'}<=set(layers) else layers)
            if changed:expected=sorted((set(expected)-{'snow','deep_snow'})|{'snow'})
            label='-'.join(layers) or 'none'
            case('snow',f'growth-layer-guard-{label}-{delta}',[D('grow_snow',-1 if delta<0 else 0,3)],
                 [check('state.maps.main.layers.0.layers',expected),check('state.maps.main.layers.0.data',100+delta if changed else 100),check('draws',1,length=True),check('state.maps.main.external_effects',[])],
                 map={'size':[1,1],'layers':[{'at':[0,0],'layers':layers,'data':100}]},random={'streams':{'snow_growth':[abs(delta)]}},mode='diagnostic')
    case('snow','growth-x-major',[D('grow_snow',1,9)],
         [check('state.maps.main.snow_validation_trace',[1,2,3,4],project='data'),check('draws',[1,2,3,4],project='value')],
         map={'size':[2,2]},random={'streams':{'snow_growth':[1,2,3,4]}})
    # Roster corruption and ID-only consistency clearing retain directed data.
    for mapindex,slot in ((999,0),(-1,0),(0,0),(1000,99),(1000,1),(1000,0)):
        wire=dynamic([40,41],[3,4],[[1,2],[3,4]])
        case('dynamic',f'consistency-{mapindex}-{slot}',[F('load_dynamic',count=2),D('membership_state',{'mapindex':mapindex,'mapnumber':slot}),D('consistency')],
             [check('state.units.u.mapindex',1000 if mapindex==1000 and slot==0 else mapindex if mapindex<=0 else -1),check('state.maps.main.roster_ids',[-1,41] if mapindex==1000 and slot!=0 else [40,41]),check('state.maps.main.slot_flags',[3,4]),check('state.maps.main.slot_los',[[1,2],[3,4]])],
             units=[{'name':'u','id':40},{'name':'v','id':41}],files={'record':{'hex':wire.hex()}})
    for index in (1,99):
        wire=dynamic([40,41],[3,4],[[1,2],[3,4]])
        case('dynamic',f'remove-wrong-slot-{index}',[F('load_dynamic',count=2),D('membership_state',{'mapnumber':index}),D('membership_remove')],
             [check('state.maps.main.roster_ids',[-1,41]),check('state.units.u.mapindex',-1)],units=[{'name':'u','id':40},{'name':'v','id':41}],files={'record':{'hex':wire.hex()}})
