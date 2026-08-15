from django.test import override_settings

from tests.base import JSONAPITestCase
from tests.testapp.models import Article, Author


class PaginationTests(JSONAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ada = Author.objects.create(name="Ada")
        for i in range(5):
            Article.objects.create(title=f"A{i}", author=cls.ada)

    def test_meta_and_default_page(self):
        body = self.api_get("/api/articles/").json()
        self.assertEqual(body["meta"]["count"], 5)
        self.assertEqual(body["meta"]["pages"], 1)
        self.assertEqual(len(body["data"]), 5)

    def test_page_size_and_links(self):
        body = self.api_get("/api/articles/?page[size]=2&page[number]=2").json()
        self.assertEqual(len(body["data"]), 2)
        self.assertEqual(body["meta"]["pages"], 3)
        self.assertIsNotNone(body["links"]["next"])
        self.assertIsNotNone(body["links"]["prev"])

    def test_size_clamped_to_max(self):
        body = self.api_get("/api/articles/?page[size]=9999").json()
        self.assertIn("page%5Bsize%5D=100", body["links"]["self"])

    def test_invalid_page_is_400(self):
        resp = self.api_get("/api/articles/?page[number]=abc")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["errors"][0]["source"]["parameter"], "page[number]")

    @override_settings(DJULIA={"PAGE_SIZE": 1})
    def test_page_size_setting(self):
        body = self.api_get("/api/articles/").json()
        self.assertEqual(len(body["data"]), 1)
        self.assertEqual(body["meta"]["pages"], 5)
