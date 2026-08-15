from tests.base import JSONAPI, JSONAPITestCase
from tests.testapp.models import Author


class ErrorTests(JSONAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ada = Author.objects.create(name="Ada")

    def test_404_shape(self):
        resp = self.api_get("/api/articles/999999/")
        self.assertEqual(resp.status_code, 404)
        err = resp.json()["errors"][0]
        self.assertEqual(err["status"], "404")
        self.assertEqual(err["title"], "Not Found")

    def test_validation_error_has_pointer(self):
        doc = {"data": {
            "type": "articles",
            "attributes": {"title": ""},  # required -> fails full_clean
            "relationships": {"author": {"data": {"type": "authors", "id": str(self.ada.pk)}}},
        }}
        resp = self.api_post("/api/articles/", doc)
        self.assertEqual(resp.status_code, 422)
        pointers = [e.get("source", {}).get("pointer") for e in resp.json()["errors"]]
        self.assertIn("/data/attributes/title", pointers)

    def test_malformed_json_is_400(self):
        resp = self.client.post("/api/articles/", data="{not json",
                                content_type=JSONAPI, HTTP_ACCEPT=JSONAPI)
        self.assertEqual(resp.status_code, 400)

    def test_missing_data_member_is_400(self):
        resp = self.api_post("/api/articles/", {"nope": 1})
        self.assertEqual(resp.status_code, 400)
