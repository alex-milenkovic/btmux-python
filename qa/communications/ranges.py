"""Source range and visibility folds, plus ordinary combat consumers."""
from qa.communications.common import *
from qa.communications.membership import changed

def run():
 a=Audit('ranges')
 for ident,n,r,line in rows('ranges'):
  u=unit('A',kind='C3',masters=1,at=[3,15,0]);t=unit('T',ident=90,kind=None,character=190,at=[3,3,0],team=2);units=[u];acts=[];kw={};actual=12;kind='C3'
  if n==1:
   actual=int(r['real']);specs=r['peers'].split(';')
   for i,s in enumerate(specs):
    name,description=s.split(':');distance=int(description.split('-')[0]);p=t if name=='target' else unit(name,kind='C3',at=[3,3+distance,0]);units.append(p);acts.append(command('c3',p['name'],'AA'))
    if name=='target':p['team']=1;p['specials']=C['C3_SLAVE_TECH'];p['sections'][2]['slots']=[dict(index=0,special='C3_SLAVE')]
    else:
     visibility='invisible' if '-invisible' in s else 'something' if '-something' in s else 'clear';acts.append(cache(name,'T',visibility))
     if s.endswith('unconscious'):acts+=changed(name,'unconscious')
     if s.endswith('stopped'):acts+=changed(name,'stopped')
     if s.endswith('AngelECM'):acts+=changed(name,'Angel-disturbed')
   if t not in units:units.append(t)
   acts.append(diag('range',target='T',distance=actual))
  elif n==2:
   s=r['state'];kind='C3i' if 'C3i' in s else 'C3';u=unit('A',kind=kind,masters=int(kind=='C3'),at=[4,15,0]);units=[u,unit('B',kind=kind,at=[4,5,0]),t];acts=[command(kind.lower(),'B','AA')]
   if s.startswith('hex'):
    x=0 if 'X0' in s else 4;y=0 if 'Y0' in s else 4
    if 'height3' in s:kw['map']={'size':[30,30],'hexes':[dict(at=[4,4],terrain='GRASSLAND',elevation=3)]}
    acts+=[command('lock',args=f'{x} {y}'),diag('range',distance=12,ordinary=kind=='C3')]
   else:
    if 'destroyed' in s:acts.append(setcomm(crit_status=C['C3_DESTROYED' if kind=='C3' else 'C3I_DESTROYED']))
    if 'ECM' in s:acts+=changed('A','ECM-disturbed')
    if 'empty' in s:acts.append(command(kind.lower(),'B','-'))
    acts+=[diag('range',target='T',distance=12,reference=77,ordinary=kind=='C3')]
  elif n==3:
   s=r['views'];views=[] if s=='none' else s.split(',')
   for i,v in enumerate(views):
    name=chr(66+i);p=unit(name,kind='C3',at=[3,5+i,0])
    if v=='target-self':p=t;p['team']=1;p['specials']=C['C3_SLAVE_TECH'];p['sections'][2]['slots']=[dict(index=0,special='C3_SLAVE')]
    units.append(p);acts.append(command('c3',p['name'],'AA'))
    if v=='unconscious-clear':acts+=changed(p['name'],'unconscious')
    acts.append(cache(p['name'],'T',v if v in ('clear','something','invisible') else 'clear'))
   if t not in units:units.append(t)
   acts.append(diag('network-visibility',target='T'))
  else:
   s=r['condition'];actual=12 if s.startswith('real12') else .2 if s.startswith('own-') else 8
   u['at']=[3,3+int(actual),0];weapon='IS.LRM-5' if s.startswith('own-') else 'IS.MediumLaser';u['weapons']=[dict(name=weapon,section=0,critical=4)]
   if s.startswith('own-'):
    u['real']=[1000,1000+.2*322.5,0];t['real']=[1000,1000,0];u['ammo']=[dict(weapon=weapon,rounds=20,section=3,critical=0)]
   distance=4 if 'peer4' in s else 2;b=unit('B',kind='C3',at=[3,3+distance,0]);units=[u,b,t];acts=[command('c3','B','AA')]
   if s.startswith('both'):
    u['specials2']=C['C3I_TECH'];u['sections'][3]['slots']=[dict(index=0,special='C3I')];units.append(unit('C',at=[3,5,0]));acts.append(command('c3i','C','AA'))
   if 'peer-shutdown' in s:acts.append(command('shutdown','B'))
   if 'owner-ECM' in s:acts+=changed('A','ECM-disturbed')
   acts+=[command('sight',args='0 TT'),command('fire',args='0 TT')]
  o=runrow(a,ident,n,r,line,doc(acts,units=units,streams=combat_streams(),**kw),mode='ordinary joins/sight/fire; explicit cache and range diagnostics' if n<4 or 'ECM' in str(r) else 'ordinary joins/sight/fire');result=o['results'][-1]
  if n==1:
   value,ref=r['result'].split(',');a.near('strict best source distance',result[0],float(value));a.eq('ordered contributor reference',result[1],0 if ref=='0' else 10*(ord(ref)-64))
  elif n==2:
   if s=='hex-X4-Y4-height3':
    a.eq('actual target elevation',state(o)['targ_z'],3);a.near('elevated geometry',result[0],(1+.6**2)**.5);a.eq('hex contributor',result[1],20)
   else:
    a.eq('early return range/reference',result,[12,0 if s.startswith(('hex','empty')) else 77]);a.eq('stored owner',peers(o,'A',kind),[] if 'C3i-destroyed' in s or 'empty' in s else [20]);a.eq('reciprocal peer',peers(o,'B',kind),[] if 'C3i-destroyed' in s or 'empty' in s else [10])
  elif n==3:a.eq('ordered source fold',result,int(r['code']))
  else:
   bracket='TOFAR' if actual==12 or s.startswith('own-') else 'LONG' if 'then-' in s else 'MED' if distance==4 else 'SHORT';expectedref=0 if 'peer-shutdown' in s else -1 if 'owner-ECM' in s else -1 if s.startswith('own-') else 20
   for shot in o['results'][-2:]:
    bth=shot.get('attack',{}).get('bth_breakdown')
    a.true('actual combat breakdown',bth is not None)
    if bth and s.startswith('own-'):a.eq('accepted minimum bypass arithmetic',bth['range_mod'],6)
    if bth:a.eq('source selected bracket',bth['range_bracket'],bracket);a.eq('actual combat reference',bth['c3_ref'],expectedref)
   a.eq('fire gate',result.get('accepted'),actual!=12)
   if actual!=12:a.true('weapon entered recycle',state(o)['weapons'][0]['recycle']>0)
   if expectedref>0:a.true('source range-data message',any('Using range data from B [BB]' in m for m in state(o)['messages']))
 return a.save()
if __name__=='__main__':run()
