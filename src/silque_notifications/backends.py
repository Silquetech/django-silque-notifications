from django.core.mail.backends.smtp import EmailBackend
from silque.models import ErrorLog, EmailLog
from django.contrib import messages
import requests
import traceback
import time

class SilqueEmailBackend(EmailBackend):
    def __init__(self, host=None, port=None, username=None, password=None,
                use_tls=None, fail_silently=None, use_ssl=None, timeout=None,
                ssl_keyfile=None, ssl_certfile=None,
                **kwargs):

        from silque.models import EmailConfiguration
        configuration = EmailConfiguration.get_solo()
 
        super(SilqueEmailBackend, self).__init__(
            host = configuration.host if host is None else host,
            port = configuration.port if port is None else port,
            username = configuration.username if username is None else username,
            password = configuration.password if password is None else password,
            use_tls = configuration.use_tls if use_tls is None else use_tls,
            fail_silently = configuration.fail_silently if fail_silently is None else fail_silently,
            use_ssl = configuration.use_ssl if use_ssl is None else use_ssl,
            timeout = configuration.timeout if timeout is None else timeout,
            ssl_keyfile = ssl_keyfile, # TODO: configuration.ssl_keyfile if ssl_keyfile is not None else ssl_keyfile,
            ssl_certfile = ssl_certfile, # TODO: configuration.ssl_certfile if ssl_certfile is not None else ssl_certfile,
            **kwargs)

    def send_messages(self, email_messages):
        """
        Send one or more EmailMessage objects and return the number of email
        messages sent.
        """

        if not email_messages:
            return 0
        with self._lock:
            new_conn_created = self.open()
            if not self.connection or new_conn_created is None:
                # We failed silently on open().
                # Trying to send would be pointless.
                return 0
            num_sent = 0
            for message in email_messages:
                recipients = '; '.join(message.recipients())
                email_record = EmailLog.objects.create(
                    recipients=recipients,
                    subject=message.subject, body=message.body,
                )
                
                try:
                    sent = self._send(message)
                    if sent:
                        num_sent += 1
                    
                    else:
                        email_record.sent_successfully = False
                        email_record.save()
                
                except Exception as e:
                    ErrorLog.objects.create(
                        error=f"[EMAIL-FAILED]: {str(e)}",
                        traceback=f"[RECIPIENTS]: {recipients}\n[SUBJECT]: {message.subject}\n[BODY]: {message.body}\n\n{traceback.format_exc()}",
                    )

            if new_conn_created:
                self.close()
        return num_sent