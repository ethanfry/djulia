def from_header(request):
    """Test-only identity: token-like claims from an X-Test-Scopes header.

    Never trust a raw header like this in production; verify a token instead.
    """
    scopes = request.headers.get("X-Test-Scopes")
    return None if scopes is None else {"sub": "tester", "scope": scopes}


def deny_reads(identity, resource, action, request):
    """A custom policy that also gates reads."""
    return identity is not None
