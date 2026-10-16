"""Remaining source consumer and state-transition regressions."""
from combat_support import *

def cases():
    for name in ('nullsig','stealtharmor'):
        d=fixture();u=d['units'][0];u.update(specials2=16 if name=='nullsig' else 1,num_sinks=10)
        if name=='stealtharmor':u['equipment']=['Guardian']
        d['actions']=[cmd(name),advance(30),inspect(),cmd(name),advance(30)]
        yield Case(d,lambda o:checks((state(o,index=2)['plus_heat'],10.0),(state(o)['plus_heat'],0.0)),label='equipment-signature-live-heat-'+name,mode='normal')
    for enabled in (False,True):
        d=fixture();d['units'][0]['equipment']=['searchlight'];d['map'].update(light=0,mapvis=10);d['random']['streams']['sensor.detect']=[1]*500
        d['actions']=[cmd('mechprefs','SLWarn','ON' if enabled else 'OFF',unit='v'),cmd('slite'),advance(8),inspect(),cmd('slite'),advance(8)]
        yield Case(d,lambda o,enabled=enabled:checks((bool(state(o,'v',3)['crit_status']&2048),True),(bool(state(o,'v')['crit_status']&2048),False),(sum('being illuminated!' in m for m in state(o,'v')['messages']),int(enabled))),label=f'preferences-searchlight-warning-consumer-{enabled}',mode='normal')
        d=fixture(False);section(d,2,armor=100,armor_orig=200);d['actions']=[cmd('mechprefs','ArmorWarn','ON' if enabled else 'OFF'),diag('damage',section=2,amount=1)]
        yield Case(d,lambda o,enabled=enabled:eq(len(state(o)['armor_notices']),int(enabled)),label=f'preferences-armor-warning-consumer-{enabled}',mode='normal')
        d=fixture();d['units'][0].update(at=[3,3,3],piloting=0);d['units'][1]['at']=[8,8,0];d['map']['hexes']=[dict(at=[3,3],terrain='CLEAR',elevation=3)]
        d['actions']=[cmd('mechprefs','AutoFall','ON' if enabled else 'OFF'),cmd('speed','64.5'),advance(20)]
        yield Case(d,lambda o,enabled=enabled:checks((state(o)['fallen'],enabled),(state(o)['speed'],0.0),(loss(o,'u')>0,enabled)),label=f'preferences-cliff-autofall-consumer-{enabled}',mode='normal')
        d=fixture();d['map'].update(size=[30,30],maxvis=5);d['units'][1].update(started=False,at=[20,20,0]);d['units'][0]['target']=-1;d['random']['streams']['sensor.detect']=[1]*500
        d['actions']=[cmd('mechprefs','AutoconShutdown','ON' if enabled else 'OFF'),dict(op='place',unit='v',at=[3,2,0]),advance(8)]
        yield Case(d,lambda o,enabled=enabled:eq(any('notice v' in m for m in state(o)['messages']),enabled),label=f'preferences-autocon-shutdown-consumer-{enabled}',mode='normal')
    for name,tech in [('ecm','Guardian'),('eccm','Guardian'),('angelecm','Angel'),('angeleccm','Angel')]:
        d=fixture();d['units'][0]['equipment']=[tech];d['actions']=[cmd(name),advance(2),inspect(),cmd(name),advance(2)]
        yield Case(d,lambda o,name=name:checks((o['results'][0]['accepted'],True),(bool(state(o,'v',2)['status2']&(4|2048)),name in ('ecm','angelecm')),(bool(state(o,'v')['status2']&(4|2048)),False)),label='equipment-ECM-shared-consumer-'+name,mode='normal')
    for disabled in (False,True):
        d=fixture(False);mount(d,'IS.GaussRifle',crits=1,ammo=10)
        d['actions']=([cmd('disableweap','0')] if disabled else [])+[cmd('weaponstatus'),diag('slot',section=4,slot=0,attacker='v')]
        yield Case(d,lambda o,disabled=disabled:checks((o['results'][-2]['weapons'][0]['status'],'DESTROYED' if disabled else 'OPERATIONAL'),(state(o)['sections'][4]['internal'],200 if disabled else 180)),label=f'preferences-disabled-gauss-critical-{disabled}',mode='normal')
    for condition in ('none','destroyed','stopped','ECM','enemy','no-master','no-LOS','removed'):
        d=fixture(False);mount(d,range_min=0,range_short=3,range_medium=6,range_long=9);u=d['units'][0];u.update(at=[3,10,0],specials=128,working_c3_masters=0 if condition=='no-master' else 1,c3_network=['p']);d['units'][1]['at']=[3,2,0]
        p=dict(name='p',at=[3,3,0],specials=256,team=0)
        if condition=='destroyed':p['destroyed']=True
        if condition=='stopped':p['started']=False
        if condition=='ECM':p['status2']=4
        if condition=='enemy':p['team']=2
        if condition=='no-LOS':d['map']['hexes']=[dict(at=[3,2],terrain='BUILDING',elevation=9)]
        d['units'].append(p);d['actions']=[advance(2)]
        if condition=='removed':d['actions'].append(dict(op='remove',unit='p'))
        d['actions'] += [diag('combat-range',weapon=0,target='v',distance=8),diag('combat-bth',weapon=0,target='v',distance=8)]
        yield Case(d,lambda o,condition=condition:checks((o['results'][-2]['network_range'],1.0 if condition=='none' else 8.0),(o['results'][-1]['c3_ref'],3 if condition=='none' else 0)),label='ranges-real-network-'+condition)
    for mode in (8192,16384,32768):
        d=fixture(False);mount(d,'IS.RotaryAC/5',fire=mode,ammo=0,crits=1);d['random']['streams']['attack_rolls']=[12];d['actions']=[cmd('fire','0')]
        yield Case(d,lambda o:checks((rawslot(o)['firemode'],0),(rounds(o),0),(loss(o),5)),label=f'ammunition-RAC-zero-stock-{mode}',mode='normal',note='Defined local consequences retained; no undefined C ammo pointer is read.')
    for mode in (0,1048576,2097152):
        d=fixture(False);mount(d,'IS.LRM-5',ammo=5,crits=1);slot(d,2,9,ammo='IS.LRM-5',data=5,ammomode=mode)
        d['random']['streams'].update(attack_rolls=[12],missile_pre_roll=[3]*3,missile_cluster=[12]);d['actions']=([cmd('atmrange' if mode==1048576 else 'atmexplosive','0')] if mode else [])+[cmd('weaponstatus'),cmd('fire','0')]
        yield Case(d,lambda o,mode=mode:checks((rawslot(o)['ammomode'],mode),(rawslot(o,2,9)['data'],4),(rawslot(o,2,10)['data'],5),(loss(o),5)),label=f'modes-ATM-selected-bin-{mode}',mode='normal')
    for condition in ('no-ammo-first','catchup','pod-shotdown','normal-mode2-miss'):
        d=fixture(False);mount(d,'IS.NarcBeacon' if condition=='pod-shotdown' else 'IS.SRM-6',ammo=10,crits=1);d['units'][1].update(status=8|2048,specials=4|64)
        mount(d,'IS.Anti-MissileSystem',unit=1,ammo=None if condition=='no-ammo-first' else 10,loc=0,index=4,crits=1,vrt=4,heat=1)
        if condition=='no-ammo-first':mount(d,'CL.Anti-MissileSystem',unit=1,ammo=10,loc=1,index=4,crits=1)
        if condition=='catchup':section(d,5,unit=1,recycle=10);d['actions']=[advance(5)]
        d['random']['streams'].update(ams_rolls=[5],attack_rolls=[6],missile_pre_roll=[3]*3,missile_cluster=[12])
        if condition=='normal-mode2-miss':d['config']['glancing_blows']=2;d['units'][0]['gunnery']=7;d['actions'].append(cmd('fire','0'))
        else:d['actions'].append(diag('missile-hit',weapon=0,target='v',bth=7,roll=12,incoming=6))
        def check(o,condition=condition):
            if condition in ('no-ammo-first','normal-mode2-miss'):checks((draws(o,'ams_rolls'),[]),(rounds(o,'v'),10),(rawslot(o,0,4,'v')['data'],0))
            if condition=='pod-shotdown':checks((state(o,'v')['sections'][4]['specials'],0),(loss(o),0),(draws(o,'ams_rolls'),[5]))
            if condition=='catchup':checks((state(o,'v')['sections'][5]['recycle'],5),(rawslot(o,0,4,'v')['data'],4))
        yield Case(d,check,label='missiles-AMS-'+condition,mode='normal' if condition=='normal-mode2-miss' else 'diagnostic')
    for terrain,expected in [('LIGHT_FOREST',10),('HEAVY_FOREST',8)]:
        d=fixture(False);mount(d,'IS.SRM-6',crits=1);d['config']['moddamagewithwoods']=1;d['map']['hexes']=[dict(at=[3,2],terrain=terrain,elevation=0)];d['random']['streams'].update(missile_pre_roll=[3]*3,missile_cluster=[12],terrain_rolls=[7,6,12]);d['actions']=[diag('missile-hit',weapon=0,target='v',bth=7,roll=12,incoming=6)]
        yield Case(d,lambda o,expected=expected:eq(loss(o),expected),label='missiles-woods-conversion-'+terrain)
    d=fixture(False);mount(d);d['units'][0]['gunnery']=6;d['units'][1].update(**{'class':'BA'},swarm_target='host');d['units'].append(dict(name='host',at=[3,2,0],team=2,facing=180,sections=[sec(i) for i in range(8)]));d['actions']=[diag('combat-attack',weapon=0,target='v',roll=6)]
    yield Case(d,lambda o:checks((loss(o),0),(loss(o,'host'),5),(o['results'][0]['target_id'],3)),label='impacts-same-roll-host-redirection')
    for condition in ('ammo-disabled','reactor-disabled','explosion-safe','ICE','busy','override'):
        d=fixture(False);mount(d,'IS.AC/5',ammo=2,crits=1);u=d['units'][0]
        if condition=='ammo-disabled':d['config']['explode_ammo']=0
        if condition=='reactor-disabled':d['config']['explode_reactor']=0
        if condition=='explosion-safe':u['status']=8|4096
        if condition=='ICE':u['specials']=4194304
        if condition in ('busy','override'):slot(d,4,data=10)
        if condition=='override':u['caller_wizard']=True;d['config']['explode_reactor']=0
        text='ammo' if condition in ('ammo-disabled','explosion-safe') else 'reactor override' if condition=='override' else 'reactor'
        d['actions']=[cmd('explode',*text.split())]
        yield Case(d,lambda o,condition=condition:checks((o['results'][0]['accepted'],condition=='override'),(len(events(o,kind='EXPLODE')),int(condition=='override'))),label='equipment-explode-command-'+condition,mode='normal')
    for cls in ('BA','GROUND','VTOL','AERO','NAVAL'):
        for data in (1,257):
            d=fixture(False);d['units'][0]['class']=cls;mount(d,'IS.AC/5',ammo=2,crits=1);d['actions']=[diag('combat-callback',name='explode',data=data)]
            yield Case(d,lambda o:checks((state(o)['sections'][3]['internal'],0),(state(o)['at'][2],6),(events(o,kind='EXPLODE'),[])),label=f'equipment-explode-class-{cls}-data{data}')
