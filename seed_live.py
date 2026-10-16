"""Populate a deployment that has no listings yet.

A fresh database holds only the bootstrap administrator, so the marketplace
opens empty. This creates a handful of demo seller accounts and then runs the
normal seeder, which inserts the listings and fetches their photographs.

Unlike GLOBALTRADE_DEMO_DATA it is safe to run on the live site:

  * it never creates an administrator, and
  * every account it makes gets a random password, because these accounts exist
    only to own listings and are never meant to be signed into. Nothing here is
    a password published in the source.

    python seed_live.py

If it reports "inserted 0", the host could not reach Wikimedia Commons for the
photographs (the seeder refuses to insert a listing with no photo). In that
case the photos have to come from somewhere the host can read instead.
"""

import secrets

from werkzeug.security import generate_password_hash

from app import app, db, User
import seed_demo_data

# Owners for the seeded listings. The @globaltrade.com addresses are what the
# seeder looks for; the names just make the board read like real people.
SELLERS = [
    ("aman@globaltrade.com",    "Aman Durdyýew",    "Ashgabat"),
    ("selbi@globaltrade.com",   "Selbi Hojaýewa",   "Ashgabat"),
    ("maral@globaltrade.com",   "Maral Begençowa",  "Mary"),
    ("arslan@globaltrade.com",  "Arslan Myradow",   "Daşoguz"),
    ("oguljan@globaltrade.com", "Oguljan Nuryýewa", "Balkan"),
]


def ensure_sellers():
    created = 0
    for email, full_name, region in SELLERS:
        if User.query.filter_by(email=email).first():
            continue
        db.session.add(User(
            email=email,
            username=full_name.split()[0].lower(),
            full_name=full_name,
            region=region,
            role="member",
            kyc_status="verified",
            # Random, never a published password: these are listing owners, not
            # logins. A reset link is the only way into one, by design.
            password_hash=generate_password_hash(secrets.token_urlsafe(24), method="scrypt"),
        ))
        created += 1
    db.session.commit()
    print("demo sellers: created %d, already present %d" % (created, len(SELLERS) - created))


if __name__ == "__main__":
    with app.app_context():
        ensure_sellers()
    # Opens its own app context, inserts listings owned by the sellers above,
    # and fetches a photograph for each from Wikimedia Commons.
    seed_demo_data.main()
