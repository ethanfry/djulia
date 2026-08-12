from djulia import Resource, api

from .models import Article, Author, Tag

# Zero config: full CRUD + filtering + sorting + pagination for free.
api.register(Author)
api.register(Tag)


# Or subclass to override just what the defaults don't cover.
@api.register(Article)
class ArticleResource(Resource):
    ordering_fields = ["title", "created"]  # restrict sortable fields
