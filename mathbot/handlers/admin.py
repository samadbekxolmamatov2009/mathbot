import asyncio
import time

from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
    BotCommandScopeChat,
    WebAppInfo,
)

import database as db
from config import ADMIN_IDS, BOSS_IDS, COURSES, WEBAPP_URL, is_admin
from states import Broadcast
from keyboards import admin_menu_keyboard, NAV_BUTTON_TEXTS
from handlers.boss import notify_boss

WEBAPP_BASE = WEBAPP_URL.rstrip("/")

router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")


ADMIN_COMMANDS = [
    BotCommand(command="stats", description="📊 Statistika"),
    BotCommand(command="users", description="👥 Foydalanuvchilar ro'yxati"),
    BotCommand(command="delete", description="🗑 Foydalanuvchini o'chirish"),
    BotCommand(command="admins", description="👮 Adminlar ro'yxati"),
    BotCommand(command="help", description="ℹ️ Yordam"),
]


# Boss uchun buyruqlar - bu ro'yxat FAQAT BOSS_IDS'ning shaxsiy chatiga
# (BotCommandScopeChat) o'rnatiladi, shuning uchun boshqa hech kim - hatto
# oddiy adminlar ham - buni ko'ra olmaydi (Telegram bot menyusi har bir
# chat uchun alohida, boshqalarga umuman ko'rinmaydi).
BOSS_COMMANDS = ADMIN_COMMANDS + [
    BotCommand(command="boss_add", description="➕ Admin qo'shish"),
    BotCommand(command="boss_remove", description="➖ Adminni olib tashlash"),
    BotCommand(command="boss_score", description="⚖️ O'quvchi ballini o'zgartirish"),
]


async def set_admin_menu(bot):
    """Chap tomondagi ko'k 'Menu' tugmasini faqat adminlar uchun sozlaydi"""
    for admin_id in ADMIN_IDS:
        try:
            await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception:
            pass


async def set_boss_menu(bot):
    """Boss'lar uchun shaxsiy menyuni (admin buyruqlari + boss buyruqlari) sozlaydi."""
    for boss_id in BOSS_IDS:
        try:
            await bot.set_my_commands(BOSS_COMMANDS, scope=BotCommandScopeChat(chat_id=boss_id))
        except Exception:
            pass


async def set_admin_menu_for(bot, admin_id: int):
    try:
        await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
    except Exception:
        pass


async def clear_admin_menu_for(bot, admin_id: int):
    try:
        await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=admin_id))
    except Exception:
        pass


@router.message(Command("get_sticker_id"))
async def cmd_get_sticker_id_prompt(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "Fayl ID'sini bilmoqchi bo'lgan stikeringizni shu chatga yuboring "
        "(yoki forward qiling) — men uning file_id'sini qaytaraman."
    )


@router.message(F.sticker)
async def cmd_get_sticker_id(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        f"🆔 Sticker file_id:\n<code>{message.sticker.file_id}</code>\n\n"
        "Buni <code>registration.py</code> faylidagi <code>WELCOME_STICKER_FILE_ID</code> "
        "qatoriga qo'ying.",
        parse_mode="HTML",
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Yordam")
async def cmd_help(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "Admin buyruqlari:\n"
        "📊 Statistika — ro'yxatdan o'tganlar statistikasi\n"
        "👥 Foydalanuvchilar — barcha foydalanuvchilar ro'yxati (oxirgi 20 tasi)\n"
        "🗑 Foydalanuvchini o'chirish — /delete <telegram_id>\n"
        "👮 Adminlar — adminlar ro'yxati",
        reply_markup=admin_menu_keyboard(),
    )


@router.message(Command("stats"))
@router.message(F.text == "📊 Statistika")
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    rows = await db.count_users_by_course()
    if not rows:
        await message.answer("Hozircha hech kim ro'yxatdan o'tmagan.")
        return

    text = "📊 Statistika:\n\n"
    total = 0
    for row in rows:
        course_name = COURSES.get(row["course"], {}).get("name", row["course"] or "Noma'lum")
        text += f"{course_name}: {row['cnt']}\n"
        total += row["cnt"]
    text += f"\nJami: {total}"
    await message.answer(text)


@router.message(Command("users"))
@router.message(F.text == "👥 Foydalanuvchilar")
async def cmd_users(message: Message):
    if not is_admin(message.from_user.id):
        return

    users = await db.get_all_users()
    if not users:
        await message.answer("Hozircha hech kim ro'yxatdan o'tmagan.")
        return

    text = "👥 Oxirgi foydalanuvchilar:\n\n"
    for u in users[:20]:
        course_name = COURSES.get(u["course"], {}).get("name", u["course"] or "Noma'lum")
        text += (
            f"• ID: <code>{u['telegram_id']}</code> — {u['full_name']}\n"
            f"  {course_name}, {u['region']}, {u['district']}, {u['phone']}\n"
        )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("admins"))
@router.message(F.text == "👮 Adminlar")
async def cmd_admins(message: Message, bot):
    if not is_admin(message.from_user.id):
        return

    lines = ["👮 <b>Adminlar ro'yxati:</b>\n"]
    for admin_id in ADMIN_IDS:
        try:
            chat = await bot.get_chat(admin_id)
            name = chat.full_name or "Noma'lum"
            username = f"@{chat.username}" if chat.username else "—"
        except Exception:
            name = "Noma'lum"
            username = "—"
        lines.append(f"• {name} ({username}) — ID: <code>{admin_id}</code>")

    await message.answer("\n".join(lines), parse_mode="HTML")


DELETE_USAGE_TEXT = (
    "Foydalanuvchi ID sini kiriting:\n<code>/delete 123456789</code>\n\n"
    "ID larni /users buyrug'i orqali ko'rishingiz mumkin."
)


@router.message(F.text == "🗑 Foydalanuvchini o'chirish")
async def delete_button(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(DELETE_USAGE_TEXT, parse_mode="HTML")


@router.message(Command("delete"))
async def cmd_delete(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return

    args = (command.args or "").strip()
    if not args.isdigit():
        await message.answer(DELETE_USAGE_TEXT, parse_mode="HTML")
        return

    target_id = int(args)
    user = await db.get_user(target_id)
    if not user:
        await message.answer("Bunday ID li foydalanuvchi topilmadi.")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ha, o'chirish", callback_data=f"admin_del:{target_id}"
                ),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_del_cancel"),
            ]
        ]
    )
    name = user["full_name"] or "Ism kiritilmagan"
    await message.answer(
        f"⚠️ <b>{name}</b> (ID: {target_id}) ni bazadan butunlay o'chirmoqchimisiz?",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("admin_del:"))
async def confirm_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
        return

    target_id = int(callback.data.split(":", 1)[1])
    deleted = await db.delete_user(target_id)

    if deleted:
        await callback.message.edit_text(f"🗑 Foydalanuvchi (ID: {target_id}) o'chirildi.")
    else:
        await callback.message.edit_text("Foydalanuvchi topilmadi (allaqachon o'chirilgan bo'lishi mumkin).")
    await callback.answer()


@router.callback_query(F.data == "admin_del_cancel")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("Bekor qilindi.")
    await callback.answer()


# ---------- Admin: barcha foydalanuvchilarga xabar yuborish (broadcast) ----------
# Admin xohlagancha matn, rasm va PDF fayl yuborib "xabar"ni tayyorlaydi;
# har biri to'plangandan keyin "✅ Yuborish" tugmasini bosgach, hammasi
# ketma-ket barcha ro'yxatdan o'tgan foydalanuvchilarga jo'natiladi.

def _broadcast_status_kb(count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"✅ Yuborish ({count} ta)", callback_data="broadcast_send"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="broadcast_cancel"),
            ]
        ]
    )


@router.message(F.text == "📢 Xabar yuborish")
async def start_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(Broadcast.composing)
    await state.update_data(items=[])
    await message.answer(
        "📢 Barcha ro'yxatdan o'tgan foydalanuvchilarga yubormoqchi bo'lgan xabaringizni tayyorlang.\n"
        "Matn, rasm yoki PDF fayl yuborishingiz mumkin — xohlagancha, istalgan tartibda.\n"
        "Tayyor bo'lgach, \"✅ Yuborish\" tugmasini bosing."
    )


@router.message(Broadcast.composing, F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def collect_broadcast_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    items = data.get("items", [])
    items.append({"type": "text", "content": message.text})
    await state.update_data(items=items)
    await message.answer(
        f"✅ Matn qabul qilindi ({len(items)} ta element to'plandi).",
        reply_markup=_broadcast_status_kb(len(items)),
    )


@router.message(Broadcast.composing, F.photo)
async def collect_broadcast_photo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    items = data.get("items", [])
    items.append({"type": "photo", "content": message.photo[-1].file_id, "caption": message.caption})
    await state.update_data(items=items)
    await message.answer(
        f"✅ Rasm qabul qilindi ({len(items)} ta element to'plandi).",
        reply_markup=_broadcast_status_kb(len(items)),
    )


@router.message(Broadcast.composing, F.document)
async def collect_broadcast_document(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    items = data.get("items", [])
    items.append({"type": "document", "content": message.document.file_id, "caption": message.caption})
    await state.update_data(items=items)
    await message.answer(
        f"✅ Fayl qabul qilindi ({len(items)} ta element to'plandi).",
        reply_markup=_broadcast_status_kb(len(items)),
    )


@router.callback_query(F.data == "broadcast_send")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
        return

    data = await state.get_data()
    items = data.get("items", [])
    await state.clear()
    await callback.answer()

    if not items:
        await callback.message.edit_text("Hech narsa qo'shilmagan edi, bekor qilindi.")
        return

    await callback.message.edit_text("⏳ Xabar yuborilmoqda...")

    users = await db.get_all_users()
    sent = 0
    failed = 0
    for u in users:
        ok = True
        for item in items:
            try:
                if item["type"] == "text":
                    await bot.send_message(u["telegram_id"], item["content"])
                elif item["type"] == "photo":
                    await bot.send_photo(u["telegram_id"], item["content"], caption=item.get("caption"))
                else:
                    await bot.send_document(u["telegram_id"], item["content"], caption=item.get("caption"))
            except Exception:
                ok = False
            await asyncio.sleep(0.05)
        if ok:
            sent += 1
        else:
            failed += 1

    await callback.message.edit_text(f"✅ Yuborildi: {sent} ta\n❌ Yetib bormadi: {failed} ta")
    await notify_boss(
        bot,
        f"📢 Admin xabar yubordi.\nYuboruvchi ID: <code>{callback.from_user.id}</code>\n"
        f"✅ {sent} ta yetdi, ❌ {failed} ta yetmadi.",
        exclude=callback.from_user.id,
    )


@router.callback_query(F.data == "broadcast_cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Bekor qilindi.")
    await callback.answer()


# ---------- Admin: sozlamalar (haftalik xabar rejasi) ----------

@router.message(F.text == "⚙️ Sozlamalar")
async def open_settings_app(message: Message):
    if not is_admin(message.from_user.id):
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚙️ Sozlamalarni ochish",
                    web_app=WebAppInfo(url=f"{WEBAPP_BASE}/settings.html?t={int(time.time())}"),
                )
            ]
        ]
    )
    await message.answer(
        "Avtomatik xabar rejasini shu yerdan sozlashingiz mumkin — "
        "qaysi kuni, qaysi vaqtda, qanday xabar kanalga yuborilishini belgilang:",
        reply_markup=kb,
    )
