"""Public map requests, source bounds and explicit component-visibility fixtures."""
from hud_displays_common import *


def hud_maps():
    for name,n,row,meta in examples('hud_tactical'):
        doc=document(actions=[hud('key=test')]);u=doc['units'][0];u['at']=[50,50,0];u['lrs_range']=30;case=Case(name,doc,meta)
        if n==1:
            doc['actions'].append(hud('t '+row['height']));bounds=row['bounds'].split(',')
            case.expect('results.1.records',int(row['rows'])+2,'length')
            for i,value in enumerate(bounds):case.expect(f'results.1.records.0.payload|{i}',value)
            sy=int(bounds[1])
            for i in range(int(row['rows'])):
                case.expect(f'results.1.records.{i+1}.payload',str(sy+i)+','+'.0'*70)
        elif n==2:
            doc['actions'].append(hud(row['request']))
            if row['outcome']=='map-list':case.expect('results.1.ok',True).expect('results.1.records.0.type','S')
            else:record(case,1,'T','E',row['outcome'])
        elif n==3:
            flags={'both':7,'terrain-only':3,'elevation-only':5,'neither':1}[row['visibility']]
            doc['map']['hexes']=[dict(at=[50,49],terrain='GRASSLAND',elevation=3)]
            u['display']=dict(display_los_cells=[dict(x=50,y=49,flags=flags)])
            doc['actions'].append(hud('t 2 0 0 l'))
            case.expect('results.1.records.1.payload|1',r'^.{70}'+re.escape(row['pair'])+'.{68}$','regex').expect('results.1.diagnostic_los',True)
        else:
            doc['hud_display']=dict(hudinfo_show_mapinfo=int(row['config']),map_in_character=row['ic']=='true')
            doc['map']['name']='QA map';doc['actions'].append(hud('t 2'))
            for i,value in [(4,'1000' if row['identity']=='actual' else '-1'),(5,'QA map' if row['identity']=='actual' else '-1'),(7,'100'),(8,'100')]:case.expect(f'results.1.records.0.payload|{i}',value)
        if n!=2 or row['outcome']=='map-list':case.expect('results.1.records.-1.type','D')
        yield case


def lrs():
    for name,n,row,meta in examples('lrs_navigation'):
        doc=document();u=doc['units'][0];u['at']=[50,50,0];u['lrs_range']=30;case=Case(name,doc,meta)
        if n==1:
            form={'biped':'biped','quad':'quad','fly':'AERO','track':'VEHICLE-TRACK','wheel':'VEHICLE-WHEEL','hover':'VEHICLE-HOVER','VTOL':'VTOL','hull':'NAVAL-HULL','sub':'NAVAL-SUB','foil':'NAVAL-FOIL'}[row['movement']]
            doc['units'].append(dict(name='target',id=20,contact_id='TT',at=[50,49,0],team=0 if row['friend']=='true' else 2,**formed(form)))
            doc['diagnostic_cache']=[dict(viewer='u',target='target',flags=6)]
            doc['actions']=[command('lrs','m')]
            case.expect('results.0.cells',dict(x=50,y=49,glyph=row['glyph']),'has_fields')
        elif n==2:
            doc['map']['hexes']=[dict(at=[50,49],terrain='GRASSLAND',elevation=int(row['elevation']))];doc['actions']=[command('lrs',row['mode'])]
            case.expect('results.0.cells',dict(x=50,y=49,glyph=' ' if row['glyph']=='space' else row['glyph']),'has_fields')
        elif n==3:
            doc['map']['hexes']=[dict(at=[50,49],terrain='LIGHT_FOREST',elevation=7)]
            u['display']=dict(display_los_cells=[dict(x=50,y=49,flags=0 if row['visibility']=='unvisited' else 1)])
            doc['actions']=[command('lrs','l'),command('tactical','l')]
            case.expect('results.0.cells',dict(x=50,y=49,glyph=row['glyph'],terrain=None,elevation=None),'has_fields')
            case.expect('results.1.cells',dict(x=50,y=49,terrain_visible=False,elevation_visible=False),'has_fields')
        elif n==4:
            u['lrs_range']=int(row['range']);u['display']=dict(lrsheight='' if row['preference']=='unset' else row['preference'])
            doc['actions']=[command('lrs','t')];case.expect('results.0.rows',3+2*int(row['height']),'length').expect('results.0.warnings',int(row['warnings']),'length')
        elif n==5:
            x,y=map(int,row['position'].split(','));u['at']=[x,y,0]
            doc['units'].append(dict(name='target',id=20,contact_id='TT',at=[x,y,0],team=2))
            doc['diagnostic_cache']=[dict(viewer='u',target='target',flags=6)];doc['actions']=[command('navigate'),command('findcenter')]
            case.expect('results.0.rows',13,'length').expect('results.0.window',[x-2,y-2,5,5]).expect('results.0.plain','Location:','contains').expect('results.0.plain','Speed:','contains').expect('results.0.plain','*','contains')
            case.expect('results.0.cells',dict(x=x,y=y),'has_fields')
            case.expect('results.1.message','0.00','contains')
        else:
            u['display']=dict(ansimap=True,mapcolor=row['palette'])
            doc['units'].append(dict(name='target',id=20,contact_id='TT',at=[50,50,0],display=dict(ansimap=True)))
            doc['actions']=[command('tactical'),command('tactical'),command('tactical',unit='target')]
            case.expect('results.0.warnings',int(row['warnings']),'length').expect('results.1.warnings',int(row['warnings']),'length').expect('results.2.warnings',[])
            case.expect('results.0.rows','results.1.rows','same')
        yield case
