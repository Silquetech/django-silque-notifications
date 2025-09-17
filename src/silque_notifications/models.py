from django.db import models, transaction, router
from django.db import IntegrityError

from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from silque_notifications.services import NotificationService
# from silque.models import Notification, ErrorLog

# Detect Celery availability without importing the module directly
try:
    import importlib.util as _importlib_util
    celery_available = _importlib_util.find_spec('celery') is not None
except Exception:
    celery_available = False


class EmailRecipient(models.Model):
    class Meta:
        verbose_name = _("Email Recipient")
        verbose_name_plural = _("Email Recipients")

    by_docfield = models.CharField(
        max_length=255, verbose_name=_("By Document Field"),
        blank=True, null=True
    )

    by_email = models.EmailField(
        verbose_name=_("By Email"), blank=True,
        null=True
    )

    created = models.DateTimeField(
        verbose_name=_("Created"), blank=True, 
        null=True
    )

    updated = models.DateTimeField(
        verbose_name=_("Last Updated"), blank=True, 
        null=True
    )

    def save(self, *args, **kwargs):
        if not self.pk:  # New instance
            self.created = timezone.now()
        
        self.updated = timezone.now()
        super(EmailRecipient, self).save(*args, **kwargs)

class NumberRecipient(models.Model):
    class Meta:
        verbose_name = _("Number Recipient")
        verbose_name_plural = _("Number Recipients")

    by_docfield = models.CharField(
        max_length=255, verbose_name=_("By Document Field"),
        blank=True, null=True
    )

    by_number = models.CharField(
        max_length=255, verbose_name=_("By Number"), blank=True,
        null=True
    )

    created = models.DateTimeField(
        verbose_name=_("Created"), blank=True, 
        null=True
    )

    updated = models.DateTimeField(
        verbose_name=_("Last Updated"), blank=True, 
        null=True
    )

    def save(self, *args, **kwargs):
        if not self.pk:  # New instance
            self.created = timezone.now()
        
        self.updated = timezone.now()
        super(NumberRecipient, self).save(*args, **kwargs)

class Notification(models.Model):
    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")

    is_active = models.BooleanField(
        default=True, verbose_name=_("Is Active")
    )
        
    CHANNELS = (
        ("E", "Email"),
        ("S", "SMS"),
        ("W", "Whatsapp"),
    )

    channel = models.CharField(
        max_length=1, verbose_name=_("Channel"),
        choices=CHANNELS, default=CHANNELS[0][0]
    )

    email_recipients = models.ManyToManyField(
        EmailRecipient, verbose_name=_("Email Recipients"),
        blank=True
    )

    number_recipients = models.ManyToManyField(
        NumberRecipient, verbose_name=_("Number Recipients"),
        blank=True
    )

    title = models.CharField(
        max_length=255, verbose_name=_("Title")
    )

    message = models.TextField(
        verbose_name=_("Message")
    )

    model = models.CharField(
        max_length=255, verbose_name=_("Model")
    )

    ALERT_OPTIONS = (
        ("N", "New"), # When a new object is created
        ("U", "Update"), # When an object is updated
        ("V", "Value Change"), # When a value is changed
        ("D", "Delete"), # When an object is deleted

        ("B", "Days Before"),
        ("A", "Days After")
    )

    send_alert_on = models.CharField(
        max_length=1, choices=ALERT_OPTIONS,
        default=ALERT_OPTIONS[0][0], verbose_name=_("Send Alert On")
    )

    value_change_field = models.CharField(
        max_length=255, verbose_name=_("Value Change Field"),
        blank=True, null=True
    )

    date_field = models.CharField(
        max_length=255, verbose_name=_("Day Field"),
        blank=True, null=True
    )

    alert_days = models.IntegerField(
        verbose_name=_("Alert Days"), null=True,
        blank=True
    )

    conditions = models.TextField(
        verbose_name=_("Conditions"), null=True,
        blank=True
    )

    created = models.DateTimeField(
        verbose_name=_("Created"), blank=True, 
        null=True
    )

    updated = models.DateTimeField(
        verbose_name=_("Last Updated"), blank=True, 
        null=True
    )

    def clean(self):
        """Model-level validation mirroring form rules for robustness in all entry points."""
        from django.core.exceptions import ValidationError

        errors = {}
        # Alert dependencies
        if self.send_alert_on in ['B', 'A']:
            if not self.date_field:
                errors['date_field'] = 'This field is required for Days Before/After.'
            if self.alert_days in [None, '']:
                errors['alert_days'] = 'This field is required for Days Before/After.'
            else:
                try:
                    if int(self.alert_days) < 0:
                        errors['alert_days'] = 'Alert days must be zero or a positive number.'
                except (TypeError, ValueError):
                    errors['alert_days'] = 'Alert days must be a valid integer.'
        if self.send_alert_on == 'V':
            if not self.value_change_field:
                errors['value_change_field'] = 'This field is required for Value Change.'

        # Channel recipients - only enforce on updates (pk present) due to M2M timing
        if self.channel == 'E' and self.pk:
            if self.email_recipients.count() == 0:
                errors['email_recipients'] = 'At least one email recipient is required for Email channel.'
        if self.channel in ['S', 'W'] and self.pk:
            if self.number_recipients.count() == 0:
                errors['number_recipients'] = 'At least one number recipient is required for SMS or Whatsapp channel.'

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Validate before saving to enforce invariants outside admin
        self.full_clean()

        if not self.pk:  # New instance
            self.created = timezone.now()
        
        self.updated = timezone.now()
        super(Notification, self).save(*args, **kwargs)

    def __str__(self):
        return self.title

class NotificationModel(models.Model):
    """Abstract marker base for models that should trigger notifications.

    Signals (registered in apps.ready) handle pre_save/post_save/post_delete to
    gather and enqueue notifications in a transaction-safe way. This base class
    only serves as a semantic marker; no brittle save_base overrides.
    """

    # Marker used by signal filter to detect subclasses without importing here
    _silque_notifications_marker = True

    class Meta:
        abstract = True
