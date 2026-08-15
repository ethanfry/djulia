from tests.base import JSONAPITestCase
from tests.testapp.models import Article, Author


class SparseFieldsetTests(JSONAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ada = Author.objects.create(name="Ada")
        Article.objects.create(title="Hello", body="world", author=cls.ada)

    def test_limits_attributes(self):
        data = self.api_get("/api/articles/?fields[articles]=title").json()["data"][0]
        self.assertEqual(list(data["attributes"].keys()), ["title"])

    def test_drops_unlisted_relationships(self):
        data = self.api_get("/api/articles/?fields[articles]=title").json()["data"][0]
        self.assertNotIn("relationships", data)

    def test_can_select_relationship_only(self):
        data = self.api_get("/api/articles/?fields[articles]=author").json()["data"][0]
        self.assertEqual(data["attributes"], {})
        self.assertIn("author", data["relationships"])
