"""Generated APS construction bindings; independent QA has separate ownership."""
from functools import lru_cache
from data import templates as t
from data.construction_catalog import Catalog,source_part,runtime_part
from data.template_files import clear_mech
from entities.mech import Mech,Specials as S

BINDINGS=[]


def step(pattern):
    def register(function):BINDINGS.append((pattern,function));return function
    return register


def eq(actual,expected):assert actual==expected,(actual,expected)


def text(value):return '' if value=='empty' else value.replace('~',' ').replace('/BAR/','|')


@lru_cache(None)
def catalog(parts=True):return Catalog(parts=parts)


def unit(w,kind='Mech',move='Biped',tons=50):
    value=Mech();clear_mech(value,True);value.unit_type=t.name_index(t.MECH_TYPES,kind)
    value.move_type=t.name_index(t.MOVE_TYPES,move);value.tonnage=int(tons);w['unit']=value
    return value


def part(name):return runtime_part(source_part(name))


def tech(unit,value):
    first={'XL':S.XL_TECH,'XXL':S.XXL_TECH,'Light':S.LE_TECH,'Compact':S.CE_TECH,'ICE':S.ICE_TECH,
       'DoubleHS':S.DOUBLE_HEAT_TECH,'Clan':S.CLAN_TECH,'EndoSteel':S.ES_TECH,'Reinforced':S.REINFI_TECH,
       'IS-FF':S.FF_TECH,'Clan-FF':S.CLAN_TECH|S.FF_TECH,'hardened':S.HARDA_TECH}
    for word in value.split('+'):
        unit.specials|=first.get(word,0)
        unit.specials2|={'heavy-FF':2,'light-FF':0x4000}.get(word,0)


def attempt(w,fn,*args,**kwargs):
    w['error']=None
    try:w['result']=fn(*args,**kwargs)
    except (ValueError,OSError) as error:w['error']=str(error)


@step(r'a fresh construction session with explicit source defaults')
def fresh(w):
    w.clear();w['construction_templates']=True;w['catalog']=catalog();unit(w)


from . import catalog_steps,numeric,helpers,editor,files,lifecycle,integration
