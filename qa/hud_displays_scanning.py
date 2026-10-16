"""Scan, report, vector and sight workflows through the public CLI."""
from hud_displays_common import *
from hud_displays_contacts import pair,building


def scanning():
    for name,n,row,meta in examples('scanning'):
        doc,u,t=pair(float(row.get('range',2)));u['scan_range']=20;case=Case(name,doc,meta)
        if n==1:
            doc['actions']=[command(row['command'],'TT')]
            case.expect('results.0.ok',row['outcome']=='success')
            if row['outcome']=='out-of-range':case.expect('results.0.message','Target is out of scanner range.')
            case.expect('state.units.target.messages',dict(text='You are being scanned',count=int(row['notices'])),'count_contains')
        elif n==2:
            u['observer']=row['observer']=='true';t['sections']=[dict(index=0,armor=44,armor_orig=99,slots=[dict(index=4,weapon='IS.MediumLaser',data=4)])]
            doc['actions']=[command('scan','TT'+('' if row['option']=='all' else ' '+row['option']))]
            case.expect('results.0.sections',row['sections'].split(','))
            if row['armor']=='44':case.expect('results.0.armor.0.armor',44)
            elif row['armor']=='XX':case.expect('results.0.armor.0.front','X','contains').expect('results.0.armor_display.plain','XX','contains')
            else:case.expect('results.0.sections','armor','excludes')
        elif n==3:
            doc['units']=[u];doc.pop('diagnostic_cache');objects=row['objects']
            if objects=='building-and-mine':building(doc,(50,52));board=doc['maps'][0]
            else:board=doc['map']
            if objects!='empty':doc['actions'].append(command('addmine','50 52 STANDARD 20'))
            index=len(doc['actions']);doc['actions'].append(command('scan','50 52 '+row['option']))
            case.expect(f'results.{index}.ok',True).expect(f'results.{index}.building_queried',True).expect(f'results.{index}.mines_queried',row['mine']=='true')
            if row['mine']=='true':case.expect(f'results.{index}.mines_found',objects!='empty')
        elif n==4:
            u['at']=[2,2,0];doc['actions']=[command('vector','2 2 '+row['z'])]
            case.expect('results.0.message',row['range']+' hexes','contains').expect('results.0.message','mark '+row['mark'],'contains')
        elif n==5:
            u['at']=[2,2,0];doc['map'].update(dark=row['dark']=='true',hexes=[dict(at=[2,5],terrain='GRASSLAND',elevation=4)])
            doc['actions']=[command('range','2 5')];case.expect('results.0.message',row['range']+' hexes','contains')
            case.expect('results.0.message','ground hexes','excludes' if row['ground']=='absent' else 'contains')
            if row['ground']!='absent':case.expect('results.0.message','('+row['ground']+' ground hexes)','contains')
        else:
            t['markings']='' if row['markings']=='empty' else row['markings'];u['facing']=180;u['target']=20
            u['weapons']=[dict(name='IS.MediumLaser',section=0,critical=4)]
            doc['actions']=[action('inspect'),command('view','TT'),command('sight','0'),action('inspect')]
            case.expect('results.1.message',row['text']).expect('results.2.accepted',True).expect('results.2.attack.bth_breakdown.range_mod',0)
            for unit_name,fields in [('u',('heat','sections','weapons')),('target',('sections',))]:
                for field in fields:case.expect(f'results.3.units.{unit_name}.{field}',f'results.0.units.{unit_name}.{field}','same')
        yield case
