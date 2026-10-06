import json

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import router, transaction
from django.http import HttpResponse
from django.views import View

from . import browsable
from .errors import (BadRequest, Conflict, Forbidden, JSONAPIError, MEDIA_TYPE,
                     MethodNotAllowed, NotAuthenticated, NotFound, ValidationFailed,
                     error_response)
from .filters import apply_filters, apply_sort, parse_sparse_fields
from .negotiation import check_request
from .pagination import paginate
from .permissions import get_identity
from .serialization import linkage, resource_object


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

    def read_document(self, request, pk=None):
        """Parse and shape-check the request document; ``pk`` is the URL id on update."""
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            raise BadRequest("Request body is not valid JSON.")
        if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
            raise BadRequest("Document must have a `data` object.", pointer="/data")
        data = body["data"]
        # A missing `type` is fine (the URL already says it); a wrong one is a client bug.
        type_name = self.resource.type_name
        if "type" in data and data["type"] != type_name:
            raise Conflict(f"Expected type '{type_name}', got {data['type']!r}.",
                           pointer="/data/type")
        if pk is not None and "id" in data and str(data["id"]) != str(pk):
            raise Conflict("`id` in the document does not match the URL.", pointer="/data/id")
        for member in ("attributes", "relationships"):
            if not isinstance(data.get(member, {}), dict):
                raise BadRequest(f"`{member}` must be an object.", pointer=f"/data/{member}")
        return data

    def apply_client_id(self, instance, data):
        """Set a client-generated ``id`` on a new instance, if its primary key allows one."""
        resource, model = self.resource, self.resource.model
        if "id" not in data:
            if resource.client_id == "required":
                raise ValidationFailed(f"An `id` is required to create {resource.type_name}.",
                                       pointer="/data")
            return
        if resource.client_id == "forbidden":
            raise Forbidden("Client-generated ids are not supported.", pointer="/data/id")
        try:
            pk = model._meta.pk.to_python(data["id"])
        except ValidationError as exc:
            raise ValidationFailed(exc.messages[0], pointer="/data/id")
        if model._default_manager.filter(pk=pk).exists():
            raise Conflict(f"{resource.type_name} with id '{data['id']}' already exists.",
                           pointer="/data/id")
        instance.pk = pk

    def apply_document(self, instance, data, creating=False):
        """Write attributes + relationships from a JSON:API document onto ``instance``.

        Returns the list of (spec, pks) to-many assignments to apply after save.
        Every related id is checked here, so a bad one fails before anything is saved.
        A read-only value sent back unchanged on update is ignored, since clients
        may send the whole object they received; trying to change one is a 403.
        """
        resource = self.resource
        for name, value in data.get("attributes", {}).items():
            pointer = f"/data/attributes/{name}"
            if name not in resource.attribute_names:
                raise BadRequest(f"Unknown attribute '{name}'.", pointer=pointer)
            if name not in resource.writable_attributes:
                if not creating and _as_sent(getattr(instance, name)) == _as_sent(value):
                    continue
                raise Forbidden(f"Attribute '{name}' is read-only.", pointer=pointer)
            setattr(instance, name, value)

        deferred = []
        for name, rel in data.get("relationships", {}).items():
            pointer = f"/data/relationships/{name}"
            spec = resource.relations.get(name)
            if spec is None or name not in resource.relationship_names:
                raise BadRequest(f"Unknown relationship '{name}'.", pointer=pointer)
            if not spec.writable:
                if not creating and isinstance(rel, dict) and _same_linkage(
                        rel.get("data"), linkage(instance, spec, resource.registry)):
                    continue
                raise Forbidden(f"Relationship '{name}' is read-only.", pointer=pointer)
            if not isinstance(rel, dict) or "data" not in rel:
                raise BadRequest(f"Relationship '{name}' must be an object with a `data` member.",
                                 pointer=pointer)
            target, pointer = rel["data"], f"{pointer}/data"
            if spec.to_many:
                if not isinstance(target, list):
                    raise BadRequest(f"Relationship '{name}' takes a list of resource identifiers.",
                                     pointer=pointer)
                ids = [self.linked_id(spec, item, f"{pointer}/{i}")
                       for i, item in enumerate(target)]
                deferred.append((spec, self.existing_pks(spec, ids, pointer)))
            elif target is None:
                setattr(instance, spec.name, None)
            else:
                # Existence and id format are checked by full_clean in save().
                setattr(instance, f"{spec.name}_id", self.linked_id(spec, target, pointer))
        return deferred

    def linked_id(self, spec, identifier, pointer):
        """Check one resource identifier against ``spec`` and return its id."""
        if not isinstance(identifier, dict) or "type" not in identifier or "id" not in identifier:
            raise BadRequest("A resource identifier needs `type` and `id`.", pointer=pointer)
        expected = self.resource.registry.type_name_for_model(spec.related_model)
        if identifier["type"] != expected:
            raise Conflict(f"Expected type '{expected}', got {identifier['type']!r}.",
                           pointer=f"{pointer}/type")
        return identifier["id"]

    def existing_pks(self, spec, ids, pointer):
        """Convert to-many ids to primary keys, failing with a 422 if any don't exist."""
        model = spec.related_model
        pks = []
        for i, raw in enumerate(ids):
            try:
                pks.append(model._meta.pk.to_python(raw))
            except ValidationError as exc:
                raise ValidationFailed(exc.messages[0], pointer=f"{pointer}/{i}/id")
        found = model._default_manager.in_bulk(pks)
        for i, pk in enumerate(pks):
            if pk not in found:
                type_name = self.resource.registry.type_name_for_model(model)
                raise ValidationFailed(f"No {type_name} with id '{ids[i]}'.",
                                       pointer=f"{pointer}/{i}/id")
        return pks

    def save(self, instance, deferred, creating=False):
        try:
            instance.full_clean(exclude=[spec.name for spec, _ in deferred])
        except ValidationError as exc:
            raise _validation_error(exc, self.resource)
        # The row and its to-many links are saved together or not at all.
        with transaction.atomic(using=router.db_for_write(type(instance))):
            # force_insert: with a client-supplied pk, save() would otherwise
            # UPDATE an existing row rather than fail.
            instance.save(force_insert=creating)
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
        self.apply_client_id(instance, data)
        self.save(instance, self.apply_document(instance, data, creating=True), creating=True)
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
        data = self.read_document(request, pk)
        self.save(instance, self.apply_document(instance, data))
        sparse = parse_sparse_fields(request)
        return render_document(request, {"data": resource_object(instance, self.resource, sparse)})

    def delete(self, request, pk, *args, **kwargs):
        self.check_permission(request, "delete")
        self.get_object(request, pk).delete()
        return HttpResponse(status=204)


def _as_sent(value):
    """``value`` as it appears in a response (e.g. datetimes rounded to milliseconds)."""
    return json.dumps(value, cls=DjangoJSONEncoder, sort_keys=True)


def _same_linkage(incoming, current):
    """Whether submitted linkage matches the current one, ignoring to-many order."""
    def key(ident):
        if isinstance(ident, dict):
            return (str(ident.get("type")), str(ident.get("id")))
        return ("", repr(ident))
    if isinstance(current, list):
        return isinstance(incoming, list) and sorted(map(key, incoming)) == sorted(map(key, current))
    if current is None or incoming is None:
        return incoming is current
    return key(incoming) == key(current)


def _validation_error(exc, resource):
    errors = []
    if hasattr(exc, "message_dict"):
        for field, messages in exc.message_dict.items():
            if field == "__all__":
                pointer = "/data"
            elif field in resource.relations:
                pointer = f"/data/relationships/{field}"
            else:
                pointer = f"/data/attributes/{field}"
            errors.extend(ValidationFailed(m, pointer=pointer) for m in messages)
    else:
        errors = [ValidationFailed(m) for m in exc.messages]
    wrapper = ValidationFailed("Validation failed.")
    wrapper.errors = errors or [ValidationFailed("Validation failed.")]
    return wrapper
