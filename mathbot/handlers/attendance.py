import asyncio
import os
import random
import tempfile

from aiogram import Router, F
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    FSInputFile,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import database as db
from config import ADMIN_IDS, BOSS_IDS, COURSES, is_admin
from states import Attendance, AttendanceCode
from pdf_report import generate_attendance_report, generate_attendance_matrix_report
from keyboards import NAV_BUTTON_TEXTS

router = Router()
router.message.filter(F.chat.type == "private")

CONSECUTIVE_MISS_THRESHOLD = 3


class HasPendingAbsenceReason(BaseFilter):
    """Foydalanuvchidan 3 kunlik qatnashmaslik sababi so'ralgan-so'ralmaganini tekshiradi."""

    async def __call__(self, message: Message) -> bool:
        pending = await db.get_pending_absence_reason(message.from_user.id)
        return pending is not None


@router.message(F.text == "📅 Davomat")
async def davomat_button(message: Message, state: FSMContext):
    if is_admin(message.from_user.id):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🆕 Yangi davomat boshlash", callback_data="attendance_new")],
                [InlineKeyboardButton(text="📊 Jadvalni ko'rish", callback_data="attendance_matrix")],
                [InlineKeyboardButton(text="🔄 Davomatni yangilash", callback_data="attendance_reset_ask")],
            ]
        )
        await message.answer("📅 Davomat bo'limi:", reply_markup=kb)
    else:
        await start_attendance_user(message, state)


@router.callback_query(F.data == "attendance_new")
async def attendance_new_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
        return
    await callback.answer()
    await start_attendance_admin(callback.message, state)


def _format_session_label(session) -> str:
    created = session["created_at"] or ""
    try:
        date_part, time_part = created.split(" ")
        _, month, day = date_part.split("-")
        hh, mm = time_part.split(":")[:2]
        return f"{day}.{month} {hh}:{mm}"
    except Exception:
        return session["code"]


@router.callback_query(F.data == "attendance_matrix")
async def attendance_matrix_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
        return
    await callback.answer()

    sessions, users, attended_set = await db.get_attendance_matrix()
    if not sessions:
        await callback.message.edit_text("Hozircha birorta davomat sessiyasi o'tkazilmagan.")
        return
    if not users:
        await callback.message.edit_text("Hozircha birorta ro'yxatdan o'tgan foydalanuvchi yo'q.")
        return

    await callback.message.edit_text("⏳ Jadval tayyorlanmoqda...")

    session_labels = [_format_session_label(s) for s in sessions]
    rows = []
    for u in users:
        statuses = []
        for s in sessions:
            if u["registered_at"] and s["created_at"] and u["registered_at"] > s["created_at"]:
                statuses.append("na")
            elif (s["id"], u["telegram_id"]) in attended_set:
                statuses.append("in")
            else:
                statuses.append("out")
        rows.append((u["full_name"] or "Noma'lum", statuses))

    path = os.path.join(tempfile.gettempdir(), "davomat_jadvali.pdf")
    generate_attendance_matrix_report(path, session_labels, rows)

    await callback.message.delete()
    await callback.message.answer_document(
        FSInputFile(path),
        caption="📊 Yashil — qatnashdi, Qizil — qatnashmadi, Kulrang — o'sha payt hali ro'yxatdan o'tmagan edi.",
    )


@router.callback_query(F.data == "attendance_reset_ask")
async def attendance_reset_ask_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
        return
    await callback.answer()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, yangilash", callback_data="attendance_reset_confirm"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="attendance_reset_no"),
            ]
        ]
    )
    await callback.message.edit_text(
        "🔄 Davomat jadvalini yangilamoqchimisiz?\n\n"
        "Hozirgacha bo'lgan davomat sessiyalari \"📊 Jadvalni ko'rish\" hisobotida "
        "endi ko'rsatilmaydi — jadval shu paytdan boshlab yangidan boshlanadi "
        "(PDF fayl vaqt o'tishi bilan haddan tashqari kattalashib ketmasligi uchun).\n\n"
        "❗️ Bu o'quvchilarning tanga/ball hisobiga ta'sir qilmaydi — faqat "
        "hisobot jadvalining ko'rinishi qisqaradi.",
        reply_markup=kb,
    )


@router.callback_query(F.data == "attendance_reset_no")
async def attendance_reset_no_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("Bekor qilindi.")


@router.callback_query(F.data == "attendance_reset_confirm")
async def attendance_reset_confirm_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
        return
    await callback.answer()

    await db.reset_attendance_matrix()
    await callback.message.edit_text("✅ Davomat jadvali yangilandi — endi shu paytdan boshlab yuritiladi.")


# ---------- Admin: davomat sessiyasini boshlash ----------
# Muddatlar SOATDA kiritiladi (masalan 24 yoki 1,5), bazada esa daqiqada saqlanadi.
# Bir vaqtda bir nechta davomat ochiq turishi mumkin.

HOURS_RE = r"^\s*\d+([.,]\d+)?\s*$"


def _hours_to_minutes(text: str) -> int:
    return round(float(text.strip().replace(",", ".")) * 60)


def _fmt_hours(minutes: int) -> str:
    h = minutes / 60
    return (f"{h:g}".replace(".", ",")) + " soat"


async def start_attendance_admin(message: Message, state: FSMContext):
    active = await db.get_active_attendance_sessions()
    if active:
        codes = ", ".join(f"<code>{s['code']}</code>" for s in active)
        await message.answer(
            f"ℹ️ Hozir {len(active)} ta faol davomat bor (kodlar: {codes}).\n"
            "Yangisini boshlasangiz, ular ham <b>o'z muddati tugaguncha faol qoladi</b> - "
            "o'quvchilar istalgan faol davomat kodini kiritishi mumkin.",
            parse_mode="HTML",
        )

    await state.set_state(Attendance.waiting_warning_minutes)
    await message.answer(
        "⏰ Necha <b>soatdan</b> keyin kod kiritmagan o'quvchilarga ogohlantirish yuborilsin?\n"
        "Faqat son kiriting (masalan: 12 yoki 1,5)",
        parse_mode="HTML",
    )


@router.message(Attendance.waiting_warning_minutes, F.text.regexp(HOURS_RE))
async def set_warning_minutes(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    minutes = _hours_to_minutes(message.text)
    if minutes <= 0:
        await message.answer("Iltimos, musbat son kiriting (masalan: 12)")
        return

    await state.update_data(warning_minutes=minutes)
    await state.set_state(Attendance.waiting_report_minutes)
    await message.answer(
        "📄 Necha <b>soatdan</b> keyin davomat yopilib, yakuniy hisobot (PDF) yuborilsin?\n"
        "Faqat son kiriting (masalan: 24)",
        parse_mode="HTML",
    )


@router.message(Attendance.waiting_warning_minutes, F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def set_warning_minutes_invalid(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Iltimos, soatni son bilan kiriting (masalan: 12 yoki 1,5)")


@router.message(Attendance.waiting_report_minutes, F.text.regexp(HOURS_RE))
async def set_report_minutes(message: Message, state: FSMContext, bot):
    if not is_admin(message.from_user.id):
        return

    report_minutes = _hours_to_minutes(message.text)
    data = await state.get_data()
    warning_minutes = data["warning_minutes"]
    if report_minutes <= 0 or report_minutes < warning_minutes:
        await message.answer(
            f"Hisobot vaqti ogohlantirishdan ({_fmt_hours(warning_minutes)}) keyin bo'lishi kerak. "
            "Qaytadan kiriting (masalan: 24)"
        )
        return
    await state.clear()

    # Kod faol davomatlar kodlari bilan takrorlanmasin
    busy = {s["code"] for s in await db.get_active_attendance_sessions()}
    free = [f"{i:02d}" for i in range(100) if f"{i:02d}" not in busy]
    code = random.choice(free) if free else f"{random.randint(100, 999)}"
    session_id = await db.create_attendance_session(code, warning_minutes, report_minutes)

    await message.answer(
        "✅ <b>Davomat boshlandi!</b>\n\n"
        f"🔑 Kod: <code>{code}</code>\n"
        f"⏰ Ogohlantirish: {_fmt_hours(warning_minutes)}dan keyin\n"
        f"📄 Yopilish va hisobot: {_fmt_hours(report_minutes)}dan keyin\n\n"
        "Kodni o'quvchilarga ayting. Ular \"📅 Davomat\" tugmasi orqali kiritishadi.",
        parse_mode="HTML",
    )

    asyncio.create_task(
        _run_attendance_session(bot, session_id, warning_minutes, report_minutes)
    )


@router.message(Attendance.waiting_report_minutes, F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def set_report_minutes_invalid(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Iltimos, soatni son bilan kiriting (masalan: 24)")


async def _run_attendance_session(bot, session_id: int, warning_minutes: int, report_minutes: int,
                                  elapsed_seconds: float = 0):
    """elapsed_seconds - bot qayta ishga tushganda davomat boshlanganidan beri
    o'tgan vaqt: qolgan vaqt kutiladi, o'tib ketgan ogohlantirish qayta yuborilmaydi."""
    warn_left = warning_minutes * 60 - elapsed_seconds
    if warn_left > 0:
        await asyncio.sleep(warn_left)
        unattended = await db.get_unattended_user_ids(session_id)
        for user_id in unattended:
            try:
                await bot.send_message(user_id, "❗️ Hurmatli o'quvchi, darslarni qoldirmang!")
            except Exception:
                pass

    remaining = report_minutes * 60 - max(elapsed_seconds, warning_minutes * 60)
    if remaining > 0:
        await asyncio.sleep(remaining)

    await db.close_attendance_session(session_id)

    final_unattended = await db.get_unattended_user_ids(session_id)
    for user_id in final_unattended:
        streak = await db.get_consecutive_miss_streak(user_id)
        if streak == CONSECUTIVE_MISS_THRESHOLD:
            await db.set_pending_absence_reason(user_id, session_id)
            try:
                await bot.send_message(
                    user_id,
                    f"❗️ Siz ketma-ket {CONSECUTIVE_MISS_THRESHOLD} marta darsga qatnashmadingiz.\n"
                    "Nega shuncha vaqt davomida darsga qatnashmaganingiz sababini yozib yuboring "
                    "— bu ustozingizga yetkaziladi:",
                )
            except Exception:
                pass

    summary = await db.get_attendance_summary(session_id)
    rows = [
        (
            u["full_name"] or "Noma'lum",
            COURSES.get(u["course"], {}).get("name", u["course"] or "Noma'lum"),
            bool(u["attended"]),
        )
        for u in summary
    ]

    report_path = os.path.join(tempfile.gettempdir(), f"davomat_{session_id}.pdf")
    generate_attendance_report(report_path, rows)

    for admin_id in ADMIN_IDS + BOSS_IDS:
        try:
            await bot.send_document(admin_id, FSInputFile(report_path))
        except Exception:
            pass


@router.startup()
async def _resume_attendance_sessions(bot):
    """Bot qayta ishga tushganda (deploy) faol davomatlar taymeri yo'qolmasin."""
    from datetime import datetime, timezone
    for s_ in await db.get_active_attendance_sessions():
        try:
            created = datetime.strptime(str(s_["created_at"])[:19], "%Y-%m-%d %H:%M:%S")
            elapsed = (datetime.now(timezone.utc).replace(tzinfo=None) - created).total_seconds()
        except ValueError:
            elapsed = 0
        asyncio.create_task(_run_attendance_session(
            bot, s_["id"], s_["warning_minutes"], s_["report_minutes"], elapsed_seconds=max(0, elapsed)
        ))


# ---------- O'quvchi: kodni kiritish ----------

async def start_attendance_user(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or not user["is_registered"]:
        await message.answer("Iltimos, avval /start orqali ro'yxatdan o'ting.")
        return

    sessions = await db.get_active_attendance_sessions()
    if not sessions:
        await message.answer("Hozircha faol davomat mavjud emas.")
        return

    pending = [s_ for s_ in sessions if not await db.has_submitted_attendance(s_["id"], message.from_user.id)]
    if not pending:
        await message.answer("✅ Siz barcha faol darslarga davomat belgilagansiz.")
        return

    await state.set_state(AttendanceCode.waiting_code)
    await message.answer("🔑 Ustozingiz aytgan davomat kodini kiriting:")


@router.message(AttendanceCode.waiting_code, F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def process_attendance_code(message: Message, state: FSMContext):
    code = message.text.strip()
    sessions = [s_ for s_ in await db.get_active_attendance_sessions() if s_["code"] == code]

    if not sessions:
        await message.answer("❌ Kod noto'g'ri yoki bu davomat yakunlangan. Qaytadan urinib ko'ring:")
        return

    session = sessions[0]
    if await db.has_submitted_attendance(session["id"], message.from_user.id):
        await state.clear()
        await message.answer("✅ Siz bu darsga allaqachon davomat belgilagansiz.")
        return

    await db.record_attendance(session["id"], message.from_user.id)
    await state.clear()
    await message.answer("✅ Davomatingiz qabul qilindi. Rahmat!")


# ---------- O'quvchi: ketma-ket qatnashmaslik sababini yozish ----------

@router.message(HasPendingAbsenceReason(), F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def process_absence_reason(message: Message, bot):
    pending = await db.get_pending_absence_reason(message.from_user.id)
    if not pending:
        return

    await db.clear_pending_absence_reason(message.from_user.id)

    user = await db.get_user(message.from_user.id)
    name = (user["full_name"] if user else None) or "Noma'lum"
    course = COURSES.get(user["course"], {}).get("name", user["course"]) if user else "Noma'lum"

    for admin_id in ADMIN_IDS + BOSS_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"⚠️ <b>{name}</b> ({course}, ID: <code>{message.from_user.id}</code>) "
                f"ketma-ket {CONSECUTIVE_MISS_THRESHOLD} kun darsga qatnashmadi.\n\n"
                f"📝 Sababi: {message.text}",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await message.answer("✅ Rahmat, sababingiz ustozingizga yetkazildi.")
