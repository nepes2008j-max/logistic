"""End-to-end checks for the logistics pivot.

Runs against a throwaway copy of the real database so nothing in
instance/handshake.db is touched:

    HANDSHAKE_DATABASE_URI=sqlite:////tmp/handshake_test.db \
        .venv/bin/python test_logistics_flow.py

It exercises, and fails loudly on:

  * the access flow end to end, plus a rejected request, a replayed token and
    an expired token
  * a non-admin hitting /admin
  * a full order across two accounts to a different velayat
  * money conservation across the whole order
  * a re-submitted payment
  * one DeliveryEvent row for every transition
"""

import base64
import os
import sys
import shutil
import tempfile
from datetime import datetime, timedelta

FAILURES = []
CHECKS = 0

# A 1x1 PNG, enough to stand in for a passport capture.
PNG_1PX = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000"
    "000a49444154789c6360000002000100ffff03000006000557bfabd40000000049454e"
    "44ae426082"
)).decode()
PASSPORT_DATA_URL = "data:image/png;base64," + PNG_1PX


def check(label, condition, detail=""):
    global CHECKS
    CHECKS += 1
    if condition:
        print("  ok    %s" % label)
    else:
        print("  FAIL  %s  %s" % (label, detail))
        FAILURES.append(label)


def section(title):
    print()
    print("== %s" % title)


def main():
    scratch = tempfile.mkdtemp(prefix="handshake_test_")
    scratch_db = os.path.join(scratch, "handshake_test.db")
    source_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "handshake.db")
    if os.path.exists(source_db):
        shutil.copy(source_db, scratch_db)
    os.environ["HANDSHAKE_DATABASE_URI"] = "sqlite:///" + scratch_db
    print("scratch database: %s" % scratch_db)

    import app as handshake
    a = handshake.app
    db = handshake.db
    a.config["TESTING"] = True
    a.config["WTF_CSRF_ENABLED"] = False
    # Passport captures go to the scratch directory, never into the real
    # static/uploads/passports folder.
    a.config["UPLOAD_FOLDER"] = os.path.join(scratch, "passports")
    os.makedirs(a.config["UPLOAD_FOLDER"], exist_ok=True)

    def money_total():
        with a.app_context():
            wallets = db.session.query(
                db.func.coalesce(db.func.sum(handshake.User.wallet_balance), 0.0)
            ).scalar()
            account = handshake.PlatformAccount.query.filter_by(
                name=handshake.PLATFORM_ACCOUNT_NAME
            ).first()
            return round(wallets + account.balance + account.escrow_balance, 2)

    def login(client, email, password):
        return client.post("/login", data={"email": email, "password": password},
                           follow_redirects=True)

    # -- fixtures -----------------------------------------------------------
    with a.app_context():
        admin = handshake.User.query.filter_by(email="nepes@handshake.com").first()
        admin.role = "admin"
        admin.password_hash = handshake.generate_password_hash("nepes123", method="scrypt")
        seller = handshake.User.query.filter_by(email="aman@handshake.com").first()
        seller.password_hash = handshake.generate_password_hash("aman123", method="scrypt")
        buyer = handshake.User.query.filter_by(email="selbi@handshake.com").first()
        buyer.password_hash = handshake.generate_password_hash("selbi123", method="scrypt")
        buyer.kyc_status = "verified"
        buyer.wallet_balance = 5000.0
        courier = handshake.User.query.filter_by(email="maral@handshake.com").first()
        courier.role = "courier"
        courier.password_hash = handshake.generate_password_hash("maral123", method="scrypt")
        outsider = handshake.User.query.filter_by(email="arslan@handshake.com").first()
        outsider.password_hash = handshake.generate_password_hash("arslan123", method="scrypt")

        origin = handshake.find_seeded_neighborhood("Ashgabat", "Berkararlyk", "Central Ashgabat")
        destination = handshake.find_seeded_neighborhood("Mary", "Bayramaly", "Bayramaly")
        item = handshake.Item(
            title="Test parcel, large", price=120.0, category="tools",
            size_class="large", weight_kg=30.0, status="listed",
            neighborhood_id=origin.id, user_id=seller.id,
            description="A test listing.", image_url="/static/uploads/items/none.jpg",
        )
        db.session.add(item)
        db.session.commit()
        admin_id, seller_id, buyer_id, courier_id = admin.id, seller.id, buyer.id, courier.id
        item_id, destination_id, origin_id = item.id, destination.id, origin.id
        dest_velayat = destination.district.velayat.name
        origin_velayat = origin.district.velayat.name

    section("geography")
    check("destination is in a different velayat from the origin",
          dest_velayat != origin_velayat, "%s vs %s" % (origin_velayat, dest_velayat))
    with a.app_context():
        empty = [v["name"] for v in handshake.get_location_tree() if not v["districts"]]
        check("every velayat has districts", not empty, "empty: %s" % empty)

    section("delivery pricing")
    with a.app_context():
        o = handshake.Neighborhood.query.get(origin_id)
        d = handshake.Neighborhood.query.get(destination_id)
        same_district = handshake.find_seeded_neighborhood(
            "Ashgabat", "Berkararlyk", "Ataturk Street")
        same_velayat = handshake.find_seeded_neighborhood(
            "Ashgabat", "Kopetdag", "Archabil Avenue")
        check("same neighborhood, small = 15.00",
              handshake.calculate_delivery_fee(o, o, "small") == 15.0,
              handshake.calculate_delivery_fee(o, o, "small"))
        check("same district, small = 25.00",
              handshake.calculate_delivery_fee(o, same_district, "small") == 25.0,
              handshake.calculate_delivery_fee(o, same_district, "small"))
        check("same velayat, medium = (15+25)*1.6 = 64.00",
              handshake.calculate_delivery_fee(o, same_velayat, "medium") == 64.0,
              handshake.calculate_delivery_fee(o, same_velayat, "medium"))
        check("cross velayat, large = (15+60)*2.5 = 187.50",
              handshake.calculate_delivery_fee(o, d, "large") == 187.5,
              handshake.calculate_delivery_fee(o, d, "large"))

    # -- access flow ---------------------------------------------------------
    section("access flow")
    public = a.test_client()
    r = public.get("/register")
    check("/register is a 302", r.status_code == 302, r.status_code)
    check("/register points at /request-access",
          "/request-access" in (r.headers.get("Location") or ""), r.headers.get("Location"))
    check("/request-access renders", public.get("/request-access").status_code == 200)

    r = public.post("/request-access", data={
        "full_name": "Ayna Test", "email": "ayna.test@example.com",
        "phone": "+99365000000", "age": "28", "reason": "I send parcels to Mary.",
        "neighborhood_id": str(destination_id),
    }, follow_redirects=True)
    check("access request accepted", r.status_code == 200)
    with a.app_context():
        req = handshake.AccessRequest.query.filter_by(email="ayna.test@example.com").first()
        check("access request stored", req is not None)
        check("request is pending", req and req.status == "pending", req and req.status)
        check("no account created yet",
              handshake.User.query.filter_by(email="ayna.test@example.com").first() is None)
        # The passport capture is gone. A confirmable email address replaced
        # it, so what must exist now is an unspent verification token.
        check("verification token issued", req and bool(req.verify_token))
        check("email not confirmed yet", req and req.email_verified_at is None)
        check("no passport stored", req and not req.passport_img)
        check("region derived from the chosen neighborhood",
              req and req.region == dest_velayat, req and req.region)
        request_id = req.id

    # a second request for the same address must not queue twice
    public.post("/request-access", data={
        "full_name": "Ayna Test", "email": "ayna.test@example.com",
        "phone": "+99365000000", "neighborhood_id": str(destination_id),
       
    }, follow_redirects=True)
    with a.app_context():
        check("duplicate request is not queued twice",
              handshake.AccessRequest.query.filter_by(
                  email="ayna.test@example.com", status="pending").count() == 1)

    section("admin authorisation")
    member = a.test_client()
    login(member, "selbi@handshake.com", "selbi123")
    r = member.get("/admin")
    check("non-admin is redirected away from /admin", r.status_code == 302, r.status_code)
    check("non-admin lands somewhere other than /admin",
          "/admin" not in (r.headers.get("Location") or ""), r.headers.get("Location"))
    check("non-admin is refused the access queue",
          member.get("/admin/access-requests").status_code == 302)
    check("non-admin cannot approve",
          member.post("/admin/access-requests/%d/approve" % request_id).status_code == 302)
    with a.app_context():
        check("the request is still pending after that attempt",
              handshake.AccessRequest.query.get(request_id).status == "pending")
    anonymous = a.test_client()
    check("anonymous is refused /admin", anonymous.get("/admin").status_code == 302)

    admin_client = a.test_client()
    login(admin_client, "nepes@handshake.com", "nepes123")
    r = admin_client.get("/admin")
    check("admin reaches /admin", r.status_code == 200, r.status_code)
    r = admin_client.get("/admin/access-requests")
    check("the request shows in the queue",
          r.status_code == 200 and b"ayna.test@example.com" in r.data, r.status_code)

    r = admin_client.post("/admin/access-requests/%d/approve" % request_id,
                          data={"review_note": "Passport looks fine."}, follow_redirects=True)
    check("approve returns 200", r.status_code == 200)
    with a.app_context():
        req = handshake.AccessRequest.query.get(request_id)
        check("request is approved", req.status == "approved", req.status)
        check("an invite token was issued", bool(req.invite_token))
        ttl_days = (req.invite_expires_at - datetime.utcnow()).total_seconds() / 86400.0
        check("the invite expires in 7 days", 6.9 < ttl_days <= 7.0, ttl_days)
        check("still no account before activation",
              handshake.User.query.filter_by(email="ayna.test@example.com").first() is None)
        good_token = req.invite_token

    check("activation page renders", public.get("/activate/%s" % good_token).status_code == 200)
    check("a bogus token is refused", public.get("/activate/not-a-real-token").status_code == 302)

    r = public.post("/activate/%s" % good_token,
                    data={"password": "short", "confirm_password": "short"},
                    follow_redirects=True)
    with a.app_context():
        check("a short password does not create an account",
              handshake.User.query.filter_by(email="ayna.test@example.com").first() is None)

    r = public.post("/activate/%s" % good_token,
                    data={"password": "a-good-password", "confirm_password": "a-good-password"},
                    follow_redirects=True)
    check("activation returns 200", r.status_code == 200)
    with a.app_context():
        new_user = handshake.User.query.filter_by(email="ayna.test@example.com").first()
        check("the account now exists", new_user is not None)
        check("the approved account is verified",
              new_user and new_user.kyc_status == "verified", new_user and new_user.kyc_status)
        check("the new account is a plain member",
              new_user and new_user.role == "member", new_user and new_user.role)

    new_client = a.test_client()
    r = login(new_client, "ayna.test@example.com", "a-good-password")
    check("the new account can sign in", r.status_code == 200 and b"Invalid email" not in r.data)

    section("invitations that must be refused")
    r = public.post("/activate/%s" % good_token,
                    data={"password": "another-password", "confirm_password": "another-password"},
                    follow_redirects=False)
    check("a used token is refused", r.status_code == 302, r.status_code)
    with a.app_context():
        check("no second account from the replayed token",
              handshake.User.query.filter_by(email="ayna.test@example.com").count() == 1)

    # rejected request
    public2 = a.test_client()
    public2.post("/request-access", data={
        "full_name": "Rejected Person", "email": "rejected@example.com",
        "phone": "+99365111111", "neighborhood_id": str(destination_id),
       
    }, follow_redirects=True)
    with a.app_context():
        rejected = handshake.AccessRequest.query.filter_by(email="rejected@example.com").first()
        rejected_id = rejected.id
    admin_client.post("/admin/access-requests/%d/reject" % rejected_id,
                      data={"review_note": "Not this time."}, follow_redirects=True)
    with a.app_context():
        rejected = handshake.AccessRequest.query.get(rejected_id)
        check("the rejected request holds no token", rejected.invite_token is None)
        check("the rejected request is marked rejected", rejected.status == "rejected")
        # force a token onto it to prove status alone blocks activation
        rejected.invite_token = "forced-token-for-a-rejected-request"
        rejected.invite_expires_at = datetime.utcnow() + timedelta(days=7)
        db.session.commit()
    r = public2.post("/activate/forced-token-for-a-rejected-request",
                     data={"password": "a-good-password", "confirm_password": "a-good-password"},
                     follow_redirects=False)
    check("a rejected request cannot activate even holding a token", r.status_code == 302)
    with a.app_context():
        check("no account for the rejected person",
              handshake.User.query.filter_by(email="rejected@example.com").first() is None)

    # expired invitation
    public3 = a.test_client()
    public3.post("/request-access", data={
        "full_name": "Late Person", "email": "late@example.com",
        "phone": "+99365222222", "neighborhood_id": str(destination_id),
       
    }, follow_redirects=True)
    with a.app_context():
        late = handshake.AccessRequest.query.filter_by(email="late@example.com").first()
        late_id = late.id
    admin_client.post("/admin/access-requests/%d/approve" % late_id, follow_redirects=True)
    with a.app_context():
        late = handshake.AccessRequest.query.get(late_id)
        late.invite_expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
        late_token = late.invite_token
        check("an expired invite reports itself expired", late.invite_state == "expired",
              late.invite_state)
    r = public3.post("/activate/%s" % late_token,
                     data={"password": "a-good-password", "confirm_password": "a-good-password"},
                     follow_redirects=False)
    check("an expired token is refused", r.status_code == 302)
    with a.app_context():
        check("no account from the expired token",
              handshake.User.query.filter_by(email="late@example.com").first() is None)

    # -- order flow ----------------------------------------------------------
    section("order flow")
    money_before = money_total()
    print("  money in the system before the order: %.2f" % money_before)

    buyer_client = a.test_client()
    login(buyer_client, "selbi@handshake.com", "selbi123")
    seller_client = a.test_client()
    login(seller_client, "aman@handshake.com", "aman123")
    courier_client = a.test_client()
    login(courier_client, "maral@handshake.com", "maral123")
    outsider_client = a.test_client()
    login(outsider_client, "arslan@handshake.com", "arslan123")

    check("the order form renders",
          buyer_client.get("/order/new/%d" % item_id).status_code == 200)

    r = buyer_client.post("/order/new/%d" % item_id, data={
        "dest_neighborhood_id": str(destination_id),
        "dest_address_line": "12 Bayramaly Street, flat 4",
        "dest_contact_phone": "+99365999999",
    }, follow_redirects=False)
    check("placing the order redirects", r.status_code == 302, r.status_code)
    with a.app_context():
        order = handshake.Order.query.filter_by(item_id=item_id).order_by(
            handshake.Order.id.desc()).first()
        check("the order exists", order is not None)
        order_id = order.id
        check("the order is 'placed'", order.status == "placed", order.status)
        check("delivery fee is the cross-velayat large price (187.50)",
              order.delivery_fee == 187.5, order.delivery_fee)
        check("service fee is 5% of the goods price (6.00)",
              order.service_fee == 6.0, order.service_fee)
        check("total is goods + delivery + service (313.50)",
              order.total == 313.5, order.total)
        check("no delivery exists before payment", order.delivery is None)

    check("a stranger cannot read the order",
          outsider_client.get("/order/%d" % order_id).status_code == 404)
    check("the buyer can read the order",
          buyer_client.get("/order/%d" % order_id).status_code == 200)
    check("the seller can read the order",
          seller_client.get("/order/%d" % order_id).status_code == 200)
    check("a stranger cannot accept the order",
          outsider_client.post("/order/%d/accept" % order_id).status_code == 404)
    check("the buyer cannot accept their own order",
          buyer_client.post("/order/%d/accept" % order_id).status_code == 404)
    with a.app_context():
        check("the order is still 'placed' after those attempts",
              handshake.Order.query.get(order_id).status == "placed")

    check("paying before acceptance is refused",
          buyer_client.post("/order/%d/pay" % order_id, follow_redirects=False).status_code == 302)
    with a.app_context():
        check("the order did not become paid",
              handshake.Order.query.get(order_id).status == "placed",
              handshake.Order.query.get(order_id).status)
    check("money did not move", money_total() == money_before,
          "%.2f vs %.2f" % (money_total(), money_before))

    seller_client.post("/order/%d/accept" % order_id, follow_redirects=True)
    with a.app_context():
        check("the seller accepted the order",
              handshake.Order.query.get(order_id).status == "accepted",
              handshake.Order.query.get(order_id).status)

    with a.app_context():
        buyer_wallet_before = handshake.User.query.get(buyer_id).wallet_balance
        seller_wallet_before = handshake.User.query.get(seller_id).wallet_balance
        account_before = handshake.PlatformAccount.query.filter_by(
            name=handshake.PLATFORM_ACCOUNT_NAME).first()
        platform_fees_before = account_before.balance
        platform_escrow_before = account_before.escrow_balance

    r = buyer_client.post("/order/%d/pay" % order_id, follow_redirects=False)
    check("payment redirects", r.status_code == 302, r.status_code)
    with a.app_context():
        order = handshake.Order.query.get(order_id)
        check("the order is paid", order.status == "paid", order.status)
        check("the item is reserved", order.item.status == "reserved", order.item.status)
        check("a delivery was created", order.delivery is not None)
        delivery_id = order.delivery.id if order.delivery else None
        check("the delivery is awaiting pickup",
              order.delivery and order.delivery.status == "awaiting_pickup")
        check("a pickup code exists", order.delivery and bool(order.delivery.pickup_code))
        check("a dropoff code exists", order.delivery and bool(order.delivery.dropoff_code))
        check("the pickup and dropoff codes differ",
              order.delivery and order.delivery.pickup_code != order.delivery.dropoff_code)
        check("an ETA was set", order.delivery and order.delivery.eta_date is not None)
        check("the buyer was debited the full total",
              round(handshake.User.query.get(buyer_id).wallet_balance, 2)
              == round(buyer_wallet_before - 313.5, 2),
              handshake.User.query.get(buyer_id).wallet_balance)
        check("the seller has NOT been paid yet",
              handshake.User.query.get(seller_id).wallet_balance == seller_wallet_before)
        account = handshake.PlatformAccount.query.filter_by(
            name=handshake.PLATFORM_ACCOUNT_NAME).first()
        check("the goods price is in escrow",
              round(account.escrow_balance - platform_escrow_before, 2) == 120.0,
              account.escrow_balance)
        check("the fees are on the platform balance",
              round(account.balance - platform_fees_before, 2) == round(187.5 + 6.0, 2),
              account.balance)
        check("one delivery event was written",
              len(order.delivery.events) == 1, len(order.delivery.events))
    check("money is conserved after payment", money_total() == money_before,
          "%.2f vs %.2f" % (money_total(), money_before))

    section("double submission")
    r = buyer_client.post("/order/%d/pay" % order_id, follow_redirects=False)
    check("the second payment redirects rather than charging", r.status_code == 302)
    with a.app_context():
        check("the buyer was charged exactly once",
              round(handshake.User.query.get(buyer_id).wallet_balance, 2)
              == round(buyer_wallet_before - 313.5, 2),
              handshake.User.query.get(buyer_id).wallet_balance)
        check("still exactly one delivery",
              handshake.Delivery.query.filter_by(order_id=order_id).count() == 1)
        account = handshake.PlatformAccount.query.filter_by(
            name=handshake.PLATFORM_ACCOUNT_NAME).first()
        check("escrow was not doubled",
              round(account.escrow_balance - platform_escrow_before, 2) == 120.0,
              account.escrow_balance)
    check("money is still conserved", money_total() == money_before,
          "%.2f vs %.2f" % (money_total(), money_before))

    # -- delivery pipeline ---------------------------------------------------
    section("delivery pipeline")
    check("a stranger cannot open the delivery",
          outsider_client.get("/delivery/%d" % delivery_id).status_code == 404)
    check("the buyer can open the delivery",
          buyer_client.get("/delivery/%d" % delivery_id).status_code == 200)
    check("a plain member is refused the courier console",
          buyer_client.get("/courier").status_code == 302)
    check("the courier reaches the console",
          courier_client.get("/courier").status_code == 200)

    courier_client.post("/delivery/%d/claim" % delivery_id, follow_redirects=True)
    with a.app_context():
        check("the courier now holds the delivery",
              handshake.Delivery.query.get(delivery_id).courier_id == courier_id)

    with a.app_context():
        d = handshake.Delivery.query.get(delivery_id)
        pickup_code, dropoff_code = d.pickup_code, d.dropoff_code

    courier_client.post("/delivery/%d/pickup" % delivery_id,
                        data={"code": "WRONG1"}, follow_redirects=True)
    with a.app_context():
        check("a wrong pickup code does not move the delivery",
              handshake.Delivery.query.get(delivery_id).status == "awaiting_pickup")

    # A non-ASCII paste used to reach secrets.compare_digest, which raises
    # TypeError on non-ASCII strings, so a doorstep typo became a 500.
    r = courier_client.post("/delivery/%d/pickup" % delivery_id,
                            data={"code": "\u041f\u0420\u0418\u0412\u0415\u0422"},
                            follow_redirects=False)
    check("a non-ASCII pickup code is refused, not a 500",
          r.status_code == 302, r.status_code)
    r = courier_client.post("/delivery/%d/pickup" % delivery_id,
                            data={"code": ""}, follow_redirects=False)
    check("an empty pickup code is refused", r.status_code == 302, r.status_code)
    with a.app_context():
        check("neither attempt moved the delivery",
              handshake.Delivery.query.get(delivery_id).status == "awaiting_pickup")

    courier_client.post("/delivery/%d/dropoff" % delivery_id,
                        data={"code": dropoff_code}, follow_redirects=True)
    with a.app_context():
        check("a handover cannot be recorded before pickup",
              handshake.Delivery.query.get(delivery_id).status == "awaiting_pickup")
        check("the seller was not paid by that attempt",
              handshake.User.query.get(seller_id).wallet_balance == seller_wallet_before)

    courier_client.post("/delivery/%d/pickup" % delivery_id,
                        data={"code": pickup_code}, follow_redirects=True)
    with a.app_context():
        d = handshake.Delivery.query.get(delivery_id)
        check("pickup confirmed", d.status == "picked_up", d.status)
        check("picked_up_at was set", d.picked_up_at is not None)
        check("the pickup code was consumed", d.pickup_code is None)

    courier_client.post("/delivery/%d/pickup" % delivery_id,
                        data={"code": pickup_code}, follow_redirects=True)
    with a.app_context():
        check("the pickup code cannot be replayed",
              handshake.Delivery.query.get(delivery_id).status == "picked_up")

    courier_client.post("/delivery/%d/advance" % delivery_id,
                        data={"status": "out_for_delivery"}, follow_redirects=True)
    with a.app_context():
        check("the pipeline cannot be skipped",
              handshake.Delivery.query.get(delivery_id).status == "picked_up",
              handshake.Delivery.query.get(delivery_id).status)

    courier_client.post("/delivery/%d/advance" % delivery_id,
                        data={"status": "in_transit"}, follow_redirects=True)
    with a.app_context():
        check("in transit", handshake.Delivery.query.get(delivery_id).status == "in_transit")

    courier_client.post("/delivery/%d/advance" % delivery_id,
                        data={"status": "out_for_delivery"}, follow_redirects=True)
    with a.app_context():
        check("out for delivery",
              handshake.Delivery.query.get(delivery_id).status == "out_for_delivery")

    check("a stranger cannot drive the delivery",
          outsider_client.post("/delivery/%d/dropoff" % delivery_id,
                               data={"code": dropoff_code}).status_code == 302)
    with a.app_context():
        check("that attempt changed nothing",
              handshake.Delivery.query.get(delivery_id).status == "out_for_delivery")

    courier_client.post("/delivery/%d/dropoff" % delivery_id,
                        data={"code": "WRONG2"}, follow_redirects=True)
    with a.app_context():
        check("a wrong dropoff code does not complete the delivery",
              handshake.Delivery.query.get(delivery_id).status == "out_for_delivery")
        check("the seller still has not been paid",
              handshake.User.query.get(seller_id).wallet_balance == seller_wallet_before)

    courier_client.post("/delivery/%d/dropoff" % delivery_id,
                        data={"code": dropoff_code}, follow_redirects=True)
    with a.app_context():
        d = handshake.Delivery.query.get(delivery_id)
        order = handshake.Order.query.get(order_id)
        check("delivered", d.status == "delivered", d.status)
        check("delivered_at was set", d.delivered_at is not None)
        check("the dropoff code was consumed", d.dropoff_code is None)
        check("the order is completed", order.status == "completed", order.status)
        check("the item is sold", order.item.status == "sold", order.item.status)
        check("the seller was paid the goods price on delivery",
              round(handshake.User.query.get(seller_id).wallet_balance, 2)
              == round(seller_wallet_before + 120.0, 2),
              handshake.User.query.get(seller_id).wallet_balance)
        account = handshake.PlatformAccount.query.filter_by(
            name=handshake.PLATFORM_ACCOUNT_NAME).first()
        check("escrow is back where it started",
              round(account.escrow_balance - platform_escrow_before, 2) == 0.0,
              account.escrow_balance)
        check("the platform kept its fees",
              round(account.balance - platform_fees_before, 2) == 193.5, account.balance)

        statuses = [event.status for event in d.events]
        check("one event per transition",
              statuses == ["awaiting_pickup", "awaiting_pickup", "picked_up",
                           "in_transit", "out_for_delivery", "delivered"],
              statuses)
        check("every event has an actor", all(e.actor_id for e in d.events))
        check("every event has a timestamp", all(e.created_at for e in d.events))

    check("money is conserved across the whole order", money_total() == money_before,
          "%.2f vs %.2f" % (money_total(), money_before))

    # -- the failed / returned branch ---------------------------------------
    section("failed and returned refunds the buyer")
    with a.app_context():
        origin = handshake.Neighborhood.query.get(origin_id)
        item2 = handshake.Item(
            title="Second test parcel", price=50.0, category="books",
            size_class="small", status="listed",
            neighborhood_id=origin.id, user_id=seller_id,
            description="Another test listing.", image_url="/static/uploads/items/none.jpg",
        )
        db.session.add(item2)
        db.session.commit()
        item2_id = item2.id
    before_return = money_total()
    buyer_client.post("/order/new/%d" % item2_id, data={
        "dest_neighborhood_id": str(destination_id),
        "dest_address_line": "12 Bayramaly Street",
        "dest_contact_phone": "+99365999999",
    }, follow_redirects=True)
    with a.app_context():
        order2 = handshake.Order.query.filter_by(item_id=item2_id).first()
        order2_id = order2.id
    seller_client.post("/order/%d/accept" % order2_id, follow_redirects=True)
    with a.app_context():
        buyer_before_return = handshake.User.query.get(buyer_id).wallet_balance
    buyer_client.post("/order/%d/pay" % order2_id, follow_redirects=True)
    with a.app_context():
        delivery2 = handshake.Order.query.get(order2_id).delivery
        delivery2_id = delivery2.id
        code2 = delivery2.pickup_code
    courier_client.post("/delivery/%d/claim" % delivery2_id, follow_redirects=True)
    courier_client.post("/delivery/%d/pickup" % delivery2_id,
                        data={"code": code2}, follow_redirects=True)
    courier_client.post("/delivery/%d/advance" % delivery2_id,
                        data={"status": "in_transit"}, follow_redirects=True)
    courier_client.post("/delivery/%d/advance" % delivery2_id,
                        data={"status": "out_for_delivery"}, follow_redirects=True)
    courier_client.post("/delivery/%d/fail" % delivery2_id,
                        data={"note": "Nobody at the address."}, follow_redirects=True)
    with a.app_context():
        check("the delivery is marked failed",
              handshake.Delivery.query.get(delivery2_id).status == "failed")
        check("a failed attempt moves no money", money_total() == before_return,
              "%.2f vs %.2f" % (money_total(), before_return))
    courier_client.post("/delivery/%d/return" % delivery2_id, follow_redirects=True)
    with a.app_context():
        d2 = handshake.Delivery.query.get(delivery2_id)
        check("the delivery is returned", d2.status == "returned", d2.status)
        check("the order was cancelled",
              handshake.Order.query.get(order2_id).status == "cancelled")
        check("the item is back on the shelf",
              handshake.Item.query.get(item2_id).status == "listed")
        check("the buyer was made whole",
              round(handshake.User.query.get(buyer_id).wallet_balance, 2)
              == round(buyer_before_return, 2),
              handshake.User.query.get(buyer_id).wallet_balance)
        check("the return is on the audit trail",
              [e.status for e in d2.events][-1] == "returned")
    check("money is conserved across the returned order",
          money_total() == before_return, "%.2f vs %.2f" % (money_total(), before_return))

    # -- the high value gate -------------------------------------------------
    section("the high-value gate is reachable now")
    with a.app_context():
        unverified = handshake.User.query.filter_by(email="arslan@handshake.com").first()
        unverified.kyc_status = "processing"
        item3 = handshake.Item(
            title="Expensive parcel", price=900.0, category="tech",
            size_class="small", status="listed",
            neighborhood_id=origin_id, user_id=seller_id,
            description="Over the threshold.", image_url="/static/uploads/items/none.jpg",
        )
        db.session.add(item3)
        db.session.commit()
        item3_id = item3.id
    outsider_client.post("/order/new/%d" % item3_id, data={
        "dest_neighborhood_id": str(destination_id),
        "dest_address_line": "Somewhere",
        "dest_contact_phone": "+99365000001",
    }, follow_redirects=True)
    with a.app_context():
        check("an unverified buyer cannot order over 100 TMT",
              handshake.Order.query.filter_by(item_id=item3_id).count() == 0)
        verified = handshake.User.query.filter_by(email="selbi@handshake.com").first()
        check("a verified buyer is not blocked by the gate",
              verified.kyc_status == "verified")
    buyer_client.post("/order/new/%d" % item3_id, data={
        "dest_neighborhood_id": str(destination_id),
        "dest_address_line": "Somewhere",
        "dest_contact_phone": "+99365000001",
    }, follow_redirects=True)
    with a.app_context():
        check("a verified buyer can order over 100 TMT",
              handshake.Order.query.filter_by(item_id=item3_id).count() == 1)

    # -- the trust layer still bites ----------------------------------------
    section("blocking stops an order, not just a message")
    with a.app_context():
        blocked_item = handshake.Item(
            title="Item from a blocked seller", price=30.0, category="books",
            size_class="small", status="listed", neighborhood_id=origin_id,
            user_id=seller_id, description="x", image_url="/static/uploads/items/none.jpg")
        db.session.add(blocked_item)
        db.session.add(handshake.BlockedUser(blocker_id=buyer_id, blocked_id=seller_id))
        db.session.commit()
        blocked_item_id = blocked_item.id
    buyer_client.post("/order/new/%d" % blocked_item_id, data={
        "dest_neighborhood_id": str(destination_id),
        "dest_address_line": "Somewhere", "dest_contact_phone": "+99365000002",
    }, follow_redirects=True)
    with a.app_context():
        check("a blocked seller's listing cannot be ordered",
              handshake.Order.query.filter_by(item_id=blocked_item_id).count() == 0)
        handshake.BlockedUser.query.filter_by(
            blocker_id=buyer_id, blocked_id=seller_id).delete()
        db.session.commit()

    section("an item with no seller cannot be ordered")
    with a.app_context():
        orphan = handshake.Item(
            title="Orphan listing", price=10.0, category="books",
            size_class="small", status="listed", neighborhood_id=origin_id,
            user_id=None, description="x", image_url="/static/uploads/items/none.jpg")
        db.session.add(orphan)
        db.session.commit()
        orphan_id = orphan.id
    r = buyer_client.post("/order/new/%d" % orphan_id, data={
        "dest_neighborhood_id": str(destination_id),
        "dest_address_line": "Somewhere", "dest_contact_phone": "+99365000003",
    }, follow_redirects=False)
    check("an ownerless listing is refused rather than crashing",
          r.status_code == 302, r.status_code)
    with a.app_context():
        check("no order was written for the ownerless listing",
              handshake.Order.query.filter_by(item_id=orphan_id).count() == 0)

    # -- every page still renders -------------------------------------------
    section("pages render")
    pages = [
        ("/", public), ("/market", public), ("/search?q=camera", public),
        ("/login", public), ("/request-access", public), ("/forgot-password", public),
        ("/item/%d" % item_id, buyer_client), ("/orders", buyer_client),
        ("/order/%d" % order_id, buyer_client), ("/delivery/%d" % delivery_id, buyer_client),
        ("/profile/%d" % buyer_id, buyer_client), ("/profile/%d" % seller_id, buyer_client),
        ("/chat", buyer_client), ("/upload", buyer_client), ("/edit-profile", buyer_client),
        ("/courier", courier_client),
        ("/admin", admin_client), ("/admin/access-requests?status=all", admin_client),
        ("/admin/users", admin_client), ("/admin/deliveries", admin_client),
    ]
    for path, client in pages:
        response = client.get(path, follow_redirects=True)
        check("GET %s renders" % path, response.status_code == 200, response.status_code)

    print()
    print("=" * 60)
    print("%d checks, %d failures" % (CHECKS, len(FAILURES)))
    if FAILURES:
        for name in FAILURES:
            print("  FAILED: %s" % name)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
