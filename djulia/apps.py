from django.apps import AppConfig


class DjuliaConfig(AppConfig):
    name = "djulia"
    verbose_name = "djulia JSON:API"

    def ready(self):
        from django.utils.module_loading import autodiscover_modules
        from .conf import get_setting
        autodiscover_modules(get_setting("AUTODISCOVER_MODULE"))
