from django.apps import AppConfig


class GreyLiteratureConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "grey_literature"
    verbose_name = "Grey Literature"

    def ready(self):
        from . import signals  # noqa: F401
