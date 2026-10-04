from .errors import MEDIA_TYPE, NotAcceptable, UnsupportedMediaType

# The only media type parameters JSON:API 1.1 allows. djulia supports no
# extensions, so any `ext` is unsupported; profiles are accepted and ignored.
ALLOWED_PARAMS = {"ext", "profile"}

# Plain JSON bodies are accepted too: hand-written clients default to it, and it
# needs a CORS preflight just like the JSON:API type, so it costs no CSRF safety.
BODY_TYPES = {MEDIA_TYPE, "application/json"}


def _parse(media_type):
    """Split ``type/subtype; a=1; b="2"`` into ``("type/subtype", {"a": "1", "b": "2"})``."""
    base, *params = media_type.split(";")
    parsed = {}
    for param in params:
        name, _, value = param.partition("=")
        parsed[name.strip().lower()] = value.strip().strip('"')
    return base.strip().lower(), parsed


def _supported(params):
    return set(params) <= ALLOWED_PARAMS and "ext" not in params


def check_request(request):
    """Enforce JSON:API 1.1 content negotiation, leniently where it's harmless.

    - A request with a body must declare the JSON:API media type or
      ``application/json`` (else 415), so an untyped or form-encoded cross-site
      body can't slip through to the JSON parser.
    - ``charset=utf-8`` is ignored (some HTTP libraries always add it). Beyond
      that, only the JSON:API type's ``profile`` parameter is accepted; ``ext``
      names an extension djulia doesn't support (else 415).
    - If ``Accept`` lists the JSON:API media type but no instance of it is
      usable (other parameters, or an unsupported ``ext``), respond 406.
    """
    if request.body:
        base, params = _parse(request.META.get("CONTENT_TYPE", ""))
        if base not in BODY_TYPES:
            raise UnsupportedMediaType(
                f"Request bodies must be sent with 'Content-Type: {MEDIA_TYPE}' "
                "(or 'application/json').")
        if params.pop("charset", "utf-8").lower() != "utf-8":
            raise UnsupportedMediaType("Request bodies must be UTF-8.")
        if params and (base != MEDIA_TYPE or not _supported(params)):
            raise UnsupportedMediaType(
                f"Unsupported Content-Type parameters {sorted(params)}: only "
                f"`profile` on '{MEDIA_TYPE}' is accepted, and no extensions are supported.")

    accept = request.META.get("HTTP_ACCEPT", "")
    instances = [params for base, params in map(_parse, accept.split(",")) if base == MEDIA_TYPE]
    if instances and not any(_supported(params) for params in instances):
        raise NotAcceptable(
            "No acceptable instance of the JSON:API media type in Accept; "
            "only a `profile` parameter is supported.")
