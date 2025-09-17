"""
Management command to test Celery notification tasks.
"""
from django.core.management.base import BaseCommand

from silque_notifications.tasks import send_email_task, send_sms_task


class Command(BaseCommand):
    help = 'Test Celery notification tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            action='store_true',
            help='Test email notification task',
        )
        parser.add_argument(
            '--sms',
            action='store_true',
            help='Test SMS notification task',
        )
        parser.add_argument(
            '--to',
            type=str,
            help='Recipient email or phone number',
        )

    def handle(self, *args, **options):
        if options['email'] and options['to']:
            self.stdout.write('Enqueuing test email task...')
            task = send_email_task.delay(
                'Test Email from Celery',
                'This is a test email sent via Celery task.',
                [options['to']]
            )
            self.stdout.write(
                self.style.SUCCESS(f'Email task enqueued with ID: {task.id}')
            )
        
        elif options['sms'] and options['to']:
            self.stdout.write('Enqueuing test SMS task...')
            task = send_sms_task.delay(
                [options['to']],
                'This is a test SMS sent via Celery task.'
            )
            self.stdout.write(
                self.style.SUCCESS(f'SMS task enqueued with ID: {task.id}')
            )
        
        else:
            self.stdout.write(
                self.style.ERROR(
                    'Please specify --email or --sms with --to recipient'
                )
            )
