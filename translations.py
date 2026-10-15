"""English, Russian and Turkmen, as plain dictionaries.

No Flask-Babel and no gettext. Babel wants .po files compiled to .mo, which is
a build step, and this project does not have one — CLAUDE.md is explicit that
a problem solvable with plain Python should not acquire a toolchain. A dict
lookup with an English fallback does the same job here and can be read and
edited by anyone without extracting a catalogue first.

Keys are short dotted paths grouped by where they appear. A key with no entry
for the active language falls back to English rather than rendering blank, so
a half-finished translation degrades into a mixed-language page instead of an
empty one.

Turkmen is the Latin alphabet in official use since 1993, with the letters
ä ç ž ň ö ş ü ý that Turkmen needs and Turkish does not.
"""

LANGUAGES = {
    "en": "English",
    "ru": "Русский",
    "tk": "Türkmençe",
}

DEFAULT_LANGUAGE = "en"

TRANSLATIONS = {
    # ---------------------------------------------------------------- nav --
    "nav.marketplace":     {"en": 'Marketplace', "ru": "Торговая площадка", "tk": "Bazar"},
    "nav.post":            {"en": 'Post an item', "ru": "Разместить товар", "tk": "Haryt goý"},
    "nav.messages":        {"en": 'Messages', "ru": "Сообщения", "tk": "Habarlar"},
    "nav.search":          {"en": 'Search listings, tools, cameras, cars…', "ru": "Поиск товаров, инструментов, камер…",
                            "tk": "Harytlary, gurallary, kameralary gözle…"},
    "nav.account":         {"en": 'Account', "ru": "Аккаунт", "tk": "Hasap"},
    "nav.theme":           {"en": 'Switch theme', "ru": "Сменить тему", "tk": "Temany çalyş"},
    "nav.language":        {"en": 'Language', "ru": "Язык", "tk": "Dil"},
    "nav.menu":            {"en": 'Menu', "ru": "Меню", "tk": "Menýu"},

    # ----------------------------------------------------------- tab bar --
    "tab.home":            {"en": 'Home', "ru": "Главная", "tk": "Baş sahypa"},
    "tab.browse":          {"en": 'Browse', "ru": "Каталог", "tk": "Gözle"},
    "tab.post":            {"en": 'Post', "ru": "Разместить", "tk": "Goý"},
    "tab.messages":        {"en": 'Messages', "ru": "Сообщения", "tk": "Habarlar"},
    "tab.account":         {"en": 'Account', "ru": "Аккаунт", "tk": "Hasap"},
    "tab.profile":         {"en": 'Profile', "ru": "Профиль", "tk": "Profil"},

    # -------------------------------------------------------------- home --
    "home.headline":       {"en": 'We move it. You both stay put.', "ru": "Мы везём. Вы остаётесь на месте.",
                            "tk": "Biz daşaýarys. Siz ýeriňizde galýarsyňyz."},
    "home.lede":           {"en": 'Ordinary things, posted by ordinary people and carried across the country by our couriers. Order it, we collect it, and the seller is paid only once it is in your hands.', "ru": "Обычные вещи, которые размещают обычные люди, "
                                  "а наши курьеры везут их по всей стране. Закажите — "
                                  "мы заберём, а продавец получит деньги только после "
                                  "того, как товар окажется у вас.",
                            "tk": "Adaty adamlaryň goýan adaty zatlary, kurýerlerimiz "
                                  "bolsa olary ýurduň içinde daşaýar. Sargyt ediň — biz "
                                  "alyp gaýdarys, satyjy bolsa diňe haryt eliňize "
                                  "gowşanda pul alar."},
    "home.browse":         {"en": 'Browse listings', "ru": "Смотреть объявления", "tk": "Bildirişlere seret"},
    "home.post":           {"en": 'Post an item', "ru": "Разместить товар", "tk": "Haryt goý"},
    "home.collected":      {"en": 'Collected', "ru": "Забрали", "tk": "Alyndy"},
    "home.in_transit":     {"en": 'In transit', "ru": "В пути", "tk": "Ýolda"},
    "home.handed_over":    {"en": 'Handed over', "ru": "Вручено", "tk": "Gowşuryldy"},
    "home.recent":         {"en": 'Recently listed', "ru": "Недавно размещено", "tk": "Täze goýlanlar"},
    "home.all_listings":   {"en": 'All listings', "ru": "Все объявления", "tk": "Ähli bildirişler"},
    "home.near_you":       {"en": 'Near you', "ru": "Рядом с вами", "tk": "Siziň ýanyňyzda"},

    # ------------------------------------------------------- marketplace --
    "market.title":        {"en": 'Everything on offer near you', "ru": "Всё, что предлагают рядом",
                            "tk": "Ýakynyňyzda hödürlenýän ähli zatlar"},
    "market.categories":   {"en": 'Categories', "ru": "Категории", "tk": "Kategoriýalar"},
    "market.all_items":    {"en": 'All items', "ru": "Все товары", "tk": "Ähli harytlar"},
    "market.all_cats":     {"en": 'All categories', "ru": "Все категории", "tk": "Ähli kategoriýalar"},
    "market.fewer":        {"en": 'Fewer', "ru": "Свернуть", "tk": "Azalt"},
    "market.filter":       {"en": 'Search and filter', "ru": "Поиск и фильтр", "tk": "Gözleg we süzgüç"},
    "market.filter_on":    {"en": 'on', "ru": "вкл", "tk": "açyk"},
    "market.search":       {"en": 'Search', "ru": "Поиск", "tk": "Gözleg"},
    "market.region":       {"en": 'Region', "ru": "Регион", "tk": "Welaýat"},
    "market.district":     {"en": 'District', "ru": "Этрап", "tk": "Etrap"},
    "market.street":       {"en": 'Street or neighbourhood', "ru": "Улица или район", "tk": "Köçe ýa-da etrapça"},
    "market.all_regions":  {"en": 'All regions', "ru": "Все регионы", "tk": "Ähli welaýatlar"},
    "market.all_districts": {"en": 'All districts', "ru": "Все этрапы", "tk": "Ähli etraplar"},
    "market.anywhere":     {"en": 'Anywhere', "ru": "Где угодно", "tk": "Islendik ýerde"},
    "market.apply":        {"en": 'Apply', "ru": "Применить", "tk": "Ulan"},
    "market.clear":        {"en": 'Clear', "ru": "Сбросить", "tk": "Arassala"},
    "market.listings":     {"en": 'listings', "ru": "объявлений", "tk": "bildiriş"},
    "market.paid_on_del":  {"en": 'Paid on delivery, never before.', "ru": "Оплата при доставке, не раньше.",
                            "tk": "Töleg gowşurylanda, ondan öň däl."},
    "market.nothing":      {"en": 'Nothing matches these filters yet', "ru": "Пока ничего не подходит",
                            "tk": "Häzirlikçe hiç zat gabat gelmedi"},

    # -------------------------------------------------------------- item --
    "item.order":          {"en": 'Order it', "ru": "Заказать", "tk": "Sargyt et"},
    "item.order_full":     {"en": 'Order this and have it delivered', "ru": "Заказать с доставкой",
                            "tk": "Sargyt edip, eltip bermegi haýyş et"},
    "item.login_to_order": {"en": 'Log in to order', "ru": "Войдите, чтобы заказать", "tk": "Sargyt üçin giriň"},
    "item.your_listing":   {"en": 'Your listing', "ru": "Ваше объявление", "tk": "Siziň bildirişiňiz"},
    "item.plus_delivery":  {"en": '+ delivery', "ru": "+ доставка", "tk": "+ eltip bermek"},
    "item.ask":            {"en": 'Ask about this item', "ru": "Спросить об этом товаре", "tk": "Bu haryt barada sora"},
    "item.about":          {"en": 'About this item', "ru": "Об этом товаре", "tk": "Bu haryt barada"},
    "item.reviews":        {"en": 'Reviews', "ru": "Отзывы", "tk": "Synlar"},
    "item.no_reviews":     {"en": 'No reviews yet', "ru": "Отзывов пока нет", "tk": "Heniz syn ýok"},
    "item.who":            {"en": 'Who you are dealing with', "ru": "С кем вы имеете дело", "tk": "Kim bilen iş salyşýarsyňyz"},
    "item.approved":       {"en": 'Approved member', "ru": "Проверенный участник", "tk": "Tassyklanan agza"},
    "item.ready":          {"en": 'Ready to send', "ru": "Готово к отправке", "tk": "Ugratmaga taýýar"},

    # ------------------------------------------------------- order flow --
    "flow.where":          {"en": 'Where to', "ru": "Куда", "tk": "Nirä"},
    "flow.pay":            {"en": 'Pay', "ru": "Оплата", "tk": "Töleg"},
    "flow.track":          {"en": 'Track', "ru": "Отслеживание", "tk": "Yzarla"},
    "order.place":         {"en": 'Place the order', "ru": "Оформить заказ", "tk": "Sargydy tassykla"},
    "order.pay":           {"en": 'Pay', "ru": "Оплатить", "tk": "Töle"},
    "orders.title":        {"en": 'Orders', "ru": "Заказы", "tk": "Sargytlar"},
    "orders.buying":       {"en": 'Buying', "ru": "Покупки", "tk": "Satyn alýanlarym"},
    "orders.selling":      {"en": 'Selling', "ru": "Продажи", "tk": "Satýanlarym"},
    "orders.none_bought":  {"en": 'Nothing ordered yet', "ru": "Вы пока ничего не заказывали",
                            "tk": "Heniz hiç zat sargyt etmediňiz"},
    "orders.none_sold":    {"en": 'No orders yet', "ru": "У вас пока никто ничего не заказывал",
                            "tk": "Heniz sizden hiç kim sargyt etmedi"},

    # -------------------------------------------------------------- auth --
    "auth.login":          {"en": 'Log in', "ru": "Войти", "tk": "Gir"},
    "auth.logout":         {"en": 'Log out', "ru": "Выйти", "tk": "Çyk"},
    "auth.email":          {"en": 'Email', "ru": "Эл. почта", "tk": "E-poçta"},
    "auth.password":       {"en": 'Password', "ru": "Пароль", "tk": "Parol"},
    "auth.welcome":        {"en": 'Welcome back.', "ru": "С возвращением.", "tk": "Hoş geldiňiz."},
    "auth.forgot":         {"en": 'Forgot your password?', "ru": "Забыли пароль?", "tk": "Parolyňyzy unutdyňyzmy?"},
    "auth.request_access": {"en": 'Request access', "ru": "Запросить доступ", "tk": "Rugsat sora"},
    "auth.no_account":     {"en": 'No account?', "ru": "Нет аккаунта?", "tk": "Hasabyňyz ýokmy?"},

    # ------------------------------------------------------------ common --
    "common.cancel":       {"en": 'Cancel', "ru": "Отмена", "tk": "Ýatyr"},
    "common.save":         {"en": 'Save', "ru": "Сохранить", "tk": "Ýatda sakla"},
    "common.back":         {"en": 'Back', "ru": "Назад", "tk": "Yza"},
    "common.open":         {"en": 'Open', "ru": "Открыть", "tk": "Aç"},
    "common.tmt":          {"en": 'TMT', "ru": "ТМТ", "tk": "TMT"},
}


def translate(key, language):
    """The string for a key, falling back to English, then to the key itself.

    Returning the key rather than an empty string when nothing matches makes a
    missing translation obvious on the page instead of silently blank.
    """
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return key
    return entry.get(language) or entry.get(DEFAULT_LANGUAGE) or key
