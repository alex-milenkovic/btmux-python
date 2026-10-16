"""Configured persistent object discovery and source-context expression services."""
from types import SimpleNamespace
from core.attributes import AttributeStore,attributes_for


class ObjectRegistry:
    """Durable object metadata; live hardcode instances resolve through a loader.

    The loader may hydrate an unloaded unit. Containment order is persisted
    explicitly, so discovery does not depend on Personnel's active membership.
    """
    def __init__(self,path=None,resolve=None):
        self.store=AttributeStore(path)
        self.resolve_live=resolve or (lambda identity:None)

    def register(self,obj,*,kind=None):
        import json
        ident=obj._id
        old=self.resolve(ident)
        origin=getattr(old,'location',-1)
        location=getattr(obj,'location',-1)
        if origin!=location:self._remove(origin,ident)
        record=dict(location=location,hardcode=bool(getattr(obj,'hardcode',hasattr(obj,'sections'))),
                    zombie=bool(getattr(obj,'zombie',False)),
                    kind=kind or ('mech' if hasattr(obj,'sections') else 'object'))
        self.store.set(ident,'OBJECT',json.dumps(record))
        children=self.contents(location)
        if ident not in children:
            children.append(ident);self.store.set(location,'CONTENTS',json.dumps(children))

    def _remove(self,location,ident):
        import json
        self.store.set(location,'CONTENTS',json.dumps([i for i in self.contents(location) if i!=ident]))

    def resolve(self,ident):
        import json
        raw=self.store.get(ident,'OBJECT',None)
        if raw is None:return self.resolve_live(ident)
        return SimpleNamespace(_id=ident,**json.loads(raw))

    def contents(self,ident):
        import json
        return json.loads(self.store.get(ident,'CONTENTS','[]'))

    def mech(self,ident):
        obj=self.resolve(ident)
        if obj is None or not getattr(obj,'hardcode',False) or getattr(obj,'zombie',False):return None
        if getattr(obj,'kind','mech' if hasattr(obj,'sections') else '')!='mech':return None
        live=self.resolve_live(ident)
        return live if live is not None and hasattr(live,'sections') else None


STATUS_FLAGS=('EV_STRIP_AROUND','EV_NO_COMPRESS','EV_NO_LOCATION','EV_NOFCHECK','EV_NOTRACE','EV_FIGNORE')


def status_template(unit,caller=None):
    """Return (attribute was nonempty, evaluated text), including empty results."""
    from systems.armor_display import DisplayDependencyError
    value=attributes_for(unit).get(unit._id,'A_MECHSTATUS',None)
    if value is None:
        value=getattr(unit,'status_template','')
        if not getattr(unit,'status_expression',False):return bool(value),value
    if not value:return False,''
    evaluator=getattr(getattr(unit,'_engine',None),'expression_evaluator',None)
    if evaluator is None:
        raise DisplayDependencyError('Custom status expression evaluator unavailable.','MUX-custom-template-expression')
    actor=caller if caller is not None else getattr(unit,'command_actor',getattr(unit,'pilot',None))
    player=actor if isinstance(actor,int) else getattr(actor,'_id',-1)
    result=evaluator(value,executor=player,enactor=unit._id,flags=STATUS_FLAGS,args=())
    return True,str(result)
