import json

from django.test import TestCase

JSONAPI = "application/vnd.api+json"


class JSONAPITestCase(TestCase):
    """TestCase with helpers that speak the JSON:API media type."""

    def api_get(self, path, **extra):
        return self.client.get(path, HTTP_ACCEPT=JSONAPI, **extra)

    def api_post(self, path, document, **extra):
        return self.client.post(path, data=json.dumps(document),
                                content_type=JSONAPI, HTTP_ACCEPT=JSONAPI, **extra)

    def api_patch(self, path, document, **extra):
        return self.client.patch(path, data=json.dumps(document),
                                 content_type=JSONAPI, HTTP_ACCEPT=JSONAPI, **extra)

    def api_delete(self, path, **extra):
        return self.client.delete(path, HTTP_ACCEPT=JSONAPI, **extra)
