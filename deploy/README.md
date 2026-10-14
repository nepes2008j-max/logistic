# Putting Global Trade somewhere real

"Real" here means it stays up when the laptop is closed, which the Cloudflare
quick tunnel does not — that serves from this machine and dies with it.

Every option below needs **you** to create the account. That is the one step
that cannot be automated away, and it is deliberate: signing up is a decision
about terms and billing, not a build step.

## What was already tried, so nobody repeats it

| | Outcome |
|---|---|
| **Render** | Demands a card even on the `$0` plan — the deploy button opens a Stripe dialog asking for "a temporary authorization for $1 USD". The whole service was configured and ready; it stops there. `render.yaml` in the repo root still works if you ever accept that. |
| **Hugging Face Spaces** | Docker Spaces are PRO-only now. The new-Space page says it outright: "Gradio and Docker Spaces require a paid plan." Static Spaces stay free and cannot run Flask. |
| **Cloudflare quick tunnel** | Works, and is what is running today — but it serves from this laptop and the URL changes on every restart. |

## PythonAnywhere — the recommended one

Free, no card, and the only free host in this list where **the database
survives a redeploy**. It runs Flask and SQLite natively, which is exactly
what this application is.

1. Sign up at **pythonanywhere.com** → "Create a Beginner account".
2. **Consoles → Bash**, then:
   ```bash
   git clone https://github.com/nepes2008j-max/logistic.git
   cd logistic
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
3. **Web → Add a new web app → Manual configuration → Python 3.x**.
4. Set **Virtualenv** to `/home/<username>/logistic/.venv`.
5. Open the **WSGI configuration file** link and replace its contents with
   `deploy/pythonanywhere_wsgi.py` from this repo, changing `USERNAME` and the
   secret key.
6. Under **Static files**, map URL `/static/` to
   `/home/<username>/logistic/static/`. Without this every stylesheet and
   photograph 404s and the site renders as unstyled text.
7. **Reload**. You are at `https://<username>.pythonanywhere.com`.
8. Read the log — the first boot prints the generated administrator password
   once, and that is the only time it is shown.

Mail will not send: the free tier's outbound allowlist excludes Gmail's SMTP.
Messages land in `instance/outbox/` as `.eml` files instead, so the invitation
and password-reset flows still work; you read the link out of the file.

## Koyeb — if you would rather use the Dockerfile

Takes `Dockerfile` unchanged. Sign in with GitHub at **app.koyeb.com**, create
a Web Service from `nepes2008j-max/logistic`, and set `GLOBALTRADE_ADMIN_EMAIL`
and `GLOBALTRADE_SECRET_KEY`. Check the plan is the free one before deploying —
their terms move, and this note may already be out of date by the time you
read it.

Its free tier has no persistent disk, so the database resets on every
redeploy. The administrator bootstrap rebuilds a working login each time, so
the site is never locked, but listings and orders do not accumulate.

## Whatever you pick

- Never set `GLOBALTRADE_DEMO_DATA`. It seeds accounts whose passwords are in
  `app.py`, and one of them is an administrator.
- Set `GLOBALTRADE_SECRET_KEY` to something long and random. Unset, the app
  generates one per machine, which is fine for one process and wrong the
  moment a host runs two.
- Set `GLOBALTRADE_HTTPS=1` once TLS is in front, so the session cookie is
  marked Secure. Setting it without TLS stops sessions working entirely.
- `GLOBALTRADE_ADMIN_EMAIL` is the only way into a fresh database, because
  there is no public sign-up.
