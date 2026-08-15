from tests.base import JSONAPI, JSONAPITestCase
from tests.testapp.models import Author


class NegotiationTests(JSONAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ada = Author.objects.create(name="Ada")

    def test_wrong_content_type_is_415(self):
        resp = self.client.post("/api/articles/", data="{}",
                                content_type="application/json", HTTP_ACCEPT=JSONAPI)
        self.assertEqual(resp.status_code, 415)

    def test_parametrized_content_type_is_415(self):
        resp = self.client.post("/api/articles/", data="{}",
                                content_type="application/vnd.api+json; charset=utf-8",
                                HTTP_ACCEPT=JSONAPI)
        self.assertEqual(resp.status_code, 415)

    def test_parametrized_accept_is_406(self):
        resp = self.client.get("/api/articles/",
                               HTTP_ACCEPT="application/vnd.api+json; version=1")
        self.assertEqual(resp.status_code, 406)
