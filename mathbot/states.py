from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    waiting_role = State()
    waiting_last_name = State()
    waiting_first_name = State()
    waiting_course = State()
    waiting_region = State()
    waiting_district = State()
    waiting_phone = State()


class ProfileEdit(StatesGroup):
    """Foydalanuvchi profilidagi ma'lumotlarni tahrirlayotganda ishlatiladigan holatlar"""
    waiting_last_name = State()
    waiting_first_name = State()
    waiting_region = State()
    waiting_district = State()
    waiting_phone = State()


class Attendance(StatesGroup):
    """Admin yangi davomat sessiyasini boshlashda ishlatiladigan holatlar"""
    waiting_warning_minutes = State()
    waiting_report_minutes = State()


class AttendanceCode(StatesGroup):
    """O'quvchi davomat kodini kiritayotganda ishlatiladigan holat"""
    waiting_code = State()


class TestCode(StatesGroup):
    """O'quvchi test kodini kiritayotganda ishlatiladigan holat"""
    waiting_code = State()


class APlusCode(StatesGroup):
    """O'quvchi A+ (yozma javobli) test kodini kiritayotganda ishlatiladigan holat"""
    waiting_code = State()


class Broadcast(StatesGroup):
    """Admin barcha foydalanuvchilarga xabar tayyorlayotganda (matn/rasm/PDF
    to'plab, keyin bittalikda yuborishda) ishlatiladigan holat"""
    composing = State()


class SpecialTaskAdmin(StatesGroup):
    """Admin yangi maxsus topshiriq nomini kiritayotganda ishlatiladigan holat"""
    waiting_name = State()


class Boss(StatesGroup):
    """Boss admin qo'shish/o'chirish va o'quvchi ballini o'zgartirishda ishlatiladigan holatlar"""
    waiting_add_admin_id = State()
    waiting_score_id = State()
    waiting_score_delta = State()
    waiting_score_reason = State()
