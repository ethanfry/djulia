from tests.base import JSONAPI, JSONAPITestCase
from tests.testapp.models import Author


class NegotiationTests(JSONAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ada = Author.objects.create(name="Ada")

    def test_wrong_content_type_is_415(self):
        resp = self.client.post("/api/articles/", data="{}",
                                content_type="text/plain", HTTP_ACCEPT=JSONAPI)
        self.assertEqual(resp.status_code, 415)

    def test_form_encoded_body_is_415(self):
        resp = self.client.post("/api/articles/", data="{}",
                                content_type="application/x-www-form-urlencoded",
                                HTTP_ACCEPT=JSONAPI)
        self.assertEqual(resp.status_code, 415)

    def test_plain_json_content_type_is_accepted(self):
        # Passes negotiation; the empty document then fails as a 400.
        resp = self.client.post("/api/articles/", data="{}",
                                content_type="application/json", HTTP_ACCEPT=JSONAPI)
        self.assertEqual(resp.status_code, 400)

    def test_parametrized_content_type_is_415(self):
        resp = self.client.post("/api/articles/", data="{}",
                                content_type=f"{JSONAPI}; version=1", HTTP_ACCEPT=JSONAPI)
        self.assertEqual(resp.status_code, 415)

    def test_utf8_charset_is_ignored(self):
        for content_type in (f"{JSONAPI}; charset=utf-8", "application/json; charset=UTF-8"):
            resp = self.client.post("/api/articles/", data="{}",
                                    content_type=content_type, HTTP_ACCEPT=JSONAPI)
            self.assertEqual(resp.status_code, 400, content_type)

    def test_non_utf8_charset_is_415(self):
        resp = self.client.post("/api/articles/", data="{}",
                                content_type=f"{JSONAPI}; charset=latin-1", HTTP_ACCEPT=JSONAPI)
        self.assertEqual(resp.status_code, 415)

    def test_profile_on_plain_json_is_415(self):
        resp = self.client.post("/api/articles/", data="{}",
                                content_type='application/json; profile="https://example.com/p"',
                                HTTP_ACCEPT=JSONAPI)
        self.assertEqual(resp.status_code, 415)

    def test_parametrized_accept_is_406(self):
        resp = self.client.get("/api/articles/",
                               HTTP_ACCEPT="application/vnd.api+json; version=1")
        self.assertEqual(resp.status_code, 406)

    def test_untyped_body_is_415(self):
        resp = self.client.post("/api/articles/", data="{}", content_type="",
                                HTTP_ACCEPT=JSONAPI)
        self.assertEqual(resp.status_code, 415)

    def test_profile_content_type_is_accepted(self):
        # Passes negotiation; the empty document then fails as a 400.
        resp = self.client.post("/api/articles/", data="{}",
                                content_type=f'{JSONAPI}; profile="https://example.com/p"',
                                HTTP_ACCEPT=JSONAPI)
        self.assertEqual(resp.status_code, 400)

    def test_ext_content_type_is_415(self):
        resp = self.client.post("/api/articles/", data="{}",
                                content_type=f'{JSONAPI}; ext="https://jsonapi.org/ext/atomic"',
                                HTTP_ACCEPT=JSONAPI)
        self.assertEqual(resp.status_code, 415)

    def test_profile_accept_is_ok(self):
        resp = self.client.get("/api/articles/",
                               HTTP_ACCEPT=f'{JSONAPI}; profile="https://example.com/p"')
        self.assertEqual(resp.status_code, 200)

    def test_ext_only_accept_is_406(self):
        resp = self.client.get("/api/articles/",
                               HTTP_ACCEPT=f'{JSONAPI}; ext="https://jsonapi.org/ext/atomic"')
        self.assertEqual(resp.status_code, 406)

    def test_any_usable_accept_instance_is_ok(self):
        resp = self.client.get(
            "/api/articles/",
            HTTP_ACCEPT=f'{JSONAPI}; ext="https://jsonapi.org/ext/atomic", {JSONAPI}')
        self.assertEqual(resp.status_code, 200)
