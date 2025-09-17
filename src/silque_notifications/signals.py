from __future__ import annotations

from django.apps import apps
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Notification

# Detect Celery availability without importing it eagerly each time
try:
    import importlib.util as _importlib_util
    _celery_available = _importlib_util.find_spec('celery') is not None
except Exception:
    _celery_available = False


def _is_notification_model_instance(instance) -> bool:
    try:
        # Avoid hard import-cycle: dynamically resolve base abstract class
        NotificationModel = apps.get_model('silque_notifications', 'NotificationModel')  # type: ignore[attr-defined]
    except Exception:
        # The abstract model isn't a real DB model; fallback to attribute flag
        NotificationModel = None
    # Use duck-typing: any model that defines _silque_notifications_marker = True is considered
    return getattr(instance.__class__, '_silque_notifications_marker', False)


@receiver(pre_save)
def _silque_pre_save(sender, instance, **kwargs):  # noqa: D401
    """Capture old instance before save for NotificationModel subclasses."""
    if getattr(kwargs, 'raw', False):  # skip fixtures
        return
    # Quick reject for non-app models
    if not _is_notification_model_instance(instance):
        return
    # Stash old object for comparison; safe read if pk exists
    try:
        instance._old_obj = sender.objects.get(pk=instance.pk) if instance.pk else None
    except Exception:
        instance._old_obj = None


def _gather_valid_notifications(instance, created: bool):
    # Build model label string exactly like stored in Notification.model
    model_label = f"{instance._meta.app_label} ~ {instance._meta.object_name} ~ {instance._meta.verbose_name}"
    qs = Notification.objects.filter(model=model_label, is_active=True)
    if created:
        return list(qs.filter(send_alert_on='N'))
    # updated
    valids = list(qs.filter(send_alert_on='U'))
    # value-change: inspect value_change_field against _old_obj
    old_obj = getattr(instance, '_old_obj', None)
    if old_obj is not None:
        for notif in qs.filter(send_alert_on='V'):
            try:
                field = (notif.value_change_field or '').split(' ~ ')[0]
                if field and getattr(old_obj, field) != getattr(instance, field):
                    valids.append(notif)
            except Exception:
                # Keep silent; optional debug log can be added via settings flag
                pass
    return valids


def _enqueue_notifications(old_obj_data: dict | None, new_obj_data: dict | None, notification_ids: list[int]):
    if not _celery_available or not notification_ids:
        return
    try:
        from .tasks import send_notification_task
        transaction.on_commit(lambda: send_notification_task.delay(old_obj_data, new_obj_data, notification_ids))
    except Exception:
        # Best-effort: do not break save/delete
        pass


@receiver(post_save)
def _silque_post_save(sender, instance, created, **kwargs):
    if getattr(kwargs, 'raw', False):
        return
    if not _is_notification_model_instance(instance):
        return
    try:
        valid = _gather_valid_notifications(instance, created)
        if not valid:
            return
        # Serialize references for task
        old_obj = getattr(instance, '_old_obj', None)
        old_obj_data = None
        if old_obj is not None:
            old_obj_data = {
                'app_label': old_obj._meta.app_label,
                'model_name': old_obj._meta.model_name,
                'pk': old_obj.pk,
            }
        new_obj_data = {
            'app_label': instance._meta.app_label,
            'model_name': instance._meta.model_name,
            'pk': instance.pk,
        }
        _enqueue_notifications(old_obj_data, new_obj_data, [n.id for n in valid])
    finally:
        # Cleanup to avoid leaking references
        if hasattr(instance, '_old_obj'):
            try:
                delattr(instance, '_old_obj')
            except Exception:
                pass


@receiver(post_delete)
def _silque_post_delete(sender, instance, **kwargs):
    if getattr(kwargs, 'raw', False):
        return
    if not _is_notification_model_instance(instance):
        return
    # Gather delete notifications
    try:
        model_label = f"{instance._meta.app_label} ~ {instance._meta.object_name} ~ {instance._meta.verbose_name}"
        valids = list(Notification.objects.filter(model=model_label, is_active=True, send_alert_on='D'))
        if not valids:
            return
        new_obj_data = {
            'app_label': instance._meta.app_label,
            'model_name': instance._meta.model_name,
            'pk': instance.pk,
        }
        _enqueue_notifications(None, new_obj_data, [n.id for n in valids])
    except Exception:
        # Best-effort
        pass


# Optional: react to M2M edits if you need notifications for relationship changes.
# Example skeleton (disabled by default):
# @receiver(m2m_changed)
# def _silque_m2m_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
#     if not _is_notification_model_instance(instance):
#         return
#     # Implement custom logic based on action (post_add/post_remove/post_clear)
#     pass
