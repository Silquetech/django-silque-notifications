"""
Celery tasks for the notification system.
"""
from celery import shared_task
from django.conf import settings
import traceback
import logging

logger = logging.getLogger('silque_notifications')


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_task(self, old_obj_data, new_obj_data, valid_notifications_data):
    """
    Celery task to process notifications asynchronously.
    
    Args:
        old_obj_data: Serialized old object data (dict or None)
        new_obj_data: Serialized new object data (dict)
        valid_notifications_data: List of notification data
    """
    try:
        from .services import NotificationService
        from .models import Notification
        from django.apps import apps
        
        # Reconstruct objects from serialized data
        if old_obj_data:
            app_label = old_obj_data['app_label']
            model_name = old_obj_data['model_name']
            pk = old_obj_data['pk']
            try:
                model_class = apps.get_model(app_label, model_name)
                old_obj = model_class.objects.get(pk=pk)
            except Exception:
                old_obj = None
        else:
            old_obj = None
            
        app_label = new_obj_data['app_label']
        model_name = new_obj_data['model_name']
        pk = new_obj_data['pk']
        model_class = apps.get_model(app_label, model_name)
        new_obj = model_class.objects.get(pk=pk)
        
        # Reconstruct notifications
        notification_ids = valid_notifications_data
        valid_notifications = Notification.objects.filter(id__in=notification_ids)
        
        # Process notifications
        notification_service = NotificationService(old_obj, new_obj, valid_notifications)
        notification_service.send_notifications()
        
    except Exception as exc:
        # Log error and retry without depending on ErrorLog
        logger.exception("[CELERY-NOTIFICATION-TASK] Task failed")
        # Retry the task
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, subject, message, recipients, html_message=None):
    """
    Celery task to send emails asynchronously.
    """
    try:
        from .services import EmailService
        email_service = EmailService()
        email_service.send_mail(subject, message, recipients, html_message)
        
    except Exception as exc:
        logger.exception("[CELERY-EMAIL-TASK] Email task failed")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_sms_task(self, receiver_list, message, sender_name='', success_msg=True):
    """
    Celery task to send SMS asynchronously.
    """
    try:
        from .services import SMSService
        sms_service = SMSService()
        sms_service.send_sms(receiver_list, message, sender_name, success_msg)
        
    except Exception as exc:
        logger.exception("[CELERY-SMS-TASK] SMS task failed")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_whatsapp_task(self, recipients_list, message):
    """
    Celery task to send WhatsApp messages asynchronously.
    """
    try:
        from .services import WhatsappService
        whatsapp_service = WhatsappService()
        whatsapp_service.send_whatsapp_message(recipients_list, message)
        
    except Exception as exc:
        logger.exception("[CELERY-WHATSAPP-TASK] WhatsApp task failed")
        raise self.retry(exc=exc)
