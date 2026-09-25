"""Sending real email, with the standard library and nothing else.

There is no Flask-Mail here and no API client. `smtplib` and `email.message`
ship with Python, they speak to every SMTP server anyone would use, and adding
a dependency to format a string and open a socket would be worse.

Configuration is entirely environment variables, because credentials must not
live in the repository:

    HANDSHAKE_SMTP_HOST      smtp.gmail.com
    HANDSHAKE_SMTP_PORT      587 (STARTTLS, the default) or 465 (implicit TLS)
    HANDSHAKE_SMTP_USER      the account that authenticates
    HANDSHAKE_SMTP_PASSWORD  its password — for Gmail this must be an App
                             Password, not the account password
    HANDSHAKE_MAIL_FROM      what recipients see; defaults to SMTP_USER
    HANDSHAKE_MAIL_REPLY_TO  optional

With no host configured nothing is sent. Messages are written to
`instance/outbox/` as complete .eml files instead and the send is reported as
deferred, so the whole flow — request, approval, invitation, reset — can be
walked end to end on a laptop with no mail account, and the link that would
have been posted is sitting in a file you can open.

Sending happens on a worker thread. An SMTP handshake across the internet
takes seconds, and no user should watch a page hang while their own
confirmation email is delivered.
"""

import os
import re
import smtplib
import ssl
import threading
import queue
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr

# Deliberately permissive. This rejects the things that are certainly not
# addresses — no @, whitespace, no dot in the domain — and leaves the rest to
# the only test that actually proves an address: sending to it and seeing
# whether the person clicks. Clever regexes here reject real addresses.
_ADDRESS = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def looks_like_address(value):
    """A cheap sanity check, not a verification."""
    return bool(_ADDRESS.match((value or "").strip()))


class Mailer:
    def __init__(self, instance_path):
        self.host = os.environ.get("HANDSHAKE_SMTP_HOST", "").strip()
        self.port = int(os.environ.get("HANDSHAKE_SMTP_PORT", "587"))
        self.user = os.environ.get("HANDSHAKE_SMTP_USER", "").strip()
        self.password = os.environ.get("HANDSHAKE_SMTP_PASSWORD", "")
        self.sender = (os.environ.get("HANDSHAKE_MAIL_FROM")
                       or self.user or "handshake@localhost")
        self.reply_to = os.environ.get("HANDSHAKE_MAIL_REPLY_TO", "").strip()
        self.outbox = os.path.join(instance_path, "outbox")
        self.timeout = int(os.environ.get("HANDSHAKE_SMTP_TIMEOUT", "20"))

        self._queue = queue.Queue()
        self._worker = threading.Thread(
            target=self._drain, name="handshake-mailer", daemon=True
        )
        self._worker.start()

    @property
    def configured(self):
        return bool(self.host)

    def describe(self):
        if self.configured:
            return "SMTP %s:%d as %s" % (self.host, self.port, self.user or "anonymous")
        return "no SMTP configured — mail is written to %s" % self.outbox

    def send(self, to, subject, body, reply_to=None):
        """Queue one plain-text message. Returns False if the address is junk."""
        to = (to or "").strip()
        if not looks_like_address(to):
            return False

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr(("HandShake", parseaddr(self.sender)[1] or self.sender))
        message["To"] = to
        message["Date"] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
        message["Message-ID"] = make_msgid(domain="handshake.local")
        if reply_to or self.reply_to:
            message["Reply-To"] = reply_to or self.reply_to
        # Transactional mail, and this one in particular carries a login link.
        # Ask the well-behaved bulk filters to leave it alone.
        message["Auto-Submitted"] = "auto-generated"
        message.set_content(body)

        self._queue.put(message)
        return True

    def _drain(self):
        while True:
            message = self._queue.get()
            try:
                self._deliver(message)
            except Exception as exc:                      # noqa: BLE001
                # A failed send must never take the process down, and the
                # message must not vanish silently: it lands in the outbox so
                # there is something to look at.
                print("[mail] delivery failed for %s: %s" % (message["To"], exc))
                try:
                    self._spool(message, prefix="failed")
                except OSError:
                    pass
            finally:
                self._queue.task_done()

    def _deliver(self, message):
        if not self.configured:
            path = self._spool(message)
            print("[mail] not configured; wrote %s" % path)
            return

        context = ssl.create_default_context()
        if self.port == 465:
            server = smtplib.SMTP_SSL(self.host, self.port,
                                      timeout=self.timeout, context=context)
        else:
            server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
        try:
            server.ehlo()
            if self.port != 465:
                server.starttls(context=context)
                server.ehlo()
            if self.user:
                server.login(self.user, self.password)
            server.send_message(message)
            print("[mail] sent %r to %s" % (message["Subject"], message["To"]))
        finally:
            try:
                server.quit()
            except Exception:                              # noqa: BLE001
                pass

    def _spool(self, message, prefix="mail"):
        os.makedirs(self.outbox, exist_ok=True)
        stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")
        safe = re.sub(r"[^a-zA-Z0-9._-]", "_", message["To"] or "unknown")
        path = os.path.join(self.outbox, "%s-%s-%s.eml" % (prefix, stamp, safe))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(message.as_string())
        return path
