"""Who is calling (identity) and what they may do (policy).

djulia never verifies credentials. An identity function turns a request into
whatever your auth layer produced (a user, a dict of verified token claims, a
service name) or ``None`` for an anonymous caller. A policy then decides each
action. The built-in policies only gate writes; reads stay public. A custom
policy is called for reads too, so it can restrict them.
"""
from functools import lru_cache

from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from .conf import get_setting

READ_ACTIONS = {"list", "retrieve"}


def default_identity(request):
    """The logged-in Django user, when there is one (e.g. a session cookie)."""
    user = getattr(request, "user", None)  # absent without AuthenticationMiddleware
    return user if user is not None and user.is_authenticated else None


def get_identity(request):
    """Resolve the caller once per request with the ``IDENTITY`` setting."""
    if not hasattr(request, "_djulia_identity"):
        path = get_setting("IDENTITY")
        func = _import(path, "IDENTITY") if path else default_identity
        request._djulia_identity = func(request)
    return request._djulia_identity


def get_scopes(identity):
    """Granted scopes from token claims: OAuth's space-separated ``scope``, or ``scp``."""
    if not isinstance(identity, dict):
        return set()
    granted = identity.get("scope", identity.get("scp", ()))
    return set(granted.split() if isinstance(granted, str) else granted)


def read_only(identity, resource, action, request):
    return action in READ_ACTIONS


def authenticated(identity, resource, action, request):
    return action in READ_ACTIONS or identity is not None


def scopes(identity, resource, action, request):
    """Writes need ``<type>:write``, e.g. ``articles:write``."""
    return action in READ_ACTIONS or f"{resource.type_name}:write" in get_scopes(identity)


def allow_all(identity, resource, action, request):
    return True


PRESETS = {
    "read_only": read_only,
    "authenticated": authenticated,
    "scopes": scopes,
    "allow_all": allow_all,
}


def get_policy(name):
    """A preset by name, or a ``check(identity, resource, action, request)`` by dotted path."""
    if name in PRESETS:
        return PRESETS[name]
    if "." not in name:
        raise ImproperlyConfigured(
            f"Unknown permission policy {name!r}: use one of {sorted(PRESETS)} "
            "or a dotted path to a function.")
    return _import(name, "PERMISSION")


@lru_cache(maxsize=None)
def _import(path, setting):
    try:
        return import_string(path)
    except ImportError as exc:
        raise ImproperlyConfigured(f"DJULIA[{setting!r}] could not import {path!r}: {exc}")
