# Configuring djulia

Zero-config registration (`api.register(Model)`) already gives a fully-featured
endpoint. You override **only what you need** on a `Resource` subclass —
everything you don't set keeps its introspected default.

Two places config lives:
- **Per-resource** — a `Resource` subclass registered for a model.
- **Project-wide** — a `DJULIA` dict in `settings.py`.

Every snippet below reflects behaviour that's implemented today (see the
[test suite](../tests) and [`example/blog/djulia_resources.py`](../example/blog/djulia_resources.py)
for live versions).

## Registering resources

```python
from djulia import Resource, api
from .models import Author

api.register(Author)                     # zero-config defaults
api.register(Author, AuthorResource)     # explicit class

@api.register(Author)                    # decorator form
class AuthorResource(Resource):
    ...
```

Put these in `<app>/djulia_resources.py`; djulia autodiscovers that module on
startup.

Register **every model in an app** at once:

```python
api.register_app("blog")     # all models in `blog`, with defaults
```

Models you've already registered (e.g. with a custom `Resource`) are left
untouched, so you can bulk-register and still override the few that need it.

## Recipes

### Choose which attributes are exposed — `fields`

```python
@api.register(Author)
class AuthorResource(Resource):
    fields = ["name"]        # only these attributes; omit `fields` to expose all
```

There's no `exclude`/`hidden` shorthand yet — list the columns you want to keep.

### Choose which relationships appear — `relationships`

```python
class ArticleResource(Resource):
    relationships = ["author"]   # expose `author`, hide `tags`
```

### Rename the JSON:API type — `type_name`

Default is the slug of the model's plural verbose name (`Article` → `"articles"`).

```python
class ArticleResource(Resource):
    type_name = "posts"   # served at /api/posts/; linkage uses {"type": "posts"}
```

### Restrict or shape filtering — `filterset_fields`

Default: every field is filterable with type-aware lookups. Narrow it:

```python
class ArticleResource(Resource):
    filterset_fields = ["title", "author"]                      # exact-match only

class ArticleResource(Resource):
    filterset_fields = {"title": ["icontains"],                 # or choose lookups
                        "created": ["gte", "lte"]}
```

Query with `?filter[title__icontains]=django&filter[created__gte]=2026-01-01`.

### Custom filters — `filterset_class`

When the generated filters aren't enough, bring your own django-filter
`FilterSet` (e.g. a free-text search across columns):

```python
import django_filters
from django.db.models import Q

class ArticleFilterSet(django_filters.FilterSet):
    search = django_filters.CharFilter(method="search_title_body")

    class Meta:
        model = Article
        fields = ["published", "author"]

    def search_title_body(self, queryset, name, value):
        return queryset.filter(Q(title__icontains=value) | Q(body__icontains=value))

class ArticleResource(Resource):
    filterset_class = ArticleFilterSet   # replaces the auto-generated filters
```

Query with `?filter[search]=django`. `filterset_class` takes precedence —
`filterset_fields` is ignored when it's set.

### Limit which fields are sortable — `ordering_fields`

Default: all concrete fields are sortable. Restrict:

```python
class ArticleResource(Resource):
    ordering_fields = ["title", "created"]
```

Query with `?sort=-created,title`. Sorting by anything else returns `400`.

### Scope rows per request — `get_queryset`

Object-level visibility. Always call `super().get_queryset()` so you keep the
automatic `select_related`/`prefetch_related`:

```python
class ArticleResource(Resource):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_staff:          # assumes AuthenticationMiddleware
            qs = qs.filter(published=True)
        return qs
```

Applies to both list and detail — a hidden object returns `404`.

### Allow or deny per action — `has_permission`

`action` is one of `"list"`, `"retrieve"`, `"create"`, `"update"`, `"delete"`.
Return `False` to respond `403`:

```python
class ArticleResource(Resource):
    def has_permission(self, request, action):
        if action in ("create", "update", "delete"):
            return request.user.is_authenticated
        return True
```

## Project-wide settings — the `DJULIA` dict

```python
# settings.py
DJULIA = {
    "PAGE_SIZE": 25,             # default page size
    "MAX_PAGE_SIZE": 100,        # cap on ?page[size]
    "BROWSABLE": True,           # HTML browsable API for browsers
    "STRICT_CONTENT_TYPE": True, # enforce vnd.api+json negotiation (415/406)
    "AUTODISCOVER_MODULE": "djulia_resources",  # per-app module djulia imports
    "OPENAPI_TITLE": "djulia API",
    "OPENAPI_VERSION": "1.0.0",
}
```

Any key you omit falls back to the default shown above.

## Not yet supported

- No `exclude`/`hidden` shorthand — list `fields` explicitly.
- No `register(Model, **overrides)` kwarg form — subclass or use the decorator.
- No `?include=` compound documents or dedicated relationship endpoints.

The database-introspection roadmap lives in [docs/standalone.md](standalone.md).
