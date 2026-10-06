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

## Writing

Create with `POST /api/<type>/`, update with `PATCH /api/<type>/<id>/`. An update
changes only the attributes and relationships you send. Each write is saved in
one transaction, and every related id is checked first, so a bad request
changes nothing.

### Read-only fields

Fields Django treats as non-editable (`auto_now`, `auto_now_add`,
`editable=False`) appear in responses but can't be written, and the OpenAPI
schema marks them `readOnly`. The same goes for reverse one-to-many and
one-to-one relationships (e.g. an author's `articles`); a reverse many-to-many
is writable.

Clients may send back the whole object they received: a read-only value sent
unchanged on update is ignored. Trying to change one, or sending one on create,
returns `403`.

### Ids on create

What a create request may do with `id` depends on the model's primary key:

| Primary key | `id` in a create request |
|---|---|
| auto-increment (Django's default) | not allowed (`403`) |
| has a default, e.g. `UUIDField(default=uuid.uuid4)` | optional; generated if absent |
| neither, e.g. `CharField(primary_key=True)` | required (`422` if missing) |

A client-supplied `id` that already exists returns `409`.

## Permissions

djulia doesn't authenticate anyone. It works in two steps, and you plug your
existing auth into the first:

1. **Identity** — who is calling. A function `get_identity(request)` returns
   whatever your auth layer produced (a user, a dict of verified token claims, a
   service name), or `None` for an anonymous caller.
2. **Policy** — may they do this. A function
   `check(identity, resource, action, request)` returns `True` or `False`.
   `action` is one of `"list"`, `"retrieve"`, `"create"`, `"update"`, `"delete"`.

A denied request gets `401` when there's no identity and `403` otherwise.

### Built-in policies — `DJULIA["PERMISSION"]`

The built-in policies only gate **writes**; reads are always public.

| Policy | Writes are allowed when… |
|---|---|
| `"read_only"` (default) | never |
| `"authenticated"` | there's any identity |
| `"scopes"` | the identity's token claims grant `<type>:write`, e.g. `articles:write` (read from OAuth's space-separated `scope` claim, or `scp`) |
| `"allow_all"` | always (for an API behind a gateway that already enforces access, or a demo) |

```python
DJULIA = {"PERMISSION": "scopes"}
```

Set a different policy for one resource with `permission`:

```python
class TagResource(Resource):
    permission = "authenticated"
```

### Plug in your auth — `DJULIA["IDENTITY"]`

By default the identity is the logged-in Django user (`request.user`), if
there is one. For tokens, verify them with the library you already use and
return the claims:

```python
# myproject/auth.py
import jwt  # PyJWT

def identity_from_token(request):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        return jwt.decode(header.removeprefix("Bearer "), PUBLIC_KEY,
                          algorithms=["RS256"], audience="my-api")
    except jwt.InvalidTokenError:
        return None
```

```python
DJULIA = {
    "IDENTITY": "myproject.auth.identity_from_token",
    "PERMISSION": "scopes",
}
```

**Behind a gateway** that has already checked the caller, the identity function
can read what the gateway forwards (e.g. an `X-User` header). Only do this if
the app is unreachable except through the gateway; otherwise anyone can send
that header.

### Your own policy

Point `PERMISSION` (or a resource's `permission`) at a function. Unlike the
built-in policies, it's called for reads too:

```python
# myproject/auth.py
def staff_only(identity, resource, action, request):
    return identity is not None and identity.get("role") == "staff"
```

```python
DJULIA = {"PERMISSION": "myproject.auth.staff_only"}
```

For logic tied to one resource, override `has_permission` directly:

```python
from djulia.permissions import get_identity

class ArticleResource(Resource):
    def has_permission(self, request, action):
        return action != "delete" and get_identity(request) is not None
```

## Project-wide settings — the `DJULIA` dict

```python
# settings.py
DJULIA = {
    "PAGE_SIZE": 25,             # default page size
    "MAX_PAGE_SIZE": 100,        # cap on ?page[size]
    "BROWSABLE": True,           # HTML browsable API for browsers
    "IDENTITY": None,            # dotted path to get_identity(request); None -> request.user
    "PERMISSION": "read_only",   # a built-in policy name, or a dotted path to your own
    "AUTODISCOVER_MODULE": "djulia_resources",  # per-app module djulia imports
    "OPENAPI_TITLE": "djulia API",
    "OPENAPI_VERSION": "1.0.0",
}
```

Any key you omit falls back to the default shown above.

## Not yet supported

- No `exclude`/`hidden` shorthand — list `fields` explicitly.
- No `register(Model, **overrides)` kwarg form — subclass or use the decorator.
- No `id_field` option: the public `id` is always the primary key. Sequential
  integer keys reveal record counts and are easy to enumerate; use a UUID
  primary key if that matters.
- No `?include=` compound documents or dedicated relationship endpoints.

The database-introspection roadmap lives in [docs/standalone.md](standalone.md).
