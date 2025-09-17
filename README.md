# django-silque-notifications

Flexible, admin-driven notifications for Django with Celery/Redis, relational recipient resolution, and safe templating.

- Admin-first UX: define notifications in Django admin
- Channels: Email (E), SMS (S), WhatsApp (W)
- Triggers: New/Update/Delete, Value Change, Before/After date
- Recipients: direct email/number, document fields, and relational mappings
- Celery + Redis: scalable task queue with retries
- Safe expressions and Jinja-like templating

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

See `src/silque_notifications/NOTIFICATIONS-FLOW-AND-BEHAVIOR.md` for the full, detailed guide. Highlights:

- Recipient resolution supports:
  - Direct: by email/number
  - Dotted paths: `doc.customer.email`, `old_doc.customer.email`
  - Relational tokens: `silque.doc.customer.supplier.Supplier ~ New Supplier`
- Heuristics and per-model hints discover likely email/number fields
- Safe condition evaluation and templating
- Celery tasks perform delivery with retries

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

## License

AGPL-3.0-or-later. By using or modifying this project (including over a network), you agree to share source under the same license and preserve notices.
