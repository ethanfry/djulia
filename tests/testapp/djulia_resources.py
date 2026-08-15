from djulia import Resource, api

from .models import Article, Author, Tag, Widget

api.register(Author)
api.register(Tag)


@api.register(Article)
class ArticleResource(Resource):
    ordering_fields = ["title", "created"]


@api.register(Widget)
class WidgetResource(Resource):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(visible=True)

    def has_permission(self, request, action):
        return action != "delete"
