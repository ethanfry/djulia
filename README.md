# djulia

Register a Django model, get a [JSON:API](https://jsonapi.org)-compatible
endpoint — with filtering, sorting, sparse fieldsets, pagination, a browsable
HTML API, and auto-generated OpenAPI/Swagger docs.

Built on plain Django class-based views + [django-filter](https://django-filter.readthedocs.io).
No DRF dependency.

> **Early days:** djulia is at 0.0.1. Defaults, status codes and settings may
> still change between releases.

## Install

Not on PyPI yet; install from a checkout:

```bash
pip install -e .
```

Requires Python ≥ 3.10 and Django ≥ 4.2 (tested with Django 4.2, 5.2 and 6.1).

## Quickstart

djulia works with the models you already have; there's no app to generate.

1. Add it to `INSTALLED_APPS`:

   ```python
   INSTALLED_APPS = [..., "djulia", "yourapp"]
   ```

2. Declare resources in `yourapp/djulia_resources.py` (autodiscovered on startup):

   ```python
   from djulia import Resource, api
   from .models import Article, Author

   api.register(Author)                 # zero config: read API + filters + sort + ...

   @api.register(Article)               # or subclass to override just what you need
   class ArticleResource(Resource):
       ordering_fields = ["title", "created"]

   # or: api.register_app("yourapp")    # every model in the app, with defaults
   ```

3. Mount the URLs:

   ```python
   # urls.py
   path("api/", include("djulia.urls")),
   ```

That's it. Each registered model now serves:

- CRUD at `/api/<type>/` and `/api/<type>/<id>/` (reads are public; writes are
  off until you choose a permission policy, see [Writing data](#writing-data))
- Filtering: `?filter[title__icontains]=x` (auto, type-aware lookups)
- Sorting: `?sort=-created,title`
- Sparse fieldsets: `?fields[articles]=title`
- Pagination: `?page[number]=2&page[size]=10`
- A browsable HTML API (for browsers) and JSON (for API clients)
- OpenAPI schema at `/api/openapi.json` and Swagger UI at `/api/docs/`

> **Reads are public by default, and every field is exposed.** Registering a
> model (or a whole app with `register_app`) publishes all of its rows and
> columns to anonymous callers. Before pointing djulia at real data, list the
> fields you mean to share with [`fields`](docs/configuration.md#choose-which-attributes-are-exposed--fields),
> scope rows with [`get_queryset`](docs/configuration.md#scope-rows-per-request--get_queryset),
> or restrict reads with a [custom policy](docs/configuration.md#your-own-policy).
>
> The OpenAPI schema and Swagger UI are also always public, whatever the
> permission policy, so they list every registered model and field. Swagger UI
> loads its assets from the jsDelivr CDN, so it needs internet access and won't
> work under a strict Content-Security-Policy.

## Writing data

Writes are off by default. Turn them on by choosing who may write, for example
anyone with a verified token carrying an `articles:write` scope:

```python
# settings.py
DJULIA = {
    "IDENTITY": "myproject.auth.identity_from_token",  # your token check
    "PERMISSION": "scopes",
}
```

([Here's a recipe](docs/configuration.md#plug-in-your-auth--djuliaidentity) for
`identity_from_token`.)

Then create and update by sending a JSON:API document:

```bash
curl -X POST http://localhost:8000/api/articles/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/vnd.api+json" \
  -d '{"data": {"type": "articles", "attributes": {"title": "Hello"},
       "relationships": {"author": {"data": {"type": "authors", "id": "1"}}}}}'
```

`Content-Type: application/json` works too. A body sent as any other type,
including a bare `curl -d` (which sends form encoding), gets `415`.

Each write is validated up front and saved in one transaction, so a bad request
changes nothing and gets a JSON:API error pointing at the problem. Clients can
send back the whole object they received: read-only fields such as `created`
are ignored when unchanged.

## Auth

djulia doesn't log anyone in. It asks your existing auth who is calling, then
applies a policy:

- **Identity** — `DJULIA["IDENTITY"]` points to a function that returns the
  caller (a user, verified token claims, anything) or `None`. By default it's
  the logged-in Django user, if there is one.
- **Policy** — `DJULIA["PERMISSION"]` is `"read_only"` (the default),
  `"authenticated"`, `"scopes"`, `"allow_all"`, or a path to your own function.
  A resource can set its own with `permission = ...`.

Anonymous callers who are refused get `401`; identified ones get `403`. See
[Permissions](docs/configuration.md#permissions) for a token-verification
recipe and the gateway pattern.

## See it live

The [`example/`](example/) project is a runnable demo with sample data. See
[`example/README.md`](example/README.md) for the few commands to browse a live
API and Swagger UI.

## Running the tests

From the repository root, with djulia installed in a virtualenv:

```bash
python runtests.py                    # the whole suite
python runtests.py tests.test_writes  # one module
```

To test across every supported Django and Python version, use
[tox](https://tox.wiki) (`pip install tox`):

```bash
tox                                   # all versions; Pythons you don't have are skipped
tox -e py313-django52                 # one combination
tox -e py313-django61 -- tests.test_writes
```

## Configuring

Zero-config registration gives you the full read API; override only what you
need on a `Resource` subclass. Per-resource seams: `type_name`, `fields`, `relationships`,
`filterset_fields`, `filterset_class`, `ordering_fields`, `get_queryset`,
`permission`, `has_permission`. Project-wide behaviour lives in a `DJULIA`
settings dict (`PAGE_SIZE`, `MAX_PAGE_SIZE`, `BROWSABLE`, `IDENTITY`,
`PERMISSION`, `AUTODISCOVER_MODULE`, `OPENAPI_TITLE`, `OPENAPI_VERSION`).

See **[docs/configuration.md](docs/configuration.md)** for a recipe per use case,
and [`example/blog/djulia_resources.py`](example/blog/djulia_resources.py) for
live examples.

## Status

Implemented: CRUD with validated, transactional writes; filtering, sorting,
sparse fieldsets, pagination; relationship linkage; pluggable auth and
permission policies; a browsable API; OpenAPI/Swagger.

Not yet: `?include=` (related records in the same response), dedicated
relationship endpoints, full-text search, and using a field other than the
primary key as the public `id`.
