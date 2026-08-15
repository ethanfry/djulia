from tests.base import JSONAPITestCase
from tests.testapp.models import Article, Author


class FilterTests(JSONAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ada = Author.objects.create(name="Ada")
        cls.bob = Author.objects.create(name="Bob")
        Article.objects.create(title="Hello World", author=cls.ada, published=True)
        Article.objects.create(title="Draft", author=cls.bob, published=False)

    def _count(self, path):
        resp = self.api_get(path)
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()["meta"]["count"]

    def test_exact(self):
        self.assertEqual(self._count("/api/articles/?filter[title]=Draft"), 1)

    def test_boolean(self):
        self.assertEqual(self._count("/api/articles/?filter[published]=true"), 1)

    def test_fk(self):
        self.assertEqual(self._count(f"/api/articles/?filter[author]={self.ada.pk}"), 1)

    def test_text_lookups(self):
        cases = [("icontains", "hello", 1), ("istartswith", "hello", 1),
                 ("iendswith", "world", 1), ("icontains", "r", 2)]
        for lookup, value, expected in cases:
            with self.subTest(lookup=lookup):
                self.assertEqual(self._count(f"/api/articles/?filter[title__{lookup}]={value}"), expected)

    def test_invalid_filter_is_400_with_parameter(self):
        resp = self.api_get("/api/articles/?filter[author]=notanumber")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["errors"][0]["source"]["parameter"], "filter[author]")
