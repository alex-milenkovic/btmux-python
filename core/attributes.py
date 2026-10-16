"""Local object attributes, with optional durable storage for template services."""
import json
import os
from pathlib import Path
import tempfile


class AttributeStore:
    def __init__(self,path=None,*,root=None):
        self.path=Path(path).absolute() if path is not None else None
        self.root=(Path(root).resolve() if root is not None else self.path.parent.resolve()) if self.path is not None else None
        self.values={};self.writes=[]
        self._automatic_fallback=False
        self._refresh()

    def _checked_path(self,path):
        resolved=path.resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError('Attribute path leaves designated root')
        return resolved

    def _refresh(self):
        if self.path is not None:
            path=self._checked_path(self.path)
            self.values=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

    def get(self,object_id,name,default=''):
        self._refresh()
        return self.values.get(str(object_id),{}).get(name,default)

    def set(self,object_id,name,value):
        # Re-read durable values so independent directory adapters do not erase
        # writes made by each other. The engine serializes template commands.
        self._refresh()
        self.values.setdefault(str(object_id),{})[name]=str(value)
        if self.path is not None:
            destination=self._checked_path(self.path)
            destination.parent.mkdir(parents=True,exist_ok=True)
            # mkstemp opens exclusively: a preexisting file/link is never used
            # as staging storage. Both write targets stay under the store root.
            fd,temporary_name=tempfile.mkstemp(prefix=destination.name+'.',suffix='.tmp',dir=destination.parent)
            temporary=Path(temporary_name)
            try:
                with os.fdopen(fd,'w',encoding='utf-8') as stream:
                    self._checked_path(temporary)
                    json.dump(self.values,stream,sort_keys=True)
                temporary.replace(self._checked_path(self.path))
            finally:
                temporary.unlink(missing_ok=True)
        self.writes.append(dict(object_id=object_id,attribute=name,value=str(value)))


def attributes_for(unit,default=None):
    store=getattr(unit,'attribute_store',None)
    configured=getattr(getattr(unit,'_engine',None),'attributes',None) or default
    # An automatic scratch adapter must not pin a live object to memory when a
    # configured service becomes available. Explicit adapters retain priority.
    if store is None or getattr(store,'_automatic_fallback',False) and configured is not None:
        store=configured
        if store is None:
            store=AttributeStore();store._automatic_fallback=True
        unit.attribute_store=store
    return store


def player_preference(unit, actor, name, field=None, default=''):
    """Read an issuing player's live attribute, with the scalar actor adapter."""
    from systems.targeting import resolve_object
    actor = actor if actor is not None else getattr(unit,'command_actor',getattr(unit,'pilot',None))
    ident = actor if isinstance(actor,int) else getattr(actor,'_id',-1)
    if isinstance(actor,int): actor=resolve_object(unit,actor)
    fallback=getattr(actor,field,default) if field else default
    store=attributes_for(actor,attributes_for(unit)) if actor is not None else attributes_for(unit)
    return store.get(ident,name,fallback)
