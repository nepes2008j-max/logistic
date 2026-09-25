---
title: HandShake
emoji: 📦
colorFrom: gray
colorTo: blue
sdk: docker
app_port: 8000
pinned: false
---

# HandShake

A logistics marketplace. Someone posts an item, someone else orders it, and the
platform moves it between them: it takes the order, holds the money in escrow,
dispatches a courier, and records the handoff at each end. The marketplace is
the front door; the delivery is the product.

Built for Turkmenistan — the geography, the velayats and their districts, are
real and seeded.

## What it does

**Access is granted, not self-served.** There is no open registration. Someone
asks for access, confirms their email address from their inbox, and an
administrator approves or declines. Approval emails a single-use invitation,
and only then does an account exist.

**An order is a journey.** The seller accepts, the buyer pays into escrow, an
administrator assigns a courier. The courier collects against a code the seller
reads out and hands over against a code the buyer reads out. The money reaches
the seller at that second handoff and not before. Every transition is written
to an append-only event log.

**Delivery is priced, not guessed.** A base fee plus a distance band — same
neighbourhood, same district, same velayat, or across the country — multiplied
by the parcel's size class.

## Running it

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python seed_demo_data.py        # optional: demo listings with photos
HANDSHAKE_ADMIN_EMAIL=you@example.com .venv/bin/python run_lan.py 5500
```

That serves on every interface so a real phone on the same Wi-Fi can open it,
and prints the address. `HANDSHAKE_ADMIN_EMAIL` creates the first administrator
on an empty database — without it a fresh install has no way in, because there
is no public sign-up.

`python app.py` binds to localhost only. Neither entry point turns on the
Werkzeug debugger, which is an interactive Python console for anyone who can
reach a traceback.

Copy `.env.example` to `.env` to configure mail and the rest; it documents what
each variable is for and what breaks when it is unset. With no SMTP configured
the application writes its emails into `instance/outbox/` as `.eml` files
rather than sending them, so the invitation and password-reset flows can be
walked end to end without a mail account.

## Deploying

`Dockerfile` runs it under gunicorn as a non-root user. Mount a volume on
`/app/instance` or the SQLite database and the uploaded photographs vanish on
redeploy. `render.yaml` is a Render blueprint for the same thing.

## Stack

Flask, SQLAlchemy over SQLite, server-rendered Jinja, and vanilla CSS and
JavaScript. No build step, no frontend framework, no bundler. The design system
lives in `DESIGN.md` and its tokens in `static/css/variables.css`.

## Tests

```bash
HANDSHAKE_DATABASE_URI=sqlite:////tmp/handshake_test.db .venv/bin/python test_logistics_flow.py
```

154 checks against a throwaway copy of the database: the access flow including
replayed and expired invitations, a full order across two accounts, the
delivery pipeline, and that the sum of every wallet plus the platform account
does not drift by a single tenga across any of it.
