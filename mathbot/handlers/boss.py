from aiogram import Router, F
from aiogram.filters import or_f
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated

import database as db
from config import ADMIN_IDS, BOSS_IDS, DEFAULT_ADMIN_CONTACT_URL, REPORT_CHANNEL, is_boss
from states import Boss
from keyboards import NAV_BUTTON_TEXTS

router = Router()
# Shaxsiy chat + guruh ichida yoziladigan buyruqlar: /hisobot_shu_yerga, /obuna_shu_yerga
router.message.filter(or_f(F.chat.type == "private", Command("hisobot_shu_yerga", "obuna_shu_yerga")))
router.callback_query.filter(F.message.chat.type == "private")

# Bu buyruq/tugmalar hech qayerda ADMIN_MENU_TEXTS/Bot Menu orqali boshqa
# hech kimga ko'rinmaydi - faqat BOSS_IDS'ning shaxsiy chatiga o'rnatiladi
# (handlers/admin.py: set_boss_menu, keyboards.py: boss_menu_keyboard).
# Boss bo'lmagan foydalanuvchi shu buyruqlarni yozsa ham bot butunlay jim
# qoladi - hech qanday "ruxsat yo'q" javobi yo'q, aks holda mavjudligi bilinib qoladi.


@router.message(
    StateFilter(
        Boss.waiting_add_admin_id,
        Boss.waiting_score_id,
        Boss.waiting_score_delta,
        Boss.waiting_score_reason,
        Boss.waiting_admin_contact_url,
        Boss.waiting_report_channel,
    ),
    Command("cancel"),
)
async def boss_cancel(message: Message, state: FSMContext):
    if not is_boss(message.from_user.id):
        return
    await state.clear()
    await message.answer("Bekor qilindi.")


async def notify_boss(bot, text: str, exclude: int | None = None):
    for boss_id in BOSS_IDS:
        if boss_id == exclude:
            continue
        try:
            await bot.send_message(boss_id, text, parse_mode="HTML")
        except Exception:
            pass


async def _do_add_admin(bot, target_id: int, actor_id: int):
    await db.add_admin(target_id)
    ADMIN_IDS.append(target_id)

    from handlers.admin import set_admin_menu_for
    await set_admin_menu_for(bot, target_id)

    await notify_boss(
        bot,
        f"👮 Yangi admin qo'shildi: <code>{target_id}</code>\n(qo'shdi: <code>{actor_id}</code>)",
        exclude=actor_id,
    )


async def _do_remove_admin(bot, target_id: int, actor_id: int) -> bool:
    removed = await db.remove_admin(target_id)
    if target_id in ADMIN_IDS:
        ADMIN_IDS.remove(target_id)

    if removed:
        from handlers.admin import clear_admin_menu_for
        await clear_admin_menu_for(bot, target_id)
        await notify_boss(
            bot,
            f"👮 Admin olib tashlandi: <code>{target_id}</code>\n(olib tashladi: <code>{actor_id}</code>)",
            exclude=actor_id,
        )
    return removed


# ---------- Admin qo'shish ----------

@router.message(F.text == "➕ Admin qo'shish")
async def boss_add_button(message: Message, state: FSMContext):
    if not is_boss(message.from_user.id):
        return
    await state.set_state(Boss.waiting_add_admin_id)
    await message.answer(
        "Yangi admin qilib tayinlamoqchi bo'lgan foydalanuvchining Telegram ID sini yuboring "
        "(bekor qilish uchun /cancel):"
    )


@router.message(Boss.waiting_add_admin_id, F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def boss_add_button_id(message: Message, state: FSMContext, bot):
    if not is_boss(message.from_user.id):
        return

    text = message.text.strip()
    if not text.isdigit():
        await message.answer("ID faqat raqamlardan iborat bo'lishi kerak. Qayta kiriting:")
        return

    target_id = int(text)
    await state.clear()

    if target_id in BOSS_IDS:
        await message.answer("Bu ID allaqachon eng yuqori darajaga ega.")
        return
    if target_id in ADMIN_IDS:
        await message.answer("Bu foydalanuvchi allaqachon admin.")
        return

    await _do_add_admin(bot, target_id, message.from_user.id)
    await message.answer(f"✅ <code>{target_id}</code> admin qilib qo'shildi.", parse_mode="HTML")


@router.message(Command("boss_add"))
async def boss_add_command(message: Message, command: CommandObject, bot):
    if not is_boss(message.from_user.id):
        return

    args = (command.args or "").strip()
    if not args.isdigit():
        await message.answer("Foydalanish: <code>/boss_add 123456789</code>", parse_mode="HTML")
        return

    target_id = int(args)
    if target_id in BOSS_IDS:
        await message.answer("Bu ID allaqachon eng yuqori darajaga ega.")
        return
    if target_id in ADMIN_IDS:
        await message.answer("Bu foydalanuvchi allaqachon admin.")
        return

    await _do_add_admin(bot, target_id, message.from_user.id)
    await message.answer(f"✅ <code>{target_id}</code> admin qilib qo'shildi.", parse_mode="HTML")


# ---------- Adminni olib tashlash ----------

@router.message(F.text == "➖ Adminni olib tashlash")
async def boss_remove_button(message: Message, bot):
    if not is_boss(message.from_user.id):
        return

    if not ADMIN_IDS:
        await message.answer("Hozircha hech qanday admin yo'q.")
        return

    buttons = []
    for admin_id in ADMIN_IDS:
        try:
            chat = await bot.get_chat(admin_id)
            label = chat.full_name or str(admin_id)
        except Exception:
            label = str(admin_id)
        buttons.append([InlineKeyboardButton(text=f"❌ {label} ({admin_id})", callback_data=f"boss_rm:{admin_id}")])

    await message.answer(
        "Qaysi adminni olib tashlamoqchisiz?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("boss_rm:"))
async def boss_remove_confirm(callback: CallbackQuery, bot):
    if not is_boss(callback.from_user.id):
        await callback.answer()
        return

    target_id = int(callback.data.split(":", 1)[1])
    removed = await _do_remove_admin(bot, target_id, callback.from_user.id)

    if removed:
        await callback.message.edit_text(f"🗑 <code>{target_id}</code> adminlikdan olindi.", parse_mode="HTML")
    else:
        await callback.message.edit_text("Bu ID admin emas edi.")
    await callback.answer()


@router.message(Command("boss_remove"))
async def boss_remove_command(message: Message, command: CommandObject, bot):
    if not is_boss(message.from_user.id):
        return

    args = (command.args or "").strip()
    if not args.isdigit():
        await message.answer("Foydalanish: <code>/boss_remove 123456789</code>", parse_mode="HTML")
        return

    target_id = int(args)
    removed = await _do_remove_admin(bot, target_id, message.from_user.id)

    if removed:
        await message.answer(f"🗑 <code>{target_id}</code> adminlikdan olindi.", parse_mode="HTML")
    else:
        await message.answer("Bu ID admin emas edi.")


# ---------- O'quvchi ballini o'zgartirish ----------

@router.message(F.text == "⚖️ Ball o'zgartirish")
async def boss_score_button(message: Message, state: FSMContext):
    if not is_boss(message.from_user.id):
        return
    await state.set_state(Boss.waiting_score_id)
    await message.answer("Ballini o'zgartirmoqchi bo'lgan o'quvchining Telegram ID sini yuboring:")


@router.message(Boss.waiting_score_id, F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def boss_score_id(message: Message, state: FSMContext):
    if not is_boss(message.from_user.id):
        return

    text = message.text.strip()
    if not text.isdigit():
        await message.answer("ID faqat raqamlardan iborat bo'lishi kerak. Qayta kiriting:")
        return

    target_id = int(text)
    user = await db.get_user(target_id)
    if not user:
        await message.answer("Bunday ID li foydalanuvchi topilmadi. Qayta kiriting yoki /cancel bosing.")
        return

    coins = await db.get_user_coins(target_id)
    await state.update_data(target_id=target_id)
    await state.set_state(Boss.waiting_score_delta)
    await message.answer(
        f"👤 <b>{user['full_name'] or target_id}</b> — joriy jami ball: <b>{coins['total']}</b>\n\n"
        "Necha ball qo'shish yoki ayirish kerak? (masalan: <code>50</code> yoki <code>-30</code>)",
        parse_mode="HTML",
    )


@router.message(Boss.waiting_score_delta, F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def boss_score_delta(message: Message, state: FSMContext):
    if not is_boss(message.from_user.id):
        return

    try:
        delta = int(message.text.strip())
    except ValueError:
        await message.answer("Butun son kiriting, masalan 50 yoki -30.")
        return

    await state.update_data(delta=delta)
    await state.set_state(Boss.waiting_score_reason)
    await message.answer("Sababini yozing (yoki o'tkazib yuborish uchun /skip bosing):")


@router.message(Boss.waiting_score_reason, Command("skip"))
async def boss_score_skip_reason(message: Message, state: FSMContext):
    if not is_boss(message.from_user.id):
        return
    await _finish_score_adjustment(message, state, reason=None)


@router.message(Boss.waiting_score_reason, F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def boss_score_reason(message: Message, state: FSMContext):
    if not is_boss(message.from_user.id):
        return
    await _finish_score_adjustment(message, state, reason=message.text.strip())


async def _finish_score_adjustment(message: Message, state: FSMContext, reason: str | None):
    data = await state.get_data()
    target_id = data["target_id"]
    delta = data["delta"]
    await state.clear()

    await db.adjust_user_score(target_id, delta, reason)
    coins = await db.get_user_coins(target_id)
    user = await db.get_user(target_id)

    sign = "+" if delta >= 0 else ""
    await message.answer(
        f"✅ <b>{user['full_name'] or target_id}</b> uchun ball {sign}{delta} o'zgartirildi.\n"
        f"Joriy jami ball: <b>{coins['total']}</b>",
        parse_mode="HTML",
    )


# ---------- "Adminga xabar" tugmasidagi havolani o'zgartirish ----------

@router.message(F.text == "🔗 Admin havolasini o'zgartirish")
async def boss_admin_contact_button(message: Message, state: FSMContext):
    if not is_boss(message.from_user.id):
        return

    current = await db.get_setting("admin_contact_url", DEFAULT_ADMIN_CONTACT_URL)
    await state.set_state(Boss.waiting_admin_contact_url)
    await message.answer(
        f"Hozirgi havola: {current}\n\n"
        "O'quvchilarga \"📩 Adminga xabar\" tugmasi bosilganda ko'rinadigan "
        "yangi havolani yuboring (masalan: <code>https://t.me/username</code>).\n"
        "Bekor qilish uchun /cancel bosing.",
        parse_mode="HTML",
    )


@router.message(Boss.waiting_admin_contact_url, F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def boss_admin_contact_save(message: Message, state: FSMContext):
    if not is_boss(message.from_user.id):
        return

    url = message.text.strip()
    if not (url.startswith("https://t.me/") or url.startswith("https://") or url.startswith("http://")):
        await message.answer(
            "Havola https:// bilan boshlanishi kerak (masalan https://t.me/username). Qayta kiriting:"
        )
        return

    await state.clear()
    await db.set_setting("admin_contact_url", url)
    await message.answer(f"✅ Admin havolasi yangilandi:\n{url}")


# ---------- Xabar/hisobot yuboriladigan kanalni o'zgartirish ----------

@router.message(F.text == "📡 Kanalni o'zgartirish")
async def boss_report_channel_button(message: Message, state: FSMContext):
    if not is_boss(message.from_user.id):
        return

    current = await db.get_setting("report_channel_id", REPORT_CHANNEL)
    await state.set_state(Boss.waiting_report_channel)
    await message.answer(
        f"Hozirgi kanal: <code>{current}</code>\n\n"
        "Haftalik hisobot va \"⚙️ Sozlamalar\"da belgilangan xabarlar endi qaysi "
        "kanalga yuborilishi kerak? Kanal username'ini (masalan "
        "<code>@turbomathka</code>) yoki kanal ID'sini yuboring.\n"
        "Bot o'sha kanalda admin bo'lishi shart. Bekor qilish uchun /cancel.",
        parse_mode="HTML",
    )


@router.message(Boss.waiting_report_channel, F.text, ~F.text.in_(NAV_BUTTON_TEXTS))
async def boss_report_channel_save(message: Message, state: FSMContext):
    if not is_boss(message.from_user.id):
        return

    value = message.text.strip()
    if "t.me/+" in value or "t.me/joinchat" in value:
        await message.answer(
            "Taklif havolasi (t.me/+...) orqali bot kanalni topa olmaydi.\n\n"
            "Buning o'rniga: botni o'sha guruh/kanalga <b>admin</b> qilib qo'shing va "
            "o'sha guruhning o'zida <code>/hisobot_shu_yerga</code> buyrug'ini yuboring - "
            "bot guruh ID'sini o'zi aniqlab, saqlaydi.",
            parse_mode="HTML",
        )
        return
    if not (value.startswith("@") or value.startswith("-") or value.lstrip("-").isdigit()):
        await message.answer(
            "Kanal username'i @ bilan boshlanishi yoki kanal ID (masalan -1001234567890) "
            "bo'lishi kerak. Qayta kiriting:"
        )
        return

    await state.clear()
    await db.set_setting("report_channel_id", value)
    await message.answer(f"✅ Kanal yangilandi:\n<code>{value}</code>", parse_mode="HTML")


# ---------- Hisobot kanalini guruhning O'ZIDAN belgilash ----------
# Yopiq guruh/kanalning (t.me/+... havolali) @username'i bo'lmaydi. Boss o'sha
# guruhning ichida /hisobot_shu_yerga deb yozadi - bot chat ID'sini o'zi saqlaydi.

async def _save_report_chat(message: Message):
    chat_id = str(message.chat.id)
    await db.set_setting("report_channel_id", chat_id)
    try:
        await message.answer(
            "✅ Haftalik hisobot va rejalashtirilgan xabarlar endi <b>shu guruhga</b> yuboriladi.\n"
            f"Guruh ID: <code>{chat_id}</code>",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(Command("hisobot_shu_yerga"), F.chat.type.in_({"group", "supergroup"}))
async def boss_report_here_group(message: Message):
    if not message.from_user or not is_boss(message.from_user.id):
        return
    await _save_report_chat(message)


@router.channel_post(Command("hisobot_shu_yerga"))
async def boss_report_here_channel(message: Message):
    # Kanalga faqat uning adminlari post yoza oladi.
    await _save_report_chat(message)


# ---------- Obuna tekshiriladigan kanalni guruhning O'ZIDAN belgilash ----------
# Boss Turbo guruhining ichida /obuna_shu_yerga deb yozadi - endi ro'yxatdan
# o'tish va davomiy tekshiruv shu guruh a'zoligi bo'yicha bo'ladi.

async def _save_subscription_chat(message: Message):
    from config import COURSES
    chat_id = str(message.chat.id)
    for course_key in COURSES:
        await db.set_setting(f"subscription_channel_{course_key}", chat_id)
    names = ", ".join(c["name"] for c in COURSES.values())
    try:
        await message.answer(
            f"✅ Endi <b>{names}</b> kursiga faqat <b>shu guruh a'zolari</b> ro'yxatdan o'ta oladi.\n"
            f"Guruh ID: <code>{chat_id}</code>\n\n"
            "Bot shu guruhda admin bo'lishi shart.",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(Command("obuna_shu_yerga"), F.chat.type.in_({"group", "supergroup"}))
async def boss_subscription_here_group(message: Message):
    if not message.from_user or not is_boss(message.from_user.id):
        return
    await _save_subscription_chat(message)


@router.channel_post(Command("obuna_shu_yerga"))
async def boss_subscription_here_channel(message: Message):
    await _save_subscription_chat(message)


# ---------- Obuna guruhini GURUHGA HECH NARSA YOZMASDAN belgilash ----------
# Yopiq guruhning taklif havolasidan (t.me/+...) bot guruhni topa olmaydi -
# unga guruhning raqamli ID'si kerak. ID'ni guruhga hech narsa yozmasdan
# olishning ikki yo'li bor:
#   1) Boss botni guruhga admin qilib qo'shadi (yoki allaqachon admin bo'lsa,
#      uning huquqlaridan birini o'zgartirib saqlaydi). Telegram botga shu
#      haqida xabar beradi va bot guruh ID'sini o'zi saqlaydi.
#   2) Kanal bo'lsa: Boss kanaldagi istalgan postni botga forward qiladi.
# Ikkala holatda ham guruhga/kanalga hech qanday xabar yuborilmaydi -
# tasdiq faqat Boss'ning shaxsiy chatiga keladi.

async def _set_subscription_chat_silent(bot, chat, boss_id: int):
    from config import COURSES
    chat_id = str(chat.id)
    for course_key in COURSES:
        await db.set_setting(f"subscription_channel_{course_key}", chat_id)
    # Haftalik hisobot ham shu guruhga yuborilsin
    await db.set_setting("report_channel_id", chat_id)
    names = ", ".join(c["name"] for c in COURSES.values())
    try:
        member = await bot.get_chat_member(chat.id, boss_id)
        check = f"✅ Tekshiruv ishlayapti (sizning holatingiz: {member.status})."
    except Exception as e:
        check = f"⚠️ Bot a'zolarni tekshira olmayapti: {e}\nBotni shu guruhda admin qiling."
    try:
        await bot.send_message(
            boss_id,
            f"🔒 <b>{names}</b> kursiga endi faqat <b>{chat.title or chat_id}</b> a'zolari "
            f"ro'yxatdan o'ta oladi.\n📊 Haftalik hisobot ham shu guruhga yuboriladi.\n"
            f"Guruh ID: <code>{chat_id}</code>\n\n{check}",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.my_chat_member()
async def boss_bot_added_to_chat(event: ChatMemberUpdated):
    if event.chat.type not in ("group", "supergroup", "channel"):
        return
    if event.new_chat_member.status not in ("administrator", "member"):
        return
    if not event.from_user or not is_boss(event.from_user.id):
        return
    await _set_subscription_chat_silent(event.bot, event.chat, event.from_user.id)


@router.message(StateFilter(None), F.forward_origin.type == "channel")
async def boss_forward_from_channel(message: Message):
    if not is_boss(message.from_user.id):
        return
    await _set_subscription_chat_silent(message.bot, message.forward_origin.chat, message.from_user.id)


# ---------- Haftalik hisobotni tekshirish: /hisobot_test ----------
# Boss shaxsiy chatda /hisobot_test yozadi - bot hisobot qayerga ketishini,
# jadval (kun/vaqt) bor-yo'qligini ko'rsatadi va hisobotni HOZIROQ yuborib ko'radi.
# Xato bo'lsa, xato matnini Boss'ga yozadi.

@router.message(Command("hisobot_test"), F.chat.type == "private")
async def boss_report_test(message: Message):
    if not is_boss(message.from_user.id):
        return
    import os
    import tempfile
    from datetime import datetime, timedelta
    from aiogram.types import FSInputFile
    from pdf_report import generate_period_report
    from timezone_utils import now_tashkent

    WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
    channel = await db.get_setting("report_channel_id", REPORT_CHANNEL)
    schedules = await db.get_report_schedules()
    active = [s for s in schedules if s["enabled"]]
    sched_text = "\n".join(
        f"• {WEEKDAYS[s['day_of_week']]} {s['time_of_day']}" for s in active
    ) or "❌ Yoqilgan jadval YO'Q - hisobot hech qachon avtomatik yuborilmaydi! (⚙️ Sozlamalar orqali kun/vaqt qo'shing)"
    last_sent = await db.get_report_last_sent_at() or "hali yuborilmagan"

    lines = [
        "📊 <b>Haftalik hisobot holati</b>",
        f"Kanal/guruh: <code>{channel}</code>",
        f"Oxirgi yuborilgan: {last_sent}",
        f"Jadval:\n{sched_text}",
        "",
    ]
    try:
        now = now_tashkent()
        since_dt = now - timedelta(days=7)
        rows = await db.get_submissions_since(since_dt.strftime("%Y-%m-%dT%H:%M:%S"))
        path = os.path.join(tempfile.gettempdir(), "hisobot_test.pdf")
        generate_period_report(path, rows, since_dt, now)
        await message.bot.send_document(channel, FSInputFile(path), caption="🧪 Sinov hisoboti (oxirgi 7 kun)")
        lines.append("✅ Sinov hisoboti kanalga muvaffaqiyatli yuborildi.")
    except Exception as e:
        import html as _h
        lines.append(f"❌ Kanalga yuborib bo'lmadi:\n<code>{_h.escape(str(e))}</code>")
        lines.append("\nKo'pincha sabab: bot o'sha guruh/kanalda admin emas yoki kanal noto'g'ri.")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("boss_score"))
async def boss_score_command(message: Message, command: CommandObject):
    if not is_boss(message.from_user.id):
        return

    parts = (command.args or "").split(maxsplit=2)
    if len(parts) < 2 or not parts[0].isdigit():
        await message.answer(
            "Foydalanish: <code>/boss_score 123456789 50</code> (kamaytirish uchun: "
            "<code>/boss_score 123456789 -30 sabab</code>)",
            parse_mode="HTML",
        )
        return

    target_id = int(parts[0])
    try:
        delta = int(parts[1])
    except ValueError:
        await message.answer("Ball miqdori butun son bo'lishi kerak, masalan 50 yoki -30.")
        return

    reason = parts[2] if len(parts) > 2 else None

    user = await db.get_user(target_id)
    if not user:
        await message.answer("Bunday ID li foydalanuvchi topilmadi.")
        return

    await db.adjust_user_score(target_id, delta, reason)
    coins = await db.get_user_coins(target_id)

    sign = "+" if delta >= 0 else ""
    await message.answer(
        f"✅ <b>{user['full_name'] or target_id}</b> uchun ball {sign}{delta} o'zgartirildi.\n"
        f"Joriy jami ball: <b>{coins['total']}</b>",
        parse_mode="HTML",
    )
