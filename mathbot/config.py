import os

# Bot tokenini @BotFather dan oling.
# Terminalga: export BOT_TOKEN="YOUR_TOKEN_HERE"
BOT_TOKEN = os.getenv("BOT_TOKEN", "7702163893:AAHsFojA3DzEwZTCh-vWaq_1_s0REhkjNvU")
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


DB_PATH = "mathbot.db"

# Kurslar: har biri o'z guruh havolasiga ega
# group_link o'rniga o'zingizning guruh/kanal invite havolangizni qo'ying
COURSES = {
    "turbo_4_0": {
        "name": "Turbo 4.0 MS",
        "group_link": "https://t.me/turbomathka",
    },
}

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
