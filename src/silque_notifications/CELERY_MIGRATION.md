# Django RQ to Celery Migration

This document outlines the migration from django_rq to Celery for the notification system.

## Changes Made

### 1. Dependencies
- **Added**: `celery==5.4.0` to `requirements.txt`
- **Removed**: All `django_rq` imports and usage

### 2. Configuration Files
- **Created**: `LibTest/celery.py` - Main Celery application configuration
- **Updated**: `LibTest/__init__.py` - Import Celery app for Django integration
- **Updated**: `LibTest/settings.py` - Added Celery configuration using Redis as broker

### 3. Task Definitions
- **Created**: `silque_notifications/tasks.py` - Celery task definitions:
  - `send_notification_task` - Main notification processing task
  - `send_email_task` - Email sending task
  - `send_sms_task` - SMS sending task
  - `send_whatsapp_task` - WhatsApp sending task

### 4. Code Updates
- **Updated**: `silque_notifications/models.py`
  - Replaced `django_rq.enqueue()` with Celery `delay()` calls
  - Added object serialization for task parameters
  - Improved error handling
  
- **Updated**: `silque_notifications/services.py`
  - Removed `django_rq` import
  - Replaced direct service method enqueuing with Celery task calls

### 5. Testing & Utilities
- **Created**: Management command `test_celery_notifications` for testing
- **Created**: Worker startup scripts for both Bash and PowerShell

## Configuration

Celery is configured to use Redis as both broker and result backend:

```python
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_RESULT_EXPIRES = 3600  # 1 hour
```

## Running Celery

### Start Worker (PowerShell)
```powershell
.\start_celery_worker.ps1
```

### Start Worker (Bash)
```bash
./start_celery_worker.sh
```

### Manual Start
```bash
celery -A LibTest worker --loglevel=info
```

## Testing

Test the notification system:

```bash
# Test email notification
python manage.py test_celery_notifications --email --to user@example.com

# Test SMS notification  
python manage.py test_celery_notifications --sms --to +1234567890
```

## Benefits of Migration

1. **Better Django Integration**: Celery integrates more naturally with Django
2. **Improved Monitoring**: Better task monitoring and debugging capabilities
3. **Enhanced Reliability**: More robust task retry and error handling
4. **Scalability**: Better support for distributed task processing
5. **Maintenance**: More active development and community support

## Task Flow

1. Model save/delete triggers notification check
2. Valid notifications are serialized and passed to `send_notification_task`
3. Task reconstructs objects and processes notifications
4. Individual service tasks are spawned for email/SMS/WhatsApp
5. Each service task handles the actual message sending with retry logic

## Error Handling

- All tasks include retry logic (max 3 retries, 60-second delay)
- Errors are logged to `ErrorLog` model
- Failed tasks don't break the main application flow
- Graceful fallback if Celery is unavailable
