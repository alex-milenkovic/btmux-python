"""Independent JSON/subprocess helpers; no engine imports are permitted here."""
from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'tmp/qa-sensors-los'
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp'))
SCALE=322.5
X2=744.7818472546172
Y1=483.75


def u(name='u',**kw):
    return dict(name=name,contact_id={'u':'AA','t':'TT','b':'BB'}.get(name,name[:2].upper().ljust(2,'0')),
                team=1 if name in ('u','b') else 2,at=[2,1 if name=='u' else 2,0],facing=180,**kw)


def actor(name='u',**kw):
    value=u(name);value.update(kw);return value


def at_range(d):
    # C MapCoordToRealCoord(2,1), translated constants, then vertical range in hexes.
    return [X2,Y1+d*SCALE,0]


def cmd(name,*args,unit='u'): return dict(op='command',unit=unit,name=name,args=list(args))
def adv(n): return dict(op='advance',seconds=n)
def inspect(): return dict(op='inspect')
def diag(kind,target='t',unit='u',**options):
    return dict(op='diagnose',kind=kind,unit=unit,**({'target':target} if target else {}),**({'options':options} if options else {}))
def config(unit='u',**values): return dict(op='configure',unit=unit,values=values)
def move(d,unit='t'): return dict(op='place',unit=unit,at=[2,int(d)+1,0],real=at_range(d))
def cache(flags=15,unit='u',target='t'): return dict(op='cache',unit=unit,target=target,flags=flags)
def state(out,name='u',index=None): return (out['state'] if index is None else out['results'][index])['units'][name]
def events(s,kind): return [e['deadline'] for e in s['events'] if e['kind']==kind]
def messages(s,text): return sum(text in m for m in s['messages'])
def equal(actual,expected): assert actual==expected,f'{actual!r} != {expected!r}'
def near(actual,expected): assert abs(actual-expected)<1e-6,f'{actual} != {expected}'
def equipment(pair): return [name for letter,name in [('R','Radar'),('B','Beagle'),('A','LightBeagle'),('H','Bloodhound')] if letter in pair]


@dataclass
class Case:
    document: dict
    check: object
    label: str=''
    diagnostic: bool=False
    invalid: bool=False
    blocked: str=''
    assertions: str=''

    def execute(self):
        folder=OUTPUT/self.label
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'input.json').write_text(json.dumps(self.document,indent=2)+'\n')
        result=subprocess.run([sys.executable,'-m','tools.sensors_los','--input',str(folder/'input.json')],cwd=ROOT,env=ENV,capture_output=True,text=True,timeout=60)
        (folder/'stdout.json').write_text(result.stdout)
        (folder/'stderr.txt').write_text(result.stderr)
        (folder/'exit-code.txt').write_text(str(result.returncode)+'\n')
        failure=None
        try:
            if self.invalid:
                assert result.returncode!=0,'invalid input accepted'
                assert result.stderr.strip(),'missing error diagnostic'
                assert not result.stdout.strip(),'invalid input emitted success document'
                output={}
            else:
                equal(result.returncode,0);equal(result.stderr,'')
                output=json.loads(result.stdout)
            self.check(output)
        except Exception as error: failure=f'{type(error).__name__}: {error}'
        report=dict(label=self.label,status='failed' if failure else 'blocked' if self.blocked else 'passed',failure=failure,
                    diagnostic=self.diagnostic,blocked=self.blocked,assertions=self.assertions or self.check.__doc__ or 'Independent feature expectations in QA builder.')
        (folder/'assertions.json').write_text(json.dumps(report,indent=2)+'\n')
        return report


def document(units=None,actions=None,**kw):
    return dict(map={'size':[8,80]},units=units or [actor(),actor('t')],actions=actions or [],**kw)
