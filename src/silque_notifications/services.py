import ast
import logging
import re
import time

import requests
from django.apps import apps
from django.conf import settings
from django.core.mail import send_mail

from silque_notifications.helpers import validate_email

# Try to import ErrorLog from silque_core if app is installed
try:
    from django.apps import apps as _apps
    if _apps.is_installed('silque_core'):
        from silque_core.models import ErrorLog  # type: ignore
    else:
        ErrorLog = None  # type: ignore
except Exception:
    ErrorLog = None  # type: ignore


EmailConfiguration = None
logger = logging.getLogger('silque_notifications')

class EmailService:
    def __init__(self):
        # Open-source safe: no hard dependency on a config model
        self.email_config = None

    def send_mail(self, subject, message, recipients, html_message=None):
        try:
            from_email = getattr(self.email_config, 'from_email', None) if self.email_config else None
            send_mail(subject, message, from_email, recipients, html_message=html_message)
        except Exception as e:
            logger.exception("[EMAIL-SERVICE] Failed to send email")
            if ErrorLog:
                try:
                    ErrorLog.from_exception(e, source="notifications.email", code="EMAIL_SEND_FAIL")
                except Exception:
                    pass

class SMSService:
    def __init__(self):
        # self.sms_config = SMSConfiguration.get_solo()   
        pass     

    def get_headers(self):
        headers = {'Accept': "text/plain, text/html, */*"}
        for parameter in self.sms_config.parameters.all():
            headers.update({parameter.parameter: parameter.value})

        return headers

    def send_request(self, gateway_url, params, headers=None, use_post=False):
        if not headers:
            headers = self.get_headers()

        if use_post:
            response = requests.post(gateway_url, headers=headers, data=params)

        else:
            response = requests.get(gateway_url, headers=headers, params=params)

        response.raise_for_status()
        return response

    def validate_receiver_nos(self, receiver_list):
        validated_receiver_list = []
        for receiver in receiver_list:
            # remove invalid character
            for x in [' ','-', '(', ')']:
                receiver = receiver.replace(x, '')

            validated_receiver_list.append(receiver)

        if not validated_receiver_list:
            return None

        return validated_receiver_list

    def send_via_gateway(self, arg):
        headers = self.get_headers()

        args = {self.sms_config.message_parameter: arg.get('message')}
        for parameter in self.sms_config.parameters.all():
            args.update({parameter.parameter: parameter.value})

        success_list = []
        for receiver in arg.get('receiver_list'):
            args[self.sms_config.receiver_parameter] = receiver
            
            try:
                response = self.send_request(self.sms_config.gateway, args, headers, self.sms_config.use_post)

                try:
                    _response = response.json()
                except:
                    _response = response.text

                # SMSLog.objects.create(
                #     recipient=receiver,
                #     message=f"{arg.get('message')}\n\n{_response}",
                # )
            except Exception as e:
                logger.exception("[SMS-FAILED] recipient=%s", receiver)
                if ErrorLog:
                    try:
                        ErrorLog.from_exception(e, source="notifications.sms", code="SMS_SEND_FAIL", context={"recipient": receiver})
                    except Exception:
                        pass
        

    def send_sms(self, receiver_list, msg, sender_name='', success_msg=True):

        """From erpnext SMS Settings File. Not sure what this does just yet...

        if isinstance(receiver_list, string_types):
            receiver_list = json.loads(receiver_list)
            if not isinstance(receiver_list, list):
                receiver_list = [receiver_list]
        """

        receiver_list = self.validate_receiver_nos(receiver_list)

        arg = {
            'receiver_list' : receiver_list,
            'message'		: msg,
            'success_msg'	: success_msg
        }

        if self.sms_config:
            self.send_via_gateway(arg)


class WhatsappService:
    def __init__(self):
        # whatsapp_config = WhatsappConfiguration.get_solo()
        pass

    def validate_receiver_nos(self, receiver_list):
        validated_receiver_list = []
        for receiver in receiver_list:
            # remove invalid character
            for x in [' ','-', '(', ')', '+']:
                receiver = receiver.replace(x, '')

            validated_receiver_list.append(receiver)

        if not validated_receiver_list:
            return None

        return validated_receiver_list

    def send_whatsapp_message(self, recipients_list, message):
        if self.whatsapp_config:
            recipients_list = self.validate_receiver_nos(recipients_list)

            count = 0
            for recipient in recipients_list:
                count += 1

                if count == 100:
                    count = 0
                    time.sleep(20)

                try:
                    response = requests.post(f"{self.whatsapp_config.gateway}/sendText", data={
                        "authorization_key_one": self.whatsapp_config.authorization_key_one,
                        "authorization_key_two": self.whatsapp_config.authorization_key_two,
                        "authorization_key_three": self.whatsapp_config.authorization_key_three,
                        "number": recipient, "message": message
                    })

                    response = response.json()

                    # whatsapp_log = WhatsappLog.objects.create(
                    #     recipient=recipient,
                    #     message=message + f"\n\n RESPONSE: {str(response)}",
                    # )

                    if response.get("status") == "E":
                        logger.warning("[WS] gateway returned error for recipient=%s: %s", recipient, response)

                except Exception as e:
                    logger.exception("[WS-FAILED] recipient=%s", recipient)
                    if ErrorLog:
                        try:
                            ErrorLog.from_exception(e, source="notifications.whatsapp", code="WHATSAPP_SEND_FAIL", context={"recipient": recipient})
                        except Exception:
                            pass

class NotificationService:
    def __init__(self, old_obj, new_obj, valid_notifications):
        self.old_obj = old_obj
        self.new_obj = new_obj
        self.valid_notifications = valid_notifications

    @staticmethod
    def resolve_attr_path(root, path):
        """Safely resolve dotted attribute path on an object or dict.
        Returns None if any step is missing.
        """
        if root is None or not path:
            return None
        cur = root
        for part in path.split('.'):
            if cur is None:
                return None
            try:
                if isinstance(cur, dict):
                    cur = cur.get(part)
                else:
                    cur = getattr(cur, part)
            except Exception:
                return None
        return cur

    @staticmethod
    def _safe_eval_condition(expr: str, context: dict) -> bool:
        """Evaluate a boolean condition with a restricted AST.
        Allowed: names (doc, old_doc, notif), attributes, constants, comparisons,
        boolean ops (and/or), unary not, parentheses.
        """
        allowed_nodes = (
            ast.Module, ast.Expr, ast.Expression,
            ast.BoolOp, ast.And, ast.Or,
            ast.UnaryOp, ast.Not,
            ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
            ast.Load,
            ast.Name, ast.Attribute,
            ast.Constant,
            ast.Tuple, ast.List
        )

        tree = ast.parse(expr, mode='eval')

        class Checker(ast.NodeVisitor):
            def generic_visit(self, node):
                if not isinstance(node, allowed_nodes):
                    raise ValueError(f"Disallowed expression: {type(node).__name__}")
                super().generic_visit(node)

        Checker().visit(tree)
        code = compile(tree, '<condition>', 'eval')
        return bool(eval(code, {'__builtins__': {}}, context))

    def parse_string(self, notification, string):
        # Identify {{ doc.* }}, {{ old_doc.* }}, {{ notif.* }} tokens and replace safely
        detected_expressions = sorted([''.join(exp) for exp in re.findall(r"(\{\{)(.+?)(\}\})", string)])

        doc = self.new_obj
        old_doc = self.old_obj

        for expression in detected_expressions:
            cleaned_expression = expression.replace("{{", "").replace("}}", "").strip()
            try:
                if cleaned_expression.startswith('doc.'):
                    val = self.resolve_attr_path(doc, cleaned_expression[len('doc.'):])
                elif cleaned_expression.startswith('old_doc.'):
                    val = self.resolve_attr_path(old_doc, cleaned_expression[len('old_doc.'):])
                elif cleaned_expression.startswith('notif.'):
                    val = self.resolve_attr_path(notification, cleaned_expression[len('notif.'):])
                else:
                    val = None
                if val is not None:
                    string = string.replace(expression, str(val))
            except Exception as e:
                logger.exception("[TEMPLATE] Failed to resolve expression: %s", cleaned_expression)
                if ErrorLog:
                    try:
                        ErrorLog.from_exception(e, source="notifications.template", code="TEMPLATE_PARSE_FAIL", context={"expression": cleaned_expression})
                    except Exception:
                        pass

        return string

    def meets_conditions(self, notification):
        if notification.conditions:
            for condition in notification.conditions.split("\n"):
                if len(condition) > 1:
                    try:
                        ctx = {'doc': self.new_obj, 'old_doc': self.old_obj, 'notif': notification}
                        if self._safe_eval_condition(condition, ctx):
                            return True
                    except Exception as e:
                        logger.exception("[CONDITION-EVALUATION] Invalid condition: %s", condition)
                        if ErrorLog:
                            try:
                                ErrorLog.from_exception(e, source="notifications.condition", code="CONDITION_EVAL_FAIL", context={"condition": condition})
                            except Exception:
                                pass
                
            return False

        else:
            return True

    def get_email_recipients(self, notification):
        notification_relational_recipients = getattr(settings, "S_NOTIFICATION_RELATIONAL_EMAIL_RECIPIENTS", None)
        recipients = []

        for recipient in notification.email_recipients.all():
            if recipient.by_email:
                is_valid = validate_email(recipient.by_email)
                if is_valid:
                    recipients.append(recipient.by_email)

                else:
                    logger.warning("[EMAIL-RECIPIENT] Invalid email provided: %s", recipient.by_email)

            if recipient.by_docfield:
                docfields = []
                try_fields = []

                try: 
                    if recipient.by_docfield.startswith('silque.') and notification_relational_recipients:
                        split_docfield = recipient.by_docfield.replace("silque.", "").split(".")
                        model = '.'.join([split_docfield[2], split_docfield[3].split(' ~ ')[0]])

                        if model in notification_relational_recipients:
                            # mapped; build candidate fields from mapping
                            for field in notification_relational_recipients[model]:
                                if type(field) == str:
                                    docfields.append(f"{split_docfield[0]}.{split_docfield[1]}.{field}")

                                    # simple mapped field

                                elif type(field) == tuple or type(field) == list:
                                    for try_field in field:

                                        # prioritized list of fields
                                        docfields.append(f"{split_docfield[0]}.{split_docfield[1]}.{try_field}")
                                        try_fields.append(f"{split_docfield[0]}.{split_docfield[1]}.{try_field}")
                    elif recipient.by_docfield.startswith('silque.') and not notification_relational_recipients:
                        # No mapping provided: heuristic guess and model-declared hints
                        split = recipient.by_docfield.replace("silque.", "").split(".")
                        fk_prefix = f"{split[0]}.{split[1]}"
                        app_label = split[2]
                        model_name = split[3].split(' ~ ')[0]
                        likely = ["email", "email_address"]
                        # Check model-declared notification fields if any
                        try:
                            model_cls = apps.get_model(app_label, model_name)
                            likely = list(set(likely + list(getattr(model_cls, 'NOTIFICATION_EMAIL_FIELDS', []))))
                        except Exception:
                            pass
                        for name in likely:
                            docfields.append(f"{fk_prefix}.{name}")
                    else:
                        docfields.append(recipient.by_docfield)

                    for docfield in docfields:
                        try:
                            if docfield.startswith('doc.'):
                                email = self.resolve_attr_path(self.new_obj, docfield[len('doc.'):])
                            elif docfield.startswith('old_doc.'):
                                email = self.resolve_attr_path(self.old_obj, docfield[len('old_doc.'):])
                            else:
                                email = self.resolve_attr_path(self.new_obj, docfield)

                            is_valid = validate_email(email)
                            if is_valid:
                                recipients.append(email)

                            else:
                                if docfield not in try_fields:
                                    logger.warning("[EMAIL-RECIPIENT] Invalid resolved email from %s", docfield)

                        except Exception as e:
                            if docfield not in try_fields:
                                logger.exception("[EMAIL-RECIPIENT] Failed to resolve from %s", docfield)
                            if ErrorLog:
                                try:
                                    ErrorLog.from_exception(e, source="notifications.email_recipients", code="EMAIL_RECIPIENT_RESOLVE_FAIL", context={"docfield": docfield})
                                except Exception:
                                    pass

                except Exception as e:
                    logger.exception("[EMAIL-RECIPIENT] Unknown error for %s", recipient.by_docfield)
                    if ErrorLog:
                        try:
                            ErrorLog.from_exception(e, source="notifications.email_recipients", code="EMAIL_RECIPIENT_ERROR", context={"by_docfield": recipient.by_docfield})
                        except Exception:
                            pass

        return recipients

    def get_number_recipients(self, notification):
        notification_relational_recipients = getattr(settings, "S_NOTIFICATION_RELATIONAL_NUMBER_RECIPIENTS", None)
        recipients = []

        for recipient in notification.number_recipients.all():
            if recipient.by_number:
                recipients.append(recipient.by_number)

            if recipient.by_docfield:
                docfields = []
                try_fields = []

                try:
                    if recipient.by_docfield.startswith('silque.') and notification_relational_recipients:
                        split_docfield = recipient.by_docfield.replace("silque.", "").split(".")
                        model = '.'.join([split_docfield[2], split_docfield[3].split(' ~ ')[0]])

                        if model in notification_relational_recipients:
                            for field in notification_relational_recipients[model]:
                                if type(field) == str:
                                    docfields.append(f"{split_docfield[0]}.{split_docfield[1]}.{field}")

                                elif type(field) == tuple or type(field) == list:
                                    for try_field in field:
                                        docfields.append(f"{split_docfield[0]}.{split_docfield[1]}.{try_field}")
                                        try_fields.append(f"{split_docfield[0]}.{split_docfield[1]}.{try_field}")
                        
                    elif recipient.by_docfield.startswith('silque.') and not notification_relational_recipients:
                        split = recipient.by_docfield.replace("silque.", "").split(".")
                        fk_prefix = f"{split[0]}.{split[1]}"
                        app_label = split[2]
                        model_name = split[3].split(' ~ ')[0]
                        likely = ["mobile_number", "phone", "phone_number", "mobile", "contact_number"]
                        try:
                            model_cls = apps.get_model(app_label, model_name)
                            likely = list(set(likely + list(getattr(model_cls, 'NOTIFICATION_NUMBER_FIELDS', []))))
                        except Exception:
                            pass
                        for name in likely:
                            docfields.append(f"{fk_prefix}.{name}")
                    else:
                        docfields.append(recipient.by_docfield)

                    for docfield in docfields:
                        try:
                            if docfield.startswith('doc.'):
                                number = self.resolve_attr_path(self.new_obj, docfield[len('doc.'):])
                            elif docfield.startswith('old_doc.'):
                                number = self.resolve_attr_path(self.old_obj, docfield[len('old_doc.'):])
                            else:
                                number = self.resolve_attr_path(self.new_obj, docfield)
                            if number is not None:
                                recipients.append(number)

                        except Exception as e:
                            if docfield not in try_fields:
                                logger.exception("[NUMBER-RECIPIENT] Failed to resolve from %s", docfield)
                            if ErrorLog:
                                try:
                                    ErrorLog.from_exception(e, source="notifications.number_recipients", code="NUMBER_RECIPIENT_RESOLVE_FAIL", context={"docfield": docfield})
                                except Exception:
                                    pass

                except Exception as e:
                    logger.exception("[NUMBER-RECIPIENT] Unknown error for %s", recipient.by_docfield)
                    if ErrorLog:
                        try:
                            ErrorLog.from_exception(e, source="notifications.number_recipients", code="NUMBER_RECIPIENT_ERROR", context={"by_docfield": recipient.by_docfield})
                        except Exception:
                            pass

        return recipients

    def send_notifications(self):
        for notification in self.valid_notifications:
            if self.meets_conditions(notification):
                if notification.channel == 'E':
                    email_recipients = self.get_email_recipients(notification)

                    if email_recipients:
                        subject = self.parse_string(notification, notification.title)
                        message = self.parse_string(notification, notification.message)

                        # Use Celery task (it uses EmailService under the hood)
                        from .tasks import send_email_task
                        send_email_task.delay(subject, message, email_recipients, None)
                
                elif notification.channel in ["S", "W"]:
                    number_recipients = self.get_number_recipients(notification)

                    if number_recipients:
                        message = self.parse_string(notification, notification.message)

                        if notification.channel == "S":
                            sms_obj = SMSService()
                            # Use Celery task instead of django_rq
                            from .tasks import send_sms_task
                            send_sms_task.delay(number_recipients, message)
                            
                        elif notification.channel == "W":
                            whatsapp_obj = WhatsappService()
                            # Use Celery task instead of django_rq
                            from .tasks import send_whatsapp_task
                            send_whatsapp_task.delay(number_recipients, message)