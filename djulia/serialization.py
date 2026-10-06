"""Turn model instances into JSON:API resource objects and identifiers.

The two primitives are ``resource_object`` (full ``type``/``id``/``attributes``/
``relationships``) and ``resource_identifier`` (the ``type``/``id`` linkage stub).
``resource_object`` composes the identifier for each relationship.
"""


def resource_identifier(instance, resource):
    return {"type": resource.type_name, "id": str(instance.pk)}


def resource_object(instance, resource, sparse=None):
    type_name = resource.type_name
    allowed = sparse.get(type_name) if sparse else None

    obj = {"type": type_name, "id": str(instance.pk), "attributes": {}}
    for name in resource.attribute_names:
        if allowed is not None and name not in allowed:
            continue
        obj["attributes"][name] = getattr(instance, name)

    relationships = {}
    for name in resource.relationship_names:
        if allowed is not None and name not in allowed:
            continue
        spec = resource.relations.get(name)
        if spec is None:
            continue
        relationships[name] = {"data": linkage(instance, spec, resource.registry)}
    if relationships:
        obj["relationships"] = relationships
    return obj


def linkage(instance, spec, registry):
    if spec.to_many:
        manager = getattr(instance, spec.accessor)
        return [_ident(o, spec.related_model, registry) for o in manager.all()]
    related = getattr(instance, spec.accessor, None)
    if related is None:
        return None
    return _ident(related, spec.related_model, registry)


def _ident(obj, model, registry):
    resource = registry.for_model(model)
    type_name = resource.type_name if resource is not None else registry.type_name_for_model(model)
    return {"type": type_name, "id": str(obj.pk)}
