"""Independent weather, snow and spread diagnostics and real event consumers."""
import itertools
from maps_environment_qa import case,examples,check,D,M,A,I,V
from maps_qa_oracle import oracle

TN={'grass':'CLEAR','water':'WATER','ice':'ICE','fire':'FIRE','bridge':'BRIDGE','light-forest':'LIGHT_FOREST','heavy-forest':'HEAVY_FOREST','wall':'WALL','building':'BUILDING','smoke':'SMOKE','rough':'ROUGH'}
T={'grass':' ','water':'~','ice':'-','fire':'&','bridge':'/','light-forest':'`','heavy-forest':'"','wall':'=','building':'@','smoke':':','rough':'%'}
def raw(text):return {} if text=='none' else {k.replace('-','_'):int(v) for k,v in (s.split('=') for s in text.split(','))}
def fixture(temp=20,**kw):return {'size':[1,1],'temp':temp,**kw}
def unit(**kw):return [{'name':'u','at':[0,0,0],**kw}]
def effects(precip,temp,wind):
    result=set()
    if wind>60:result.add('high_winds')
    elif wind>=30:result.add('winds')
    if 'heavy_precip' in precip:
        if temp>0:result.add('heavy_rain')
        elif wind>60:result.discard('high_winds');result.add('blizzard')
        else:result.add('heavy_snow')
    elif 'precip' in precip:result.add('snow' if temp<=0 else 'rain')
    result.update(set(precip)&{'fog','sand'})
    return sorted(result)
def build():
    c=oracle()
    for i,r in enumerate(examples('weather',1)):
        symbols={'none':[],'ordinary':['precip'],'heavy':['heavy_precip'],'ordinary-and-heavy':['precip','heavy_precip']}[r['precip']]
        case('weather',f'example-01-{i}',[D('calc_weather',symbols,int(r['temp']),int(r['wind']))],
             [check('results.0',sorted([] if r['effects']=='none' else r['effects'].replace('-','_').split(',')))])
    for mask in range(16):
        symbols=[s for i,s in enumerate(('precip','heavy_precip','fog','sand')) if mask&(1<<i)]
        for temp,wind in itertools.product((0,1),(29,30,60,61)):
            valid=[v for v in symbols if not(v=='precip' and 'heavy_precip' in symbols)]
            case('weather',f'all-classification-{mask}-{temp}-{wind}',[D('validate_weather',symbols),D('calc_weather',symbols,temp,wind)],
                 [check('results.0',sorted(valid)),check('results.1',effects(symbols,temp,wind))])
    types={'TBEAM':0,'TMISSILE':1,'TAMMO':3,'STREAK':8}
    for i,r in enumerate(examples('weather',2)):
        case('weather',f'example-02-{i}',[D('gun_weather',raw(r['effects']),types[r['weapon']])],[check('results.0',int(r['modifier']))])
    keys=('rain','heavy_rain','blizzard','heavy_snow','fog','sand','high_winds','winds')
    for weapon,mask in itertools.product((0,1,3,8),range(256)):
        # Every raw predicate combination, including the source's bitwise high-wind test.
        values=[1 if mask&(1<<i) else 0 for i in range(8)]
        expected=c('gun',weapon,*values)
        case('weather',f'c-gun-{weapon}-{mask}',[D('gun_weather',dict(zip(keys,values)),weapon)],[check('results.0',expected)])
    for v in (0,1,2,3,4,128):
        case('weather',f'c-raw-high-wind-{v}',[D('gun_weather',{'high_winds':v},3)],[check('results.0',c('gun',3,0,0,0,0,0,0,v,0))])
    for i,r in enumerate(examples('weather',3)):
        record={'movement':'HOVER' if r['move']=='hover' else 'BIPED'}
        if r['position']=='jumping':record['status']=64
        if r['position']=='above-ground':record['at']=[0,0,1]
        actions=[D('membership_remove')] if r['position']=='no-map' else []
        actions.append(D('pilot_weather',{'heavy_rain':1}))
        case('weather',f'example-03-{i}',actions,[check(f'results.{len(actions)-1}',int(r['modifier']))],units=unit(**record),map=fixture(layers=[{'at':[0,0],'layers':['deep_snow','mud','rapids'],'data':1001}]))
    for i,r in enumerate(examples('weather',4)):
        values={} if r['effects']=='none' else {r['effects'].replace('-','_'):1}
        case('weather',f'example-04-{i}',[D('heat_weather',values)],[check('results.0',int(r['minus']))],units=unit(core={'minus_heat':10}),map=fixture(int(r['temp'])))
    for temp in (-128,-41,-40,-31,-30,50,51,60,61,127):
        for legs in (0,1):
            adjust=(-30-temp+9)//10 if temp< -30 else -(temp-50+9)//10 if temp>50 else 0
            # Parentheses here follow C truncating positive ceiling before subtraction.
            if temp>50:adjust=-((temp-50+9)//10)
            case('weather',f'heat-priorities-{temp}-{legs}',[D('heat_weather',{'heavy_rain':1,'rain':1,'blizzard':1,'heavy_snow':1},legs)],
                 [check('results.0',10-4+adjust-legs)],units=unit(core={'minus_heat':10}),map=fixture(temp,layers=[{'at':[0,0],'layers':['deep_snow'],'data':1500}]))
    for i,r in enumerate(examples('snow',1)):
        layer='deep_snow' if r['layer']=='deep' else 'snow';after=[] if r['result']=='none' else ['deep_snow' if r['result']=='deep' else 'snow']
        case('snow',f'example-01-{i}',[D('melt_snow',0,0,int(r['depth']),{'steam':False,'ice':False})],
             [check('state.maps.main.layers.0.data',int(r['after'])),check('state.maps.main.layers.0.layers',sorted(after+['mud']))],
             map=fixture(layers=[{'at':[0,0],'layers':[layer,'mud'],'data':int(r['data'])}]))
    for i,r in enumerate(examples('snow',2)):
        duration=None if r['duration']=='none' else int(r['duration'])
        actions=[D('melt_snow',0,0,int(r['depth']),{'steam':r['steam']=='true','ice':False}),I()]
        checks=[check('draws',1 if r['usage']=='used' else 0,length=True),check('results.1.maps.main.objects',int(duration is not None),length=True)]
        if duration is not None:
            checks += [check('results.1.maps.main.objects.0.deadline',duration)]
            actions += [A(duration-1),I(),A(1),I()]
            checks += [check('results.3.maps.main.hexes.0.terrain',':'),check('results.5.maps.main.hexes.0.terrain',' '),check('state.events',[])]
        case('snow',f'example-02-{i}',actions,checks,map=fixture(layers=[{'at':[0,0],'layers':['snow'],'data':500}]),random={'streams':{'snow_steam':[int(r['draw'])]}})
    for i,r in enumerate(examples('snow',3)):
        used=r['usage']=='used';blocked=False
        case('snow',f'example-03-{i}',[D('grow_snow',int(r['low']),int(r['high']))],
             [check('state.maps.main.layers.0.data',int(r['data'])),check('state.maps.main.layers.0.layers',sorted(r['layers'].replace('shallow','snow').replace('deep','deep_snow').split(','))),check('draws',int(used),length=True),check('state.maps.main.external_effects',int(blocked),length=True)],
             map=fixture(default=[TN[r['terrain']],0],layers=[{'at':[0,0],'layers':['snow','mud'],'data':100}]),random={'streams':{'snow_growth':[int(r['draw'])]}},mode='blocked' if blocked else 'diagnostic')
    # C coordinate oracle: four scalar bodies, each six headings and three offsets;
    # exercise actual rounded four-candidate producer in both parities and edges.
    def coords(x,y,wind,w=12,h=12):
        heading=int((wind+30)/60)*60
        heading-=int(heading/360)*360
        def one(x,y,i):
            dx,dy=c('coord',heading,i,int(x%2!=0));xx,yy=x+dx,y+dy
            return [xx,yy] if 0<=xx<w and 0<=yy<h else [-1,-1]
        first=[one(x,y,i) for i in range(3)]
        return first+[one(*first[0],0)]
    for i,r in enumerate(examples('spread',1)):
        expected=[list(map(int,p.split(','))) for p in r['coordinates'].split(';')]
        case('spread',f'example-01-{i}',[D('spread_coordinates',int(r['x']),4,int(r['wind']))],[check('results.0',expected)],map={'size':[12,12]})
    for x,y,wind in itertools.product((0,4,5,11),(0,4,11),(0,29,30,60,89,90,120,180,240,300,329,330,359)):
        case('spread',f'c-coordinates-{x}-{y}-{wind}',[D('spread_coordinates',x,y,wind)],[check('results.0',coords(x,y,wind))],map={'size':[12,12]})
    for x in (4,5):
        case('spread',f'c-undefined-heading-{x}',[D('spread_coordinates',x,4,-90)],[check('results.0',coords(x,4,-90))],map={'size':[12,12]})
    for i,r in enumerate(examples('spread',2)):
        index={9:0,11:1,12:3}[int(r['threshold'])];rolls=[2]*4;rolls[index]=int(r['roll']);wind=int(r['wind']);delay=max(20,60-wind)
        xy=coords(4,4,0)[index]
        case('spread',f'example-02-{i}',[M('addfire',4,4,120),A(delay)],
             [check('draws',1 if r['consumed']=='used' else 0,where={'name':'fire_wind'},length=True),
              check('state.maps.main.objects',int(r['eligible']=='true'),where={'kind':'FIRE','x':xy[0],'y':xy[1]},length=True)],
             map={'size':[12,12],'windspeed':wind,'hexes':[{'at':xy,'terrain':'LIGHT_FOREST','elevation':0}]},random={'streams':{'fire_spread':rolls,'fire_wind':[int(r['number'])],'smoke_duration':[90]*4,'fire_duration':[120]}})
    for i,r in enumerate(examples('spread',3)):
        setup=[M('addfire',4,4,120)]
        if r['decoration']=='smoke':setup.append(M('addsmoke',4,3,90))
        setup.append(A(30))
        expected={'fire':'&','smoke':':','none':T[r['underlying']]}[r['overlay']]
        case('spread',f'example-03-{i}',setup,[check('state.maps.main.hexes', [expected],where={'at':[4,3]},project='terrain')],
             map={'size':[12,12],'windspeed':30,'hexes':[{'at':[4,3],'terrain':TN[r['underlying']],'elevation':0}]},
             random={'streams':{'fire_spread':[9,2,2,2],'fire_wind':[30],'smoke_duration':[90]*4,'fire_duration':[120]}})
