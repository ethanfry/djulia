from tests.base import JSONAPITestCase
from tests.testapp.models import Article, Author


class SortTests(JSONAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ada = Author.objects.create(name="Ada")
        for title in ["Banana", "Apple", "Cherry"]:
            Article.objects.create(title=title, author=cls.ada)

    def _titles(self, path):
        return [a["attributes"]["title"] for a in self.api_get(path).json()["data"]]

    def test_ascending(self):
        self.assertEqual(self._titles("/api/articles/?sort=title"),
                         ["Apple", "Banana", "Cherry"])

    def test_descending(self):
        self.assertEqual(self._titles("/api/articles/?sort=-title"),
                         ["Cherry", "Banana", "Apple"])

    def test_disallowed_field_is_400(self):
        resp = self.api_get("/api/articles/?sort=body")  # not in ordering_fields
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["errors"][0]["source"]["parameter"], "sort")
