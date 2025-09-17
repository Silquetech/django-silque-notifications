# django-silque-notifications

Flexible, admin-driven notifications for Django with Celery/Redis, relational recipient resolution, and safe templating.

- Admin-first UX: define notifications in Django admin
- Channels: Email (E), SMS (S), WhatsApp (W)
- Triggers: New/Update/Delete, Value Change, Before/After date
- Recipients: direct email/number, document fields, and relational mappings
- Celery + Redis: scalable task queue with retries
- Safe expressions and Jinja-like templating

> The world’s first fully admin-driven, dynamic notification system for Django—no code changes required to add or evolve notifications.

## Feature highlights

| Area | What you get |
|---|---|
| Channels | Email, SMS, WhatsApp |
| Triggers | New (N), Update (U), Delete (D), Value Change (V), Days Before (B), Days After (A) |
| Recipients | Direct emails/numbers; document-field lookups; deep relational recipients with mappings, heuristics, and per-model hints |
| Authoring | Everything from Django admin; popup recipient creation with context-aware suggestions |
| Safety | Strict validation, restricted condition evaluator (no eval), and robust attribute resolution |
| Delivery | Celery + Redis with retries; enqueue on save/delete via signals, transaction-safe |
| UI/UX | Clean admin widgets, helpful JS, dark mode-friendly CSS |
| Extensibility | Pluggable settings for relational mappings; model-level hints to improve suggestions |

## Quickstart

1) Install

```powershell
pip install django-silque-notifications
```

2) Add to Django settings

```python
INSTALLED_APPS = [
    # ...
    "silque_notifications",
]

# Redis + Celery
REDIS_URL = "redis://localhost:6379/0"
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_RESULT_EXPIRES = 3600

# Optional mappings for relational recipients
S_NOTIFICATION_RELATIONAL_EMAIL_RECIPIENTS = {
    "supplier.Supplier": ["email_address"],
    "employee.Employee": ["email_address"],
    # Try these in order
    "silque_user.User": [("employee.email_address", "supplier.email_address")],
}
S_NOTIFICATION_RELATIONAL_NUMBER_RECIPIENTS = {
    "supplier.Supplier": ["mobile_number"],
    "employee.Employee": ["mobile_number"],
}
```

Note on names:
- Install name (pip): django-silque-notifications
- Import/app name (Python/Django): silque_notifications

Python imports can’t contain hyphens, so use underscores when importing or adding to INSTALLED_APPS:

```python
import silque_notifications

INSTALLED_APPS = [
    # ...
    "silque_notifications",
]
```

3) Wire Celery (standard Django pattern)

Create `celery.py` in your Django project and load it in `__init__.py`. See `src/silque_notifications/CELERY_MIGRATION.md` for a reference.

4) Migrate

```powershell
python manage.py migrate
```

5) Start Celery worker

```powershell
celery -A <your_project> worker --loglevel=info
```

6) Use in admin

- Add Notification entries
- Choose Channel, Trigger, and Recipients
- Save and let Celery handle delivery

## How it works

This section inlines the full behavior guide so you don’t need to jump around.

### 1) Setup at a glance

- Enable `silque_notifications` in `INSTALLED_APPS` (plus your own app models, e.g., `euser`).
- Configure Redis + Celery in your project settings: `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, and set JSON serializers.
- Optional relational mapping settings (see table below).
- Optional per-model field hints on your own models to improve suggestions.

Settings quick-reference:

| Setting | Purpose | Example |
|---|---|---|
| S_NOTIFICATION_RELATIONAL_EMAIL_RECIPIENTS | Fields to try for email on related models | `{ "supplier.Supplier": ["email_address"], "silque_user.User": [("employee.email_address", "supplier.email_address")] }` |
| S_NOTIFICATION_RELATIONAL_NUMBER_RECIPIENTS | Fields to try for numbers on related models | `{ "supplier.Supplier": ["mobile_number"] }` |

Per-model hints (on your models):

```python
class Customer(models.Model):
        NOTIFICATION_EMAIL_FIELDS = ["primary_email", "billing_email"]
        NOTIFICATION_NUMBER_FIELDS = ["mobile", "office_phone"]
```

### 2) Admin flow (create/edit Notification)

1. Choose a Model: pick any model that subclasses `NotificationModel`.
2. Pick Channel: E (Email), S (SMS), W (WhatsApp).
3. Choose Trigger:
     - V (Value Change): requires `value_change_field`
     - B/A (Before/After date): requires `date_field` and non-negative `alert_days`
     - N/U/D (New/Update/Delete): no extra inputs
4. Add Recipients via M2M widgets:
     - Use the “Add …Recipient via lookup” buttons; popups carry model context.
     - Select from suggestions or type a dotted path; you can also set a direct email/number.
5. Save: form validation enforces the minimum inputs; the model also validates via `full_clean()` in `save()`.

At a glance — channels and triggers:

| Channel | Requires | Best for |
|---|---|---|
| Email (E) | At least one email recipient | Transactional emails, alerts |
| SMS (S) | At least one number recipient | Short alerts, OTP-like flows |
| WhatsApp (W) | At least one number recipient | Chat-first notifications |

| Trigger | Extra fields | Behavior |
|---|---|---|
| New (N) | — | On object creation |
| Update (U) | — | On object update |
| Delete (D) | — | On object deletion |
| Value Change (V) | `value_change_field` | When the selected field changes |
| Days Before (B) | `date_field`, `alert_days ≥ 0` | Relative to a date on the object |
| Days After (A) | `date_field`, `alert_days ≥ 0` | Relative to a date on the object |

### 3) Recipient admin popups (context-aware)

- The Notification form passes `model_hint` + `_popup=1` into recipient popups.
- Email/Number Recipient admin forms use this context to show suggestions in `by_docfield`:
    - Direct fields on the selected model (`doc.email`, `old_doc.email`), if present
    - Relational tokens for FKs/O2Os when likely fields exist on related models
- You can always type a dotted path manually if suggestions don’t fit.

### 4) Relational recipients and mappings

You can target recipients by dotted paths:

- Direct: `doc.customer.email` or `old_doc.customer.email`
- Relational token: `silque.doc.customer.supplier.Supplier ~ New Supplier`
    - `silque.doc` or `silque.old_doc` indicates which object to traverse
    - `<customer>` is your FK/O2O field on the selected model
    - `<supplier.Supplier>` identifies the related model

Mappings tell the resolver which fields to try on reached models (strings are used as-is; tuples/lists indicate priority order):

```python
S_NOTIFICATION_RELATIONAL_EMAIL_RECIPIENTS = {
        "supplier.Supplier": ["email_address"],
        "employee.Employee": ["email_address"],
        # Priority example: try these in sequence
        "silque_user.User": [("employee.email_address", "supplier.email_address")],
}
S_NOTIFICATION_RELATIONAL_NUMBER_RECIPIENTS = {
        "supplier.Supplier": ["mobile_number"],
        "employee.Employee": ["mobile_number"],
}
```

### 5) Heuristics and per-model hints

If no mapping is provided for a reached model, the resolver uses heuristics:

- Email: `email`, `email_address`
- Number: `mobile_number`, `phone`, `phone_number`, `mobile`, `contact_number`

If the selected model itself has those fields, suggestions include direct paths (`doc.email`, `old_doc.email`, etc.).

### 6) Conditions and templating

- Templates support: `{{ doc.* }}`, `{{ old_doc.* }}`, `{{ notif.* }}`
- Conditions (one per line) use a restricted AST (no `eval`), allowing simple boolean logic and comparisons.

Examples:

```
doc.status == "APPROVED"
old_doc.amount != doc.amount
(notif.channel == "E") and (doc.total > 0)
```

### 7) Delivery and tasks

- NotificationModel events enqueue Celery tasks (email/SMS/WhatsApp) using Redis.
- Tasks resolve recipients from direct values, dotted paths, and relational tokens via mappings/heuristics/hints.
- Invalid emails are filtered out; numbers are treated as strings. Errors are logged.

### 8) Validation & safety

- Channel E requires at least one email recipient; S/W require at least one number recipient.
- V requires `value_change_field`; B/A require `date_field` + `alert_days ≥ 0`.
- `save().full_clean()` ensures programmatic writes obey rules.
- Attribute resolution is safe; condition evaluator uses a restricted AST.

### 9) UI/UX details

- Shippable admin: extends Django admin with lightweight JS/CSS.
- Dark mode support via CSS variables and MutationObserver.
- M2M widgets get “Add via lookup” buttons; popups carry `model_hint` & `_popup=1`.

### 10) Troubleshooting

- No suggestions on NumberRecipient? Ensure the model has a number field or an FK/O2O to a mapped model.
- A mapped field doesn’t appear in UI? Mapped subfields are tried at runtime when a relational token is chosen.
- ExtendedUser mapping example: if the actual field is `email`, use `"euser.ExtendedUser": ["email"]`.

## Example recipient mappings

```python
S_NOTIFICATION_RELATIONAL_EMAIL_RECIPIENTS = {
    "supplier.Supplier": ["email_address"],
    "employee.Employee": ["email_address"],
    # Priority example (sequential)
    "silque_user.User": [("employee.email_address", "supplier.email_address")],
}
S_NOTIFICATION_RELATIONAL_NUMBER_RECIPIENTS = {
    "supplier.Supplier": ["mobile_number"],
    "employee.Employee": ["mobile_number"],
}
```

## Troubleshooting

- No number suggestions? Ensure the selected model has a number field or FK/O2O to a mapped model.
- A mapped field doesn’t appear in the UI? Mapped subfields are tried at runtime when a relational token is chosen.
- ExtendedUser mapping: if actual field is `email`, use `"euser.ExtendedUser": ["email"]`.

## Development

- Repo uses src layout and includes templates/static via MANIFEST.in
- Lint/type/test with Ruff, mypy, and pytest (config included)

## Comparison with alternatives

Here's how `django-silque-notifications` compares to other Django notification systems:

| Feature | django-silque-notifications | django-notifications | pinax-notifications | django-notify-x2 | django-rest-framework-notifications |
|---|---|---|---|---|---|
| **Admin Interface** | ✅ Full admin UI | ❌ Basic admin | ✅ Basic admin | ❌ Programmatic only | ❌ API only |
| **No-code Setup** | ✅ Everything via admin | ❌ Requires code | ❌ Requires code | ❌ Requires code | ❌ Requires code |
| **Multiple Channels** | ✅ Email, SMS, WhatsApp | ❌ In-app only | ✅ Email, custom backends | ❌ In-app only | ❌ Push notifications |
| **Dynamic Triggers** | ✅ 6 trigger types via admin | ❌ Signal-based only | ❌ Manual send only | ❌ Signal-based only | ❌ Manual send only |
| **Relational Recipients** | ✅ Deep FK/O2O traversal | ❌ Direct recipients only | ❌ Direct recipients only | ❌ Direct recipients only | ❌ Direct recipients only |
| **Background Processing** | ✅ Celery + Redis | ❌ Synchronous | ✅ Queue system | ❌ Synchronous | ✅ Various backends |
| **Template Engine** | ✅ Safe Jinja-like | ❌ Basic text | ✅ Django templates | ❌ Basic text | ✅ Custom formats |
| **Condition Logic** | ✅ Safe expressions | ❌ No conditions | ❌ No conditions | ❌ No conditions | ❌ No conditions |
| **Live Updates** | ❌ Background only | ✅ JavaScript API | ❌ Background only | ✅ WebSocket support | ✅ Real-time |
| **User Preferences** | ❌ Admin-driven | ✅ User settings page | ✅ User settings page | ✅ User settings | ✅ User settings |
| **Date-based Alerts** | ✅ Before/After triggers | ❌ Manual scheduling | ❌ Manual scheduling | ❌ Manual scheduling | ❌ Manual scheduling |
| **Value Change Detection** | ✅ Field-level monitoring | ❌ Manual comparison | ❌ Manual comparison | ❌ Manual comparison | ❌ Manual comparison |
| **Recipient Suggestions** | ✅ Context-aware | ❌ No suggestions | ❌ No suggestions | ❌ No suggestions | ❌ No suggestions |
| **Popup UI** | ✅ Context-aware popups | ❌ No popups | ❌ No popups | ❌ No popups | ❌ No popups |
| **License** | AGPL-3.0 | MIT | MIT | MIT | MIT |
| **Maintenance** | Active | Active | Active | Inactive | Active |

### Key differentiators

**django-silque-notifications** is unique in providing:

1. **True admin-first experience**: Configure everything through Django admin without writing code
2. **Multi-channel delivery**: Email, SMS, and WhatsApp in one system
3. **Intelligent recipient resolution**: Deep relational traversal with mappings and heuristics
4. **Smart triggers**: Date-based alerts and field change detection built-in
5. **Context-aware UI**: Popup forms that understand your model relationships
6. **Zero-code notification evolution**: Add new notification types without deployments

**django-notifications** excels at in-app notifications with live updates but requires significant coding for email/SMS and lacks admin configuration.

**pinax-notifications** provides email flexibility and user preferences but requires template creation and coding for each notification type.

Most other systems focus on either in-app notifications or simple email alerts, while `django-silque-notifications` is designed as a comprehensive, admin-driven notification platform for business applications.

## License

AGPL-3.0-or-later. By using or modifying this project (including over a network), you agree to share source under the same license and preserve notices.
