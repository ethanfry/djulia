from django.test import TestCase

from djulia import Resource
from djulia.registry import APIRegistry
from tests.testapp.models import Article


class RegisterAppTests(TestCase):
    def test_registers_all_models_in_app(self):
        reg = APIRegistry()
        reg.register_app("testapp")
        self.assertEqual(
            {r.type_name for r in reg.all_resources()},
            {"authors", "tags", "articles", "widgets", "currencies", "tokens"},
        )

    def test_does_not_clobber_explicit_registration(self):
        reg = APIRegistry()

        class PostResource(Resource):
            type_name = "posts"

        reg.register(Article, PostResource)
        reg.register_app("testapp")
        self.assertEqual(reg.for_model(Article).type_name, "posts")
