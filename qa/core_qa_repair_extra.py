"""Source repair flag, section, sink and intact-template replay procedures."""
from core_simulation_qa import D,C,I,case,check as q


def build():
    triggers=(15,9,4,6,5,10,7,8,0,2,1,3,17,18,36,21,37,35,19,48,20,29,40)
    for kind in triggers+(11,12,13,14,16,23,49,50):
        for cls in ('MECH','VEH_GROUND'):
            missing=cls=='MECH' and kind in triggers
            case('repair',f'special-trigger-{kind}-{cls}',[C('repair',0,0)],
                 [q('state.units.u.sections.0.slots.0.firemode',32),q('state.units.u.sections.0.slots.0.brand',3),q('state.units.u.sections.0.slots.0.data',17),q('state.units.u.sections.0.slots.0.weap_damage_flags',0),q('state.units.u.external_effects',int(missing),where={'service':'intact unit template'},length=True)],
                 units=[dict(name='u',**{'class':cls},sections=[dict(index=0,slots=[dict(index=0,type=394+kind,firemode=1|2|4|8|64|32,brand=163,data=17,weap_damage_flags=127)])])],mode='blocked' if missing else 'ordinary')
    for cls in ('MECH','AERO','DS','SPHEROID_DS','BSUIT'):
        for remaining in (False,True):
            sections=[dict(index=i,armor=0,internal=0 if i==0 or i==1 and remaining else 10,internal_orig=10,config=10 if i==0 or i==1 and remaining else 0) for i in range(8)]
            case('repair',f'attach-repeat-{cls}-{remaining}',[C('reattach',0),I(),C('reattach',0),I()],
                 [q('results.1',same_as='results.3'),q('state.units.u.sections.0.internal',0 if cls in ('DS','SPHEROID_DS') else 1 if cls=='AERO' else 10),q('state.units.u.sections.0.config',10 if cls in ('DS','SPHEROID_DS') else 0),q('state.units.u.destroyed',True)],units=[dict(name='u',**{'class':cls},destroyed=True,sections=sections)],mode='ordinary')
    for operation in ('reattach','replacesuit','reseal'):
        for dead in (False,True):
            for flooded in (False,True):
                case('repair',f'section-guards-{operation}-{dead}-{flooded}',[C(operation,0)],
                     [q('state.units.u.sections.0.internal',10 if operation!='reseal' or not dead else 0),q('state.units.u.sections.0.config', ((2 if operation=='reseal' and dead else 0)|(8 if flooded else 0)) if (operation=='replacesuit' or operation=='reattach' and not dead or operation=='reseal' and dead) else 0)],
                     units=[dict(name='u',sections=[dict(index=0,armor=0,internal=0 if dead else 10,internal_orig=10,config=(2 if dead else 0)|(8 if flooded else 0))])],mode='ordinary')
    for cls,move,limit in [('MECH','BIPED',6),('MECH','QUAD',6),('MW','BIPED',2),('VEH_GROUND','TRACK',12)]:
        # Use non-trigger cargo slots so this isolates iteration boundaries.
        case('repair','fixextra-bounds-'+cls+move,[C('fixextra')],
             [q('state.units.u.sections.7.config',0),q('state.units.u.sections.7.slots',[0 if i<limit else 3 for i in range(12)],project='firemode')],
             units=[dict(name='u',**{'class':cls},movement=move,sections=[dict(index=7,config=8,slots=[dict(index=i,type=512,firemode=3) for i in range(12)])])],mode='blocked' if cls=='MECH' else 'ordinary')
    for flags in (0,1,2,3,7,8,128|1):
        case('repair','fixextra-ammo-'+str(flags),[C('fixextra')],[q('state.units.u.sections.4.slots.0.firemode',flags&~2),q('state.units.u.sections.4.slots.0.data',10 if flags&128 else 20)],
             units=[dict(name='u',**{'class':'VEH_GROUND'},ammo=[dict(weapon='IS.AC/5',section=4,critical=0,rounds=0)],sections=[dict(index=4,slots=[dict(index=0,firemode=flags)])])],mode='ordinary')
    for double,clan,compact,ice in [(False,False,False,False),(True,False,False,False),(False,True,False,False),(False,False,True,False),(False,False,False,True)]:
        for loud in (False,True):
            for damaged in (0,1,2):
                size=2 if clan else 3 if double else 1;eff=2 if double or clan else 1
                engine=0 if ice else 8;count=5+min(10*size//eff,engine*size);full=count//size*eff;remaining=full-damaged*eff//size
                case('repair',f'sinks-derived-{double}-{clan}-{compact}-{ice}-{loud}-{damaged}',[D('do_sub_magic',loud)],
                     [q('state.units.u.real_num_sinks',10 if loud and remaining!=10 else remaining),q('state.units.u.original_sinks',full),q('state.units.u.jump_speed',0)],
                     units=[dict(name='u',profile='sparse',max_speed=64.5,specials=(8 if double else 0)|(0x20 if clan else 0)|(0x400000 if ice else 0),specials2=512 if compact else 0,core={'engine_rating':200,'real_num_sinks':10},sections=[dict(index=0,slots=[dict(index=i,special='HEAT_SINK',firemode=1 if i<damaged else 0) for i in range(5)])])])
    template=dict(name='intact',core={'engine_rating':200},max_speed=64.5,num_sinks=10,sections=[dict(index=4,slots=[dict(index=i,special='ENGINE') for i in range(3)]),dict(index=7,slots=[dict(index=0,special='SENSORS')])],weapons=[dict(name='IS.SmallLaser',section=0,critical=4)])
    unit=dict(template,name='u',core={'engine_rating':1,'template_ref':'intact'},sections=[dict(index=4,slots=[dict(index=0,special='ENGINE',firemode=1),dict(index=1,special='ENGINE',firemode=1),dict(index=2,special='ENGINE')]),dict(index=7,slots=[dict(index=0,special='SENSORS',firemode=1)]),dict(index=0,config=32,specials=30,slots=[dict(index=4,firemode=256|512|0x100000|0x40000)])])
    case('repair','full-template-copyback',[I(),C('repair',4,0),I(),C('repair',7,0),I()],
         [q('results.0.templates',same_as='state.templates'),q('results.2.units.u.engine_heat',5),q('results.2.units.u.lrs_range',15),q('state.units.u.lrs_range',30),q('state.units.u.engine_rating',200),q('state.units.u.sections.0.specials',0,mask=30),q('state.units.u.sections.0.slots.4.firemode',256)],units=[unit],templates=[{'name':'intact','unit':template}],mode='ordinary')
