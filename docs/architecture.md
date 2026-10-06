# Architecture

How djulia is put together, and why. For what's planned or missing, see the
[roadmap](roadmap.md); for how to use it, see [configuration](configuration.md).

## The shape of it

djulia turns Django models into a JSON:API. A project registers models with a
global registry; each registration builds a `Resource` by introspecting the
model; the registry generates URL patterns that route to two generic views
(one for collections, one for single records). Everything else (filtering,
pagination, serialization, permissions, OpenAPI) is a small module those views
call.

There is no code generation and no per-model view or serializer. A model's
`_meta` is the source of truth, and a `Resource` subclass only records where a
project wants to differ from what introspection produced.

## Startup

```
Django starts
  └─ DjuliaConfig.ready()                        apps.py
       └─ autodiscover <app>.djulia_resources     (AUTODISCOVER_MODULE setting)
            └─ api.register(Model) / register_app  registry.py
                 └─ Resource(registry, model)      resource.py: _introspect()
                      fields, relations, pk policy, writability, type name

URLconf loads include("djulia.urls")
  └─ api.urls                                      registry.py
       openapi.json, docs/, and per resource:
       <type>/       -> ResourceListView(resource=...)
       <type>/<pk>/  -> ResourceDetailView(resource=...)
```

URL patterns are built when `djulia.urls` is imported, after autodiscovery, so
everything must be registered by the time the URLconf loads.

## A request

```
ResourceListView / ResourceDetailView            views.py
  dispatch
    check_request        content negotiation     negotiation.py   -> 415 / 406
    check_permission     identity + policy       permissions.py   -> 401 / 403
  GET
    get_queryset         row scoping             resource.py
    apply_filters        ?filter[...]            filters.py (django-filter)
    apply_sort           ?sort=...               filters.py
    paginate             ?page[...]              pagination.py
    resource_object      ?fields[...]            serialization.py
    render_document      JSON or browsable HTML  views.py, browsable.py
  POST / PATCH
    read_document        parse + shape checks    -> 400 / 409
    apply_client_id      POST only, by pk type   -> 403 / 409 / 422
    apply_document       attributes, linkage     -> 400 / 403 / 409 / 422
    save                 full_clean, then one transaction   -> 422
```

Any `JSONAPIError` raised along the way is caught in `dispatch` and rendered as
a JSON:API error document (`errors.py`).

## Modules

| Module | Responsibility |
|---|---|
| `apps.py` | Autodiscovers each app's `djulia_resources` module on startup. |
| `registry.py` | `APIRegistry` and the global `api`: model ↔ resource ↔ type name, `register_app`, URL patterns. Rejects two models claiming one type name. |
| `resource.py` | `Resource`: introspects a model into attribute names, `RelationSpec`s (direction, to-many, writability), the client-id policy and type name. Holds the override points (`fields`, `get_queryset`, `permission`, `has_permission`, ...). |
| `views.py` | The two generic views: dispatch, permission check, read path, write path, validation-error mapping. |
| `negotiation.py` | Content-Type and Accept rules. |
| `permissions.py` | Identity hook, built-in policies, policy lookup. |
| `filters.py` | Builds a django-filter `FilterSet` per resource; parses `filter[...]`, `sort`, `fields[...]`. |
| `pagination.py` | Page-number pagination with `links` and `meta`. |
| `serialization.py` | Resource objects and relationship linkage. |
| `openapi.py` | Generates an OpenAPI 3.0 document from the registry; serves Swagger UI. |
| `browsable.py` | Renders a response document as an HTML page for browsers. |
| `errors.py` | `JSONAPIError` and its subclasses, one per status code. |
| `conf.py` | The `DJULIA` settings dict and its defaults. |
| `checks.py` | System checks: reports columns hidden by default, rejects exposed binary columns. |

## Design decisions

**Plain Django, no DRF.** Views are Django class-based views, and filtering
uses django-filter. djulia stays small, and Django's own conventions (apps,
settings, middleware, auth) apply unchanged.

**Introspect by default; override per resource.** Bare registration gives a
complete endpoint. A `Resource` subclass changes only the attributes it sets;
everything else keeps its introspected default, much like Django's admin.

**OpenAPI is the main contract; JSON:API where it helps.** Most clients are
plain HTTP code or generated from the OpenAPI schema, not JSON:API libraries.
djulia follows the spec where it protects clients or correctness, and is
lenient where strictness would only reject reasonable requests:

- `application/json` bodies are accepted as well as the JSON:API media type,
  and `charset=utf-8` is ignored.
- A missing document `type` is accepted (the URL already says it); a wrong one
  is a `409`.
- Read-only values sent back unchanged are ignored, since clients often send
  the whole object back.

Strictness stays where it does real work: bodies with no type or a
CORS-"simple" type are rejected (this blocks cross-site form posts), and an
unsupported `ext` is rejected rather than silently ignored.

**djulia doesn't authenticate.** It asks an identity function who is calling
and a policy whether they may act. The identity can be anything your auth
produced (a Django user, verified token claims, a gateway-provided name), so
djulia never handles credentials, and it works without Django's auth app. The
primary audience is external clients using tokens; session cookies work
through the default identity but aren't a design driver, which is why CSRF
handling isn't built yet.

**Safe defaults, explicit opt-in.** Reads are public and writes are off
(`read_only`). Built-in policies gate writes only; a custom policy can gate
reads too. Binary columns and columns whose names look like credentials are
hidden unless listed in `fields`; a system check reports what was hidden.
Default filters and sorting only cover visible columns, since either would
otherwise leak hidden values.

**Writes are all-or-nothing.** The document's shape, types and every related
id are checked before anything is saved; then the row and its to-many links
are saved in one transaction. A bad request changes nothing.

**Read-only follows Django.** Non-editable fields (`auto_now`, `editable=False`)
and reverse one-to-many/one-to-one relationships are output-only, and marked
`readOnly` in the schema. Whether a create may send an `id` follows the primary
key: never for auto-increment, optionally for keys with a default, always for
natural keys.

## Testing

`runtests.py` runs the suite against `tests/settings.py` (in-memory SQLite,
`PERMISSION = "allow_all"` so CRUD tests don't need credentials). The test
models in `tests/testapp/` cover the shapes djulia must handle: foreign keys,
many-to-many, a non-editable field, a natural primary key and a UUID primary
key. Permission tests use a test-only identity read from a header
(`tests/identity.py`).

`tox` runs the suite per supported Django on the Pythons it supports, and
GitHub Actions runs the whole matrix on every push and pull request.
