"""aiosqlite bilan bir xil (async context-manager) interfeys beruvchi
moslashtiruvchi qatlam - database.py bitta qatorini o'zgartirib, ikkita
rejimdan birini tanlaydi:

- TURSO_DATABASE_URL sozlangan bo'lsa: Turso (libSQL, tarmoq orqali) -
  Render'da bir nechta alohida service (botlar + Mini App backend) BIR
  XIL bazani ko'rishi uchun shu kerak, chunki ular alohida konteynerlarda
  ishlaydi va oddiy SQLite fayl bilan bazani bo'lisha olmaydi.
- Aks holda: oddiy mahalliy aiosqlite (fayl asosidagi SQLite) - lokal
  ishlab chiqishda hech narsa o'zgarmaydi, Turso hisobi shart emas.

database.py'dagi barcha SQL so'rovlar (AUTOINCREMENT, INSERT OR IGNORE,
datetime('now') va h.k.) ikkala rejimda ham o'zgarishsiz ishlaydi, chunki
Turso SQLite bilan wire-protocol darajasida mos.
"""

from config import TURSO_DATABASE_URL, TURSO_AUTH_TOKEN

if TURSO_DATABASE_URL:
    import libsql_client

    # Turso dashboard/CLI har doim "libsql://" manzilini ko'rsatadi, lekin
    # shu Python client kutubxonasida "libsql://" -> WebSocket (wss://)
    # protokoliga aylanadi va Turso serveri bilan handshake xatosi beradi.
    # "https://" (oddiy HTTP protokol) esa ishonchli ishlaydi - shuning
    # uchun manzil qanday kiritilishidan qat'iy nazar shu yerda avtomatik
    # to'g'irlanadi.
    _RESOLVED_URL = TURSO_DATABASE_URL.replace("libsql://", "https://", 1)

    class _Cursor:
        def __init__(self, result_set):
            self._rows = iter(result_set.rows)
            self.lastrowid = result_set.last_insert_rowid
            self.rowcount = result_set.rows_affected

        async def fetchone(self):
            return next(self._rows, None)

        async def fetchall(self):
            return list(self._rows)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _ExecuteAwaitable:
        """db.execute(...) natijasi - aiosqlite'dagi kabi ham to'g'ridan-to'g'ri
        await qilinadi ("await db.execute(...)"), ham "async with db.execute(...)
        as cursor:" ko'rinishida ishlatiladi - shu ikkalasi ham database.py'da
        qo'llanilgani uchun ikkalasini ham qo'llab-quvvatlash shart."""

        def __init__(self, client, sql, params):
            self._client = client
            self._sql = sql
            self._params = params

        async def _run(self):
            result = await self._client.execute(
                self._sql, list(self._params) if self._params else []
            )
            return _Cursor(result)

        def __await__(self):
            return self._run().__await__()

        async def __aenter__(self):
            self._cursor = await self._run()
            return self._cursor

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class Connection:
        def __init__(self):
            self._client = libsql_client.create_client(
                url=_RESOLVED_URL, auth_token=TURSO_AUTH_TOKEN
            )
            # Moslik uchun saqlanadi (aiosqlite'da "db.row_factory = aiosqlite.Row"
            # deb yoziladi) - Turso qatorlari indeks va nom orqali ham allaqachon
            # ochiladigan bo'lgani uchun bu qiymat hech qayerda ishlatilmaydi.
            self.row_factory = None

        def execute(self, sql, params=()):
            return _ExecuteAwaitable(self._client, sql, params)

        async def commit(self):
            pass  # Turso har bir execute()ni darhol, alohida yozadi

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            await self._client.close()
            return False

    def connect(_ignored_path=None):
        return Connection()

    Row = None

else:
    from aiosqlite import connect, Row  # noqa: F401
