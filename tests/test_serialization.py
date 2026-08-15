from django.db import connection
from django.test.utils import CaptureQueriesContext

from tests.base import JSONAPITestCase
from tests.testapp.models import Article, Author, Tag


class SerializationTests(JSONAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ada = Author.objects.create(name="Ada")
        cls.t1 = Tag.objects.create(label="python")
        cls.t2 = Tag.objects.create(label="web")

    def _article(self, title="A", tags=()):
        art = Article.objects.create(title=title, author=self.ada, published=True)
        if tags:
            art.tags.set(tags)
        return art

    def test_resource_object_shape(self):
        art = self._article("Hello", tags=[self.t1, self.t2])
        data = self.api_get(f"/api/articles/{art.pk}/").json()["data"]
        self.assertEqual(data["type"], "articles")
        self.assertEqual(data["id"], str(art.pk))
        self.assertIn("title", data["attributes"])
        self.assertEqual(data["relationships"]["author"]["data"],
                         {"type": "authors", "id": str(self.ada.pk)})
        tag_ids = {t["id"] for t in data["relationships"]["tags"]["data"]}
        self.assertEqual(tag_ids, {str(self.t1.pk), str(self.t2.pk)})

    def test_empty_to_many_is_empty_list(self):
        art = self._article("NoTags")
        data = self.api_get(f"/api/articles/{art.pk}/").json()["data"]
        self.assertEqual(data["relationships"]["tags"]["data"], [])

    def test_datetime_serialized_as_iso_string(self):
        art = self._article()
        created = self.api_get(f"/api/articles/{art.pk}/").json()["data"]["attributes"]["created"]
        self.assertIsInstance(created, str)
        self.assertIn("T", created)

    def test_list_avoids_n_plus_one(self):
        self._article("a0", tags=[self.t1])
        self._article("a1", tags=[self.t1])
        with CaptureQueriesContext(connection) as few:
            self.api_get("/api/articles/")
        for i in range(8):
            self._article(f"b{i}", tags=[self.t1, self.t2])
        with CaptureQueriesContext(connection) as many:
            self.api_get("/api/articles/")
        self.assertEqual(len(few.captured_queries), len(many.captured_queries))
