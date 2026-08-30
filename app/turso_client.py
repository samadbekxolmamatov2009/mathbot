"""
Botning Turso (libSQL) bazasiga so'rov yuborish uchun yordamchi funksiya.

TURSO_DATABASE_URL va TURSO_AUTH_TOKEN backend'ning `.env` faylida bo'lishi kerak.
Bu qiymatlar bot uchun ishlatilayotgan bazaning O'ZI — botning kodini o'zgartirish
shart emas, biz faqat o'qish (SELECT) uchun ulanamiz.
"""
import libsql_client

from .config import settings


class TursoNotConfigured(Exception):
    pass


async def query_turso(sql: str, params: tuple = ()) -> list[dict]:
    """
    SQL so'rovni Turso'da bajaradi va natijani lug'atlar ro'yxati sifatida qaytaradi
    (masalan: [{"full_name": "Aziz", "phone": "+998..."}, ...]).
    """
    if not settings.turso_database_url or not settings.turso_auth_token:
        raise TursoNotConfigured(
            "TURSO_DATABASE_URL yoki TURSO_AUTH_TOKEN backend .env faylida sozlanmagan"
        )

    client = libsql_client.create_client(
        url=settings.turso_database_url,
        auth_token=settings.turso_auth_token,
    )
    try:
        result = await client.execute(sql, params)
        columns = result.columns
        return [dict(zip(columns, row)) for row in result.rows]
    finally:
        await client.close()