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
    "home.hop":            {"en": 'Shortest hop, smallest delivery fee.', "ru": "Ближе путь — меньше плата за доставку.", "tk": "Ýol näçe gysga bolsa, eltip bermek şonça arzan."},
    "home.collected_d":    {"en": 'A courier picks the item up from the seller and reads back the pickup code.',
                            "ru": "Курьер забирает товар у продавца и называет код получения.",
                            "tk": "Kurýer haryt satyjydan alýar we almak kodyny okaýar."},
    "home.in_transit_d":   {"en": "The item is in someone's care, and every leg of the trip is written down.",
                            "ru": "Товар под присмотром, и каждый этап пути фиксируется.",
                            "tk": "Haryt birine ynanylýar we ýoluň her bölegi ýazga alynýar."},
    "home.handed_over_d":  {"en": 'You give the drop-off code at the door. Only then does the seller get paid.',
                            "ru": "Вы называете код у двери. Только тогда продавец получает деньги.",
                            "tk": "Gapyda gowşuryş kodyny aýdýarsyňyz. Diňe şonda satyjy pul alýar."},
    "home.fact_listings":  {"en": 'listings on the board', "ru": "товаров на витрине", "tk": "haryt tagtada"},
    "home.fact_region":    {"en": 'and Ahal', "ru": "и Ахал", "tk": "we Ahal"},
    "home.fact_paid_b":    {"en": 'Paid', "ru": "Оплата", "tk": "Töleg"},
    "home.fact_paid":      {"en": 'on delivery, not before', "ru": "при доставке, не раньше", "tk": "gowşurylanda, ondan öň däl"},
    "home.empty_h":        {"en": 'The board is empty', "ru": "Витрина пуста", "tk": "Tagta boş"},
    "home.empty_p":        {"en": 'Nothing has been listed yet. Post the first item and it will appear here straight away, in front of everyone looking to buy.',
                            "ru": "Пока ничего не размещено. Разместите первый товар — он сразу появится здесь, перед всеми покупателями.",
                            "tk": "Heniz hiç zat goýulmady. Ilkinji haryty goýuň — ol şobada bu ýerde, ähli alyjylaryň öňünde peýda bolar."},
    "home.step_one":       {"en": 'Step one', "ru": "Шаг первый", "tk": "Birinji ädim"},
    "home.step_two":       {"en": 'Step two', "ru": "Шаг второй", "tk": "Ikinji ädim"},
    "home.step_three":     {"en": 'Step three', "ru": "Шаг третий", "tk": "Üçünji ädim"},
    "home.p1_h":           {"en": 'Ask before you commit', "ru": "Сначала спросите", "tk": "Ilki soraň"},
    "home.p1_p":           {"en": 'Chat opens only when both sides agree to it, so your inbox stays yours. Settle the price and where it has to reach in writing.',
                            "ru": "Чат открывается только при согласии обеих сторон — ваши сообщения остаются вашими. Договоритесь о цене и адресе письменно.",
                            "tk": "Söhbet diňe iki tarap razy bolanda açylýar, şonuň üçin habarlaryňyz özüňizde galýar. Bahany we salgyny ýazmaça ylalaşyň."},
    "home.p2_h":           {"en": 'Pay into escrow', "ru": "Оплата в эскроу", "tk": "Pul escrow-a geçýär"},
    "home.p2_p":           {"en": "The money leaves your wallet but not the seller's way. Global Trade holds it for the whole time the item is travelling.",
                            "ru": "Деньги списываются с вашего кошелька, но продавцу ещё не уходят. Global Trade держит их всё время, пока товар в пути.",
                            "tk": "Pul gapjygyňyzdan çykýar, ýöne satyja geçmeýär. Haryt ýoldaka Global Trade ony saklaýar."},
    "home.p3_h":           {"en": 'Codes at both doors', "ru": "Коды у обеих дверей", "tk": "Iki gapyda-da kod"},
    "home.p3_p":           {"en": "The courier collects against the seller's code and hands over against yours. Reading your code back is what releases the money.",
                            "ru": "Курьер забирает по коду продавца и вручает по вашему. Названный вами код и освобождает деньги.",
                            "tk": "Kurýer satyjynyň kody bilen alýar, siziňki bilen gowşurýar. Siziň kodyňyzyň okalmagy puly boşadýar."},
    "home.tools_h":        {"en": 'Tools and equipment', "ru": "Инструменты и техника", "tk": "Gurallar we enjamlar"},
    "home.tools_note":     {"en": 'Borrow the thing, not the whole shed.', "ru": "Возьмите нужное, а не весь сарай.", "tk": "Gerek zady al, bütin ammary däl."},
    "home.cta_h":          {"en": 'Got something that needs to reach another city?', "ru": "Нужно доставить что-то в другой город?", "tk": "Başga şähere ýetirmeli bir zadyňyz barmy?"},
    "home.howto":          {"en": 'How a hand-off works', "ru": "Как проходит передача", "tk": "Gowşuryş nähili işleýär"},
    "home.cta_p":          {"en": 'List it and anyone in the country can order it. Our courier collects from your door, and nobody gets your number until you say so.',
                            "ru": "Разместите — и заказать сможет любой в стране. Курьер заберёт у двери, а ваш номер никто не узнает без вашего согласия.",
                            "tk": "Goýuň — ýurduň islendik ýerinden sargyt edip bilerler. Kurýer gapyňyzdan alýar, belgiňizi bolsa siz aýtmasaňyz hiç kim bilmeýär."},
    "home.cta_h2":         {"en": "Getting in takes an email and an administrator's nod.", "ru": "Чтобы войти, нужны адрес почты и одобрение администратора.", "tk": "Girmek üçin e-poçta we administratoryň ygtyýary gerek."},
    "home.cta_p2":         {"en": 'Every member confirmed their address and was let in by a person. That is what makes handing a stranger your camera a reasonable thing to do.',
                            "ru": "Каждый участник подтвердил адрес, и его впустил человек. Именно поэтому доверить незнакомцу свою камеру — разумно.",
                            "tk": "Her agza salgysyny tassyklady we ony adam içeri goýberdi. Ine şonuň üçin kesekä kameraňy ynanmak makul bolýar."},

    # ------------------------------------------------------- marketplace --
    "market.title":        {"en": 'Everything on offer near you', "ru": "Всё, что предлагают рядом",
                            "tk": "Ýakynyňyzda hödürlenýän ähli zatlar"},
    "market.categories":   {"en": 'Categories', "ru": "Категории", "tk": "Kategoriýalar"},
    "market.all_items":    {"en": 'All items', "ru": "Все товары", "tk": "Ähli harytlar"},
    "market.all_cats":     {"en": 'All categories', "ru": "Все категории", "tk": "Ähli kategoriýalar"},
    "market.fewer":        {"en": 'Fewer', "ru": "Свернуть", "tk": "Azalt"},
    "market.filter":       {"en": 'Search and filter', "ru": "Поиск и фильтр", "tk": "Gözleg we süzgüç"},
    "market.filters":      {"en": 'Filters', "ru": "Фильтры", "tk": "Süzgüçler"},
    "market.filter_on":    {"en": 'on', "ru": "вкл", "tk": "açyk"},
    "market.search":       {"en": 'Search', "ru": "Поиск", "tk": "Gözleg"},
    "market.search_ph":    {"en": 'Search listings…', "ru": "Поиск товаров…", "tk": "Harytlary gözle…"},
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

    # ------------------------------------------------- parcel size & status --
    "size.small":          {"en": 'Small', "ru": "Маленькая", "tk": "Kiçi"},
    "size.medium":         {"en": 'Medium', "ru": "Средняя", "tk": "Orta"},
    "size.large":          {"en": 'Large', "ru": "Большая", "tk": "Uly"},
    "item.parcel":         {"en": 'parcel', "ru": "посылка", "tk": "paket"},

    "status.listed":       {"en": 'Listed', "ru": "В продаже", "tk": "Satuwda"},
    "status.reserved":     {"en": 'Reserved', "ru": "Забронировано", "tk": "Bronlandy"},
    "status.sold":         {"en": 'Sold', "ru": "Продано", "tk": "Satyldy"},
    "status.withdrawn":    {"en": 'Withdrawn', "ru": "Снято", "tk": "Aýryldy"},

    # ------------------------------------------------------------ categories --
    "cat.tech":            {"en": 'Electronics', "ru": "Электроника", "tk": "Elektronika"},
    "cat.phones":          {"en": 'Phones', "ru": "Телефоны", "tk": "Telefonlar"},
    "cat.computers":       {"en": 'Computers', "ru": "Компьютеры", "tk": "Kompýuterler"},
    "cat.appliances":      {"en": 'Appliances', "ru": "Бытовая техника", "tk": "Durmuş tehnikasy"},
    "cat.furniture":       {"en": 'Furniture', "ru": "Мебель", "tk": "Mebel"},
    "cat.houses":          {"en": 'Property', "ru": "Недвижимость", "tk": "Gozgalmaýan emläk"},
    "cat.tools":           {"en": 'Tools', "ru": "Инструменты", "tk": "Gurallar"},
    "cat.building":        {"en": 'Building materials', "ru": "Стройматериалы", "tk": "Gurluşyk serişdeleri"},
    "cat.cars":            {"en": 'Vehicles', "ru": "Транспорт", "tk": "Ulaglar"},
    "cat.parts":           {"en": 'Vehicle parts', "ru": "Автозапчасти", "tk": "Awtoşaýlar"},
    "cat.bikes":           {"en": 'Bikes and scooters', "ru": "Велосипеды и самокаты", "tk": "Welosipedler we samokatlar"},
    "cat.clothing":        {"en": 'Clothing', "ru": "Одежда", "tk": "Egin-eşik"},
    "cat.shoes":           {"en": 'Shoes and bags', "ru": "Обувь и сумки", "tk": "Aýakgap we sumkalar"},
    "cat.kids":            {"en": 'Kids and baby', "ru": "Детское", "tk": "Çaga harytlary"},
    "cat.sports":          {"en": 'Sport and outdoors', "ru": "Спорт и отдых", "tk": "Sport we dynç alyş"},
    "cat.hobbies":         {"en": 'Hobbies', "ru": "Хобби", "tk": "Höwesler"},
    "cat.music":           {"en": 'Instruments', "ru": "Муз. инструменты", "tk": "Saz gurallary"},
    "cat.books":           {"en": 'Books', "ru": "Книги", "tk": "Kitaplar"},
    "cat.garden":          {"en": 'Garden', "ru": "Сад и огород", "tk": "Bag we bakja"},
    "cat.pets":            {"en": 'Pets', "ru": "Питомцы", "tk": "Öý haýwanlary"},
    "cat.beauty":          {"en": 'Health and beauty', "ru": "Красота и здоровье", "tk": "Saglyk we gözellik"},
    "cat.business":        {"en": 'Business and trade', "ru": "Бизнес и торговля", "tk": "Işewürlik we söwda"},

    # ------------------------------------------------------- item detail page --
    "item.weight_kg":      {"en": 'kg', "ru": "кг", "tk": "kg"},
    "item.before_fee":     {"en": 'before delivery and the 5% service fee',
                            "ru": "без доставки и сервисного сбора 5%",
                            "tk": "eltip bermek we 5% hyzmat tölegi aýratyn"},
    "item.rated":          {"en": 'Rated', "ru": "Оценка", "tk": "Baha"},
    "item.review_one":     {"en": 'review', "ru": "отзыв", "tk": "syn"},
    "item.reviews_many":   {"en": 'reviews', "ru": "отзывов", "tk": "syn"},
    "item.on_board":       {"en": 'It is on the board and anyone can order it.',
                            "ru": "Товар на витрине — заказать может любой.",
                            "tk": "Haryt tagtada — islendik adam sargyt edip biler."},
    "item.open_chat":      {"en": 'Open chat', "ru": "Открыть чат", "tk": "Söhbeti aç"},
    "item.chat_pending":   {"en": 'Chat request pending', "ru": "Запрос на чат отправлен", "tk": "Söhbet haýyşy iberildi"},
    "item.listing_is":     {"en": 'This listing is', "ru": "Статус объявления:", "tk": "Bu bildirişiň ýagdaýy:"},
    "item.no_seller_h":    {"en": "This seller's account is gone",
                            "ru": "Аккаунт продавца удалён",
                            "tk": "Satyjynyň hasaby ýok"},
    "item.no_seller_p":    {"en": 'The listing is still on record, but there is no one to contact. Browse similar items instead.',
                            "ru": "Объявление осталось в записях, но связаться не с кем. Посмотрите похожие товары.",
                            "tk": "Bildiriş ýazgyda galýar, ýöne habarlaşara adam ýok. Meňzeş harytlara serediň."},
    "item.see_other":      {"en": 'See other', "ru": "Другие товары", "tk": "Başga harytlar"},
    "item.signin_mark":    {"en": 'Sign in', "ru": "Войдите", "tk": "Giriň"},
    "item.signin_body":    {"en": 'You need an account to order this or message the seller.',
                            "ru": "Чтобы заказать или написать продавцу, нужен аккаунт.",
                            "tk": "Sargyt etmek ýa-da satyjy bilen habarlaşmak üçin hasap gerek."},
    "item.log_in":         {"en": 'Log in', "ru": "Войти", "tk": "Gir"},
    "item.or_request":     {"en": 'or', "ru": "или", "tk": "ýa-da"},
    "item.review_rating":  {"en": 'Your rating', "ru": "Ваша оценка", "tk": "Siziň bahaňyz"},
    "item.review_q":       {"en": 'What should the next buyer know?',
                            "ru": "Что стоит знать следующему покупателю?",
                            "tk": "Indiki alyja näme bilmek peýdaly?"},
    "item.post_review":    {"en": 'Post review', "ru": "Оставить отзыв", "tk": "Syn galdyr"},
    "item.no_reviews_p":   {"en": 'Nobody has ordered this through Global Trade yet. If you do, your review will be the first thing the next person reads.',
                            "ru": "Через Global Trade это ещё никто не заказывал. Закажете — ваш отзыв прочитают первым.",
                            "tk": "Muny Global Trade arkaly heniz hiç kim sargyt etmedi. Sargyt etseňiz, synyňyz ilki okalar."},
    "item.rating_word":    {"en": 'rating', "ru": "рейтинг", "tk": "reýting"},
    "item.listing_one":    {"en": 'listing', "ru": "объявление", "tk": "bildiriş"},
    "item.listing_many":   {"en": 'listings', "ru": "объявлений", "tk": "bildiriş"},
    "item.not_yet":        {"en": 'Not yet', "ru": "Пока нет", "tk": "Heniz ýok"},
    "item.first_buyer":    {"en": 'first buyer sets it', "ru": "первый покупатель задаст", "tk": "ilkinji alyjy kesgitlär"},
    "item.collected_from": {"en": 'Collected from', "ru": "Забрать у", "tk": "Alynýan ýeri"},
    "item.delivery_quoted":   {"en": 'Delivery is quoted', "ru": "Доставка рассчитывается", "tk": "Eltip bermek bahasy"},
    "item.delivery_quoted_b": {"en": 'once you say where it has to reach',
                               "ru": "когда укажете адрес доставки",
                               "tk": "nirä gowşurylmalydygyny aýdanyňyzda hasaplanýar"},
    "item.deal_note":      {"en": 'You can offer a different price on the order form. The seller has to accept before anything leaves your wallet.',
                            "ru": "Вы можете предложить другую цену в форме заказа. Деньги спишутся только после согласия продавца.",
                            "tk": "Sargyt formasynda başga baha teklip edip bilersiňiz. Satyjy razy bolýança gapjygyňyzdan pul çykmaz."},
    "item.yours":          {"en": 'Yours', "ru": "Ваше", "tk": "Siziňki"},
    "item.yours_body":     {"en": 'This is your listing, so you cannot order it.',
                            "ru": "Это ваше объявление, заказать его нельзя.",
                            "tk": "Bu siziň bildirişiňiz, ony sargyt edip bilmersiňiz."},
    "item.currently":      {"en": 'It is currently', "ru": "Сейчас статус:", "tk": "Häzirki ýagdaýy:"},
    "item.no_desc":        {"en": "The seller hasn't written a description. Ask them in chat before you commit.",
                            "ru": "Продавец не добавил описание. Спросите в чате, прежде чем заказывать.",
                            "tk": "Satyjy düşündiriş ýazmandyr. Sargyt etmezden öň söhbetde soraň."},
    "item.listing_no":     {"en": 'Listing', "ru": "Объявление", "tk": "Bildiriş"},
    "item.ai_live":        {"en": 'Live', "ru": "Онлайн", "tk": "Göni"},
    "item.ai_idle":        {"en": 'Nothing runs until you ask.', "ru": "Ничего не запускается, пока вы не спросите.", "tk": "Soramasaňyz hiç zat işlemeýär."},
    "item.ai_basics":      {"en": 'Teach me the basics', "ru": "Объясни основы", "tk": "Esaslaryny öwret"},
    "item.ai_setup":       {"en": 'Set it up safely', "ru": "Как настроить безопасно", "tk": "Howpsuz gurnamak"},
    "item.ai_yourq":       {"en": 'Your question', "ru": "Ваш вопрос", "tk": "Soragyňyz"},
    "item.ai_ph":          {"en": 'Ask about setup, usage, or first steps', "ru": "Спросите о настройке, использовании или первых шагах", "tk": "Gurnama, ulanyş ýa-da ilkinji ädimler barada soraň"},
    "item.ask_btn":        {"en": 'Ask', "ru": "Спросить", "tk": "Sora"},
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
