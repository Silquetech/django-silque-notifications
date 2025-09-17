from django.test import TestCase
from django.core.exceptions import ValidationError

from .models import Notification, EmailRecipient, NumberRecipient
from .forms import NotificationAdminForm
from .services import NotificationService


class Dummy:
	"""Simple attribute container for parse/condition tests."""
	def __init__(self, **kwargs):
		for k, v in kwargs.items():
			setattr(self, k, v)


class NotificationModelValidationTests(TestCase):
	def test_value_change_requires_field(self):
		notif = Notification(
			is_active=True,
			channel='E',
			title='Test',
			message='Msg',
			model='euser ~ ExtendedUser ~ User',
			send_alert_on='V',  # Value Change
			value_change_field=None,
		)
		with self.assertRaises(ValidationError) as ctx:
			notif.full_clean()
		self.assertIn('value_change_field', ctx.exception.message_dict)

	def test_days_before_requires_date_and_alert_days(self):
		notif = Notification(
			is_active=True,
			channel='E',
			title='Test',
			message='Msg',
			model='euser ~ ExtendedUser ~ User',
			send_alert_on='B',  # Days Before
			date_field=None,
			alert_days=None,
		)
		with self.assertRaises(ValidationError) as ctx:
			notif.full_clean()
		self.assertIn('date_field', ctx.exception.message_dict)
		self.assertIn('alert_days', ctx.exception.message_dict)

	def test_alert_days_must_be_non_negative_int(self):
		# Negative
		notif = Notification(
			is_active=True,
			channel='E',
			title='Test',
			message='Msg',
			model='euser ~ ExtendedUser ~ User',
			send_alert_on='A',
			date_field='created ~ Created',
			alert_days=-1,
		)
		with self.assertRaises(ValidationError) as ctx:
			notif.full_clean()
		self.assertIn('alert_days', ctx.exception.message_dict)

		# Non-int
		notif.alert_days = 'x'
		with self.assertRaises(ValidationError) as ctx2:
			notif.full_clean()
		self.assertIn('alert_days', ctx2.exception.message_dict)


class NotificationAdminFormValidationTests(TestCase):
	def setUp(self):
		# Common valid base data
		self.base = {
			'is_active': 'on',
			'title': 'Hello',
			'message': 'World',
			'channel': 'E',
			'model': 'euser ~ ExtendedUser ~ User',
			'send_alert_on': 'N',
			'value_change_field': '',
			'date_field': '',
			'alert_days': '',
			'conditions': '',
		}

	def test_email_channel_requires_some_email_recipient(self):
		form = NotificationAdminForm(data=self.base)
		self.assertFalse(form.is_valid())
		# Error appears on field now that relational helpers moved
		self.assertIn('email_recipients', form.errors)

	# Provide a direct EmailRecipient
		r = EmailRecipient.objects.create(by_email='user@example.com')
		data = self.base | {'email_recipients': [str(r.id)]}
		form2 = NotificationAdminForm(data=data)
		self.assertTrue(form2.is_valid())

	def test_value_change_requires_value_field(self):
		data = self.base | {
			'send_alert_on': 'V',
		}
		form = NotificationAdminForm(data=data)
		self.assertFalse(form.is_valid())
		self.assertIn('value_change_field', form.errors)

	def test_days_before_requires_date_and_days(self):
		data = self.base | {
			'send_alert_on': 'B',
			'date_field': '',
			'alert_days': '',
		}
		form = NotificationAdminForm(data=data)
		self.assertFalse(form.is_valid())
		self.assertIn('date_field', form.errors)
		self.assertIn('alert_days', form.errors)


class NotificationServiceUnitTests(TestCase):
	def test_parse_string_replaces_doc_old_notif(self):
		old_obj = Dummy(username='old', email='old@example.com')
		new_obj = Dummy(username='new', email='new@example.com')
		notif = Dummy(title='T')
		svc = NotificationService(old_obj, new_obj, [])

		src = 'Hello {{ doc.username }} and {{ old_doc.email }} / {{ notif.title }}'
		out = svc.parse_string(notif, src)
		self.assertIn('new', out)
		self.assertIn('old@example.com', out)
		self.assertIn('T', out)

	def test_meets_conditions_true_and_false(self):
		old_obj = Dummy(is_active=False)
		new_obj = Dummy(is_active=True)
		svc = NotificationService(old_obj, new_obj, [])

		class N:
			conditions = 'doc.is_active == True'  # one line -> true

		class N2:
			conditions = 'doc.is_active == False'  # -> false

		self.assertTrue(svc.meets_conditions(N()))
		self.assertFalse(svc.meets_conditions(N2()))

	def test_get_email_recipients_from_direct_and_docfield(self):
		# Build a Notification with one direct email and one by docfield
		n = Notification.objects.create(
			is_active=True,
			channel='E',
			title='T',
			message='M',
			model='euser ~ ExtendedUser ~ User',
			send_alert_on='N',
		)
		direct = EmailRecipient.objects.create(by_email='user@example.com')
		bydoc = EmailRecipient.objects.create(by_docfield='doc.email')
		n.email_recipients.add(direct, bydoc)

		new_obj = Dummy(email='new@example.com')
		svc = NotificationService(None, new_obj, [n])
		emails = svc.get_email_recipients(n)
		self.assertIn('user@example.com', emails)
		self.assertIn('new@example.com', emails)

	def test_get_number_recipients_from_direct_and_docfield(self):
		n = Notification.objects.create(
			is_active=True,
			channel='S',
			title='T',
			message='M',
			model='euser ~ ExtendedUser ~ User',
			send_alert_on='N',
		)
		direct = NumberRecipient.objects.create(by_number='1234567890')
		bydoc = NumberRecipient.objects.create(by_docfield='doc.phone')
		n.number_recipients.add(direct, bydoc)

		new_obj = Dummy(phone='5550001111')
		svc = NotificationService(None, new_obj, [n])
		nums = svc.get_number_recipients(n)
		self.assertIn('1234567890', nums)
		self.assertIn('5550001111', nums)

