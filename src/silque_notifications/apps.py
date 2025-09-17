from django.apps import AppConfig


class SilqueNotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'silque_notifications'

    def ready(self):
        # Import signal handlers
        from . import signals  # noqa: F401
