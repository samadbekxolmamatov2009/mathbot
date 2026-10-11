"""Boss va adminlar uchun "hisobot olish" tugmalari.

Avvalgi tizimda har bir davomat/test muddati tugaganda hamma adminga avtomatik
PDF kelardi. Endi hisobot kerak bo'lganda tugma bosiladi va OXIRGI olingan
hisobotdan keyin yakunlangan davomat/testlar (har kim uchun alohida belgi bilan)
jadval ko'rinishida yuboriladi. Qaysi davrni qamrab olgani database.py'dagi
get_report_batch() izohida.
"""

import logging
import os
import tempfile
from datetime import datetime, timedelta
from html import escape as _html_escape

from aiogram import F, Router
from aiogram.types import FSInputFile, Message

import database as db
from config import is_admin
from pdf_report import generate_attendance_matrix_report, generate_tests_matrix_report

def escape(text) -> str:
    """Telegram HTML uchun: faqat < > & almashtiriladi (apostrof/qo'shtirnoq o'z holicha)."""
    return _html_escape(str(text), quote=False)


router = Router()
router.message.filter(F.chat.type == "private")

ATTENDANCE_BUTTON = "📋 Davomat hisoboti"
TESTS_BUTTON = "🧾 Test hisoboti"

MAX_NAMES = 40          # matnda ko'rsatiladigan ismlar soni (to'liq ro'yxat PDF'da)
TG_TEXT_LIMIT = 3800


def _tashkent(created_at, with_year: bool = False) -> str:
    """Bazadagi UTC vaqt ("YYYY-MM-DD HH:MM:SS") -> Toshkent vaqti ("dd.mm HH:MM")."""
    try:
        dt = datetime.strptime(str(created_at)[:19], "%Y-%m-%d %H:%M:%S") + timedelta(hours=5)
    except ValueError:
        return str(created_at or "?")
    return dt.strftime("%d.%m.%Y %H:%M" if with_year else "%d.%m %H:%M")


def _names_block(names) -> str:
    shown = [escape(n or "Noma'lum") for n in names[:MAX_NAMES]]
    text = "\n".join(f"  • {n}" for n in shown)
    if len(names) > MAX_NAMES:
        text += f"\n  … va yana {len(names) - MAX_NAMES} ta (to'liq ro'yxat PDF'da)"
    return text


async def _send_long(message: Message, text: str):
    """Telegram 4096 belgi chegarasi: uzun matnni qatorlar bo'yicha bo'lib yuboradi."""
    chunk = ""
    for line in text.split("\n"):
        if len(chunk) + len(line) + 1 > TG_TEXT_LIMIT and chunk:
            await message.answer(chunk, parse_mode="HTML")
            chunk = ""
        chunk += line + "\n"
    if chunk.strip():
        await message.answer(chunk, parse_mode="HTML")


def _last_report_line(last_at) -> str:
    return f"Oxirgi hisobot: {last_at}" if last_at else "Bu — birinchi hisobot."


# ---------- Davomat hisoboti ----------

@router.message(F.text == ATTENDANCE_BUTTON)
async def attendance_report(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    batch, new_cursor, last_at = await db.get_report_batch("attendance", user_id)
    if not batch:
        await message.answer(
            "📭 Yangi davomat hisoboti yo'q — oxirgi hisobotdan beri yakunlangan "
            f"davomat bo'lmadi.\n{_last_report_line(last_at)}"
        )
        return

    wait = await message.answer("⏳ Hisobot tayyorlanmoqda...")
    try:
        students = await db.get_report_students()
        attended = await db.get_report_attendance_records([s["id"] for s in batch])

        labels = [_tashkent(s["created_at"]) for s in batch]
        rows = []
        per_session = [[0, 0] for _ in batch]       # [qatnashdi, qatnashmadi]
        missed_all = []
        for st in students:
            statuses = []
            for i, s in enumerate(batch):
                if st["registered_at"] and s["created_at"] and st["registered_at"] > s["created_at"]:
                    statuses.append("na")          # o'sha payt hali ro'yxatdan o'tmagan edi
                elif (s["id"], st["telegram_id"]) in attended:
                    statuses.append("in")
                    per_session[i][0] += 1
                else:
                    statuses.append("out")
                    per_session[i][1] += 1
            rows.append((st["full_name"] or "Noma'lum", statuses))
            counted = [x for x in statuses if x != "na"]
            if counted and all(x == "out" for x in counted):
                missed_all.append(st["full_name"])

        path = os.path.join(tempfile.gettempdir(), f"davomat_hisobot_{user_id}.pdf")
        # Qatnashmaganlar tepada chiqsin (qo'ng'iroq qilish uchun qulay)
        rows.sort(key=lambda r: (-sum(1 for x in r[1] if x == "out"), r[0]))
        generate_attendance_matrix_report(path, labels, rows)

        lines = [
            "📋 <b>Davomat hisoboti</b>",
            f"🗓 {_tashkent(batch[0]['created_at'], True)} → {_tashkent(batch[-1]['created_at'], True)}",
            f"Darslar soni: <b>{len(batch)}</b>   |   O'quvchilar: <b>{len(students)}</b>",
            "",
        ]
        for s, (came, absent) in zip(batch, per_session):
            lines.append(f"• {_tashkent(s['created_at'])} (kod {escape(str(s['code']))}): ✅ {came}  ❌ {absent}")
        if missed_all:
            lines += ["", f"🚫 <b>Hamma darsga qatnashmaganlar ({len(missed_all)}):</b>", _names_block(missed_all)]
        elif len(batch):
            lines += ["", "🎉 Hamma kamida bitta darsga qatnashgan."]
        lines += ["", _last_report_line(last_at)]

        await _send_long(message, "\n".join(lines))
        await message.answer_document(
            FSInputFile(path),
            caption="📊 Yashil — qatnashdi, Qizil — qatnashmadi, Kulrang — o'sha payt hali ro'yxatdan o'tmagan edi.",
        )
        await db.commit_report_cursor("attendance", user_id, new_cursor)
    except Exception:
        logging.exception("Davomat hisobotini tayyorlashda xatolik")
        await message.answer("⚠️ Hisobotni tayyorlab bo'lmadi. Keyinroq qayta urinib ko'ring "
                             "(belgi o'zgarmadi — hech narsa o'tkazib yuborilmaydi).")
    finally:
        try:
            await wait.delete()
        except Exception:
            pass


# ---------- Test hisoboti (oddiy + A+) ----------

@router.message(F.text == TESTS_BUTTON)
async def tests_report(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    plain, plain_cursor, last_plain = await db.get_report_batch("tests", user_id)
    aplus, aplus_cursor, last_aplus = await db.get_report_batch("aplus", user_id)
    last_at = last_plain or last_aplus
    if not plain and not aplus:
        await message.answer(
            "📭 Yangi test hisoboti yo'q — oxirgi hisobotdan beri muddati tugagan "
            f"test bo'lmadi.\n{_last_report_line(last_at)}"
        )
        return

    wait = await message.answer("⏳ Hisobot tayyorlanmoqda...")
    try:
        students = await db.get_report_students()
        plain_scores = await db.get_report_submission_scores("tests", [t["id"] for t in plain])
        aplus_scores = await db.get_report_submission_scores("aplus", [t["id"] for t in aplus])

        # (yorliq, test, ballar lug'ati, A+mi)
        tests = (
            [((t["name"] or t["code"]), t, plain_scores, False) for t in plain]
            + [("A+ " + (t["name"] or t["code"]), t, aplus_scores, True) for t in aplus]
        )
        labels = [label for label, *_ in tests]

        rows = []
        per_test = [{"done": 0, "total": 0, "sum": 0} for _ in tests]
        none_done = []
        for st in students:
            cells, done, total = [], 0, 0
            for i, (_, t, scores, _is_aplus) in enumerate(tests):
                if st["registered_at"] and t["created_at"] and st["registered_at"] > t["created_at"]:
                    cells.append(("na", ""))
                    continue
                total += 1
                per_test[i]["total"] += 1
                score = scores.get((t["id"], st["telegram_id"]))
                if score is None:
                    cells.append(("out", "-"))
                else:
                    cells.append(("in", str(score)))
                    done += 1
                    per_test[i]["done"] += 1
                    per_test[i]["sum"] += score or 0
            rows.append((st["full_name"] or "Noma'lum", cells, done, total))
            if total and done == 0:
                none_done.append(st["full_name"])

        # Eng kam ishlaganlar tepada (qo'ng'iroq qilish uchun qulay)
        rows.sort(key=lambda r: ((r[2] / r[3]) if r[3] else 1, r[0]))

        path = os.path.join(tempfile.gettempdir(), f"test_hisobot_{user_id}.pdf")
        generate_tests_matrix_report(path, "TESTLAR HISOBOTI", labels, rows)

        lines = [
            "🧾 <b>Test hisoboti</b>",
            f"Testlar: <b>{len(tests)}</b>   |   O'quvchilar: <b>{len(students)}</b>",
            "",
        ]
        for (label, t, _scores, _is_aplus), stat in zip(tests, per_test):
            avg = f", o'rtacha {stat['sum'] / stat['done']:.1f}" if stat["done"] else ""
            lines.append(f"• {escape(str(label))}: <b>{stat['done']}/{stat['total']}</b> ishladi{avg}")
        if none_done:
            lines += ["", f"🚫 <b>Birorta ham test ishlamaganlar ({len(none_done)}):</b>", _names_block(none_done)]
        else:
            lines += ["", "🎉 Hamma kamida bitta test ishlagan."]
        lines += ["", _last_report_line(last_at)]

        await _send_long(message, "\n".join(lines))
        await message.answer_document(
            FSInputFile(path),
            caption="📊 Yashil — ishlagan (ball), Qizil — ishlamagan, Kulrang — test chiqqanda hali ro'yxatdan o'tmagan edi.",
        )
        if plain:
            await db.commit_report_cursor("tests", user_id, plain_cursor)
        if aplus:
            await db.commit_report_cursor("aplus", user_id, aplus_cursor)
    except Exception:
        logging.exception("Test hisobotini tayyorlashda xatolik")
        await message.answer("⚠️ Hisobotni tayyorlab bo'lmadi. Keyinroq qayta urinib ko'ring "
                             "(belgi o'zgarmadi — hech narsa o'tkazib yuborilmaydi).")
    finally:
        try:
            await wait.delete()
        except Exception:
            pass
