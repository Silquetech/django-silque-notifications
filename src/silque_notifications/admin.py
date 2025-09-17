from django.contrib import admin, messages
from django.utils.translation import ngettext

from .forms import (
    EmailRecipientAdminForm,
    NotificationAdminForm,
    NumberRecipientAdminForm,
)
from .models import EmailRecipient, Notification, NumberRecipient


@admin.register(EmailRecipient)
class EmailRecipientAdmin(admin.ModelAdmin):
    form = EmailRecipientAdminForm
    readonly_fields = ["created", "updated"]

    def get_form(self, request, obj=None, **kwargs):
        # Inject request into form to read query params for model_hint
        base_form = super().get_form(request, obj, **kwargs)
        request_ref = request
        class RequestAwareForm(base_form):
            def __init__(self2, *args, **kw):
                kw['request'] = request_ref
                super().__init__(*args, **kw)
        return RequestAwareForm

    # Ensure popup add uses the standard admin popup response so M2M updates
    def response_add(self, request, obj, post_url_continue=None):
        if request.GET.get('_popup') == '1' or request.POST.get('_popup') == '1':
            from django.http import HttpResponse
            return HttpResponse('<script type="text/javascript">opener.dismissAddRelatedObjectPopup(window);</script>')
        return super().response_add(request, obj, post_url_continue)

@admin.register(NumberRecipient)
class NumberRecipientAdmin(admin.ModelAdmin):
    form = NumberRecipientAdminForm
    readonly_fields = ["created", "updated"]

    def get_form(self, request, obj=None, **kwargs):
        base_form = super().get_form(request, obj, **kwargs)
        request_ref = request
        class RequestAwareForm(base_form):
            def __init__(self2, *args, **kw):
                kw['request'] = request_ref
                super().__init__(*args, **kw)
        return RequestAwareForm

    def response_add(self, request, obj, post_url_continue=None):
        if request.GET.get('_popup') == '1' or request.POST.get('_popup') == '1':
            from django.http import HttpResponse
            return HttpResponse('<script type="text/javascript">opener.dismissAddRelatedObjectPopup(window);</script>')
        return super().response_add(request, obj, post_url_continue)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    form = NotificationAdminForm
    change_form_template = 'admin/silque_notifications/notification/change_form.html'
    readonly_fields = [
        "created", "updated"
    ]

    list_display = [
        "title", "is_active",
        "channel", "model", 
        "send_alert_on", "message", 
        "created"
    ]

    list_filter = [
        "is_active", "channel",
        "send_alert_on", "model",
        "created", "updated"
    ]

    search_fields = [
        "title", "message",
        "email_recipients__by_docfield",
        "email_recipients__by_email",
        "number_recipients__by_docfield",
        "number_recipients__by_number",
    ]

    filter_horizontal = ["email_recipients", "number_recipients"]

    class Media:
        js = ['silque_notifications/notification_admin.js']

    @admin.action(description="Mark Notifications active.")
    def mark_notifications_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, ngettext(
            '%d notification was successfully marked as active.',
            '%d notifications were successfully marked as active.',
            updated,
        ) % updated, messages.SUCCESS)

    @admin.action(description="Mark Notifications inactive.")
    def mark_notifications_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, ngettext(
            '%d notification was successfully marked as inactive.',
            '%d notifications were successfully marked as inactive.',
            updated,
        ) % updated, messages.SUCCESS)

    @admin.action(description="Make duplicate copy.")
    def make_duplicate_copy(self, request, queryset):
        for obj in queryset:
            new_obj = Notification.objects.create(
                is_active=obj.is_active,
                channel=obj.channel,
                title=f"Duplicate - {obj.title}",
                message=obj.message,
                model=obj.model,
                send_alert_on=obj.send_alert_on,
                value_change_field=obj.value_change_field,
                date_field=obj.date_field,
                alert_days=obj.alert_days,
                conditions=obj.conditions,
            )
            new_obj.email_recipients.add(*obj.email_recipients.all())
            new_obj.number_recipients.add(*obj.number_recipients.all())
            messages.success(request, f"A duplicate has been created for: [{obj.id}] {obj.title}")
        

    actions = [
        mark_notifications_active, mark_notifications_inactive,
        make_duplicate_copy
    ]

    # Use default Django admin change form template for broader compatibility