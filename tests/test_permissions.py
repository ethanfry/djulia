from tests.base import JSONAPITestCase
from tests.testapp.models import Widget


class PermissionTests(JSONAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.visible = Widget.objects.create(name="Shown", visible=True)
        cls.hidden = Widget.objects.create(name="Hidden", visible=False)

    def test_get_queryset_scopes_list(self):
        body = self.api_get("/api/widgets/").json()
        self.assertEqual(body["meta"]["count"], 1)
        self.assertEqual(body["data"][0]["id"], str(self.visible.pk))

    def test_get_queryset_hides_detail(self):
        self.assertEqual(self.api_get(f"/api/widgets/{self.hidden.pk}/").status_code, 404)

    def test_has_permission_denies_delete(self):
        resp = self.api_delete(f"/api/widgets/{self.visible.pk}/")
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Widget.objects.filter(pk=self.visible.pk).exists())

    def test_allowed_action_works(self):
        self.assertEqual(self.api_get("/api/widgets/").status_code, 200)
