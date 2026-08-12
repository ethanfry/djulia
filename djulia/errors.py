import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse

MEDIA_TYPE = "application/vnd.api+json"


class JSONAPIError(Exception):
    """A single JSON:API error, renderable as an error object.

    Instances may also carry a list of sub-errors on ``.errors`` (used when one
    logical failure maps to several field-level errors, e.g. validation).
    """

    status = 500
    title = "Internal Server Error"

    def __init__(self, detail=None, *, pointer=None, parameter=None, code=None,
                 title=None, status=None):
        self.detail = detail
        self.pointer = pointer
        self.parameter = parameter
        self.code = code
        self.errors = None
        if title is not None:
            self.title = title
        if status is not None:
            self.status = status
        super().__init__(detail or self.title)

    def as_error_object(self):
        obj = {"status": str(self.status), "title": self.title}
        if self.detail:
            obj["detail"] = str(self.detail)
        if self.code:
            obj["code"] = self.code
        source = {}
        if self.pointer:
            source["pointer"] = self.pointer
        if self.parameter:
            source["parameter"] = self.parameter
        if source:
            obj["source"] = source
        return obj


class BadRequest(JSONAPIError):
    status, title = 400, "Bad Request"


class Forbidden(JSONAPIError):
    status, title = 403, "Forbidden"


class NotFound(JSONAPIError):
    status, title = 404, "Not Found"


class MethodNotAllowed(JSONAPIError):
    status, title = 405, "Method Not Allowed"


class NotAcceptable(JSONAPIError):
    status, title = 406, "Not Acceptable"


class UnsupportedMediaType(JSONAPIError):
    status, title = 415, "Unsupported Media Type"


class ValidationFailed(JSONAPIError):
    status, title = 422, "Validation Error"


def error_response(error):
    """Render a ``JSONAPIError`` (or a list of them) as an ``{"errors": [...]}`` document."""
    if isinstance(error, JSONAPIError) and error.errors:
        errors = error.errors
    elif isinstance(error, (list, tuple)):
        errors = error
    else:
        errors = [error]
    status = errors[0].status
    body = {"errors": [e.as_error_object() for e in errors]}
    return HttpResponse(
        json.dumps(body, cls=DjangoJSONEncoder),
        status=status,
        content_type=MEDIA_TYPE,
    )
