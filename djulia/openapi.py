"""Generate an OpenAPI 3.0 document from the registry, and serve Swagger UI.

Because every resource is introspected into typed attributes, relationships, and
filters, the whole spec is derived — no hand-written schema to drift out of date.
"""
import json

from django.db import models
from django.http import HttpResponse, JsonResponse

from .conf import get_setting

_LINKAGE = {
    "type": "object",
    "properties": {"type": {"type": "string"}, "id": {"type": "string"}},
}


def _attribute_schema(field):
    if isinstance(field, models.BooleanField):
        return {"type": "boolean"}
    if isinstance(field, (models.IntegerField, models.AutoField)):
        return {"type": "integer"}
    if isinstance(field, models.FloatField):
        return {"type": "number"}
    if isinstance(field, models.DecimalField):
        return {"type": "string", "format": "decimal"}
    if isinstance(field, models.DateTimeField):  # subclass of DateField, check first
        return {"type": "string", "format": "date-time"}
    if isinstance(field, models.DateField):
        return {"type": "string", "format": "date"}
    if isinstance(field, models.TimeField):
        return {"type": "string", "format": "time"}
    if isinstance(field, models.UUIDField):
        return {"type": "string", "format": "uuid"}
    if isinstance(field, models.EmailField):
        return {"type": "string", "format": "email"}
    if isinstance(field, models.URLField):
        return {"type": "string", "format": "uri"}
    return {"type": "string"}


def _resource_schema(resource):
    attributes = {}
    for name in resource.attribute_names:
        attributes[name] = _attribute_schema(resource.model._meta.get_field(name))
        if name not in resource.writable_attributes:
            attributes[name]["readOnly"] = True

    relationships = {}
    for name in resource.relationship_names:
        spec = resource.relations.get(name)
        if spec is None:
            continue
        data = {"type": "array", "items": _LINKAGE} if spec.to_many else dict(_LINKAGE, nullable=True)
        relationships[name] = {"type": "object", "properties": {"data": data}}
        if not spec.writable:
            relationships[name]["readOnly"] = True

    return {
        "type": "object",
        "properties": {
            "type": {"type": "string", "example": resource.type_name},
            "id": {"type": "string", "readOnly": True} if resource.client_id == "forbidden"
                  else {"type": "string"},
            "attributes": {"type": "object", "properties": attributes},
            "relationships": {"type": "object", "properties": relationships},
        },
    }


def _query_params(resource):
    params = [{
        "name": f"filter[{name}]", "in": "query", "required": False,
        "schema": {"type": "string"},
    } for name in resource.get_filterset_class().base_filters]
    params += [
        {"name": "sort", "in": "query", "required": False, "schema": {"type": "string"},
         "description": "Comma-separated fields; prefix '-' for descending. Allowed: "
                        + ", ".join(sorted(resource.sortable_fields))},
        {"name": f"fields[{resource.type_name}]", "in": "query", "required": False,
         "schema": {"type": "string"}, "description": "Sparse fieldset (comma-separated)."},
        {"name": "page[number]", "in": "query", "required": False, "schema": {"type": "integer"}},
        {"name": "page[size]", "in": "query", "required": False, "schema": {"type": "integer"}},
    ]
    return params


def _json_content(schema):
    return {"content": {"application/vnd.api+json": {"schema": schema}}}


def generate_schema(registry):
    paths, schemas = {}, {}
    for resource in registry.all_resources():
        type_name = resource.type_name
        ref = {"$ref": f"#/components/schemas/{type_name}"}
        schemas[type_name] = _resource_schema(resource)
        list_doc = {"type": "object", "properties": {
            "data": {"type": "array", "items": ref},
            "links": {"type": "object"}, "meta": {"type": "object"}}}
        item_doc = {"type": "object", "properties": {"data": ref}}
        id_param = {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}

        paths[f"/{type_name}/"] = {
            "get": {"summary": f"List {type_name}", "tags": [type_name],
                    "parameters": _query_params(resource),
                    "responses": {"200": dict(description="A collection", **_json_content(list_doc))}},
            "post": {"summary": f"Create {type_name}", "tags": [type_name],
                     "requestBody": dict(required=True, **_json_content(item_doc)),
                     "responses": {"201": dict(description="Created", **_json_content(item_doc))}},
        }
        paths[f"/{type_name}/{{id}}/"] = {
            "get": {"summary": f"Fetch a {type_name}", "tags": [type_name], "parameters": [id_param],
                    "responses": {"200": dict(description="The resource", **_json_content(item_doc))}},
            "patch": {"summary": f"Update a {type_name}", "tags": [type_name], "parameters": [id_param],
                      "requestBody": dict(required=True, **_json_content(item_doc)),
                      "responses": {"200": dict(description="Updated", **_json_content(item_doc))}},
            "delete": {"summary": f"Delete a {type_name}", "tags": [type_name], "parameters": [id_param],
                       "responses": {"204": {"description": "Deleted"}}},
        }

    return {
        "openapi": "3.0.3",
        "info": {"title": get_setting("OPENAPI_TITLE"), "version": get_setting("OPENAPI_VERSION")},
        "paths": paths,
        "components": {"schemas": schemas},
    }


def openapi_view(request):
    from .registry import api
    return JsonResponse(generate_schema(api))


_SWAGGER = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>API docs</title><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head><body><div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>window.ui = SwaggerUIBundle({url:"__URL__",dom_id:"#swagger-ui"});</script>
</body></html>"""


def swagger_ui_view(request):
    url = request.build_absolute_uri("../openapi.json")
    return HttpResponse(_SWAGGER.replace("__URL__", url), content_type="text/html; charset=utf-8")
