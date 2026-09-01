import asyncio
import logging
import os
import tempfile
from datetime import datetime, timedelta

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile
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
from pdf_report import generate_period_report, generate_test_results_report
from quiz_structure import DEFAULT_TOTAL_QUESTIONS
from timezone_utils import now_tashkent
from webapp.server import create_app

REPORT_PATH = os.path.join(tempfile.gettempdir(), "mathbot_haftalik_hisobot.pdf")
TEST_REPORT_CHECK_INTERVAL = 60
REPORT_SCHEDULE_CHECK_INTERVAL = 30
NOTIFY_CHECK_INTERVAL = 20

DIRECTION_LABELS = {
    "oddiy": "📘 Oddiy test",
    "aplus": "🌟 A+ test",
    "maxsus": "📋 Maxsus topshiriq",
}


async def send_report_schedule_loop(bot: Bot):
    """Haftalik hisobot PDF'ini "⚙️ Sozlamalar"da (Boss/admin tomonidan)
    belgilangan kun/vaqt(lar)da, real test natijalari asosida hisoblab,
    kanalga yuboradi. Bir nechta kun/vaqt yozuvi bo'lishi mumkin (masalan bir
    kunda yoki haftada bir necha marta yuborish uchun) - har biri mustaqil
    "signal" sifatida tekshiriladi. Hisobot MAZMUNI ("oxirgi yuborilgandan
    beri" oralig'i) esa yozuvlardan mustaqil, umumiy "last_report_sent_at"
    sozlamasi orqali kuzatiladi - shunda bir kunda ikkita yozuv ketma-ket
    ishga tushsa ham, ikkinchisi faqat BIRINCHISIDAN keyingi yangi
    natijalarni o'z ichiga oladi (takrorlanish bo'lmaydi)."""
    while True:
        try:
            schedules = await db.get_report_schedules()
            now = now_tashkent()
            if schedules:
                logging.info(
                    "Hisobot tekshiruvi: %d ta jadval | hozir kun=%s vaqt=%s",
                    len(schedules),
                    now.weekday(),
                    now.strftime("%H:%M"),
                )
            else:
                logging.info("Hisobot tekshiruvi: schedule=None hozir=%s", now.strftime("%H:%M"))

            for schedule in schedules:
                if not schedule["enabled"]:
                    continue

                last_fired_date = schedule["last_fired_date"]
                # Aniq daqiqa ("==") emas, "vaqt allaqachon yetdi" ("<=")
                # tekshiriladi - aks holda tsikl aynan shu daqiqaga to'g'ri
                # kelmay qolsa (bot qayta ishga tushib qolsa yoki biroz
                # kechiksa), hisobot butun haftaga tushib qolardi. Shu
                # YOZUVNING o'zi bir kunda bir martadan ortiq ishga
                # tushmasligi uchun faqat shu yozuvning last_fired_date'i
                # solishtiriladi - boshqa yozuvlarga ta'sir qilmaydi, ya'ni
                # bir kunga bir nechta yozuv qo'yilsa, har biri o'z vaqtida
                # alohida yuboraveradi.
                if (
                    now.weekday() == schedule["day_of_week"]
                    and now.strftime("%H:%M") >= schedule["time_of_day"]
                    and last_fired_date != now.strftime("%Y-%m-%d")
                ):
                    try:
                        last_sent_at = await db.get_setting("last_report_sent_at")
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
                        sent_at_iso = now.strftime("%Y-%m-%dT%H:%M:%S")
                        await db.set_setting("last_report_sent_at", sent_at_iso)
                        await db.mark_report_schedule_fired(schedule["id"], now.strftime("%Y-%m-%d"))
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
    asyncio.create_task(notify_new_activities_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
