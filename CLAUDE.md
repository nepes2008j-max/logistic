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
verified passport is what makes a stranger safe to hand goods to. The product is
**goods in motion**, and trust between strangers is what makes it work.

This replaced an earlier rent / sell / swap marketplace. If you find rental
vocabulary anywhere — `price_unit`, `deposit_price`, a `'rent'` item type,
`return_item` — you are looking at the old product. The backend no longer has
those columns; a small compatibility shim at the bottom of `app.py` keeps
not-yet-migrated templates alive and is marked for deletion.

## Access is granted, not self-served

**There is no open registration.** Anyone can ask for access, but only an
administrator can grant it.

- A prospective user submits an **access request** — who they are, how to reach
  them, and why they want in — and that request sits in a queue.
- An **administrator** reviews the queue and approves or declines each one.
- Approval issues a single-use invitation, and only then does the person set a
  password and gain an account.
- `/login` continues to work normally for people who already have accounts.

This is deliberate. The product asks strangers to hand real property to each
other, so the gate at the front door is a feature, not friction. Do not add a
public sign-up form, and do not let an unapproved request become an account by
any path.

## Stack

Flask (Python) with server-rendered Jinja templates, SQLAlchemy over SQLite, and
vanilla CSS and JavaScript. There is no build step and no frontend framework.

- `app.py` — routes, models and view logic
- `ai_logic.py` — the AI assistant
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
HandShake moves ordinary goods for ordinary people; the interface should not
dress that up as luxury air charter. An earlier attempt at an aircraft hero was
removed for exactly this reason: a private jet claimed a scale and a class of
service this product does not have. The backend now genuinely models origin,
destination, couriers and a delivery pipeline, but that is vans and handoffs
across Turkmenistan, not aviation. Imagery should show the real thing — the
goods, the handoff, the people — not a metaphor borrowed from another industry.

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
