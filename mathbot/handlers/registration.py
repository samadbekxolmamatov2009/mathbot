import asyncio
import logging
import re

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import database as db
from states import Registration
from config import COURSES, is_admin, is_boss
from keyboards import (
    role_keyboard,
    courses_keyboard,
    regions_keyboard,
    districts_keyboard,
    phone_request_keyboard,
    main_menu_keyboard,
    admin_menu_keyboard,
    boss_menu_keyboard,
)

router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")

PHONE_RE = re.compile(r"^\+998\d{9}$")

import os

from aiogram.types import FSInputFile

WELCOME_STICKER_FILE_ID = (
    "CAACAgIAAxkBAAID8WqEPP6ypYIZMHQNZdoiPD-zPvdbAAJCAAMnFEkLruH2y45Rc_g9BA"
)

# Agar stiker o'rniga oddiy rasm (jpg/png) yuborishni xohlasangiz - shu nomdagi
# faylni "mathbot/assets/welcome.jpg" (yoki .png) sifatida repo'ga qo'shing.
# Fayl topilsa, u stiker o'rniga avtomatik yuboriladi (stikerga umuman
# tegilmaydi). Fayl bo'lmasa - yuqoridagi WELCOME_STICKER_FILE_ID ishlatiladi.
WELCOME_IMAGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "welcome.jpg"
)


def progress(step: int, total: int = 7) -> str:
    filled = "\u25cf" * step
    empty = "\u25cb" * (total - step)
    return f"{filled}{empty}  ({step}/{total})"


# ---------- Kanalga obuna tekshiruvi (kurs tanlanganda) ----------

async def _is_subscribed(bot, user_id: int, channel: str) -> bool:
    """Foydalanuvchi berilgan kanalga obuna ekanini tekshiradi. Bot o'sha
    kanalda admin bo'lishi shart - aks holda (yoki boshqa texnik xato bo'lsa)
    ro'yxatdan o'tishni butunlay bloklab qo'ymaslik uchun xavfsiz tomonga
    (obuna deb hisoblab) o'tamiz, xatoni esa logga yozamiz."""
    try:
        member = await bot.get_chat_member(channel, user_id)
        return member.status not in ("left", "kicked")
    except Exception:
        logging.exception("Obuna tekshiruvida xatolik (kanal: %s, user: %s)", channel, user_id)
        return True


def _subscription_gate_keyboard(channel: str, course_key: str) -> InlineKeyboardMarkup:
    url = f"https://t.me/{channel.lstrip('@')}" if channel.startswith("@") else channel
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url=url)],
            [
                InlineKeyboardButton(
                    text="✅ Obuna bo'ldim, tekshirish",
                    callback_data=f"check_course_sub:{course_key}",
                )
            ],
        ]
    )


async def _begin_registration(bot, chat_id: int, user_id: int, state: FSMContext):
    await db.start_registration(user_id)
    await state.set_state(Registration.waiting_role)
    try:
        if os.path.isfile(WELCOME_IMAGE_PATH):
            await bot.send_photo(chat_id, FSInputFile(WELCOME_IMAGE_PATH))
        else:
            await bot.send_sticker(chat_id, WELCOME_STICKER_FILE_ID)
    except Exception:
        pass
    await bot.send_message(
        chat_id,
        "\U0001F44B <b>Assalomu alaykum!</b>\n\n"
        "Ro'yxatdan o'tish uchun bir necha savolga javob bering.\n\n"
        f"{progress(1)}\n"
        "\U0001F393 Siz o'quvchimisiz yoki o'qituvchimisiz?",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await bot.send_message(chat_id, "Tanlang:", reply_markup=role_keyboard())


# ---------- /start ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    if is_boss(message.from_user.id):
        await message.answer(
            "Assalomu alaykum, Boss! \U0001F451\n\n"
            "Quyidagi menyudan foydalaning \U0001F447",
            reply_markup=boss_menu_keyboard(),
        )
        return

    if is_admin(message.from_user.id):
        await message.answer(
            "Assalomu alaykum, Admin! \U0001F44B\n\n"
            "Quyidagi menyudan foydalaning \U0001F447",
            reply_markup=admin_menu_keyboard(),
        )
        return

    if await db.is_user_registered(message.from_user.id):
        await message.answer(
            "Siz allaqachon ro'yxatdan o'tgansiz! \U0001F389\n"
            "Quyidagi menyudan foydalaning \U0001F447",
            reply_markup=main_menu_keyboard(),
        )
        return

    await _begin_registration(message.bot, message.chat.id, message.from_user.id, state)


ROLE_LABELS = {"student": "O'quvchi", "teacher": "O'qituvchi"}


# ---------- 1. Rol ----------

@router.callback_query(Registration.waiting_role, F.data.startswith("role:"))
async def process_role(callback: CallbackQuery, state: FSMContext):
    role = callback.data.split(":", 1)[1]

    await db.save_role(callback.from_user.id, role)
    await state.set_state(Registration.waiting_last_name)
    await callback.message.edit_text(
        f"\u2705 Rol: <b>{ROLE_LABELS.get(role, role)}</b>\n\n"
        f"{progress(2)}\n"
        "\U0001F4DD Familiyangizni kiriting:\n"
        "<i>Masalan: Karimov</i>",
        parse_mode="HTML",
    )
    await callback.answer()


# ---------- 2-3. Familiya, Ism ----------

@router.message(Registration.waiting_last_name)
async def process_last_name(message: Message, state: FSMContext):
    last_name = (message.text or "").strip()
    if len(last_name.split()) != 1 or len(last_name) < 2:
        await message.answer(
            "Iltimos, familiyangizni bitta so'z bilan kiriting.\n"
            "<i>Masalan: Karimov</i>",
            parse_mode="HTML",
        )
        return

    await state.update_data(last_name=last_name)
    await state.set_state(Registration.waiting_first_name)
    await message.answer(
        f"\u2705 Familiya: <b>{last_name}</b>\n\n"
        f"{progress(3)}\n"
        "\U0001F4DD Ismingizni kiriting:\n"
        "<i>Masalan: Jasur</i>",
        parse_mode="HTML",
    )


@router.message(Registration.waiting_first_name)
async def process_first_name(message: Message, state: FSMContext):
    first_name = (message.text or "").strip()
    if len(first_name.split()) != 1 or len(first_name) < 2:
        await message.answer(
            "Iltimos, ismingizni bitta so'z bilan kiriting.\n"
            "<i>Masalan: Jasur</i>",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    full_name = f"{data['last_name']} {first_name}"
    await db.save_full_name(message.from_user.id, full_name)
    await state.set_state(Registration.waiting_course)
    await message.answer(
        f"\u2705 Rahmat, <b>{full_name}</b>!\n\n"
        f"{progress(4)}\n"
        "\U0001F4DA Qaysi kursga ro'yxatdan o'tmoqchisiz?",
        parse_mode="HTML",
        reply_markup=courses_keyboard(),
    )


# ---------- 4. Kurs ----------

@router.callback_query(Registration.waiting_course, F.data.startswith("course:"))
async def process_course(callback: CallbackQuery, state: FSMContext):
    course_key = callback.data.split(":", 1)[1]
    course = COURSES[course_key]

    channel = course.get("channel")
    if channel and not await _is_subscribed(callback.bot, callback.from_user.id, channel):
        await callback.answer()
        await callback.message.edit_text(
            f"🔒 <b>{course['name']}</b> kursiga ro'yxatdan o'tish uchun avval "
            f"kanaliga obuna bo'lishingiz kerak.\n\nObuna bo'lgach, pastdagi "
            f"\"✅ Obuna bo'ldim\" tugmasini bosing.",
            parse_mode="HTML",
            reply_markup=_subscription_gate_keyboard(channel, course_key),
        )
        return

    await callback.answer()
    await _save_course_and_continue(callback, state, course_key)


@router.callback_query(F.data.startswith("check_course_sub:"))
async def cb_check_course_subscription(callback: CallbackQuery, state: FSMContext):
    course_key = callback.data.split(":", 1)[1]
    course = COURSES[course_key]
    channel = course.get("channel")

    if channel and not await _is_subscribed(callback.bot, callback.from_user.id, channel):
        await callback.answer(
            "Hali obuna bo'lmagansiz. Obuna bo'lib, qaytadan urinib ko'ring.",
            show_alert=True,
        )
        return

    await callback.answer("✅ Obuna tasdiqlandi!")
    await _save_course_and_continue(callback, state, course_key)


async def _save_course_and_continue(callback: CallbackQuery, state: FSMContext, course_key: str):
    course_name = COURSES[course_key]["name"]
    await db.save_course(callback.from_user.id, course_key)
    await state.set_state(Registration.waiting_region)
    await callback.message.edit_text(
        f"\u2705 Kurs: <b>{course_name}</b>\n\n"
        f"{progress(5)}\n"
        "\U0001F4CD Viloyatingizni tanlang:",
        parse_mode="HTML",
        reply_markup=regions_keyboard(),
    )


# ---------- 3. Viloyat ----------

@router.callback_query(Registration.waiting_region, F.data.startswith("region:"))
async def process_region(callback: CallbackQuery, state: FSMContext):
    region = callback.data.split(":", 1)[1]

    await db.save_region(callback.from_user.id, region)
    await state.update_data(region=region)
    await state.set_state(Registration.waiting_district)
    await callback.message.edit_text(
        f"\u2705 Viloyat: <b>{region}</b>\n\n"
        f"{progress(6)}\n"
        "\U0001F3D8 Tumaningizni / shahringizni tanlang:",
        parse_mode="HTML",
        reply_markup=districts_keyboard(region),
    )
    await callback.answer()


@router.callback_query(Registration.waiting_district, F.data == "back_to_region")
async def back_to_region(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Registration.waiting_region)
    await callback.message.edit_text(
        f"{progress(5)}\n"
        "\U0001F4CD Viloyatingizni tanlang:",
        parse_mode="HTML",
        reply_markup=regions_keyboard(),
    )
    await callback.answer()


# ---------- 4. Tuman ----------

@router.callback_query(Registration.waiting_district, F.data.startswith("district:"))
async def process_district(callback: CallbackQuery, state: FSMContext):
    district = callback.data.split(":", 1)[1]

    await db.save_district(callback.from_user.id, district)
    await state.set_state(Registration.waiting_phone)
    await callback.message.edit_text(
        f"\u2705 Manzil: <b>{district}</b>\n\n"
        f"{progress(7)}\n"
        "\U0001F4F1 Telefon raqamingizni yuboring.",
        parse_mode="HTML",
    )
    await callback.message.answer(
        "Tugmani bosing yoki raqamni qo'lda kiriting (+998XXXXXXXXX):",
        reply_markup=phone_request_keyboard(),
    )
    await callback.answer()


# ---------- 5. Telefon ----------

@router.message(Registration.waiting_phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    await finish_flow(message, state, phone)


@router.message(Registration.waiting_phone, F.text)
async def process_phone_text(message: Message, state: FSMContext):
    phone = message.text.strip().replace(" ", "")
    if not phone.startswith("+"):
        phone = "+" + phone

    if not PHONE_RE.match(phone):
        await message.answer(
            "\u2757\ufe0f Raqam formati noto'g'ri. Iltimos, quyidagicha kiriting:\n"
            "<code>+998901234567</code>\n"
            "yoki pastdagi tugmani bosing.",
            parse_mode="HTML",
            reply_markup=phone_request_keyboard(),
        )
        return

    await finish_flow(message, state, phone)


async def finish_flow(message: Message, state: FSMContext, phone: str):
    await message.answer("\U0001F50E Ma'lumotlar tekshirilmoqda...", reply_markup=ReplyKeyboardRemove())
    await asyncio.sleep(1)

    await db.finish_registration(message.from_user.id, phone)
    user = await db.get_user(message.from_user.id)
    await state.clear()

    course = COURSES.get(user["course"], {"name": user["course"], "group_link": None})

    text = (
        "\u2705 <b>Ro'yxatdan muvaffaqiyatli o'tdingiz!</b>\n\n"
        f"\U0001F464 Ism: <b>{user['full_name']}</b>\n"
        f"\U0001F4DA Kurs: <b>{course['name']}</b>\n"
        f"\U0001F4CD Viloyat: <b>{user['region']}</b>\n"
        f"\U0001F3D8 Manzil: <b>{user['district']}</b>\n"
        f"\U0001F4F1 Telefon: <b>{user['phone']}</b>\n\n"
        "Birinchi vazifangizni kuting \U0001F447"
    )

    await message.answer(text, parse_mode="HTML")
    await message.answer(
        "Quyidagi menyudan kerakli bo'limni tanlashingiz mumkin \U0001F447",
        reply_markup=main_menu_keyboard(),
    )
