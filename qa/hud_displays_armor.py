"""Armor oracles from literal C templates and independently supplied point values."""
import ast
from hud_displays_common import *

SOURCE=ROOT/'btmux/btmux/btech/src/btech/mech.status.c'


def source_template(name):
    text=SOURCE.read_text()
    literal=re.search(r'\*const '+name+r'\s*=\s*(.*?);',text,re.S)[1]
    return ''.join(ast.literal_eval(token) for token in re.findall(r'"(?:\\.|[^"\\])*"',literal))


def sketch(template,sections,divide=False):
    """Plain owned source grammar; fixture points are the independent oracle."""
    lines=[]
    for line in template.splitlines():
        if line[:1] in '1234567':line=line[1:]
        out=[];i=0
        while i<len(line):
            c=line[i]
            if c=='&' and i+1<len(line) and line[i+1]=='&':out.append('&');i+=2;continue
            match=re.match(r'&([0-9]?)([+:-])([0-9])',line[i:])
            if match:
                width=int(match[1] or 2);sec=sections[int(match[3])];value=sec[{'+':'armor','-':'rear',':':'internal'}[match[2]]]
                out.append(' '*width if not sec['internal'] else str((value+9)//10 if divide else value).rjust(width)[-width:]);i+=len(match[0]);continue
            match=re.match(r'@([0-9])(.)|!([0-9])([0-9])(.)',line[i:])
            if match:
                locs=[int(match[1])] if match[1] else [int(match[3]),int(match[4])]
                out.append((match[2] or match[5]) if any(sections[j]['internal'] for j in locs) else ' ');i+=len(match[0]);continue
            out.append(c);i+=1
        lines.append(''.join(out))
    return '\r\n'.join(lines)


def armor():
    templates=dict(light='lightmechdesc',medium='mediummechdesc',heavy='heavymechdesc',assault='assaultmechdesc',quad='quaddesc',turreted='vehdesc',**{'no-turret':'veh_not_desc'},VTOL='vtoldesc',MW='mwdesc',squad='bsuitdesc',ship='shipdesc',foil='foildesc',sub='subdesc',aerodyne='aerod_ds_desc',spheroid='spher_ds_desc')
    for name,n,row,meta in examples('armor'):
        doc=document();case=Case(name,doc,meta);u=doc['units'][0]
        if n==1:
            target=dict(name='target',id=20,contact_id='TT',team=2,at=[5,4,0],sections=[dict(index=0,armor=int(row['current']),armor_orig=99,internal=10,internal_orig=10)],display=dict(status_template='7 &+0'))
            doc['units'].append(target);doc['diagnostic_cache']=[dict(viewer='u',target='target',flags=6)]
            if row['repair']=='true':doc['actions'].append(action('repair_diagnose',kind='schedule',unit='target',type=47,payload=0,delay=100))
            index=len(doc['actions']);doc['actions'].append(command('scan',['TT','A']))
            # Source key 7 emits three spaces for an enemy, plus the literal space.
            case.expect(f'results.{index}.armor_display.plain','    '+row['field'])
            doc['actions'].append(action('display_diagnostic',kind='armor_field',values=dict(current=int(row['current']),original=99,repairing=row['repair']=='true')))
            case.expect(f'results.{index+1}.level',int(row['level'])).expect(f'results.{index+1}.plain',row['field'])
        elif n in (2,3):
            values=dict(current=int(row.get('value',0)),original=int(row.get('value',10)),internal=1 if n==2 else 0,
                owner=row.get('owner','true')=='true',width=int(row.get('width',2)),divide=row.get('divide')=='true',show_destroyed=row.get('show')=='true')
            doc['actions']=[action('display_diagnostic',kind='armor_field',values=values)]
            case.expect('results.0.plain',row['field'].replace('_',' ')).expect('results.0.diagnostic',True)
            if n==2:case.expect('results.0.plain',int(row['actual']),'length')
        elif n==4:
            u['sections']=[dict(index=0,internal=int(row['internal'])),dict(index=1,internal=0)]
            u['display']=dict(status_template='7 @0A!01B&&');doc['actions']=[command('status','A')]
            case.expect('results.0.armor.plain',row['output'].replace('_',' '))
        else:
            u.update(formed(row['form']));u['tonnage']=int(row['tons']);u['real_mass']=int(row['tons'])
            sections=[dict(index=i,armor=21+i,armor_orig=99,internal=11+i,internal_orig=99,rear=31+i,rear_orig=99) for i in range(8)]
            if row['form']=='vehicle' and row['turret']=='false':sections[4].update(armor=0,armor_orig=0,internal=0,internal_orig=0,rear=0,rear_orig=0)
            u['sections']=sections;doc['actions']=[command('status','A')];case.expect('results.0.armor.family',row['diagram'])
            if row['diagram']=='six-location-fighter':
                for label,i in [('Nose',0),('Left Wing',1),('Right Wing',2),('Fuselage',3),('Cockpit',4),('Engine',5)]:case.expect('results.0.armor.plain',label+' '+str(21+i),'contains')
            else:case.expect('results.0.armor.plain',sketch(source_template(templates[row['diagram']]),sections,divide=row['form']=='MW'))
        yield case
