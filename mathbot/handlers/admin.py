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
from config import ADMIN_IDS, BOSS_IDS, COURSES, WEBAPP_URL, can_use_panel, is_admin, is_boss
from states import Broadcast
from keyboards import admin_menu_keyboard, NAV_BUTTON_TEXTS
from handlers.boss import notify_boss

WEBAPP_BASE = WEBAPP_URL.rstrip("/")

router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")


ADMIN_COMMANDS = [
    BotCommand(command="delete", description="🗑 Foydalanuvchini o'chirish"),
    BotCommand(command="admins", description="👮 Adminlar ro'yxati"),
    BotCommand(command="help", description="ℹ️ Yordam"),
]


# Boss uchun buyruqlar - bu ro'yxat FAQAT BOSS_IDS'ning shaxsiy chatiga
# (BotCommandScopeChat) o'rnatiladi, shuning uchun boshqa hech kim - hatto
# oddiy adminlar ham - buni ko'ra olmaydi (Telegram bot menyusi har bir
# chat uchun alohida, boshqalarga umuman ko'rinmaydi).
BOSS_COMMANDS = [
    BotCommand(command="stats", description="📊 Statistika"),
    BotCommand(command="users", description="👥 Foydalanuvchilar ro'yxati"),
] + ADMIN_COMMANDS + [
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

    boss_lines = (
        "📊 Statistika — ro'yxatdan o'tganlar statistikasi\n"
        "👥 Foydalanuvchilar — barcha foydalanuvchilar ro'yxati (oxirgi 20 tasi)\n"
        if is_boss(message.from_user.id) else ""
    )
    text = (
        "🛠 <b>Admin buyruqlari</b>\n\n"
        "🖥 Admin panel — o'quvchilar nazorati va 📊 Hisobotlar (har bir test/davomatni necha kishi qilgani)\n"
        + boss_lines +
        "🗑 Foydalanuvchini o'chirish — /delete &lt;telegram_id&gt;\n"
        "👮 Adminlar — adminlar ro'yxati\n"
        "📅 Davomat — davomat olish/hisobot\n"
        "📝 Javoblarni yozish — oddiy test yaratish (Mini App orqali)\n"
        "🗂 Mening testlarim — yaratilgan oddiy testlar ro'yxati\n"
        "➕ A+ yaratish — A+ test yaratish (Mini App orqali)\n"
        "🗂 Mening A+ testlarim — yaratilgan A+ testlar ro'yxati\n"
        "📋 Maxsus topshiriq yaratish — o'quvchilar rasm/PDF yuboradigan topshiriq\n"
        "📢 Xabar yuborish — barcha o'quvchilarga darhol xabar (matn, rasm, PDF, video, dumaloq video, ovozli xabar va h.k.)\n"
        "⚙️ Sozlamalar — haftalik hisobot vaqtini sozlash\n"
        "/get_sticker_id — botga stiker yuborib, uning file_id'sini olish\n\n"
        "ℹ️ Eslatma: yangi test/A+/maxsus topshiriq faollashtirilganda, barcha "
        "ro'yxatdan o'tgan o'quvchilarga avtomatik xabar boradi."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=admin_menu_keyboard(message.from_user.id))


@router.message(Command("stats"))
@router.message(F.text == "📊 Statistika")
async def cmd_stats(message: Message):
    if not is_boss(message.from_user.id):
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
    if not is_boss(message.from_user.id):
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


@router.message(Command("klaviatura_sinov"), F.chat.type == "private")
async def keyboard_test_command(message: Message):
    """A+ klaviaturasini telefonda sinash: ikki javobni (masalan 0.5 va 1/2) yozib, bir xil
    hisoblanishini ko'rish. Faqat adminlar."""
    if not is_admin(message.from_user.id):
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="⌨ Klaviaturani sinash",
                web_app=WebAppInfo(url=f"{WEBAPP_BASE}/keyboard_test.html?t={int(time.time())}"),
            )
        ]]
    )
    await message.answer(
        "⌨ <b>A+ klaviatura sinovi</b>\n"
        "To'g'ri javobni va o'quvchi javobini kiriting (masalan <code>0.5</code> va <code>1/2</code>) — "
        "bir xil hisoblanishini ko'rasiz.",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.message(Command("xabar_sinov"), F.chat.type == "private")
async def broadcast_self_test(message: Message):
    """Xabar yuborishni O'ZINGIZGA sinash: biror xabarga (premium emoji bilan) javob qilib
    /xabar_sinov yozing - bot uni xuddi o'quvchilarga yuboriladigandek (copy_message) sizga ko'chiradi."""
    if not is_admin(message.from_user.id):
        return
    src = message.reply_to_message
    if not src:
        await message.answer(
            "Sinash uchun: premium emoji bilan xabar yozing, so'ng shu xabarga REPLY qilib /xabar_sinov yuboring.\n"
            "Bot uni o'quvchilarga yuboriladigan usulda faqat sizga ko'chiradi."
        )
        return
    try:
        await message.bot.copy_message(message.chat.id, src.chat.id, src.message_id)
    except Exception as e:
        await message.answer(f"❌ Ko'chirib bo'lmadi: {e}")


@router.message(F.text == "📢 Xabar yuborish")
async def start_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(Broadcast.composing)
    await state.update_data(items=[])
    await message.answer(
        "📢 Barcha ro'yxatdan o'tgan foydalanuvchilarga yubormoqchi bo'lgan xabaringizni tayyorlang.\n"
        "Matn, rasm, PDF, video, dumaloq video, ovozli xabar, GIF, stiker — istalganini, shu jumladan bir nechta faylni BIRDAN (albom) yuborishingiz mumkin. "
        "Premium emoji, qalin/kursiv matn va havolalar o'z holicha saqlanadi.\n"
        "Tayyor bo'lgach, \"✅ Yuborish\" tugmasini bosing."
    )


_broadcast_locks: dict = {}


async def _collect_broadcast_item(message: Message, state: FSMContext, label: str, extra: dict | None = None):
    """Xabarni to'plamga qo'shadi. Bir nechta fayl (albom) BIRDAN yuborilsa, Telegram ularni alohida
    xabarlar sifatida (bir xil media_group_id bilan) kelib tushiradi: ular bir vaqtda kelgani uchun
    to'plam qulf ostida yangilanadi (aks holda ba'zilari yo'qolardi) va albomga faqat BIR marta javob
    beriladi (keyingi fayllar uchun tugma sonini yangilaydi)."""
    lock = _broadcast_locks.setdefault(message.chat.id, asyncio.Lock())
    async with lock:
        data = await state.get_data()
        items = data.get("items", [])
        gid = message.media_group_id
        items.append({
            "type": message.content_type if isinstance(message.content_type, str) else message.content_type.value,
            "chat_id": message.chat.id, "message_id": message.message_id, "group": gid,
            **(extra or {}),
        })
        status = data.get("status")   # [media_group_id, status_message_id]
        await state.update_data(items=items)
        kb = _broadcast_status_kb(len(items))
        if gid and status and status[0] == gid:
            try:
                await message.bot.edit_message_reply_markup(
                    chat_id=message.chat.id, message_id=status[1], reply_markup=kb
                )
            except Exception:
                pass
            return
        sent = await message.answer(
            f"✅ {label} qabul qilindi ({len(items)} ta element to'plandi).", reply_markup=kb
        )
        await state.update_data(status=[gid, sent.message_id] if gid else None)


@router.message(Broadcast.composing, F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def collect_broadcast_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await _collect_broadcast_item(message, state, "Matn", {"content": message.text})


@router.message(Broadcast.composing, F.photo)
async def collect_broadcast_photo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await _collect_broadcast_item(message, state, "Rasm")


@router.message(Broadcast.composing, F.document)
async def collect_broadcast_document(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await _collect_broadcast_item(message, state, "Fayl")


_BROADCAST_OTHER_TYPES = {
    "video": "Video", "video_note": "Dumaloq video", "voice": "Ovozli xabar", "audio": "Audio",
    "animation": "GIF", "sticker": "Stiker", "location": "Joylashuv", "contact": "Kontakt", "poll": "So'rovnoma",
}


@router.message(Broadcast.composing, F.content_type.in_(set(_BROADCAST_OTHER_TYPES)))
async def collect_broadcast_other(message: Message, state: FSMContext):
    """Video, dumaloq video, ovozli xabar, audio, GIF, stiker va boshqalar: yuborishda
    copy_message bilan o'zgarishsiz ko'chiriladi."""
    if not is_admin(message.from_user.id):
        return
    kind = message.content_type if isinstance(message.content_type, str) else message.content_type.value
    await _collect_broadcast_item(message, state, _BROADCAST_OTHER_TYPES.get(kind, "Xabar"))


def _broadcast_batches(items):
    """Ketma-ket kelgan bir xil albom (media_group_id) fayllarini bitta to'plamga birlashtiradi -
    ular copy_messages bilan albom bo'lib yuboriladi. Qolganlari bittadan."""
    batches = []
    for item in items:
        gid = item.get("group")
        if gid and batches and batches[-1]["group"] == gid:
            batches[-1]["items"].append(item)
        else:
            batches.append({"group": gid, "items": [item]})
    return batches


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
    batches = _broadcast_batches(items)
    for u in users:
        ok = True
        for batch in batches:
            try:
                group_items = batch["items"]
                if len(group_items) > 1 and all(i.get("message_id") for i in group_items):
                    # Albom: copy_messages albom tuzilishini saqlab ko'chiradi
                    ids = sorted(i["message_id"] for i in group_items)[:100]
                    await bot.copy_messages(u["telegram_id"], group_items[0]["chat_id"], ids)
                    continue
                for item in group_items:
                    if item.get("message_id"):
                        # copy_message xabarni ASL holicha ko'chiradi: premium emoji, qalin/kursiv,
                        # havolalar va rasm/fayl izohidagi formatlash ham saqlanadi
                        await bot.copy_message(u["telegram_id"], item["chat_id"], item["message_id"])
                    elif item["type"] == "text":
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


# ---------- Admin / Boss: Admin panel (Mini App) ----------

@router.message(F.text == "🖥 Admin panel")
async def open_admin_panel_app(message: Message):
    if not can_use_panel(message.from_user.id):
        # Panel hozircha faqat Boss uchun. Eski menyuda tugma qolib ketgan oddiy
        # admin bosib yuborsa - menyusi tugmasiz holatda yangilanadi.
        if is_admin(message.from_user.id):
            await message.answer(
                "Menyu yangilandi \U0001F447",
                reply_markup=admin_menu_keyboard(message.from_user.id),
            )
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🖥 Admin panelni ochish",
                    web_app=WebAppInfo(url=f"{WEBAPP_BASE}/panel.html?t={int(time.time())}"),
                )
            ]
        ]
    )
    await message.answer(
        "🖥 <b>Admin panel</b>\n"
        "O'quvchilar, vazifa va davomat holati — bir joyda. "
        "Darsga kelmagan va vazifa qilmaganlarni birinchi ko'rib, qo'ng'iroq qilib chiqishingiz mumkin.",
        reply_markup=kb,
        parse_mode="HTML",
    )


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
        "Haftalik hisobot rejasini shu yerdan sozlashingiz mumkin — "
        "qaysi kuni, qaysi vaqtda PDF hisobot kanalga yuborilishini belgilang:",
        reply_markup=kb,
    )
