from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from djulia import Resource
from djulia.checks import check_resources
from djulia.registry import APIRegistry
from djulia.resource import looks_sensitive
from tests.base import JSONAPITestCase
from tests.testapp.models import Account, Author


class SensitiveNameTests(SimpleTestCase):
    def test_credential_like_names(self):
        for name in ("password", "password_hash", "passwordHash", "api_key", "apiKey",
                     "client_secret", "refresh_token", "salt", "session_key", "PRIVATE_KEY"):
            self.assertTrue(looks_sensitive(name), name)

    def test_lookalikes_are_not_hidden(self):
        for name in ("tokenizer", "secretary", "description", "keyword", "passage", "username"):
            self.assertFalse(looks_sensitive(name), name)


class DefaultHidingTests(JSONAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(
            username="ada", password_hash="pbkdf2$abc", sessionKey="s3cr3t",
            avatar=b"\x89PNG", tokenizer="basic")

    def test_hidden_columns_are_not_served(self):
        resp = self.api_get(f"/api/accounts/{self.account.pk}/")
        self.assertEqual(resp.status_code, 200)  # the binary column no longer crashes reads
        attributes = resp.json()["data"]["attributes"]
        self.assertEqual(set(attributes), {"username", "tokenizer"})

    def test_hidden_columns_are_not_filterable_or_sortable(self):
        resp = self.api_get("/api/accounts/?filter[password_hash__istartswith]=pbkdf2")
        self.assertEqual(resp.json()["meta"]["count"], 1)  # unknown filter ignored, not applied
        self.assertEqual(self.api_get("/api/accounts/?sort=password_hash").status_code, 400)

    def test_hidden_columns_are_not_writable(self):
        doc = {"data": {"type": "accounts", "attributes": {"password_hash": "x"}}}
        resp = self.api_patch(f"/api/accounts/{self.account.pk}/", doc)
        self.assertEqual(resp.status_code, 400)

    def test_hidden_columns_are_left_out_of_the_schema(self):
        schema = self.client.get("/api/openapi.json").json()
        attributes = schema["components"]["schemas"]["accounts"]["properties"]["attributes"]
        self.assertEqual(set(attributes["properties"]), {"username", "tokenizer"})
        params = {p["name"] for p in schema["paths"]["/accounts/"]["get"]["parameters"]}
        self.assertNotIn("filter[password_hash]", params)


class ExplicitFieldsTests(SimpleTestCase):
    def resource(self, **attrs):
        return type("R", (Resource,), attrs)(APIRegistry(), Account)

    def test_fields_exposes_a_hidden_column(self):
        resource = self.resource(fields=["username", "password_hash"])
        self.assertEqual(resource.attribute_names, ["username", "password_hash"])
        self.assertEqual(resource.auto_hidden, {})

    def test_fields_also_limits_default_filters_and_sorting(self):
        resource = type("R", (Resource,), {"fields": ["name"]})(APIRegistry(), Author)
        self.assertNotIn("email", resource.get_filterset_class().base_filters)
        self.assertNotIn("email", resource.sortable_fields)

    def test_exclude_removes_attributes_and_relationships(self):
        resource = self.resource(exclude=["tokenizer", "owner"])
        self.assertEqual(resource.attribute_names, ["username"])
        self.assertNotIn("owner", resource.relationship_names)

    def test_unknown_exclude_is_an_error(self):
        with self.assertRaises(ImproperlyConfigured):
            self.resource(exclude=["nope"])


class CheckTests(SimpleTestCase):
    def test_reports_hidden_columns(self):
        messages = {m.id: m for m in check_resources(None)}
        info = messages["djulia.I001"]
        self.assertIn("password_hash (looks sensitive)", info.msg)
        self.assertIn("avatar (binary)", info.msg)

    def test_exposed_binary_column_is_an_error(self):
        registry = APIRegistry()
        registry.register(Account, type("R", (Resource,), {"fields": ["username", "avatar"]}))
        from unittest import mock
        with mock.patch("djulia.registry.api", registry):
            ids = [m.id for m in check_resources(None)]
        self.assertIn("djulia.E001", ids)
