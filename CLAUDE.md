# HandShake

## What this application is

HandShake is a **logistics application that delivers goods between people**.
Someone posts an item. Someone else orders it. HandShake moves it between them:
the platform takes the order, holds the money, dispatches a courier, and records
the handoff at each end. **HandShake operates the delivery itself** — an
administrator assigns one of the platform's couriers, who collects from the
seller and delivers to the buyer. There is no peer-traveller matching and no
concept of a trip; the marketplace is the front door, and the delivery is the
product.

Read the interface through that lens. A listing is goods waiting to move. An
order starts a journey. A chat is two people arranging the details around it. A
confirmed email address and an administrator's approval are what make a stranger
safe to hand goods to. The product is **goods in motion**, and trust between
strangers is what makes it work.

This replaced an earlier rent / sell / swap marketplace. If you find rental
vocabulary anywhere — `price_unit`, `deposit_price`, a `'rent'` item type,
`return_item` — you are looking at the old product. Those columns are gone and
the compatibility shim that once kept old templates alive has been deleted.

## Access is granted, not self-served

**There is no open registration.** Anyone can ask for access, but only an
administrator can grant it.

- A prospective user submits an **access request** — who they are, how to reach
  them, and why they want in.
- They are emailed a link and must **confirm the address**. Until they do, the
  request is not something an administrator should spend time on.
- An **administrator** reviews the queue and approves or declines each one.
  Either way the applicant is emailed the outcome.
- Approval emails a single-use invitation, and only then does the person set a
  password and gain an account.
- `/login` works normally for people who already have accounts, and
  `/forgot-password` emails a single-use, two-hour reset link.

**There is no passport check.** There used to be, and it is gone: it wrote an
unvalidated file to disk from an unauthenticated route, it left declined
applicants' government ID on disk forever, and an administrator looking at a
phone photograph was never identity verification. A confirmable email address
replaced it — weaker as proof of who someone is, far stronger as proof that the
contact details work, and the only one of the two the system can actually
check. Do not reintroduce it.

**A fresh database has no accounts at all**, so `HANDSHAKE_ADMIN_EMAIL` creates
the first administrator on an empty user table — the only way into a new
deployment. Once any account exists it only promotes, never creates.

This is deliberate. The product asks strangers to hand real property to each
other, so the gate at the front door is a feature, not friction. Do not add a
public sign-up form, and do not let an unapproved request become an account by
any path.

## Stack

Flask (Python) with server-rendered Jinja templates, SQLAlchemy over SQLite, and
vanilla CSS and JavaScript. There is no build step and no frontend framework.

- `app.py` — routes, models and view logic
- `ai_logic.py` — the AI assistant
- `mailer.py` — sending email, with `smtplib` and nothing else. Unconfigured it
  writes `.eml` files into `instance/outbox/` instead of sending, so every flow
  can be walked without an SMTP account
- `instance/handshake.db` — SQLite database
- `templates/` — Jinja templates, all extending `base.html`
- `static/css/` — `variables.css` (design tokens), `base.css`, `style.css`,
  `profile.css`, `chat.css`
- `static/js/script.js` — all client-side behaviour
- `static/device_preview.html` — device preview harness; opens the running app
  inside accurate phone frames, several models at once
- `run_lan.py` — serves the app on the local network so it can be opened from a
  real phone; runs with `debug=False` deliberately, because the Werkzeug
  debugger is remote code execution and must never be exposed to a network
- `design_qa/` — visual QA screenshots, per page, per theme, per viewport
- `Dockerfile`, `render.yaml`, `.env.example` — deployment. Every setting is an
  environment variable, and `.env.example` says what breaks when each is unset

Keep it vanilla. Do not introduce jQuery, a CSS framework, or a bundler to solve
a problem that plain CSS and a few lines of JavaScript can solve.

## Design direction

`DESIGN.md` is the authoritative style reference and `static/css/variables.css`
holds its tokens. It is a near-monochrome editorial system: deep ink on white,
one warm clay accent used exactly once per page, architectural display
typography at extreme scale with very tight tracking, pill-shaped actions,
hard-edged panels, and **no drop shadows** — elevation comes from surface colour
shifts only.

`DESIGN.md` was extracted from an aviation brand, so it talks constantly about
jets and private travel. **Take its visual system, never its subject matter.**
HandShake moves ordinary goods for ordinary people, by road, across
Turkmenistan.

The home hero does carry an aircraft: a small airliner silhouette that crosses
the top of the page and leaves, trailing the wordmark. It is public-domain NIH
BioArt inlined as one vector path — see `static/img/CREDITS.txt` — and it is a
figure for distance covered, not a description of the fleet. An earlier version
used a photograph of a real Dassault Falcon 7X whose licence could not be
confirmed and whose livery belonged to a real company; that was withdrawn and
must not come back. If you replace the aircraft, replace it with something
whose licence you can state.

Mobile is a first-class target, not a fallback. At phone width the app presents
as a native-feeling application with a bottom tab bar, safe-area insets
respected, and tap targets of at least 44px.

## Conventions that must not break

Templates are wired to the Flask app by name. When editing markup, preserve
exactly:

- every Jinja block name and `{% extends %}` relationship
- every `url_for(...)` endpoint reference
- every form `action`, `method`, and field `name=` attribute
- every `id=` and class that `static/js/script.js` selects on

A page that looks right but posts the wrong field names is broken. Check
`app.py` for what each route expects before changing a form.

## Working on the UI

Every visual change gets verified in a real browser before it is called done —
run the app, load the page, look at it in both themes at desktop and phone
width, and check the console. Use `static/device_preview.html` to check several
phone models at once. Screenshots go in `design_qa/`, named
`NN-page__theme__viewport.png`.

Do not report a fix as working on the strength of the diff alone.
