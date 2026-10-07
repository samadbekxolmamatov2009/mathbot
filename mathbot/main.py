import asyncio
import base64
import logging
import os
import tempfile
from datetime import datetime, timedelta

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile, FSInputFile
from aiohttp import web

import config
from config import (
    ADMIN_IDS,
    BOSS_IDS,
    BOT_TOKEN,
    REPORT_CHANNEL,
    WEBAPP_HOST,
    WEBAPP_PORT,
    WEBAPP_URL,
)

KEEP_ALIVE_INTERVAL_SECONDS = 600  # 10 daqiqa


async def keep_webapp_alive_loop():
    """mathbot-1 (Render Free Web Service) 15 daqiqa harakatsizlikdan keyin
    "uxlab qolib", keyingi haqiqiy so'rovga sekin/xato javob bermasligi uchun,
    uni shu worker (hech qachon uxlamaydigan Background Worker) ichidan
    muntazam ping qilib turadi."""
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(WEBAPP_URL, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    logging.info(f"Keep-alive ping: {WEBAPP_URL} -> {resp.status}")
            except Exception:
                logging.exception("Keep-alive ping muvaffaqiyatsiz")
            await asyncio.sleep(KEEP_ALIVE_INTERVAL_SECONDS)
import database as db
from database import init_db
from handlers import registration, admin, menu, attendance, tests, aplus, special_task, boss
from middlewares import SubscriptionCheckMiddleware
from pdf_report import generate_period_report, generate_test_results_report
from quiz_structure import DEFAULT_TOTAL_QUESTIONS
from timezone_utils import now_tashkent
from webapp.server import create_app

REPORT_PATH = os.path.join(tempfile.gettempdir(), "nazoratchi_haftalik_hisobot.pdf")
TEST_REPORT_CHECK_INTERVAL = 60
BROADCAST_CHECK_INTERVAL = 30
REPORT_SCHEDULE_CHECK_INTERVAL = 30
NOTIFY_CHECK_INTERVAL = 20

DIRECTION_LABELS = {
    "oddiy": "📘 Oddiy test",
    "aplus": "🌟 A+ test",
    "maxsus": "📋 Maxsus topshiriq",
}


async def send_report_schedule_loop(bot: Bot):
    """Haftalik hisobot PDF'ini "⚙️ Sozlamalar"da (Boss/admin tomonidan)
    qo'shilgan HAR BIR kun/vaqtda, real test natijalari asosida hisoblab,
    kanalga yuboradi. Bir nechta kun/vaqt qo'shilgan bo'lishi mumkin
    (masalan har Dushanba VA har Juma) - shu vaqtlardan BIRI kelganda,
    oldingi (istalgan vaqtdagi) hisobotdan keyin topshirilgan natijalar
    hisobga olinadi."""
    while True:
        try:
            now = now_tashkent()
            current_minute = now.strftime("%Y-%m-%dT%H:%M")
            last_fired_at = await db.get_setting("report_last_fired_at")

            if last_fired_at != current_minute:
                schedules = await db.get_report_schedules()
                # Aniq bir daqiqani kutish o'rniga 10 daqiqalik oyna: bot shu
                # daqiqada qayta ishga tushayotgan (deploy) bo'lsa ham hisobot
                # o'tkazib yuborilmaydi. Har bir jadval kuniga bir marta ishlaydi.
                today = now.strftime("%Y-%m-%d")
                matching = []
                for s in schedules:
                    if not s["enabled"] or s["day_of_week"] != now.weekday():
                        continue
                    try:
                        hh, mm = map(int, str(s["time_of_day"]).split(":"))
                    except ValueError:
                        continue
                    start = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
                    if not (start <= now < start + timedelta(minutes=10)):
                        continue
                    key = f"report_fired_{s['id']}"
                    if await db.get_setting(key) == today:
                        continue
                    await db.set_setting(key, today)
                    matching.append(s)
                if matching:
                    await db.set_setting("report_last_fired_at", current_minute)
                    try:
                        last_sent_at = await db.get_report_last_sent_at()
                        since_iso = last_sent_at or ""
                        since_dt = (
                            datetime.fromisoformat(last_sent_at)
                            if last_sent_at
                            else now - timedelta(days=7)
                        )
                        rows = await db.get_submissions_since(since_iso)
                        generate_period_report(REPORT_PATH, rows, since_dt, now)
                        channel = await db.get_setting("report_channel_id", REPORT_CHANNEL)
                        await bot.send_document(channel, FSInputFile(REPORT_PATH))
                        await db.mark_report_sent(now.strftime("%Y-%m-%dT%H:%M:%S"))
                    except Exception:
                        logging.exception("Haftalik hisobotni kanalga yuborishda xatolik yuz berdi")
        except Exception:
            logging.exception("Haftalik hisobot rejasini tekshirishda xatolik")
        await asyncio.sleep(REPORT_SCHEDULE_CHECK_INTERVAL)


async def send_test_results_loop(bot: Bot):
    """Vaqti tugagan testlar uchun natijalar PDF'ini adminlarga yuboradi."""
    while True:
        try:
            pending = await db.get_tests_pending_report()
            for test in pending:
                submissions = await db.get_test_submissions_with_names(test["id"])
                rows = [(s["full_name"], s["score"]) for s in submissions]
                path = os.path.join(tempfile.gettempdir(), f"test_natija_{test['id']}.pdf")
                generate_test_results_report(
                    path,
                    test["code"],
                    test["name"],
                    test["total_questions"] or DEFAULT_TOTAL_QUESTIONS,
                    rows,
                )
                for admin_id in ADMIN_IDS + BOSS_IDS:
                    try:
                        await bot.send_document(admin_id, FSInputFile(path))
                    except Exception:
                        pass
                await db.mark_test_reported(test["id"])
        except Exception:
            logging.exception("Test natijalarini yuborishda xatolik yuz berdi")
        await asyncio.sleep(TEST_REPORT_CHECK_INTERVAL)


async def send_aplus_results_loop(bot: Bot):
    """Vaqti tugagan A+ testlar uchun natijalar PDF'ini adminlarga yuboradi."""
    while True:
        try:
            pending = await db.get_aplus_tests_pending_report()
            for test in pending:
                submissions = await db.get_aplus_test_submissions_with_names(test["id"])
                rows = [(s["full_name"], s["score"]) for s in submissions]
                path = os.path.join(tempfile.gettempdir(), f"aplus_natija_{test['id']}.pdf")
                generate_test_results_report(
                    path, test["code"], test["name"], test["question_count"] * 2, rows
                )
                for admin_id in ADMIN_IDS + BOSS_IDS:
                    try:
                        await bot.send_document(admin_id, FSInputFile(path))
                    except Exception:
                        pass
                await db.mark_aplus_test_reported(test["id"])
        except Exception:
            logging.exception("A+ natijalarini yuborishda xatolik yuz berdi")
        await asyncio.sleep(TEST_REPORT_CHECK_INTERVAL)


async def notify_new_activities_loop(bot: Bot):
    """Admin/Boss yangi A+ test, oddiy test yoki maxsus topshiriq
    faollashtirsa - barcha ro'yxatdan o'tgan o'quvchilarga avtomatik xabar
    yuboradi ("yana bir mavzu faollashtirildi" + yo'nalishi + eslatma)."""
    while True:
        try:
            users = None  # faqat kerak bo'lganda (kamida bitta yangi mavzu bo'lsa) yuklanadi

            async def _broadcast(text: str):
                nonlocal users
                if users is None:
                    users = await db.get_all_users()
                for u in users:
                    try:
                        await bot.send_message(u["telegram_id"], text, parse_mode="HTML")
                    except Exception:
                        pass
                    await asyncio.sleep(0.05)

            for test in await db.get_unnotified_tests():
                name = test["name"] or test["code"]
                await _broadcast(
                    f"🆕 Yana bir mavzu faollashtirildi!\n"
                    f"{DIRECTION_LABELS['oddiy']}: <b>{name}</b>\n\n"
                    f"✍️ Vazifangizni yuboring!"
                )
                await db.mark_test_notified(test["id"])

            for test in await db.get_unnotified_aplus_tests():
                name = test["name"] or test["code"]
                await _broadcast(
                    f"🆕 Yana bir mavzu faollashtirildi!\n"
                    f"{DIRECTION_LABELS['aplus']}: <b>{name}</b>\n\n"
                    f"✍️ Vazifangizni yuboring!"
                )
                await db.mark_aplus_test_notified(test["id"])

            for task in await db.get_unnotified_special_tasks():
                await _broadcast(
                    f"🆕 Yana bir mavzu faollashtirildi!\n"
                    f"{DIRECTION_LABELS['maxsus']}: <b>{task['name']}</b>\n\n"
                    f"✍️ Vazifangizni yuboring!"
                )
                await db.mark_special_task_notified(task["id"])
        except Exception:
            logging.exception("Yangi mavzu haqida xabar berishda xatolik")
        await asyncio.sleep(NOTIFY_CHECK_INTERVAL)


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


async def send_broadcast_schedule_loop(bot: Bot):
    """Chorshanba va shanba 14:00 da guruhga navbatdagi hazilni (va Boss tanlagan
    stikerni) yuboradi. Belgilangan vaqtdan keyingi 10 daqiqa ichida yuboriladi -
    shu payt bot qayta ishga tushayotgan bo'lsa ham o'tkazib yuborilmaydi."""
    while True:
        try:
            now = now_tashkent()
            start = now.replace(hour=JOKE_TIME[0], minute=JOKE_TIME[1], second=0, microsecond=0)
            today = now.strftime("%Y-%m-%d")
            if (
                now.weekday() in JOKE_DAYS
                and start <= now < start + timedelta(minutes=10)
                and await db.get_setting("joke_last_sent_date") != today
            ):
                await db.set_setting("joke_last_sent_date", today)
                index = int(await db.get_setting("joke_index", "0") or 0)
                channel = await db.get_setting("report_channel_id", REPORT_CHANNEL)
                try:
                    await bot.send_message(channel, JOKES[index % len(JOKES)])
                    sticker = await db.get_setting("joke_sticker_id")
                    if sticker:
                        await bot.send_sticker(channel, sticker)
                except Exception:
                    logging.exception("Hazilni guruhga yuborishda xatolik")
                await db.set_setting("joke_index", str((index + 1) % len(JOKES)))
        except Exception:
            logging.exception("Hazil yuborish jarayonida xatolik yuz berdi")
        await asyncio.sleep(BROADCAST_CHECK_INTERVAL)


async def start_webapp_server():
    """Test Mini App uchun aiohttp serverni fon rejimida ishga tushiradi."""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT)
    await site.start()
    logging.info(f"Mini App server ishga tushdi: http://{WEBAPP_HOST}:{WEBAPP_PORT}")


async def main():
    logging.basicConfig(level=logging.INFO)

    await init_db()

    # "admins" jadvali - ADMIN_IDS ro'yxatining o'zagida, shuning uchun
    # boshqa modullardagi "from config import ADMIN_IDS" ham darhol yangi
    # holatni ko'rishi uchun ro'yxat joyida (in-place) yangilanadi.
    config.ADMIN_IDS[:] = await db.get_admin_ids()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # ---------- DIAGNOSTIKA (botning ishini O'ZGARTIRMAYDI, faqat logga yozadi) ----------
    # 1) Har bir kelgan xabar: kimdan (user id) va nima yozildi.
    @dp.update.outer_middleware()
    async def _log_incoming(handler, event, data):
        u = None
        text = None
        if event.message:
            u = event.message.from_user
            text = event.message.text or f"<{event.message.content_type}>"
        elif event.callback_query:
            u = event.callback_query.from_user
            text = f"<tugma: {event.callback_query.data}>"
        logging.info("KELDI: user=%s (@%s) -> %r", u.id if u else "?", u.username if u else "?", text)
        return await handler(event, data)

    # 2) Bot Telegram'ga yuborgan har bir so'rov va, eng muhimi, XATOLARI -
    #    kod ichida "except: pass" bilan yashirilgan xatolar ham shu yerda ko'rinadi.
    from aiogram.client.session.middlewares.base import BaseRequestMiddleware

    class _LogOutgoing(BaseRequestMiddleware):
        async def __call__(self, make_request, bot_, method):
            name = type(method).__name__
            if name == "GetUpdates":
                return await make_request(bot_, method)
            chat = getattr(method, "chat_id", None) or getattr(method, "user_id", None)
            try:
                result = await make_request(bot_, method)
                logging.info("YUBORILDI: %s -> %s OK", name, chat)
                return result
            except Exception as e:
                logging.error("YUBORILMADI: %s -> %s | %s: %s", name, chat, type(e).__name__, e)
                raise

    bot.session.middleware(_LogOutgoing())
    # ---------- DIAGNOSTIKA tugadi ----------

    # Ro'yxatdan o'tgan foydalanuvchilarning kanal obunasini davomiy
    # tekshiradi - kanaldan chiqarib yuborilganlarni avtomatik "ro'yxatdan
    # chiqaradi" (qarang: middlewares.py).
    subscription_middleware = SubscriptionCheckMiddleware()
    dp.message.middleware(subscription_middleware)
    dp.callback_query.middleware(subscription_middleware)

    await admin.set_admin_menu(bot)
    await admin.set_boss_menu(bot)

    # special_task hammasidan oldin turishi shart: u SkipHandler orqali
    # to'plangan fayllarni yuborib, xabarni keyingi routerlarga o'tkazib yuboradi.
    dp.include_router(special_task.router)
    dp.include_router(boss.router)
    # Admin handlerlari registration'dan oldin bo'lishi kerak
    # (chunki /start admin uchun boshqacha ishlaydi)
    dp.include_router(admin.router)
    dp.include_router(registration.router)
    dp.include_router(attendance.router)
    dp.include_router(tests.router)
    dp.include_router(aplus.router)
    dp.include_router(menu.router)

    await bot.delete_webhook(drop_pending_updates=True)

    await start_webapp_server()
    asyncio.create_task(keep_webapp_alive_loop())
    asyncio.create_task(send_report_schedule_loop(bot))
    asyncio.create_task(send_test_results_loop(bot))
    asyncio.create_task(send_aplus_results_loop(bot))
    asyncio.create_task(send_broadcast_schedule_loop(bot))
    asyncio.create_task(notify_new_activities_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
