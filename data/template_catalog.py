# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mechrep.c
# Historical Aerospace sources:
#   btech/template.c

"""Opt-in custom/upstream routing, retaining the existing per-root directory rules."""
from pathlib import Path
from data.template_directory import TemplateDirectory
from data.template_files import isolated_template, clear_mech, TemplateError, report_template_error


class CatalogDirectory(TemplateDirectory):
    def __init__(self,root,upstream,**options):
        super().__init__(root,**options)
        self.upstream=TemplateDirectory(upstream,**{**options,'attributes':self.attributes})
        if self.root.is_relative_to(self.upstream.root) or self.upstream.root.is_relative_to(self.root):
            raise ValueError('Custom and upstream template roots overlap')
        self.custom_reader=TemplateDirectory(self.root,**{**options,'attributes':self.attributes})
        self.custom_reader.catalog=self.catalog
        self.selected=None

    def reset(self):
        super().reset()
        if hasattr(self,'upstream'):self.upstream.reset()

    def path(self,name):
        return self.mutation_path(name)

    def mutation_path(self,name,origin=None):
        if origin not in (None,'custom'):raise ValueError('Upstream catalog is read-only')
        path=super().path(name)
        if path.is_relative_to(self.upstream.root):raise ValueError('Upstream catalog is read-only')
        return path

    def _roots(self,origin):
        if origin not in (None,'custom','upstream'):raise ValueError('Unknown template origin')
        roots=[('custom',self),('upstream',self.upstream)]
        return [(name,directory) for name,directory in roots if origin is None or name==origin]

    def listing(self):
        entries=[]
        for origin,directory in self._roots(None):
            rows=TemplateDirectory.listing(directory)
            entries.extend(row|{'origin':origin,'path':str(Path(row['directory'])/row['reference']),
                                'lookup_key':row['reference'][:24].lower()} for row in rows)
        for row in entries:
            row['collisions']=[{'origin':other['origin'],'path':other['path']} for other in entries
                               if other['lookup_key']==row['lookup_key']] if sum(other['lookup_key']==row['lookup_key'] for other in entries)>1 else []
        return entries

    def lookup(self,name,origin=None):
        all_matches=[];chosen=None
        for label,directory in self._roots(None):
            path=TemplateDirectory.lookup(directory,name)
            if path is not None:
                if '/' in name:matches=[path.relative_to(directory.root).as_posix()]
                else:matches=directory.ambiguities or [path.relative_to(directory.root).as_posix()]
                all_matches.extend({'origin':label,'path':item} for item in matches)
                if chosen is None and origin in (None,label):chosen=(label,directory,path)
        self._roots(origin)  # Validate even on misses.
        self.ambiguities=all_matches if len(all_matches)>1 else []
        if chosen is None:self.selected=None;return None
        label,directory,path=chosen
        self.selected={'origin':label,'path':path.relative_to(directory.root).as_posix(),
                       'reference':path.name[:24]}
        return path

    def loadnew(self,unit,reference,*,wrapper=False,origin=None,canonical_reference=None,notify=None):
        path=self.lookup(reference,origin)
        selected=dict(self.selected) if self.selected else None
        if selected is None:
            clear_mech(unit,getattr(unit,'template_ref',unit.mech_type)!=(reference if canonical_reference is None else canonical_reference));report_template_error(unit,TemplateError(f"No matching file for '{reference}'."),notify)
            return False
        # Delegate all parser/fallback/event semantics to one existing root.
        directory=self.upstream if selected and selected['origin']=='upstream' else self
        if directory is self:
            # A separate custom adapter prevents recursive dual-root fallback.
            directory=self.custom_reader
            directory.entries=self.entries
        ok=directory.loadnew(unit,reference,wrapper=wrapper,canonical_reference=canonical_reference,notify=notify)
        if ok:
            unit.template_directory=self;unit.template_origin=selected['origin'];unit.template_source=selected['path']
            unit._catalog_baseline=isolated_template(unit)
        return ok

    def restore(self,unit,*,notify=None):
        reference=self._attributes_for(unit).get(unit._id,'A_MECHREF')
        if not reference:raise ValueError("Sorry, I don't know what type of mech this is")
        source=getattr(unit,'template_source',reference) if reference==unit.template_ref else reference
        return self.loadnew(unit,source,origin=getattr(unit,'template_origin',None),canonical_reference=reference,notify=notify)

    def load_reference(self,reference,origin=None):
        # Origin and path belong to the key; caller always receives an isolated copy.
        from entities.mech import Mech
        self.lookup(reference,origin);key=(reference,origin,repr(self.selected))
        if self.reference_key==key and self.reference_unit is not None:return isolated_template(self.reference_unit)
        unit=Mech()
        if not self.loadnew(unit,reference,origin=origin):self.reference_key='';return None
        self.reference_key=key;self.reference_unit=isolated_template(unit)
        return isolated_template(self.reference_unit)
