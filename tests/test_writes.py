import uuid

from django.db.models.signals import m2m_changed

from tests.base import JSONAPITestCase
from tests.testapp.models import Article, Author, Currency, Tag


class WriteTestCase(JSONAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ada = Author.objects.create(name="Ada")
        cls.tag = Tag.objects.create(label="t")

    def article(self, relationships=None, **data):
        rels = {"author": {"data": {"type": "authors", "id": str(self.ada.pk)}}}
        rels.update(relationships or {})
        return {"data": {"type": "articles", "attributes": {"title": "x"},
                         "relationships": rels, **data}}

    def assertError(self, resp, status, pointer):
        self.assertEqual(resp.status_code, status, resp.content)
        self.assertEqual(resp.json()["errors"][0]["source"]["pointer"], pointer)


class AtomicityTests(WriteTestCase):
    def fail_on_tags(self, sender, action, **kwargs):
        if action == "pre_add":
            raise RuntimeError("link failed")

    def setUp(self):
        m2m_changed.connect(self.fail_on_tags, sender=Article.tags.through)
        self.addCleanup(m2m_changed.disconnect, self.fail_on_tags, sender=Article.tags.through)

    def test_failed_link_rolls_back_create(self):
        doc = self.article({"tags": {"data": [{"type": "tags", "id": str(self.tag.pk)}]}})
        with self.assertRaises(RuntimeError):
            self.api_post("/api/articles/", doc)
        self.assertFalse(Article.objects.exists())

    def test_failed_link_rolls_back_update(self):
        art = Article.objects.create(title="old", author=self.ada)
        doc = {"data": {"type": "articles", "id": str(art.pk), "attributes": {"title": "new"},
                        "relationships": {"tags": {"data": [{"type": "tags",
                                                              "id": str(self.tag.pk)}]}}}}
        with self.assertRaises(RuntimeError):
            self.api_patch(f"/api/articles/{art.pk}/", doc)
        art.refresh_from_db()
        self.assertEqual(art.title, "old")


class DocumentShapeTests(WriteTestCase):
    def test_attributes_must_be_an_object(self):
        resp = self.api_post("/api/articles/", {"data": {"type": "articles", "attributes": "x"}})
        self.assertError(resp, 400, "/data/attributes")

    def test_relationships_must_be_an_object(self):
        resp = self.api_post("/api/articles/", {"data": {"type": "articles", "relationships": []}})
        self.assertError(resp, 400, "/data/relationships")

    def test_relationship_needs_data_member(self):
        art = Article.objects.create(title="t", author=self.ada)
        art.tags.set([self.tag])
        doc = {"data": {"type": "articles", "relationships": {"tags": "nope"}}}
        resp = self.api_patch(f"/api/articles/{art.pk}/", doc)
        self.assertError(resp, 400, "/data/relationships/tags")
        self.assertEqual(list(art.tags.all()), [self.tag])  # not silently cleared

    def test_identifier_needs_type_and_id(self):
        resp = self.api_post("/api/articles/", self.article({"author": {"data": {"type": "authors"}}}))
        self.assertError(resp, 400, "/data/relationships/author/data")
        resp = self.api_post("/api/articles/", self.article({"tags": {"data": [{"id": "1"}]}}))
        self.assertError(resp, 400, "/data/relationships/tags/data/0")

    def test_to_many_needs_a_list(self):
        doc = self.article({"tags": {"data": {"type": "tags", "id": str(self.tag.pk)}}})
        self.assertError(self.api_post("/api/articles/", doc), 400, "/data/relationships/tags/data")


class RelatedIdTests(WriteTestCase):
    def test_missing_to_many_id_is_422_and_saves_nothing(self):
        doc = self.article({"tags": {"data": [{"type": "tags", "id": str(self.tag.pk)},
                                              {"type": "tags", "id": "999"}]}})
        self.assertError(self.api_post("/api/articles/", doc), 422,
                         "/data/relationships/tags/data/1/id")
        self.assertFalse(Article.objects.exists())

    def test_malformed_to_many_id_is_422(self):
        doc = self.article({"tags": {"data": [{"type": "tags", "id": "abc"}]}})
        self.assertError(self.api_post("/api/articles/", doc), 422,
                         "/data/relationships/tags/data/0/id")

    def test_missing_to_one_id_points_at_relationship(self):
        doc = self.article({"author": {"data": {"type": "authors", "id": "999"}}})
        self.assertError(self.api_post("/api/articles/", doc), 422, "/data/relationships/author")

    def test_valid_to_many_is_set(self):
        doc = self.article({"tags": {"data": [{"type": "tags", "id": str(self.tag.pk)}]}})
        resp = self.api_post("/api/articles/", doc)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(list(Article.objects.get().tags.all()), [self.tag])

    def test_reverse_many_to_many_is_writable(self):
        art = Article.objects.create(title="t", author=self.ada)
        doc = {"data": {"type": "tags", "attributes": {"label": "new"},
                        "relationships": {"articles": {"data": [{"type": "articles",
                                                                  "id": str(art.pk)}]}}}}
        self.assertEqual(self.api_post("/api/tags/", doc).status_code, 201)
        self.assertEqual(art.tags.get().label, "new")


class TypeAndIdTests(WriteTestCase):
    def test_wrong_document_type_is_409(self):
        self.assertError(self.api_post("/api/articles/", self.article(type="authors")),
                         409, "/data/type")

    def test_missing_document_type_is_accepted(self):
        doc = self.article()
        del doc["data"]["type"]
        self.assertEqual(self.api_post("/api/articles/", doc).status_code, 201)

    def test_wrong_identifier_type_is_409(self):
        doc = self.article({"author": {"data": {"type": "tags", "id": str(self.tag.pk)}}})
        self.assertError(self.api_post("/api/articles/", doc), 409,
                         "/data/relationships/author/data/type")



class ReadOnlyTests(WriteTestCase):
    def test_unchanged_read_only_values_are_ignored_on_update(self):
        art = Article.objects.create(title="t", author=self.ada)
        sent_back = self.api_get(f"/api/articles/{art.pk}/").json()["data"]
        sent_back["attributes"]["title"] = "edited"
        resp = self.api_patch(f"/api/articles/{art.pk}/", {"data": sent_back})
        self.assertEqual(resp.status_code, 200, resp.content)
        art.refresh_from_db()
        self.assertEqual(art.title, "edited")

    def test_unchanged_read_only_relationship_is_ignored_on_update(self):
        Article.objects.create(title="t", author=self.ada)
        sent_back = self.api_get(f"/api/authors/{self.ada.pk}/").json()["data"]
        sent_back["attributes"]["name"] = "Ada L."
        resp = self.api_patch(f"/api/authors/{self.ada.pk}/", {"data": sent_back})
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_changing_read_only_attribute_is_403(self):
        art = Article.objects.create(title="t", author=self.ada)
        created = art.created
        doc = {"data": {"type": "articles", "attributes": {"created": "2000-01-01T00:00:00Z"}}}
        self.assertError(self.api_patch(f"/api/articles/{art.pk}/", doc), 403,
                         "/data/attributes/created")
        art.refresh_from_db()
        self.assertEqual(art.created, created)

    def test_read_only_attribute_on_create_is_403(self):
        doc = self.article(attributes={"title": "x", "created": "2000-01-01T00:00:00Z"})
        self.assertError(self.api_post("/api/articles/", doc), 403, "/data/attributes/created")

    def test_changing_read_only_relationship_is_403(self):
        art = Article.objects.create(title="t", author=self.ada)
        doc = {"data": {"type": "authors", "attributes": {"name": "B"},
                        "relationships": {"articles": {"data": [{"type": "articles",
                                                                  "id": str(art.pk)}]}}}}
        self.assertError(self.api_post("/api/authors/", doc), 403,
                         "/data/relationships/articles")
        self.assertFalse(Author.objects.filter(name="B").exists())

    def test_openapi_marks_read_only(self):
        schema = self.client.get("/api/openapi.json").json()["components"]["schemas"]
        articles = schema["articles"]["properties"]
        self.assertTrue(articles["attributes"]["properties"]["created"]["readOnly"])
        self.assertNotIn("readOnly", articles["attributes"]["properties"]["title"])
        self.assertTrue(articles["id"]["readOnly"])
        self.assertNotIn("readOnly", schema["currencies"]["properties"]["id"])
        authors = schema["authors"]["properties"]
        self.assertTrue(authors["relationships"]["properties"]["articles"]["readOnly"])


class ClientIdTests(JSONAPITestCase):
    def test_auto_increment_id_is_403(self):
        doc = {"data": {"type": "tags", "id": "123", "attributes": {"label": "x"}}}
        resp = self.api_post("/api/tags/", doc)
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Tag.objects.exists())

    def test_natural_key_requires_id(self):
        doc = {"data": {"type": "currencies", "attributes": {"name": "Euro"}}}
        self.assertEqual(self.api_post("/api/currencies/", doc).status_code, 422)
        doc["data"]["id"] = "EUR"
        resp = self.api_post("/api/currencies/", doc)
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["data"]["id"], "EUR")
        self.assertTrue(resp["Location"].endswith("/api/currencies/EUR/"))

    def test_existing_client_id_is_409_and_not_overwritten(self):
        Currency.objects.create(code="EUR", name="Euro")
        doc = {"data": {"type": "currencies", "id": "EUR", "attributes": {"name": "Other"}}}
        resp = self.api_post("/api/currencies/", doc)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(Currency.objects.get().name, "Euro")

    def test_defaulted_key_accepts_or_generates_id(self):
        chosen = str(uuid.uuid4())
        doc = {"data": {"type": "tokens", "id": chosen, "attributes": {"label": "a"}}}
        self.assertEqual(self.api_post("/api/tokens/", doc).json()["data"]["id"], chosen)
        doc = {"data": {"type": "tokens", "attributes": {"label": "b"}}}
        resp = self.api_post("/api/tokens/", doc)
        self.assertEqual(resp.status_code, 201)
        self.assertNotEqual(resp.json()["data"]["id"], chosen)

    def test_malformed_client_id_is_422(self):
        doc = {"data": {"type": "tokens", "id": "not-a-uuid", "attributes": {"label": "a"}}}
        resp = self.api_post("/api/tokens/", doc)
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["errors"][0]["source"]["pointer"], "/data/id")
