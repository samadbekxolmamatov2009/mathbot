from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db
from .deps import require_admin

router = APIRouter(tags=["courses"])


@router.get("/courses", response_model=list[schemas.CourseOut])
def list_courses(db: Session = Depends(get_db)):
    return (
        db.query(models.Course)
        .filter(models.Course.is_active.is_(True))
        .order_by(models.Course.sort_order, models.Course.id)
        .all()
    )


@router.post("/admin/courses", response_model=schemas.CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: schemas.CourseCreate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    course = models.Course(**payload.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("/admin/courses", response_model=list[schemas.CourseOut])
def list_courses_admin(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    return db.query(models.Course).order_by(models.Course.sort_order, models.Course.id).all()


@router.delete("/admin/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kurs topilmadi")
    db.delete(course)
    db.commit()