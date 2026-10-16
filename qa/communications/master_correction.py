"""Public regressions for C3 master ordering correction.

These use actual fire -> internal damage -> apply_critical_to_slot, not a
manually destroyed slot or a direct consequence-helper call.
"""
from qa.communications.common import *
from qa.communications.workflows import Scenario,joined,arm,target,snap_peers

def run():
 a=Audit('master-correction')
 for count in (1,2):
  names='AB' if count==1 else 'ABCDEF'
  units=[arm(unit('A',kind='C3',masters=count,at=[3,11,0],tag_target=999))]
  for name in names[1:]:units.append(unit(name,kind='C3',at=[3,5 if count==1 or name in 'EF' else 9,0]))
  units.append(unit('H',kind='C3',at=[3,9,0]));t=arm(arm(target()),critical=4,section=1);t['facing']=180;units.append(t)
  units[0]['sections'][2]['armor']=0
  s=joined(Scenario(),names,'c3').add('before',inspect()).add('before-sight',command('sight',args='0 TT'))
  s.add('TAG-boundary-fixture',dict(op='configure',unit='A',values={'tag_target':999})).add('TAG-before',inspect())
  s.add('first-hit',command('fire','T','0 AA')).add('after-first',inspect()).add('physical-count',diag('masters'))
  s.add('after-sight',command('sight',args='0 TT')).add('try-capacity',command('c3','H','AA'),True).add('validated',inspect())
  s.add('second-hit',command('fire','T','1 AA')).add('after-second',inspect()).add('post-loss-report',command('c3network'),count==1).add('post-loss-fire',command('fire',args='0 TT'))
  o,v=s.check(a,'sole-master' if count==1 else 'two-separate-masters',units,streams={'hit_location_rolls':[8,8,7],'critical_rolls':[8,8],'critical_slot':[0,1]})
  a.eq('actual first critical location',v['first-hit']['attack']['location'],2)
  first=v['after-first']['units']['A'];second=v['after-second']['units']['A']
  a.true('functional slot physically destroyed',first['sections'][2]['slots'][0]['firemode']&C['DESTROYED_MODE'])
  a.eq('physical working groups',v['physical-count']['working'],count-1)
  a.eq('first-hit cache immediately updated',first['working_c3_masters'],count-1)
  a.eq('last-master flag immediately set',bool(first['crit_status']&C['C3_DESTROYED']),count==1)
  a.eq('post-use capacity',len(snap_peers(v['validated'],'A','c3')),0 if count==1 else 3)
  after_bth=v['after-sight']['attack']['bth_breakdown']
  a.eq('no obsolete nearest contributor',after_bth['c3_ref'],-1 if count==1 else 20)
  a.eq('post-loss range bracket',after_bth['range_bracket'],'LONG' if count==1 else 'MED')
  a.eq('actual post-loss fire uses same eligibility',v['post-loss-fire']['attack']['bth_breakdown']['c3_ref'],after_bth['c3_ref'])
  a.eq('actual post-loss fire bracket',v['post-loss-fire']['attack']['bth_breakdown']['range_bracket'],after_bth['range_bracket'])
  if count==1:a.eq('TAG pre-hit setup',v['TAG-before']['units']['A']['relationships']['tag_target'],999)
  if count==1:a.eq('existing TAG consequence',first['tag_target'] if 'tag_target' in first else first['relationships']['tag_target'],0)
  loss='One of your C3 systems has been destroyed!'
  a.eq('first-hit loss consequence once',first['messages'].count(loss),1)
  a.eq('disabled master next hit does not repeat loss',second['messages'].count(loss),1)
  a.eq('subsequent disabled-master cache stable',second['working_c3_masters'],count-1)
 return a.save()
if __name__=='__main__':raise SystemExit(bool(run()['failures']))
