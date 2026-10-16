"""Independent source-chart vectors (mech.hitloc.c), one fresh CLI per roll."""
from damage_support import *

# C arcs in order FRONT, BACK, LEFTSIDE, RIGHTSIDE; numbers are C section indices.
AERO_FASA=('00220001100','33223331133','01001113313','02002223323')
AERO_LEGACY=('00220001200','32223231223','31301110313','32302220323')
DS=('55105551155','44404441444','51111115111','50000005000')
NAVAL=('22222222442','22222222442','00000000440','11111110441')
SIDES=('FRONT','BACK','LEFTSIDE','RIGHTSIDE')

def table_case(kind,profile,arc,roll,expected,turret=10):
    d=document(kind);u=d['units'][0];u['sections']=[sec(i) for i in range(8)];section(d,4,internal=turret,internal_orig=10)
    d['random']['streams'].update(crittable_chance=[1]*20,motive_rolls=[2]*10,dropship_wing=[1]*20,vehicle_weapon_weight=[0]*20)
    d['actions']=[diag('location',profile=profile,side=arc,roll=roll)]
    def check(o):
        s=state(o);eq(o['results'][0][0],expected)
        if kind=='VTOL':
            rotor=expected==5
            lost=rotor and (profile=='legacy' and roll==2 or profile=='FASA' and (roll==2 or arc in ('FRONT','BACK') and roll==3))
            damaged=rotor and profile in ('legacy','FASA') and not lost
            checks((s['sections'][5]['internal']==0,lost),(s['max_speed'],0 if lost else 53.75 if damaged else 64.5))
        if profile=='critproof':eq(o['results'][0][1],False)
    return Case(d,check,label=f'vehicle_locations-supp-chart-{kind}-{profile}-{arc}-{turret}-{roll}')


def cases():
    for kind in ('GROUND','VTOL','AERO','DS','SPHEROID_DS','NAVAL'):
        for profile in ('legacy','FASA','critproof'):
            for arcidx,arc in enumerate(SIDES):
                for turret in ((0,10) if kind=='GROUND' else (10,)):
                    if kind=='AERO':vector=(AERO_FASA if profile=='FASA' else AERO_LEGACY)[arcidx]
                    elif kind in ('DS','SPHEROID_DS'):
                        vector=DS[arcidx]
                        if kind=='SPHEROID_DS' and arc=='BACK':vector='44434442444'
                    elif kind=='NAVAL':
                        vector=NAVAL[arcidx]
                        if profile=='FASA' and arc=='BACK':vector='33333333443'
                    elif kind=='GROUND':
                        digit=str((2,3,0,1)[arcidx]);vector=digit*8+('44' if turret else digit*2)+digit
                        if profile=='FASA' and arcidx<2 and turret:vector=vector[:-1]+'4'
                    else:
                        digit=str((2,3,0,1)[arcidx]);vector='555'+digit*5+'555'
                        if profile=='FASA':vector='5555'+digit*4+'555' if arcidx<2 else '5055'+digit*3+'0555'
                    for roll,expected in enumerate(vector,2):yield table_case(kind,profile,arc,roll,int(expected),turret)
    for kind in ('GROUND','VTOL'):
        for arcidx,arc in enumerate(SIDES):
            for turret in ((0,10) if kind=='GROUND' else (10,)):
                vector={('GROUND',0,0):'22212220000',('GROUND',0,10):'22212220444',('GROUND',1,0):'33303331111',('GROUND',1,10):'33303331444',('GROUND',2,0):'00020003000',('GROUND',2,10):'00020003444',('GROUND',3,0):'11121113111',('GROUND',3,10):'11121113444',('VTOL',0,10):'22212220555',('VTOL',1,10):'33303331555',('VTOL',2,10):'00020003555',('VTOL',3,10):'11121113555'}[kind,arcidx,turret]
                for roll,expected in enumerate(vector,2):yield table_case(kind,'advanced',arc,roll,int(expected),turret)
    for profile in ('legacy','FASA','advanced','critproof'):
        d=document('GROUND');u=d['units'][0];u['sections']=[sec(i) for i in range(8)]
        d['config'].update(fasacrit=int(profile=='FASA'),fasaadvvhlcrit=int(profile=='advanced'))
        if profile=='critproof':u['specials']=0x40000000
        d['random']['streams'].update(hit_location_rolls=[7,7],crittable_chance=[1])
        d['actions']=[diag('location',side='FRONT')]
        def check(o,profile=profile):checks((o['results'][0][0],2),(count_draw(o,'hit_location_rolls'),1 if profile=='legacy' else 2))
        yield Case(d,check,label=f'vehicle_locations-supp-full-dispatch-{profile}')
    for draw in (6,5):
        d=document('GROUND');u=d['units'][0];u['sections']=[sec(i,armor=20) for i in range(8)]
        for s in u['sections']:s['armor_orig']=100
        d['random']['streams'].update(crittable_chance=[draw,draw],motive_rolls=[10]);d['actions']=[diag('location',profile='advanced',roll=3)]
        def check(o,draw=draw):checks((count_draw(o,'crittable_chance'),2),(state(o)['max_speed'],53.75 if draw==6 else 64.5))
        yield Case(d,check,label=f'vehicle_locations-supp-double-crittable-{draw}')
    for proof in (False,True):
        d=document('GROUND');d['config']['fasaadvvhlcrit']=1;d['units'][0]['specials']=0x40000000 if proof else 0
        section(d,4,internal=0);d['random']['streams'].update(hit_location_rolls=[7,12],crittable_chance=[1]*10)
        d['actions']=[diag('location',side='FRONT')]
        yield Case(d,lambda o:eq(o['results'][0][0],0),label=f'vehicle_locations-supp-advanced-before-proof-{proof}')
    # Biped rear physical charts equal front; every result uses a fresh fixture.
    for attack,vector in [('punch','024317'),('kick','666555')]:
        for roll,location in enumerate(vector,1):
            d=document();d['actions']=[diag('physical-location',attack=attack,side='BACK',roll=roll)]
            yield Case(d,lambda o,location=location:eq(o['results'][0],int(location)),label=f'locations-supp-biped-back-{attack}-{roll}')
