import random
import string
import uuid
from re import fullmatch as re_fullmatch

from django.apps import apps
from django.conf import settings
from django.db import models
from django.db.models import Max
from django.utils import timezone

try:
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse
    
EmailConfiguration = None

def generate_incremental_docname(model_class, owner_account, prefix):
    current_year = str(timezone.now().year)
   
    # Get latest docname for this owner
    latest = model_class.objects.filter(
        owner_account=owner_account,
        docname__startswith=f"{prefix}-{current_year}"
    ).aggregate(Max('docname'))['docname__max']
    
    if latest:
        # Extract number from latest docname
        latest_number = int(latest.split('-')[-1])
        new_number = latest_number + 1
    else:
        new_number = 1
        
    return f"{prefix}-{current_year}-{str(new_number).zfill(5)}"

def generate_docname(model_class, prefix=None, digits=8):
    def generate():
        generated = ''.join(random.choices(string.ascii_uppercase + string.digits, k=digits))
        return f"{prefix}-{generated}" if prefix else generated
    
    generated = generate()
    while model_class.objects.filter(docname=generated):
        generated = generate()
    
    return generated


def generate_n_digit_uuid(n=8):
    full_uuid = uuid.uuid4()
    short_uuid = str(full_uuid)[:n]    # Fab→Fahad 2024-10-09: should we use upper case for doc names ?

    return short_uuid

def get_configuration_admin_url():
    meta = EmailConfiguration._meta
    return reverse(f'admin:{meta.app_label}_{meta.model_name}_change')

def get_notification_models():
    return [model for model in apps.get_models() if type.mro(model)[1].__name__ == 'NotificationModel']

def get_notification_models_with_app_label():
    return [f"{model._meta.app_label} ~ {model._meta.object_name} ~ {model._meta.verbose_name}" for model in apps.get_models() if 'NotificationModel' in [_class.__name__ for _class in type.mro(model)]]

def get_model_fields(app_label, model):
    return [f"{field.name} ~ {field.verbose_name}" for field in apps.get_model(app_label, model)._meta.fields]
 
def get_model_date_fields(app_label, model):
    return [f"{field.name} ~ {field.verbose_name}" for field in apps.get_model(app_label, model)._meta.fields if type(field).mro()[0].__name__ in ['DateTimeField', 'DateField']]

def get_model_relational_recipients(app_label, model, for_email):
    """
    S_NOTIFICATION_RELATIONAL_EMAIL_RECIPIENTS = {
        # "app_label.model": fields list
        "supplier.Supplier": ["email_address"],
        "employee.Employee": ["email_address"],

        #                   "employee.email_address" will be prioritized over "supplier.email_address"
        "silque_user.User": [("employee.email_address", "supplier.email_address")]
    }

    S_NOTIFICATION_RELATIONAL_NUMBER_RECIPIENTS = {
        # "app_label.model": fields list
        "supplier.Supplier": ["mobile_number"],
        "employee.Employee": ["mobile_number"],

        #                   "employee.mobile_number" will be prioritized over "supplier.mobile_number"
        "silque_user.User": [("employee.mobile_number", "supplier.mobile_number")]
    }
    """
    recipients = []

    if for_email:
        notification_relational_recipients = getattr(settings, "S_NOTIFICATION_RELATIONAL_EMAIL_RECIPIENTS", None)
        heuristic_fields = ["email", "email_address"]
    else:
        notification_relational_recipients = getattr(settings, "S_NOTIFICATION_RELATIONAL_NUMBER_RECIPIENTS", None)
        heuristic_fields = [
            "mobile_number", "phone", "phone_number", "mobile", "contact_number",
        ]

    _model = apps.get_model(app_label, model)

    # 1) Include direct fields on the selected model itself (e.g. doc.email / old_doc.email)
    try:
        model_field_names = {f.name: f for f in _model._meta.fields}
        for name in heuristic_fields:
            if name in model_field_names:
                verbose_model = _model._meta.verbose_name
                verbose_field = getattr(model_field_names[name], 'verbose_name', name)
                recipients.append(f"doc.{name} ~ This {verbose_model} {verbose_field}")
                recipients.append(f"old_doc.{name} ~ Old {verbose_model} {verbose_field}")
    except Exception:
        # Be resilient; direct-field suggestions are best-effort
        pass

    # 2) Suggest relational paths via FK/O2O fields when likely recipient fields exist on related models
    for field in _model._meta.fields:
        if isinstance(field, models.ForeignKey) or isinstance(field, models.OneToOneField):
            field_model = field.remote_field.model
            field_model_str = f"{field_model._meta.app_label}.{field_model._meta.object_name}"

            # If mapping provided, show suggestions for only mapped models
            if notification_relational_recipients and field_model_str in notification_relational_recipients:
                recipients.append(f"silque.doc.{field.name}.{field_model_str} ~ New {field.verbose_name}")
                recipients.append(f"silque.old_doc.{field.name}.{field_model_str} ~ Old {field.verbose_name}")
            # Otherwise, use heuristics: if related model has any likely field, still suggest
            elif not notification_relational_recipients:
                related_field_names = {f.name for f in field_model._meta.fields}
                if any(name in related_field_names for name in heuristic_fields):
                    recipients.append(f"silque.doc.{field.name}.{field_model_str} ~ New {field.verbose_name}")
                    recipients.append(f"silque.old_doc.{field.name}.{field_model_str} ~ Old {field.verbose_name}")

    return recipients

def validate_email(email):
    regex = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}"

    if re_fullmatch(regex, email):
        return True
 
    else:
        return False

__all__ = [
    'get_configuration_admin_url', 'get_notification_models', 
    'get_notification_models_with_app_label', 'get_model_fields',
    'get_model_date_fields'
]