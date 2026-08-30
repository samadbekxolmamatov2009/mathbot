from fastapi import APIRouter, Depends, HTTPException, status

from . import models
from .deps import require_admin
from .turso_client import query_turso, TursoNotConfigured

router = APIRouter(tags=["turso"])


@router.get("/admin/students")
async def list_students(_admin: models.User = Depends(require_admin)):
    """
    Botda ro'yxatdan o'tgan barcha o'quvchilarni qaytaradi (faqat admin ko'ra oladi).
    Manba: Turso'dagi 'users' jadvali (botning o'zi).
    """
    try:
        return await query_turso(
            "SELECT telegram_id, full_name, course, region, district, phone, "
            "registered_at, role FROM users ORDER BY registered_at DESC"
        )
    except TursoNotConfigured as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.get("/public/stats")
async def public_stats():
    """
    Sayt bosh sahifasidagi statistika uchun (login talab qilinmaydi).
    Faqat sonlar qaytadi — hech qanday shaxsiy ma'lumot (ism, telefon) yo'q.
    """
    try:
        students = await query_turso("SELECT COUNT(*) AS cnt FROM users")
        # 'aplus_submissions' — A+ darajadagi testni topshirganlar (taxminiy "sertifikat olganlar")
        certs = await query_turso("SELECT COUNT(DISTINCT telegram_id) AS cnt FROM aplus_submissions")
        return {
            "students": students[0]["cnt"] if students else 0,
            "certificates": certs[0]["cnt"] if certs else 0,
        }
    except TursoNotConfigured:
        # Turso hali sozlanmagan bo'lsa ham sayt ishlashda davom etsin — 0 qaytaramiz
        return {"students": 0, "certificates": 0}