import json
import traceback

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import HttpResponseNotFound, HttpResponseRedirect, JsonResponse
from django.template import loader
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from .helpers import get_model_date_fields as get_model_date_fields_helper
from .helpers import get_model_fields as get_model_fields_helper
from .helpers import get_model_relational_recipients as get_model_relational_recipients_helper
from .helpers import get_notification_models_with_app_label
from .models import EmailRecipient, Notification, NumberRecipient

# Optional integrations with external 'silque' project. Provide safe fallbacks
# so this app remains shippable and works independently.
try:
    from silque.helpers import get_configuration_admin_url as _get_config_url  # type: ignore
except Exception:
    from django.urls import reverse

    def _get_config_url():
        return reverse('admin:index')

try:
    from silque.models import EmailConfiguration as _EmailConfiguration  # type: ignore
except Exception:
    _EmailConfiguration = None

try:
    from silque.models import File as _File  # type: ignore
except Exception:
    _File = None

try:
    from silque.templatetags.core_tags import has_group as _has_group  # type: ignore
except Exception:
    def _has_group(user, group_name):
        return False

try:
    from silque.view_responses import invalid_field_provided as _invalid_field  # type: ignore
except Exception:
    def _invalid_field(name):
        return JsonResponse({
            'status': 'E',
            'error': f'Invalid {name}',
            'message': ''
        })

subject = getattr(settings, 'S_EMAIL_TEST_SUBJECT', _("Test Email"))
text_template = getattr(settings, 'S_EMAIL_TEST_TEXT_TEMPLATE', "email/test_email.txt")
html_template = getattr(settings, 'S_EMAIL_TEST_HTML_TEMPLATE', None)
# Do not render templates at import time; render on demand inside the view.
# Note: optional integrations handled via safe fallbacks defined above


@require_http_methods(["POST"])
def send_test_email(request):

    if request.user is None or not request.user.is_staff:
        return HttpResponseNotFound()

    email = request.POST.get('email', None)
    if _EmailConfiguration is None:
        return JsonResponse({
            'status': 'E',
            'error': 'Email configuration unavailable',
            'message': 'EmailConfiguration model not installed.'
        })
    config = _EmailConfiguration.get_solo()

    if email:
        try:
            # Render templates safely at request time; fall back to plain text if missing
            try:
                message_text = loader.render_to_string(text_template)
            except Exception:
                message_text = "This is a test email from the system."

            message_html = None
            if html_template:
                try:
                    message_html = loader.render_to_string(html_template)
                except Exception:
                    message_html = None

            send_mail(
                subject,
                message_text,
                config.from_email or None,
                [email],
                html_message = message_html)

            messages.success(request,
                 _("Test email sent. Please check \"{}\" for a "
                 "message with the subject \"{}\"").format(
                    email,
                    subject
                )
            )
        except Exception as e:
            messages.error(request, _("Could not send email. {}").format(e))
    else:
        messages.error(request, _("You must provide an email address to test with."))

    return HttpResponseRedirect(_get_config_url())

def create_recipients(channel, valid_recipients):
    try:
        _valid_recipients = {}
        recipient_objects = []

        if channel in ["E", "S", "W"]:
            if channel == "E":
                for recipient in valid_recipients:
                    if valid_recipients[recipient]["by_docfield"] or valid_recipients[recipient]["by_email"]:
                        try:
                            recipient_id = int(recipient)
                            email_recipient = EmailRecipient.objects.get(id=recipient_id)
                            email_recipient.by_docfield = valid_recipients[recipient]["by_docfield"]
                            email_recipient.by_email = valid_recipients[recipient]["by_email"]
                            email_recipient.save()

                            recipient_objects.append(email_recipient)

                            _valid_recipients[email_recipient.id] = {
                                "by_docfield": email_recipient.by_docfield,
                                "by_email": email_recipient.by_email,
                                "saved": True
                            }

                        except:
                            email_recipient = EmailRecipient.objects.create(
                                by_docfield = valid_recipients[recipient]["by_docfield"],
                                by_email = valid_recipients[recipient]["by_email"]
                            )

                            recipient_objects.append(email_recipient)

                            _valid_recipients[email_recipient.id] = {
                                "by_docfield": email_recipient.by_docfield,
                                "by_email": email_recipient.by_email,
                                "saved": True
                            }

            else:
                for recipient in valid_recipients:
                    if valid_recipients[recipient]["by_docfield"] or valid_recipients[recipient]["by_number"]:
                        try:
                            recipient_id = int(recipient)
                            number_recipient = NumberRecipient.objects.get(id=recipient_id)
                            number_recipient.by_docfield = valid_recipients[recipient]["by_docfield"]
                            number_recipient.by_number = valid_recipients[recipient]["by_number"]
                            number_recipient.save()

                            recipient_objects.append(number_recipient)

                            _valid_recipients[number_recipient.id] = {
                                "by_docfield": number_recipient.by_docfield,
                                "by_number": number_recipient.by_number,
                                "saved": True
                            }

                        except:
                            number_recipient = NumberRecipient.objects.create(
                                by_docfield = valid_recipients[recipient]["by_docfield"],
                                by_number = valid_recipients[recipient]["by_number"]
                            )

                            recipient_objects.append(number_recipient)

                            _valid_recipients[number_recipient.id] = {
                                "by_docfield": number_recipient.by_docfield,
                                "by_number": number_recipient.by_number,
                                "saved": True
                            }
            
            if recipient_objects:
                return ["S", recipient_objects, _valid_recipients]

            else:
                return ["E", JsonResponse({
                    "status": "E",
                    "error": "Recipient fields are empty!",
                    "message": "You can't submit an empty recipients table."
                })]

        else:
            return ["E", JsonResponse({
                "status": "E",
                "error": "Invalid channel selected!",
                "message": "The channel must be one of 'Email', 'SMS', 'Whatsapp'."
            })]

    except Exception as e:
        return ["E", JsonResponse({
            "status": "E",
            "error": f"An unknown error has occured: {str(e)}",
            "message": f"An unknown error has occured while creating recipients:\n\n{traceback.format_exc()}"
        })]

@login_required
@require_http_methods(["POST",])
def get_model_fields(request):
    try:
        if request.user.is_superuser:
            model = request.POST.get("model", None)

            if model:
                split_model = model.split(' ~ ')
                fields = get_model_fields_helper(split_model[0], split_model[1])

                if fields:
                    return JsonResponse({
                        "status": "S",
                        "fields": fields
                    })

                else:
                    return JsonResponse({
                        "status": "E",
                        "error": "No fields found!",
                        "message": "This is odd but the model you selected has no usabled fields, M2M are not yet supported."
                    })

            else:
                return JsonResponse({
                    "status": "E",
                    "error": "Insufficient Data!",
                    "message": "A model is required to proceed with this POST request."
                })

        else:
            return JsonResponse({
                "status": "E",
                "error": "You're not a superuser!",
                "message": "Only superusers are allowed to create notifications."
            })

    except Exception as e:
        return JsonResponse({
            "status": "E",
            "error": f"An unknown error has occured: {str(e)}",
            "message": f"An unknown error has occured while fetching model fields:\n\n{traceback.format_exc()}"
        })

@login_required
@require_http_methods(["POST",])
def get_model_date_fields(request):
    try:
        if request.user.is_superuser:
            model = request.POST.get("model", None)

            if model:
                split_model = model.split(' ~ ')
                fields = get_model_date_fields_helper(split_model[0], split_model[1])

                if fields:
                    return JsonResponse({
                        "status": "S",
                        "fields": fields
                    })

                else:
                    return JsonResponse({
                        "status": "E",
                        "error": "No fields found!",
                        "message": "This is odd but the model you selected has no usabled fields, M2M are not yet supported."
                    })

            else:
                return JsonResponse({
                    "status": "E",
                    "error": "Insufficient Data!",
                    "message": "A model is required to proceed with this POST request."
                })

        else:
            return JsonResponse({
                "status": "E",
                "error": "You're not a superuser!",
                "message": "Only superusers are allowed to create notifications."
            })

    except Exception as e:
        return JsonResponse({
            "status": "E",
            "error": f"An unknown error has occured: {str(e)}",
            "message": f"An unknown error has occured while fetching model fields:\n\n{traceback.format_exc()}"
        })

@login_required
@require_http_methods(["POST",])
def get_model_relational_recipients(request):
    try:
        if request.user.is_superuser:
            model = request.POST.get("model", None)
            for_email = request.POST.get("for_email", None)

            for_email = for_email == "true" if for_email else False

            if model:
                split_model = model.split(' ~ ')
                fields = get_model_relational_recipients_helper(split_model[0], split_model[1], for_email)

                if fields:
                    return JsonResponse({
                        "status": "S",
                        "fields": fields
                    })

                else:
                    return JsonResponse({
                        "status": "E",
                        "empty": True
                    })

            else:
                return JsonResponse({
                    "status": "E",
                    "error": "Insufficient Data!",
                    "message": "A model is required to proceed with this POST request."
                })

        else:
            return JsonResponse({
                "status": "E",
                "error": "You're not a superuser!",
                "message": "Only superusers are allowed to create notifications."
            })

    except Exception as e:
        return JsonResponse({
            "status": "E",
            "error": f"An unknown error has occured: {str(e)}",
            "message": f"An unknown error has occured while fetching relation recipients:\n\n{traceback.format_exc()}"
        })

@login_required
@require_http_methods(["POST",])
def save_notification(request):
    try:
        if request.user.is_superuser:
            doc_id = request.POST.get('doc_id', None)
            is_active = request.POST.get('is_active', None)
            title = request.POST.get('title', None)
            message = request.POST.get('message', None)
            channel = request.POST.get('channel', None)
            valid_recipients = request.POST.get('valid_recipients', None)

            model = request.POST.get('model', None)
            send_alert_on = request.POST.get('send_alert_on', None)
            value_change_field = request.POST.get('value_change_field', None)
            date_field = request.POST.get('date_field', None)
            alert_days = request.POST.get('alert_days', None)

            conditions = request.POST.get('conditions', None)

            notification = None

            if not title:
                return JsonResponse({
                    "status": "E",
                    "error": "No title provided!",
                    "message": "The title field is mandatory."
                })

            if not channel:
                return JsonResponse({
                    "status": "E",
                    "error": "No channel provided!",
                    "message": "The channel field is mandatory."
                })

            if not message:
                return JsonResponse({
                    "status": "E",
                    "error": "No message provided!",
                    "message": "The message field is mandatory."
                })

            if is_active == None:
                return JsonResponse({
                    "status": "E",
                    "error": "No is_active state provided!",
                    "message": "The is_active field is mandatory."
                })
                
            else:
                is_active = is_active == "true"

            if not model:
                return JsonResponse({
                    "status": "E",
                    "error": "No model provided!",
                    "message": "The model field is mandatory."
                })

            elif model not in get_notification_models_with_app_label():
                return JsonResponse({
                    "status": "E",
                    "error": "Invalid model provided!",
                    "message": "The Model you provided is an invalid option and not in the usable models list."
                })

            if not send_alert_on:
                return JsonResponse({
                    "status": "E",
                    "error": "No Event Trigger provided!",
                    "message": "The 'Send Alert On' field is mandatory."
                })

            elif send_alert_on not in ['N', 'U', 'V', 'D', 'B', 'A']:
                return JsonResponse({
                    "status": "E",
                    "error": "Invalid Event Trigger provided!",
                    "message": "The 'Send Alert On' field you prived in not an available option."
                })

            elif send_alert_on == "V":
                if not value_change_field:
                    return JsonResponse({
                        "status": "E",
                        "error": "No 'Value Change Field' provided!",
                        "message": "The 'Value Change Field' field is mandatory."
                    })

                elif value_change_field not in get_model_fields_helper(model.split(' ~ ')[0], model.split(' ~ ')[1]):
                    return JsonResponse({
                        "status": "E",
                        "error": "Invalid 'Value Change Field' provided!",
                        "message": "The 'Value Change Field' field you provided is not a valid field for the model you selected."
                    })

            elif send_alert_on in ["B", "A"]:
                if not date_field:
                    return JsonResponse({
                        "status": "E",
                        "error": "No 'Date Field' provided!",
                        "message": "The 'Date Field' field is mandatory."
                    })

                elif date_field not in get_model_date_fields_helper(model.split(' ~ ')[0], model.split(' ~ ')[1]):
                    return JsonResponse({
                        "status": "E",
                        "error": "Invalid 'Date Field' provided!",
                        "message": "The 'Date Field' field you provided is not a valid field for the model you selected."
                    })

                if not alert_days:
                    return JsonResponse({
                        "status": "E",
                        "error": "No 'Alert Days' provided!",
                        "message": "The 'Alery Days' field is mandatory."
                    })

                else:
                    try:
                        alert_days = int(alert_days)

                    except:
                        return JsonResponse({
                            "status": "E",
                            "error": "Invalid 'Alert Days' provided!",
                            "message": "The 'Alert Days' field you provided is not a valid number."
                        })

            if valid_recipients:
                valid_recipients = json.loads(valid_recipients)
            
            else:
                return JsonResponse({
                    "status": "E",
                    "error": "No recipients added!",
                    "message": "Recipients are mandatory in order to save/create a notification."
                })

            if doc_id:
                try:
                    notification = Notification.objects.get(id=int(doc_id))
                    notification.is_active = is_active
                    notification.title = title
                    notification.message = message
                    notification.channel = channel
                    notification.model = model
                    notification.send_alert_on = send_alert_on
                    notification.value_change_field = value_change_field
                    notification.date_field = date_field
                    notification.alert_days = alert_days
                    notification.conditions = conditions
                    notification.save()
                            
                except:
                    return JsonResponse({
                        "status": "E",
                        "error": "Invalid Doc ID!",
                        "message": "The server has received an invalid doc_id with this POST request. Reload the page and try again or contact support."
                    })

            else:
                notification = Notification.objects.create(
                    title = title,
                    is_active = is_active,
                    message = message,
                    channel = channel,
                    model = model,
                    send_alert_on = send_alert_on,
                    value_change_field = value_change_field,
                    date_field = date_field,
                    alert_days = alert_days,
                    conditions = conditions
                )

            cleaned_recipients = create_recipients(channel, valid_recipients)
            if cleaned_recipients[0] == "E":
                return cleaned_recipients[1]

            else:
                if notification.channel == "E":
                    notification.email_recipients.clear()
                    notification.email_recipients.add(*cleaned_recipients[1])

                else:
                    notification.number_recipients.clear()
                    notification.number_recipients.add(*cleaned_recipients[1])

            return JsonResponse({
                "status": "S",
                "doc_id": notification.id,
                "valid_recipients": cleaned_recipients[2],
                "is_active": notification.is_active
            })

        else:
            return JsonResponse({
                "status": "E",
                "error": "You're not a superuser!",
                "message": "Only superusers are allowed to create notifications."
            })

    except Exception as e:
        return JsonResponse({
            "status": "E",
            "error": f"An unknown error has occured: {str(e)}",
            "message": f"An unknown error has occured while creating the notificaiton:\n\n{traceback.format_exc()}"
        })


@login_required
@require_http_methods(["POST",])
def upload_file(request):
    try:
        if _has_group(request.user, 'File Uploader'):
            file = request.FILES.get('file', None)
            is_private = request.POST.get('is_private', False)
            is_featured = request.POST.get('is_featured', False)
            
            if _File is None:
                return JsonResponse({
                    'status': 'E',
                    'error': 'File model unavailable',
                    'message': 'File model not installed.'
                })
            
            if not file:
                return JsonResponse({
                    'status': 'E',
                    'error': 'File is required!',
                    'message': 'A File is required but wasn\'t provided with this POST request.'
                })
            
            _file = _File.objects.create(
                file = file,
                is_private = is_private,
                is_featured = is_featured
            )
            
            return JsonResponse({
                'status': 'S',
                'message': 'Successfully uploaded File.',
                'doc_id': _file.id
            })
            
        else:
            return JsonResponse({
                "status": "E",
                "error": "You're not authorized to access this resource!",
                "message": "Only superusers are allowed to ."
            })

    except Exception as e:
        return JsonResponse({
            "status": "E",
            "error": f"An unknown error has occured: {str(e)}",
            "message": f"An unknown error has occured while creating the notificaiton:\n\n{traceback.format_exc()}"
        })
        

@login_required
@require_http_methods(["POST",])
def media_library(request):
    try:
        if _has_group(request.user, 'Media Library Manager'):
            if _File is None:
                return JsonResponse({
                    'status': 'E',
                    'error': 'File model unavailable',
                    'message': 'File model not installed.'
                })
            filter_start = request.POST.get('filter_start', 0)
            filter_end = request.POST.get('filter_end', 20)
            
            try:
                filter_start = int(filter_start)
            except:
                return _invalid_field('Filter Start')
            
            try:    
                filter_end = int(filter_end)
            except:
                return _invalid_field('Filter End')
            
            files = _File.objects.all().order_by('-created')[filter_start:filter_end]
            
            return JsonResponse({
                'status': 'S',
                'data': {
                    file.id: {
                        'is_featured': file.is_featured,
                        'is_private': file.is_private,
                        'file_url': file.file.url,
                        'attached_model': file.attached_model,
                        'attached_docname': file.attached_docname,
                        'attached_docfield': file.attached_docfield,
                        'created': file.created,
                        'updated': file.updated
                    }
                for file in files},
                'filter_start': filter_start + len(files),
                'filter_end': (filter_start + len(files)) + (filter_end - filter_start)
            })
            
        else:
            return JsonResponse({
                "status": "E",
                "error": "You're not authorized to access this resource!",
                "message": "Only superusers are allowed to ."
            })

    except Exception as e:
        return JsonResponse({
            "status": "E",
            "error": f"An unknown error has occured: {str(e)}",
            "message": f"An unknown error has occured while creating the notificaiton:\n\n{traceback.format_exc()}"
        })