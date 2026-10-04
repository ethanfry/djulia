# djulia

Register a Django model, get a [JSON:API](https://jsonapi.org)-compatible
endpoint — with filtering, sorting, sparse fieldsets, pagination, a browsable
HTML API, and auto-generated OpenAPI/Swagger docs.

Built on plain Django class-based views + [django-filter](https://django-filter.readthedocs.io).
No DRF dependency.

## Install

```bash
pip install -e .   # from a checkout; PyPI packaging is still 0.0.1
```

Requires Python ≥ 3.10, Django ≥ 4.2.

## Quickstart

Add djulia to an existing project's models — you don't scaffold a new app.

1. Add it to `INSTALLED_APPS`:

   ```python
   INSTALLED_APPS = [..., "djulia", "yourapp"]
   ```

2. Declare resources in `yourapp/djulia_resources.py` (autodiscovered on startup):

   ```python
   from djulia import Resource, api
   from .models import Article, Author

   api.register(Author)                 # zero config: full CRUD + filters + sort + ...

   @api.register(Article)               # or subclass to override just what you need
   class ArticleResource(Resource):
       ordering_fields = ["title", "created"]
   ```

3. Mount the URLs:

   ```python
   # urls.py
   path("api/", include("djulia.urls")),
   ```

That's it. Each registered model now serves:

- CRUD at `/api/<type>/` and `/api/<type>/<id>/`
- Filtering: `?filter[title__icontains]=x` (auto, type-aware lookups)
- Sorting: `?sort=-created,title`
- Sparse fieldsets: `?fields[articles]=title`
- Pagination: `?page[number]=2&page[size]=10`
- A browsable HTML API (for browsers) and JSON (for API clients)
- OpenAPI schema at `/api/openapi.json` and Swagger UI at `/api/docs/`

## See it live

The [`example/`](example/) project is a runnable demo with sample data. See
[`example/README.md`](example/README.md) for the few commands to browse a live
API and Swagger UI.

## Configuring

Zero-config registration is fully-featured; override only what you need on a
`Resource` subclass. Per-resource seams: `type_name`, `fields`, `relationships`,
`filterset_fields`, `filterset_class`, `ordering_fields`, `get_queryset`,
`has_permission`. Project-wide behaviour lives in a `DJULIA` settings dict
(`PAGE_SIZE`, `MAX_PAGE_SIZE`, `BROWSABLE`, `AUTODISCOVER_MODULE`,
`OPENAPI_TITLE`, `OPENAPI_VERSION`).

See **[docs/configuration.md](docs/configuration.md)** for a recipe per use case,
and [`example/blog/djulia_resources.py`](example/blog/djulia_resources.py) for
live examples.

## Status

Cheap-core: CRUD, filtering, sorting, sparse fieldsets, pagination, flat
relationship linkage, browsable API, OpenAPI/Swagger. Not yet implemented:
`?include=` compound documents and dedicated relationship endpoints.
