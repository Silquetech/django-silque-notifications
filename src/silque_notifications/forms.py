from django import forms
from django.urls import reverse

from .helpers import get_notification_models_with_app_label
from .models import EmailRecipient, Notification, NumberRecipient


class NotificationAdminForm(forms.ModelForm):
    """Admin form to integrate with default Django admin.

    - Provides a Select for the `model` field with dynamic choices from helpers.
    - Renders `value_change_field` and `date_field` as Selects so we can populate
      options via lightweight JS based on the chosen model and alert type.
    """

    model = forms.ChoiceField(choices=(), required=True, label="Model")
    value_change_field = forms.ChoiceField(choices=(), required=False, label="Value Change Field")
    date_field = forms.ChoiceField(choices=(), required=False, label="Date Field")
    # Relational selections removed: now handled in Email/Number Recipient admin via model hint

    class Meta:
        model = Notification
        fields = [
            'is_active', 'title', 'message', 'channel', 'model', 'send_alert_on',
            'value_change_field', 'date_field', 'alert_days', 'conditions',
            'email_recipients', 'number_recipients'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate available models into the select
        try:
            models_list = get_notification_models_with_app_label()
        except Exception:
            models_list = []

        self.fields["model"].choices = [(m, m) for m in models_list]

        # When editing an existing object, show the saved values as the first choice
        if self.instance and self.instance.pk:
            if self.instance.value_change_field:
                self.fields["value_change_field"].choices = [
                    (self.instance.value_change_field, self.instance.value_change_field)
                ]
            if self.instance.date_field:
                self.fields["date_field"].choices = [
                    (self.instance.date_field, self.instance.date_field)
                ]

        # Add helpful data-attrs for JS using named URLs (no hardcoded prefixes)
        try:
            fields_url = reverse('silque_notifications:get_model_fields')
            date_fields_url = reverse('silque_notifications:get_model_date_fields')
            relational_url = reverse('silque_notifications:get_model_relational_recipients')
        except Exception:
            # Fallbacks in case URL reversing fails at import time; JS will still handle gracefully
            fields_url = '/get_model_fields/'
            date_fields_url = '/get_model_date_fields/'
            relational_url = '/get_model_relational_recipients/'

        self.fields["model"].widget.attrs.update({
            "data-fields-url": fields_url,
            "data-date-fields-url": date_fields_url,
            "data-relational-url": relational_url,
        })

        # Add CSS classes to help with conditional showing/hiding
        # Don't set display:none here, let JavaScript handle visibility
        self.fields["value_change_field"].widget.attrs.update({
            "class": "conditional-field field-for-value-change"
        })
        self.fields["date_field"].widget.attrs.update({
            "class": "conditional-field field-for-date"
        })
        self.fields["alert_days"].widget.attrs.update({
            "class": "conditional-field field-for-date"
        })

    def clean(self):
        cleaned = super().clean()
        send_on = cleaned.get('send_alert_on')
        channel = cleaned.get('channel')

        value_change_field = cleaned.get('value_change_field')
        date_field = cleaned.get('date_field')
        alert_days = cleaned.get('alert_days')

        email_recipients = cleaned.get('email_recipients')
        number_recipients = cleaned.get('number_recipients')

        # Validate alert dependencies
        # B/A -> date_field + alert_days required
        if send_on in ['B', 'A']:
            if not date_field:
                self.add_error('date_field', 'This field is required for Days Before/After.')
            if alert_days in [None, '']:
                self.add_error('alert_days', 'This field is required for Days Before/After.')
        # V -> value_change_field required
        if send_on == 'V':
            if not value_change_field:
                self.add_error('value_change_field', 'This field is required for Value Change.')

        # Additional numeric check
        if alert_days not in [None, '']:
            try:
                if int(alert_days) < 0:
                    self.add_error('alert_days', 'Alert days must be zero or a positive number.')
            except (TypeError, ValueError):
                self.add_error('alert_days', 'Alert days must be a valid integer.')

        # Channel recipients validation
        # Email -> some email recipient (explicit or relational)
        if channel == 'E':
            has_emails = (email_recipients and email_recipients.exists())
            if not has_emails:
                self.add_error('email_recipients', 'At least one email recipient is required for Email channel.')
                # Note: relational suggestions now live on EmailRecipient admin
        # SMS/Whatsapp -> some number recipient (explicit or relational)
        if channel in ['S', 'W']:
            has_numbers = (number_recipients and number_recipients.exists())
            if not has_numbers:
                self.add_error('number_recipients', 'At least one number recipient is required for SMS or Whatsapp channel.')
                # Note: relational suggestions now live on NumberRecipient admin

        return cleaned

    def save(self, commit=True):
        # Relational creation removed; manage via recipient admin
        return super().save(commit)


class EmailRecipientAdminForm(forms.ModelForm):
    """Recipient admin with implicit model context from querystring (no visible field)."""

    class Meta:
        model = EmailRecipient
        fields = ['by_docfield', 'by_email']
        widgets = {
            'by_docfield': forms.TextInput(attrs={'placeholder': 'e.g. doc.customer.email'}),
            'by_email': forms.EmailInput(attrs={'placeholder': 'name@example.com'})
        }

    class Media:
        js = ['silque_notifications/recipients_admin.js']

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        # Provide endpoint to JS via widget data-attr
        try:
            rel_url = reverse('silque_notifications:get_model_relational_recipients')
        except Exception:
            rel_url = '/get_model_relational_recipients/'
        self.fields['by_docfield'].widget.attrs.update({'data-relational-url': rel_url})
        # Pre-populate by_docfield options server-side using model_hint from URL
        model_hint_val = None
        if request:
            model_hint_val = request.GET.get('model_hint')
        if model_hint_val:
            suggestions = []
            try:
                parts = [p.strip() for p in model_hint_val.split('~')]
                # Support both "app ~ Model ~ Verbose" and "app ~ Model"
                app_label = parts[0]
                model_name = parts[1] if len(parts) > 1 else None
                if app_label and model_name:
                    from .helpers import get_model_relational_recipients
                    suggestions = get_model_relational_recipients(app_label, model_name, for_email=True)
            except Exception:
                suggestions = []
            if suggestions:
                choices = [('', '--- Select ---')] + [(s.split(' ~ ')[0], s) for s in suggestions]
                current_val = None
                if self.instance and self.instance.pk and self.instance.by_docfield:
                    current_val = self.instance.by_docfield
                    if current_val and all(cv[0] != current_val for cv in choices):
                        choices.append((current_val, current_val))
                self.fields['by_docfield'] = forms.ChoiceField(choices=choices, required=False, label=self.fields['by_docfield'].label)
                # Preserve data attribute on the newly created field's widget
                self.fields['by_docfield'].widget.attrs.update({'data-relational-url': rel_url})


class NumberRecipientAdminForm(forms.ModelForm):
    """Recipient admin with implicit model context from querystring (no visible field)."""

    class Meta:
        model = NumberRecipient
        fields = ['by_docfield', 'by_number']
        widgets = {
            'by_docfield': forms.TextInput(attrs={'placeholder': 'e.g. doc.customer.phone'}),
            'by_number': forms.TextInput(attrs={'placeholder': '+15551234567'})
        }

    class Media:
        js = ['silque_notifications/recipients_admin.js']

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        # Provide endpoint to JS via widget data-attr
        try:
            rel_url = reverse('silque_notifications:get_model_relational_recipients')
        except Exception:
            rel_url = '/get_model_relational_recipients/'
        self.fields['by_docfield'].widget.attrs.update({'data-relational-url': rel_url})
        model_hint_val = None
        if request:
            model_hint_val = request.GET.get('model_hint')
        if model_hint_val:
            suggestions = []
            try:
                parts = [p.strip() for p in model_hint_val.split('~')]
                app_label = parts[0]
                model_name = parts[1] if len(parts) > 1 else None
                if app_label and model_name:
                    from .helpers import get_model_relational_recipients
                    suggestions = get_model_relational_recipients(app_label, model_name, for_email=False)
            except Exception:
                suggestions = []
            if suggestions:
                choices = [('', '--- Select ---')] + [(s.split(' ~ ')[0], s) for s in suggestions]
                current_val = None
                if self.instance and self.instance.pk and self.instance.by_docfield:
                    current_val = self.instance.by_docfield
                    if current_val and all(cv[0] != current_val for cv in choices):
                        choices.append((current_val, current_val))
                self.fields['by_docfield'] = forms.ChoiceField(choices=choices, required=False, label=self.fields['by_docfield'].label)
                # Preserve data attribute on the newly created field's widget
                self.fields['by_docfield'].widget.attrs.update({'data-relational-url': rel_url})
