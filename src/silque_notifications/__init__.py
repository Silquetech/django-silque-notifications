"""Silque Notifications Django app.

Admin-driven notifications with Celery/Redis, relational recipients, and templating.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"

default_app_config = "silque_notifications.apps.SilqueNotificationsConfig"

