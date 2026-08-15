from tests.base import JSONAPITestCase
from tests.testapp.models import Article, Author


class CrudTests(JSONAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ada = Author.objects.create(name="Ada", email="ada@example.com")

    def test_create_returns_201_location_and_sets_fk(self):
        doc = {"data": {
            "type": "articles",
            "attributes": {"title": "New", "body": "b", "published": True},
            "relationships": {"author": {"data": {"type": "authors", "id": str(self.ada.pk)}}},
        }}
        resp = self.api_post("/api/articles/", doc)
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIn("/api/articles/", resp["Location"])
        body = resp.json()
        self.assertEqual(body["data"]["attributes"]["title"], "New")
        self.assertEqual(body["data"]["relationships"]["author"]["data"]["id"], str(self.ada.pk))
        self.assertTrue(Article.objects.filter(title="New", author=self.ada).exists())

    def test_retrieve(self):
        art = Article.objects.create(title="Hi", author=self.ada)
        resp = self.api_get(f"/api/articles/{art.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["id"], str(art.pk))

    def test_patch_is_partial(self):
        art = Article.objects.create(title="Old", body="keep", author=self.ada)
        doc = {"data": {"type": "articles", "id": str(art.pk), "attributes": {"title": "Newer"}}}
        resp = self.api_patch(f"/api/articles/{art.pk}/", doc)
        self.assertEqual(resp.status_code, 200)
        art.refresh_from_db()
        self.assertEqual(art.title, "Newer")
        self.assertEqual(art.body, "keep")

    def test_patch_id_mismatch_is_400(self):
        art = Article.objects.create(title="X", author=self.ada)
        doc = {"data": {"type": "articles", "id": "999", "attributes": {"title": "Y"}}}
        resp = self.api_patch(f"/api/articles/{art.pk}/", doc)
        self.assertEqual(resp.status_code, 400)

    def test_delete(self):
        art = Article.objects.create(title="Bye", author=self.ada)
        resp = self.api_delete(f"/api/articles/{art.pk}/")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Article.objects.filter(pk=art.pk).exists())
        self.assertEqual(self.api_get(f"/api/articles/{art.pk}/").status_code, 404)
