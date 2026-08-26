import asyncio
import base64
import logging
import os
import tempfile
from datetime import datetime

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
    REPORT_INTERVAL_SECONDS,
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
from pdf_report import generate_weekly_report, generate_test_results_report
from quiz_structure import DEFAULT_TOTAL_QUESTIONS
from webapp.server import create_app

REPORT_PATH = os.path.join(tempfile.gettempdir(), "mathbot_haftalik_hisobot.pdf")
TEST_REPORT_CHECK_INTERVAL = 60
BROADCAST_CHECK_INTERVAL = 30


async def send_weekly_report_loop(bot: Bot):
    """Har REPORT_INTERVAL_SECONDS soniyada hisobot PDF faylini yuborishga
    urinadi - lekin FAQAT "⚙️ Sozlamalar" orqali "Avtomatik soatlik hisobot"
    yoqilgan bo'lsa (standart holatda o'chirilgan, chunki bu keraksiz
    ma'lumot bilan kanalni to'ldirib yuborardi)."""
    while True:
        try:
            hourly_enabled = await db.get_setting("hourly_report_enabled", "0")
            if hourly_enabled == "1":
                channel = await db.get_setting("report_channel_id", REPORT_CHANNEL)
                generate_weekly_report(REPORT_PATH)
                await bot.send_document(channel, FSInputFile(REPORT_PATH))
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
    """Rejalashtirilgan xabarni belgilangan kun/vaqtda kanalga yuboradi
    (har bir foydalanuvchiga alohida emas - "⚙️ Sozlamalar" orqali admin
    belgilagan kun/vaqtda, biriktirilgan fayl (masalan PDF) bo'lsa hujjat
    sifatida, bo'lmasa oddiy matn sifatida, sozlamalardagi kanalga)."""
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
                    channel = await db.get_setting("report_channel_id", REPORT_CHANNEL)
                    try:
                        file_data = schedule["file_data"]
                        if file_data:
                            file_bytes = base64.b64decode(file_data)
                            file_name = schedule["file_name"] or "fayl.pdf"
                            document = BufferedInputFile(file_bytes, filename=file_name)
                            await bot.send_document(
                                channel, document, caption=(schedule["message"] or None)
                            )
                        else:
                            await bot.send_message(channel, schedule["message"])
                    except Exception:
                        logging.exception("Rejalashtirilgan xabarni kanalga yuborishda xatolik")
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
    asyncio.create_task(keep_webapp_alive_loop())
    asyncio.create_task(send_weekly_report_loop(bot))
    asyncio.create_task(send_test_results_loop(bot))
    asyncio.create_task(send_aplus_results_loop(bot))
    asyncio.create_task(send_broadcast_schedule_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
