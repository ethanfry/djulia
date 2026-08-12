from .conf import get_setting
from .errors import MEDIA_TYPE, NotAcceptable, UnsupportedMediaType


def _base(media_type):
    return media_type.split(";")[0].strip()


def check_request(request):
    """Enforce JSON:API content negotiation (spec sections on Content-Type/Accept).

    - A request body ``Content-Type`` of the JSON:API media type MUST carry no
      media-type parameters (else 415).
    - If ``Accept`` mentions the JSON:API media type and *every* instance is
      parameterised, the server MUST respond 406.
    """
    if not get_setting("STRICT_CONTENT_TYPE"):
        return

    content_type = request.META.get("CONTENT_TYPE", "")
    if request.method in ("POST", "PATCH") and content_type:
        if _base(content_type) == MEDIA_TYPE and ";" in content_type:
            raise UnsupportedMediaType("The JSON:API media type must not carry parameters.")
        if _base(content_type) != MEDIA_TYPE:
            raise UnsupportedMediaType(f"Expected Content-Type '{MEDIA_TYPE}'.")

    accept = request.META.get("HTTP_ACCEPT", "")
    if accept:
        matches = [a.strip() for a in accept.split(",") if _base(a) == MEDIA_TYPE]
        if matches and all(";" in a for a in matches):
            raise NotAcceptable("The JSON:API media type must not carry parameters.")
