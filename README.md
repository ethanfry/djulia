# djulia

**Turn a SQL database into a full REST API, with almost no code.**

Point Django at your database, let it generate models from the tables, and
register them with djulia. Every table becomes a [JSON:API](https://jsonapi.org)
endpoint with create/read/update/delete, filtering, sorting, pagination,
relationships, a browsable HTML view, and OpenAPI/Swagger docs.

- **Sensible defaults.** One line exposes a whole database. Reads work
  immediately; writes stay off until you decide who may make them.
- **Adjustable with reasonable effort.** Hide columns, scope rows, restrict
  filters or rename types on a single resource, without giving up the defaults
  for everything else.
- **Built on Django.** Auth, middleware, database backends and deployment work
  the way they already do in Django, so you add those pieces with tools and
  standards you know. No DRF dependency.

> **Early days:** djulia is at 0.0.1. Defaults, status codes and settings may
> still change between releases.

## Install

Not on PyPI yet; install from a checkout:

```bash
pip install -e .
```

Requires Python ≥ 3.10 and Django ≥ 4.2 (tested with Django 4.2, 5.2 and 6.1).

## From database to API

Any database Django can talk to works: PostgreSQL, MySQL, MariaDB, SQLite and
Oracle are built in, and third-party backends add SQL Server, CockroachDB and
others.

1. **Create a Django project and point it at your database.** Installing
   djulia already installed Django; add the driver for your database
   (SQLite needs none):

   ```bash
   pip install "psycopg[binary]"   # PostgreSQL; mysqlclient for MySQL/MariaDB, oracledb for Oracle
   django-admin startproject mysite && cd mysite
   python manage.py startapp shop
   ```

   ```python
   # mysite/settings.py
   DATABASES = {
       "default": {
           "ENGINE": "django.db.backends.postgresql",
           "NAME": "shop", "USER": "...", "PASSWORD": "...", "HOST": "...",
       }
   }
   INSTALLED_APPS = [..., "djulia", "shop"]
   ```

2. **Generate models from your tables.**

   ```bash
   python manage.py inspectdb > shop/models.py
   ```

   The generated models are marked `managed = False`, so Django never creates,
   alters or drops your tables. Skim the file: `inspectdb` sometimes has to
   guess a column's type (it notes where), and you may want nicer names for
   relationships, which default to things like `order_set`.

3. **Register every model.**

   ```python
   # shop/djulia_resources.py  (found automatically on startup)
   from djulia import api

   api.register_app("shop")
   ```

4. **Mount the URLs and run it.**

   ```python
   # mysite/urls.py
   from django.urls import include, path

   urlpatterns = [path("api/", include("djulia.urls"))]
   ```

   ```bash
   python manage.py runserver
   ```

Each table now has an endpoint. For example, `GET /api/orders/10/` returns:

```json
{"data": {"type": "orders", "id": "10",
          "attributes": {"placed_at": "2026-03-01T12:00:00Z", "total": "19.98"},
          "relationships": {"customer": {"data": {"type": "customers", "id": "1"}}}}}
```

## What you get

For every registered model:

- CRUD at `/api/<type>/` and `/api/<type>/<id>/` (reads are public; writes are
  off until you choose a permission policy, see [Writing data](#writing-data))
- Filtering: `?filter[name__icontains]=ada` (lookups chosen per column type)
- Sorting: `?sort=-placed_at,id`
- Sparse fieldsets: `?fields[customers]=name,email`
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

## Adjusting the defaults

Override only what you need, one resource at a time. Everything you don't set
keeps its default:

```python
# shop/djulia_resources.py
from djulia import Resource, api
from .models import Customer

@api.register(Customer)
class CustomerResource(Resource):
    fields = ["name", "created_at"]          # hide email
    ordering_fields = ["created_at"]
    permission = "authenticated"              # any identified caller may write

api.register_app("shop")                      # the rest keep the defaults
```

Already have Django models? Skip the database steps and register them
directly with `api.register(MyModel)` or `api.register_app("myapp")`.

Per-resource options: `type_name`, `fields`, `relationships`,
`filterset_fields`, `filterset_class`, `ordering_fields`, `get_queryset`,
`permission`, `has_permission`. Project-wide settings live in a `DJULIA` dict
(`PAGE_SIZE`, `MAX_PAGE_SIZE`, `BROWSABLE`, `IDENTITY`, `PERMISSION`,
`AUTODISCOVER_MODULE`, `OPENAPI_TITLE`, `OPENAPI_VERSION`). See
**[docs/configuration.md](docs/configuration.md)** for a recipe per use case.

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

## Status

Implemented: CRUD with validated, transactional writes; filtering, sorting,
sparse fieldsets, pagination; relationship linkage; pluggable auth and
permission policies; a browsable API; OpenAPI/Swagger.

Not yet: `?include=` (related records in the same response), dedicated
relationship endpoints, full-text search, and using a field other than the
primary key as the public `id`.

Planned: serving an existing database with no Django project at all; see the
[design sketch](docs/standalone.md). The full list lives in the
[roadmap](docs/roadmap.md), and [architecture.md](docs/architecture.md)
explains how djulia is put together.
