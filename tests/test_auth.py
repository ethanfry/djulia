from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, override_settings

from djulia import Resource
from djulia.registry import APIRegistry
from tests.base import JSONAPITestCase
from tests.testapp.models import Author

IDENTITY = "tests.identity.from_header"
NEW_AUTHOR = {"data": {"type": "authors", "attributes": {"name": "Bo"}}}


def policy(name):
    return override_settings(DJULIA={"PERMISSION": name, "IDENTITY": IDENTITY})


class DefaultPolicyTests(JSONAPITestCase):
    @override_settings(DJULIA={"IDENTITY": IDENTITY})
    def test_default_is_read_only(self):
        self.assertEqual(self.api_get("/api/authors/").status_code, 200)
        resp = self.api_post("/api/authors/", NEW_AUTHOR, HTTP_X_TEST_SCOPES="authors:write")
        self.assertEqual(resp.status_code, 403)

    @override_settings(DJULIA={})
    def test_default_identity_without_auth_middleware_is_anonymous(self):
        resp = self.api_post("/api/authors/", NEW_AUTHOR)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp["WWW-Authenticate"], "Bearer")
        self.assertEqual(resp.json()["errors"][0]["status"], "401")


class PresetTests(JSONAPITestCase):
    @policy("authenticated")
    def test_authenticated(self):
        self.assertEqual(self.api_post("/api/authors/", NEW_AUTHOR).status_code, 401)
        resp = self.api_post("/api/authors/", NEW_AUTHOR, HTTP_X_TEST_SCOPES="")
        self.assertEqual(resp.status_code, 201)

    @policy("scopes")
    def test_scopes_needs_type_write_scope(self):
        self.assertEqual(self.api_get("/api/authors/").status_code, 200)
        self.assertEqual(self.api_post("/api/authors/", NEW_AUTHOR).status_code, 401)
        wrong = self.api_post("/api/authors/", NEW_AUTHOR, HTTP_X_TEST_SCOPES="articles:write")
        self.assertEqual(wrong.status_code, 403)
        right = self.api_post("/api/authors/", NEW_AUTHOR,
                              HTTP_X_TEST_SCOPES="openid authors:write")
        self.assertEqual(right.status_code, 201)

    @policy("scopes")
    def test_scopes_covers_update_and_delete(self):
        ada = Author.objects.create(name="Ada")
        patch = {"data": {"type": "authors", "id": str(ada.pk), "attributes": {"name": "A"}}}
        self.assertEqual(self.api_patch(f"/api/authors/{ada.pk}/", patch,
                                        HTTP_X_TEST_SCOPES="authors:write").status_code, 200)
        self.assertEqual(self.api_delete(f"/api/authors/{ada.pk}/",
                                         HTTP_X_TEST_SCOPES="authors:write").status_code, 204)

    @policy("allow_all")
    def test_allow_all(self):
        self.assertEqual(self.api_post("/api/authors/", NEW_AUTHOR).status_code, 201)

    @policy("tests.identity.deny_reads")
    def test_custom_policy_can_gate_reads(self):
        self.assertEqual(self.api_get("/api/authors/").status_code, 401)
        self.assertEqual(self.api_get("/api/authors/", HTTP_X_TEST_SCOPES="").status_code, 200)

    @policy("nonsense")
    def test_unknown_preset_is_improperly_configured(self):
        with self.assertRaises(ImproperlyConfigured):
            self.api_get("/api/authors/")


class ScopeClaimTests(JSONAPITestCase):
    def check(self, claims, resource_class=Resource):
        resource = resource_class(APIRegistry(), Author)
        request = RequestFactory().post("/")
        request._djulia_identity = claims
        return resource.has_permission(request, "create")

    @override_settings(DJULIA={"PERMISSION": "scopes"})
    def test_scp_list_claim(self):
        self.assertTrue(self.check({"scp": ["authors:write"]}))
        self.assertFalse(self.check({"scp": ["authors:read"]}))

    @override_settings(DJULIA={"PERMISSION": "read_only"})
    def test_per_resource_permission_overrides_project(self):
        class OpenAuthors(Resource):
            permission = "authenticated"

        self.assertFalse(self.check({"sub": "x"}))
        self.assertTrue(self.check({"sub": "x"}, OpenAuthors))
