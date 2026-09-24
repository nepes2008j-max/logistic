# BACKEND_CONTRACT.md

What the backend now offers and what it expects, written for the design pass
that updates the templates the backend agent is not allowed to touch.

Generated from the running application on 2026-09-20. Everything below was
verified by running it (`test_logistics_flow.py`, 147 checks, 0 failures).

---

## 1. What changed, in one paragraph

HandShake is no longer a rental marketplace. A person posts a **good for sale**
(`Item`), another person **orders** it and says where it has to arrive
(`Order`), pays, and that payment creates a **Delivery** that a courier walks
from `awaiting_pickup` to `delivered`. Every transition writes a
`DeliveryEvent`. Registration is gone: a stranger submits an `AccessRequest`,
an administrator approves it, and only then does an invitation let them set a
password and become a `User`.

---

## 2. Endpoints

### New

| Endpoint | Methods | URL | Who |
|---|---|---|---|
| `request_access` | GET, POST | `/request-access` | public |
| `activate` | GET, POST | `/activate/<token>` | public, one-time token |
| `place_order` | GET, POST | `/order/new/<int:item_id>` | any signed-in user but the item's owner |
| `orders` | GET | `/orders` | signed in |
| `order_detail` | GET | `/order/<int:order_id>` | buyer, seller, assigned courier, admin — everyone else gets **404** |
| `accept_order` | POST | `/order/<int:order_id>/accept` | seller |
| `reject_order` | POST | `/order/<int:order_id>/reject` | seller |
| `cancel_order` | POST | `/order/<int:order_id>/cancel` | buyer |
| `pay_order` | GET, POST | `/order/<int:order_id>/pay` | buyer |
| `delivery_detail` | GET | `/delivery/<int:delivery_id>` | same audience as the order |
| `courier_console` | GET | `/courier` | role `courier` or `admin` |
| `claim_delivery` | POST | `/delivery/<int:delivery_id>/claim` | courier |
| `delivery_pickup` | POST | `/delivery/<int:delivery_id>/pickup` | assigned courier / admin |
| `advance_delivery` | POST | `/delivery/<int:delivery_id>/advance` | assigned courier / admin |
| `delivery_dropoff` | POST | `/delivery/<int:delivery_id>/dropoff` | assigned courier / admin |
| `fail_delivery` | POST | `/delivery/<int:delivery_id>/fail` | assigned courier / admin |
| `return_delivery` | POST | `/delivery/<int:delivery_id>/return` | assigned courier / admin |
| `admin_dashboard` | GET | `/admin` | role `admin` |
| `admin_access_requests` | GET | `/admin/access-requests?status=pending\|approved\|rejected\|all` | admin |
| `approve_access_request` | POST | `/admin/access-requests/<int:request_id>/approve` | admin |
| `reject_access_request` | POST | `/admin/access-requests/<int:request_id>/reject` | admin |
| `admin_users` | GET | `/admin/users` | admin |
| `admin_set_role` | POST | `/admin/users/<int:user_id>/role` | admin |
| `admin_deliveries` | GET | `/admin/deliveries` | admin |
| `admin_assign_courier` | POST | `/admin/deliveries/<int:delivery_id>/assign` | admin |

### Changed

| Endpoint | What happened |
|---|---|
| `register` | Still exists at `/register` but is now **only a 302 to `/request-access`**. It is kept because `base.html:101,134` and `login.html:52` hardcode the path instead of calling `url_for`, so a rename would silently 404 rather than raise BuildError. It renders nothing. |
| `upload` | No longer reads `type` or `price_unit`. Reads `size_class` and `weight_kg` instead. `price` is now parsed to a float and must be greater than zero. `title` and `category` are now required. The view also passes `size_classes` to the template. |
| `rate_item` | Now writes `Review.target_user_id` (the item's owner), so `/profile` review lists are no longer permanently empty. |
| `dashboard`, `index`, `search` | Exclude items whose `status == 'withdrawn'`. |

### Retired but still routable (compatibility shims — see §7)

`buy_item`, `negotiate`, `accept_negotiation`, `decline_negotiation`,
`confirm_deal`, `process_negotiated_payment`, `return_item`.
All of these are now redirect-only. **Stop linking to them.**

### Never existed

`process_payment` — `payment.html:11` falls back to
`url_for('process_payment', item_id=item.id)` for a route that has never
existed in this codebase. See §5.

---

## 3. Form fields

Exact `name=` attributes. A form that posts the wrong names is silently ignored
or rejected.

### `POST /request-access`
| field | required | notes |
|---|---|---|
| `full_name` | yes | |
| `email` | yes | must contain `@` and a dot in the domain |
| `phone` | yes | |
| `neighborhood_id` | yes | a `Neighborhood.id` from `location_tree` |
| `age` | no | 16–120 if present |
| `reason` | no | free text |
| `passport_image` | yes | a `data:image/...;base64,...` data URL |

The response is deliberately identical whether the email is new, already
queued, or already an account. Do not add a "that email is taken" message.

### `POST /activate/<token>`
`password` (min 8), `confirm_password`.

### `POST /upload`
`title`, `category`, `price`, `neighborhood_id`, `size_class`
(`small|medium|large`), `weight_kg` (optional number), `description`,
`item_image` (file) or `camera_image` (data URL).
`type` and `price_unit` are **no longer read**.

### `POST /order/new/<item_id>`
`dest_neighborhood_id` (required), `dest_address_line` (required),
`dest_contact_phone` (required), `proposed_price` (optional number > 0).

### `POST /order/<id>/pay`
No fields. The button alone.

### Delivery
* `POST /delivery/<id>/pickup` → `code`
* `POST /delivery/<id>/dropoff` → `code`
* `POST /delivery/<id>/advance` → `status` (`in_transit` or `out_for_delivery`), `note` (optional)
* `POST /delivery/<id>/fail` → `note` (optional)
* `POST /delivery/<id>/claim`, `POST /delivery/<id>/return` → no fields

### Admin
* `POST /admin/access-requests/<id>/approve` → `review_note` (optional)
* `POST /admin/access-requests/<id>/reject` → `review_note` (optional)
* `POST /admin/users/<id>/role` → `role` (`member|courier|admin`)
* `POST /admin/deliveries/<id>/assign` → `courier_id` (empty string unassigns)

---

## 4. Model attributes templates may read

### `User`
`id, username, full_name, email, region, age, bio, rating, num_ratings,
passport_img, profile_pic, kyc_status, role, wallet_balance, items,
purchases, sales`

* **new:** `role` — `'member' | 'courier' | 'admin'`
* **new:** `is_admin`, `is_courier` (properties; `is_courier` is true for admins too)
* `passport_img` is now **nullable**
* `purchases` / `sales` are now lists of **`Order`**, not `Transaction`

### `Item`
`id, title, price, description, image_url, category, rating, num_ratings,
status, weight_kg, size_class, user_id, neighborhood_id, owner, neighborhood,
orders`

* **`price` is a `Float` now, not a string.** Format it —
  `{{ "%.2f"|format(item.price) }}` or `{{ '{:,g}'.format(item.price or 0) }}`.
  Printing it raw gives `200.0`.
* **new:** `status` — `'listed' | 'reserved' | 'sold' | 'withdrawn'`
* **new:** `size_class` — `'small' | 'medium' | 'large'`
* **new:** `weight_kg` — float or `None`
* **new:** `is_orderable` (property, `status == 'listed'`)
* `location_label`, `pickup_label` — the full "Neighbourhood, District, Velayat" string
* **gone:** `price_unit`, `deposit_price`, `type`, `is_available` (see §7)

### `Order`
`id, buyer_id, seller_id, item_id, item_price, proposed_price, delivery_fee,
service_fee, total, status, dest_neighborhood_id, dest_address_line,
dest_contact_phone, created_at, updated_at, buyer, seller, item,
dest_neighborhood, delivery`

* `status` — `'placed' | 'accepted' | 'rejected' | 'cancelled' | 'paid' | 'completed'`
* `agreed_price` (property) — `proposed_price` if the buyer countered, otherwise `item_price`
* `is_negotiated` (property)
* `destination_label` (property)
* `delivery` is `None` until the order is paid for

### `Delivery`
`id, order_id, origin_neighborhood_id, dest_neighborhood_id, courier_id,
status, pickup_code, dropoff_code, picked_up_at, delivered_at, eta_date, fee,
created_at, updated_at, order, courier, origin_neighborhood,
dest_neighborhood, events`

* `status` — `'awaiting_pickup' | 'picked_up' | 'in_transit' |
  'out_for_delivery' | 'delivered' | 'failed' | 'returned'`
* `next_statuses` (property) — the transitions the backend will accept right now
* `is_open` (property)
* **`pickup_code` must only ever be shown to the seller**, `dropoff_code`
  **only to the buyer**. Both are `None` once used. An admin page may show
  neither; the courier types them in, never reads them off the screen.

### `DeliveryEvent`
`id, delivery_id, status, note, actor_id, created_at, actor`. Append-only.

### `AccessRequest`
`id, full_name, email, phone, region, neighborhood_id, age, reason,
passport_img, status, created_at, reviewed_at, reviewed_by_id, review_note,
invite_token, invite_expires_at, invite_used_at, neighborhood, reviewed_by`

* `invite_state` (property) — `'pending' | 'rejected' | 'live' | 'used' | 'expired'`
* `invite_is_live` (property)

### `PlatformAccount`
`id, name, balance, escrow_balance`. One row, named `handshake`.

### Gone entirely
`Transaction` and every attribute on it (`amount`, `commission`,
`deposit_amount`, `total_amount`, `duration`, `timestamp`). The table is
preserved in the database as `transaction_legacy` and is not mapped.

### Available in every template (context processor)
`pending_chat_request_count` (unchanged) and the new
`pending_access_request_count` — zero unless the viewer is an admin.

---

## 5. The exact edits the design pass must make

These are in files the backend agent was told not to touch.

### `base.html`
1. **Line 101 and 134** hardcode `/register`. They still work (302), but they
   should say `{{ url_for('request_access') }}` and read "Request access",
   not "Sign up" / "Get verified".
2. **Line 129** — the footer note still says "The deposit stays with us until
   the item arrives, and the hand-off is closed in person with a scan."
   Replace with something true: HandShake holds the goods price until the
   courier records the handover, and the handover is closed with a code, not a
   scan.
3. Add an **Admin** entry to the user dropdown, shown only when
   `current_user.is_admin`, pointing at `{{ url_for('admin_dashboard') }}` —
   optionally with the `pending_access_request_count` badge.
4. Add a **Courier** entry shown when `current_user.is_courier`, pointing at
   `{{ url_for('courier_console') }}`.
5. Add an **Orders** entry pointing at `{{ url_for('orders') }}` for signed-in
   users. There is currently no way to reach `/orders` from the chrome.
6. `<title>` default is "HandShake | Buy, Sell, Rent" — drop "Rent".

### `login.html`
* **Line 10** — "Your wallet, your deposits and your open chats are where you
  left them." There are no deposits. Say wallet and chats.
* **Line 52** hardcodes `/register`. Point it at
  `{{ url_for('request_access') }}` and word it as *request access*, because
  self-service sign-up no longer exists.

### `dashboard.html`
* **Line 12** — `{{ item.type|capitalize }}` badge. `item.type` is a shim that
  always returns `'sell'`. Replace the badge with `item.status`, or with
  `item.size_class`, or delete it.
* **Line 19** — `{{ item.price }} TMT {% if item.type == 'rent' %}<span>/ …`
  Replace the whole line with `{{ "%.2f"|format(item.price) }} TMT`.
* **Lines 61, 140, 145** — the explainer band still describes renting, holding
  a deposit for "the whole time the item is out", and a QR code starting a
  clock. Rewrite for: order it, we collect it from the seller, we carry it,
  you give the courier a code at the door, the seller is paid then.

### `index.html`
* **Line 132** — same `item.type` badge as dashboard.
* **Line 139** — the `{% if item.type == 'rent' %}/ day{% endif %}` suffix.
  The float formatting there is already correct; only the rental suffix and the
  badge need to go.

### `item_detail.html`
* **Line 63** — `item.type` tag.
* **Line 65** — `{% if item.is_available %}`; use `{% if item.is_orderable %}`
  and show `item.status` when it is not.
* **Lines 77–78** — price figure and "per {{ 'item' if … }}". Should be
  `{{ "%.2f"|format(item.price) }} TMT` with no unit line.
* **Lines 114–129** — the whole duration/buy block. Replace the
  `url_for('buy_item', …)` link with
  `{{ url_for('place_order', item_id=item.id) }}` and the label with
  "Order this and have it delivered". Delete the duration input.
* **Lines 148–160** — the negotiate form posts to `url_for('negotiate', …)`
  with `proposed_price` and `duration`. The offer now lives on the order form:
  either delete this block, or make it a GET link to
  `{{ url_for('place_order', item_id=item.id) }}`.
* **Line 166** — "You need a verified account to rent, buy or message a
  seller… `url_for('register')`". Rewrite; point at `request_access`.
* **Lines 232–263** — the inline duration JavaScript. Delete it; the elements
  it selects are gone.
* Worth adding: `item.size_class`, `item.weight_kg` and the pickup point, since
  they drive the delivery fee the buyer is about to be quoted.

### `upload.html`
* **Lines 28–35** — the "Rent, sell or swap" select (`name="type"`). Delete it
  and replace with a **size** select, `name="size_class"`, options
  `small` / `medium` / `large`. The view passes `size_classes` for this.
* **Line 45** — the `price_unit` select. Delete it.
* Add an optional `name="weight_kg"` number input.
* **Line ~173** of the inline script does
  `document.querySelector('select[name="type"]').addEventListener(...)`.
  That will throw a TypeError the moment the select is removed. Delete those
  four lines along with the `price-unit-select` reference.
* Copy: "Post an item" → posting a good for sale; "where the hand-off happens"
  is now the **pickup point** the courier collects from.

### `profile.html`
* **Lines 168, 204, 238** filter `user.sales` / `user.purchases` on the old
  status words. The new `Order` statuses are `placed`, `accepted`, `rejected`,
  `cancelled`, `paid`, `completed`. Update all three `selectattr` lists:
  incoming → `['placed']`, outgoing → `['placed', 'accepted']`,
  history → `['paid', 'completed', 'cancelled']`.
* **Line 184** — `{{ tx.amount }} for {{ tx.duration }} day(s)`. Use
  `{{ "%.2f"|format(tx.agreed_price) }}` and drop the duration entirely.
* **Lines 190–194** — `accept_negotiation`, `decline_negotiation` and the
  `showQR(...)` button. Replace with POST forms to
  `{{ url_for('accept_order', order_id=tx.id) }}` and
  `{{ url_for('reject_order', order_id=tx.id) }}`, and a link to
  `{{ url_for('order_detail', order_id=tx.id) }}`.
* **Lines 252–256** — duration and the `rental-timer` block. Delete; there is
  no rental clock. Show `tx.delivery.status` instead.
* **Line 263** — `tx.total_amount` → `tx.total`.
* **Line 264** — `tx.timestamp` → `tx.created_at`.
* **Line 301** and the QR modal — delete the whole modal. The QR is gone. The
  seller now reads a `pickup_code` to the courier; it is shown on
  `order_detail.html` and `delivery_detail.html`.
* **Lines 326–333** of the inline script drive the rental timer. Delete.
* **Line 89** — "HandShake takes 5% of every completed rental". The 5% is now
  the service fee on the goods price of an order, and it is charged at payment,
  not at completion.
* **Line 241** — the heading "Your rentals". These are orders.

### `payment.html`
* **This file is now dead.** Nothing renders it; the payment page is
  `order_payment.html`. Either delete it or, if you want to keep the visual
  design, port the markup into `order_payment.html` and delete this one.
* Its line 11 `url_for('process_payment', item_id=item.id)` fallback points at
  a route that has never existed and would raise `BuildError` if that branch
  were ever taken. The plan called for deleting it; it is in your file, not
  the backend's.

### `register.html`
* Also dead — `/register` is a redirect and never renders a template. Delete
  it, or cannibalise its five-step passport capture for
  `request_access.html`. Its line 101 still offers a "HandShake rental
  agreement", which is another reason not to leave it lying around.

### New templates the backend created (yours to style)
`request_access.html`, `activate.html`, `order_new.html`, `orders.html`,
`order_detail.html`, `order_payment.html`, `delivery_detail.html`,
`courier_console.html`, `admin_dashboard.html`, `admin_access_requests.html`,
`admin_users.html`, `admin_deliveries.html`.

They use only classes that already exist in the stylesheets and carry no
bespoke styling. Restyle them freely. Preserve every `url_for`, every form
`action`/`method`, and every field `name=`.

---

## 6. Money

```
total = agreed_price + delivery_fee + service_fee
service_fee   = 5% of the agreed price
delivery_fee  = (15 + distance) x size
                distance: same neighbourhood +0, same district +10,
                          same velayat +25, different velayat +60
                size:     small x1.0, medium x1.6, large x2.5
```

On payment the buyer's wallet is debited the whole total. The goods price goes
to `PlatformAccount.escrow_balance` and the two fees to
`PlatformAccount.balance`. **The seller is paid on `delivered`, not on
payment.** On `returned` the buyer gets the whole total back and the platform
gives up the fees.

`sum(User.wallet_balance) + PlatformAccount.balance +
PlatformAccount.escrow_balance` is invariant. `flask --app app money-check`
prints it.

Copy that says the deposit is held until the item comes back is now wrong
everywhere it appears.

---

## 7. Temporary compatibility shims — delete these

At the very bottom of `app.py`, under a banner reading
`TEMPLATE COMPATIBILITY SHIMS -- DELETE THIS WHOLE BLOCK`, there are:

* read-only properties `Item.type` (always `'sell'`), `Item.price_unit`
  (always `None`), `Item.deposit_price` (always `0.0`), `Item.is_available`
* read-only properties `Order.amount`, `Order.total_amount`, `Order.timestamp`,
  `Order.duration` (always `1`)
* redirect-only routes `buy_item`, `negotiate`, `accept_negotiation`,
  `decline_negotiation`, `confirm_deal`, `process_negotiated_payment`,
  `return_item`

They exist for exactly one reason: without them the templates listed in §5
raise `UndefinedError` and `BuildError` instead of rendering, and the app would
have been handed over broken. **They are not part of the domain.** When the
last edit in §5 lands, delete the whole block and run:

```
grep -rn "price_unit\|deposit\|is_available\|item\.type\|duration\|buy_item\|negotiat\|confirm_deal\|return_item\|process_payment\|total_amount\|rental\|rent " templates/
```

It should come back empty.

---

## 8. Running it

```
cd /home/nepes/Desktop/PROJECTS/new_design_handshake
.venv/bin/python run_lan.py 5601

# first administrator
.venv/bin/flask --app app create-admin nepes@handshake.com
.venv/bin/flask --app app create-courier maral@handshake.com
# or, at boot:  HANDSHAKE_ADMIN_EMAIL=someone@example.com

# the end-to-end suite, against a throwaway copy of the database
.venv/bin/python test_logistics_flow.py
```

Two new environment variables, both optional:
`HANDSHAKE_SECRET_KEY` (the session key is otherwise the old hardcoded string)
and `HANDSHAKE_DATABASE_URI` (so a test never touches `instance/handshake.db`).
