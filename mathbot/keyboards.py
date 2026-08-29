from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import COURSES
from locations import REGIONS

# Barcha doimiy menyu tugmalarining matni. FSM holatida (masalan "son kiriting"
# kutilayotganda) matnli xabarlarni qabul qiladigan handlerlar bu matnlarni
# chetlab o'tishi kerak - aks holda admin/foydalanuvchi menyu tugmasini bossa,
# u "noto'g'ri qiymat" xatoligi sifatida qabul qilinib, navigatsiya buziladi.
ADMIN_MENU_TEXTS = {
    "📊 Statistika",
    "👥 Foydalanuvchilar",
    "🗑 Foydalanuvchini o'chirish",
    "👮 Adminlar",
    "📅 Davomat",
    "📝 Javoblarni yozish",
    "🗂 Mening testlarim",
    "➕ A+ yaratish",
    "🗂 Mening A+ testlarim",
    "📋 Maxsus topshiriq yaratish",
    "📢 Xabar yuborish",
    "⚙️ Sozlamalar",
    "ℹ️ Yordam",
}

BOSS_MENU_TEXTS = {
    "➕ Admin qo'shish",
    "➖ Adminni olib tashlash",
    "⚖️ Ball o'zgartirish",
    "🔗 Admin havolasini o'zgartirish",
    "📡 Kanalni o'zgartirish",
}

MAIN_MENU_TEXTS = {
    "📝 Test yuborish",
    "➕ A+ ishlash",
    "📋 Maxsus topshiriq yuborish",
    "📅 Davomat",
    "👤 Profil",
    "🏆 Reyting",
    "📊 Natijalarim",
    "📩 Adminga xabar",
}

NAV_BUTTON_TEXTS = ADMIN_MENU_TEXTS | MAIN_MENU_TEXTS | BOSS_MENU_TEXTS


def role_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎓 O'quvchi", callback_data="role:student"),
                InlineKeyboardButton(text="O'qituvchi", callback_data="role:teacher"),
            ]
        ]
    )


def courses_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=data["name"], callback_data=f"course:{key}")]
        for key, data in COURSES.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def regions_keyboard() -> InlineKeyboardMarkup:
    names = list(REGIONS.keys())
    buttons = []
    for i in range(0, len(names), 2):
        row = [InlineKeyboardButton(text=names[i], callback_data=f"region:{names[i]}")]
        if i + 1 < len(names):
            row.append(
                InlineKeyboardButton(text=names[i + 1], callback_data=f"region:{names[i + 1]}")
            )
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def districts_keyboard(region: str) -> InlineKeyboardMarkup:
    districts = REGIONS[region]
    buttons = []
    for i in range(0, len(districts), 2):
        row = [InlineKeyboardButton(text=districts[i], callback_data=f"district:{districts[i]}")]
        if i + 1 < len(districts):
            row.append(
                InlineKeyboardButton(
                    text=districts[i + 1], callback_data=f"district:{districts[i + 1]}"
                )
            )
        buttons.append(row)
    buttons.append(
        [InlineKeyboardButton(text="⬅️ Orqaga (viloyat)", callback_data="back_to_region")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def phone_request_keyboard():
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def admin_menu_keyboard():
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika"),
                KeyboardButton(text="👥 Foydalanuvchilar"),
            ],
            [
                KeyboardButton(text="🗑 Foydalanuvchini o'chirish"),
                KeyboardButton(text="👮 Adminlar"),
            ],
            [
                KeyboardButton(text="📅 Davomat"),
                KeyboardButton(text="📝 Javoblarni yozish"),
            ],
            [
                KeyboardButton(text="🗂 Mening testlarim"),
                KeyboardButton(text="ℹ️ Yordam"),
            ],
            [
                KeyboardButton(text="➕ A+ yaratish"),
                KeyboardButton(text="🗂 Mening A+ testlarim"),
            ],
            [
                KeyboardButton(text="📋 Maxsus topshiriq yaratish"),
                KeyboardButton(text="📢 Xabar yuborish"),
            ],
            [
                KeyboardButton(text="⚙️ Sozlamalar"),
            ],
        ],
        resize_keyboard=True,
    )


def boss_menu_keyboard():
    """Faqat Boss'ning shaxsiy chatida ko'rsatiladigan menyu - admin tugmalari
    + Boss'ga xos qo'shimcha tugmalar (boshqa hech kim buni ko'rmaydi)."""
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    base = admin_menu_keyboard()
    return ReplyKeyboardMarkup(
        keyboard=base.keyboard + [
            [
                KeyboardButton(text="➕ Admin qo'shish"),
                KeyboardButton(text="➖ Adminni olib tashlash"),
            ],
            [
                KeyboardButton(text="⚖️ Ball o'zgartirish"),
            ],
            [
                KeyboardButton(text="🔗 Admin havolasini o'zgartirish"),
            ],
            [
                KeyboardButton(text="📡 Kanalni o'zgartirish"),
            ],
        ],
        resize_keyboard=True,
    )


def special_task_collecting_keyboard():
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Maxsus topshiriqni tugatish")]],
        resize_keyboard=True,
    )


def main_menu_keyboard():
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📝 Test yuborish"),
                KeyboardButton(text="➕ A+ ishlash"),
            ],
            [
                KeyboardButton(text="📋 Maxsus topshiriq yuborish"),
                KeyboardButton(text="📅 Davomat"),
            ],
            [
                KeyboardButton(text="👤 Profil"),
                KeyboardButton(text="🏆 Reyting"),
            ],
            [
                KeyboardButton(text="📊 Natijalarim"),
            ],
            [
                KeyboardButton(text="📩 Adminga xabar"),
            ],
        ],
        resize_keyboard=True,
    )
