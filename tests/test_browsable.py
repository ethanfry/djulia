from django.test import TestCase, override_settings

from tests.testapp.models import Article, Author


class BrowsableTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ada = Author.objects.create(name="Ada")
        Article.objects.create(title="Hello", author=cls.ada)

    def test_browser_gets_html_with_data(self):
        resp = self.client.get("/api/articles/", HTTP_ACCEPT="text/html")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp["content-type"])
        self.assertIn("Hello", resp.content.decode())

    def test_format_json_overrides_accept(self):
        resp = self.client.get("/api/articles/?format=json", HTTP_ACCEPT="text/html")
        self.assertIn("application/vnd.api+json", resp["content-type"])

    @override_settings(DJULIA={"BROWSABLE": False})
    def test_browsable_can_be_disabled(self):
        resp = self.client.get("/api/articles/", HTTP_ACCEPT="text/html")
        self.assertIn("application/vnd.api+json", resp["content-type"])
