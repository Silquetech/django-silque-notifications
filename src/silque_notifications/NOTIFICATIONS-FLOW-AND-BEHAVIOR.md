# Silque Notifications: Flows & Behavior

This guide explains how the `silque_notifications` app behaves end‑to‑end: setup, admin flows, relational recipients, prioritization, evaluation, and delivery.

## 1) Setup at a glance

- Install and enable apps:
  - `INSTALLED_APPS`: `silque_notifications` (+ your models like `euser`)
- Configure Redis + Celery (broker/result backend) in `settings.py`:
  - `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, serializers set to `json`
- Optional relational mappings:
  - `S_NOTIFICATION_RELATIONAL_EMAIL_RECIPIENTS`
  - `S_NOTIFICATION_RELATIONAL_NUMBER_RECIPIENTS`
- Optional per‑model hints on your own models:
  - `NOTIFICATION_EMAIL_FIELDS = ["email", ...]`
  - `NOTIFICATION_NUMBER_FIELDS = ["mobile_number", ...]`

The app ships without external UI build steps and runs with default Django admin.

## 2) Admin flow (create/edit Notification)

- Choose a Model: select a NotificationModel‑derived model from the dropdown.
- Pick Channel:
  - E = Email (shows Email recipients UI)
  - S/W = SMS/WhatsApp (shows Number recipients UI)
- Choose Trigger (Send alert on):
  - V (Value Change): requires `value_change_field`
  - B/A (Before/After a date): requires `date_field` and non‑negative `alert_days`
  - N/U/D (New/Update/Delete): no extra inputs
- Add Recipients via M2M widgets:
  - Click “Add …Recipient via lookup” (or the + icon). A popup opens with implicit model context.
  - In the popup, select a By document field suggestion or type a dotted path manually; you can also set a direct email/number.
- Save: form validation enforces the minimum required inputs; model validation enforces the same server‑side. The model’s `save()` calls `full_clean()`.

## 3) Recipient admin popups (context‑aware)

- The Notification form passes `model_hint` + `_popup=1` into the recipient add popup.
- EmailRecipient/NumberRecipient admin forms use this context to show suggestions in `by_docfield`:
  - Direct fields on the selected model, if they exist (e.g., `doc.email`, `old_doc.email`).
  - Relational tokens for FKs/O2Os when likely email/number fields exist on the related model.
- If no suggestions fit, the `by_docfield` stays a text input so you can type a path.
- Saving the popup uses Django’s standard `dismissAddRelatedObjectPopup` to update the M2M on the parent form.

## 4) Relational recipients and mappings

- You can target recipients by dotted paths:
  - Direct: `doc.customer.email` or `old_doc.customer.email`
  - Relational token: `silque.doc.customer.supplier.Supplier ~ New Supplier`
    - `silque.doc` or `silque.old_doc` indicates which object to traverse.
    - `<customer>` is your FK/O2O field on the selected model.
    - `<supplier.Supplier>` identifies the related model.
- Mappings in settings tell the resolver which fields to try on reached models:

```python
S_NOTIFICATION_RELATIONAL_EMAIL_RECIPIENTS = {
    "supplier.Supplier": ["email_address"],
    "employee.Employee": ["email_address"],
    # Priority example: will try in order
    "silque_user.User": [("employee.email_address", "supplier.email_address")],
}
S_NOTIFICATION_RELATIONAL_NUMBER_RECIPIENTS = {
    "supplier.Supplier": ["mobile_number"],
    "employee.Employee": ["mobile_number"],
}
```

- Strings are used as‑is.
- Tuples/lists indicate priority order ("try these in sequence"). The current implementation tries all valid matches; if you want "first non‑empty only" within a tuple, you can switch to short‑circuiting.
- Non‑existent fields are skipped at runtime (logged) and are not shown as suggestions.

## 5) Heuristics and per‑model hints

- If no mapping is provided for a reached model, the resolver uses heuristics:
  - Email: `email`, `email_address`
  - Number: `mobile_number`, `phone`, `phone_number`, `mobile`, `contact_number`
- If the selected model itself has those fields, we also suggest direct paths (`doc.email`, `old_doc.email`, etc.).
- You can refine with per‑model hints on your own models:

```python
class Customer(models.Model):
    NOTIFICATION_EMAIL_FIELDS = ["primary_email", "billing_email"]
    NOTIFICATION_NUMBER_FIELDS = ["mobile", "office_phone"]
```

## 6) Conditions and templating

- Message/title templating supports: `{{ doc.* }}`, `{{ old_doc.* }}`, `{{ notif.* }}`
- Conditions (one per line): safe, restricted expression evaluation for simple boolean logic and comparisons.
- Examples:

```
doc.status == "APPROVED"
old_doc.amount != doc.amount
(notif.channel == "E") and (doc.total > 0)
```

## 7) Delivery and tasks

- On NotificationModel events, the app enqueues Celery tasks (email/SMS/WhatsApp) using Redis.
- Tasks resolve recipients by combining:
  - Direct recipients (`by_email`, `by_number`)
  - `by_docfield` dotted paths
  - Relational tokens expanded via mappings/heuristics/hints
- Invalid emails are filtered out; numbers are taken as strings. Errors are logged.

## 8) Validation & safety

- Form + model validation mirror each other:
  - Channel E requires at least one email recipient (direct or by_docfield).
  - Channel S/W requires at least one number recipient.
  - V requires `value_change_field`; B/A require `date_field` + `alert_days >= 0`.
- `save().full_clean()` ensures programmatic writes obey rules.
- Attribute resolution is safe; condition evaluator uses restricted AST (no `eval`).

## 9) UI/UX details

- Shippable admin: extends Django admin with minimal inline JS/CSS.
- Dark mode: CSS variables with live updates via MutationObserver.
- The M2M widgets gain “Add via lookup” buttons; default add icons also work. All popups carry `model_hint` & `_popup=1`.

## 10) Troubleshooting

- No suggestions on NumberRecipient:
  - Ensure the selected model has a number field or an FK/O2O to a mapped model; otherwise the field remains a text input.
- A mapped field doesn’t appear in UI:
  - The UI only shows real fields on the selected model and relational tokens. Mapped subfields are tried at runtime when a relational token is chosen.
- ExtendedUser mapping example:
  - If the actual field is `email`, use `"euser.ExtendedUser": ["email"]`. A non‑existent `email_address` won’t show in UI and will be skipped at runtime.

---

For examples, see `README.md` and `LibTest/settings.py`. This app is designed to work standalone, with clean fallbacks when optional integrations aren’t present.
