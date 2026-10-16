"""Ordinary loaded-unit consumers, with source-derived weather/resource expectations."""
from qa.construction_qa_common import *
def M(name,args='',**kw):return dict(op='map_command',name=name,args=args,**kw)
def W(**kw):return M('weather.set',kw)
def F(kind,file='bits'):return dict(op='map_file',kind=kind,file=file)
def X(kind,*args):return dict(op='diagnose',kind=kind,args=list(args))

_document=document
def document(*args,**kwargs):
    doc=_document(*args,**kwargs)
    if 'streams' in doc['random']:doc['random']['streams'].update({'sensor.detect':[1]*1000,'breach_rolls':[12]*20})
    return doc

def run(a):
    units=[{'name':'u','at':[3,3,0]},{'name':'v','at':[3,1,0],'team':2,'facing':180},{'name':'p','at':[6,6,0],'fallen':True}]
    actions=[T('load','QA50'),E('setradio','4'),dict(op='construction_pilot',actor={'gunnery':4,'piloting':5}),C('startup'),A(40),C('lock','01'),A(1),C('sight','1 01'),W(conditions=['heavy_precipitation'],temperature=51,windspeed=61),C('sight','1 01'),C('fire','1 01'),C('stand','check',unit='p'),C('stand','',unit='p'),A(2),I(),X('ProperMyomer'),X('ProperInternal')]
    doc=document(actions,{'QA50':modern()},units=units,ordinary=True);doc['config']['complexrepair']=True;doc['random']['streams']['pilot_rolls']=[12]*10
    d=a.run('ordinary/10-weather-loaded',doc,'ordinary');r=d['results'];base=r[7]['attack']['bth_breakdown'];wet=r[9]['attack']['bth_breakdown'];shot=r[10]['attack']
    a.eq('weather sight/fire same calculation',shot['bth_breakdown'],wet);a.eq('weather applied once',wet['total']-base['total'],2);a.eq('weather term',wet['weather_mod'],2);a.eq('shot damage',shot['damage_dealt'],5)
    a.eq('weather stand BTH',r[11]['message'],'Your BTH to stand would be: 6');a.eq('stand accepted',r[12]['accepted'],True);a.eq('temperature and rain heat once',r[14]['units']['u']['minus_heat'],7);a.eq('Core numeric aliases',r[-2:],[683,703])
    # Ordinary right-edge BUILD producer, persistence, and movement consumer.
    maps=[{'name':'main','id':10,'size':[9,9]},{'name':'Depot','id':20,'size':[9,9],'cf':100,'cfmax':100}]
    attrs={'10':{'BUILDLINKS':'20'},'20':{'BUILDCOORD':'8,2','BUILDENTRANCE':'0 0 0 0'}}
    doc=document([T('load','QA50'),M('updatelinks'),F('save_objects')],{'QA50':modern()},units=[{'name':'u','at':[8,3,0]}],ordinary=True,maps=maps,attributes=attrs);doc.pop('map')
    d=a.run('ordinary/10-right-edge-save',doc,'ordinary');raw=(OUT/'ordinary/10-right-edge-save/maps/bits').read_bytes();a.eq('real object bytes',len(raw)>10,True)
    doc=document([T('load','QA50'),F('load_objects'),dict(op='construction_pilot'),C('startup'),A(40),C('speed','32'),A(30),I()],units=[{'name':'u','at':[8,3,0]}],ordinary=True,maps=maps,attributes=attrs);doc.pop('map');doc['files']={'bits':{'hex':raw.hex()}}
    d=a.run('ordinary/10-right-edge-fresh',doc,'ordinary',root=OUT/'ordinary/10-right-edge-save/templates');a.eq('right-edge movement sees building',any('Depot has CF of 100' in m for m in d['state']['units']['u']['messages']),True)
    # A missed Streak command must not reach AMS or consume either ammunition pool.
    for throw in (2,12):
        content=modern(weapon='CL.StreakSRM-2',ammo=50).replace('CRIT_1-4 { CL.StreakSRM-2','CRIT_1 { CL.StreakSRM-2')
        target={'name':'v','at':[3,1,0],'team':2,'facing':180,'status':8|2048,'specials':4,'weapons':[{'name':'IS.Anti-MissileSystem','section':0,'critical':4}],'ammo':[{'weapon':'IS.Anti-MissileSystem','rounds':20,'section':1,'critical':4}]}
        doc=document([T('load','STREAK'),dict(op='construction_pilot',actor={'gunnery':8,'piloting':5}),C('startup'),A(40),C('lock','01'),A(1),I(),C('fire','1 01'),I()],{'STREAK':content},units=[units[0],target],ordinary=True)
        doc['random']['streams'].update(attack_rolls=[throw],ams_rolls=[2]);d=a.run('ordinary/10-Streak-'+str(throw),doc,'ordinary');r=d['results'];before,after=r[6]['units'],r[8]['units'];hit=throw==12
        a.eq('Streak hit gate',r[7]['attack']['hit'],hit);a.eq('Streak ammo gate',after['u']['sections'][3]['slots'][0]['data'],50-int(hit));a.eq('AMS draw gate',[x['value'] for x in d['draws'] if x['name']=='ams_rolls'],[2] if hit else [])
        a.eq('AMS ammunition gate',after['v']['sections'][1]['slots'][4]['data'],before['v']['sections'][1]['slots'][4]['data']-(2 if hit else 0))
    # Source building-specific SRM rack2 row consumes a real template-loaded shot.
    maps[0]['map_objects']=[{'kind':'BUILDING','x':3,'y':1,'obj':20}]
    content=modern(weapon='IS.SRM-2',ammo=50).replace('CRIT_1-4 { IS.SRM-2','CRIT_1 { IS.SRM-2')
    doc=document([T('load','SRM'),dict(op='construction_pilot'),C('startup'),A(40),C('lock','3 1 B'),A(1),C('fire','1'),I()],{'SRM':content},units=[units[0]],ordinary=True,maps=maps);doc.pop('map')
    d=a.run('ordinary/10-building-missile',doc,'ordinary');a.eq('building shot accepted',d['results'][-2]['accepted'],True);a.eq('building rack two full row',d['state']['maps']['Depot']['cf'],96)
