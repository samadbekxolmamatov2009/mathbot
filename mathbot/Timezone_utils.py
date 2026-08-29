"""Butun loyiha uchun bitta joylashgan vaqt manbai: O'zbekiston (Toshkent, UTC+5).

Muammo: Render serveri qaysi mamlakatda joylashgan bo'lsa, oddiy
`datetime.now()` O'SHA joyning vaqtini qaytaradi (odatda UTC) - bizning
barcha mijozlarimiz O'zbekistonda bo'lgani uchun, test ochilish/yopilish
vaqtlari, rejalashtirilgan xabarlar va hisobotlar noto'g'ri (bir necha soat
siljigan) bo'lib qolardi. Shu modul orqali butun kodda FAQAT
`now_tashkent()` ishlatiladi - server qayerda joylashganidan qat'iy nazar,
har doim O'zbekiston vaqtini qaytaradi.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")


def now_tashkent() -> datetime:
    """O'zbekiston (Toshkent) bo'yicha joriy vaqtni qaytaradi (tz-siz/naive,
    lekin qiymati doim UTC+5 bo'yicha hisoblangan) - bazadagi va boshqa
    joylardagi tz-siz vaqt satrlari bilan to'g'ridan-to'g'ri solishtirish
    uchun qulay."""
    return datetime.now(TASHKENT_TZ).replace(tzinfo=None)


def now_tashkent_str(fmt: str = "%Y-%m-%dT%H:%M") -> str:
    return now_tashkent().strftime(fmt)
