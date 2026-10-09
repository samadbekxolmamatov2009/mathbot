import os

# Bot tokenini @BotFather dan oling.
# Terminalga: export BOT_TOKEN="YOUR_TOKEN_HERE"
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi. Telegram bot tokenini @BotFather dan oling va "
        "BOT_TOKEN degan muhit o'zgaruvchisiga qo'ying."
    )

# Adminlarning Telegram ID raqamlari.
# Bu ro'yxat endi bot ishga tushganda database.py orqali "admins" jadvali
# bilan sinxronlanadi va Boss /boss_add, /boss_remove buyruqlari bilan
# dinamik boshqaradi - shu ro'yxatni qo'lda o'zgartirish shart emas.
ADMIN_IDS = [
    506095476,
]

# Botning ENG yuqori darajasi - oddiy adminlardan yashirin.
# Hech qanday ro'yxatda (/admins, admin panel va h.k.) ko'rinmaydi va
# alohida /boss_* buyruqlari hech qayerda reklama qilinmaydi (Bot Menu
# tugmasiga ham qo'shilmaydi) - faqat shu ID'lar qo'lda buyruq yozsa ishlaydi.
BOSS_IDS = [
    8113300476,
    1586890780,
]


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS or user_id in BOSS_IDS


def is_boss(user_id: int) -> bool:
    return user_id in BOSS_IDS


# "🖥 Admin panel" Mini App'i hozircha FAQAT Boss'larga ko'rinadi va ishlaydi.
# Oddiy adminlarga ochish uchun hosting sozlamalariga PANEL_FOR_ADMINS=1 qo'ying
# (kod o'zgartirish shart emas) va botni qayta ishga tushiring.
PANEL_FOR_ADMINS = os.getenv("PANEL_FOR_ADMINS", "").strip().lower() in ("1", "true", "yes", "on")


def can_use_panel(user_id) -> bool:
    return is_boss(user_id) or (PANEL_FOR_ADMINS and is_admin(user_id))


DB_PATH = "mathbot.db"

# Turso (libSQL) - tarmoq orqali ulaniladigan baza. Render'da botlar
# (Background Worker) va Mini App backend (Web Service) ikkita alohida
# konteynerda ishlaydi va oddiy SQLite fayl bilan bazani bo'lisha olmaydi -
# shu ikkalasi BIR XIL bazani ko'rishi uchun shu ikki o'zgaruvchi ikkala
# service'da ham bir xil qiymat bilan sozlanishi kerak.
# Sozlanmagan bo'lsa (masalan lokal ishlab chiqishda), oddiy mahalliy
# SQLite fayl (yuqoridagi DB_PATH) ishlatiladi - hech narsa talab qilinmaydi.
# .strip() muhim: Render'ga token/URL nusxalab joylashtirilganda oxiriga
# tasodifan bo'sh joy yoki yangi qator belgisi (\n) qo'shilib qolishi mumkin.
# Bunday "ko'rinmas" belgi Turso'ga so'rov yuborilganda "Forbidden control
# character detected in headers" xatosiga va HAR BIR so'rovning
# muvaffaqiyatsiz bo'lishiga olib keladi.
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL", "").strip()
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "").strip()

# Kurslar: har biri o'z guruh havolasiga va OBUNA TEKSHIRILADIGAN kanaliga ega.
# "channel" - bot.get_chat_member() uchun ishlatiladi (bot shu kanalda admin
# bo'lishi shart). Yangi kurs qo'shmoqchi bo'lsangiz, shu ro'yxatga yangi
# kalit qo'shing - ro'yxatdan o'tishda avtomatik variantlardan biri sifatida
# chiqadi va o'sha kursning kanaliga obuna tekshiriladi.
# Diqqat: lug'at kaliti ("turbo_4_0") ataylab o'zgartirilmagan - u bazada har bir
# o'quvchining kursi sifatida saqlangan. Uni o'zgartirsangiz, eski o'quvchilar
# kursini "yo'qotib" qo'yadi. Foydalanuvchiga ko'rinadigan nom - "name".
#
# Obuna tekshiriladigan kanal: yopiq (invite-link'li) guruhni get_chat_member()
# faqat uning raqamli ID'si orqali tekshira oladi (masalan -1001234567890).
# Uni .env / hosting sozlamalariga TURBO_CHANNEL_ID qilib yozing.
COURSES = {
    "turbo_4_0": {
        "name": "Turbo 5.0 MS",
        "group_link": "https://t.me/+U0a_NalUzd8zMzBi",
        "channel": os.getenv("TURBO_CHANNEL_ID", "").strip() or "@turbomathka",
    },
}

# Obunani qayta tekshirish oralig'i (soniyalarda) - foydalanuvchi bot bilan
# HAR safar muloqot qilganda emas, shu vaqt oralig'ida bir marta tekshiriladi
# (Telegram API so'rovlar chegarasidan (rate limit) himoyalanish uchun -
# minglab faol foydalanuvchida har xabarga tekshirish botni sekinlashtirib,
# hatto Telegram tomonidan vaqtincha bloklanishiga olib kelishi mumkin).
SUBSCRIPTION_RECHECK_INTERVAL_SECONDS = 600  # 10 daqiqa

# "Adminga xabar" tugmasidagi standart havola - Boss "🔗 Admin havolasini
# o'zgartirish" tugmasi orqali bazada saqlangan qiymat bilan buni
# almashtirishi mumkin (database.py: get_setting/set_setting). Bu shunchaki
# hech qachon o'zgartirilmagan holatdagi zaxira (fallback) qiymat.
DEFAULT_ADMIN_CONTACT_URL = "https://t.me/xolmamatov09"

# Haftalik hisobot PDF shu kanalga yuboriladi.
# Bot shu kanalda ADMIN bo'lishi va "Xabarlarni yuborish" huquqiga ega bo'lishi kerak.
REPORT_CHANNEL = "@turbomathka"

# Hisobot necha soniyada bir marta yuborilishi (1 soat = 3600 soniya)
REPORT_INTERVAL_SECONDS = 3600

# --- Test Mini App (WebApp) sozlamalari ---
# Ikkita alohida manzil bor:
#
# 1) WEBAPP_URL - backend serveringiz (shu aiohttp ilova) qayerda ishlayotgani.
#    Admin panel (admin.html) va /api/* endpointlar shu manzildan xizmat qiladi.
#    Doim https:// bilan boshlanishi SHART (Telegram shunday talab qiladi).
#    Bu manzil sizning VPS/serveringiz domeni bo'lishi kerak (masalan https://api.mathbot.uz).
#
# 2) TEST_WEBAPP_URL - Netlify'da joylashgan o'quvchilar uchun "Test" mini-app sahifasi
#    (netlify-site/ papkasi). Netlify'ga deploy qilgach shu yerga o'zingizning
#    netlify.app (yoki custom) domeningizni yozing (masalan https://mathbot-test.netlify.app).
#    Netlify faqat statik frontendni beradi - u netlify-site/config.js ichidagi
#    API_BASE orqali WEBAPP_URL'dagi backendga so'rov yuboradi.
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://api.mathbot.uz")
TEST_WEBAPP_URL = os.getenv("TEST_WEBAPP_URL", "https://mathbot-test.netlify.app")
WEBAPP_HOST = "0.0.0.0"
# Render Web Service kabi platformalar tashqi PORT o'zgaruvchisini o'zi beradi -
# ilova aynan shu portda tinglashi shart, aks holda tashqi trafik yetib kelmaydi.
WEBAPP_PORT = int(os.getenv("PORT", 8080))

# Backend API'ga boshqa origin'dan (Netlify) so'rov yuborilishiga ruxsat berish uchun.
ALLOWED_ORIGINS = [TEST_WEBAPP_URL.rstrip("/")]


# Har chorshanba va shanba soat 14:00 da guruhga yuboriladigan hazillar.
# Ketma-ket yuboriladi: 1, 2, 3, 4, 5, 6, keyin yana 1 dan - bitta hazil qolgan
# 5 tasi ishlatilmaguncha takrorlanmaydi. Navbat bazada saqlanadi (deploydan keyin ham davom etadi).
JOKE_DAYS = (2, 5)  # 2 = chorshanba, 5 = shanba
JOKE_TIME = (14, 0)
JOKES = [
    "🤖 Salom, Turbo jamoasi! Men bu yerda bir haftadan beri zerikib o'tiribman... 😴\n"
    "Vazifalarni qiling, shunda men ham ishlab, ball qo'yib zavqlanaman! 📚✍️",

    "😩 Voy-voy-voy... Yana bir kun o'tdi, men hali biror vazifa ko'rmadim!\n"
    "Testlaringizni kutaverib, mening ham simlarim chang bosib ketdi 🕸\n"
    "Qani, kim birinchi bo'lib meni xursand qiladi? 🏆",

    "⏰ Diqqat, diqqat! Bot gapiryapti!\n"
    "Agar vazifalar topshirilmasa, men har kuni \"salom\" deb yozib, sizni charchatib qo'yaman 😈\n"
    "Yaxshisi, vazifalarni qilib qo'ying 😁",

    "🎙 Assalomu alaykum, aziz tomoshabinlar! Soat 14:00...\n"
    "Jamoamiz hali ham \"vazifa\" degan to'pni darvozaga kiritmadi! ⚽️\n"
    "Kim birinchi bo'lib gol uradi? Reytingda joy bo'sh turibdi! 🥇",

    "🥱 Men zerikdim...\n"
    "📚 Siz esa vazifani qilmadingiz...\n"
    "🤝 Keling, ikkalamiz ham bu muammoni hal qilamiz: siz vazifani qiling, men ball qo'yaman!",

    "📐 Bugungi tenglama:\n"
    "Bot + zerikish = 💤\n"
    "Bot + vazifalar = 🔥\n"
    "Xulosa: vazifalarni topshiring, botni uyg'oting! 😄",
]
