"""Equipment identities, scan gates, buildings, turrets and status transitions."""
from hud_displays_common import *
from hud_displays_contacts import pair,building
from hud_displays_catalog import definitions


def remaining():
    doc=document(actions=[hud('key=test'),hud('we')]);doc['units'][0]['weapons']=[dict(name='IS.LargeLaser',section=1,critical=4),dict(name='IS.MediumLaser',section=0,critical=6)]
    yield Case('supplement/multi-critical-order',doc).expect('results.1.records',3,'length').expect('results.1.records.0.payload|3','LA').expect('results.1.records.1.payload|3','RA')
    doc,u,t=pair();t['sections']=[dict(index=0,armor=0,internal=0,slots=[dict(index=4,weapon='IS.MediumLaser')]),dict(index=1,slots=[dict(index=4,weapon='IS.MediumLaser')])]
    doc['sessions'].append(dict(name='target-session',unit='target'));doc['actions']=[hud('key=test'),hud('key=target','target-session'),hud('we','target-session'),hud('wsc TT')]
    yield Case('supplement/destroyed-section-we-wsc',doc).expect('results.2.records',3,'length').expect('results.3.records',2,'length').expect('results.3.records.0.payload|0','0').expect('results.3.records.0.payload|2','RA')
    for name,letter in [('IS.iNarcBeacon','I'),('IS.NarcBeacon','N'),('IS.StreakSRM-2','S'),('IS.RL-10','O')]:
        doc=document(actions=[hud('key=test'),hud('we')]);doc['units'][0]['weapons']=[dict(name=name,section=0,critical=4)]
        yield Case('supplement/inherent-mode-'+name.replace('/','_'),doc).expect('results.1.records.0.payload|5',letter)
    defs=definitions();fire=sum(defs[name] for name in ['RAC_TWOSHOT_MODE','RAC_FOURSHOT_MODE','RAC_SIXSHOT_MODE','WILL_JETTISON_MODE','GATTLING_MODE','HOTLOAD_MODE','RFAC_MODE','ON_TC','ULTRA_MODE','HEAT_MODE','OS_MODE'])
    doc=document(actions=[hud('key=test'),hud('we')]);doc['units'][0]['sections']=[dict(index=0,slots=[dict(index=4,weapon='IS.MediumLaser',firemode=fire)])]
    yield Case('supplement/combined-fire-order',doc).expect('results.1.records.0.payload|5','246BGHRTUhO')
    doc=document(actions=[hud('key=test'),hud('sgi')]);doc['units'][0].update(specials=defs['LIGHT_BAP_TECH']|defs['C3_MASTER_TECH'],specials2=defs['BLOODHOUND_PROBE_TECH'])
    yield Case('supplement/duplicate-probe-tech',doc).expect('results.1.records.0.payload|9','bbTm')
    for mode in (0,1):
        doc=document(actions=[hud('key=test'),hud('am')]);doc['units'][0]['sections']=[dict(index=2,slots=[dict(index=0,ammo='IS.AC/5',data=5,ammomode=mode),dict(index=1,ammo='IS.AC/5',data=0,ammomode=mode),dict(index=2,ammo='IS.AC/5',data=7,firemode=2,ammomode=mode)])]
        yield Case('supplement/ammo-empty-disabled-mode-'+str(mode),doc).expect('results.1.records.0.payload|3','5').expect('results.1.records.0.payload|4','60')
    doc,u,t=pair();t['construction']=dict(name='');doc['actions']=[hud('key=test'),hud('c')]
    yield Case('supplement/contact-empty-name',doc).expect('results.1.records.0.payload|4','-')
    for flag,expected in [(8,'    '),(8|64,'J   '),(8|128,'F   '),(8|0x04000000,'H   ')]:
        doc,u,t=pair();u['brief']=1;t['status']=flag;doc['actions']=[command('contacts')]
        yield Case('supplement/status-position-'+str(flag),doc).expect('results.0.contacts.0.status','  '+expected[0]+'  ')
    for status2,enabled,char in [(0x10000,1,'M'),(0x20000,1,'m'),(0x10000,0,' '),(0x20000,0,' ')]:
        doc,u,t=pair();doc['config']['movement_modes']=bool(enabled);u['brief']=1;t['status2']=status2;doc['actions']=[command('contacts')]
        yield Case(f'supplement/movement-mode-{status2}-{enabled}',doc).expect('results.0.contacts.0.status',char+'    ')
    for request in ('asc TT','wsc TT'):
        doc,u,t=pair();u['scan_range']=0;doc['actions']=[hud('key=test'),hud(request)]
        yield Case('supplement/no-scanner-'+request[:3],doc).expect('results.1.records.0.payload','Your system seems to be inoperational').expect('results.1.records',1,'length')
    for invisible in (False,True):
        doc=document([unit(at=[50,50,0])]);building(doc,(50,53));doc['maps'][1]['name']='%crColored Building%cn';doc['maps'][0]['hexes']=[dict(at=[50,53],terrain='BUILDING',elevation=2)]
        if invisible:doc['maps'][0]['map_objects'][0]['obj']=999999
        doc['actions']=[hud('key=test'),hud('cb'),action('configure',unit='u',values=dict(brief=1)),command('contacts')]
        case=Case('supplement/building-name-z-'+str(invisible),doc).expect('results.1.records',1 if invisible else 2,'length')
        if not invisible:case.expect('results.1.records.0.payload|1','Colored Building').expect('results.1.records.0.payload|4','3').expect('results.3.contacts.0.z',2)
        yield case
    # Actual forwarded command with a connected gunner in the registered turret room.
    doc=document([unit(**formed('AERO'))]);doc['characters']=[dict(id=200,name='Gunner',location=300,connected=True)]
    doc['turrets']=[dict(name='nose',id=300,parent='u',gunner=200,arcs=1)]
    doc['actions']=[action('inspect'),action('turret',turret='nose',actor=200,name='status',args='A'),action('inspect')]
    case=Case('supplement/turret-display-restore',doc).expect('results.1.ok',True).expect('results.1.armor.family','six-location-fighter').expect('state.overrides',dict(pilot=0,arc=0))
    case.expect('results.2.units.u.pilot','results.0.units.u.pilot','same');yield case
    # Sight failure must stay a refusal while normal display state remains intact.
    for text in ('0 ZZ','0 TT'):
        doc,u,t=pair(30);u.update(target=20,facing=180,weapons=[dict(name='IS.MediumLaser',section=0,critical=4)]);doc['actions']=[action('inspect'),command('sight',text),action('inspect')]
        case=Case('supplement/sight-refusal-'+text.replace(' ','_'),doc).expect('results.1.accepted',False)
        for peer in ('u','target'):
            for field in ('sections','weapons','heat'):case.expect(f'results.2.units.{peer}.{field}',f'results.0.units.{peer}.{field}','same')
        yield case
