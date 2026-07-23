from django.apps import AppConfig


class JournalapisConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "journalApis"
    verbose_name = "Journal Tables"

    def ready(self):
        from . import signals  # noqa: F401
