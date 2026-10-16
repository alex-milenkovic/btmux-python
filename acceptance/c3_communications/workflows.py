"""Normal APS dispatch for the independently owned public QA procedures."""
import json
import os
from pathlib import Path
import subprocess
import sys
from . import step

ROOT=Path(__file__).resolve().parents[2]

@step(r'procedure (.+) from the QA specification')
def procedure(world,name):
    world['procedure']=name

@step(r'QA executes the user-visible workflow in a fresh process')
def execute(world):
    name=world['procedure']
    families=['workflows','supplements']
    if name=='c3i-membership-and-loss':families.append('master_correction')
    reports=[]
    for family in families:
        report='aps-'+name+'-'+family
        environment=dict(os.environ,PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp'),
                         QA_COMMS_CASE=name,QA_COMMS_REPORT=report,QA_COMMS_OUTPUT=str(ROOT/'tmp/qa-c3-aps'))
        result=subprocess.run([sys.executable,'-m','qa.communications','--family',family],cwd=ROOT,env=environment,
                              capture_output=True,text=True,timeout=600)
        folder=ROOT/'tmp/qa-c3-aps';folder.mkdir(parents=True,exist_ok=True)
        (folder/(report+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode==0,(family,name,result.stdout[-2000:],result.stderr[-2000:])
        data=json.loads((folder/(report+'.json')).read_text())
        assert data['failures']==0,data
        if family=='workflows':
            identities=[r['identity']['values'] for r in data['results'] if r.get('identity')]
            assert len(identities)==1 and identities[0]['procedure']==name,identities
            world['outcome']=identities[0]['outcome']
        reports.append(data)
    world['workflow_reports']=reports

@step(r'required observable outcome is (.+)')
def outcome(world,expected):
    assert world['outcome']==expected,(world['outcome'],expected)
    assert sum(r['cases'] for r in world['workflow_reports'])>0
