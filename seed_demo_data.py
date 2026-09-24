"""
Seed realistic demo goods for HandShake to deliver.

Data only. This script inserts rows through the existing SQLAlchemy models and
never touches the schema, app.py or ai_logic.py. It is safe to run repeatedly:
listings are matched on title, so a second run updates nothing and inserts
nothing that is already there.

Photos are real photographs pulled once from Wikimedia Commons, written into
static/uploads/items/ and referenced with the same
"/static/uploads/items/<file>" path that a real upload through the form
produces, so seeded listings behave exactly like user-uploaded ones. Nothing
points at a remote host at render time and nothing falls back to a grey box.

    python seed_demo_data.py            # insert missing listings, fetch photos
    python seed_demo_data.py --reset    # remove seeded listings first
    python seed_demo_data.py --repair   # re-point older rows at local photos
"""

import json
import os
import random
import subprocess
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from app import app, db, Item, User, Neighborhood, District, Velayat

IMAGE_DIR = os.path.join("static", "uploads", "items")
IMAGE_PREFIX = "seed_"
WEB_PREFIX = "/static/uploads/items/"

# Wikimedia Commons is the photo source: real photographs, openly licensed,
# and searchable by subject. Files land on disk once and are served locally
# from then on.
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "HandShakeSeeder/1.0 (local demo data)"

# When a subject search comes back with nothing usable, fall back to a broader
# term for the category rather than to a placeholder.
CATEGORY_FALLBACK = {
    "tech": "consumer electronics product photo",
    "tools": "power tool workshop",
    "cars": "car parked street",
    "hobbies": "sports equipment",
    "books": "stack of books",
    "houses": "apartment interior room",
    "phones": "smartphone product photo",
    "computers": "desktop computer",
    "appliances": "kitchen appliance",
    "furniture": "wooden furniture room",
    "building": "building materials stack",
    "parts": "car engine parts",
    "bikes": "bicycle",
    "clothing": "folded clothing",
    "shoes": "leather shoes",
    "kids": "children toys",
    "sports": "sports equipment",
    "music": "musical instrument",
    "garden": "garden plants",
    "pets": "pet supplies",
    "beauty": "cosmetics bottles",
    "business": "warehouse shelving",
}

# title, category, size class, price in TMT, weight in kg, photo keyword, description
LISTINGS = [
    # ---- Tools -----------------------------------------------------------
    ("Makita Angle Grinder", "tools", "medium", 45, 4.0, "grinder",
     "125mm grinder with three cutting discs and a spare guard. Good for tile and rebar."),
    ("Concrete Mixer, 120L", "tools", "large", 180, 160.0, "concrete,mixer",
     "Tows behind a car. Heavy, so it goes in the large size band."),
    ("Scaffold Tower, 4m", "tools", "large", 220, 90.0, "scaffolding",
     "Aluminium, two platforms and stabilisers. Two people can put it up in ten minutes."),
    ("Wallpaper Steamer", "tools", "medium", 35, 6.0, "steamer",
     "Strips a whole room in an afternoon. Comes with a long hose and a small plate."),
    ("Wet Tile Cutter", "tools", "large", 70, 35.0, "tile,cutter",
     "Cuts up to 60cm porcelain. New blade fitted last month."),
    ("Impact Driver Set", "tools", "small", 40, 3.5, "impact,driver",
     "18V brushless, two batteries, 40-piece bit set in a case."),
    ("Extension Ladder, 6m", "tools", "large", 30, 18.0, "ladder",
     "Aluminium triple-section. Fits on a roof rack, not inside a car."),
    ("Pressure Washer", "tools", "medium", 55, 12.0, "pressure,washer",
     "150 bar with a patio head and a car brush. Bring your own hose."),

    # ---- Tech ------------------------------------------------------------
    ("MacBook Pro 14, M3", "tech", "small", 260, 1.6, "macbook",
     "16GB and 512GB. Wiped and reinstalled before it ships. Charger and sleeve included."),
    ("iPad Pro 12.9 with Pencil", "tech", "small", 140, 0.7, "ipad",
     "For drawing and site drawings. Screen protector on, no scratches."),
    ("Epson Projector, 1080p", "tech", "medium", 120, 3.2, "projector",
     "3000 lumens, works in a half-lit room. HDMI and a 5m cable included."),
    ("Studio Lighting Kit", "tech", "large", 95, 22.0, "studio,lighting",
     "Two softboxes, one backlight, stands and a grey backdrop."),
    ("Rode Wireless Mic Set", "tech", "small", 65, 0.6, "microphone",
     "Two transmitters and a receiver. Good for interviews and weddings."),
    ("Gaming PC, RTX 4070", "tech", "large", 300, 14.0, "gaming,computer",
     "Ryzen 7, 32GB, 1TB. Monitor not included unless you ask."),
    ("Portable Power Station", "tech", "medium", 85, 11.0, "power,station",
     "1000Wh. Runs a fridge for about a day, or a laptop for a week."),
    ("Dell 27in 4K Monitor", "tech", "medium", 2400, 6.5, "monitor",
     "Two years old, no dead pixels. Selling because I moved to a laptop."),
    ("DJI Osmo Gimbal", "tech", "small", 70, 0.5, "gimbal",
     "Three-axis for phones. Balanced and ready, takes a minute to set up."),

    # ---- Cars ------------------------------------------------------------
    ("Hyundai Sonata 2021", "cars", "large", 420, 1450.0, "hyundai,sedan",
     "Automatic, cold air conditioning, full tank at pickup. Ashgabat only."),
    ("Lexus LX570", "cars", "large", 1300, 2700.0, "lexus,suv",
     "Seven seats, full service history. Collection from the garage, or we move it for you."),
    ("Toyota Land Cruiser Prado", "cars", "large", 900, 2300.0, "land,cruiser",
     "Proper desert car. Roof rack and a second spare wheel included."),
    ("Nissan Almera", "cars", "large", 260, 1100.0, "nissan,car",
     "Small, cheap on fuel, easy to park. A good first car."),
    ("Mercedes Sprinter, 16 seats", "cars", "large", 1100, 3000.0, "sprinter,van",
     "For groups and airport runs. Driver available for 200 TMT more."),
    ("Kia Rio 2020", "cars", "large", 240, 1100.0, "kia,car",
     "Manual gearbox. Clean, serviced in spring, new tyres."),

    # ---- Hobbies ---------------------------------------------------------
    ("Yamaha Acoustic Guitar", "hobbies", "medium", 35, 2.5, "acoustic,guitar",
     "FG800 with a soft case, capo and spare strings. Freshly tuned."),
    ("Roland Electric Piano, 88 keys", "hobbies", "large", 110, 26.0, "piano,keyboard",
     "Weighted keys and a stand. Two people needed to carry it."),
    ("Camping Set for Four", "hobbies", "large", 130, 24.0, "camping,tent",
     "Four-person tent, four mats, two sleeping bags and a gas stove."),
    ("Telescope, 130mm Reflector", "hobbies", "medium", 90, 9.0, "telescope",
     "Two eyepieces and a moon filter. Best outside the city lights."),
    ("Kayak, Two Seat", "hobbies", "large", 150, 18.0, "kayak",
     "Inflatable with a pump, two paddles and buoyancy aids."),
    ("Chess Set, Tournament Size", "hobbies", "small", 15, 2.0, "chess",
     "Weighted pieces and a roll-up board. Clock included."),
    ("GoPro Hero 12", "hobbies", "small", 85, 0.4, "gopro,action,camera",
     "Chest mount, head strap, two batteries and a 64GB card."),
    ("Road Bike, 54cm Frame", "hobbies", "large", 70, 9.0, "road,bicycle",
     "Carbon fork, recently serviced. Helmet and a pump come with it."),
    ("DSLR Starter Kit", "hobbies", "small", 95, 2.2, "dslr,camera",
     "Body, 18-55mm and 50mm lens, bag and two cards. Good for learning."),
    ("Drone with 4K Camera", "hobbies", "medium", 160, 2.0, "drone",
     "Three batteries, controller and a case. Everything in the box, nothing missing."),
    ("Football Kit, Full Team", "hobbies", "large", 120, 16.0, "football,kit",
     "Fourteen shirts, bibs, cones and two match balls. Washed and folded."),

    # ---- Books -----------------------------------------------------------
    ("IELTS Preparation Set", "books", "medium", 40, 5.0, "textbook,study",
     "Cambridge 15 to 18 with the answer keys. Clean, no writing in them."),
    ("Turkmen Poetry Collection", "books", "small", 85, 1.2, "poetry,book",
     "Magtymguly and later poets, hardback. Good condition, no marks."),
    ("Medical Anatomy Atlas", "books", "medium", 25, 3.0, "anatomy,book",
     "Netter, sixth edition. Heavy, so the delivery costs a little more."),
    ("Programming Bookshelf", "books", "large", 60, 14.0, "programming,books",
     "Nine books on Python, Go and system design. Sold as one box."),
    ("Children's Library, 30 Books", "books", "large", 45, 12.0, "children,books",
     "Picture books and early readers, Russian and Turkmen. Rotate monthly."),

    # ---- Houses ----------------------------------------------------------
    ("One-Room Flat Contents", "houses", "large", 190, None, "apartment,interior",
     "The whole contents of a one-room flat: bed, table, two chairs and a small fridge."),
    ("Workbench and Tool Chests", "houses", "large", 80, None, "garage",
     "A full workbench with a vice, a shelf unit and two tool chests. Two people to lift."),
    ("Eighty Chairs and Ten Tables", "houses", "large", 900, None, "event,hall",
     "Eighty stacking chairs and ten folding tables. Sold together, needs a van."),
    ("Garden Set and Tandyr", "houses", "large", 450, None, "country,house",
     "Garden furniture set and a cast-iron tandyr. Heavy, collection from Gokdepe."),
    ("Studio Backdrops and Lights", "houses", "large", 60, None, "photo,studio",
     "Two paper backdrops, a stand and three studio lights. Long, awkward to carry."),
    # ---- Phones ----------------------------------------------------------
    ("iPhone 13, 128GB", "phones", "small", 190, 0.25, "iphone",
     "Battery health 89%. Unlocked, original box, one small mark on the frame."),
    ("Samsung Galaxy A54", "phones", "small", 95, 0.3, "samsung,galaxy,phone",
     "Dual SIM, works on every network here. Case and glass already fitted."),
    ("Xiaomi Redmi Note 12", "phones", "small", 60, 0.3, "xiaomi,smartphone",
     "Bought as a spare and barely used. Charger in the box."),

    # ---- Computers -------------------------------------------------------
    ("Desktop PC, Ryzen 5", "computers", "medium", 210, 9.0, "desktop,computer,tower",
     "16GB, 512GB NVMe, RX 6600. Runs everything at 1080p without complaint."),
    ("Dell 27\" Monitor", "computers", "medium", 85, 5.5, "computer,monitor",
     "1440p IPS, height adjustable stand. No dead pixels."),
    ("Mechanical Keyboard", "computers", "small", 30, 1.0, "mechanical,keyboard",
     "Brown switches, Turkmen and Russian legends, detachable cable."),

    # ---- Appliances ------------------------------------------------------
    ("Bosch Washing Machine", "appliances", "large", 320, 68.0, "washing,machine",
     "7kg, 1200rpm. Working perfectly, moving house and it will not fit."),
    ("Chest Freezer, 200L", "appliances", "large", 240, 45.0, "chest,freezer",
     "Kept in a garage, defrosted and cleaned. Two baskets inside."),
    ("Air Fryer, 5.5L", "appliances", "medium", 55, 5.0, "air,fryer",
     "Used a handful of times. Basket is dishwasher safe."),

    # ---- Furniture -------------------------------------------------------
    ("Oak Dining Table, 6 Seats", "furniture", "large", 280, 40.0, "dining,table,wooden",
     "Solid oak, one owner. Two small dents on the underside, none on top."),
    ("Office Chair, Ergonomic", "furniture", "large", 90, 16.0, "office,chair",
     "Adjustable lumbar and armrests. Gas lift replaced this year."),
    ("Bookshelf, 5 Shelves", "furniture", "large", 70, 25.0, "bookshelf",
     "Flat-packs down for the courier. All fixings in a bag taped inside."),

    # ---- Building materials ----------------------------------------------
    ("Ceramic Floor Tiles, 12m2", "building", "large", 130, 220.0, "ceramic,tiles",
     "60x60 matt grey, four boxes left over from a flat. Same batch."),
    ("Cement, 10 Bags", "building", "large", 95, 250.0, "cement,bags",
     "50kg bags, sealed, stored dry. Collection from Buzmeyin."),
    ("Insulation Rolls, 20m2", "building", "large", 60, 18.0, "insulation,roll",
     "Mineral wool, 100mm. Two rolls, bagged and unopened."),

    # ---- Vehicle parts ---------------------------------------------------
    ("Winter Tyres, Set of 4", "parts", "large", 260, 44.0, "winter,tyre",
     "205/55 R16, two seasons on them, plenty of tread left."),
    ("Roof Box, 420L", "parts", "large", 150, 15.0, "roof,box,car",
     "Locks both sides, keys present. Fits standard bars."),
    ("Car Battery, 60Ah", "parts", "medium", 55, 14.0, "car,battery",
     "Bought last winter, car has since been sold. Holds charge."),

    # ---- Bikes and scooters ----------------------------------------------
    ("Mountain Bike, 27.5\"", "bikes", "large", 175, 14.0, "mountain,bike",
     "Hydraulic discs, recently serviced. Frame size M."),
    ("Electric Scooter, 30km", "bikes", "large", 210, 13.0, "electric,scooter",
     "Folds for the boot. Charger included, battery still strong."),
    ("Child's Bike, 20\"", "bikes", "medium", 45, 9.0, "childrens,bicycle",
     "Outgrown. Stabilisers in the box if you want them."),

    # ---- Clothing --------------------------------------------------------
    ("Winter Parka, Size L", "clothing", "medium", 70, 1.8, "winter,parka,coat",
     "Down filled, hood detaches. Worn two winters, no tears."),
    ("Wedding Suit, Size 50", "clothing", "medium", 110, 2.0, "mens,suit",
     "Worn once. Dry cleaned and still in the garment bag."),
    ("Traditional Keteni Dress", "clothing", "small", 140, 1.2, "embroidered,dress",
     "Hand embroidered, made in Mary. Never altered."),

    # ---- Shoes and bags --------------------------------------------------
    ("Leather Boots, 43", "shoes", "medium", 60, 1.6, "leather,boots",
     "Goodyear welted, resoled once. Plenty of life in them."),
    ("Travel Suitcase, 75L", "shoes", "large", 65, 4.5, "suitcase,luggage",
     "Hard shell, four wheels, TSA lock. One scuff on a corner."),
    ("Running Shoes, 41", "shoes", "small", 35, 0.7, "running,shoes",
     "Bought the wrong size. Tried indoors only."),

    # ---- Kids and baby ---------------------------------------------------
    ("Pushchair with Rain Cover", "kids", "large", 120, 11.0, "pushchair,stroller",
     "Folds one handed. Washed covers, rain cover never used."),
    ("Cot Bed and Mattress", "kids", "large", 95, 22.0, "cot,bed,baby",
     "Converts to a toddler bed. Mattress is new."),
    ("Lego, 4kg Mixed", "kids", "medium", 80, 4.0, "lego,bricks",
     "Sorted, washed and weighed. Several part-built sets in there."),

    # ---- Sport and outdoors ----------------------------------------------
    ("Camping Tent, 4 Person", "sports", "medium", 85, 7.0, "camping,tent",
     "Two bedrooms and a porch. Pitched three times, all pegs present."),
    ("Weight Set, 60kg", "sports", "large", 130, 60.0, "weight,plates,barbell",
     "Barbell, two dumbbells and plates. Courier will want help with this."),
    ("Fishing Rod and Reel", "sports", "medium", 55, 1.5, "fishing,rod",
     "Carbon, 3.6m, with a spare spool and a seat box."),

    # ---- Instruments -----------------------------------------------------
    ("Acoustic Guitar with Case", "music", "large", 120, 3.5, "acoustic,guitar",
     "Solid top, set up last month. Hard case included."),
    ("Digital Piano, 88 Keys", "music", "large", 380, 26.0, "digital,piano,keyboard",
     "Weighted hammer action, stand and pedal. Barely played."),
    ("Dutar, Handmade", "music", "medium", 260, 1.2, "dutar,stringed,instrument",
     "Made in Ashgabat by a known maker. Comes with a soft case."),

    # ---- Garden ----------------------------------------------------------
    ("Lawn Mower, Petrol", "garden", "large", 160, 28.0, "lawn,mower",
     "Self propelled, serviced and blade sharpened. Starts first pull."),
    ("Garden Table and 4 Chairs", "garden", "large", 140, 35.0, "garden,table,chairs",
     "Powder coated steel, cushions included. Kept under cover."),
    ("Greenhouse Frame, 2x3m", "garden", "large", 110, 45.0, "greenhouse",
     "Aluminium frame with polycarbonate panels. Dismantled and bundled."),

    # ---- Pets ------------------------------------------------------------
    ("Dog Crate, Large", "pets", "large", 50, 12.0, "dog,crate",
     "Folds flat. Tray washes out, no rust."),
    ("Aquarium, 120L", "pets", "large", 90, 22.0, "aquarium,fish,tank",
     "With cabinet, filter and heater. Emptied and cleaned."),
    ("Cat Tree, 1.5m", "pets", "large", 45, 9.0, "cat,tree,scratching",
     "Two platforms and a hammock. Rope wrapped and intact."),

    # ---- Health and beauty -----------------------------------------------
    ("Hair Dryer, Professional", "beauty", "small", 65, 0.8, "hair,dryer",
     "Salon model with two nozzles and a diffuser."),
    ("Massage Gun", "beauty", "small", 55, 1.1, "massage,gun",
     "Four heads, carry case, charged and working."),
    ("Electric Shaver", "beauty", "small", 40, 0.4, "electric,shaver",
     "Wet and dry, cleaned, new foil fitted."),

    # ---- Business and trade ----------------------------------------------
    ("Display Fridge, 400L", "business", "large", 620, 85.0, "display,fridge,shop",
     "Glass door, shop-ready and cooling. Coming out of a closed kiosk."),
    ("Shop Shelving, 6 Bays", "business", "large", 280, 120.0, "shop,shelving,rack",
     "Steel, adjustable. Dismantles flat for the van."),
    ("Receipt Printer and Till", "business", "medium", 190, 6.0, "cash,register,receipt",
     "Thermal printer, cash drawer and a roll of paper to start you off."),
]

# Five listings were named after places rather than goods, because the product
# used to rent out space. Any row still carrying the old title is renamed in
# place rather than left behind as a duplicate.
LEGACY_TITLE_RENAMES = {
    "Studio Flat, Berkararlyk": "One-Room Flat Contents",
    "Garage with Inspection Pit": "Workbench and Tool Chests",
    "Event Hall, 80 Seats": "Eighty Chairs and Ten Tables",
    "Summer House, Gokdepe": "Garden Set and Tandyr",
    "Photo Studio, Hourly": "Studio Backdrops and Lights",
}


def rename_legacy_listings(verbose=True):
    renamed = 0
    for old_title, new_title in LEGACY_TITLE_RENAMES.items():
        row = Item.query.filter_by(title=old_title).first()
        if row and not Item.query.filter_by(title=new_title).first():
            row.title = new_title
            renamed += 1
    if renamed:
        db.session.commit()
        if verbose:
            print(f"renamed {renamed} listing(s) left over from the rental product")
    return renamed


def _curl(url, dest=None, timeout=70):
    """One HTTP fetch. curl rather than urllib because the proxy in front of
    this machine mangles chunked reads in Python's http client."""
    cmd = ["curl", "-sSL", "--compressed", "-A", USER_AGENT, "--max-time", str(timeout), url]
    if dest:
        cmd += ["-o", dest]
        return subprocess.run(cmd, capture_output=True).returncode == 0
    return subprocess.run(cmd, capture_output=True).stdout


def commons_search(term, limit=6, width=1200):
    """Ask Commons for photographs of a subject, widest first."""
    query = urllib.parse.urlencode({
        "action": "query", "generator": "search",
        "gsrsearch": f"filetype:bitmap {term}",
        "gsrnamespace": "6", "gsrlimit": str(limit),
        "prop": "imageinfo", "iiprop": "url|size",
        "iiurlwidth": str(width), "format": "json",
    })
    try:
        data = json.loads(_curl(f"{COMMONS_API}?{query}", timeout=45))
    except Exception:
        return []

    hits = []
    for page in ((data.get("query") or {}).get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("thumburl") or info.get("url")
        w, h = info.get("thumbwidth") or 0, info.get("thumbheight") or 0
        # Listing cards are 4:3, so portraits and panoramas are skipped rather
        # than cropped into nonsense.
        if url and w >= 600 and h and 1.1 <= w / h <= 2.1:
            hits.append((page.get("index", 99), url))
    return [url for _, url in sorted(hits)]


def fetch_photo(keyword, category, destination):
    """Put one real photograph on disk for a listing.

    Tries the listing's own subject first and the category's broader term
    second. A listing that ends up with no photograph is reported and skipped
    rather than inserted with a grey box behind it.
    """
    if os.path.exists(destination) and os.path.getsize(destination) > 12000:
        return True

    terms = [keyword.replace(",", " "), CATEGORY_FALLBACK.get(category, category)]
    for term in terms:
        for url in commons_search(term):
            if _curl(url, destination) and os.path.getsize(destination) > 12000:
                with open(destination, "rb") as handle:
                    head = handle.read(4)
                # Anything that is not a real JPEG or PNG is an error page.
                if head[:3] == b"\xff\xd8\xff" or head[:4] == b"\x89PNG":
                    return True
            if os.path.exists(destination):
                os.remove(destination)
    return False


def slugify(title):
    return "".join(c.lower() if c.isalnum() else "_" for c in title).strip("_")


def pick_neighborhoods():
    """Spread listings over real seeded locations rather than one address."""
    rows = (
        Neighborhood.query.join(District).join(Velayat)
        .order_by(Neighborhood.id).all()
    )
    return rows or []


def repair_remote_images(verbose=True):
    """Point any listing still holding a remote image at a local photograph.

    The app was first populated with rows whose image_url pointed at an image
    CDN. Those render as holes anywhere the host is unreachable, so this walks
    them and gives each one a real file on disk, matched on its own title.
    """
    rows = [item for item in Item.query.all()
            if (item.image_url or "").startswith("http")]
    if not rows:
        return 0

    def work(item):
        filename = f"{IMAGE_PREFIX}{slugify(item.title)}.jpg"
        destination = os.path.join(IMAGE_DIR, filename)
        ok = fetch_photo(item.title, item.category, destination)
        return item, filename, ok

    fixed = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for item, filename, ok in pool.map(work, rows):
            if ok:
                item.image_url = f"{WEB_PREFIX}{filename}"
                fixed += 1
            elif verbose:
                print(f"  ! no photograph found for existing listing {item.title!r}")
    db.session.commit()
    if verbose:
        print(f"repaired {fixed} of {len(rows)} listings that pointed at a remote image")
    return fixed


def main():
    reset = "--reset" in sys.argv
    repair_only = "--repair" in sys.argv

    with app.app_context():
        os.makedirs(IMAGE_DIR, exist_ok=True)
        rename_legacy_listings()

        if reset:
            removed = Item.query.filter(Item.image_url.like(f"{WEB_PREFIX}{IMAGE_PREFIX}%")).all()
            for item in removed:
                db.session.delete(item)
            db.session.commit()
            print(f"removed {len(removed)} seeded listings")

        if repair_only:
            repair_remote_images()
            return

        sellers = User.query.filter(User.email.like("%@handshake.com")).order_by(User.id).all()
        if not sellers:
            print("No users found. Start the app once so it seeds its accounts.")
            return

        neighborhoods = pick_neighborhoods()
        if not neighborhoods:
            print("No locations found. Start the app once so it seeds locations.")
            return

        pending = [row for row in LISTINGS if not Item.query.filter_by(title=row[0]).first()]
        skipped = len(LISTINGS) - len(pending)

        # The photographs are the slow part by a wide margin, so they are
        # fetched together before anything touches the database.
        def photo_for(row):
            title, category, _size, _price, _weight, keyword, _description = row
            filename = f"{IMAGE_PREFIX}{slugify(title)}.jpg"
            destination = os.path.join(IMAGE_DIR, filename)
            return row, filename, fetch_photo(keyword, category, destination)

        print(f"fetching photographs for {len(pending)} listings...")
        results = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            for row, filename, ok in pool.map(photo_for, pending):
                results.append((row, filename, ok))
                print(f"  {'ok  ' if ok else 'MISS'}  {row[0]}", flush=True)

        random.seed(20260918)
        inserted = 0
        no_photo = 0

        for index, (row, filename, ok) in enumerate(results):
            title, category, size_class, price, weight_kg, _keyword, description = row
            if not ok:
                # A listing with no photograph is not inserted at all. A grey
                # box in the grid is worse than one fewer listing.
                no_photo += 1
                continue

            seller = sellers[index % len(sellers)]
            neighborhood = neighborhoods[(index * 7) % len(neighborhoods)]

            db.session.add(Item(
                title=title,
                price=price,
                size_class=size_class,
                weight_kg=weight_kg,
                status='listed',
                category=category,
                description=description,
                image_url=f"{WEB_PREFIX}{filename}",
                user_id=seller.id,
                neighborhood_id=neighborhood.id,
                rating=round(random.uniform(4.1, 5.0), 1),
                num_ratings=random.randint(1, 24),
            ))
            inserted += 1

        db.session.commit()

        repair_remote_images()

        total = Item.query.count()
        print(f"inserted {inserted}, already present {skipped}, skipped for want of a photo {no_photo}")
        print(f"catalogue now holds {total} listings")


if __name__ == "__main__":
    main()
