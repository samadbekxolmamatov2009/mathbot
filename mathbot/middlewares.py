"""Ro'yxatdan o'tgan foydalanuvchilarning kanal obunasini DAVOMIY tekshirish.

Talab: agar admin/boss foydalanuvchini kanaldan (masalan Turbo 4.0) chiqarib
yuborsa, u botdan ham "chiqarilishi" (ro'yxatdan o'tgan holati bekor
qilinishi) va qayta ro'yxatdan o'tishga majbur bo'lishi kerak - va obunasi
yo'qligi sababli o'sha kursni qayta tanlab bo'lmaydi.

Muhim: bu tekshiruv HAR bitta xabar/tugma bosilganda emas, balki
SUBSCRIPTION_RECHECK_INTERVAL_SECONDS oralig'ida bir marta ishlaydi - aks
holda minglab faol foydalanuvchida har xabarga Telegram API'ga so'rov
yuborish bot javobini sekinlashtiradi va Telegram'ning so'rovlar chegarasiga
(rate limit) tez tegib qolishi mumkin. Shunga qaramay, amalda bu "deyarli
darhol" ta'sir qiladi - eng ko'pi bilan bir necha daqiqa kechikish bilan.
"""

import logging

from aiogram import BaseMiddleware

import database as db
from config import ADMIN_IDS, BOSS_IDS, COURSES, DEFAULT_ADMIN_CONTACT_URL, SUBSCRIPTION_RECHECK_INTERVAL_SECONDS
from timezone_utils import now_tashkent, now_tashkent_str


class SubscriptionCheckMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is None or user.id in ADMIN_IDS or user.id in BOSS_IDS:
            return await handler(event, data)

        db_user = await db.get_user(user.id)
        if not db_user or not db_user["is_registered"]:
            return await handler(event, data)

        course_key = db_user["course"]
        channel = COURSES.get(course_key, {}).get("channel") if course_key else None
        if not channel:
            return await handler(event, data)

        checked_at = db_user["subscription_checked_at"]
        if checked_at:
            try:
                from datetime import datetime

                elapsed = (now_tashkent() - datetime.fromisoformat(checked_at)).total_seconds()
                if elapsed < SUBSCRIPTION_RECHECK_INTERVAL_SECONDS:
                    return await handler(event, data)
            except Exception:
                pass

        bot = data.get("bot") or getattr(event, "bot", None)
        try:
            member = await bot.get_chat_member(channel, user.id)
            still_subscribed = member.status not in ("left", "kicked")
        except Exception:
            logging.exception("Obunani qayta tekshirishda xatolik (kanal: %s, user: %s)", channel, user.id)
            # Texnik xato bo'lsa foydalanuvchini bloklamaymiz, lekin
            # keyingi urinishgacha (cooldown) qayta-qayta urinib, Telegram'ni
            # bezovta qilmaslik uchun tekshirilgan vaqtni baribir yangilaymiz.
            await db.update_subscription_check(user.id, now_tashkent_str())
            return await handler(event, data)

        if not still_subscribed:
            await db.reset_user_registration(user.id)
            course_name = COURSES.get(course_key, {}).get("name", "kurs")
            admin_url = await db.get_setting("admin_contact_url", DEFAULT_ADMIN_CONTACT_URL)
            text = (
                f"\u26a0\ufe0f Siz <b>{course_name}</b> kanalidan chiqarib yuborilgansiz "
                "(yoki obunani bekor qilgansiz).\n\n"
                "Botdan foydalanishni davom ettirish uchun administrator bilan bog'laning: "
                f"{admin_url}"
            )
            try:
                if bot:
                    await bot.send_message(user.id, text, parse_mode="HTML")
            except Exception:
                pass
            return  # handler() chaqirilmaydi - joriy xabar/tugma bekor qilinadi

        await db.update_subscription_check(user.id, now_tashkent_str())
        return await handler(event, data)
