"""WSGI entry point for PythonAnywhere.

PythonAnywhere does not run Docker — it imports a WSGI callable from a file
you point it at in the Web tab. Paste the contents of this file into that
editor (it opens at /var/www/<username>_pythonanywhere_com_wsgi.py), replacing
everything already there, and change USERNAME below.

Why this host: it runs Flask and SQLite natively, the free tier needs no
credit card, and — unlike every free container host — the disk persists, so
listings and orders survive a redeploy instead of resetting.

One real limitation to know before relying on it: outbound network access on
the free tier is restricted to an allowlist, and Gmail's SMTP is not on it.
Mail will not send. The application already handles that: with no SMTP
configured it writes each message into instance/outbox/ as a .eml file, so
the invitation and reset flows still work end to end, you just read the link
out of the file rather than an inbox. Paid tiers lift the restriction.
"""

import os
import sys

USERNAME = "yourname"                      # <- your PythonAnywhere username
PROJECT = "/home/%s/logistic" % USERNAME   # where you cloned the repo

if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

# Everything the application reads at import time. There is no .env on this
# host, so they are set here — and nothing secret should be typed into a file
# you then commit, so keep this copy on the server only.
os.environ.setdefault("GLOBALTRADE_SECRET_KEY", "replace-with-a-long-random-string")
os.environ.setdefault("GLOBALTRADE_ADMIN_EMAIL", "you@example.com")
os.environ.setdefault("GLOBALTRADE_HTTPS", "1")   # PythonAnywhere terminates TLS

# Deliberately not set: GLOBALTRADE_DEMO_DATA. Turning it on seeds accounts
# whose passwords are published in app.py, one of which is an administrator.

from app import app as application   # noqa: E402  (path setup has to come first)
