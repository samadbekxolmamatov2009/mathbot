import asyncio
import logging
from datetime import datetime

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand, BotCommandScopeDefault, BotCommandScopeChat
)
from aiogram.exceptions import TelegramBadRequest

# ====== SOZLAMALAR ======
BOT_TOKEN = "8949758073:AAHN_yAycBiuQRo2oVfIqvsh-_h6ZXv_Qtw"
CHANNEL_USERNAME = "@Sertifikat_pro"
ADMIN_IDS = [8113300476, 222222222]  # o'zingizning va boshqa adminlarning Telegram user_id'larini shu yerga yozing
DB_PATH = "bot.db"

# Sovg'a olingandan keyin dumaloq video necha soniyadan keyin yuborilsin.
# Shu raqamni o'zgartirib, kutish vaqtini sozlashingiz mumkin (sekundlarda).
FOLLOWUP_DELAY_SECONDS = 1 * 60  # 1 soat
# =========================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

BOT_USERNAME = ""  # main() ichida avtomatik to'ldiriladi


class AdminStates(StatesGroup):
    waiting_for_files = State()
    waiting_for_followup_video = State()


def subscribe_keyboard(target: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data=f"checksub:{target}")]
    ])


# ---------- Ma'lumotlar bazasi ----------

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gifts (
                gift_id INTEGER PRIMARY KEY AUTOINCREMENT,
                followup_file_id TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gift_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gift_id INTEGER,
                file_id TEXT,
                file_type TEXT,
                caption TEXT,
                position INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                user_id INTEGER,
                gift_id INTEGER,
                full_name TEXT,
                claimed_at TEXT,
                PRIMARY KEY (user_id, gift_id)
            )
        """)
        await db.commit()


async def create_gift() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("INSERT INTO gifts DEFAULT VALUES")
        await db.commit()
        return cur.lastrowid


async def add_file_to_gift(gift_id: int, file_id: str, file_type: str, caption: str | None, position: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO gift_files (gift_id, file_id, file_type, caption, position) VALUES (?, ?, ?, ?, ?)",
            (gift_id, file_id, file_type, caption, position)
        )
        await db.commit()


async def get_all_gifts():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT gift_id FROM gifts ORDER BY gift_id")
        rows = await cur.fetchall()
        return [row[0] for row in rows]


async def gift_exists(gift_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM gifts WHERE gift_id = ?", (gift_id,))
        return (await cur.fetchone()) is not None


async def get_gift_files(gift_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT file_id, file_type, caption FROM gift_files WHERE gift_id = ? ORDER BY position",
            (gift_id,)
        )
        return await cur.fetchall()


async def mark_claim(user_id: int, gift_id: int, full_name: str) -> bool:
    """True qaytaradi — agar bu foydalanuvchi ushbu sovg'ani ilk marta olayotgan bo'lsa."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM claims WHERE user_id = ? AND gift_id = ?", (user_id, gift_id))
        if await cur.fetchone():
            return False
        await db.execute(
            "INSERT INTO claims (user_id, gift_id, full_name, claimed_at) VALUES (?, ?, ?, ?)",
            (user_id, gift_id, full_name, datetime.now().isoformat())
        )
        await db.commit()
        return True


async def delete_gift_from_db(gift_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM gifts WHERE gift_id = ?", (gift_id,))
        await db.execute("DELETE FROM gift_files WHERE gift_id = ?", (gift_id,))
        await db.execute("DELETE FROM claims WHERE gift_id = ?", (gift_id,))
        await db.commit()


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT g.gift_id, COUNT(c.user_id)
            FROM gifts g
            LEFT JOIN claims c ON g.gift_id = c.gift_id
            GROUP BY g.gift_id
            ORDER BY g.gift_id
        """)
        per_gift = await cur.fetchall()
        cur2 = await db.execute("SELECT COUNT(DISTINCT user_id) FROM claims")
        total_users = (await cur2.fetchone())[0]
        return per_gift, total_users


async def set_gift_followup(gift_id: int, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE gifts SET followup_file_id = ? WHERE gift_id = ?", (file_id, gift_id))
        await db.commit()


async def get_gift_followup(gift_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT followup_file_id FROM gifts WHERE gift_id = ?", (gift_id,))
        row = await cur.fetchone()
        return row[0] if row else None


# ---------- Yordamchi funksiyalar ----------

async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramBadRequest:
        return False


async def show_welcome(chat_id: int):
    await bot.send_message(
        chat_id,
        "Salom! 👋 Botga xush kelibsiz.\n\n"
        "Sovg'alarni olish uchun tegishli maxsus havoladan (masalan Instagram'dagi post yoki bio'dagi link) foydalaning."
    )


async def schedule_followup(chat_id: int, gift_id: int):
    """Belgilangan vaqt o'tgach, shu sovg'aga tegishli dumaloq videoni (agar qo'shilgan bo'lsa) yuboradi."""
    await asyncio.sleep(FOLLOWUP_DELAY_SECONDS)
    file_id = await get_gift_followup(gift_id)
    if file_id:
        try:
            await bot.send_video_note(chat_id, file_id)
        except TelegramBadRequest:
            pass


async def send_gift(chat_id: int, gift_id: int, user_id: int, full_name: str):
    if not await gift_exists(gift_id):
        await bot.send_message(chat_id, "Bu sovg'a topilmadi, qayta urinib ko'ring.")
        return
    files = await get_gift_files(gift_id)
    if not files:
        await bot.send_message(chat_id, "🎁 Sovg'angiz\n\n(Bu sovg'aga hali fayl biriktirilmagan)")
    else:
        for file_id, file_type, caption in files:
            if file_type == "video":
                await bot.send_video(chat_id, file_id, caption=caption)
            elif file_type == "document":
                await bot.send_document(chat_id, file_id, caption=caption)
            elif file_type == "photo":
                await bot.send_photo(chat_id, file_id, caption=caption)
    is_new = await mark_claim(user_id, gift_id, full_name)
    if is_new:
        # Faqat ilk marta sovg'a olganda, shu sovg'aga tegishli dumaloq video rejalashtiriladi
        asyncio.create_task(schedule_followup(chat_id, gift_id))


async def deliver_target(chat_id: int, user_id: int, full_name: str, target: str):
    """target 'gift_<id>' bo'lsa o'sha sovg'ani to'g'ridan-to'g'ri, aks holda oddiy salomlashuv xabarini yuboradi."""
    if target.startswith("gift_"):
        try:
            gift_id = int(target.split("_", 1)[1])
        except ValueError:
            gift_id = None
        if gift_id is not None and await gift_exists(gift_id):
            await send_gift(chat_id, gift_id, user_id, full_name)
            return
    await show_welcome(chat_id)


# ---------- Foydalanuvchi oqimi ----------

@dp.message(CommandStart(deep_link=True))
async def start_with_payload(message: Message, command: CommandObject):
    target = command.args or "menu"
    if await is_subscribed(message.from_user.id):
        await deliver_target(message.chat.id, message.from_user.id, message.from_user.full_name, target)
        return
    await message.answer(
        "Assalomu alaykum 🙈 Afsuski, siz hali kanalga obuna bo'lmagansiz, shu sababli "
        "va'da qilingan videoni (yoki PDF-ni) sizga yubora olmayapman 😔 Iltimos, avval "
        "kanalga obuna bo'ling, so'ngra \"✅ Obuna bo'ldim\" tugmasini bosing — sovg'angiz darrov yetib boradi 🎁",
        reply_markup=subscribe_keyboard(target)
    )


@dp.message(CommandStart())
async def start_handler(message: Message):
    if await is_subscribed(message.from_user.id):
        await show_welcome(message.chat.id)
        return
    await message.answer(
        "Assalomu alaykum 🙈 Afsuski, siz hali kanalga obuna bo'lmagansiz, shu sababli "
        "va'da qilingan videoni (yoki PDF-ni) sizga yubora olmayapman 😔 Iltimos, avval "
        "kanalga obuna bo'ling, so'ngra \"✅ Obuna bo'ldim\" tugmasini bosing — sovg'angiz darrov yetib boradi 🎁",
        reply_markup=subscribe_keyboard("menu")
    )


@dp.callback_query(F.data.startswith("checksub:"))
async def check_sub_handler(callback: CallbackQuery):
    target = callback.data.split(":", 1)[1]
    if await is_subscribed(callback.from_user.id):
        await callback.message.delete()
        await deliver_target(callback.message.chat.id, callback.from_user.id, callback.from_user.full_name, target)
        await callback.answer()
    else:
        await callback.answer(
            "Siz hali kanalga obuna bo'lmadingiz ❌ Obuna bo'lib, qayta urinib ko'ring.",
            show_alert=True
        )


@dp.callback_query(F.data.startswith("gift_"))
async def gift_chosen_handler(callback: CallbackQuery):
    gift_id = int(callback.data.split("_", 1)[1])
    await send_gift(callback.message.chat.id, gift_id, callback.from_user.id, callback.from_user.full_name)
    await callback.answer()


# ---------- Admin oqimi: sovg'a qo'shish ----------

@dp.message(Command("add_gift"))
async def add_gift_start(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.update_data(files=[])
    await message.answer(
        "Sovg'aga tegishli video, rasm yoki faylлarni birma-bir yuboring "
        "(bir nechtasini yuborsangiz bo'ladi). Hammasini yuborib bo'lgach, /done buyrug'ini bosing.\n"
        "Bekor qilish uchun /cancel bosing."
    )
    await state.set_state(AdminStates.waiting_for_files)


async def _collect_file(message: Message, state: FSMContext, file_id: str, file_type: str):
    data = await state.get_data()
    files = data.get("files", [])
    files.append({"file_id": file_id, "file_type": file_type, "caption": message.caption})
    await state.update_data(files=files)
    await message.answer(f"✅ Qabul qilindi ({len(files)} ta fayl). Yana yuborishingiz mumkin yoki /done bosing.")


@dp.message(AdminStates.waiting_for_files, F.video)
async def collect_video(message: Message, state: FSMContext):
    await _collect_file(message, state, message.video.file_id, "video")


@dp.message(AdminStates.waiting_for_files, F.document)
async def collect_document(message: Message, state: FSMContext):
    await _collect_file(message, state, message.document.file_id, "document")


@dp.message(AdminStates.waiting_for_files, F.photo)
async def collect_photo(message: Message, state: FSMContext):
    await _collect_file(message, state, message.photo[-1].file_id, "photo")


@dp.message(AdminStates.waiting_for_files, Command("done"))
async def finish_add_gift(message: Message, state: FSMContext):
    data = await state.get_data()
    files = data.get("files", [])
    if not files:
        await message.answer("Hali birorta ham fayl yubormadingiz. Kamida bitta fayl yuboring yoki /cancel bosing.")
        return
    gift_id = await create_gift()
    for position, f in enumerate(files):
        await add_file_to_gift(gift_id, f["file_id"], f["file_type"], f["caption"], position)
    link = f"https://t.me/{BOT_USERNAME}?start=gift_{gift_id}"
    await message.answer(
        f"✅ Sovg'a #{gift_id} — {len(files)} ta fayl bilan qo'shildi.\n\n"
        f"Ushbu sovg'a uchun shaxsiy havola (uni Instagram va h.k. joylarga qo'ysangiz bo'ladi):\n{link}"
    )
    await state.update_data(followup_gift_id=gift_id)
    await state.set_state(AdminStates.waiting_for_followup_video)
    await message.answer(
        f"Endi shu sovg'a (#{gift_id}) uchun dumaloq video xabarni yuboring — u foydalanuvchiga "
        f"sovg'ani olgandan {FOLLOWUP_DELAY_SECONDS // 60} daqiqadan keyin shaxsan yuborilgandek avtomatik yetkaziladi.\n"
        f"Video qo'shmoqchi bo'lmasangiz /skip, bekor qilish uchun /cancel bosing."
    )


@dp.message(AdminStates.waiting_for_followup_video, Command("skip"))
async def skip_followup(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bo'pti, bu sovg'aga dumaloq video qo'shilmadi. Xohlasangiz keyinroq /set_followup_video orqali qo'shishingiz mumkin.")


@dp.message(AdminStates.waiting_for_files, Command("cancel"))
async def cancel_add_gift(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.")


# ---------- Admin oqimi: har bir sovg'aga alohida dumaloq video ----------

@dp.message(Command("set_followup_video"))
async def set_followup_start(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    gift_ids = await get_all_gifts()
    if not gift_ids:
        await message.answer("Hozircha sovg'a yo'q. Avval /add_gift orqali sovg'a qo'shing.")
        return
    buttons = [[InlineKeyboardButton(text=f"🎥 Sovg'a #{gift_id}", callback_data=f"setfup_{gift_id}")] for gift_id in gift_ids]
    await message.answer(
        "Qaysi sovg'a uchun dumaloq video sozlamoqchisiz?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@dp.callback_query(F.data.startswith("setfup_"))
async def set_followup_choose_gift(callback: CallbackQuery, state: FSMContext):
    gift_id = int(callback.data.split("_", 1)[1])
    await state.update_data(followup_gift_id=gift_id)
    await state.set_state(AdminStates.waiting_for_followup_video)
    await callback.message.edit_text(
        f"Endi Sovg'a #{gift_id} uchun dumaloq videoni (Telegram'ning video note formatida) yuboring.\n"
        f"U foydalanuvchiga shu sovg'a olingandan {FOLLOWUP_DELAY_SECONDS // 60} daqiqadan keyin avtomatik yuboriladi."
    )
    await callback.answer()


@dp.message(AdminStates.waiting_for_followup_video, F.video_note)
async def set_followup_save(message: Message, state: FSMContext):
    data = await state.get_data()
    gift_id = data.get("followup_gift_id")
    await set_gift_followup(gift_id, message.video_note.file_id)
    await message.answer(f"✅ Sovg'a #{gift_id} uchun dumaloq video saqlandi.")
    await state.clear()


@dp.message(AdminStates.waiting_for_followup_video, Command("cancel"))
async def cancel_followup(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.")


# ---------- Admin oqimi: sovg'ani o'chirish ----------

@dp.message(Command("delete_gift"))
async def delete_gift_start(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    gift_ids = await get_all_gifts()
    if not gift_ids:
        await message.answer("Hozircha o'chiriladigan sovg'a yo'q.")
        return
    buttons = [[InlineKeyboardButton(text=f"❌ Sovg'a #{gift_id}", callback_data=f"delgift_{gift_id}")] for gift_id in gift_ids]
    await message.answer(
        "O'chirmoqchi bo'lgan sovg'ani tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@dp.callback_query(F.data.startswith("delgift_"))
async def delete_gift_confirm(callback: CallbackQuery):
    gift_id = int(callback.data.split("_", 1)[1])
    if not await gift_exists(gift_id):
        await callback.answer("Bu sovg'a allaqachon o'chirilgan.", show_alert=True)
        return
    await callback.message.edit_text(
        f"Sovg'a #{gift_id} ni rostdan ham o'chirmoqchimisiz?\n"
        "Bu bilan uning statistikasi va dumaloq videosi ham o'chib ketadi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Ha, o'chirilsin", callback_data=f"delyes_{gift_id}"),
            InlineKeyboardButton(text="🚫 Bekor qilish", callback_data="delno")
        ]])
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("delyes_"))
async def delete_gift_do(callback: CallbackQuery):
    gift_id = int(callback.data.split("_", 1)[1])
    await delete_gift_from_db(gift_id)
    await callback.message.edit_text(f"🗑 Sovg'a #{gift_id} o'chirildi.")
    await callback.answer()


@dp.callback_query(F.data == "delno")
async def delete_gift_cancel(callback: CallbackQuery):
    await callback.message.edit_text("Bekor qilindi.")
    await callback.answer()


# ---------- Admin oqimi: ro'yxat va statistika ----------

@dp.message(Command("gifts"))
async def list_gifts_handler(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    gift_ids = await get_all_gifts()
    if not gift_ids:
        await message.answer("Hozircha hech qanday sovg'a qo'shilmagan.")
        return
    lines = []
    for gift_id in gift_ids:
        files = await get_gift_files(gift_id)
        has_followup = await get_gift_followup(gift_id)
        link = f"https://t.me/{BOT_USERNAME}?start=gift_{gift_id}"
        followup_note = "✅ dumaloq video bor" if has_followup else "➖ dumaloq video yo'q"
        lines.append(f"Sovg'a #{gift_id} ({len(files)} ta fayl, {followup_note})\n{link}")
    await message.answer("🎁 Mavjud sovg'alar:\n\n" + "\n\n".join(lines))


@dp.message(Command("stats"))
async def stats_handler(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    per_gift, total_users = await get_stats()
    if not per_gift:
        await message.answer("Hozircha hech qanday sovg'a qo'shilmagan.")
        return
    lines = [f"• Sovg'a #{gift_id}: {count} kishi" for gift_id, count in per_gift]
    text = "📊 Statistika:\n\n" + "\n".join(lines) + f"\n\nJami (takrorsiz) foydalanuvchilar: {total_users}"
    await message.answer(text)


async def setup_commands():
    await bot.set_my_commands(
        [BotCommand(command="start", description="Botni ishga tushirish")],
        scope=BotCommandScopeDefault()
    )
    admin_commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="add_gift", description="Yangi sovg'a qo'shish"),
        BotCommand(command="delete_gift", description="Sovg'ani o'chirish"),
        BotCommand(command="set_followup_video", description="Sovg'aga dumaloq video sozlash"),
        BotCommand(command="gifts", description="Sovg'alar ro'yxati va havolalari"),
        BotCommand(command="stats", description="Statistikani ko'rish"),
    ]
    for admin_id in ADMIN_IDS:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except TelegramBadRequest:
            pass


async def main():
    global BOT_USERNAME
    me = await bot.get_me()
    BOT_USERNAME = me.username
    await init_db()
    await setup_commands()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())