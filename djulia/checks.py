"""System checks: shown by `runserver` and `manage.py check`, silenced the usual
Django way with ``SILENCED_SYSTEM_CHECKS``."""
from django.core.checks import Error, Info, register
from django.db.models import BinaryField


@register()
def check_resources(app_configs, **kwargs):
    from .registry import api
    messages = []
    for resource in api.all_resources():
        if resource.auto_hidden:
            hidden = ", ".join(f"{name} ({why})" for name, why in resource.auto_hidden.items())
            messages.append(Info(
                f"'{resource.type_name}' hides these columns by default: {hidden}.",
                hint="List a column in the resource's `fields` to expose it.",
                obj=resource.model, id="djulia.I001"))
        for name in resource.attribute_names:
            if isinstance(resource.model._meta.get_field(name), BinaryField):
                messages.append(Error(
                    f"'{resource.type_name}' exposes binary column '{name}', which can't be "
                    "serialized to JSON.",
                    hint="Remove it from `fields`.", obj=resource.model, id="djulia.E001"))
    return messages
