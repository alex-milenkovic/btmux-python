"""Built-in AI gameplay encounters and independent public stdin replays.

Run python -B -m tests.test_autopilot_scenarios [--record DIRECTORY].
Only commands, advances and controller save/load mutate the starting world.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from tools.autopilot import AutopilotSession
from tests.test_gameplay_scenarios import observation

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / 'examples/gameplay_scenarios'
NAMES = ('ai_navigation','ai_combat','ai_aerospace')
RESULTS = {}
RECORD = None


def document(name, root):
    doc = json.loads((INPUTS/(name+'.json')).read_text())
    doc['hud_display'] = {'root':str(root)}
    assert all(a['op'] in ('command','advance','ai_save','ai_load','inspect') for a in doc['actions'])
    assert all(a['name'] in ('sendchannel','heading','speed') for a in doc['actions'] if a['op']=='command')
    return doc


def observe(session):
    state = observation(session)
    for name,u in session.units.items():
        state['units'][name].update(shots=getattr(u,'shots_fired',0),weapon_heat=round(u.weap_heat,4),
                                   desired_speed=round(u.desired_speed,4))
    state['autopilots'] = {name:dict(id=a._id,commands=[c.args[:] for c in a.commands],
        target=a.target,flags=a.flags,speed=a.speed,path=None if a.astar_path is None else [[n.x,n.y] for n in a.astar_path],
        weapons=None if a.weaplist is None else [n.weapon_number for n in a.weaplist],
        events=[dict(kind=e.event_type.name,deadline=e.tick) for e in session.engine.events.pending_events(data=a)])
        for name,a in session.autopilots.items()}
    return state


def important(state):
    return dict(units={n:{k:u[k] for k in ('at','started','destroyed','damage','shots','ammo','sensors','target','fallen')}
                             for n,u in state['units'].items()},
                ai={n:{k:a[k] for k in ('commands','target','speed','flags')} for n,a in state['autopilots'].items()})


def play(name):
    with TemporaryDirectory(prefix='btmux-ai-') as directory:
        doc = document(name,Path(directory)/'local')
        session = AutopilotSession(doc)
        session._scenario_los = True
        frames,actions,results = [],[],[]
        cursors = {}
        def note(action=None,result=None,force=False):
            state = observe(session)
            messages = {}
            for n,u in session.units.items():
                new = u.movement_messages[cursors.get(n,0):]
                cursors[n] = len(u.movement_messages)
                if new:messages[n] = list(new)
            if force or messages or not frames or important(state)!=important(frames[-1]['state']):
                frame = dict(state=state,messages=messages)
                if action is not None:frame.update(action=deepcopy(action),result=deepcopy(result))
                frames.append(frame)
        note(force=True)
        for action in doc['actions']:
            if action['op']=='advance':
                for _ in range(action['seconds']):
                    result = session.action(dict(op='advance',seconds=1))
                    assert not result.get('error'),result
                    note()
                note(force=True)
            else:
                result = session.action(action)
                assert result.get('ok',True),result
                actions.append(dict(tick=session.engine.tick,action=action,result=result))
                note(action,result,True)
            results.append(deepcopy(result))
        final = session.snapshot()
        public_doc = document(name,Path(directory)/'public')
        process = subprocess.run([sys.executable,'-B','-m','tools.autopilot'],cwd=ROOT,
            input=json.dumps(public_doc),text=True,capture_output=True,encoding='utf-8',timeout=60,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8'))
        assert process.returncode==0,process.stderr
        public = json.loads(process.stdout)
        assert public['draws']==json.loads(json.dumps(session.draws)),'stdio random draw mismatch'
        for action,expected,actual in zip(doc['actions'],results,public['results'],strict=True):
            if action['op']!='advance':assert actual==json.loads(json.dumps(expected)),(action,expected,actual)
        for field in ('units','maps','events','autopilots','characters'):
            assert public['state'].get(field)==json.loads(json.dumps(final.get(field))),'stdio '+field+' mismatch'
        return dict(name=name,frames=frames,actions=actions,final=observe(session),draws=deepcopy(session.draws),
                    stdio=dict(exit_status=0,commands=True,units=True,maps=True,events=True,controllers=True,characters=True,draws=True))


def milestones(run):
    states=[f['state'] for f in run['frames']]
    final=run['final'];name=run['name'];checks=[]
    def check(value,label):checks.append(dict(milestone=label,passed=bool(value)))
    def at(tick):return next(s for s in states if s['tick']==tick)
    def before_action(text):return next(f['state'] for f in run['frames'] if f.get('action',{}).get('args')==text)
    def messages(unit):return '\n'.join(m for f in run['frames'] for m in f['messages'].get(unit,[]))
    check(all(r['result'].get('ok',True) for r in run['actions']),'Public commands and persistence operations accepted')
    check(any('AUTO_REPLY'==e['kind'] for s in states for e in s['events']),'Replies use delayed AUTO_REPLY events')
    check(any('Captain' in messages('Commander') or word in messages('Commander') for word in ('Roger','Affirmative','Aye','boss')),'Acknowledgments reach Commander through ordinary radio')
    if name=='ai_navigation':
        check(at(2)['autopilots']['ScoutAI']['commands']==[['goto','3','3']] and not at(2)['autopilots']['WingAI']['commands'],'Addressed order reaches only Scout')
        check(all(a['speed']==90 for a in at(20)['autopilots'].values()),'All-unit speed order changes both controllers')
        check(at(20)['units']['Scout']['speed']>0 and at(20)['units']['Scout']['at']!=[3,14,0],'Scout accelerates and crosses real hexes')
        saved=next(f for f in run['frames'] if f.get('action',{}).get('op')=='ai_save')
        loaded=next(f for f in run['frames'] if f.get('action',{}).get('op')=='ai_load')
        check(saved['state']['autopilots']['ScoutAI']['path'] and loaded['state']['autopilots']['ScoutAI']['path'] is None,'Reload discards transient path')
        check(saved['state']['autopilots']['ScoutAI']['events']==loaded['state']['autopilots']['ScoutAI']['events'],'Reload retains next navigation deadline')
        check(at(22)['autopilots']['ScoutAI']['path'] and at(22)['units']['Scout']['speed']>0,'Normal next decision rebuilds path while movement continues')
        route=[s['units']['Scout']['at'] for s in states]
        check(any(x>=7 and y==8 for x,y,z in route) and all(not(x<7 and y==8) for x,y,z in route),'Scout passes around the impassable ridge without entering it')
        check(at(460)['units']['Scout']['at']==[3,3,0] and not at(460)['autopilots']['ScoutAI']['commands'],'Scout arrives and consumes goto command')
        following=before_action('a=WI follow CM')['autopilots']['WingAI']
        check(following['commands'][-1]==['follow','10'] and all(e['kind']!='AUTOGOTO' for e in following['events']),'Follow replaces active goto and cancels its callback')
        check(at(100)['units']['Commander']['at']!=at(40)['units']['Commander']['at'] and at(100)['units']['Wing']['at']!=at(40)['units']['Wing']['at'],'Leader and follower move under normal steering updates')
        check(at(460)['units']['Wing']['at']==at(460)['units']['Commander']['at'] and at(460)['units']['Wing']['speed']==0,'Follower catches and holds beside its stopped leader')
        check(all(not a['commands'] and not a['events'] for a in at(463)['autopilots'].values()),'All-unit stop clears running follow and queues')
        check('Standing' in messages('Commander') or 'standing' in messages('Commander'),'All-unit reports return current status')
    elif name=='ai_combat':
        check(any(s['los']['Sheep->Target']['seen'] for s in states),'Autonomous sensor updates acquire the hostile contact')
        check(at(45)['units']['Sheep']['sensors']==['E','I'],'Heavy target selects EM and infrared sensors')
        check(at(45)['autopilots']['SheepAI']['target']==12,'Radio assigned target reaches gun decisions')
        check(at(45)['units']['Sheep']['shots']>=4 and at(45)['units']['Sheep']['ammo']<40,'Real weapon selection fires repeatedly and consumes ammunition')
        check(any(s['units']['Sheep']['weapon_heat']>0 for s in states) and at(45)['units']['Target']['damage']>0,'Real firing generates heat and target damage')
        check(not at(53)['units']['Sheep']['started'] and at(53)['units']['Sheep']['shots']==at(45)['units']['Sheep']['shots'],'Shutdown suspends actual gunfire')
        check(at(91)['units']['Sheep']['started'] and at(91)['units']['Sheep']['shots']>at(53)['units']['Sheep']['shots'],'Startup countdown completes and autonomous firing resumes')
        check(at(131)['autopilots']['SheepAI']['target']==13 and at(131)['units']['Spare']['damage']>0,'Replacement target order causes damage to the new hostile')
        check(not final['autopilots']['SheepAI']['flags']&256 and final['autopilots']['SheepAI']['target'] in (12,13),'Clearing assigned target returns to scored acquisition')
    else:
        check(any(s['units']['Target']['destroyed'] for s in states),'Fighter destroys its initial target through normal attacks')
        check(any(s['autopilots']['FighterAI']['target']==13 for s in states),'Loss of destroyed target causes autonomous reacquisition')
        check(any(s['units']['Fighter']['sensors']==['E','I'] for s in states),'Historical sensor callback reaches delayed EM/infrared change')
        saved=next(f for f in run['frames'] if f.get('action',{}).get('op')=='ai_save')
        loaded=next(f for f in run['frames'] if f.get('action',{}).get('op')=='ai_load')
        check(saved['state']['autopilots']['FighterAI']['events']==loaded['state']['autopilots']['FighterAI']['events'],'Aerospace reload preserves three service deadlines')
        check(loaded['state']['autopilots']['FighterAI']['weapons'] is None and at(45)['autopilots']['FighterAI']['weapons'],'Weapon profiles rebuild after active reload')
        check(at(65)['units']['Fighter']['shots']==at(45)['units']['Fighter']['shots'] and not at(65)['autopilots']['FighterAI']['events'],'Historical autogun off cancels services and stops firing')
        check(final['units']['Fighter']['shots']>at(65)['units']['Fighter']['shots'],'Historical autogun on resumes actual firing')
        check(final['units']['Fighter']['ammo']<40 and final['units']['Spare']['damage']>0,'Retargeted Aerospace attacks consume ammo and damage survivor')
        check({e['kind'] for e in final['autopilots']['FighterAI']['events']}=={'AUTOGUN','AUTO_SENSOR','AUTO_PROFILE'},'Historical three service chains continue at end of play')
    return checks


def record(run,directory):
    directory.mkdir(parents=True,exist_ok=True)
    (directory/(run['name']+'.json')).write_text(json.dumps(run,separators=(',',':'))+'\n',encoding='utf-8')
    lines=['# '+run['name'],'',f"Replay: `python -B -m tests.test_autopilot_scenarios --replay {run['name']}`",'', '| Tick | Gameplay |','|---|---|']
    previous=None
    for frame in run['frames']:
        state=frame['state'];changes=[]
        if 'action' in frame:changes.append(str(frame['action']))
        for name,u in state['units'].items():
            old=previous['units'][name] if previous else {}
            values=[f'{k}={u[k]}' for k in ('at','started','destroyed','shots','ammo','damage','sensors') if u[k]!=old.get(k)]
            if values:changes.append(name+': '+', '.join(values))
        for name,a in state['autopilots'].items():
            old=previous['autopilots'][name] if previous else {}
            values=[f'{k}={a[k]}' for k in ('commands','target','speed') if a[k]!=old.get(k)]
            if values:changes.append(name+': '+', '.join(values))
        if changes:lines.append(f"| {state['tick']} | "+'; '.join(changes).replace('|','\\|')+' |')
        previous=state
    lines+=['','Milestones:','']+['- '+('PASS: ' if c['passed'] else 'FAIL: ')+c['milestone'] for c in run['checks']]
    lines+=['','Public stdin replay matches commands, unit/map/controller state, characters, pending events and all random draws.','']
    (directory/(run['name']+'.md')).write_text('\n'.join(lines),encoding='utf-8')


class AutopilotScenarios(unittest.TestCase):pass

def scenario(name):
    def test(self):
        run=play(name);run['checks']=milestones(run);RESULTS[name]=run
        if RECORD:record(run,RECORD)
        self.assertEqual([], [c['milestone'] for c in run['checks'] if not c['passed']])
    return test
for name in NAMES:setattr(AutopilotScenarios,'test_'+name,scenario(name))


def main():
    global RECORD
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record',type=Path);parser.add_argument('--replay',choices=NAMES)
    args=parser.parse_args();RECORD=args.record
    suite=unittest.TestSuite(AutopilotScenarios('test_'+n) for n in ([args.replay] if args.replay else NAMES))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if RECORD:
        summary={n:dict(checks=len(r['checks']),ticks=r['final']['tick'],passed=all(c['passed'] for c in r['checks']),stdio=r['stdio']) for n,r in RESULTS.items()}
        (RECORD/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    elif args.replay and args.replay in RESULTS:print(json.dumps(RESULTS[args.replay],indent=2))
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
