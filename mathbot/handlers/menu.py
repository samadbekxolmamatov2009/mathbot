import re
import time

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    ReplyKeyboardRemove,
)

import database as db
from config import ADMIN_IDS, COURSES, WEBAPP_URL
from states import ProfileEdit
from keyboards import NAV_BUTTON_TEXTS, regions_keyboard, districts_keyboard, phone_request_keyboard

router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")

WEBAPP_BASE = WEBAPP_URL.rstrip("/")
ADMIN_CONTACT_URL = "https://t.me/xolmamatov09"
PHONE_RE = re.compile(r"^\+998\d{9}$")


async def _ensure_registered(message: Message) -> bool:
    user = await db.get_user(message.from_user.id)
    if not user or not user["is_registered"]:
        await message.answer("Iltimos, avval /start orqali ro'yxatdan o'ting.")
        return False
    return True


@router.message(F.text == "👤 Profil")
async def show_profile(message: Message):
    if not await _ensure_registered(message):
        return

    user = await db.get_user(message.from_user.id)
    course = COURSES.get(user["course"], {}).get("name", user["course"])

    text = (
        "👤 <b>Profilingiz</b>\n\n"
        f"Ism: <b>{user['full_name']}</b>\n"
        f"Kurs: <b>{course}</b>\n"
        f"Viloyat: <b>{user['region']}</b>\n"
        f"Manzil: <b>{user['district']}</b>\n"
        f"Telefon: <b>{user['phone']}</b>"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Ma'lumotlarni tahrirlash", callback_data="profile_edit_menu")]
        ]
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "profile_edit_menu")
async def profile_edit_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Ism-familiya", callback_data="profile_edit:name")],
            [InlineKeyboardButton(text="📍 Manzil (viloyat/tuman)", callback_data="profile_edit:location")],
            [InlineKeyboardButton(text="📱 Telefon", callback_data="profile_edit:phone")],
        ]
    )
    await callback.message.edit_text("Qaysi ma'lumotni o'zgartirmoqchisiz?", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "profile_edit:name")
async def profile_edit_name_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileEdit.waiting_last_name)
    await callback.message.edit_text(
        "📝 Yangi familiyangizni kiriting:\n<i>Masalan: Karimov</i>", parse_mode="HTML"
    )
    await callback.answer()


@router.message(ProfileEdit.waiting_last_name)
async def profile_edit_last_name(message: Message, state: FSMContext):
    last_name = (message.text or "").strip()
    if len(last_name.split()) != 1 or len(last_name) < 2:
        await message.answer("Iltimos, familiyani bitta so'z bilan kiriting.")
        return

    await state.update_data(last_name=last_name)
    await state.set_state(ProfileEdit.waiting_first_name)
    await message.answer("📝 Endi ismingizni kiriting:\n<i>Masalan: Jasur</i>", parse_mode="HTML")


@router.message(ProfileEdit.waiting_first_name)
async def profile_edit_first_name(message: Message, state: FSMContext):
    first_name = (message.text or "").strip()
    if len(first_name.split()) != 1 or len(first_name) < 2:
        await message.answer("Iltimos, ismni bitta so'z bilan kiriting.")
        return

    data = await state.get_data()
    full_name = f"{data['last_name']} {first_name}"
    await state.clear()
    await db.save_full_name(message.from_user.id, full_name)
    await message.answer(f"✅ Ism-familiya yangilandi: <b>{full_name}</b>", parse_mode="HTML")


@router.callback_query(F.data == "profile_edit:location")
async def profile_edit_location_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileEdit.waiting_region)
    await callback.message.edit_text("📍 Yangi viloyatingizni tanlang:", reply_markup=regions_keyboard())
    await callback.answer()


@router.callback_query(ProfileEdit.waiting_region, F.data.startswith("region:"))
async def profile_edit_region(callback: CallbackQuery, state: FSMContext):
    region = callback.data.split(":", 1)[1]
    await state.update_data(region=region)
    await state.set_state(ProfileEdit.waiting_district)
    await callback.message.edit_text(
        f"✅ Viloyat: <b>{region}</b>\n\n🏘 Tumaningizni / shahringizni tanlang:",
        parse_mode="HTML",
        reply_markup=districts_keyboard(region),
    )
    await callback.answer()


@router.callback_query(ProfileEdit.waiting_district, F.data == "back_to_region")
async def profile_edit_back_to_region(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileEdit.waiting_region)
    await callback.message.edit_text("📍 Yangi viloyatingizni tanlang:", reply_markup=regions_keyboard())
    await callback.answer()


@router.callback_query(ProfileEdit.waiting_district, F.data.startswith("district:"))
async def profile_edit_district(callback: CallbackQuery, state: FSMContext):
    district = callback.data.split(":", 1)[1]
    data = await state.get_data()
    await state.clear()

    await db.save_region(callback.from_user.id, data["region"])
    await db.save_district(callback.from_user.id, district)
    await callback.message.edit_text(
        f"✅ Manzil yangilandi: <b>{data['region']}, {district}</b>", parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "profile_edit:phone")
async def profile_edit_phone_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileEdit.waiting_phone)
    await callback.message.edit_text("📱 Yangi telefon raqamingizni yuboring.")
    await callback.message.answer(
        "Tugmani bosing yoki raqamni qo'lda kiriting (+998XXXXXXXXX):",
        reply_markup=phone_request_keyboard(),
    )
    await callback.answer()


@router.message(ProfileEdit.waiting_phone, F.contact)
async def profile_edit_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    await _finish_phone_edit(message, state, phone)


@router.message(ProfileEdit.waiting_phone, F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def profile_edit_phone_text(message: Message, state: FSMContext):
    phone = message.text.strip().replace(" ", "")
    if not phone.startswith("+"):
        phone = "+" + phone

    if not PHONE_RE.match(phone):
        await message.answer(
            "❗️ Raqam formati noto'g'ri. Iltimos, quyidagicha kiriting:\n"
            "<code>+998901234567</code>\nyoki pastdagi tugmani bosing.",
            parse_mode="HTML",
            reply_markup=phone_request_keyboard(),
        )
        return

    await _finish_phone_edit(message, state, phone)


async def _finish_phone_edit(message: Message, state: FSMContext, phone: str):
    await state.clear()
    await db.finish_registration(message.from_user.id, phone)
    await message.answer(
        f"✅ Telefon raqam yangilandi: <b>{phone}</b>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(F.text == "🏆 Reyting")
async def show_rating(message: Message):
    if not await _ensure_registered(message):
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏆 Reytingni ko'rish",
                    web_app=WebAppInfo(url=f"{WEBAPP_BASE}/rating.html?t={int(time.time())}"),
                )
            ]
        ]
    )
    await message.answer(
        "Eng ko'p tanga to'plagan TOP 50 o'quvchi:", reply_markup=kb
    )


@router.message(F.text == "📊 Natijalarim")
async def show_my_results(message: Message):
    if not await _ensure_registered(message):
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Natijalarni ko'rish",
                    web_app=WebAppInfo(url=f"{WEBAPP_BASE}/results.html?t={int(time.time())}"),
                )
            ]
        ]
    )
    await message.answer(
        "Barcha test natijalaringizni grafik ko'rinishida ko'rish uchun tugmani bosing:",
        reply_markup=kb,
    )


@router.message(F.text == "📩 Adminga xabar")
async def contact_admin_prompt(message: Message):
    if not await _ensure_registered(message):
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Administrator bilan bog'lanish", url=ADMIN_CONTACT_URL)],
        ]
    )
    await message.answer(
        "Administratorga savol yoki murojaatingiz bo'lsa, quyidagi tugma orqali to'g'ridan-to'g'ri bog'lanishingiz mumkin:",
        reply_markup=kb,
    )


# Boshqa hech bir router ushlamagan rasm/fayl shu yerga tushadi — bu odatda
# maxsus topshiriq sessiyasi (bot qayta ishga tushgani yoki hali boshlanmagani
# uchun) faol emasligini bildiradi. Jim qolish o'rniga foydalanuvchiga xabar
# beramiz, aks holda fayl "yo'qolgandek" ko'rinadi.
@router.message(F.photo | F.document)
async def stray_file(message: Message):
    await message.answer(
        "⚠️ Hozir bu faylni kutayotgan faol jarayon yo'q, shuning uchun u hech kimga yuborilmadi.\n"
        "Maxsus topshiriq uchun fayl yubormoqchi bo'lsangiz, avval "
        "\"📋 Maxsus topshiriq yuborish\" tugmasini bosing, so'ng rasm/PDF yuboring."
    )
