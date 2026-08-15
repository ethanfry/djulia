"""Examples of djulia's per-resource configuration.

Each resource demonstrates one or more override seams. See
../../docs/configuration.md for standalone, runnable versions of every option
(including the few commented out here to keep the base demo browsable).
"""
import django_filters
from django.db.models import Q

from djulia import Resource, api

from .models import Article, Author, Tag

# Zero config: full CRUD + filtering + sorting + pagination for free.
api.register(Tag)


@api.register(Author)
class AuthorResource(Resource):
    fields = ["name"]                                    # demonstrates: hide the `email` column
    filterset_fields = {"name": ["exact", "icontains"]}  # demonstrates: restrict + shape filtering


# demonstrates: filterset_class — a custom django-filter FilterSet with a
# free-text search. Attach it via `filterset_class = ArticleFilterSet` on the
# resource below to enable ?filter[search]=... (replaces the auto filters).
class ArticleFilterSet(django_filters.FilterSet):
    search = django_filters.CharFilter(method="search_title_body")

    class Meta:
        model = Article
        fields = ["published", "author"]

    def search_title_body(self, queryset, name, value):
        return queryset.filter(Q(title__icontains=value) | Q(body__icontains=value))


@api.register(Article)
class ArticleResource(Resource):
    ordering_fields = ["title", "created"]  # demonstrates: restrict sortable fields

    # demonstrates: row-level scoping — anonymous callers see only published articles.
    def get_queryset(self, request):
        qs = super().get_queryset(request)  # keeps select_related/prefetch
        user = getattr(request, "user", None)
        if not (user and user.is_staff):
            qs = qs.filter(published=True)
        return qs

    # demonstrates: per-action permissions — this API is read/write but never deletes.
    def has_permission(self, request, action):
        return action != "delete"

    # More seams, commented so the base demo keeps its default filters/urls:
    # type_name = "posts"                 # -> served at /api/posts/
    # relationships = ["author"]          # -> hide the `tags` relationship
    # filterset_class = ArticleFilterSet  # -> custom filters (defined above)
