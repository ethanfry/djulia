from django.test import TestCase


class OpenAPITests(TestCase):
    def test_schema_paths_types_and_params(self):
        resp = self.client.get("/api/openapi.json")
        self.assertEqual(resp.status_code, 200)
        spec = resp.json()
        self.assertEqual(spec["openapi"], "3.0.3")
        self.assertIn("/articles/", spec["paths"])
        self.assertIn("/articles/{id}/", spec["paths"])
        self.assertIn("articles", spec["components"]["schemas"])

        attrs = spec["components"]["schemas"]["articles"]["properties"]["attributes"]["properties"]
        self.assertEqual(attrs["published"]["type"], "boolean")
        self.assertEqual(attrs["created"]["format"], "date-time")

        params = [p["name"] for p in spec["paths"]["/articles/"]["get"]["parameters"]]
        self.assertIn("filter[title__icontains]", params)
        self.assertIn("sort", params)

    def test_swagger_ui_served(self):
        resp = self.client.get("/api/docs/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp["content-type"])
        self.assertIn("swagger-ui", resp.content.decode())
