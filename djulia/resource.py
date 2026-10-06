from django.core.exceptions import ImproperlyConfigured
from django.db.models import NOT_PROVIDED
from django.db.models.fields import AutoFieldMixin
from django.utils.text import slugify

from .conf import get_setting
from .permissions import get_identity, get_policy


class RelationSpec:
    """Precomputed description of one relationship on a resource's model."""

    def __init__(self, name, to_many, related_model, accessor, forward, writable):
        self.name = name
        self.to_many = to_many
        self.related_model = related_model
        self.accessor = accessor
        self.forward = forward
        self.writable = writable


def _client_id_policy(pk):
    """How a create request may supply ``id``: "forbidden", "optional" or "required".

    Auto-increment keys are always server-assigned; a key with a default (e.g. a
    UUID) may come from the client; a key with neither (a natural key) must.
    """
    while pk.remote_field is not None and pk.remote_field.parent_link:
        pk = pk.remote_field.model._meta.pk  # multi-table inheritance: the parent's key
    if isinstance(pk, AutoFieldMixin):
        return "forbidden"
    if pk.has_default() or getattr(pk, "db_default", NOT_PROVIDED) is not NOT_PROVIDED:
        return "optional"
    return "required"


class Resource:
    """Config + behaviour for exposing one model as a JSON:API resource.

    Bare registration (``api.register(Model)``) yields a fully-featured endpoint
    by introspecting the model. Every attribute below is an override seam.
    """

    model = None
    type_name = None          # None -> slug of the model's plural verbose name
    fields = None             # attribute names; None -> all concrete fields
    relationships = None      # relationship names; None -> all relations
    filterset_fields = None   # None -> auto (all fields); list/dict -> explicit
    filterset_class = None    # a full django-filter FilterSet, when the default won't do
    ordering_fields = None    # None -> all concrete fields are sortable
    permission = None         # None -> the DJULIA["PERMISSION"] policy

    def __init__(self, registry, model=None):
        self.registry = registry
        if model is not None:
            self.model = model
        if self.model is None:
            raise ImproperlyConfigured("Resource requires a `model`.")
        self._filterset_class = None
        self._introspect()

    def _introspect(self):
        meta = self.model._meta
        pk_name = meta.pk.name
        concrete, relations = [], {}
        for f in meta.get_fields():
            if f.is_relation:
                if f.auto_created:  # reverse side of a relation
                    accessor = f.get_accessor_name()
                    if accessor is None:
                        continue
                    # Only a reverse M2M can be set from this side; a reverse FK or
                    # O2O would mean reassigning (or orphaning) the other rows.
                    relations[accessor] = RelationSpec(
                        accessor, not f.one_to_one, f.related_model, accessor,
                        forward=False, writable=f.many_to_many)
                else:               # forward FK / O2O / M2M declared on this model
                    relations[f.name] = RelationSpec(
                        f.name, f.many_to_many, f.related_model, f.name,
                        forward=True, writable=f.editable)
            elif getattr(f, "concrete", False) and f.name != pk_name:
                concrete.append(f.name)

        self.pk_name = pk_name
        self.client_id = _client_id_policy(meta.pk)
        self.concrete_fields = concrete
        self.relations = relations
        self.attribute_names = list(self.fields) if self.fields is not None else concrete
        # Non-editable fields (auto_now, auto_now_add, editable=False) are output-only.
        self.writable_attributes = {
            n for n in self.attribute_names if meta.get_field(n).editable}
        self.relationship_names = (
            list(self.relationships) if self.relationships is not None else list(relations))
        self.sortable_fields = (
            set(self.ordering_fields) if self.ordering_fields is not None
            else set(concrete) | {pk_name})
        if self.type_name is None:
            self.type_name = slugify(str(meta.verbose_name_plural))

    def serialized_relations(self):
        return [self.relations[n] for n in self.relationship_names if n in self.relations]

    def get_filterset_class(self):
        if self._filterset_class is None:
            from .filters import build_filterset
            self._filterset_class = build_filterset(self)
        return self._filterset_class

    # --- override seams -------------------------------------------------

    def get_queryset(self, request):
        qs = self.model._default_manager.all()
        to_one = [s.accessor for s in self.serialized_relations() if s.forward and not s.to_many]
        to_many = [s.accessor for s in self.serialized_relations() if s.to_many]
        if to_one:
            qs = qs.select_related(*to_one)
        if to_many:
            qs = qs.prefetch_related(*to_many)
        return qs

    def has_permission(self, request, action):
        """Return whether ``action`` (list/retrieve/create/update/delete) is allowed.

        Defaults to this resource's ``permission`` policy, else the project's.
        """
        policy = get_policy(self.permission or get_setting("PERMISSION"))
        return policy(get_identity(request), self, action, request)
