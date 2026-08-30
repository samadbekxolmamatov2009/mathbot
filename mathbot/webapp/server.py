"""Test Mini App (WebApp) uchun aiohttp server.

Bitta aiohttp ilova ham statik fayllarni (HTML/CSS/JS), ham API'ni xizmat qiladi
(shu sabab CORS sozlash shart emas - hammasi bitta origin'dan).
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import random
import re
import time
from datetime import datetime
from urllib.parse import parse_qsl

from aiohttp import web

import config
import database as db
from answer_check import answers_equivalent
from config import ALLOWED_ORIGINS, BOT_TOKEN, is_admin
from quiz_structure import all_questions, options_for, DEFAULT_TOTAL_QUESTIONS
from timezone_utils import now_tashkent

ADMIN_SYNC_INTERVAL_SECONDS = 60

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MAX_INIT_DATA_AGE = 24 * 60 * 60  # 24 soat

log = logging.getLogger("webapp")


def verify_init_data(init_data: str):
    """Telegram WebApp initData imzosini tekshiradi.

    To'g'ri bo'lsa foydalanuvchi ma'lumotini (dict) qaytaradi, aks holda None.
    """
    if not init_data:
        log.warning("initData BO'SH keldi (Telegram tomonidan yuborilmadi)")
        return None

    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        log.warning("initData formatini o'qib bo'lmadi: %r", init_data[:200])
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        log.warning("initData ichida 'hash' maydoni yo'q: %r", pairs)
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        log.warning(
            "HASH MOS EMAS!\n  data_check_string=%r\n  received_hash=%s\n  computed_hash=%s\n  BOT_TOKEN(oxiri)=...%s",
            data_check_string,
            received_hash,
            computed_hash,
            BOT_TOKEN[-6:],
        )
        return None

    auth_date = pairs.get("auth_date")
    if not auth_date or time.time() - int(auth_date) > MAX_INIT_DATA_AGE:
        log.warning("auth_date eskirgan yoki yo'q: %r", auth_date)
        return None

    user_raw = pairs.get("user")
    if not user_raw:
        return None

    try:
        return json.loads(user_raw)
    except ValueError:
        return None


def _generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def _now_str() -> str:
    """datetime-local input formatiga mos joriy vaqt (YYYY-MM-DDTHH:MM) -
    O'ZBEKISTON (Toshkent) vaqti bo'yicha, server qayerda joylashganidan
    qat'iy nazar (qarang: timezone_utils.py)."""
    return now_tashkent().strftime("%Y-%m-%dT%H:%M")


def _build_details(correct_answers: dict, user_answers: dict, total_questions: int):
    details = []
    for q in range(1, total_questions + 1):
        key = str(q)
        details.append(
            {
                "question": q,
                "your_answer": user_answers.get(key),
                "correct_answer": correct_answers.get(key),
                "is_correct": user_answers.get(key) == correct_answers.get(key),
            }
        )
    return details


async def create_test_handler(request: web.Request):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad_request"}, status=400)

    user = verify_init_data(body.get("init_data", ""))
    if not user:
        return web.json_response({"error": "invalid_init_data"}, status=401)

    if not is_admin(user["id"]):
        return web.json_response({"error": "not_admin"}, status=403)

    name = (body.get("name") or "").strip()
    if not name:
        return web.json_response({"error": "missing_name"}, status=400)

    total_questions = body.get("total_questions", DEFAULT_TOTAL_QUESTIONS)
    if not isinstance(total_questions, int) or total_questions < 1:
        return web.json_response({"error": "invalid_total_questions"}, status=400)

    answers = body.get("answers", {})
    if not isinstance(answers, dict):
        return web.json_response({"error": "invalid_answers"}, status=400)

    for q in range(1, total_questions + 1):
        key = str(q)
        if answers.get(key) not in options_for(q):
            return web.json_response(
                {"error": "incomplete_or_invalid", "question": q}, status=400
            )

    start_time = body.get("start_time")
    end_time = body.get("end_time")
    if not start_time or not end_time:
        return web.json_response({"error": "missing_time"}, status=400)
    if end_time <= start_time:
        return web.json_response({"error": "invalid_time_range"}, status=400)

    code = _generate_code()
    while await db.code_exists(code):
        code = _generate_code()

    await db.create_test(code, user["id"], answers, start_time, end_time, name, total_questions)

    saved = await db.get_test_by_code(code)
    if not saved:
        log.error("Test yaratildi deb hisoblandi, lekin bazada topilmadi! code=%s", code)
        return web.json_response({"error": "save_failed"}, status=500)

    return web.json_response({"code": code})


async def get_test_edit_data_handler(request: web.Request):
    try:
        test_id = int(request.match_info["id"])
    except ValueError:
        return web.json_response({"error": "not_found"}, status=404)

    user = verify_init_data(request.query.get("init_data", ""))
    if not user:
        return web.json_response({"error": "invalid_init_data"}, status=401)
    if not is_admin(user["id"]):
        return web.json_response({"error": "not_admin"}, status=403)

    test = await db.get_test_by_id(test_id)
    if not test:
        return web.json_response({"error": "not_found"}, status=404)

    return web.json_response(
        {
            "code": test["code"],
            "name": test["name"] or "",
            "answers": json.loads(test["answers"]),
            "start_time": test["start_time"],
            "end_time": test["end_time"],
            "total_questions": test["total_questions"] or DEFAULT_TOTAL_QUESTIONS,
        }
    )


async def _recalculate_test_scores(old_test, new_answers: dict, new_total_questions: int):
    """Ustoz test javob kalitini to'g'irlaganda, o'quvchilar allaqachon
    topshirgan javoblari YANGI kalit bo'yicha qayta tekshiriladi va
    test_submissions.score yangilanadi (aks holda tangalar eski, xato
    kalitga asoslangan holda qolib ketaveradi).

    "Kech topshirilgani" uchun ball qisqartirilgan-qisqartirilmaganini
    alohida ustunda saqlamaymiz - shuning uchun bu holatni eski (kalit
    to'g'irlanishidan oldingi) ball orqali bilib olamiz: agar eski ball
    eski to'g'ri javoblar sonidan kam bo'lsa, demak kech topshirilgan."""
    old_answers = json.loads(old_test["answers"])
    old_total_questions = old_test["total_questions"] or DEFAULT_TOTAL_QUESTIONS

    submissions = await db.get_test_submissions_for_scoring(old_test["id"])
    updates = []
    for sub in submissions:
        user_answers = json.loads(sub["answers"])

        old_raw = sum(
            1
            for q in range(1, old_total_questions + 1)
            if user_answers.get(str(q)) == old_answers.get(str(q))
        )
        is_late = old_raw > 0 and sub["score"] < old_raw

        new_raw = sum(
            1
            for q in range(1, new_total_questions + 1)
            if user_answers.get(str(q)) == new_answers.get(str(q))
        )
        new_score = new_raw * LATE_SUBMISSION_SCORE_RATIO if is_late else new_raw

        if new_score != sub["score"]:
            updates.append((sub["id"], new_score))

    if updates:
        await db.update_test_submission_scores(updates)


async def update_test_handler(request: web.Request):
    try:
        test_id = int(request.match_info["id"])
    except ValueError:
        return web.json_response({"error": "not_found"}, status=404)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad_request"}, status=400)

    user = verify_init_data(body.get("init_data", ""))
    if not user:
        return web.json_response({"error": "invalid_init_data"}, status=401)
    if not is_admin(user["id"]):
        return web.json_response({"error": "not_admin"}, status=403)

    test = await db.get_test_by_id(test_id)
    if not test:
        return web.json_response({"error": "not_found"}, status=404)

    name = (body.get("name") or "").strip()
    if not name:
        return web.json_response({"error": "missing_name"}, status=400)

    total_questions = body.get("total_questions", DEFAULT_TOTAL_QUESTIONS)
    if not isinstance(total_questions, int) or total_questions < 1:
        return web.json_response({"error": "invalid_total_questions"}, status=400)

    answers = body.get("answers", {})
    if not isinstance(answers, dict):
        return web.json_response({"error": "invalid_answers"}, status=400)

    for q in range(1, total_questions + 1):
        key = str(q)
        if answers.get(key) not in options_for(q):
            return web.json_response(
                {"error": "incomplete_or_invalid", "question": q}, status=400
            )

    start_time = body.get("start_time")
    end_time = body.get("end_time")
    if not start_time or not end_time:
        return web.json_response({"error": "missing_time"}, status=400)
    if end_time <= start_time:
        return web.json_response({"error": "invalid_time_range"}, status=400)

    await db.update_test(test_id, answers, start_time, end_time, name, total_questions)

    saved = await db.get_test_by_id(test_id)
    if not saved or json.loads(saved["answers"]) != answers:
        log.error("Test yangilandi deb hisoblandi, lekin baza mos kelmadi! id=%s", test_id)
        return web.json_response({"error": "save_failed"}, status=500)

    await _recalculate_test_scores(test, answers, total_questions)

    return web.json_response({"code": test["code"]})


async def test_status_handler(request: web.Request):
    code = request.match_info["code"]
    test = await db.get_test_by_code(code)
    if not test:
        return web.json_response({"exists": False})

    total_questions = test["total_questions"] or DEFAULT_TOTAL_QUESTIONS

    user = verify_init_data(request.query.get("init_data", ""))
    already_submitted = None
    if user:
        sub = await db.has_submitted_test(test["id"], user["id"])
        if sub:
            correct_answers = json.loads(test["answers"])
            user_answers = json.loads(sub["answers"])
            already_submitted = {
                "score": sub["score"],
                "total": total_questions,
                "details": _build_details(correct_answers, user_answers, total_questions),
            }

    now = _now_str()
    if now < test["start_time"]:
        window_status = "not_started"
    elif now > test["end_time"]:
        window_status = "ended"
    else:
        window_status = "active"

    response = {
        "exists": True,
        "name": test["name"] or "",
        "window_status": window_status,
        "start_time": test["start_time"],
        "end_time": test["end_time"],
        "already_submitted": already_submitted,
    }
    if window_status in ("active", "ended") and not already_submitted:
        response["questions"] = all_questions(total_questions)

    return web.json_response(response)


LATE_SUBMISSION_SCORE_RATIO = 0.75


async def submit_test_handler(request: web.Request):
    code = request.match_info["code"]
    test = await db.get_test_by_code(code)
    if not test:
        return web.json_response({"error": "not_found"}, status=404)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad_request"}, status=400)

    user = verify_init_data(body.get("init_data", ""))
    if not user:
        return web.json_response({"error": "invalid_init_data"}, status=401)

    total_questions = test["total_questions"] or DEFAULT_TOTAL_QUESTIONS
    correct_answers = json.loads(test["answers"])

    existing = await db.has_submitted_test(test["id"], user["id"])
    if existing:
        user_answers = json.loads(existing["answers"])
        return web.json_response(
            {
                "score": existing["score"],
                "total": total_questions,
                "details": _build_details(correct_answers, user_answers, total_questions),
                "already_submitted": True,
            }
        )

    now = _now_str()
    if now < test["start_time"]:
        return web.json_response({"error": "not_started"}, status=403)

    # Test vaqti tugagan bo'lsa ham topshirish MUMKIN - lekin kech
    # topshirgani uchun ball 75% ga qisqartiriladi (talab shunday).
    is_late = now > test["end_time"]

    submitted_answers = body.get("answers", {})
    if not isinstance(submitted_answers, dict):
        submitted_answers = {}

    raw_score = sum(
        1
        for q in range(1, total_questions + 1)
        if submitted_answers.get(str(q)) == correct_answers.get(str(q))
    )
    score = raw_score * LATE_SUBMISSION_SCORE_RATIO if is_late else raw_score

    await db.save_test_submission(test["id"], user["id"], submitted_answers, score)

    return web.json_response(
        {
            "score": score,
            "total": total_questions,
            "details": _build_details(correct_answers, submitted_answers, total_questions),
            "already_submitted": False,
            "late": is_late,
        }
    )


async def rating_handler(request: web.Request):
    user = verify_init_data(request.query.get("init_data", ""))
    if not user:
        return web.json_response({"error": "invalid_init_data"}, status=401)

    leaderboard = await db.get_leaderboard(limit=50)
    return web.json_response(
        {
            "leaderboard": [
                {
                    "rank": i + 1,
                    "telegram_id": row["telegram_id"],
                    "full_name": row["full_name"] or "Noma'lum",
                    "coins": row["coins"],
                }
                for i, row in enumerate(leaderboard)
            ]
        }
    )


async def my_results_handler(request: web.Request):
    user = verify_init_data(request.query.get("init_data", ""))
    if not user:
        return web.json_response({"error": "invalid_init_data"}, status=401)

    rows = await db.get_user_test_results(user["id"])
    coins = await db.get_user_coins(user["id"])
    return web.json_response(
        {
            "results": [
                {
                    "name": row["name"] or row["code"],
                    "code": row["code"],
                    "score": row["score"],
                    "total_questions": row["total_questions"] or DEFAULT_TOTAL_QUESTIONS,
                    "submitted_at": row["submitted_at"],
                }
                for row in rows
            ],
            "coins": {
                "attendance_count": coins["attendance_count"],
                "attendance_coins": coins["attendance_coins"],
                "test_coins": coins["test_coins"],
                "test_streak_coins": coins["test_streak_coins"],
                "total": coins["total"],
            },
        }
    )


async def get_report_schedule_handler(request: web.Request):
    user = verify_init_data(request.query.get("init_data", ""))
    if not user:
        return web.json_response({"error": "invalid_init_data"}, status=401)
    if not is_admin(user["id"]):
        return web.json_response({"error": "not_admin"}, status=403)

    schedule = await db.get_report_schedule()
    if not schedule:
        return web.json_response({"schedule": None})

    return web.json_response(
        {
            "schedule": {
                "day_of_week": schedule["day_of_week"],
                "time_of_day": schedule["time_of_day"],
                "enabled": bool(schedule["enabled"]),
                "last_sent_at": schedule["last_sent_at"],
            }
        }
    )


async def save_report_schedule_handler(request: web.Request):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad_request"}, status=400)

    user = verify_init_data(body.get("init_data", ""))
    if not user:
        return web.json_response({"error": "invalid_init_data"}, status=401)
    if not is_admin(user["id"]):
        return web.json_response({"error": "not_admin"}, status=403)

    day_of_week = body.get("day_of_week")
    time_of_day = body.get("time_of_day") or ""
    enabled = bool(body.get("enabled", True))

    if not isinstance(day_of_week, int) or not (0 <= day_of_week <= 6):
        return web.json_response({"error": "invalid_day"}, status=400)
    if not re.fullmatch(r"[0-2]\d:[0-5]\d", time_of_day):
        return web.json_response({"error": "invalid_time"}, status=400)

    await db.save_report_schedule(day_of_week, time_of_day, enabled, user["id"])

    return web.json_response({"ok": True})


# ---------- A+ testlar (yozma javobli) ----------

def _aplus_field_keys(question_count: int):
    keys = []
    for n in range(1, question_count + 1):
        keys.append(f"{n}a")
        keys.append(f"{n}b")
    return keys


def _aplus_build_details(correct_answers: dict, user_answers: dict, question_count: int):
    details = []
    for key in _aplus_field_keys(question_count):
        your = user_answers.get(key)
        correct = correct_answers.get(key)
        details.append(
            {
                "key": key,
                "your_answer": your,
                "correct_answer": correct,
                "is_correct": answers_equivalent(correct, your) if your is not None else False,
            }
        )
    return details


async def aplus_create_test_handler(request: web.Request):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad_request"}, status=400)

    user = verify_init_data(body.get("init_data", ""))
    if not user:
        return web.json_response({"error": "invalid_init_data"}, status=401)
    if not is_admin(user["id"]):
        return web.json_response({"error": "not_admin"}, status=403)

    name = (body.get("name") or "").strip()
    if not name:
        return web.json_response({"error": "missing_name"}, status=400)

    question_count = body.get("question_count")
    if not isinstance(question_count, int) or question_count < 1:
        return web.json_response({"error": "invalid_question_count"}, status=400)

    answers = body.get("answers", {})
    if not isinstance(answers, dict):
        return web.json_response({"error": "invalid_answers"}, status=400)

    for key in _aplus_field_keys(question_count):
        if not isinstance(answers.get(key), str) or not answers.get(key, "").strip():
            return web.json_response({"error": "incomplete_answers", "field": key}, status=400)

    start_time = body.get("start_time")
    end_time = body.get("end_time")
    if not start_time or not end_time:
        return web.json_response({"error": "missing_time"}, status=400)
    if end_time <= start_time:
        return web.json_response({"error": "invalid_time_range"}, status=400)

    code = _generate_code()
    while await db.aplus_code_exists(code):
        code = _generate_code()

    await db.create_aplus_test(code, user["id"], answers, start_time, end_time, name, question_count)

    saved = await db.get_aplus_test_by_code(code)
    if not saved:
        log.error("A+ test yaratildi deb hisoblandi, lekin bazada topilmadi! code=%s", code)
        return web.json_response({"error": "save_failed"}, status=500)

    return web.json_response({"code": code})


async def aplus_get_edit_data_handler(request: web.Request):
    try:
        test_id = int(request.match_info["id"])
    except ValueError:
        return web.json_response({"error": "not_found"}, status=404)

    user = verify_init_data(request.query.get("init_data", ""))
    if not user:
        return web.json_response({"error": "invalid_init_data"}, status=401)
    if not is_admin(user["id"]):
        return web.json_response({"error": "not_admin"}, status=403)

    test = await db.get_aplus_test_by_id(test_id)
    if not test:
        return web.json_response({"error": "not_found"}, status=404)

    return web.json_response(
        {
            "code": test["code"],
            "name": test["name"] or "",
            "answers": json.loads(test["answers"]),
            "question_count": test["question_count"],
            "start_time": test["start_time"],
            "end_time": test["end_time"],
        }
    )


async def _recalculate_aplus_scores(old_test, new_answers: dict, new_question_count: int):
    """_recalculate_test_scores bilan bir xil mantiq, A+ (yozma javobli)
    testlar uchun - javoblar answers_equivalent() orqali solishtiriladi."""
    old_answers = json.loads(old_test["answers"])
    old_question_count = old_test["question_count"]

    submissions = await db.get_aplus_submissions_for_scoring(old_test["id"])
    updates = []
    for sub in submissions:
        user_answers = json.loads(sub["answers"])

        old_raw = sum(
            1
            for key in _aplus_field_keys(old_question_count)
            if answers_equivalent(old_answers.get(key), user_answers.get(key))
        )
        is_late = old_raw > 0 and sub["score"] < old_raw

        new_raw = sum(
            1
            for key in _aplus_field_keys(new_question_count)
            if answers_equivalent(new_answers.get(key), user_answers.get(key))
        )
        new_score = new_raw * LATE_SUBMISSION_SCORE_RATIO if is_late else new_raw

        if new_score != sub["score"]:
            updates.append((sub["id"], new_score))

    if updates:
        await db.update_aplus_submission_scores(updates)


async def aplus_update_test_handler(request: web.Request):
    try:
        test_id = int(request.match_info["id"])
    except ValueError:
        return web.json_response({"error": "not_found"}, status=404)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad_request"}, status=400)

    user = verify_init_data(body.get("init_data", ""))
    if not user:
        return web.json_response({"error": "invalid_init_data"}, status=401)
    if not is_admin(user["id"]):
        return web.json_response({"error": "not_admin"}, status=403)

    test = await db.get_aplus_test_by_id(test_id)
    if not test:
        return web.json_response({"error": "not_found"}, status=404)

    name = (body.get("name") or "").strip()
    if not name:
        return web.json_response({"error": "missing_name"}, status=400)

    question_count = body.get("question_count")
    if not isinstance(question_count, int) or question_count < 1:
        return web.json_response({"error": "invalid_question_count"}, status=400)

    answers = body.get("answers", {})
    if not isinstance(answers, dict):
        return web.json_response({"error": "invalid_answers"}, status=400)

    for key in _aplus_field_keys(question_count):
        if not isinstance(answers.get(key), str) or not answers.get(key, "").strip():
            return web.json_response({"error": "incomplete_answers", "field": key}, status=400)

    start_time = body.get("start_time")
    end_time = body.get("end_time")
    if not start_time or not end_time:
        return web.json_response({"error": "missing_time"}, status=400)
    if end_time <= start_time:
        return web.json_response({"error": "invalid_time_range"}, status=400)

    await db.update_aplus_test(test_id, answers, start_time, end_time, name, question_count)

    await _recalculate_aplus_scores(test, answers, question_count)

    return web.json_response({"code": test["code"]})


async def aplus_test_status_handler(request: web.Request):
    code = request.match_info["code"]
    test = await db.get_aplus_test_by_code(code)
    if not test:
        return web.json_response({"exists": False})

    question_count = test["question_count"]

    user = verify_init_data(request.query.get("init_data", ""))
    already_submitted = None
    if user:
        sub = await db.has_submitted_aplus_test(test["id"], user["id"])
        if sub:
            correct_answers = json.loads(test["answers"])
            user_answers = json.loads(sub["answers"])
            already_submitted = {
                "score": sub["score"],
                "total": question_count * 2,
                "details": _aplus_build_details(correct_answers, user_answers, question_count),
            }

    now = _now_str()
    if now < test["start_time"]:
        window_status = "not_started"
    elif now > test["end_time"]:
        window_status = "ended"
    else:
        window_status = "active"

    response = {
        "exists": True,
        "name": test["name"] or "",
        "window_status": window_status,
        "start_time": test["start_time"],
        "end_time": test["end_time"],
        "already_submitted": already_submitted,
    }
    if window_status in ("active", "ended") and not already_submitted:
        response["question_count"] = question_count
        response["fields"] = _aplus_field_keys(question_count)

    return web.json_response(response)


async def aplus_submit_handler(request: web.Request):
    code = request.match_info["code"]
    test = await db.get_aplus_test_by_code(code)
    if not test:
        return web.json_response({"error": "not_found"}, status=404)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad_request"}, status=400)

    user = verify_init_data(body.get("init_data", ""))
    if not user:
        return web.json_response({"error": "invalid_init_data"}, status=401)

    question_count = test["question_count"]
    correct_answers = json.loads(test["answers"])

    existing = await db.has_submitted_aplus_test(test["id"], user["id"])
    if existing:
        user_answers = json.loads(existing["answers"])
        return web.json_response(
            {
                "score": existing["score"],
                "total": question_count * 2,
                "details": _aplus_build_details(correct_answers, user_answers, question_count),
                "already_submitted": True,
            }
        )

    now = _now_str()
    if now < test["start_time"]:
        return web.json_response({"error": "not_started"}, status=403)

    # Test vaqti tugagan bo'lsa ham topshirish MUMKIN - lekin kech
    # topshirgani uchun ball 75% ga qisqartiriladi.
    is_late = now > test["end_time"]

    submitted_answers = body.get("answers", {})
    if not isinstance(submitted_answers, dict):
        submitted_answers = {}

    raw_score = sum(
        1
        for key in _aplus_field_keys(question_count)
        if answers_equivalent(correct_answers.get(key), submitted_answers.get(key))
    )
    score = raw_score * LATE_SUBMISSION_SCORE_RATIO if is_late else raw_score

    await db.save_aplus_submission(test["id"], user["id"], submitted_answers, score)

    return web.json_response(
        {
            "score": score,
            "total": question_count * 2,
            "details": _aplus_build_details(correct_answers, submitted_answers, question_count),
            "already_submitted": False,
            "late": is_late,
        }
    )


async def debug_log_handler(request: web.Request):
    try:
        info = await request.json()
    except json.JSONDecodeError:
        info = {}
    log.warning("CLIENT DEBUG: %s", json.dumps(info, ensure_ascii=False))
    return web.json_response({"ok": True})


@web.middleware
async def no_cache_middleware(request: web.Request, handler):
    response = await handler(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@web.middleware
async def cors_middleware(request: web.Request, handler):
    """Netlify'da joylashgan test mini-app (boshqa origin) /api/* ga so'rov yubora olishi uchun."""
    origin = request.headers.get("Origin")

    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        response = await handler(request)

    if origin and origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Vary"] = "Origin"

    return response


async def _refresh_admin_ids_loop():
    """mathbot-1 (Mini App backend) va bot (worker) ALOHIDA jarayonlar bo'lgani
    uchun, Boss botda yangi admin qo'shsa/olib tashlasa, bu o'zgarish worker
    xotirasida darhol ko'rinadi-yu, lekin shu (web) jarayon buni umuman
    bilmaydi - natijada yangi admin Mini App funksiyalaridan (A+ yaratish,
    sozlamalar va h.k.) foydalana olmay qoladi. Shu funksiya har
    ADMIN_SYNC_INTERVAL_SECONDS'da adminlar ro'yxatini bazadan qayta o'qib,
    config.ADMIN_IDS'ni yangilab turadi."""
    while True:
        try:
            config.ADMIN_IDS[:] = await db.get_admin_ids()
        except Exception:
            log.exception("Adminlar ro'yxatini yangilashda xatolik")
        await asyncio.sleep(ADMIN_SYNC_INTERVAL_SECONDS)


async def _on_startup(app: web.Application):
    try:
        config.ADMIN_IDS[:] = await db.get_admin_ids()
    except Exception:
        log.exception("Adminlar ro'yxatini boshlang'ich yuklashda xatolik")
    app["admin_sync_task"] = asyncio.create_task(_refresh_admin_ids_loop())


async def _on_cleanup(app: web.Application):
    task = app.get("admin_sync_task")
    if task:
        task.cancel()


def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware, no_cache_middleware])
    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)
    app.router.add_post("/api/debug_log", debug_log_handler)
    app.router.add_post("/api/create_test", create_test_handler)
    app.router.add_get("/api/test_by_id/{id}", get_test_edit_data_handler)
    app.router.add_post("/api/test_by_id/{id}/update", update_test_handler)
    app.router.add_get("/api/test/{code}/status", test_status_handler)
    app.router.add_post("/api/test/{code}/submit", submit_test_handler)
    app.router.add_get("/api/rating", rating_handler)
    app.router.add_get("/api/my_results", my_results_handler)
    app.router.add_get("/api/report_schedule", get_report_schedule_handler)
    app.router.add_post("/api/report_schedule", save_report_schedule_handler)
    app.router.add_post("/api/aplus/create_test", aplus_create_test_handler)
    app.router.add_get("/api/aplus/test_by_id/{id}", aplus_get_edit_data_handler)
    app.router.add_post("/api/aplus/test_by_id/{id}/update", aplus_update_test_handler)
    app.router.add_get("/api/aplus/test/{code}/status", aplus_test_status_handler)
    app.router.add_post("/api/aplus/test/{code}/submit", aplus_submit_handler)
    app.router.add_static("/", STATIC_DIR, show_index=False)
    return app
