import os
import base64
import binascii
import secrets
import click
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import inspect, or_, text
from ai_logic import HandshakeLiveEngine

app = Flask(__name__)


def resolve_secret_key():
    """The key that signs session cookies.

    This used to fall back to a literal in this file. Flask-Login keeps the
    signed-in user's id inside the session cookie, so a key anyone can read in
    the source is not a weak secret, it is no authentication at all: you forge
    a cookie for any user id you like, including an administrator's, and every
    @login_required and @admin_required in the file waves you through.

    HANDSHAKE_SECRET_KEY still wins when it is set. Otherwise a random key is
    generated once and kept in instance/secret_key, which means the app still
    starts with no configuration — the thing the old default was protecting —
    while the key is unguessable and sessions survive a restart.
    """
    from_env = os.environ.get('HANDSHAKE_SECRET_KEY')
    if from_env:
        return from_env

    key_path = os.path.join(app.instance_path, 'secret_key')
    try:
        with open(key_path, 'r', encoding='utf-8') as fh:
            stored = fh.read().strip()
        if stored:
            return stored
    except OSError:
        pass

    generated = secrets.token_hex(32)
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        with open(key_path, 'w', encoding='utf-8') as fh:
            fh.write(generated)
        os.chmod(key_path, 0o600)
    except OSError:
        # Read-only deployment. A per-process key is still far better than a
        # published one; it only costs everyone their session on restart.
        pass
    return generated


app.secret_key = resolve_secret_key()

# Session cookie hardening. HTTPONLY keeps the cookie away from any script that
# manages to run on the page; SAMESITE='Lax' stops another site's form post
# from arriving authenticated, which is the cheapest CSRF mitigation available
# until real tokens land. SECURE is opt-in through HANDSHAKE_HTTPS because the
# app is normally served over plain http on a LAN, and setting it there would
# silently stop sessions working at all.
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('HANDSHAKE_HTTPS') == '1'
# HANDSHAKE_DATABASE_URI lets a test run against a scratch database instead of
# the real one. Unset, it is exactly the path it always was.
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'HANDSHAKE_DATABASE_URI', 'sqlite:///handshake.db'
)
app.config['UPLOAD_FOLDER'] = 'static/uploads/passports'
app.config['UPLOAD_FOLDER_ITEMS'] = 'static/uploads/items'
app.config['UPLOAD_FOLDER_PROFILES'] = 'static/uploads/profiles'
app.config['MAX_CONTENT_LENGTH'] = 24 * 1024 * 1024

from mailer import Mailer, looks_like_address

# Real mail. Unconfigured it writes .eml files into instance/outbox instead of
# sending, so every flow below can be walked without an SMTP account.
mailer = Mailer(app.instance_path)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
expert_executor = ThreadPoolExecutor(max_workers=4)
live_engine = HandshakeLiveEngine()

# Seeded from current official administrative references for Turkmenistan,
# with Ashgabat streets and avenues taken from official city transport notices.
TURKMEN_LOCATION_DATA = [
    {
        "name": "Ashgabat",
        "kind": "city",
        "districts": [
            {
                "name": "Bagtyyarlyk",
                "category": "city_district",
                "neighborhoods": [
                    "Teke Bazar",
                    "A. Niyazov Avenue",
                    "M. Kashgari Street",
                    "D. Azady Street",
                ],
            },
            {
                "name": "Berkararlyk",
                "category": "city_district",
                "neighborhoods": [
                    "Central Ashgabat",
                    "Garashsyzlyk Avenue",
                    "Turkmenbashy Avenue",
                    "Ataturk Street",
                ],
            },
            {
                "name": "Kopetdag",
                "category": "city_district",
                "neighborhoods": [
                    "Archabil Avenue",
                    "Bitarap Turkmenistan Avenue",
                    "Chandybil Avenue",
                ],
            },
            {
                "name": "Buzmeyin",
                "category": "city_district",
                "neighborhoods": [
                    "Arzuv",
                    "10 yyl Abadanchylyk Street",
                    "B. Annanov Street",
                    "H.A. Yasavi Street",
                    "N. Andalib Street",
                ],
            },
        ],
    },
    {
        "name": "Ahal",
        "kind": "velayat",
        "districts": [
            {"name": "Ak bugday", "category": "district", "neighborhoods": ["Anau"]},
            {"name": "Altyn Asyr", "category": "district", "neighborhoods": ["Altyn Asyr"]},
            {"name": "Babadayhan", "category": "district", "neighborhoods": ["Babadayhan"]},
            {"name": "Baharly", "category": "district", "neighborhoods": ["Baharly"]},
            {"name": "Gokdepe", "category": "district", "neighborhoods": ["Gokdepe"]},
            {"name": "Kaka", "category": "district", "neighborhoods": ["Kaka"]},
            {"name": "Sarahs", "category": "district", "neighborhoods": ["Sarahs"]},
            {"name": "Tejen", "category": "district", "neighborhoods": ["Tejen"]},
        ],
    },
    {
        "name": "Balkan",
        "kind": "velayat",
        "districts": [
            {"name": "Balkanabat", "category": "city_district",
             "neighborhoods": ["Balkanabat Centre", "Jebel", "Nebitchi"]},
            {"name": "Bereket", "category": "district", "neighborhoods": ["Bereket"]},
            {"name": "Esenguly", "category": "district", "neighborhoods": ["Esenguly"]},
            {"name": "Etrek", "category": "district", "neighborhoods": ["Etrek"]},
            {"name": "Magtymguly", "category": "district", "neighborhoods": ["Magtymguly"]},
            {"name": "Serdar", "category": "district", "neighborhoods": ["Serdar", "Gumdag"]},
            {"name": "Turkmenbashy", "category": "district",
             "neighborhoods": ["Turkmenbashy", "Hazar", "Garabogaz", "Awaza"]},
        ],
    },
    {
        "name": "Dashoguz",
        "kind": "velayat",
        "districts": [
            {"name": "Dashoguz", "category": "city_district",
             "neighborhoods": ["Dashoguz Centre", "Mira Street", "Gurbansoltan Eje Street"]},
            {"name": "Akdepe", "category": "district", "neighborhoods": ["Akdepe"]},
            {"name": "Boldumsaz", "category": "district", "neighborhoods": ["Boldumsaz"]},
            {"name": "Gorogly", "category": "district", "neighborhoods": ["Gorogly"]},
            {"name": "Gubadag", "category": "district", "neighborhoods": ["Gubadag"]},
            {"name": "Koneurgench", "category": "district", "neighborhoods": ["Koneurgench"]},
            {"name": "Ruhubelent", "category": "district", "neighborhoods": ["Ruhubelent"]},
            {"name": "Shabat", "category": "district", "neighborhoods": ["Shabat"]},
            {"name": "Saparmyrat Turkmenbashy", "category": "district",
             "neighborhoods": ["Saparmyrat Turkmenbashy"]},
            {"name": "Yyllanly", "category": "district", "neighborhoods": ["Yyllanly"]},
        ],
    },
    {
        "name": "Lebap",
        "kind": "velayat",
        "districts": [
            {"name": "Turkmenabat", "category": "city_district",
             "neighborhoods": ["Turkmenabat Centre", "Bitarap Turkmenistan Street", "Magtymguly Street"]},
            {"name": "Charjew", "category": "district", "neighborhoods": ["Charjew"]},
            {"name": "Danew", "category": "district", "neighborhoods": ["Danew"]},
            {"name": "Darganata", "category": "district", "neighborhoods": ["Birata"]},
            {"name": "Dowletli", "category": "district", "neighborhoods": ["Dowletli"]},
            {"name": "Farap", "category": "district", "neighborhoods": ["Farap"]},
            {"name": "Halach", "category": "district", "neighborhoods": ["Halach"]},
            {"name": "Hojambaz", "category": "district", "neighborhoods": ["Hojambaz"]},
            {"name": "Kerki", "category": "district", "neighborhoods": ["Kerki"]},
            {"name": "Koytendag", "category": "district", "neighborhoods": ["Koytendag", "Magdanly"]},
            {"name": "Sayat", "category": "district", "neighborhoods": ["Sayat"]},
            {"name": "Seydi", "category": "district", "neighborhoods": ["Seydi"]},
        ],
    },
    {
        "name": "Mary",
        "kind": "velayat",
        "districts": [
            {"name": "Mary", "category": "city_district",
             "neighborhoods": ["Mary Centre", "Mollanepes Street", "Kemine Street"]},
            {"name": "Bayramaly", "category": "district", "neighborhoods": ["Bayramaly"]},
            {"name": "Garagum", "category": "district", "neighborhoods": ["Garagum"]},
            {"name": "Murgap", "category": "district", "neighborhoods": ["Murgap"]},
            {"name": "Oguzhan", "category": "district", "neighborhoods": ["Oguzhan"]},
            {"name": "Sakarchage", "category": "district", "neighborhoods": ["Sakarchage"]},
            {"name": "Serhetabat", "category": "district", "neighborhoods": ["Serhetabat"]},
            {"name": "Tagtabazar", "category": "district", "neighborhoods": ["Tagtabazar"]},
            {"name": "Turkmengala", "category": "district", "neighborhoods": ["Turkmengala"]},
            {"name": "Yoloten", "category": "district", "neighborhoods": ["Yoloten"]},
        ],
    },
    {
        "name": "Arkadag",
        "kind": "city",
        "districts": [
            {"name": "Arkadag", "category": "city_district",
             "neighborhoods": ["Arkadag Centre", "Bagtyyarlyk Street", "Ylym Street"]},
        ],
    },
]


# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------
ITEM_STATUSES = ('listed', 'reserved', 'sold', 'withdrawn')
SIZE_CLASSES = ('small', 'medium', 'large')

# The one list of categories. The marketplace filters and the upload form used
# to hardcode their own copies, which had already drifted; both now read this,
# so a category cannot exist in one place and not the other. The first six
# slugs are the ones already in the database and must not be renamed.
ITEM_CATEGORIES = (
    ('tech',        'Electronics'),
    ('phones',      'Phones'),
    ('computers',   'Computers'),
    ('appliances',  'Appliances'),
    ('furniture',   'Furniture'),
    ('houses',      'Property'),
    ('tools',       'Tools'),
    ('building',    'Building materials'),
    ('cars',        'Vehicles'),
    ('parts',       'Vehicle parts'),
    ('bikes',       'Bikes and scooters'),
    ('clothing',    'Clothing'),
    ('shoes',       'Shoes and bags'),
    ('kids',        'Kids and baby'),
    ('sports',      'Sport and outdoors'),
    ('hobbies',     'Hobbies'),
    ('music',       'Instruments'),
    ('books',       'Books'),
    ('garden',      'Garden'),
    ('pets',        'Pets'),
    ('beauty',      'Health and beauty'),
    ('business',    'Business and trade'),
)


def category_list(items=None):
    """The categories with a live count against the listings being shown.

    A count of zero is not hidden: an empty category is a truthful statement
    that nobody has posted one yet, and hiding it would make the filter strip
    change shape every time somebody lists something.
    """
    counts = {}
    for item in (items or []):
        counts[item.category] = counts.get(item.category, 0) + 1
    listed = [
        {'slug': slug, 'label': label, 'count': counts.get(slug, 0)}
        for slug, label in ITEM_CATEGORIES
    ]
    # Busiest first. On a phone only the first few rows are visible before the
    # list is expanded, and those rows should be the ones with goods in them.
    listed.sort(key=lambda entry: -entry['count'])
    return listed
ORDER_STATUSES = ('placed', 'accepted', 'rejected', 'cancelled', 'paid', 'completed')
DELIVERY_STATUSES = (
    'awaiting_pickup', 'picked_up', 'in_transit',
    'out_for_delivery', 'delivered', 'failed', 'returned',
)
# The courier walks the pipeline in this order. Anything else is refused.
DELIVERY_FLOW = {
    'awaiting_pickup': ('picked_up', 'failed'),
    'picked_up': ('in_transit', 'failed'),
    'in_transit': ('out_for_delivery', 'failed'),
    'out_for_delivery': ('delivered', 'failed', 'returned'),
    'delivered': (),
    'failed': ('returned',),
    'returned': (),
}

SERVICE_FEE_RATE = 0.05          # HandShake's cut of the goods price
DELIVERY_BASE_FEE = 15.0         # TMT, every delivery
DELIVERY_DISTANCE_SURCHARGE = {
    'same_neighborhood': 0.0,
    'same_district': 10.0,
    'same_velayat': 25.0,
    'cross_velayat': 60.0,
}
DELIVERY_SIZE_MULTIPLIER = {'small': 1.0, 'medium': 1.6, 'large': 2.5}
HIGH_VALUE_THRESHOLD = 100.0     # above this an unverified buyer cannot order
INVITE_TTL_DAYS = 7
PLATFORM_ACCOUNT_NAME = 'handshake'
CODE_ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'   # no 0/O/1/I


def parse_price(price_str):
    """Pull a number out of whatever the old String(50) price column held."""
    if price_str is None:
        return 0.0
    if isinstance(price_str, (int, float)):
        return float(price_str)
    import re
    cleaned = re.sub(r'[^\d.]', '', str(price_str))
    # "1.2.3" and "" both come back as zero rather than raising.
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def generate_handoff_code(length=6):
    """A short code a person can read aloud at a doorstep."""
    return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def submitted_code(raw):
    """Normalise what someone typed into the code box.

    Anything outside the code alphabet is dropped. secrets.compare_digest
    raises TypeError on a non-ASCII string, so a Cyrillic paste would
    otherwise be a 500 rather than a refusal.
    """
    return ''.join(c for c in (raw or '').strip().upper() if c in CODE_ALPHABET)


def code_matches(stored, submitted):
    if not stored or not submitted:
        return False
    return secrets.compare_digest(stored, submitted)


def generate_invite_token():
    return secrets.token_urlsafe(32)


# How long a reset link is good for. Short, because it is a password.
RESET_TTL_HOURS = 2
# How long someone has to confirm the address they applied with.
VERIFY_TTL_DAYS = 3


def send_verification_email(access_request):
    """Prove the applicant owns the address before an admin spends time on it."""
    link = url_for('verify_email', token=access_request.verify_token, _external=True)
    return mailer.send(
        access_request.email,
        "Confirm your email for HandShake",
        "Hello %s,\n\n"
        "Someone asked for access to HandShake using this email address. If it\n"
        "was you, confirm it here:\n\n"
        "    %s\n\n"
        "The link is good for %d days. Confirming does not create an account —\n"
        "an administrator still reviews every request, and you will hear from\n"
        "us either way.\n\n"
        "If this was not you, ignore this message. Nothing happens without the\n"
        "link above.\n\n"
        "— HandShake\n" % (access_request.full_name, link, VERIFY_TTL_DAYS),
    )


def send_invite_email(access_request):
    """The approval itself. This link is the only way to become an account."""
    link = url_for('activate', token=access_request.invite_token, _external=True)
    return mailer.send(
        access_request.email,
        "You have been approved for HandShake",
        "Hello %s,\n\n"
        "Your request has been approved. Set a password and your account is\n"
        "live:\n\n"
        "    %s\n\n"
        "The link works once and expires in %d days. Do not forward it — anyone\n"
        "holding it can claim the account.\n\n"
        "— HandShake\n" % (access_request.full_name, link, INVITE_TTL_DAYS),
    )


def send_rejection_email(access_request):
    note = (access_request.review_note or "").strip()
    reason = ("\n\nThe reviewer noted: %s" % note) if note else ""
    return mailer.send(
        access_request.email,
        "About your HandShake request",
        "Hello %s,\n\n"
        "Your request for access was not approved.%s\n\n"
        "You are welcome to apply again.\n\n"
        "— HandShake\n" % (access_request.full_name, reason),
    )


def send_password_reset_email(user):
    link = url_for('reset_password', token=user.reset_token, _external=True)
    return mailer.send(
        user.email,
        "Reset your HandShake password",
        "Hello %s,\n\n"
        "Someone asked to reset the password on this account. If it was you,\n"
        "choose a new one here:\n\n"
        "    %s\n\n"
        "The link works once and expires in %d hours. If it was not you, ignore\n"
        "this message — your current password still works and nothing has\n"
        "changed.\n\n"
        "— HandShake\n" % (user.full_name or user.username, link, RESET_TTL_HOURS),
    )


def notify_admins_of_request(access_request):
    """Tell whoever can act on it that something is waiting."""
    admins = User.query.filter_by(role='admin').all()
    if not admins:
        return
    link = url_for('admin_access_requests', _external=True)
    for admin in admins:
        mailer.send(
            admin.email,
            "New access request: %s" % access_request.full_name,
            "%s (%s) has asked for access and confirmed their email.\n\n"
            "Review the queue:\n\n    %s\n\n— HandShake\n"
            % (access_request.full_name, access_request.email, link),
        )


def delivery_distance_band(origin, destination):
    """How far apart two neighborhoods are, in the only four steps we price."""
    if origin is None or destination is None:
        return 'cross_velayat'
    if origin.id == destination.id:
        return 'same_neighborhood'
    if origin.district_id == destination.district_id:
        return 'same_district'
    if origin.district.velayat_id == destination.district.velayat_id:
        return 'same_velayat'
    return 'cross_velayat'


def calculate_delivery_fee(origin, destination, size_class):
    """The whole delivery price, in one place.

    base 15 TMT
      same neighborhood +0, same district +10, same velayat +25, cross +60
    then size: small x1.0, medium x1.6, large x2.5
    """
    band = delivery_distance_band(origin, destination)
    multiplier = DELIVERY_SIZE_MULTIPLIER.get(size_class or 'small', 1.0)
    fee = (DELIVERY_BASE_FEE + DELIVERY_DISTANCE_SURCHARGE[band]) * multiplier
    return round(fee, 2)


def quote_order(item, destination, price_override=None):
    """Every number the buyer is about to agree to."""
    origin = item.neighborhood
    goods = round(float(item.price if price_override is None else price_override), 2)
    delivery_fee = calculate_delivery_fee(origin, destination, item.size_class)
    service_fee = round(goods * SERVICE_FEE_RATE, 2)
    return {
        'goods': goods,
        'delivery_fee': delivery_fee,
        'service_fee': service_fee,
        'total': round(goods + delivery_fee + service_fee, 2),
        'band': delivery_distance_band(origin, destination),
    }


def save_data_url_image(data_url, destination_path):
    if not data_url or ',' not in data_url:
        raise ValueError("Missing image data")

    _, encoded = data_url.split(',', 1)
    try:
        image_bytes = base64.b64decode(encoded)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid image data") from exc

    with open(destination_path, "wb") as fh:
        fh.write(image_bytes)


def find_chat_request_between(user_a_id, user_b_id):
    return ChatRequest.query.filter(
        ((ChatRequest.sender_id == user_a_id) & (ChatRequest.recipient_id == user_b_id)) |
        ((ChatRequest.sender_id == user_b_id) & (ChatRequest.recipient_id == user_a_id))
    ).order_by(ChatRequest.timestamp.desc()).first()


def has_accepted_chat_between(user_a_id, user_b_id):
    return ChatRequest.query.filter(
        (
            ((ChatRequest.sender_id == user_a_id) & (ChatRequest.recipient_id == user_b_id)) |
            ((ChatRequest.sender_id == user_b_id) & (ChatRequest.recipient_id == user_a_id))
        ) &
        (ChatRequest.status == 'accepted')
    ).first()


def find_pending_chat_request(sender_id, recipient_id):
    return ChatRequest.query.filter_by(
        sender_id=sender_id,
        recipient_id=recipient_id,
        status='pending'
    ).order_by(ChatRequest.timestamp.desc()).first()


def get_chat_connection_state(user_a_id, user_b_id):
    accepted = has_accepted_chat_between(user_a_id, user_b_id)
    if accepted:
        return 'accepted', accepted

    outgoing_pending = find_pending_chat_request(user_a_id, user_b_id)
    if outgoing_pending:
        return 'outgoing_pending', outgoing_pending

    incoming_pending = find_pending_chat_request(user_b_id, user_a_id)
    if incoming_pending:
        return 'incoming_pending', incoming_pending

    return 'none', None


def normalize_profile_pic_url(image_url):
    if not image_url:
        return image_url

    normalized = image_url.strip().replace("\\", "/")
    if normalized.startswith("http://") or normalized.startswith("https://") or normalized.startswith("/static/"):
        return normalized

    static_index = normalized.lower().find("static/")
    if static_index >= 0:
        return "/" + normalized[static_index:]

    if normalized.startswith("uploads/"):
        return url_for('static', filename=normalized)

    return normalized


def normalize_user_profile_pic(user):
    if not user:
        return
    user.profile_pic = normalize_profile_pic_url(user.profile_pic)


def get_location_tree():
    velayats = Velayat.query.order_by(
        db.case(
            (Velayat.name == 'Ashgabat', 0),
            (Velayat.name == 'Ahal', 1),
            else_=2
        ),
        Velayat.name.asc()
    ).all()
    tree = []
    for velayat in velayats:
        districts = []
        for district in sorted(velayat.districts, key=lambda item: item.name):
            neighborhoods = [
                {"id": neighborhood.id, "name": neighborhood.name}
                for neighborhood in sorted(district.neighborhoods, key=lambda item: item.name)
            ]
            districts.append(
                {
                    "id": district.id,
                    "name": district.name,
                    "category": district.category,
                    "neighborhoods": neighborhoods,
                }
            )
        tree.append(
            {
                "id": velayat.id,
                "name": velayat.name,
                "kind": velayat.kind,
                "districts": districts,
            }
        )
    return tree


def find_seeded_neighborhood(velayat_name, district_name, neighborhood_name):
    return Neighborhood.query.join(District).join(Velayat).filter(
        Velayat.name == velayat_name,
        District.name == district_name,
        Neighborhood.name == neighborhood_name
    ).first()


def resolve_legacy_location(legacy_loc):
    normalized = (legacy_loc or '').strip().lower()
    if not normalized:
        return find_seeded_neighborhood('Ashgabat', 'Berkararlyk', 'Central Ashgabat')

    mapping = [
        ('ashgabat', ('Ashgabat', 'Berkararlyk', 'Central Ashgabat')),
        ('anau', ('Ahal', 'Ak bugday', 'Anau')),
        ('ak bugday', ('Ahal', 'Ak bugday', 'Anau')),
        ('altyn asyr', ('Ahal', 'Altyn Asyr', 'Altyn Asyr')),
        ('babadayhan', ('Ahal', 'Babadayhan', 'Babadayhan')),
        ('baharly', ('Ahal', 'Baharly', 'Baharly')),
        ('gokdepe', ('Ahal', 'Gokdepe', 'Gokdepe')),
        ('kaka', ('Ahal', 'Kaka', 'Kaka')),
        ('sarahs', ('Ahal', 'Sarahs', 'Sarahs')),
        ('tejen', ('Ahal', 'Tejen', 'Tejen')),
    ]
    for token, target in mapping:
        if token in normalized:
            return find_seeded_neighborhood(*target)
    return find_seeded_neighborhood('Ashgabat', 'Berkararlyk', 'Central Ashgabat')


def ensure_location_schema():
    Velayat.__table__.create(bind=db.engine, checkfirst=True)
    District.__table__.create(bind=db.engine, checkfirst=True)
    Neighborhood.__table__.create(bind=db.engine, checkfirst=True)

    inspector = inspect(db.engine)
    item_columns = {column['name'] for column in inspector.get_columns('item')}
    if 'neighborhood_id' not in item_columns:
        db.session.execute(text('ALTER TABLE item ADD COLUMN neighborhood_id INTEGER'))
        db.session.commit()

    user_columns = {column['name'] for column in inspector.get_columns('user')}
    if 'kyc_status' not in user_columns:
        db.session.execute(text("ALTER TABLE user ADD COLUMN kyc_status VARCHAR(20) DEFAULT 'pending'"))
        db.session.commit()


def seed_location_data():
    for velayat_data in TURKMEN_LOCATION_DATA:
        velayat = Velayat.query.filter_by(name=velayat_data['name']).first()
        if not velayat:
            velayat = Velayat(name=velayat_data['name'], kind=velayat_data['kind'])
            db.session.add(velayat)
            db.session.flush()
        else:
            velayat.kind = velayat_data['kind']

        for district_data in velayat_data['districts']:
            district = District.query.filter_by(
                velayat_id=velayat.id,
                name=district_data['name']
            ).first()
            if not district:
                district = District(
                    name=district_data['name'],
                    category=district_data['category'],
                    velayat_id=velayat.id
                )
                db.session.add(district)
                db.session.flush()
            else:
                district.category = district_data['category']

            for neighborhood_name in district_data['neighborhoods']:
                neighborhood = Neighborhood.query.filter_by(
                    district_id=district.id,
                    name=neighborhood_name
                ).first()
                if not neighborhood:
                    db.session.add(Neighborhood(name=neighborhood_name, district_id=district.id))

    db.session.commit()


def backfill_item_locations():
    inspector = inspect(db.engine)
    item_columns = {column['name'] for column in inspector.get_columns('item')}
    has_legacy_loc = 'loc' in item_columns
    if has_legacy_loc:
        rows = db.session.execute(text('SELECT id, loc, neighborhood_id FROM item')).mappings().all()
        for row in rows:
            if row['neighborhood_id']:
                continue
            neighborhood = resolve_legacy_location(row['loc'])
            if neighborhood:
                db.session.execute(
                    text('UPDATE item SET neighborhood_id = :neighborhood_id WHERE id = :item_id'),
                    {"neighborhood_id": neighborhood.id, "item_id": row['id']}
                )
        db.session.commit()
        return

    # Raw SQL on purpose: this runs before the item table has been rewritten
    # into its logistics shape, so the ORM's column list would not match.
    default_neighborhood = resolve_legacy_location(None)
    if default_neighborhood:
        db.session.execute(
            text('UPDATE item SET neighborhood_id = :neighborhood_id WHERE neighborhood_id IS NULL'),
            {"neighborhood_id": default_neighborhood.id}
        )
    db.session.commit()


def rebuild_item_table_without_legacy_loc():
    inspector = inspect(db.engine)
    item_columns = {column['name'] for column in inspector.get_columns('item')}
    if 'loc' not in item_columns:
        return

    db.session.execute(text('PRAGMA foreign_keys=OFF'))
    db.session.execute(text('DROP TABLE IF EXISTS item_new'))
    db.session.execute(text("""
        CREATE TABLE item_new (
            id INTEGER NOT NULL PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            price VARCHAR(50) NOT NULL,
            price_unit VARCHAR(20) DEFAULT "day",
            deposit_price FLOAT DEFAULT 0.0,
            is_available BOOLEAN DEFAULT 1,
            type VARCHAR(50) NOT NULL,
            description TEXT,
            image_url VARCHAR(500),
            category VARCHAR(100) NOT NULL,
            rating FLOAT,
            num_ratings INTEGER,
            user_id INTEGER,
            neighborhood_id INTEGER
        )
    """))
    db.session.execute(text("""
        INSERT INTO item_new (
            id, title, price, price_unit, deposit_price, is_available,
            type, description, image_url,
            category, rating, num_ratings, user_id, neighborhood_id
        )
        SELECT
            id, title, price, "day", 0.0, 1, type, description, image_url,
            category, rating, num_ratings, user_id, neighborhood_id
        FROM item
    """))
    db.session.execute(text('DROP TABLE item'))
    db.session.execute(text('ALTER TABLE item_new RENAME TO item'))
    db.session.execute(text('PRAGMA foreign_keys=ON'))
    db.session.commit()


# ---------------------------------------------------------------------------
# Logistics migration
#
# Hand-rolled, in the same style as the location migration above, and driven
# from apply_database_updates() at boot. It rewrites the live database in
# place: the seeded listings, the uploaded passports and the user accounts all
# survive. Every step is guarded so a second boot is a no-op.
# ---------------------------------------------------------------------------

def _table_names():
    return set(inspect(db.engine).get_table_names())


def _columns(table):
    return {column['name']: column for column in inspect(db.engine).get_columns(table)}


def ensure_user_schema():
    """Add User.role, and make passport_img nullable.

    The passport now arrives on the AccessRequest and is copied across on
    activation, so a User row is created before any file exists. The column was
    NOT NULL, which would have made that impossible; SQLite cannot drop a NOT
    NULL in place, so the table is rebuilt.
    """
    columns = _columns('user')

    if 'role' not in columns:
        db.session.execute(
            text("ALTER TABLE user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'member'")
        )
        db.session.commit()
        columns = _columns('user')

    if columns['passport_img']['nullable']:
        return

    db.session.execute(text('PRAGMA legacy_alter_table=ON'))
    db.session.execute(text('PRAGMA foreign_keys=OFF'))
    db.session.execute(text('DROP TABLE IF EXISTS user_new'))
    db.session.execute(text("""
        CREATE TABLE user_new (
            id INTEGER NOT NULL PRIMARY KEY,
            username VARCHAR(100),
            full_name VARCHAR(200),
            email VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(200) NOT NULL,
            region VARCHAR(100) NOT NULL,
            age INTEGER,
            bio TEXT,
            rating FLOAT,
            num_ratings INTEGER,
            passport_img VARCHAR(200),
            profile_pic VARCHAR(500),
            kyc_status VARCHAR(20),
            role VARCHAR(20) NOT NULL DEFAULT 'member',
            wallet_balance FLOAT
        )
    """))
    db.session.execute(text("""
        INSERT INTO user_new (
            id, username, full_name, email, password_hash, region, age, bio,
            rating, num_ratings, passport_img, profile_pic, kyc_status, role,
            wallet_balance
        )
        SELECT
            id, username, full_name, email, password_hash, region, age, bio,
            rating, num_ratings, passport_img, profile_pic, kyc_status, role,
            wallet_balance
        FROM user
    """))
    db.session.execute(text('DROP TABLE user'))
    db.session.execute(text('ALTER TABLE user_new RENAME TO user'))
    db.session.execute(text('PRAGMA foreign_keys=ON'))
    db.session.execute(text('PRAGMA legacy_alter_table=OFF'))
    db.session.commit()


def rebuild_item_table_for_logistics():
    """Drop the four rental columns and retype price from String(50) to Float.

    price is parsed through parse_price, the same function the old buy flow
    used, so "200", "200 TMT" and "" all land on a sensible number.
    """
    columns = _columns('item')
    rental_columns = {'price_unit', 'deposit_price', 'type', 'is_available'} & set(columns)
    if not rental_columns and 'status' in columns and 'size_class' in columns:
        return

    rows = db.session.execute(text('SELECT * FROM item')).mappings().all()

    db.session.execute(text('PRAGMA legacy_alter_table=ON'))
    db.session.execute(text('PRAGMA foreign_keys=OFF'))
    db.session.execute(text('DROP TABLE IF EXISTS item_logistics'))
    db.session.execute(text("""
        CREATE TABLE item_logistics (
            id INTEGER NOT NULL PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            price FLOAT NOT NULL DEFAULT 0.0,
            description TEXT,
            image_url VARCHAR(500),
            category VARCHAR(100) NOT NULL,
            rating FLOAT,
            num_ratings INTEGER,
            status VARCHAR(20) NOT NULL DEFAULT 'listed',
            weight_kg FLOAT,
            size_class VARCHAR(20) NOT NULL DEFAULT 'small',
            user_id INTEGER,
            neighborhood_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES user (id),
            FOREIGN KEY(neighborhood_id) REFERENCES neighborhood (id)
        )
    """))

    for row in rows:
        # An item that was out on a rental is not free to move; everything else
        # is simply on the shelf.
        if 'status' in row and row['status']:
            status = row['status']
        elif 'is_available' in row and row['is_available'] in (0, False):
            status = 'reserved'
        else:
            status = 'listed'
        size_class = row['size_class'] if 'size_class' in row and row['size_class'] \
            else default_size_class(row['category'])
        db.session.execute(
            text("""
                INSERT INTO item_logistics (
                    id, title, price, description, image_url, category, rating,
                    num_ratings, status, weight_kg, size_class, user_id, neighborhood_id
                ) VALUES (
                    :id, :title, :price, :description, :image_url, :category, :rating,
                    :num_ratings, :status, :weight_kg, :size_class, :user_id, :neighborhood_id
                )
            """),
            {
                "id": row['id'],
                "title": row['title'],
                "price": parse_price(row['price']),
                "description": row['description'],
                "image_url": row['image_url'],
                "category": row['category'],
                "rating": row['rating'],
                "num_ratings": row['num_ratings'],
                "status": status,
                "weight_kg": row['weight_kg'] if 'weight_kg' in row else None,
                "size_class": size_class,
                "user_id": row['user_id'],
                "neighborhood_id": row['neighborhood_id'],
            }
        )

    db.session.execute(text('DROP TABLE item'))
    db.session.execute(text('ALTER TABLE item_logistics RENAME TO item'))
    db.session.execute(text('PRAGMA foreign_keys=ON'))
    db.session.execute(text('PRAGMA legacy_alter_table=OFF'))
    db.session.commit()


def default_size_class(category):
    """A first guess at how much van a listing needs. The seller can correct it."""
    if category in ('cars', 'houses'):
        return 'large'
    if category in ('tools',):
        return 'medium'
    return 'small'


def migrate_transactions_to_orders():
    """Carry the old rental Transactions across as Orders, then retire the table.

    Only rows that actually happened are kept. 'negotiating' and 'accepted'
    rows were mid-conversation under rules that no longer exist, so they are
    not carried over. The old table is renamed rather than dropped, so nothing
    is destroyed if the new shape turns out to be wrong.
    """
    tables = _table_names()
    if 'transaction' not in tables:
        return

    rows = db.session.execute(text('SELECT * FROM "transaction"')).mappings().all()
    carried = 0
    for row in rows:
        if row['status'] not in ('active', 'returned', 'completed'):
            continue
        if Order.query.filter_by(
            buyer_id=row['buyer_id'], seller_id=row['seller_id'],
            item_id=row['item_id'], created_at=row['timestamp']
        ).first():
            continue

        buyer = User.query.get(row['buyer_id'])
        destination = resolve_legacy_location(buyer.region if buyer else None)
        item_price = float(row['amount'] or 0.0)
        service_fee = float(row['commission'] or 0.0)
        created_at = row['timestamp']
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except ValueError:
                created_at = datetime.utcnow()

        db.session.add(Order(
            buyer_id=row['buyer_id'],
            seller_id=row['seller_id'],
            item_id=row['item_id'],
            item_price=item_price,
            proposed_price=None,
            delivery_fee=0.0,          # these predate delivery entirely
            service_fee=service_fee,
            total=round(item_price + service_fee, 2),
            status='completed',
            dest_neighborhood_id=destination.id if destination else None,
            created_at=created_at,
            updated_at=created_at,
        ))
        carried += 1

    db.session.commit()
    db.session.execute(text('DROP TABLE IF EXISTS transaction_legacy'))
    db.session.execute(text('ALTER TABLE "transaction" RENAME TO transaction_legacy'))
    db.session.commit()
    if carried:
        print("migrated %d historic transaction(s) into orders" % carried)


def backfill_review_targets():
    """A review of an item is a review of the person who listed it.

    target_user_id was never written, so /profile read an always-empty list.
    """
    rows = db.session.execute(text("""
        SELECT review.id AS review_id, item.user_id AS owner_id
        FROM review JOIN item ON item.id = review.item_id
        WHERE review.target_user_id IS NULL AND item.user_id IS NOT NULL
    """)).mappings().all()
    for row in rows:
        db.session.execute(
            text('UPDATE review SET target_user_id = :owner WHERE id = :rid'),
            {"owner": row['owner_id'], "rid": row['review_id']}
        )
    if rows:
        db.session.commit()


def ensure_platform_account():
    """The account the commission and the escrow actually live in."""
    account = PlatformAccount.query.filter_by(name=PLATFORM_ACCOUNT_NAME).first()
    if not account:
        account = PlatformAccount(name=PLATFORM_ACCOUNT_NAME, balance=0.0, escrow_balance=0.0)
        db.session.add(account)
        db.session.commit()
    return account


def platform_account():
    return ensure_platform_account()


def ensure_boot_admin():
    """HANDSHAKE_ADMIN_EMAIL promotes an existing account at boot.

    It never creates an account, so setting it cannot conjure a way in.
    """
    email = (os.environ.get('HANDSHAKE_ADMIN_EMAIL') or '').strip().lower()
    if not email:
        return
    user = User.query.filter_by(email=email).first()
    if not user:
        print("HANDSHAKE_ADMIN_EMAIL=%s matches no account; not promoted" % email)
        return
    if user.role != 'admin':
        user.role = 'admin'
        db.session.commit()
        print("promoted %s to admin" % email)


def ensure_email_auth_schema():
    """Columns for email verification and password reset.

    Same hand-rolled, guarded-ALTER idiom as the migrations above: check the
    inspector, add what is missing, do nothing on a database that already has
    it. Safe to run on every boot, which is how it is run.
    """
    inspector = inspect(db.engine)

    request_columns = {c['name'] for c in inspector.get_columns('access_request')}
    for column, ddl in (
        ('verify_token', 'ALTER TABLE access_request ADD COLUMN verify_token VARCHAR(64)'),
        ('verify_sent_at', 'ALTER TABLE access_request ADD COLUMN verify_sent_at DATETIME'),
        ('email_verified_at', 'ALTER TABLE access_request ADD COLUMN email_verified_at DATETIME'),
    ):
        if column not in request_columns:
            db.session.execute(text(ddl))
            db.session.commit()

    user_columns = {c['name'] for c in inspector.get_columns('user')}
    for column, ddl in (
        ('reset_token', 'ALTER TABLE user ADD COLUMN reset_token VARCHAR(64)'),
        ('reset_expires_at', 'ALTER TABLE user ADD COLUMN reset_expires_at DATETIME'),
    ):
        if column not in user_columns:
            db.session.execute(text(ddl))
            db.session.commit()


def apply_database_updates():
    db.create_all()
    ensure_location_schema()
    seed_location_data()
    backfill_item_locations()
    rebuild_item_table_without_legacy_loc()
    ensure_user_schema()
    rebuild_item_table_for_logistics()
    migrate_transactions_to_orders()
    backfill_review_targets()
    ensure_email_auth_schema()
    ensure_platform_account()


@app.errorhandler(RequestEntityTooLarge)
def handle_request_too_large(_error):
    flash('The uploaded image is too large. Please use a smaller or compressed image.')

    if request.path == url_for('request_access'):
        return redirect(url_for('request_access'))
    if request.path == url_for('login'):
        return redirect(url_for('login'))
    if request.path == url_for('upload'):
        return redirect(url_for('upload'))
    if request.path == url_for('edit_profile'):
        return redirect(url_for('edit_profile'))
    return redirect(url_for('index'))


@app.errorhandler(404)
def handle_not_found(_error):
    # A raw Werkzeug page reads as a broken site. Hand it the designed shell
    # instead. Reached by bad URLs and by abort(404) on resources the viewer
    # is not party to, so the copy stays neutral about which it was.
    return render_template(
        'error.html',
        code='404',
        heading='Nothing here',
        message='That page does not exist, or it belongs to an order you are '
                'not part of.',
        show_orders=current_user.is_authenticated,
    ), 404


@app.errorhandler(403)
def handle_forbidden(_error):
    return render_template(
        'error.html',
        code='403',
        heading='Not your door',
        message='You are signed in, but this is not yours to open.',
        show_orders=current_user.is_authenticated,
    ), 403

# Models
class Velayat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    kind = db.Column(db.String(20), nullable=False, default='velayat')
    districts = db.relationship('District', backref='velayat', lazy=True, cascade='all, delete-orphan')


class District(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(20), nullable=False, default='district')
    velayat_id = db.Column(db.Integer, db.ForeignKey('velayat.id'), nullable=False)
    neighborhoods = db.relationship('Neighborhood', backref='district', lazy=True, cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('velayat_id', 'name', name='uq_district_velayat_name'),
    )


class Neighborhood(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    district_id = db.Column(db.Integer, db.ForeignKey('district.id'), nullable=False)
    items = db.relationship('Item', backref='neighborhood', lazy=True)

    __table_args__ = (
        db.UniqueConstraint('district_id', 'name', name='uq_neighborhood_district_name'),
    )

    @property
    def display_name(self):
        return f"{self.name}, {self.district.name}"

    @property
    def full_path(self):
        return f"{self.name}, {self.district.name}, {self.district.velayat.name}"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=True)
    full_name = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    region = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    bio = db.Column(db.Text, nullable=True)
    rating = db.Column(db.Float, default=5.0)
    num_ratings = db.Column(db.Integer, default=1)
    passport_img = db.Column(db.String(200), nullable=True)   # legacy, unused
    reset_token = db.Column(db.String(64), unique=True, nullable=True)
    reset_expires_at = db.Column(db.DateTime, nullable=True)
    profile_pic = db.Column(db.String(500), nullable=True)
    kyc_status = db.Column(db.String(20), default='pending') # pending, processing, verified, rejected
    role = db.Column(db.String(20), nullable=False, default='member') # member, courier, admin
    wallet_balance = db.Column(db.Float, default=1000.0) # Mock money for orders
    items = db.relationship('Item', backref='owner', lazy=True)
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    received_messages = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy=True)

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_courier(self):
        # An admin can drive the courier console too, so support is never blocked.
        return self.role in ('courier', 'admin')


class Item(db.Model):
    """A good offered for sale, and the origin of a delivery."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    category = db.Column(db.String(100), nullable=False)
    rating = db.Column(db.Float, default=5.0)
    num_ratings = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), nullable=False, default='listed') # listed, reserved, sold, withdrawn
    weight_kg = db.Column(db.Float, nullable=True)
    size_class = db.Column(db.String(20), nullable=False, default='small') # small, medium, large
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    # Where the courier collects it.
    neighborhood_id = db.Column(db.Integer, db.ForeignKey('neighborhood.id'), nullable=True)

    @property
    def location_label(self):
        if self.neighborhood:
            return self.neighborhood.full_path
        return "Ashgabat"

    @property
    def pickup_label(self):
        return self.location_label

    @property
    def is_orderable(self):
        return self.status == 'listed'


class AccessRequest(db.Model):
    """Someone asking to be let in. An admin turns this into a User, or does not."""
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(100), nullable=False, index=True)
    phone = db.Column(db.String(50), nullable=True)
    region = db.Column(db.String(100), nullable=True)
    neighborhood_id = db.Column(db.Integer, db.ForeignKey('neighborhood.id'), nullable=True)
    age = db.Column(db.Integer, nullable=True)
    reason = db.Column(db.Text, nullable=True)
    passport_img = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending') # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    review_note = db.Column(db.Text, nullable=True)
    invite_token = db.Column(db.String(64), unique=True, nullable=True)
    invite_expires_at = db.Column(db.DateTime, nullable=True)
    invite_used_at = db.Column(db.DateTime, nullable=True)
    # The passport used to be the identity proof. It is the email address now:
    # a request nobody confirmed from the inbox they claimed is not a request,
    # it is a typo or a stranger using someone else's address.
    verify_token = db.Column(db.String(64), unique=True, nullable=True)
    verify_sent_at = db.Column(db.DateTime, nullable=True)
    email_verified_at = db.Column(db.DateTime, nullable=True)

    neighborhood = db.relationship('Neighborhood', foreign_keys=[neighborhood_id])
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])

    @property
    def invite_is_live(self):
        """Approved, issued, never used, and not yet stale."""
        if self.status != 'approved' or not self.invite_token or self.invite_used_at:
            return False
        if self.invite_expires_at and datetime.utcnow() > self.invite_expires_at:
            return False
        return True

    @property
    def invite_state(self):
        if self.status == 'rejected':
            return 'rejected'
        if self.status == 'pending':
            return 'pending'
        if self.invite_used_at:
            return 'used'
        if self.invite_expires_at and datetime.utcnow() > self.invite_expires_at:
            return 'expired'
        return 'live'


class Order(db.Model):
    """A buyer ordering a listed good. Replaces the old rental Transaction."""
    __tablename__ = 'customer_order'

    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    item_price = db.Column(db.Float, nullable=False, default=0.0)   # snapshot at order time
    proposed_price = db.Column(db.Float, nullable=True)             # buyer's counter-offer
    delivery_fee = db.Column(db.Float, nullable=False, default=0.0)
    service_fee = db.Column(db.Float, nullable=False, default=0.0)
    total = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), nullable=False, default='placed')
    dest_neighborhood_id = db.Column(db.Integer, db.ForeignKey('neighborhood.id'), nullable=True)
    dest_address_line = db.Column(db.String(300), nullable=True)
    dest_contact_phone = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    buyer = db.relationship('User', foreign_keys=[buyer_id], backref='purchases')
    seller = db.relationship('User', foreign_keys=[seller_id], backref='sales')
    item = db.relationship('Item', backref='orders')
    dest_neighborhood = db.relationship('Neighborhood', foreign_keys=[dest_neighborhood_id])

    @property
    def agreed_price(self):
        """What the goods actually cost: the counter-offer if there is one."""
        return self.proposed_price if self.proposed_price is not None else self.item_price

    @property
    def is_negotiated(self):
        return self.proposed_price is not None and self.proposed_price != self.item_price

    @property
    def destination_label(self):
        if self.dest_neighborhood:
            return self.dest_neighborhood.full_path
        return self.dest_address_line or "Unknown"


class Delivery(db.Model):
    """One journey, created when an order is paid for."""
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('customer_order.id'), unique=True, nullable=False)
    origin_neighborhood_id = db.Column(db.Integer, db.ForeignKey('neighborhood.id'), nullable=True)
    dest_neighborhood_id = db.Column(db.Integer, db.ForeignKey('neighborhood.id'), nullable=True)
    courier_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    status = db.Column(db.String(30), nullable=False, default='awaiting_pickup')
    # Short, single-use, never leaves the server except to the one person who
    # must say it out loud. Replaces the old permanent QR URL.
    pickup_code = db.Column(db.String(12), nullable=True)
    dropoff_code = db.Column(db.String(12), nullable=True)
    picked_up_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    eta_date = db.Column(db.Date, nullable=True)
    fee = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = db.relationship('Order', backref=db.backref('delivery', uselist=False))
    courier = db.relationship('User', foreign_keys=[courier_id], backref='deliveries')
    origin_neighborhood = db.relationship('Neighborhood', foreign_keys=[origin_neighborhood_id])
    dest_neighborhood = db.relationship('Neighborhood', foreign_keys=[dest_neighborhood_id])
    events = db.relationship(
        'DeliveryEvent', backref='delivery', lazy=True,
        order_by='DeliveryEvent.id', cascade='all, delete-orphan'
    )

    @property
    def is_open(self):
        return self.status not in ('delivered', 'returned')

    @property
    def next_statuses(self):
        return DELIVERY_FLOW.get(self.status, ())


class DeliveryEvent(db.Model):
    """Append-only. One row per transition, written inside the same commit."""
    id = db.Column(db.Integer, primary_key=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey('delivery.id'), nullable=False)
    status = db.Column(db.String(30), nullable=False)
    note = db.Column(db.String(300), nullable=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    actor = db.relationship('User', foreign_keys=[actor_id])


class PlatformAccount(db.Model):
    """Where the commission and the escrowed goods money actually sit.

    Without this the money simply left the sum of all wallets and vanished.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, default=PLATFORM_ACCOUNT_NAME)
    balance = db.Column(db.Float, nullable=False, default=0.0)        # earned fees
    escrow_balance = db.Column(db.Float, nullable=False, default=0.0) # held for sellers

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    reviewer = db.relationship('User', foreign_keys=[reviewer_id], backref='reviews_written')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

class ChatRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, accepted, rejected
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_requests')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_requests')

class BlockedUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blocked_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    normalize_user_profile_pic(user)
    return user


def admin_required(view):
    """Signed in AND role == 'admin'. Anyone else is sent away, not shown a hint."""
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            flash('That area is for administrators.')
            return redirect(url_for('index'))
        return view(*args, **kwargs)
    return wrapper


def courier_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_courier:
            flash('That area is for couriers.')
            return redirect(url_for('index'))
        return view(*args, **kwargs)
    return wrapper


def record_delivery_event(delivery, status, note=None, actor=None):
    """Append-only audit row. Called inside the same transaction as the change."""
    event = DeliveryEvent(
        delivery_id=delivery.id,
        status=status,
        note=note,
        actor_id=actor.id if actor is not None else None,
    )
    db.session.add(event)
    return event


@app.context_processor
def inject_chat_request_count():
    pending_chat_request_count = 0
    pending_access_request_count = 0
    if current_user.is_authenticated:
        pending_chat_request_count = ChatRequest.query.filter_by(
            recipient_id=current_user.id,
            status='pending'
        ).count()
        if current_user.is_admin:
            pending_access_request_count = AccessRequest.query.filter_by(status='pending').count()
    return {
        'pending_chat_request_count': pending_chat_request_count,
        'pending_access_request_count': pending_access_request_count,
    }

# Initialize Database with dummy data
with app.app_context():
    apply_database_updates()
    
    if not User.query.filter_by(email="nepes@handshake.com").first():
        # Create Dummy Users
        dummy_users = [
            {"name": "Nepes", "email": "nepes@handshake.com", "pass": "nepes123", "region": "Ashgabat", "bio": "Photography enthusiast and tech geek.", "pic": "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=400"},
            {"name": "Aman", "email": "aman@handshake.com", "pass": "aman123", "region": "Ashgabat", "bio": "Professional driver. I sell cars I have looked after myself.", "pic": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400"},
            {"name": "Selbi", "email": "selbi@handshake.com", "pass": "selbi123", "region": "Ashgabat", "bio": "I love books and sharing knowledge.", "pic": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=400"},
            {"name": "Maral", "email": "maral@handshake.com", "pass": "maral123", "region": "Ashgabat", "bio": "Home renovation expert. I sell good tools I no longer need.", "pic": "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=400"},
            {"name": "Arslan", "email": "arslan@handshake.com", "pass": "arslan123", "region": "Ashgabat", "bio": "Gaming is my life. Selling my spare consoles and games.", "pic": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400"},
            {"name": "User1", "email": "user1@handshake.com", "pass": "user1", "region": "Ashgabat", "bio": "New HandShake member, ready to send and receive.", "pic": "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=400"}
        ]
        
        db_users = []
        for u in dummy_users:
            new_u = User(
                username=u['name'].lower(), full_name=u['name'], email=u['email'],
                password_hash=generate_password_hash(u['pass'], method='scrypt'),
                region=u['region'], bio=u['bio'], age=25,
                kyc_status='verified',
                profile_pic=u['pic']
            )
            db.session.add(new_u)
            db_users.append(new_u)
        db.session.commit()

        items_data = [
            {"title": "Sony A7III Camera", "price": 200.0, "size": "small", "kg": 1.2, "cat": "hobbies", "user_idx": 0, "desc": "Perfect for professional shoots. Body, battery and strap.", "img": "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=800"},
            {"title": "DJI Mavic Air 2", "price": 150.0, "size": "small", "kg": 2.0, "cat": "hobbies", "user_idx": 0, "desc": "4K drone with the case and two batteries.", "img": "https://images.unsplash.com/photo-1508614589041-895b88991e3e?w=800"},
            {"title": "Toyota Camry 2022", "price": 500.0, "size": "large", "kg": 1500.0, "cat": "cars", "user_idx": 1, "desc": "Clean, reliable, and comfortable.", "img": "https://images.unsplash.com/photo-1621007947382-bb3c3994e3fb?w=800"},
            {"title": "BMW X5", "price": 800.0, "size": "large", "kg": 2100.0, "cat": "cars", "user_idx": 1, "desc": "Luxury SUV, full service history.", "img": "https://images.unsplash.com/photo-1555215695-3004980ad54e?w=800"},
            {"title": "Mercedes-Benz G-Class", "price": 1500.0, "size": "large", "kg": 2500.0, "cat": "cars", "user_idx": 1, "desc": "The ultimate off-roader.", "img": "https://images.unsplash.com/photo-1520031441872-265e4ff70366?w=800"},
            {"title": "Rare Art History Collection", "price": 20.0, "size": "medium", "kg": 6.0, "cat": "books", "user_idx": 2, "desc": "Set of 5 books about Renaissance art.", "img": "https://images.unsplash.com/photo-1512820790803-83ca734da794?w=800"},
            {"title": "Bosch Drill Set", "price": 50.0, "size": "medium", "kg": 4.5, "cat": "tools", "user_idx": 3, "desc": "Heavy duty drill with all attachments.", "img": "https://images.unsplash.com/photo-1504148455328-c376907d081c?w=800"},
            {"title": "Professional Toolkit", "price": 75.0, "size": "medium", "kg": 12.0, "cat": "tools", "user_idx": 3, "desc": "150-piece tool set for all home repairs.", "img": "https://images.unsplash.com/photo-1581244277943-fe4a9c777189?w=800"},
            {"title": "PlayStation 5 + 2 Controllers", "price": 100.0, "size": "medium", "kg": 5.0, "cat": "hobbies", "user_idx": 4, "desc": "Two games included: GOW, Spider-Man.", "img": "https://images.unsplash.com/photo-1606813907291-d86efa9b94db?w=800"},
            {"title": "Canon EOS R5", "price": 350.0, "size": "small", "kg": 1.4, "cat": "hobbies", "user_idx": 5, "desc": "High-resolution full-frame mirrorless camera.", "img": "https://images.unsplash.com/photo-1510127034890-ba27508e9f1c?w=800"},
            {"title": "Electric Skateboard", "price": 80.0, "size": "medium", "kg": 8.0, "cat": "hobbies", "user_idx": 5, "desc": "Fast and fun city commuting.", "img": "https://images.unsplash.com/photo-1547447134-cd3f5c716030?w=800"},
            {"title": "Table Tennis Rackets (Pair)", "price": 15.0, "size": "small", "kg": 0.6, "cat": "hobbies", "user_idx": 5, "desc": "Professional grade rackets for competitive play.", "img": "https://images.unsplash.com/photo-1534158914592-062992fbe900?w=800"},
            {"title": "Mountain Bike - Trek", "price": 60.0, "size": "large", "kg": 14.0, "cat": "hobbies", "user_idx": 5, "desc": "Durable bike for trail riding.", "img": "https://images.unsplash.com/photo-1485965120184-e220f721d03e?w=800"}
        ]

        for item in items_data:
            new_item = Item(
                title=item['title'], price=item['price'],
                size_class=item['size'], weight_kg=item['kg'], status='listed',
                neighborhood_id=find_seeded_neighborhood('Ashgabat', 'Berkararlyk', 'Central Ashgabat').id,
                description=item['desc'], category=item['cat'],
                user_id=db_users[item['user_idx']].id,
                image_url=item['img']
            )
            db.session.add(new_item)
        db.session.commit()

        review = Review(
            content="Excellent camera, very well maintained!", rating=5,
            reviewer_id=db_users[1].id, item_id=1, target_user_id=db_users[0].id
        )
        db.session.add(review)
        db.session.commit()

    if not User.query.filter_by(email="friend@handshake.com").first():
        friend_user = User(
            username="friend",
            full_name="Message Friend",
            email="friend@handshake.com",
            password_hash=generate_password_hash("friend123", method='scrypt'),
            region="Ashgabat",
            bio="Seeded test account for chat checks.",
            age=27,
            passport_img="verified.png"
        )
        db.session.add(friend_user)
        db.session.commit()

    # Last, so that it can promote an account the demo seed has only just
    # created on a first boot.
    ensure_boot_admin()

@app.route('/')
def dashboard():
    all_items = Item.query.filter(Item.status != 'withdrawn').order_by(Item.id.desc()).all()
    return render_template('dashboard.html', items=all_items)


def render_marketplace():
    query = (request.args.get('q') or "").strip()
    raw_velayat_id = request.args.get('velayat_id') or ''
    raw_district_id = request.args.get('district_id') or ''
    raw_neighborhood_id = request.args.get('neighborhood_id') or ''

    try:
        velayat_id = int(raw_velayat_id) if raw_velayat_id else None
    except ValueError:
        velayat_id = None

    try:
        district_id = int(raw_district_id) if raw_district_id else None
    except ValueError:
        district_id = None

    try:
        neighborhood_id = int(raw_neighborhood_id) if raw_neighborhood_id else None
    except ValueError:
        neighborhood_id = None

    items_query = Item.query.filter(Item.status != 'withdrawn') \
        .outerjoin(Neighborhood).outerjoin(District)

    if query:
        like_query = f"%{query}%"
        items_query = items_query.filter(
            or_(
                Item.title.ilike(like_query),
                Item.description.ilike(like_query),
                Item.category.ilike(like_query),
            )
        )

    if velayat_id:
        items_query = items_query.filter(District.velayat_id == velayat_id)
    if district_id:
        items_query = items_query.filter(Neighborhood.district_id == district_id)
    if neighborhood_id:
        items_query = items_query.filter(Item.neighborhood_id == neighborhood_id)

    items = items_query.order_by(Item.id.desc()).all()
    location_tree = get_location_tree()
    selected_location = {
        "velayat_id": velayat_id,
        "district_id": district_id,
        "neighborhood_id": neighborhood_id,
    }
    return render_template(
        'index.html',
        items=items,
        categories=category_list(items),
        search_query=query,
        location_tree=location_tree,
        selected_location=selected_location,
        expert_query=query if query else ''
    )


@app.route('/market')
def index():
    return render_marketplace()

@app.route('/search')
def search():
    return render_marketplace()

@app.route('/api/expert', methods=['POST'])
def expert_api():
    payload = request.get_json(silent=True) or {}
    item_query = (payload.get('item_query') or '').strip()
    user_request = (payload.get('question') or '').strip()
    if not item_query:
        return jsonify({'error': 'item_query is required'}), 400

    future = expert_executor.submit(live_engine.generate_live_expert_result, item_query, user_request)
    try:
        result = future.result(timeout=30)
    except FuturesTimeoutError:
        future.cancel()
        fallback = live_engine.generate_live_expert_result(item_query, user_request)
        response = jsonify(fallback['payload'])
        response.headers['X-Expert-Source'] = fallback.get('source', 'fallback')
        response.headers['X-Live-Provider-Available'] = 'true' if fallback.get('live_provider_available') else 'false'
        return response
    except Exception:
        return jsonify({'error': 'Expert engine failed'}), 502

    if not result or not result.get('payload'):
        return jsonify({'error': 'No expert data available'}), 503

    response = jsonify(result['payload'])
    response.headers['X-Expert-Source'] = result.get('source', 'unknown')
    response.headers['X-Live-Provider-Available'] = 'true' if result.get('live_provider_available') else 'false'
    return response

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            if current_user.is_authenticated:
                logout_user()
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid email or password')
    elif current_user.is_authenticated:
        flash('Sign in below to switch to another account.')
    return render_template('login.html')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Send a reset link. Real now — it used to be a form that refused.

    The response is identical whether or not the address has an account. A
    reset form that says "no such user" is a free membership oracle, and this
    is an invite-only product where membership is exactly what an attacker
    would like to enumerate.
    """
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        user = User.query.filter_by(email=email).first() if email else None
        if user:
            user.reset_token = generate_invite_token()
            user.reset_expires_at = datetime.utcnow() + timedelta(hours=RESET_TTL_HOURS)
            db.session.commit()
            send_password_reset_email(user)
        flash('If that address has an account, a reset link is on its way. '
              'The link expires in %d hours.' % RESET_TTL_HOURS)
        return redirect(url_for('login'))
    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Set a new password against an emailed, single-use, expiring token."""
    user = User.query.filter_by(reset_token=token).first()
    expired = (
        user is None
        or user.reset_expires_at is None
        or user.reset_expires_at < datetime.utcnow()
    )
    if expired:
        flash('That reset link is not valid any more. Ask for a new one.')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm_password') or ''
        if len(password) < 8:
            flash('Use at least 8 characters.')
            return redirect(url_for('reset_password', token=token))
        if password != confirm:
            flash('Those two passwords do not match.')
            return redirect(url_for('reset_password', token=token))

        user.password_hash = generate_password_hash(password, method='scrypt')
        # Burn the token in the same commit that changes the password, so a
        # replayed link cannot set it a second time.
        user.reset_token = None
        user.reset_expires_at = None
        db.session.commit()
        flash('Password changed. Sign in with it.')
        return redirect(url_for('login'))

    return render_template('reset_password.html', user=user, token=token)


@app.route('/verify-email/<token>')
def verify_email(token):
    """Confirm the applicant reads the inbox they applied with.

    This replaces the passport as the identity check. It is weaker as proof of
    who someone is and far stronger as proof that the contact details work —
    and the contact details are what an administrator, and later a courier,
    actually need.
    """
    access_request = AccessRequest.query.filter_by(verify_token=token).first()
    if not access_request:
        flash('That confirmation link is not valid.')
        return redirect(url_for('request_access'))

    if access_request.email_verified_at:
        flash('That address is already confirmed. An administrator will be in touch.')
        return redirect(url_for('login'))

    sent = access_request.verify_sent_at or access_request.created_at
    if sent and sent < datetime.utcnow() - timedelta(days=VERIFY_TTL_DAYS):
        flash('That confirmation link has expired. Please submit a new request.')
        return redirect(url_for('request_access'))

    access_request.email_verified_at = datetime.utcnow()
    access_request.verify_token = None
    db.session.commit()
    notify_admins_of_request(access_request)

    flash('Thank you — your address is confirmed and your request is now with '
          'our administrators.')
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """There is no self-service registration any more.

    This endpoint is kept because base.html and login.html hardcode the path
    "/register" rather than calling url_for. Renaming the route would not raise
    BuildError, it would silently 404 those links, so /register redirects.
    """
    return redirect(url_for('request_access'), code=302)


@app.route('/request-access', methods=['GET', 'POST'])
def request_access():
    """The front door. Anyone may knock; only an admin opens it."""
    location_tree = get_location_tree()

    if request.method == 'POST':
        full_name = (request.form.get('full_name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        phone = (request.form.get('phone') or '').strip()
        reason = (request.form.get('reason') or '').strip()
        age_value = (request.form.get('age') or '').strip()
        raw_neighborhood_id = (request.form.get('neighborhood_id') or '').strip()

        if not full_name:
            flash('Your full name is required.')
            return redirect(url_for('request_access'))
        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            flash('A valid email address is required.')
            return redirect(url_for('request_access'))
        if not phone:
            flash('A phone number is required so the courier can reach you.')
            return redirect(url_for('request_access'))

        age = None
        if age_value:
            if not age_value.isdigit() or not (16 <= int(age_value) <= 120):
                flash('Age must be a number between 16 and 120.')
                return redirect(url_for('request_access'))
            age = int(age_value)

        neighborhood = None
        if raw_neighborhood_id:
            try:
                neighborhood = Neighborhood.query.get(int(raw_neighborhood_id))
            except (TypeError, ValueError):
                neighborhood = None
        if not neighborhood:
            flash('Please choose where you are, down to the street or neighbourhood.')
            return redirect(url_for('request_access'))

        # The passport capture used to live here. It is gone: it wrote an
        # unvalidated file to disk from an unauthenticated route before it had
        # even decided whether to keep the request, it left declined
        # applicants' government ID on disk indefinitely, and an administrator
        # squinting at a phone photo was never real identity verification.
        # A confirmed email address is the proof now, and unlike the passport
        # it is something the system can actually check.

        # Whether the address is already taken or already queued is not
        # disclosed: the response is identical either way.
        already_known = (
            User.query.filter_by(email=email).first() is not None
            or AccessRequest.query.filter_by(email=email, status='pending').first() is not None
        )
        if not already_known:
            access_request = AccessRequest(
                full_name=full_name,
                email=email,
                phone=phone,
                region=neighborhood.district.velayat.name,
                neighborhood_id=neighborhood.id,
                age=age,
                reason=reason,
                status='pending',
                verify_token=generate_invite_token(),
                verify_sent_at=datetime.utcnow(),
            )
            db.session.add(access_request)
            db.session.commit()
            send_verification_email(access_request)

        flash('Check your email and confirm the address. Your request reaches an administrator once you do.')
        return redirect(url_for('login'))

    return render_template('request_access.html', location_tree=location_tree)


@app.route('/activate/<token>', methods=['GET', 'POST'])
def activate(token):
    """Where the User row is finally created, and nowhere else.

    The token is single-use and expires. A rejected or pending request has no
    live token at all, so neither can be activated by any path.
    """
    access_request = AccessRequest.query.filter_by(invite_token=token).first()

    if not access_request or access_request.status != 'approved':
        flash('That invitation is not valid.')
        return redirect(url_for('request_access'))

    state = access_request.invite_state
    if state == 'used':
        flash('That invitation has already been used. Sign in instead.')
        return redirect(url_for('login'))
    if state == 'expired':
        flash('That invitation has expired. Please submit a new access request.')
        return redirect(url_for('request_access'))
    if state != 'live':
        flash('That invitation is not valid.')
        return redirect(url_for('request_access'))

    if User.query.filter_by(email=access_request.email).first():
        # Belt and braces: an account already exists for this address.
        access_request.invite_used_at = datetime.utcnow()
        db.session.commit()
        flash('An account already exists for that email. Sign in instead.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        password = request.form.get('password') or ''
        confirm_password = request.form.get('confirm_password') or ''
        if len(password) < 8:
            flash('Your password must be at least 8 characters.')
            return redirect(url_for('activate', token=token))
        if password != confirm_password:
            flash('Those passwords do not match.')
            return redirect(url_for('activate', token=token))

        # Single-use: the token is spent by the same UPDATE that can only match
        # once, so two simultaneous submissions cannot both create an account.
        spent = db.session.execute(
            text("""
                UPDATE access_request SET invite_used_at = :now
                WHERE id = :rid AND invite_used_at IS NULL
            """),
            {"now": datetime.utcnow(), "rid": access_request.id}
        ).rowcount
        if not spent:
            db.session.rollback()
            flash('That invitation has already been used. Sign in instead.')
            return redirect(url_for('login'))

        user = User(
            username=access_request.email.split('@')[0],
            full_name=access_request.full_name,
            email=access_request.email,
            password_hash=generate_password_hash(password, method='scrypt'),
            region=access_request.region or 'Turkmenistan',
            age=access_request.age,

            # Verified means: this address was confirmed from the inbox, and
            # an administrator approved the person behind it. It no longer
            # means anybody looked at a passport, because nobody does.
            kyc_status='verified',
            role='member',
            wallet_balance=1000.0,
        )
        db.session.add(user)
        db.session.commit()

        if current_user.is_authenticated:
            logout_user()
        flash('Your account is ready. Sign in below.')
        return redirect(url_for('login'))

    return render_template('activate.html', access_request=access_request, token=token)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        neighborhood_id = request.form.get('neighborhood_id')
        neighborhood = None
        try:
            neighborhood = Neighborhood.query.get(int(neighborhood_id))
        except (TypeError, ValueError):
            neighborhood = None

        if not neighborhood:
            flash('Please select a valid neighborhood or street.')
            return redirect(url_for('upload'))

        file = request.files.get('item_image')
        camera_image = request.form.get('camera_image')
        image_url = "https://images.unsplash.com/photo-1555685812-4b943f1cb0eb?w=800"

        if not os.path.exists(app.config['UPLOAD_FOLDER_ITEMS']):
            os.makedirs(app.config['UPLOAD_FOLDER_ITEMS'])

        if file and file.filename != '':
            filename = secure_filename(f"{current_user.id}_{datetime.now().timestamp()}_{file.filename}")
            file_path = os.path.join(app.config['UPLOAD_FOLDER_ITEMS'], filename)
            file.save(file_path)
            image_url = url_for('static', filename=f'uploads/items/{filename}')
        elif camera_image:
            filename = secure_filename(f"{current_user.id}_{datetime.now().timestamp()}_capture.png")
            file_path = os.path.join(app.config['UPLOAD_FOLDER_ITEMS'], filename)
            save_data_url_image(camera_image, file_path)
            image_url = url_for('static', filename=f'uploads/items/{filename}')
            
        title = (request.form.get('title') or '').strip()
        category = (request.form.get('category') or '').strip()
        if not title or not category:
            flash('A title and a category are required.')
            return redirect(url_for('upload'))

        price = parse_price(request.form.get('price'))
        if price <= 0:
            flash('Enter a price greater than zero.')
            return redirect(url_for('upload'))

        size_class = (request.form.get('size_class') or '').strip()
        if size_class not in SIZE_CLASSES:
            size_class = default_size_class(category)

        weight_kg = None
        raw_weight = (request.form.get('weight_kg') or '').strip()
        if raw_weight:
            try:
                weight_kg = float(raw_weight)
            except ValueError:
                weight_kg = None
            if weight_kg is not None and weight_kg <= 0:
                weight_kg = None

        new_item = Item(
            title=title, price=price,
            size_class=size_class, weight_kg=weight_kg, status='listed',
            neighborhood_id=neighborhood.id,
            description=request.form.get('description'), image_url=image_url,
            category=category, user_id=current_user.id
        )
        db.session.add(new_item)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template(
        'upload.html',
        location_tree=get_location_tree(),
        size_classes=SIZE_CLASSES,
        categories=category_list(),
    )

# ---------------------------------------------------------------------------
# Orders
#
# A buyer orders a listed good and says where it must end up. The seller
# accepts. The buyer pays, and that payment is what creates the delivery.
# ---------------------------------------------------------------------------

def delivery_eta_days(band):
    return {'same_neighborhood': 1, 'same_district': 1, 'same_velayat': 2, 'cross_velayat': 4}[band]


def user_can_see_order(order, user):
    if not user.is_authenticated:
        return False
    if user.is_admin:
        return True
    if order.buyer_id == user.id or order.seller_id == user.id:
        return True
    return bool(order.delivery and order.delivery.courier_id == user.id)


def resolve_destination(raw_neighborhood_id):
    try:
        return Neighborhood.query.get(int(raw_neighborhood_id))
    except (TypeError, ValueError):
        return None


@app.route('/order/new/<int:item_id>', methods=['GET', 'POST'])
@login_required
def place_order(item_id):
    item = Item.query.get_or_404(item_id)

    if not item.user_id:
        flash("That listing has no seller attached and cannot be ordered.")
        return redirect(url_for('item_detail', item_id=item.id))
    if item.user_id == current_user.id:
        flash("You cannot order your own listing.")
        return redirect(url_for('item_detail', item_id=item.id))
    if item.status != 'listed':
        flash("That listing is no longer available.")
        return redirect(url_for('item_detail', item_id=item.id))
    # Blocking is part of the trust layer: it has to stop an order, not just a
    # message. Handing goods to someone you blocked is worse than a chat.
    if BlockedUser.query.filter(
        ((BlockedUser.blocker_id == current_user.id) & (BlockedUser.blocked_id == item.user_id)) |
        ((BlockedUser.blocker_id == item.user_id) & (BlockedUser.blocked_id == current_user.id))
    ).first():
        flash("You cannot order from this seller.")
        return redirect(url_for('item_detail', item_id=item.id))

    if request.method == 'POST':
        destination = resolve_destination(request.form.get('dest_neighborhood_id'))
        if not destination:
            flash('Choose where the goods have to arrive.')
            return redirect(url_for('place_order', item_id=item.id))

        address_line = (request.form.get('dest_address_line') or '').strip()
        contact_phone = (request.form.get('dest_contact_phone') or '').strip()
        if not address_line:
            flash('A street address is required so the courier can find you.')
            return redirect(url_for('place_order', item_id=item.id))
        if not contact_phone:
            flash('A contact phone number is required for the handover.')
            return redirect(url_for('place_order', item_id=item.id))

        proposed_price = None
        raw_proposed = (request.form.get('proposed_price') or '').strip()
        if raw_proposed:
            proposed_price = parse_price(raw_proposed)
            if proposed_price <= 0:
                flash('An offer has to be more than zero.')
                return redirect(url_for('place_order', item_id=item.id))

        quote = quote_order(item, destination, price_override=proposed_price)

        # The high-value gate. Everyone who came through the access queue is
        # verified, so in practice this only stops accounts made another way.
        if quote['goods'] > HIGH_VALUE_THRESHOLD and current_user.kyc_status != 'verified':
            flash('Your account has to be verified before you can order goods over %d TMT.'
                  % int(HIGH_VALUE_THRESHOLD))
            return redirect(url_for('item_detail', item_id=item.id))

        order = Order(
            buyer_id=current_user.id,
            seller_id=item.user_id,
            item_id=item.id,
            item_price=round(float(item.price or 0.0), 2),
            proposed_price=proposed_price,
            delivery_fee=quote['delivery_fee'],
            service_fee=quote['service_fee'],
            total=quote['total'],
            status='placed',
            dest_neighborhood_id=destination.id,
            dest_address_line=address_line,
            dest_contact_phone=contact_phone,
        )
        db.session.add(order)
        db.session.commit()
        flash('Order placed. The seller has to accept it before you pay.')
        return redirect(url_for('order_detail', order_id=order.id))

    return render_template(
        'order_new.html',
        item=item,
        location_tree=get_location_tree(),
        base_fee=DELIVERY_BASE_FEE,
        distance_surcharge=DELIVERY_DISTANCE_SURCHARGE,
        size_multiplier=DELIVERY_SIZE_MULTIPLIER,
        service_fee_rate=SERVICE_FEE_RATE,
    )


@app.route('/orders')
@login_required
def orders():
    purchases = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.id.desc()).all()
    sales = Order.query.filter_by(seller_id=current_user.id).order_by(Order.id.desc()).all()
    return render_template('orders.html', purchases=purchases, sales=sales)


@app.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    if not user_can_see_order(order, current_user):
        abort(404)
    return render_template('order_detail.html', order=order, delivery=order.delivery)


@app.route('/order/<int:order_id>/accept', methods=['POST'])
@login_required
def accept_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.seller_id != current_user.id:
        abort(404)
    updated = db.session.execute(
        text("UPDATE customer_order SET status='accepted', updated_at=:now "
             "WHERE id=:oid AND seller_id=:sid AND status='placed'"),
        {"now": datetime.utcnow(), "oid": order.id, "sid": current_user.id}
    ).rowcount
    db.session.commit()
    flash('Order accepted. The buyer can pay now.' if updated else 'That order is no longer waiting on you.')
    return redirect(url_for('order_detail', order_id=order.id))


@app.route('/order/<int:order_id>/reject', methods=['POST'])
@login_required
def reject_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.seller_id != current_user.id:
        abort(404)
    updated = db.session.execute(
        text("UPDATE customer_order SET status='rejected', updated_at=:now "
             "WHERE id=:oid AND seller_id=:sid AND status='placed'"),
        {"now": datetime.utcnow(), "oid": order.id, "sid": current_user.id}
    ).rowcount
    db.session.commit()
    flash('Order rejected.' if updated else 'That order is no longer waiting on you.')
    return redirect(url_for('order_detail', order_id=order.id))


@app.route('/order/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != current_user.id:
        abort(404)
    updated = db.session.execute(
        text("UPDATE customer_order SET status='cancelled', updated_at=:now "
             "WHERE id=:oid AND buyer_id=:bid AND status IN ('placed','accepted')"),
        {"now": datetime.utcnow(), "oid": order.id, "bid": current_user.id}
    ).rowcount
    db.session.commit()
    flash('Order cancelled.' if updated else 'That order can no longer be cancelled.')
    return redirect(url_for('order_detail', order_id=order.id))


@app.route('/order/<int:order_id>/pay', methods=['GET', 'POST'])
@login_required
def pay_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != current_user.id:
        abort(404)

    if request.method == 'GET':
        if order.status != 'accepted':
            flash('That order is not waiting for payment.')
            return redirect(url_for('order_detail', order_id=order.id))
        return render_template('order_payment.html', order=order)

    goods = round(order.agreed_price, 2)
    if goods > HIGH_VALUE_THRESHOLD and current_user.kyc_status != 'verified':
        flash('Your account has to be verified before you can pay for goods over %d TMT.'
              % int(HIGH_VALUE_THRESHOLD))
        return redirect(url_for('order_detail', order_id=order.id))

    account = PlatformAccount.query.filter_by(name=PLATFORM_ACCOUNT_NAME).first()
    if account is None:
        flash('Payments are unavailable right now.')
        return redirect(url_for('order_detail', order_id=order.id))

    total = round(order.total, 2)
    fees = round(order.delivery_fee + order.service_fee, 2)
    now = datetime.utcnow()

    try:
        # Claiming the order is the double-submission guard: the row can only
        # leave 'accepted' once, so a second POST matches nothing.
        claimed = db.session.execute(
            text("UPDATE customer_order SET status='paid', updated_at=:now "
                 "WHERE id=:oid AND buyer_id=:bid AND status='accepted'"),
            {"now": now, "oid": order.id, "bid": current_user.id}
        ).rowcount
        if not claimed:
            db.session.rollback()
            flash('That order has already been paid for.')
            return redirect(url_for('order_detail', order_id=order.id))

        # The balance check and the debit are one statement, so two requests
        # cannot both read a sufficient balance and both spend it.
        debited = db.session.execute(
            text("UPDATE user SET wallet_balance = wallet_balance - :total "
                 "WHERE id = :uid AND wallet_balance >= :total"),
            {"total": total, "uid": current_user.id}
        ).rowcount
        if not debited:
            db.session.rollback()
            flash('There is not enough in your wallet for this order.')
            return redirect(url_for('pay_order', order_id=order.id))

        # The money does not vanish: the goods price is held in escrow and the
        # fees are earned, both on the platform account.
        db.session.execute(
            text("UPDATE platform_account SET escrow_balance = escrow_balance + :goods, "
                 "balance = balance + :fees WHERE id = :aid"),
            {"goods": goods, "fees": fees, "aid": account.id}
        )

        item = order.item
        band = delivery_distance_band(item.neighborhood, order.dest_neighborhood)
        delivery = Delivery(
            order_id=order.id,
            origin_neighborhood_id=item.neighborhood_id,
            dest_neighborhood_id=order.dest_neighborhood_id,
            status='awaiting_pickup',
            pickup_code=generate_handoff_code(),
            dropoff_code=generate_handoff_code(),
            eta_date=(now + timedelta(days=delivery_eta_days(band))).date(),
            fee=order.delivery_fee,
        )
        db.session.add(delivery)
        db.session.flush()
        record_delivery_event(
            delivery, 'awaiting_pickup',
            'Payment received. Waiting for a courier to collect.', current_user
        )

        item.status = 'reserved'
        # Anything else anyone had open on this item is off.
        db.session.execute(
            text("UPDATE customer_order SET status='cancelled', updated_at=:now "
                 "WHERE item_id = :iid AND id != :oid AND status IN ('placed','accepted')"),
            {"now": now, "iid": item.id, "oid": order.id}
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('That payment could not be completed. Nothing has been charged.')
        return redirect(url_for('order_detail', order_id=order.id))

    flash('Paid. HandShake is holding %.2f TMT for the seller until the goods arrive.' % goods)
    return redirect(url_for('order_detail', order_id=order.id))


# ---------------------------------------------------------------------------
# Deliveries
#
# The codes are short, single-use and only ever compared on the server. The
# old QR was a bare permanent URL: whoever photographed it once could close
# the deal forever.
# ---------------------------------------------------------------------------

def user_can_see_delivery(delivery, user):
    return user_can_see_order(delivery.order, user)


def courier_owns(delivery, user):
    return user.is_admin or (delivery.courier_id is not None and delivery.courier_id == user.id)


@app.route('/delivery/<int:delivery_id>')
@login_required
def delivery_detail(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    if not user_can_see_delivery(delivery, current_user):
        abort(404)
    return render_template(
        'delivery_detail.html',
        delivery=delivery,
        order=delivery.order,
        events=delivery.events,
        can_drive=courier_owns(delivery, current_user),
    )


@app.route('/courier')
@courier_required
def courier_console():
    assigned = Delivery.query.filter(
        Delivery.courier_id == current_user.id
    ).order_by(Delivery.id.desc()).all()
    unclaimed = Delivery.query.filter(
        Delivery.courier_id.is_(None),
        Delivery.status == 'awaiting_pickup'
    ).order_by(Delivery.id.asc()).all()
    return render_template('courier_console.html', assigned=assigned, unclaimed=unclaimed)


@app.route('/delivery/<int:delivery_id>/claim', methods=['POST'])
@courier_required
def claim_delivery(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    claimed = db.session.execute(
        text("UPDATE delivery SET courier_id = :cid, updated_at = :now "
             "WHERE id = :did AND courier_id IS NULL"),
        {"cid": current_user.id, "now": datetime.utcnow(), "did": delivery.id}
    ).rowcount
    if claimed:
        record_delivery_event(delivery, delivery.status, 'Courier assigned.', current_user)
        db.session.commit()
        flash('This delivery is yours.')
    else:
        db.session.rollback()
        flash('Another courier already has that delivery.')
    return redirect(url_for('courier_console'))


@app.route('/delivery/<int:delivery_id>/pickup', methods=['POST'])
@courier_required
def delivery_pickup(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    if not courier_owns(delivery, current_user):
        abort(404)

    code = submitted_code(request.form.get('code'))
    if not code_matches(delivery.pickup_code, code):
        flash('That pickup code does not match.')
        return redirect(url_for('delivery_detail', delivery_id=delivery.id))

    now = datetime.utcnow()
    moved = db.session.execute(
        text("UPDATE delivery SET status='picked_up', picked_up_at=:now, "
             "pickup_code=NULL, updated_at=:now WHERE id=:did AND status='awaiting_pickup'"),
        {"now": now, "did": delivery.id}
    ).rowcount
    if not moved:
        db.session.rollback()
        flash('That delivery has already been collected.')
        return redirect(url_for('delivery_detail', delivery_id=delivery.id))

    record_delivery_event(delivery, 'picked_up', 'Collected from the seller.', current_user)
    db.session.commit()
    flash('Pickup confirmed.')
    return redirect(url_for('delivery_detail', delivery_id=delivery.id))


@app.route('/delivery/<int:delivery_id>/advance', methods=['POST'])
@courier_required
def advance_delivery(delivery_id):
    """Move one step along the pipeline. Only the steps the flow allows."""
    delivery = Delivery.query.get_or_404(delivery_id)
    if not courier_owns(delivery, current_user):
        abort(404)

    target = (request.form.get('status') or '').strip()
    if target not in ('in_transit', 'out_for_delivery'):
        flash('That is not a step a courier can take here.')
        return redirect(url_for('delivery_detail', delivery_id=delivery.id))
    if target not in DELIVERY_FLOW.get(delivery.status, ()):
        flash('A delivery cannot go from %s to %s.' % (delivery.status, target))
        return redirect(url_for('delivery_detail', delivery_id=delivery.id))

    moved = db.session.execute(
        text("UPDATE delivery SET status=:target, updated_at=:now "
             "WHERE id=:did AND status=:current"),
        {"target": target, "now": datetime.utcnow(), "did": delivery.id, "current": delivery.status}
    ).rowcount
    if not moved:
        db.session.rollback()
        flash('That delivery has already moved on.')
        return redirect(url_for('delivery_detail', delivery_id=delivery.id))

    record_delivery_event(delivery, target, (request.form.get('note') or '').strip() or None, current_user)
    db.session.commit()
    flash('Delivery is now %s.' % target.replace('_', ' '))
    return redirect(url_for('delivery_detail', delivery_id=delivery.id))


@app.route('/delivery/<int:delivery_id>/dropoff', methods=['POST'])
@courier_required
def delivery_dropoff(delivery_id):
    """The handover. This is where the seller finally gets paid."""
    delivery = Delivery.query.get_or_404(delivery_id)
    if not courier_owns(delivery, current_user):
        abort(404)

    code = submitted_code(request.form.get('code'))
    if not code_matches(delivery.dropoff_code, code):
        flash('That drop-off code does not match.')
        return redirect(url_for('delivery_detail', delivery_id=delivery.id))

    order = delivery.order
    account = PlatformAccount.query.filter_by(name=PLATFORM_ACCOUNT_NAME).first()
    goods = round(order.agreed_price, 2)
    now = datetime.utcnow()

    try:
        moved = db.session.execute(
            text("UPDATE delivery SET status='delivered', delivered_at=:now, "
                 "dropoff_code=NULL, updated_at=:now "
                 "WHERE id=:did AND status='out_for_delivery'"),
            {"now": now, "did": delivery.id}
        ).rowcount
        if not moved:
            db.session.rollback()
            flash('This delivery is not out for delivery, so it cannot be handed over.')
            return redirect(url_for('delivery_detail', delivery_id=delivery.id))

        released = db.session.execute(
            text("UPDATE platform_account SET escrow_balance = escrow_balance - :goods "
                 "WHERE id = :aid AND escrow_balance >= :goods"),
            {"goods": goods, "aid": account.id}
        ).rowcount
        if not released:
            db.session.rollback()
            flash('The escrowed amount could not be released. An administrator has to look at this.')
            return redirect(url_for('delivery_detail', delivery_id=delivery.id))

        db.session.execute(
            text("UPDATE user SET wallet_balance = wallet_balance + :goods WHERE id = :sid"),
            {"goods": goods, "sid": order.seller_id}
        )
        db.session.execute(
            text("UPDATE customer_order SET status='completed', updated_at=:now WHERE id=:oid"),
            {"now": now, "oid": order.id}
        )
        item = order.item
        if item:
            item.status = 'sold'

        record_delivery_event(
            delivery, 'delivered',
            'Handed to the buyer. %.2f TMT released to the seller.' % goods, current_user
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('That handover could not be recorded.')
        return redirect(url_for('delivery_detail', delivery_id=delivery.id))

    flash('Delivered. The seller has been paid.')
    return redirect(url_for('delivery_detail', delivery_id=delivery.id))


@app.route('/delivery/<int:delivery_id>/fail', methods=['POST'])
@courier_required
def fail_delivery(delivery_id):
    """Could not be handed over today. No money moves; the goods are still ours."""
    delivery = Delivery.query.get_or_404(delivery_id)
    if not courier_owns(delivery, current_user):
        abort(404)
    if 'failed' not in DELIVERY_FLOW.get(delivery.status, ()):
        flash('A delivery cannot fail from %s.' % delivery.status)
        return redirect(url_for('delivery_detail', delivery_id=delivery.id))

    moved = db.session.execute(
        text("UPDATE delivery SET status='failed', updated_at=:now WHERE id=:did AND status=:current"),
        {"now": datetime.utcnow(), "did": delivery.id, "current": delivery.status}
    ).rowcount
    if not moved:
        db.session.rollback()
        flash('That delivery has already moved on.')
        return redirect(url_for('delivery_detail', delivery_id=delivery.id))

    record_delivery_event(
        delivery, 'failed',
        (request.form.get('note') or '').strip() or 'Delivery attempt failed.', current_user
    )
    db.session.commit()
    flash('Recorded as failed.')
    return redirect(url_for('delivery_detail', delivery_id=delivery.id))


@app.route('/delivery/<int:delivery_id>/return', methods=['POST'])
@courier_required
def return_delivery(delivery_id):
    """The goods go back to the seller and the buyer is made whole."""
    delivery = Delivery.query.get_or_404(delivery_id)
    if not courier_owns(delivery, current_user):
        abort(404)
    if 'returned' not in DELIVERY_FLOW.get(delivery.status, ()):
        flash('A delivery cannot be returned from %s.' % delivery.status)
        return redirect(url_for('delivery_detail', delivery_id=delivery.id))

    order = delivery.order
    account = PlatformAccount.query.filter_by(name=PLATFORM_ACCOUNT_NAME).first()
    goods = round(order.agreed_price, 2)
    fees = round(order.delivery_fee + order.service_fee, 2)
    now = datetime.utcnow()

    try:
        moved = db.session.execute(
            text("UPDATE delivery SET status='returned', updated_at=:now "
                 "WHERE id=:did AND status=:current"),
            {"now": now, "did": delivery.id, "current": delivery.status}
        ).rowcount
        if not moved:
            db.session.rollback()
            flash('That delivery has already moved on.')
            return redirect(url_for('delivery_detail', delivery_id=delivery.id))

        # We did not deliver, so the buyer gets the whole total back and the
        # platform gives up the fees it had taken.
        unwound = db.session.execute(
            text("UPDATE platform_account SET escrow_balance = escrow_balance - :goods, "
                 "balance = balance - :fees "
                 "WHERE id = :aid AND escrow_balance >= :goods AND balance >= :fees"),
            {"goods": goods, "fees": fees, "aid": account.id}
        ).rowcount
        if not unwound:
            db.session.rollback()
            flash('The refund could not be unwound. An administrator has to look at this.')
            return redirect(url_for('delivery_detail', delivery_id=delivery.id))

        db.session.execute(
            text("UPDATE user SET wallet_balance = wallet_balance + :refund WHERE id = :bid"),
            {"refund": round(goods + fees, 2), "bid": order.buyer_id}
        )
        db.session.execute(
            text("UPDATE customer_order SET status='cancelled', updated_at=:now WHERE id=:oid"),
            {"now": now, "oid": order.id}
        )
        item = order.item
        if item and item.status == 'reserved':
            item.status = 'listed'

        record_delivery_event(
            delivery, 'returned',
            'Returned to the seller. %.2f TMT refunded to the buyer.' % (goods + fees), current_user
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('That return could not be recorded.')
        return redirect(url_for('delivery_detail', delivery_id=delivery.id))

    flash('Returned to the seller and refunded.')
    return redirect(url_for('delivery_detail', delivery_id=delivery.id))


# ---------------------------------------------------------------------------
# Administration
# ---------------------------------------------------------------------------

@app.route('/admin')
@admin_required
def admin_dashboard():
    account = PlatformAccount.query.filter_by(name=PLATFORM_ACCOUNT_NAME).first()
    stats = {
        'pending_requests': AccessRequest.query.filter_by(status='pending').count(),
        'members': User.query.count(),
        'couriers': User.query.filter_by(role='courier').count(),
        'listings': Item.query.filter_by(status='listed').count(),
        'open_orders': Order.query.filter(Order.status.in_(('placed', 'accepted', 'paid'))).count(),
        'open_deliveries': Delivery.query.filter(
            ~Delivery.status.in_(('delivered', 'returned'))
        ).count(),
    }
    return render_template('admin_dashboard.html', stats=stats, account=account)


@app.route('/admin/listings')
@admin_required
def admin_listings():
    """Every listing, and the power to take one down.

    `withdrawn` has been a declared item status since the logistics pivot with
    nothing in the application able to set it. This is what sets it: the one
    page from which a listing that should not be on the board can leave it.
    """
    status = request.args.get('status', 'listed')
    query = Item.query
    if status in ITEM_STATUSES:
        query = query.filter_by(status=status)
    listings = (query.order_by(Item.id.desc())
                     .options(db.joinedload(Item.owner),
                              db.joinedload(Item.neighborhood))
                     .limit(200).all())
    return render_template(
        'admin_listings.html',
        listings=listings,
        status=status,
        statuses=ITEM_STATUSES,
        counts={s: Item.query.filter_by(status=s).count() for s in ITEM_STATUSES},
    )


@app.route('/admin/listings/<int:item_id>/withdraw', methods=['POST'])
@admin_required
def admin_withdraw_listing(item_id):
    item = Item.query.get_or_404(item_id)
    if item.status == 'withdrawn':
        flash('That listing is already withdrawn.')
        return redirect(url_for('admin_listings', status=request.form.get('back') or 'listed'))
    # A reserved or sold item is attached to an order that is still running;
    # pulling it out from under the buyer would strand a delivery.
    if item.status in ('reserved', 'sold'):
        flash('That listing is part of a live order. Settle the order first.')
        return redirect(url_for('admin_listings', status=request.form.get('back') or 'listed'))
    item.status = 'withdrawn'
    db.session.commit()
    flash('"%s" has been taken off the board.' % item.title)
    return redirect(url_for('admin_listings', status=request.form.get('back') or 'listed'))


@app.route('/admin/listings/<int:item_id>/restore', methods=['POST'])
@admin_required
def admin_restore_listing(item_id):
    item = Item.query.get_or_404(item_id)
    if item.status != 'withdrawn':
        flash('That listing is not withdrawn.')
        return redirect(url_for('admin_listings', status='withdrawn'))
    item.status = 'listed'
    db.session.commit()
    flash('"%s" is back on the board.' % item.title)
    return redirect(url_for('admin_listings', status='withdrawn'))


@app.route('/admin/orders')
@admin_required
def admin_orders():
    """Every order in the system, whoever it belongs to."""
    status = request.args.get('status', 'all')
    query = Order.query
    if status != 'all':
        query = query.filter_by(status=status)
    orders = (query.order_by(Order.id.desc())
                   .options(db.joinedload(Order.item),
                            db.joinedload(Order.buyer),
                            db.joinedload(Order.seller),
                            db.joinedload(Order.delivery))
                   .limit(200).all())
    statuses = ('placed', 'accepted', 'rejected', 'cancelled', 'paid', 'completed')
    return render_template(
        'admin_orders.html',
        orders=orders,
        status=status,
        statuses=statuses,
        counts={s: Order.query.filter_by(status=s).count() for s in statuses},
        total_held=sum(o.total for o in Order.query.filter_by(status='paid').all()),
    )


@app.route('/admin/access-requests')
@admin_required
def admin_access_requests():
    status = request.args.get('status', 'pending')
    if status not in ('pending', 'approved', 'rejected', 'all'):
        status = 'pending'
    query = AccessRequest.query
    if status != 'all':
        query = query.filter_by(status=status)
    requests_list = query.order_by(AccessRequest.created_at.desc(), AccessRequest.id.desc()).all()
    return render_template(
        'admin_access_requests.html',
        access_requests=requests_list,
        status=status,
        invite_ttl_days=INVITE_TTL_DAYS,
    )


@app.route('/admin/access-requests/<int:request_id>/approve', methods=['POST'])
@admin_required
def approve_access_request(request_id):
    access_request = AccessRequest.query.get_or_404(request_id)
    if access_request.status != 'pending':
        flash('That request has already been reviewed.')
        return redirect(url_for('admin_access_requests'))
    if User.query.filter_by(email=access_request.email).first():
        flash('An account already exists for that email address.')
        return redirect(url_for('admin_access_requests'))

    now = datetime.utcnow()
    access_request.status = 'approved'
    access_request.reviewed_at = now
    access_request.reviewed_by_id = current_user.id
    access_request.review_note = (request.form.get('review_note') or '').strip() or None
    access_request.invite_token = generate_invite_token()
    access_request.invite_expires_at = now + timedelta(days=INVITE_TTL_DAYS)
    access_request.invite_used_at = None
    db.session.commit()

    # The admin used to have to copy this link out of a flash message and
    # deliver it themselves. It is emailed to the applicant now.
    delivered = send_invite_email(access_request)
    if delivered and mailer.configured:
        flash('Approved. The invitation has been emailed to %s.' % access_request.email)
    elif delivered:
        flash('Approved. No SMTP is configured, so the invitation was written to '
              'instance/outbox instead of sent. Link: %s'
              % url_for('activate', token=access_request.invite_token, _external=True))
    else:
        flash('Approved, but %s is not a valid address, so nothing could be sent. '
              'Link: %s' % (access_request.email,
                            url_for('activate', token=access_request.invite_token, _external=True)))
    return redirect(url_for('admin_access_requests'))


@app.route('/admin/access-requests/<int:request_id>/reject', methods=['POST'])
@admin_required
def reject_access_request(request_id):
    access_request = AccessRequest.query.get_or_404(request_id)
    if access_request.status != 'pending':
        flash('That request has already been reviewed.')
        return redirect(url_for('admin_access_requests'))

    access_request.status = 'rejected'
    access_request.reviewed_at = datetime.utcnow()
    access_request.reviewed_by_id = current_user.id
    access_request.review_note = (request.form.get('review_note') or '').strip() or None
    # A rejected request holds no token, so there is nothing to activate.
    access_request.invite_token = None
    access_request.invite_expires_at = None
    db.session.commit()
    # Silence is the worst outcome for someone waiting on a decision.
    send_rejection_email(access_request)
    flash('Request rejected, and %s has been told.' % access_request.email)
    return redirect(url_for('admin_access_requests'))


@app.route('/admin/users')
@admin_required
def admin_users():
    people = User.query.order_by(User.id.asc()).all()
    for person in people:
        normalize_user_profile_pic(person)
    return render_template('admin_users.html', people=people)


@app.route('/admin/users/<int:user_id>/role', methods=['POST'])
@admin_required
def admin_set_role(user_id):
    person = User.query.get_or_404(user_id)
    role = (request.form.get('role') or '').strip()
    if role not in ('member', 'courier', 'admin'):
        flash('That is not a role.')
        return redirect(url_for('admin_users'))
    if person.id == current_user.id and role != 'admin':
        # Never let the last pair of hands lock itself out.
        flash('You cannot remove your own admin role.')
        return redirect(url_for('admin_users'))
    person.role = role
    db.session.commit()
    flash('%s is now a %s.' % (person.full_name or person.email, role))
    return redirect(url_for('admin_users'))


@app.route('/admin/deliveries')
@admin_required
def admin_deliveries():
    open_deliveries = Delivery.query.filter(
        ~Delivery.status.in_(('delivered', 'returned'))
    ).order_by(Delivery.id.asc()).all()
    closed = Delivery.query.filter(
        Delivery.status.in_(('delivered', 'returned'))
    ).order_by(Delivery.id.desc()).limit(25).all()
    couriers = User.query.filter(User.role.in_(('courier', 'admin'))).order_by(User.id.asc()).all()
    return render_template(
        'admin_deliveries.html',
        open_deliveries=open_deliveries,
        closed=closed,
        couriers=couriers,
    )


@app.route('/admin/deliveries/<int:delivery_id>/assign', methods=['POST'])
@admin_required
def admin_assign_courier(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    raw_courier_id = (request.form.get('courier_id') or '').strip()
    if not raw_courier_id:
        delivery.courier_id = None
        record_delivery_event(delivery, delivery.status, 'Courier unassigned.', current_user)
        db.session.commit()
        flash('Courier unassigned.')
        return redirect(url_for('admin_deliveries'))

    courier = User.query.get(int(raw_courier_id)) if raw_courier_id.isdigit() else None
    if not courier or not courier.is_courier:
        flash('That person is not a courier.')
        return redirect(url_for('admin_deliveries'))

    delivery.courier_id = courier.id
    record_delivery_event(
        delivery, delivery.status,
        'Assigned to %s.' % (courier.full_name or courier.email), current_user
    )
    db.session.commit()
    flash('Assigned to %s.' % (courier.full_name or courier.email))
    return redirect(url_for('admin_deliveries'))


@app.route('/profile/<int:user_id>')
def profile(user_id):
    user = User.query.get_or_404(user_id)
    normalize_user_profile_pic(user)
    reviews = Review.query.filter_by(target_user_id=user_id).all()
    for review in reviews:
        normalize_user_profile_pic(review.reviewer)

    chat_request = None
    has_blocked_user = False
    blocked_by_user = False
    profile_pending_requests = []

    if current_user.is_authenticated:
        if current_user.id != user_id:
            _, chat_request = get_chat_connection_state(current_user.id, user_id)
        has_blocked_user = BlockedUser.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first() is not None
        blocked_by_user = BlockedUser.query.filter_by(blocker_id=user_id, blocked_id=current_user.id).first() is not None
        if current_user.id == user_id:
            profile_pending_requests = ChatRequest.query.filter_by(
                recipient_id=current_user.id,
                status='pending'
            ).order_by(ChatRequest.timestamp.desc()).all()
            for req in profile_pending_requests:
                normalize_user_profile_pic(req.sender)

    return render_template(
        'profile.html',
        user=user,
        reviews=reviews,
        chat_request=chat_request,
        has_blocked_user=has_blocked_user,
        blocked_by_user=blocked_by_user,
        profile_pending_requests=profile_pending_requests
    )

@app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        full_name = (request.form.get('full_name') or '').strip()
        region = (request.form.get('region') or '').strip()
        bio = (request.form.get('bio') or '').strip()

        if not full_name:
            flash('Full name is required.')
            return redirect(url_for('edit_profile'))
        if not region:
            flash('Location is required.')
            return redirect(url_for('edit_profile'))

        current_user.full_name = full_name
        current_user.bio = bio
        current_user.region = region
        
        # Profile Picture
        file = request.files.get('profile_pic')
        camera_image = request.form.get('camera_image')
        
        if not os.path.exists(app.config['UPLOAD_FOLDER_PROFILES']):
            os.makedirs(app.config['UPLOAD_FOLDER_PROFILES'])
            
        if file and file.filename != '':
            filename = secure_filename(f"profile_{current_user.id}_{file.filename}")
            file_path = os.path.join(app.config['UPLOAD_FOLDER_PROFILES'], filename)
            file.save(file_path)
            current_user.profile_pic = url_for('static', filename=f'uploads/profiles/{filename}')
        elif camera_image:
            filename = secure_filename(f"profile_{current_user.id}_capture.png")
            file_path = os.path.join(app.config['UPLOAD_FOLDER_PROFILES'], filename)
            save_data_url_image(camera_image, file_path)
            current_user.profile_pic = url_for('static', filename=f'uploads/profiles/{filename}')

        normalize_user_profile_pic(current_user)
        db.session.commit()
        return redirect(url_for('profile', user_id=current_user.id))
    return render_template('edit_profile.html')

# Chat Logic
@app.route('/send-chat-request/<int:recipient_id>')
@login_required
def send_chat_request(recipient_id):
    User.query.get_or_404(recipient_id)

    if recipient_id == current_user.id:
        flash('You cannot chat-request yourself.')
        return redirect(url_for('profile', user_id=recipient_id))

    if BlockedUser.query.filter(
        ((BlockedUser.blocker_id == current_user.id) & (BlockedUser.blocked_id == recipient_id)) |
        ((BlockedUser.blocker_id == recipient_id) & (BlockedUser.blocked_id == current_user.id))
    ).first():
        flash('Chat request unavailable because one of you is blocked.')
        return redirect(url_for('profile', user_id=recipient_id))

    state, existing = get_chat_connection_state(current_user.id, recipient_id)
    if state == 'none':
        req = ChatRequest(sender_id=current_user.id, recipient_id=recipient_id)
        db.session.add(req)
        db.session.commit()
        flash('Chat request sent!')
    elif state == 'accepted':
        flash('You already have an active chat with this user.')
        return redirect(url_for('chat', recipient_id=recipient_id))
    elif state == 'outgoing_pending':
        flash('Chat request already exists.')
    else:
        flash('This user already sent you a request. Open Messages to accept it.')
        return redirect(url_for('chat', tab='requests'))
    return redirect(url_for('profile', user_id=recipient_id))

@app.route('/accept-chat-request/<int:request_id>')
@login_required
def accept_chat_request(request_id):
    req = ChatRequest.query.get_or_404(request_id)
    if req.recipient_id == current_user.id and req.status == 'pending':
        req.status = 'accepted'
        db.session.commit()
        return redirect(url_for('chat', recipient_id=req.sender_id))
    flash('This chat request is no longer available.')
    return redirect(url_for('chat'))

@app.route('/reject-chat-request/<int:request_id>')
@login_required
def reject_chat_request(request_id):
    req = ChatRequest.query.get_or_404(request_id)
    if req.recipient_id == current_user.id and req.status == 'pending':
        req.status = 'rejected'
        db.session.delete(req)
        db.session.commit()
    else:
        flash('This chat request is no longer available.')
    return redirect(url_for('chat'))

@app.route('/block-user/<int:user_id>')
@login_required
def block_user(user_id):
    if user_id == current_user.id:
        flash('You cannot block yourself.')
        return redirect(url_for('profile', user_id=current_user.id))

    existing = BlockedUser.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first()
    if not existing:
        block = BlockedUser(blocker_id=current_user.id, blocked_id=user_id)
        db.session.add(block)
        # Also delete any chat requests
        ChatRequest.query.filter(
            ((ChatRequest.sender_id == current_user.id) & (ChatRequest.recipient_id == user_id)) |
            ((ChatRequest.sender_id == user_id) & (ChatRequest.recipient_id == current_user.id))
        ).delete()
        db.session.commit()
        flash('User blocked.')
    return redirect(url_for('index'))

@app.route('/unblock-user/<int:user_id>')
@login_required
def unblock_user(user_id):
    BlockedUser.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).delete()
    db.session.commit()
    flash('User unblocked.')
    return redirect(url_for('profile', user_id=user_id))

@app.route('/chat')
@app.route('/chat/<int:recipient_id>')
@login_required
def chat(recipient_id=None):
    # Only show accepted chats
    accepted_requests = ChatRequest.query.filter(
        ((ChatRequest.sender_id == current_user.id) | (ChatRequest.recipient_id == current_user.id)) &
        (ChatRequest.status == 'accepted')
    ).order_by(ChatRequest.timestamp.desc()).all()
    
    active_chat_users = []
    seen_user_ids = set()
    for req in accepted_requests:
        other_user = req.recipient if req.sender_id == current_user.id else req.sender
        if other_user and other_user.id not in seen_user_ids:
            normalize_user_profile_pic(other_user)
            active_chat_users.append(other_user)
            seen_user_ids.add(other_user.id)

    pending_requests = ChatRequest.query.filter_by(
        recipient_id=current_user.id,
        status='pending'
    ).order_by(ChatRequest.timestamp.desc()).all()
    for req in pending_requests:
        normalize_user_profile_pic(req.sender)

    messages = []
    active_recipient = None
    initial_tab = request.args.get('tab', 'chats')
    if initial_tab not in ('chats', 'requests'):
        initial_tab = 'chats'
    if 'tab' not in request.args and pending_requests:
        initial_tab = 'requests'

    if recipient_id:
        state, _ = get_chat_connection_state(current_user.id, recipient_id)

        if state == 'accepted':
            active_recipient = User.query.get_or_404(recipient_id)
            normalize_user_profile_pic(active_recipient)
            messages = Message.query.filter(
                ((Message.sender_id == current_user.id) & (Message.recipient_id == recipient_id)) |
                ((Message.sender_id == recipient_id) & (Message.recipient_id == current_user.id))
            ).order_by(Message.timestamp.asc()).all()
            initial_tab = 'chats'
        elif state == 'incoming_pending':
            flash("This user requested to chat with you. Accept it in Requests first.")
            return redirect(url_for('chat', tab='requests'))
        elif state == 'outgoing_pending':
            flash("Your chat request is still pending approval.")
            return redirect(url_for('chat'))
        else:
            flash("Send a chat request first before messaging this user.")
            return redirect(url_for('profile', user_id=recipient_id))

    if initial_tab == 'chats' and not active_recipient and pending_requests and not active_chat_users:
        initial_tab = 'requests'

    return render_template(
        'chat.html',
        active_chat_users=active_chat_users,
        pending_requests=pending_requests,
        messages=messages,
        active_recipient=active_recipient,
        initial_tab=initial_tab
    )

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    recipient_id = request.form.get('recipient_id')
    body = (request.form.get('body') or '').strip()

    try:
        recipient_id = int(recipient_id)
    except (TypeError, ValueError):
        flash("Invalid message recipient.")
        return redirect(url_for('chat'))
    
    # Check if either side has blocked the other.
    if BlockedUser.query.filter(
        ((BlockedUser.blocker_id == recipient_id) & (BlockedUser.blocked_id == current_user.id)) |
        ((BlockedUser.blocker_id == current_user.id) & (BlockedUser.blocked_id == recipient_id))
    ).first():
        flash("Messaging is unavailable because one of you is blocked.")
        return redirect(url_for('chat'))

    if not has_accepted_chat_between(current_user.id, recipient_id):
        flash("You need an accepted chat request before sending messages.")
        return redirect(url_for('profile', user_id=recipient_id))

    if recipient_id and body:
        msg = Message(sender_id=current_user.id, recipient_id=recipient_id, body=body)
        db.session.add(msg)
        db.session.commit()
        return redirect(url_for('chat', recipient_id=recipient_id))
    return redirect(url_for('chat'))

@app.route('/item/<int:item_id>')
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    reviews = Review.query.filter_by(item_id=item_id).all()
    chat_request = None
    chat_state = 'none'
    if current_user.is_authenticated and item.owner and current_user.id != item.owner.id:
        chat_state, chat_request = get_chat_connection_state(current_user.id, item.owner.id)
    return render_template('item_detail.html', item=item, reviews=reviews, chat_request=chat_request, chat_state=chat_state)

def recompute_ratings(item):
    """Re-derive a listing's score, and its seller's, from the review rows.

    Both columns default to 5.0 with num_ratings=1, and the demo seeder fills
    listings with plausible random scores so the board does not look dead. Real
    reviews take over from that: once a listing has any, its score is the mean
    of them rather than a number nobody earned. A listing with no real reviews
    keeps whatever it was given, which for seeded demo data is the point.

    The seller's own rating had no writer at all before this — every profile in
    the app was showing the 5.0 default no matter what anyone thought.
    """
    item_scores = [r.rating for r in Review.query.filter_by(item_id=item.id).all()]
    if item_scores:
        item.rating = round(sum(item_scores) / len(item_scores), 2)
        item.num_ratings = len(item_scores)

    seller = User.query.get(item.user_id) if item.user_id else None
    if seller:
        seller_scores = [
            r.rating for r in Review.query.filter_by(target_user_id=seller.id).all()
        ]
        if seller_scores:
            seller.rating = round(sum(seller_scores) / len(seller_scores), 2)
            seller.num_ratings = len(seller_scores)


@app.route('/rate_item/<int:item_id>', methods=['POST'])
@login_required
def rate_item(item_id):
    """Review a listing you actually received.

    This used to accept a review from any signed-in account, for any listing,
    including your own, any number of times — and it recomputed the listing's
    score on every one. A seller could put their whole board at 5.0 in a loop.
    Three things gate it now: the reviewer must have taken delivery of the item,
    they cannot be the seller, and they get one review per listing.

    It also recomputes the seller's own rating, which no code path had ever
    written: every profile in the app was displaying the 5.0 default.
    """
    item = Item.query.get_or_404(item_id)

    try:
        rating = int(request.form.get('rating') or 0)
    except (TypeError, ValueError):
        # Was uncaught, so a non-numeric rating was a 500.
        flash('Rating must be a whole number between 1 and 5.')
        return redirect(url_for('item_detail', item_id=item_id))

    content = (request.form.get('content') or '').strip()
    if rating < 1 or rating > 5:
        flash('Rating must be between 1 and 5.')
        return redirect(url_for('item_detail', item_id=item_id))
    if not content:
        flash('Review cannot be empty.')
        return redirect(url_for('item_detail', item_id=item_id))

    if item.user_id == current_user.id:
        flash('You cannot review your own listing.')
        return redirect(url_for('item_detail', item_id=item_id))

    # Earned by taking delivery, not by holding an account.
    received = Order.query.filter(
        Order.item_id == item_id,
        Order.buyer_id == current_user.id,
        Order.status == 'completed',
    ).first()
    if not received:
        flash('Only someone who has received this item can review it.')
        return redirect(url_for('item_detail', item_id=item_id))

    already = Review.query.filter_by(
        reviewer_id=current_user.id, item_id=item_id
    ).first()
    if already:
        flash('You have already reviewed this listing.')
        return redirect(url_for('item_detail', item_id=item_id))

    review = Review(
        content=content, rating=rating, reviewer_id=current_user.id,
        item_id=item_id, target_user_id=item.user_id
    )
    db.session.add(review)
    db.session.flush()

    recompute_ratings(item)
    db.session.commit()
    flash('Thank you for the review.')
    return redirect(url_for('item_detail', item_id=item_id))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# CLI
#
#     flask --app app create-admin someone@example.com
#     flask --app app create-courier someone@example.com
#
# Neither creates an account. There is no path from nothing to an account
# except an approved access request.
# ---------------------------------------------------------------------------

def _set_role(email, role):
    email = (email or '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        raise click.ClickException(
            "No account with the email %s. They have to be approved through "
            "/admin/access-requests first." % email
        )
    user.role = role
    db.session.commit()
    return user


@app.cli.command('create-admin')
@click.argument('email')
def create_admin_command(email):
    """Promote an existing account to administrator."""
    user = _set_role(email, 'admin')
    click.echo("%s is now an administrator." % user.email)


@app.cli.command('create-courier')
@click.argument('email')
def create_courier_command(email):
    """Promote an existing account to courier."""
    user = _set_role(email, 'courier')
    click.echo("%s is now a courier." % user.email)


@app.cli.command('money-check')
def money_check_command():
    """Print every wallet plus the platform account. The total must not drift."""
    wallets = db.session.query(db.func.coalesce(db.func.sum(User.wallet_balance), 0.0)).scalar()
    account = PlatformAccount.query.filter_by(name=PLATFORM_ACCOUNT_NAME).first()
    held = (account.balance + account.escrow_balance) if account else 0.0
    click.echo("wallets          %.2f" % wallets)
    click.echo("platform fees    %.2f" % (account.balance if account else 0.0))
    click.echo("platform escrow  %.2f" % (account.escrow_balance if account else 0.0))
    click.echo("TOTAL            %.2f" % (wallets + held))

if __name__ == '__main__':
    # Deliberately not debug=True. The Werkzeug debugger hands anyone who can
    # reach a traceback an interactive Python console on this machine, and this
    # is the entrypoint people actually type. It used to start that console.
    #
    # `python run_lan.py` is still the way to serve the app on the network; this
    # binds to localhost only, so a mistake here cannot reach the LAN.
    #
    # If you want the debugger while working on a route, ask for it explicitly:
    #     HANDSHAKE_DEBUG=1 python app.py
    debug = os.environ.get('HANDSHAKE_DEBUG') == '1'
    if debug:
        print('  WARNING: debugger on. Never do this on a reachable interface.')
    app.run(host='127.0.0.1', port=5000, debug=debug)
