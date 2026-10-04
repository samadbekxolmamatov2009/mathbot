"""Butun loyiha uchun bitta joylashgan vaqt manbai: O'zbekiston (Toshkent, UTC+5).

Muammo: Render serveri qaysi mamlakatda joylashgan bo'lsa, oddiy
`datetime.now()` O'SHA joyning vaqtini qaytaradi (odatda UTC) - bizning
barcha mijozlarimiz O'zbekistonda bo'lgani uchun, test ochilish/yopilish
vaqtlari, rejalashtirilgan xabarlar va hisobotlar noto'g'ri (bir necha soat
siljigan) bo'lib qolardi. Shu modul orqali butun kodda FAQAT
`now_tashkent()` ishlatiladi - server qayerda joylashganidan qat'iy nazar,
har doim O'zbekiston vaqtini qaytaradi.
"""

from datetime import datetime, timedelta, timezone

# O'zbekiston 1992-yildan beri doim UTC+5 (yozgi vaqt yo'q). Shuning uchun
# serverdagi vaqt mintaqasi bazasiga (tzdata) bog'lanmasdan, to'g'ridan-to'g'ri
# UTC + 5 soat hisoblaymiz - server qaysi mamlakatda bo'lmasin, natija bir xil.
TASHKENT_TZ = timezone(timedelta(hours=5), "Asia/Tashkent")


def now_tashkent() -> datetime:
    """O'zbekiston (Toshkent) bo'yicha joriy vaqtni qaytaradi (tz-siz/naive,
    lekin qiymati doim UTC+5 bo'yicha hisoblangan) - bazadagi va boshqa
    joylardagi tz-siz vaqt satrlari bilan to'g'ridan-to'g'ri solishtirish
    uchun qulay."""
    return (datetime.now(timezone.utc) + timedelta(hours=5)).replace(tzinfo=None)


def now_tashkent_str(fmt: str = "%Y-%m-%dT%H:%M") -> str:
    return now_tashkent().strftime(fmt)


def now_tashkent_sql_str() -> str:
    """submitted_at/report_last_sent_at kabi qiymatlar bilan bir xil formatda
    ("T" ajratuvchi bilan) solishtirilishi uchun - O'ZBEKISTON vaqti bo'yicha."""
    return now_tashkent().strftime("%Y-%m-%dT%H:%M:%S")
