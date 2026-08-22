import asyncio
import logging

from aiogram import Router, F
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import database as db
from config import ADMIN_IDS, COURSES
from states import SpecialTaskAdmin
from keyboards import NAV_BUTTON_TEXTS

router = Router()
router.message.filter(F.chat.type == "private")

log = logging.getLogger("special_task")

SUBMISSION_WINDOW_SECONDS = 60


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# telegram_id -> {"task_name": str, "files": list[dict], "timer": asyncio.Task}
_pending_submissions: dict[int, dict] = {}


class IsCollectingSpecialTask(BaseFilter):
    """Foydalanuvchi hozir maxsus topshiriq uchun fayl yuborayotgan-yubormayotganini tekshiradi."""

    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in _pending_submissions


async def _flush_submission(bot, telegram_id: int) -> int:
    """To'plangan fayllarni adminlarga yuboradi va sessiyani tozalaydi. Yuborilgan fayl sonini qaytaradi."""
    session = _pending_submissions.pop(telegram_id, None)
    if not session:
        log.info("FLUSH: %s uchun pending session topilmadi (allaqachon flush bo'lgan yoki mavjud emas)", telegram_id)
        return 0

    timer = session.get("timer")
    if timer and not timer.done():
        timer.cancel()

    files = session["files"]
    log.info("FLUSH: %s uchun %d ta fayl topildi (task=%r)", telegram_id, len(files), session.get("task_name"))
    if not files:
        return 0

    user = await db.get_user(telegram_id)
    name = (user["full_name"] if user else None) or "Noma'lum"
    course = COURSES.get(user["course"], {}).get("name", user["course"]) if user else "Noma'lum"

    caption = (
        f"📋 <b>{session['task_name']}</b>\n"
        f"👤 {name} ({course})\n"
        f"ID: <code>{telegram_id}</code>\n"
        f"📎 {len(files)} ta fayl"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, caption, parse_mode="HTML")
            for f in files:
                if f["type"] == "photo":
                    await bot.send_photo(admin_id, f["file_id"])
                else:
                    await bot.send_document(admin_id, f["file_id"])
            log.info("FLUSH: admin %s ga muvaffaqiyatli yuborildi", admin_id)
        except Exception:
            log.exception("FLUSH: admin %s ga yuborishda xatolik", admin_id)

    return len(files)


async def _auto_flush_after_delay(bot, telegram_id: int):
    try:
        await asyncio.sleep(SUBMISSION_WINDOW_SECONDS)
    except asyncio.CancelledError:
        log.info("TIMER: %s uchun taymer bekor qilindi (muddatidan oldin flush bo'ldi)", telegram_id)
        return

    log.info("TIMER: %s uchun 60 soniya tugadi, flush qilinmoqda", telegram_id)
    sent = await _flush_submission(bot, telegram_id)
    if sent:
        try:
            await bot.send_message(telegram_id, f"✅ {sent} ta fayl ustozga yuborildi.")
        except Exception:
            pass


# ---------- Admin: maxsus topshiriq yaratish ----------

@router.message(F.text == "📋 Maxsus topshiriq yaratish")
async def start_create_special_task(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(SpecialTaskAdmin.waiting_name)
    await message.answer("📋 Yangi maxsus topshiriq nomini kiriting:")


@router.message(SpecialTaskAdmin.waiting_name, F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def save_special_task_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    name = message.text.strip()
    if not name:
        await message.answer("Iltimos, topshiriq nomini kiriting:")
        return

    await db.create_special_task(name, message.from_user.id)
    await state.clear()
    await message.answer(
        f"✅ <b>{name}</b> nomli maxsus topshiriq yaratildi.\n"
        "Endi o'quvchilar \"📋 Maxsus topshiriq yuborish\" tugmasi orqali fayl yuborishlari mumkin.",
        parse_mode="HTML",
    )


# ---------- O'quvchi: maxsus topshiriq bo'yicha fayl yuborish ----------

@router.message(F.text == "📋 Maxsus topshiriq yuborish")
async def start_special_task_submission(message: Message, bot):
    user = await db.get_user(message.from_user.id)
    if not user or not user["is_registered"]:
        await message.answer("Iltimos, avval /start orqali ro'yxatdan o'ting.")
        return

    task = await db.get_active_special_task()
    if not task:
        await message.answer("Hozircha faol maxsus topshiriq yo'q.")
        return

    telegram_id = message.from_user.id
    # avval yig'ilayotgan fayllar bo'lsa, ularni yuborib, yangisini boshlaymiz
    await _flush_submission(bot, telegram_id)

    timer = asyncio.create_task(_auto_flush_after_delay(bot, telegram_id))
    _pending_submissions[telegram_id] = {
        "task_name": task["name"],
        "files": [],
        "timer": timer,
    }
    log.info("START: %s uchun '%s' topshirig'i bo'yicha yig'ish boshlandi", telegram_id, task["name"])

    await message.answer(
        f"📋 <b>{task['name']}</b>\n\n"
        "Ushbu topshiriq bo'yicha rasm yoki PDF fayl yuboring.\n"
        "Bir nechta fayl yuborishingiz mumkin — 1 daqiqadan so'ng ular avtomatik ustozga yuboriladi.\n"
        "(Boshqa tugmani bossangiz, to'plangan fayllar shu zahoti yuboriladi.)",
        parse_mode="HTML",
    )


@router.message(IsCollectingSpecialTask(), F.photo)
async def collect_photo(message: Message):
    session = _pending_submissions.get(message.from_user.id)
    if not session:
        return
    session["files"].append({"type": "photo", "file_id": message.photo[-1].file_id})
    log.info("COLLECT: %s dan rasm qabul qilindi (jami %d ta)", message.from_user.id, len(session["files"]))
    await message.answer(f"✅ Qabul qilindi ({len(session['files'])} ta). Yana yuborishingiz mumkin.")


@router.message(IsCollectingSpecialTask(), F.document)
async def collect_document(message: Message):
    session = _pending_submissions.get(message.from_user.id)
    if not session:
        return
    session["files"].append({"type": "document", "file_id": message.document.file_id})
    log.info("COLLECT: %s dan hujjat qabul qilindi (jami %d ta)", message.from_user.id, len(session["files"]))
    await message.answer(f"✅ Qabul qilindi ({len(session['files'])} ta). Yana yuborishingiz mumkin.")


@router.message(IsCollectingSpecialTask())
async def flush_on_other_action(message: Message, bot):
    """Fayl/hujjatdan boshqa har qanday xabar kelsa — to'plangan fayllarni darhol
    yuborib, xabarni navbatdagi handlerga (masalan menyu tugmasi) o'tkazamiz."""
    log.info("BUTTON-FLUSH: %s boshqa xabar yubordi (text=%r), darhol flush qilinmoqda", message.from_user.id, message.text)
    sent = await _flush_submission(bot, message.from_user.id)
    if sent:
        await message.answer(f"✅ {sent} ta fayl ustozga yuborildi.")
    raise SkipHandler
