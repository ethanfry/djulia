"""Querystring handling: filtering (django-filter), sorting, sparse fieldsets.

Featured-by-default: with no configuration, every field becomes filterable with
type-appropriate lookups and sortable. Restrict via ``filterset_fields`` /
``ordering_fields``, or replace wholesale with ``filterset_class``.
"""

import re

from django.db import models
from django_filters import FilterSet

from .errors import BadRequest

_FILTER_RE = re.compile(r"^filter\[(?P<field>[^\]]+)\]$")
_FIELDS_RE = re.compile(r"^fields\[(?P<type>[^\]]+)\]$")

_TEXT = (models.CharField, models.TextField, models.SlugField, models.EmailField,
         models.URLField, models.GenericIPAddressField)
_ORDERED = (models.IntegerField, models.FloatField, models.DecimalField,
            models.DateField, models.TimeField, models.DurationField)


def _default_filter_fields(resource):
    """Auto-build django-filter's ``Meta.fields`` dict from the model's fields."""
    fields = {}
    for f in resource.model._meta.get_fields():
        if not getattr(f, "concrete", False):
            continue
        if f.primary_key or f.is_relation:
            fields[f.name] = ["exact"]
        elif isinstance(f, models.BooleanField):
            fields[f.name] = ["exact"]
        elif isinstance(f, _TEXT):
            fields[f.name] = ["exact", "icontains", "istartswith", "iendswith"]
        elif isinstance(f, _ORDERED):  # DateTimeField subclasses DateField
            fields[f.name] = ["exact", "lt", "lte", "gt", "gte"]
    return fields


def build_filterset(resource):
    if resource.filterset_class is not None:
        return resource.filterset_class
    fields = resource.filterset_fields
    if fields is None:
        fields = _default_filter_fields(resource)
    meta = type("Meta", (), {"model": resource.model, "fields": fields})
    return type(f"{resource.model.__name__}FilterSet", (FilterSet,), {"Meta": meta})


def extract_filters(request):
    """Pull JSON:API ``filter[field]=value`` params into a plain dict for django-filter."""
    data = {}
    for key in request.GET:
        m = _FILTER_RE.match(key)
        if m:
            data[m.group("field")] = request.GET[key]
    return data


def apply_filters(queryset, resource, request):
    data = extract_filters(request)
    if not data:
        return queryset
    filterset = resource.get_filterset_class()(data, queryset=queryset, request=request)
    if not filterset.is_valid():
        errors = [
            BadRequest(str(message), parameter=f"filter[{field}]")
            for field, messages in filterset.errors.items()
            for message in messages
        ]
        raise _multi(errors)
    return filterset.qs


def apply_sort(queryset, resource, request):
    sort = request.GET.get("sort")
    if not sort:
        return queryset
    order = []
    for token in (t.strip() for t in sort.split(",")):
        if not token:
            continue
        field = token[1:] if token.startswith("-") else token
        if field not in resource.sortable_fields:
            raise BadRequest(f"Cannot sort by '{field}'.", parameter="sort")
        order.append(token)  # JSON:API '-' prefix already matches Django's order_by
    return queryset.order_by(*order)


def parse_sparse_fields(request):
    out = {}
    for key in request.GET:
        m = _FIELDS_RE.match(key)
        if m:
            out[m.group("type")] = {v for v in request.GET[key].split(",") if v}
    return out


def _multi(errors):
    err = BadRequest("Invalid filter parameter(s).")
    err.errors = errors
    return err
