import json

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.views import View

from . import browsable
from .errors import (BadRequest, Forbidden, JSONAPIError, MEDIA_TYPE, MethodNotAllowed,
                     NotAuthenticated, NotFound, ValidationFailed, error_response)
from .filters import apply_filters, apply_sort, parse_sparse_fields
from .negotiation import check_request
from .pagination import paginate
from .permissions import get_identity
from .serialization import resource_object


def jsonapi_response(document, status=200):
    return HttpResponse(
        json.dumps(document, cls=DjangoJSONEncoder),
        status=status,
        content_type=MEDIA_TYPE,
    )


def render_document(request, document, status=200):
    """Return JSON, or a browsable HTML page when a browser asks for it."""
    if browsable.prefers_html(request):
        return browsable.render_html(request, document, status)
    return jsonapi_response(document, status)


class BaseResourceView(View):
    resource = None

    def dispatch(self, request, *args, **kwargs):
        try:
            check_request(request)
            return super().dispatch(request, *args, **kwargs)
        except JSONAPIError as exc:
            return error_response(exc)

    def http_method_not_allowed(self, request, *args, **kwargs):
        return error_response(
            MethodNotAllowed(f"Method '{request.method}' is not allowed here."))

    def check_permission(self, request, action):
        if self.resource.has_permission(request, action):
            return
        if get_identity(request) is None:
            raise NotAuthenticated("Authentication is required to perform this action.")
        raise Forbidden("You do not have permission to perform this action.")

    def read_document(self, request):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            raise BadRequest("Request body is not valid JSON.")
        if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
            raise BadRequest("Document must have a `data` object.", pointer="/data")
        return body["data"]

    def apply_document(self, instance, data):
        """Write attributes + relationships from a JSON:API document onto ``instance``.

        Returns the list of (spec, pks) to-many assignments to apply after save.
        """
        resource = self.resource
        for name, value in (data.get("attributes") or {}).items():
            if name not in resource.attribute_names:
                raise BadRequest(f"Unknown attribute '{name}'.",
                                 pointer=f"/data/attributes/{name}")
            setattr(instance, name, value)

        deferred = []
        for name, rel in (data.get("relationships") or {}).items():
            spec = resource.relations.get(name)
            if spec is None or name not in resource.relationship_names:
                raise BadRequest(f"Unknown relationship '{name}'.",
                                 pointer=f"/data/relationships/{name}")
            linkage = rel.get("data") if isinstance(rel, dict) else None
            if spec.to_many:
                deferred.append((spec, [item["id"] for item in (linkage or [])]))
            elif not spec.forward:
                raise BadRequest(f"Relationship '{name}' is read-only.",
                                 pointer=f"/data/relationships/{name}")
            elif linkage is None:
                setattr(instance, spec.name, None)
            else:
                setattr(instance, f"{spec.name}_id", linkage["id"])
        return deferred

    def save(self, instance, deferred):
        try:
            instance.full_clean(exclude=[spec.name for spec, _ in deferred])
        except ValidationError as exc:
            raise _validation_error(exc)
        instance.save()
        for spec, pks in deferred:
            getattr(instance, spec.accessor).set(pks)


class ResourceListView(BaseResourceView):
    def get(self, request, *args, **kwargs):
        self.check_permission(request, "list")
        qs = self.resource.get_queryset(request)
        qs = apply_filters(qs, self.resource, request)
        qs = apply_sort(qs, self.resource, request)
        objects, links, meta = paginate(qs, request)
        sparse = parse_sparse_fields(request)
        data = [resource_object(obj, self.resource, sparse) for obj in objects]
        return render_document(request, {"data": data, "links": links, "meta": meta})

    def post(self, request, *args, **kwargs):
        self.check_permission(request, "create")
        data = self.read_document(request)
        instance = self.resource.model()
        self.save(instance, self.apply_document(instance, data))
        sparse = parse_sparse_fields(request)
        response = render_document(
            request, {"data": resource_object(instance, self.resource, sparse)}, status=201)
        response["Location"] = f"{request.path}{instance.pk}/"
        return response


class ResourceDetailView(BaseResourceView):
    def get_object(self, request, pk):
        try:
            return self.resource.get_queryset(request).get(pk=pk)
        except (ObjectDoesNotExist, ValueError, TypeError):
            raise NotFound(f"No {self.resource.type_name} with id '{pk}'.")

    def get(self, request, pk, *args, **kwargs):
        self.check_permission(request, "retrieve")
        instance = self.get_object(request, pk)
        sparse = parse_sparse_fields(request)
        return render_document(request, {"data": resource_object(instance, self.resource, sparse)})

    def patch(self, request, pk, *args, **kwargs):
        self.check_permission(request, "update")
        instance = self.get_object(request, pk)
        data = self.read_document(request)
        if "id" in data and str(data["id"]) != str(pk):
            raise BadRequest("`id` in the document does not match the URL.", pointer="/data/id")
        self.save(instance, self.apply_document(instance, data))
        sparse = parse_sparse_fields(request)
        return render_document(request, {"data": resource_object(instance, self.resource, sparse)})

    def delete(self, request, pk, *args, **kwargs):
        self.check_permission(request, "delete")
        self.get_object(request, pk).delete()
        return HttpResponse(status=204)


def _validation_error(exc):
    errors = []
    if hasattr(exc, "message_dict"):
        for field, messages in exc.message_dict.items():
            pointer = "/data" if field == "__all__" else f"/data/attributes/{field}"
            errors.extend(ValidationFailed(m, pointer=pointer) for m in messages)
    else:
        errors = [ValidationFailed(m) for m in exc.messages]
    wrapper = ValidationFailed("Validation failed.")
    wrapper.errors = errors or [ValidationFailed("Validation failed.")]
    return wrapper
