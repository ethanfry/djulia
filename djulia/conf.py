from django.conf import settings

DEFAULTS = {
    "PAGE_SIZE": 25,
    "MAX_PAGE_SIZE": 100,
    "AUTODISCOVER_MODULE": "djulia_resources",
    "STRICT_CONTENT_TYPE": True,
    "BROWSABLE": True,
    "OPENAPI_TITLE": "djulia API",
    "OPENAPI_VERSION": "1.0.0",
}


def get_setting(name):
    """Read a djulia setting from the ``DJULIA`` settings dict, or its default."""
    return getattr(settings, "DJULIA", {}).get(name, DEFAULTS[name])
