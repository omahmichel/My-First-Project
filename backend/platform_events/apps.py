from django.apps import AppConfig

class PlatformEventsConfig(AppConfig):
    name = 'platform_events'
    default_auto_field = 'django.db.models.BigAutoField'
    def ready(self):
        from . import signals  # noqa: F401
        from .capture import install_log_handlers
        install_log_handlers()
