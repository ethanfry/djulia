from django.core.exceptions import ImproperlyConfigured
from django.urls import path
from django.utils.text import slugify

from .resource import Resource
from .views import ResourceDetailView, ResourceListView


class APIRegistry:
    """Admin-style registry: ``api.register(Model)`` or ``@api.register(Model)``."""

    def __init__(self):
        self._by_model = {}
        self._by_type = {}

    def register(self, model, resource_class=None):
        # Register immediately with a default (or given) resource, and also return
        # a decorator so `@api.register(Model)` over a Resource subclass works.
        self._add(model, resource_class or Resource)

        def decorator(cls):
            self._add(model, cls)
            return cls
        return decorator

    def _add(self, model, resource_class):
        instance = resource_class(registry=self, model=model)
        clash = self._by_type.get(instance.type_name)
        if clash is not None and clash.model is not model:
            raise ImproperlyConfigured(
                f"JSON:API type '{instance.type_name}' is used by both "
                f"{clash.model.__name__} and {model.__name__}; set a distinct `type_name`.")
        self._by_model[model] = instance
        self._by_type[instance.type_name] = instance

    def for_model(self, model):
        return self._by_model.get(model)

    def all_resources(self):
        return list(self._by_model.values())

    def type_name_for_model(self, model):
        resource = self._by_model.get(model)
        if resource is not None:
            return resource.type_name
        return slugify(str(model._meta.verbose_name_plural))

    @property
    def urls(self):
        from .openapi import openapi_view, swagger_ui_view
        patterns = [
            path("openapi.json", openapi_view, name="openapi"),
            path("docs/", swagger_ui_view, name="docs"),
        ]
        for resource in self._by_model.values():
            base = resource.type_name
            patterns += [
                path(f"{base}/", ResourceListView.as_view(resource=resource),
                     name=f"{base}-list"),
                path(f"{base}/<str:pk>/", ResourceDetailView.as_view(resource=resource),
                     name=f"{base}-detail"),
            ]
        return patterns


api = APIRegistry()
