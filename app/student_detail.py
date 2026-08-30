from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db
from .deps import require_admin
from .turso_client import query_turso, TursoNotConfigured

router = APIRouter(tags=["student-detail"])


@router.get("/admin/students/{telegram_id}/detail")
async def student_detail(telegram_id: int, _admin: models.User = Depends(require_admin)):
    """
    Bitta o'quvchi haqida ma'lumot: oddiy testlar, A+ testlar, davomat.
    Hammasi Turso'dan (faqat o'qish).

    Eslatma: 'score_adjustments' (ball tuzatishlari) ATAYLAB bu yerga
    qo'shilmagan — bu ma'lumot maxfiy va faqat cofounderlar uchun,
    oddiy admin panelida umuman ko'rsatilmaydi.
    """
    try:
        test_results = await query_turso(
            "SELECT t.name AS test_name, t.total_questions, ts.score, ts.submitted_at "
            "FROM test_submissions ts JOIN tests t ON ts.test_id = t.id "
            "WHERE ts.telegram_id = ? ORDER BY ts.submitted_at DESC",
            (telegram_id,),
        )

        aplus_results = await query_turso(
            "SELECT at.name AS test_name, at.question_count, aps.score, aps.submitted_at "
            "FROM aplus_submissions aps JOIN aplus_tests at ON aps.test_id = at.id "
            "WHERE aps.telegram_id = ? ORDER BY aps.submitted_at DESC",
            (telegram_id,),
        )

        attendance = await query_turso(
            "SELECT s.id AS session_id, s.code, s.created_at, "
            "CASE WHEN r.telegram_id IS NOT NULL THEN 1 ELSE 0 END AS attended "
            "FROM attendance_sessions s "
            "LEFT JOIN attendance_records r ON r.session_id = s.id AND r.telegram_id = ? "
            "ORDER BY s.created_at DESC",
            (telegram_id,),
        )

        return {
            "test_results": test_results,
            "aplus_results": aplus_results,
            "attendance": attendance,
        }
    except TursoNotConfigured:
        return {"test_results": [], "aplus_results": [], "attendance": []}


@router.get("/admin/students/{telegram_id}/notes", response_model=list[schemas.NoteOut])
def list_notes(
    telegram_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    return (
        db.query(models.StudentNote)
        .filter(models.StudentNote.telegram_id == telegram_id)
        .order_by(models.StudentNote.created_at.desc())
        .all()
    )


@router.post("/admin/students/{telegram_id}/notes", response_model=schemas.NoteOut, status_code=201)
def add_note(
    telegram_id: int,
    payload: schemas.NoteCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    note = models.StudentNote(
        telegram_id=telegram_id,
        author_name=admin.full_name,
        note=payload.note,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note