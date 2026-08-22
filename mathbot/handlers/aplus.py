import time
from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)

import database as db
from config import WEBAPP_URL, TEST_WEBAPP_URL, is_admin
from states import APlusCode
from keyboards import NAV_BUTTON_TEXTS

router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")

WEBAPP_BASE = WEBAPP_URL.rstrip("/")
TEST_WEBAPP_BASE = TEST_WEBAPP_URL.rstrip("/")


# ---------- Admin: A+ testini Mini App orqali yaratish ----------

@router.message(F.text == "➕ A+ yaratish")
async def open_admin_aplus_app(message: Message):
    if not is_admin(message.from_user.id):
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ A+ savollarini kiritish",
                    web_app=WebAppInfo(url=f"{WEBAPP_BASE}/aplus_admin.html?t={int(time.time())}"),
                )
            ]
        ]
    )
    await message.answer(
        "Quyidagi tugma orqali A+ (yozma javobli) savollarning to'g'ri javoblarini kiriting.\n"
        "Tasdiqlagach, sizga test kodi beriladi.",
        reply_markup=kb,
    )


def _aplus_status_label(test) -> str:
    if not test["is_active"]:
        return "🗑 Bekor qilingan"
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    if now < test["start_time"]:
        return "⏳ Kutilmoqda"
    if now > test["end_time"]:
        return "🔒 Tugagan"
    return "🟢 Faol"


async def _build_aplus_list():
    tests = await db.get_all_aplus_tests(limit=15)
    if not tests:
        return "Hozircha birorta A+ test yaratilmagan.", None

    lines = ["🗂 <b>A+ testlar ro'yxati</b> (oxirgi 15 tasi):"]
    kb_rows = []
    for t in tests:
        title = t["name"] or "(nomsiz)"
        lines.append(
            f"\n📌 <b>{title}</b>\n"
            f"🔑 <code>{t['code']}</code> — {_aplus_status_label(t)}\n"
            f"   {t['start_time']} → {t['end_time']}"
        )
        kb_rows.append(
            [
                InlineKeyboardButton(
                    text=f"✏️ {t['code']}",
                    web_app=WebAppInfo(
                        url=f"{WEBAPP_BASE}/aplus_admin.html?edit={t['id']}&t={int(time.time())}"
                    ),
                ),
                InlineKeyboardButton(
                    text="🗑 Bekor qilish",
                    callback_data=f"aplus_delete_ask:{t['id']}",
                ),
            ]
        )
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=kb_rows)


@router.message(F.text == "🗂 Mening A+ testlarim")
async def list_aplus_tests(message: Message):
    if not is_admin(message.from_user.id):
        return

    text, kb = await _build_aplus_list()
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("aplus_delete_ask:"))
async def ask_delete_aplus(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
        return

    test_id = int(callback.data.split(":", 1)[1])
    test = await db.get_aplus_test_by_id(test_id)
    if not test:
        await callback.answer("Test topilmadi.", show_alert=True)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"aplus_delete:{test_id}"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="aplus_delete_no"),
            ]
        ]
    )
    name = test["name"] or test["code"]
    await callback.message.edit_text(
        f"⚠️ <b>{name}</b> (<code>{test['code']}</code>) A+ testini butunlay o'chirmoqchimisiz?\n"
        "Bu amalni orqaga qaytarib bo'lmaydi — o'quvchilarning shu testdagi natijalari ham o'chib ketadi.",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("aplus_delete:"))
async def delete_aplus_confirmed(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
        return

    test_id = int(callback.data.split(":", 1)[1])
    await db.delete_aplus_test(test_id)
    await callback.answer("🗑 Test o'chirildi.")

    text, kb = await _build_aplus_list()
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "aplus_delete_no")
async def delete_aplus_cancelled(callback: CallbackQuery):
    await callback.answer("Bekor qilindi.")

    text, kb = await _build_aplus_list()
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


# ---------- O'quvchi: A+ kodini kiritish va Mini App'ni ochish ----------

@router.message(F.text == "➕ A+ ishlash")
async def start_aplus_flow(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or not user["is_registered"]:
        await message.answer("Iltimos, avval /start orqali ro'yxatdan o'ting.")
        return

    await state.set_state(APlusCode.waiting_code)
    await message.answer("🔑 Ustozingiz bergan A+ test kodini kiriting:")


@router.message(APlusCode.waiting_code, F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def process_aplus_code(message: Message, state: FSMContext):
    code = message.text.strip()
    test = await db.get_aplus_test_by_code(code)

    if not test:
        await message.answer("❌ Bunday kod topilmadi. Qaytadan kiriting:")
        return

    await state.clear()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ A+ ni boshlash",
                    web_app=WebAppInfo(url=f"{TEST_WEBAPP_BASE}/aplus.html?code={code}&t={int(time.time())}"),
                )
            ]
        ]
    )
    await message.answer("Quyidagi tugma orqali A+ ni boshlang:", reply_markup=kb)
