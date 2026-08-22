import asyncio
import logging
import os
import tempfile
from datetime import datetime

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
    REPORT_INTERVAL_SECONDS,
    WEBAPP_HOST,
    WEBAPP_PORT,
)
import database as db
from database import init_db
from handlers import registration, admin, menu, attendance, tests, aplus, special_task, boss
from pdf_report import generate_weekly_report, generate_test_results_report
from quiz_structure import DEFAULT_TOTAL_QUESTIONS
from webapp.server import create_app

REPORT_PATH = os.path.join(tempfile.gettempdir(), "mathbot_haftalik_hisobot.pdf")
TEST_REPORT_CHECK_INTERVAL = 60
BROADCAST_CHECK_INTERVAL = 30


async def send_weekly_report_loop(bot: Bot):
    """Har REPORT_INTERVAL_SECONDS soniyada haftalik hisobot PDF faylini kanalga yuboradi."""
    while True:
        try:
            generate_weekly_report(REPORT_PATH)
            await bot.send_document(REPORT_CHANNEL, FSInputFile(REPORT_PATH))
        except Exception:
            logging.exception("Haftalik hisobotni kanalga yuborishda xatolik yuz berdi")
        await asyncio.sleep(REPORT_INTERVAL_SECONDS)


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


async def send_broadcast_schedule_loop(bot: Bot):
    """Haftalik rejalashtirilgan xabarni belgilangan kun/vaqtda barcha foydalanuvchilarga yuboradi."""
    while True:
        try:
            schedule = await db.get_broadcast_schedule()
            if schedule and schedule["enabled"]:
                now = datetime.now()
                current_week = now.strftime("%G-W%V")
                if (
                    now.weekday() == schedule["day_of_week"]
                    and now.strftime("%H:%M") == schedule["time_of_day"]
                    and schedule["last_sent_week"] != current_week
                ):
                    users = await db.get_all_users()
                    for u in users:
                        try:
                            await bot.send_message(u["telegram_id"], schedule["message"])
                        except Exception:
                            pass
                        await asyncio.sleep(0.05)
                    await db.mark_broadcast_sent(current_week)
        except Exception:
            logging.exception("Rejalashtirilgan xabarni yuborishda xatolik yuz berdi")
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
    asyncio.create_task(send_weekly_report_loop(bot))
    asyncio.create_task(send_test_results_loop(bot))
    asyncio.create_task(send_aplus_results_loop(bot))
    asyncio.create_task(send_broadcast_schedule_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
