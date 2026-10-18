"""Hazil yuborish jadvali: har hafta chorshanba/shanba (config.JOKE_DAYS) 14:00, shuningdek Boss
belgilagan istisnolar:
  - joke_skip_dates  - shu sanalarda hazil YUBORILMAYDI (navbat joyida turadi, keyingi safar o'sha hazil boradi);
  - joke_extra_dates - qo'shimcha sanalar (odatdagi kun bo'lmasa ham, shu kuni ham yuboriladi).
Sanalar "YYYY-MM-DD" ko'rinishida bot_settings'da JSON ro'yxat bo'lib saqlanadi."""

import json
import re
from datetime import datetime, timedelta

import database as db
from config import JOKE_DAYS, JOKE_TIME, JOKES

SKIP_KEY = "joke_skip_dates"
EXTRA_KEY = "joke_extra_dates"


async def _load(key: str) -> set:
    try:
        return set(json.loads(await db.get_setting(key) or "[]"))
    except ValueError:
        return set()


async def get_overrides():
    """(o'tkazib yuboriladigan sanalar, qo'shimcha sanalar)"""
    return await _load(SKIP_KEY), await _load(EXTRA_KEY)


async def _save(key: str, dates: set, today: str):
    keep = sorted(d for d in dates if d >= today)       # o'tib ketgan sanalarni tozalaymiz
    await db.set_setting(key, json.dumps(keep))


def is_joke_date(day, skip: set, extra: set) -> bool:
    ds = day.strftime("%Y-%m-%d")
    return (day.weekday() in JOKE_DAYS or ds in extra) and ds not in skip


async def next_joke_time(now, sent_today: bool):
    """Navbatdagi hazil yuboriladigan sana-vaqt (istisnolar hisobga olinadi) yoki None."""
    skip, extra = await get_overrides()
    for add_days in range(0, 60):
        day = (now + timedelta(days=add_days)).replace(
            hour=JOKE_TIME[0], minute=JOKE_TIME[1], second=0, microsecond=0
        )
        if not is_joke_date(day, skip, extra):
            continue
        if add_days == 0 and (sent_today or now >= day + timedelta(minutes=10)):
            continue
        return day
    return None


async def skip_date(date_str: str, today: str):
    skip, _extra = await get_overrides()
    skip.add(date_str)
    await _save(SKIP_KEY, skip, today)


async def clear_skips():
    await db.set_setting(SKIP_KEY, "[]")


async def add_extra_date(date_str: str, today: str):
    skip, extra = await get_overrides()
    extra.add(date_str)
    skip.discard(date_str)
    await _save(EXTRA_KEY, extra, today)
    await _save(SKIP_KEY, skip, today)


def parse_date(text: str, now):
    """"21.10", "21.10.2026" yoki "2026-10-21" -> "YYYY-MM-DD" (yoki None)."""
    t = text.strip()
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?", t)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        year = (int(y) + 2000 if y and len(y) == 2 else int(y)) if y else now.year
        try:
            dt = datetime(year, mo, d)
        except ValueError:
            return None
        return dt.strftime("%Y-%m-%d")
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


EXTRA_JOKES_KEY = "extra_jokes"


async def get_all_jokes() -> list:
    """config.JOKES (kodda yozilgan) + Boss /hazil_add bilan qo'shgan hazillar (bazada saqlanadi)."""
    try:
        extra = json.loads(await db.get_setting(EXTRA_JOKES_KEY) or "[]")
    except ValueError:
        extra = []
    return JOKES + extra


async def add_joke(text: str):
    try:
        extra = json.loads(await db.get_setting(EXTRA_JOKES_KEY) or "[]")
    except ValueError:
        extra = []
    extra.append(text)
    await db.set_setting(EXTRA_JOKES_KEY, json.dumps(extra, ensure_ascii=False))
