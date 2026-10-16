"""Source arc, aim and targeting-computer fallback procedures through the CLI."""
from damage_support import *

def cases():
    for kind,rule,width,back in [('MECH',0,90,30),('MECH',1,45,45),('MECH',2,90,30),('GROUND',0,30,30),('GROUND',1,45,45),('GROUND',2,90,30)]:
        for angle,arc in [(width,'FRONT'),(width+1,'RIGHTSIDE'),(180-back-1,'RIGHTSIDE'),(180-back,'BACK'),(180+back,'BACK'),(180+back+1,'LEFTSIDE'),(360-width-1,'LEFTSIDE'),(360-width,'FRONT')]:
            d=document();fire_setup(d);d['config']['hit_arcs']=rule;d['units'][1].update({'class':kind,'facing':(360-angle)%360})
            d['actions'] += [diag('hit-arc',target='enemy'),cmd('fire',0)]
            loc={'FRONT':4,'BACK':4,'LEFTSIDE':2,'RIGHTSIDE':3}[arc] if kind=='MECH' else {'FRONT':2,'BACK':3,'LEFTSIDE':0,'RIGHTSIDE':1}[arc]
            def check(o,arc=arc,loc=loc,kind=kind):
                eq(o['results'][-2],arc)
                s=state(o,'enemy')['sections'][loc]
                eq(s['rear'] if arc=='BACK' and kind=='MECH' else s['armor'],15 if arc=='BACK' and kind=='MECH' else 95)
            yield Case(d,check,label=f'locations-supp-arcs-{kind}-{rule}-{angle}')
    for tc in (False,True):
        for aim,angle,cover,stopped,wrong,roll,expected in [(4,90,False,False,False,3,4),(7,0,False,True,False,3,7),(7,0,False,False,False,3,4),(0,91,False,False,False,3,3),(5,0,True,False,False,3,0),(4,0,True,False,True,3,0),(0,0,False,False,False,2,4)]:
            d=document();d['units'][0].update(aim=aim,aim_type=1 if wrong else 0)
            d['units'][1].update(facing=(360-angle)%360,started=not stopped,movement='BIPED')
            if cover:d['units'][1]['status']=0x2010
            d['random']['streams'].update(tc_location=[roll],physical_location=[1],hit_location_rolls=[7])
            d['actions']=[diag('tc-location' if tc else 'aim-location',target='enemy')]
            if not tc:expected=7 if aim==7 else 4 if aim==4 else 0 if aim==0 and angle==0 else expected
            def check(o,expected=expected,tc=tc,wrong=wrong):checks((o['results'][0][0],expected),(count_draw(o,'tc_location'),int(tc and not wrong)))
            yield Case(d,check,label=f'locations-supp-aim-{tc}-{aim}-{angle}-{cover}-{stopped}-{wrong}-{roll}')
