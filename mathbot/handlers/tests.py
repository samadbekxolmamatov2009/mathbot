import json
import time

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
from timezone_utils import now_tashkent_str
from config import WEBAPP_URL, TEST_WEBAPP_URL, is_admin
from states import TestCode
from keyboards import admin_menu_keyboard, NAV_BUTTON_TEXTS

router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")

WEBAPP_BASE = WEBAPP_URL.rstrip("/")
TEST_WEBAPP_BASE = TEST_WEBAPP_URL.rstrip("/")


# ---------- Admin: javoblarni Mini App orqali kiritish ----------

@router.message(F.text == "📝 Javoblarni yozish")
async def open_admin_test_app(message: Message):
    if not is_admin(message.from_user.id):
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Javoblarni belgilash",
                    web_app=WebAppInfo(url=f"{WEBAPP_BASE}/admin.html?t={int(time.time())}"),
                )
            ]
        ]
    )
    await message.answer(
        "Quyidagi tugma orqali 35 ta savolning to'g'ri javoblarini belgilang.\n"
        "Tasdiqlagach, sizga test kodi beriladi.",
        reply_markup=kb,
    )


@router.message(F.web_app_data)
async def handle_web_app_data(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        payload = json.loads(message.web_app_data.data)
    except (ValueError, TypeError):
        return

    if payload.get("type") in ("test_created", "test_updated"):
        code = payload.get("code", "?")
        name = payload.get("name", "")
        action = "yaratildi" if payload.get("type") == "test_created" else "yangilandi"
        name_line = f"📌 Nomi: <b>{name}</b>\n" if name else ""
        await message.answer(
            f"✅ <b>Test muvaffaqiyatli {action}!</b>\n\n"
            f"{name_line}"
            f"🔑 Kod: <code>{code}</code>\n\n"
            "Bu kodni o'quvchilarga bering — ular \"📝 Test yuborish\" tugmasi orqali kiritishadi.",
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard(),
        )
    elif payload.get("type") in ("aplus_test_created", "aplus_test_updated"):
        code = payload.get("code", "?")
        name = payload.get("name", "")
        action = "yaratildi" if payload.get("type") == "aplus_test_created" else "yangilandi"
        name_line = f"📌 Nomi: <b>{name}</b>\n" if name else ""
        await message.answer(
            f"✅ <b>A+ test muvaffaqiyatli {action}!</b>\n\n"
            f"{name_line}"
            f"🔑 Kod: <code>{code}</code>\n\n"
            "Bu kodni o'quvchilarga bering — ular \"➕ A+ ishlash\" tugmasi orqali kiritishadi.",
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard(),
        )
    elif payload.get("type") == "schedule_saved":
        if payload.get("enabled"):
            await message.answer(
                "✅ <b>Xabar rejasi saqlandi!</b>\n\n"
                f"📅 Har {payload.get('day', '?')}, soat {payload.get('time', '?')} da "
                "barcha o'quvchilarga avtomatik xabar yuboriladi.",
                parse_mode="HTML",
                reply_markup=admin_menu_keyboard(),
            )
        else:
            await message.answer(
                "🔕 Xabar rejasi saqlandi, lekin o'chirilgan holatda — avtomatik yuborilmaydi.",
                reply_markup=admin_menu_keyboard(),
            )


# ---------- Admin: testlar ro'yxati, tahrirlash, bekor qilish ----------

def _test_status_label(test) -> str:
    if not test["is_active"]:
        return "🗑 Bekor qilingan"
    now = now_tashkent_str()
    if now < test["start_time"]:
        return "⏳ Kutilmoqda"
    if now > test["end_time"]:
        return "🔒 Tugagan"
    return "🟢 Faol"


async def _build_tests_list():
    tests = await db.get_all_tests(limit=15)
    if not tests:
        return "Hozircha birorta test yaratilmagan.", None

    lines = ["🗂 <b>Testlar ro'yxati</b> (oxirgi 15 tasi):"]
    kb_rows = []
    for t in tests:
        title = t["name"] or "(nomsiz)"
        lines.append(
            f"\n📌 <b>{title}</b>\n"
            f"🔑 <code>{t['code']}</code> — {_test_status_label(t)}\n"
            f"   {t['start_time']} → {t['end_time']}"
        )
        kb_rows.append(
            [
                InlineKeyboardButton(
                    text=f"✏️ {t['code']}",
                    web_app=WebAppInfo(
                        url=f"{WEBAPP_BASE}/admin.html?edit={t['id']}&t={int(time.time())}"
                    ),
                ),
                InlineKeyboardButton(
                    text="🗑 Bekor qilish",
                    callback_data=f"test_delete_ask:{t['id']}",
                ),
            ]
        )
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=kb_rows)


@router.message(F.text == "🗂 Mening testlarim")
async def list_tests(message: Message):
    if not is_admin(message.from_user.id):
        return

    text, kb = await _build_tests_list()
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("test_delete_ask:"))
async def ask_delete_test(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
        return

    test_id = int(callback.data.split(":", 1)[1])
    test = await db.get_test_by_id(test_id)
    if not test:
        await callback.answer("Test topilmadi.", show_alert=True)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"test_delete:{test_id}"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="test_delete_no"),
            ]
        ]
    )
    name = test["name"] or test["code"]
    await callback.message.edit_text(
        f"⚠️ <b>{name}</b> (<code>{test['code']}</code>) testini butunlay o'chirmoqchimisiz?\n"
        "Bu amalni orqaga qaytarib bo'lmaydi — o'quvchilarning shu testdagi natijalari ham o'chib ketadi.",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("test_delete:"))
async def delete_test_confirmed(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
        return

    test_id = int(callback.data.split(":", 1)[1])
    await db.delete_test(test_id)
    await callback.answer("🗑 Test o'chirildi.")

    text, kb = await _build_tests_list()
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "test_delete_no")
async def delete_test_cancelled(callback: CallbackQuery):
    await callback.answer("Bekor qilindi.")

    text, kb = await _build_tests_list()
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


# ---------- O'quvchi: test kodini kiritish va Mini App'ni ochish ----------

@router.message(F.text == "📝 Test yuborish")
async def start_test_flow(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or not user["is_registered"]:
        await message.answer("Iltimos, avval /start orqali ro'yxatdan o'ting.")
        return

    await state.set_state(TestCode.waiting_code)
    await message.answer("🔑 Ustozingiz bergan test kodini kiriting:")


@router.message(TestCode.waiting_code, F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def process_test_code(message: Message, state: FSMContext):
    code = message.text.strip()
    test = await db.get_test_by_code(code)

    if not test:
        await message.answer("❌ Bunday kod topilmadi. Qaytadan kiriting:")
        return

    await state.clear()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Testni boshlash",
                    web_app=WebAppInfo(url=f"{TEST_WEBAPP_BASE}/?code={code}&t={int(time.time())}"),
                )
            ]
        ]
    )
    await message.answer("Quyidagi tugma orqali testni boshlang:", reply_markup=kb)
