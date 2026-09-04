import json
from datetime import datetime

# db_backend - TURSO_DATABASE_URL sozlangan bo'lsa Turso (tarmoq bazasi),
# aks holda oddiy mahalliy SQLite fayl bilan ishlaydi - aiosqlite bilan
# bir xil interfeys bergani uchun pastdagi SQL so'rovlarning birortasi
# ham o'zgartirilishi shart emas.
import db_backend as aiosqlite
from timezone_utils import now_tashkent_str
from config import DB_PATH


async def init_db():
    """Bot ishga tushganda bazani va jadvallarni yaratadi"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                full_name TEXT,
                course TEXT,
                region TEXT,
                district TEXT,
                phone TEXT,
                registered_at TEXT DEFAULT (datetime('now')),
                is_registered INTEGER DEFAULT 0,
                subscription_checked_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attendance_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                warning_minutes INTEGER NOT NULL,
                report_minutes INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attendance_records (
                session_id INTEGER NOT NULL,
                telegram_id INTEGER NOT NULL,
                submitted_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (session_id, telegram_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                answers TEXT NOT NULL,
                start_time TEXT,
                end_time TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)

        table_info_cursor = await db.execute("PRAGMA table_info(tests)")
        existing_columns = {row[1] for row in await table_info_cursor.fetchall()}
        if "start_time" not in existing_columns:
            await db.execute("ALTER TABLE tests ADD COLUMN start_time TEXT")
        if "end_time" not in existing_columns:
            await db.execute("ALTER TABLE tests ADD COLUMN end_time TEXT")
        if "name" not in existing_columns:
            await db.execute("ALTER TABLE tests ADD COLUMN name TEXT")
        if "report_sent" not in existing_columns:
            await db.execute("ALTER TABLE tests ADD COLUMN report_sent INTEGER DEFAULT 0")
        if "total_questions" not in existing_columns:
            await db.execute("ALTER TABLE tests ADD COLUMN total_questions INTEGER DEFAULT 35")
        if "show_wrong_answers" not in existing_columns:
            await db.execute("ALTER TABLE tests ADD COLUMN show_wrong_answers INTEGER DEFAULT 1")

        users_info_cursor = await db.execute("PRAGMA table_info(users)")
        users_columns = {row[1] for row in await users_info_cursor.fetchall()}
        if "role" not in users_columns:
            await db.execute("ALTER TABLE users ADD COLUMN role TEXT")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_absence_reasons (
                telegram_id INTEGER PRIMARY KEY,
                session_id INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS special_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS test_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL,
                telegram_id INTEGER NOT NULL,
                answers TEXT NOT NULL,
                score INTEGER NOT NULL,
                submitted_at TEXT DEFAULT (datetime('now')),
                UNIQUE(test_id, telegram_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS aplus_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                name TEXT,
                answers TEXT NOT NULL,
                question_count INTEGER NOT NULL DEFAULT 1,
                start_time TEXT,
                end_time TEXT,
                is_active INTEGER DEFAULT 1,
                report_sent INTEGER DEFAULT 0
            )
        """)

        aplus_table_info_cursor = await db.execute("PRAGMA table_info(aplus_tests)")
        aplus_existing_columns = {row[1] for row in await aplus_table_info_cursor.fetchall()}
        if "show_wrong_answers" not in aplus_existing_columns:
            await db.execute("ALTER TABLE aplus_tests ADD COLUMN show_wrong_answers INTEGER DEFAULT 1")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS aplus_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL,
                telegram_id INTEGER NOT NULL,
                answers TEXT NOT NULL,
                score INTEGER NOT NULL,
                submitted_at TEXT DEFAULT (datetime('now')),
                UNIQUE(test_id, telegram_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_schedule (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                message TEXT NOT NULL,
                day_of_week INTEGER NOT NULL,
                time_of_day TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                updated_by INTEGER,
                updated_at TEXT DEFAULT (datetime('now')),
                last_sent_week TEXT,
                file_data TEXT,
                file_name TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS report_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_of_week INTEGER NOT NULL,
                time_of_day TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                updated_by INTEGER,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # Eski (bitta qatorli, "CHECK (id = 1)" bilan yaratilgan) jadvalni
        # bir nechta vaqtni qo'llab-quvvatlaydigan yangi tuzilmaga o'tkazish.
        try:
            check_cursor = await db.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='report_schedule'"
            )
            row = await check_cursor.fetchone()
            if row and row[0] and "CHECK" in row[0]:
                await db.execute("ALTER TABLE report_schedule RENAME TO report_schedule_old")
                await db.execute("""
                    CREATE TABLE report_schedule (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        day_of_week INTEGER NOT NULL,
                        time_of_day TEXT NOT NULL,
                        enabled INTEGER NOT NULL DEFAULT 1,
                        updated_by INTEGER,
                        updated_at TEXT DEFAULT (datetime('now'))
                    )
                """)
                old_cursor = await db.execute(
                    "SELECT day_of_week, time_of_day, enabled, updated_by, updated_at, last_sent_at "
                    "FROM report_schedule_old WHERE day_of_week IS NOT NULL"
                )
                old_row = await old_cursor.fetchone()
                if old_row:
                    await db.execute(
                        """INSERT INTO report_schedule (day_of_week, time_of_day, enabled, updated_by, updated_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (old_row[0], old_row[1], old_row[2], old_row[3], old_row[4]),
                    )
                    if old_row[5]:
                        await db.execute(
                            """CREATE TABLE IF NOT EXISTS bot_settings (
                                   key TEXT PRIMARY KEY,
                                   value TEXT
                               )"""
                        )
                        await db.execute(
                            """INSERT INTO bot_settings (key, value) VALUES ('report_last_sent_at', ?)
                               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                            (old_row[5],),
                        )
                await db.execute("DROP TABLE report_schedule_old")
        except Exception:
            pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                telegram_id INTEGER PRIMARY KEY,
                added_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS score_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                delta INTEGER NOT NULL,
                reason TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Eski (migratsiyadan oldin yaratilgan) bazalarda broadcast_schedule
        # jadvalida file_data/file_name ustunlari bo'lmasligi mumkin - CREATE
        # TABLE IF NOT EXISTS eski jadvalni o'zgartirmaydi, shuning uchun
        # ustunlarni alohida qo'shishga harakat qilamiz (allaqachon bo'lsa,
        # xato e'tiborsiz qoldiriladi).
        for column_sql in (
            "ALTER TABLE broadcast_schedule ADD COLUMN file_data TEXT",
            "ALTER TABLE broadcast_schedule ADD COLUMN file_name TEXT",
            "ALTER TABLE tests ADD COLUMN notified INTEGER DEFAULT 0",
            "ALTER TABLE aplus_tests ADD COLUMN notified INTEGER DEFAULT 0",
            "ALTER TABLE special_tasks ADD COLUMN notified INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN subscription_checked_at TEXT",
        ):
            try:
                await db.execute(column_sql)
            except Exception:
                pass

        # Birinchi ishga tushishda config.py'dagi statik ADMIN_IDS bilan
        # "admins" jadvalini boshlang'ich holatga keltiradi (keyinchalik
        # adminlar shu jadval orqali dinamik boshqariladi).
        async with db.execute("SELECT COUNT(*) FROM admins") as cursor:
            admins_count = (await cursor.fetchone())[0]
        if admins_count == 0:
            from config import ADMIN_IDS as INITIAL_ADMIN_IDS
            for admin_id in INITIAL_ADMIN_IDS:
                await db.execute(
                    "INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)", (admin_id,)
                )

        await db.commit()


async def get_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            return await cursor.fetchone()


async def is_user_registered(telegram_id: int) -> bool:
    user = await get_user(telegram_id)
    return bool(user and user["is_registered"])


async def reset_user_registration(telegram_id: int):
    """Foydalanuvchini butunlay 'ro'yxatdan chiqargan' holatga qaytaradi -
    kanaldan chiqarib yuborilgan (obunasi bekor qilingan) foydalanuvchilar
    uchun ishlatiladi. Keyingi /start'da butun ro'yxatdan o'tish jarayonini
    boshidan o'tishga to'g'ri keladi."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
        await db.commit()


async def update_subscription_check(telegram_id: int, checked_at: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET subscription_checked_at = ? WHERE telegram_id = ?",
            (checked_at, telegram_id),
        )
        await db.commit()


# ---------- Adminlar (dinamik boshqariladigan) ----------

async def get_admin_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT telegram_id FROM admins")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def add_admin(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)", (telegram_id,)
        )
        await db.commit()


async def remove_admin(telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM admins WHERE telegram_id = ?", (telegram_id,))
        await db.commit()
        return cursor.rowcount > 0


# ---------- Umumiy sozlamalar (key-value) ----------
# Kodga "qattiq yozilgan" (hardcoded) qiymatlar o'rniga, Boss/admin botning
# o'zidan o'zgartira oladigan sozlamalar shu jadvalda saqlanadi (masalan
# "Administrator bilan bog'lanish" tugmasining havolasi).

async def get_setting(key: str, default: str | None = None) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT value FROM bot_settings WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO bot_settings (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (key, value),
        )
        await db.commit()


# ---------- Ball tuzatishlari ----------

async def adjust_user_score(telegram_id: int, delta: int, reason: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO score_adjustments (telegram_id, delta, reason) VALUES (?, ?, ?)",
            (telegram_id, delta, reason),
        )
        await db.commit()


async def get_score_adjustment_total(telegram_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(SUM(delta), 0) FROM score_adjustments WHERE telegram_id = ?",
            (telegram_id,),
        )
        return (await cursor.fetchone())[0]


async def start_registration(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (telegram_id)
               VALUES (?)
               ON CONFLICT(telegram_id) DO NOTHING""",
            (telegram_id,),
        )
        await db.commit()


async def save_full_name(telegram_id: int, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET full_name = ? WHERE telegram_id = ?",
            (full_name, telegram_id),
        )
        await db.commit()


async def save_role(telegram_id: int, role: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET role = ? WHERE telegram_id = ?",
            (role, telegram_id),
        )
        await db.commit()


async def save_course(telegram_id: int, course_key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET course = ? WHERE telegram_id = ?",
            (course_key, telegram_id),
        )
        await db.commit()


async def save_region(telegram_id: int, region: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET region = ? WHERE telegram_id = ?",
            (region, telegram_id),
        )
        await db.commit()


async def save_district(telegram_id: int, district: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET district = ? WHERE telegram_id = ?",
            (district, telegram_id),
        )
        await db.commit()


async def finish_registration(telegram_id: int, phone: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET phone = ?, is_registered = 1 WHERE telegram_id = ?",
            (phone, telegram_id),
        )
        await db.commit()


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE is_registered = 1 ORDER BY registered_at DESC"
        ) as cursor:
            return await cursor.fetchall()


async def count_users_by_course():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT course, COUNT(*) as cnt FROM users
               WHERE is_registered = 1 GROUP BY course"""
        ) as cursor:
            return await cursor.fetchall()


async def delete_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


# ---------- Davomat ----------

async def create_attendance_session(code: str, warning_minutes: int, report_minutes: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE attendance_sessions SET is_active = 0 WHERE is_active = 1")
        cursor = await db.execute(
            """INSERT INTO attendance_sessions (code, warning_minutes, report_minutes)
               VALUES (?, ?, ?)""",
            (code, warning_minutes, report_minutes),
        )
        await db.commit()
        return cursor.lastrowid


async def get_active_attendance_session():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM attendance_sessions WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        ) as cursor:
            return await cursor.fetchone()


async def get_attendance_session(session_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM attendance_sessions WHERE id = ?", (session_id,)
        ) as cursor:
            return await cursor.fetchone()


async def close_attendance_session(session_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE attendance_sessions SET is_active = 0 WHERE id = ?", (session_id,)
        )
        await db.commit()


async def has_submitted_attendance(session_id: int, telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM attendance_records WHERE session_id = ? AND telegram_id = ?",
            (session_id, telegram_id),
        ) as cursor:
            return (await cursor.fetchone()) is not None


async def record_attendance(session_id: int, telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO attendance_records (session_id, telegram_id)
               VALUES (?, ?)
               ON CONFLICT(session_id, telegram_id) DO NOTHING""",
            (session_id, telegram_id),
        )
        await db.commit()


async def get_unattended_user_ids(session_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT u.telegram_id FROM users u
               WHERE u.is_registered = 1
                 AND u.telegram_id NOT IN (
                     SELECT telegram_id FROM attendance_records WHERE session_id = ?
                 )""",
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def get_attendance_summary(session_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT u.telegram_id, u.full_name, u.course,
                      CASE WHEN a.telegram_id IS NULL THEN 0 ELSE 1 END AS attended
               FROM users u
               LEFT JOIN attendance_records a
                   ON a.telegram_id = u.telegram_id AND a.session_id = ?
               WHERE u.is_registered = 1
               ORDER BY attended DESC, u.full_name""",
            (session_id,),
        ) as cursor:
            return await cursor.fetchall()


async def get_consecutive_miss_streak(telegram_id: int) -> int:
    """Foydalanuvchi eng oxirgi davomat sessiyasidan boshlab nechta ketma-ket
    qatnashmaganini hisoblaydi (birinchi qatnashgan sessiyada to'xtaydi)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT CASE WHEN a.telegram_id IS NULL THEN 0 ELSE 1 END AS attended
               FROM attendance_sessions s
               LEFT JOIN attendance_records a
                   ON a.session_id = s.id AND a.telegram_id = ?
               ORDER BY s.id DESC""",
            (telegram_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    streak = 0
    for (attended,) in rows:
        if attended:
            break
        streak += 1
    return streak


async def get_attendance_matrix():
    """Barcha davomat sessiyalari, barcha ro'yxatdan o'tgan foydalanuvchilar va
    kim qaysi sessiyada qatnashgani (session_id, telegram_id) juftliklari to'plami."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, code, created_at FROM attendance_sessions ORDER BY id ASC"
        ) as cursor:
            sessions = await cursor.fetchall()

        async with db.execute(
            """SELECT telegram_id, full_name, registered_at FROM users
               WHERE is_registered = 1 ORDER BY registered_at ASC"""
        ) as cursor:
            users = await cursor.fetchall()

        async with db.execute(
            "SELECT session_id, telegram_id FROM attendance_records"
        ) as cursor:
            attended_set = {(row["session_id"], row["telegram_id"]) for row in await cursor.fetchall()}

    return sessions, users, attended_set


async def set_pending_absence_reason(telegram_id: int, session_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO pending_absence_reasons (telegram_id, session_id)
               VALUES (?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET
                   session_id = excluded.session_id,
                   created_at = datetime('now')""",
            (telegram_id, session_id),
        )
        await db.commit()


async def get_pending_absence_reason(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM pending_absence_reasons WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            return await cursor.fetchone()


async def clear_pending_absence_reason(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM pending_absence_reasons WHERE telegram_id = ?", (telegram_id,)
        )
        await db.commit()


# ---------- Maxsus topshiriq ----------

async def create_special_task(name: str, created_by: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE special_tasks SET is_active = 0 WHERE is_active = 1")
        cursor = await db.execute(
            "INSERT INTO special_tasks (name, created_by) VALUES (?, ?)",
            (name, created_by),
        )
        await db.commit()
        return cursor.lastrowid


async def get_active_special_task():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM special_tasks WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        ) as cursor:
            return await cursor.fetchone()


# ---------- Testlar (Mini App) ----------

async def code_exists(code: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM tests WHERE code = ?", (code,)) as cursor:
            return (await cursor.fetchone()) is not None


async def create_test(
    code: str,
    created_by: int,
    answers: dict,
    start_time: str,
    end_time: str,
    name: str = "",
    total_questions: int = 35,
    show_wrong_answers: bool = True,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO tests (code, created_by, answers, start_time, end_time, name, total_questions, show_wrong_answers)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (code, created_by, json.dumps(answers), start_time, end_time, name, total_questions, int(show_wrong_answers)),
        )
        await db.commit()
        return cursor.lastrowid


async def get_test_by_code(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tests WHERE code = ? AND is_active = 1", (code,)
        ) as cursor:
            return await cursor.fetchone()


async def get_test_by_id(test_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tests WHERE id = ?", (test_id,)
        ) as cursor:
            return await cursor.fetchone()


async def get_all_tests(limit: int = 15):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tests ORDER BY id DESC LIMIT ?", (limit,)
        ) as cursor:
            return await cursor.fetchall()


async def get_active_tests_for_students():
    """O'quvchilarga mavzu sifatida ko'rsatiladigan FAOL testlar ro'yxati -
    kod kerak emas, shuning uchun tugagan (deadline o'tgan) testlar ham
    kiradi (kech topshirish 75% bilan hali ham mumkin)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tests WHERE is_active = 1 ORDER BY id ASC"
        ) as cursor:
            return await cursor.fetchall()


async def update_test(
    test_id: int,
    answers: dict,
    start_time: str,
    end_time: str,
    name: str = "",
    total_questions: int = 35,
    show_wrong_answers: bool = True,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE tests SET answers = ?, start_time = ?, end_time = ?, name = ?, total_questions = ?, show_wrong_answers = ?
               WHERE id = ?""",
            (json.dumps(answers), start_time, end_time, name, total_questions, int(show_wrong_answers), test_id),
        )
        await db.commit()


async def set_test_active(test_id: int, is_active: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tests SET is_active = ? WHERE id = ?",
            (1 if is_active else 0, test_id),
        )
        await db.commit()


async def delete_test(test_id: int) -> bool:
    """Testni va unga tegishli barcha natijalarni (test_submissions) butunlay o'chiradi."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM test_submissions WHERE test_id = ?", (test_id,))
        cursor = await db.execute("DELETE FROM tests WHERE id = ?", (test_id,))
        await db.commit()
        return cursor.rowcount > 0


async def get_tests_pending_report():
    now = now_tashkent_str()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM tests
               WHERE is_active = 1 AND (report_sent IS NULL OR report_sent = 0)
                 AND end_time IS NOT NULL AND end_time <= ?""",
            (now,),
        ) as cursor:
            return await cursor.fetchall()


async def mark_test_reported(test_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tests SET report_sent = 1 WHERE id = ?", (test_id,))
        await db.commit()


async def get_test_submissions_with_names(test_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT ts.telegram_id, ts.score, u.full_name
               FROM test_submissions ts
               LEFT JOIN users u ON u.telegram_id = ts.telegram_id
               WHERE ts.test_id = ?
               ORDER BY ts.score DESC""",
            (test_id,),
        ) as cursor:
            return await cursor.fetchall()


async def has_submitted_test(test_id: int, telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM test_submissions WHERE test_id = ? AND telegram_id = ?",
            (test_id, telegram_id),
        ) as cursor:
            return await cursor.fetchone()


async def get_user_test_results(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT t.name, t.code, t.total_questions, ts.score, ts.submitted_at
               FROM test_submissions ts
               JOIN tests t ON t.id = ts.test_id
               WHERE ts.telegram_id = ?
               ORDER BY ts.submitted_at ASC""",
            (telegram_id,),
        ) as cursor:
            return await cursor.fetchall()


async def get_user_aplus_test_results(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT at.name, at.code, at.question_count, aps.score, aps.submitted_at
               FROM aplus_submissions aps
               JOIN aplus_tests at ON at.id = aps.test_id
               WHERE aps.telegram_id = ?
               ORDER BY aps.submitted_at ASC""",
            (telegram_id,),
        ) as cursor:
            return await cursor.fetchall()


async def save_test_submission(test_id: int, telegram_id: int, answers: dict, score: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO test_submissions (test_id, telegram_id, answers, score)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(test_id, telegram_id) DO NOTHING""",
            (test_id, telegram_id, json.dumps(answers), score),
        )
        await db.commit()


# ---------- A+ testlar (yozma javobli, Mini App) ----------

async def aplus_code_exists(code: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM aplus_tests WHERE code = ?", (code,)) as cursor:
            return (await cursor.fetchone()) is not None


async def create_aplus_test(
    code: str,
    created_by: int,
    answers: dict,
    start_time: str,
    end_time: str,
    name: str,
    question_count: int,
    show_wrong_answers: bool = True,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO aplus_tests (code, created_by, answers, start_time, end_time, name, question_count, show_wrong_answers)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (code, created_by, json.dumps(answers), start_time, end_time, name, question_count, int(show_wrong_answers)),
        )
        await db.commit()
        return cursor.lastrowid


async def get_aplus_test_by_code(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM aplus_tests WHERE code = ? AND is_active = 1", (code,)
        ) as cursor:
            return await cursor.fetchone()


async def get_aplus_test_by_id(test_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM aplus_tests WHERE id = ?", (test_id,)
        ) as cursor:
            return await cursor.fetchone()


async def get_all_aplus_tests(limit: int = 15):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM aplus_tests ORDER BY id DESC LIMIT ?", (limit,)
        ) as cursor:
            return await cursor.fetchall()


async def get_active_aplus_tests_for_students():
    """O'quvchilarga mavzu sifatida ko'rsatiladigan FAOL A+ testlar ro'yxati -
    kod kerak emas, tugaganlari ham kiradi (kech topshirish 75% bilan hali
    ham mumkin)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM aplus_tests WHERE is_active = 1 ORDER BY id ASC"
        ) as cursor:
            return await cursor.fetchall()


async def update_aplus_test(
    test_id: int,
    answers: dict,
    start_time: str,
    end_time: str,
    name: str,
    question_count: int,
    show_wrong_answers: bool = True,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE aplus_tests
               SET answers = ?, start_time = ?, end_time = ?, name = ?, question_count = ?, show_wrong_answers = ?
               WHERE id = ?""",
            (json.dumps(answers), start_time, end_time, name, question_count, int(show_wrong_answers), test_id),
        )
        await db.commit()


async def delete_aplus_test(test_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM aplus_submissions WHERE test_id = ?", (test_id,))
        cursor = await db.execute("DELETE FROM aplus_tests WHERE id = ?", (test_id,))
        await db.commit()
        return cursor.rowcount > 0


async def get_aplus_tests_pending_report():
    now = now_tashkent_str()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM aplus_tests
               WHERE is_active = 1 AND (report_sent IS NULL OR report_sent = 0)
                 AND end_time IS NOT NULL AND end_time <= ?""",
            (now,),
        ) as cursor:
            return await cursor.fetchall()


async def mark_aplus_test_reported(test_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE aplus_tests SET report_sent = 1 WHERE id = ?", (test_id,))
        await db.commit()


async def get_aplus_test_submissions_with_names(test_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT ts.telegram_id, ts.score, u.full_name
               FROM aplus_submissions ts
               LEFT JOIN users u ON u.telegram_id = ts.telegram_id
               WHERE ts.test_id = ?
               ORDER BY ts.score DESC""",
            (test_id,),
        ) as cursor:
            return await cursor.fetchall()


async def has_submitted_aplus_test(test_id: int, telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM aplus_submissions WHERE test_id = ? AND telegram_id = ?",
            (test_id, telegram_id),
        ) as cursor:
            return await cursor.fetchone()


async def save_aplus_submission(test_id: int, telegram_id: int, answers: dict, score: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO aplus_submissions (test_id, telegram_id, answers, score)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(test_id, telegram_id) DO NOTHING""",
            (test_id, telegram_id, json.dumps(answers), score),
        )
        await db.commit()


# ---------- Tangalar (davomat + test ballaridan hisoblanadi) ----------

def _streak_bonus(flags) -> int:
    """flags: eng eskisidan boshlab ketma-ket ro'y bergan/bermagan (bool)
    ro'yxati. Ketma-ket "ha" bo'lgan har bir element oldingisidan 1 ball
    ko'p beradi (1, 2, 3, ...); bitta marta "yo'q" bo'lsa, streak yana
    1 dan boshlanadi."""
    streak = 0
    total = 0
    for done in flags:
        if done:
            streak += 1
            total += streak
        else:
            streak = 0
    return total


async def get_user_coins(telegram_id: int) -> dict:
    """Foydalanuvchining tangalarini hisoblaydi:
    - davomat: har bir qatnashgan sessiya uchun flat 1 ball
    - test natijasi: har bir to'g'ri javob uchun 1 ball (test 'score' ustunidan)
    - doimiy ishtirok: testlarni ketma-ket (o'tkazib yubormay) ishlash uchun
      streak bonusi (1, 2, 3, ...; bitta testni ishlamasa yana 1 dan boshlanadi)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM attendance_records WHERE telegram_id = ?",
            (telegram_id,),
        ) as cursor:
            attendance_count = (await cursor.fetchone())[0]

        async with db.execute(
            "SELECT id FROM tests ORDER BY id ASC"
        ) as cursor:
            test_ids = [row[0] for row in await cursor.fetchall()]

        async with db.execute(
            "SELECT test_id FROM test_submissions WHERE telegram_id = ?",
            (telegram_id,),
        ) as cursor:
            submitted_test_ids = {row[0] for row in await cursor.fetchall()}

        async with db.execute(
            "SELECT COALESCE(SUM(score), 0) FROM test_submissions WHERE telegram_id = ?",
            (telegram_id,),
        ) as cursor:
            test_coins = (await cursor.fetchone())[0]

        async with db.execute(
            "SELECT COALESCE(SUM(delta), 0) FROM score_adjustments WHERE telegram_id = ?",
            (telegram_id,),
        ) as cursor:
            adjustment_coins = (await cursor.fetchone())[0]

    attendance_coins = attendance_count
    test_streak_coins = _streak_bonus([tid in submitted_test_ids for tid in test_ids])

    return {
        "attendance_count": attendance_count,
        "attendance_coins": attendance_coins,
        "test_coins": test_coins,
        "test_streak_coins": test_streak_coins,
        "adjustment_coins": adjustment_coins,
        "total": attendance_coins + test_coins + test_streak_coins + adjustment_coins,
    }


async def get_leaderboard(limit: int = 50):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT telegram_id, full_name FROM users WHERE is_registered = 1"
        ) as cursor:
            users = await cursor.fetchall()

        async with db.execute(
            "SELECT telegram_id, COUNT(*) AS cnt FROM attendance_records GROUP BY telegram_id"
        ) as cursor:
            attendance_counts = {row["telegram_id"]: row["cnt"] for row in await cursor.fetchall()}

        async with db.execute(
            "SELECT id FROM tests ORDER BY id ASC"
        ) as cursor:
            test_ids = [row[0] for row in await cursor.fetchall()]

        async with db.execute(
            "SELECT test_id, telegram_id FROM test_submissions"
        ) as cursor:
            submitted_set = {(row["test_id"], row["telegram_id"]) for row in await cursor.fetchall()}

        async with db.execute(
            "SELECT telegram_id, SUM(score) AS total_score FROM test_submissions GROUP BY telegram_id"
        ) as cursor:
            test_scores = {row["telegram_id"]: row["total_score"] for row in await cursor.fetchall()}

        async with db.execute(
            "SELECT telegram_id, SUM(delta) AS total_delta FROM score_adjustments GROUP BY telegram_id"
        ) as cursor:
            adjustments = {row["telegram_id"]: row["total_delta"] for row in await cursor.fetchall()}

    leaderboard = []
    for u in users:
        tid = u["telegram_id"]
        attendance_coins = attendance_counts.get(tid, 0)
        test_streak_coins = _streak_bonus([(test_id, tid) in submitted_set for test_id in test_ids])
        coins = attendance_coins + test_scores.get(tid, 0) + test_streak_coins + adjustments.get(tid, 0)
        leaderboard.append({"telegram_id": tid, "full_name": u["full_name"], "coins": coins})

    leaderboard.sort(key=lambda r: (-r["coins"], r["full_name"] or ""))
    return leaderboard[:limit]


# ---------- Rejalashtirilgan xabar (haftalik broadcast) ----------

async def get_broadcast_schedule():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM broadcast_schedule WHERE id = 1"
        ) as cursor:
            return await cursor.fetchone()


async def save_broadcast_schedule(
    message: str, day_of_week: int, time_of_day: str, enabled: bool, updated_by: int
):
    """Sozlamalar har safar saqlanganda `last_sent_week` ni ham tozalaydi —
    aks holda admin xabar/vaqtni o'zgartirsa ham, shu hafta uchun "allaqachon
    yuborilgan" deb hisoblanib, yangi sozlama hech qachon jo'natilmasdi."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO broadcast_schedule
                   (id, message, day_of_week, time_of_day, enabled, updated_by, updated_at, last_sent_week)
               VALUES (1, ?, ?, ?, ?, ?, datetime('now'), NULL)
               ON CONFLICT(id) DO UPDATE SET
                   message = excluded.message,
                   day_of_week = excluded.day_of_week,
                   time_of_day = excluded.time_of_day,
                   enabled = excluded.enabled,
                   updated_by = excluded.updated_by,
                   last_sent_week = NULL,
                   updated_at = excluded.updated_at""",
            (message, day_of_week, time_of_day, int(enabled), updated_by),
        )
        await db.commit()


async def mark_broadcast_sent(week_key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE broadcast_schedule SET last_sent_week = ? WHERE id = 1", (week_key,)
        )
        await db.commit()


async def set_broadcast_schedule_file(file_data: str | None, file_name: str | None, updated_by: int):
    """Rejalashtirilgan xabarga PDF (yoki boshqa fayl) biriktiradi/olib tashlaydi
    (file_data=None bo'lsa - olib tashlash). Agar hali umuman sozlama
    saqlanmagan bo'lsa (birinchi marta), bo'sh qiymatlar bilan qator yaratadi -
    admin keyinroq matn/kun/vaqtni "⚙️ Sozlamalar"dan to'ldirishi mumkin."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO broadcast_schedule
                   (id, message, day_of_week, time_of_day, enabled, updated_by, updated_at, file_data, file_name)
               VALUES (1, '', 0, '09:00', 0, ?, datetime('now'), ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   file_data = excluded.file_data,
                   file_name = excluded.file_name,
                   updated_by = excluded.updated_by,
                   updated_at = excluded.updated_at""",
            (updated_by, file_data, file_name),
        )
        await db.commit()


# ---------- Haftalik hisobot rejasi (haqiqiy test natijalari asosida) ----------
# Bir nechta kun/vaqt qo'shish mumkin (masalan har Dushanba VA har Juma).

async def get_report_schedules():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM report_schedule ORDER BY day_of_week, time_of_day"
        ) as cursor:
            return await cursor.fetchall()


async def add_report_schedule(day_of_week: int, time_of_day: str, enabled: bool, updated_by: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO report_schedule (day_of_week, time_of_day, enabled, updated_by, updated_at)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (day_of_week, time_of_day, int(enabled), updated_by),
        )
        await db.commit()
        return cursor.lastrowid


async def update_report_schedule(schedule_id: int, day_of_week: int, time_of_day: str, enabled: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE report_schedule SET day_of_week = ?, time_of_day = ?, enabled = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (day_of_week, time_of_day, int(enabled), schedule_id),
        )
        await db.commit()


async def delete_report_schedule(schedule_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM report_schedule WHERE id = ?", (schedule_id,))
        await db.commit()


async def get_report_last_sent_at() -> str | None:
    return await get_setting("report_last_sent_at")


async def mark_report_sent(sent_at_iso: str):
    await set_setting("report_last_sent_at", sent_at_iso)


async def get_submissions_since(since_iso: str):
    """Berilgan vaqtdan keyin topshirilgan BARCHA natijalarni (oddiy test +
    A+ test) birlashtirib qaytaradi - har biri qaysi "mavzu"ga (testga)
    tegishli ekani va kimning natijasi ekani bilan birga. Haftalik hisobot
    PDF'ini shundan yig'iladi."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT 'oddiy' AS kind, t.id AS test_id, COALESCE(t.name, t.code) AS test_name,
                      t.created_at AS test_created_at, ts.telegram_id, u.full_name,
                      ts.score, t.total_questions AS max_score, ts.submitted_at
               FROM test_submissions ts
               JOIN tests t ON t.id = ts.test_id
               LEFT JOIN users u ON u.telegram_id = ts.telegram_id
               WHERE ts.submitted_at > ?
               UNION ALL
               SELECT 'aplus' AS kind, at.id AS test_id, COALESCE(at.name, at.code) AS test_name,
                      at.created_at AS test_created_at, aps.telegram_id, u.full_name,
                      aps.score, at.question_count * 2 AS max_score, aps.submitted_at
               FROM aplus_submissions aps
               JOIN aplus_tests at ON at.id = aps.test_id
               LEFT JOIN users u ON u.telegram_id = aps.telegram_id
               WHERE aps.submitted_at > ?
               ORDER BY test_created_at, submitted_at""",
            (since_iso, since_iso),
        ) as cursor:
            return await cursor.fetchall()


# ---------- Yangi faollashtirilgan mavzular haqida xabar berish ----------

async def get_unnotified_tests():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tests WHERE is_active = 1 AND (notified IS NULL OR notified = 0)"
        ) as cursor:
            return await cursor.fetchall()


async def mark_test_notified(test_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tests SET notified = 1 WHERE id = ?", (test_id,))
        await db.commit()


async def get_unnotified_aplus_tests():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM aplus_tests WHERE is_active = 1 AND (notified IS NULL OR notified = 0)"
        ) as cursor:
            return await cursor.fetchall()


async def mark_aplus_test_notified(test_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE aplus_tests SET notified = 1 WHERE id = ?", (test_id,))
        await db.commit()


async def get_unnotified_special_tasks():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM special_tasks WHERE is_active = 1 AND (notified IS NULL OR notified = 0)"
        ) as cursor:
            return await cursor.fetchall()


async def mark_special_task_notified(task_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE special_tasks SET notified = 1 WHERE id = ?", (task_id,))
        await db.commit()
