import re
from datetime import datetime

from pydantic import BaseModel, field_validator, ConfigDict

from .models import UserRole

PHONE_RE = re.compile(r"^\+998\d{9}$")


class UserRegister(BaseModel):
    full_name: str
    phone: str
    password: str
    role: UserRole = UserRole.student
    region: str | None = None
    district: str | None = None

    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Ism-familiya kamida 3 ta belgidan iborat bo'lishi kerak")
        return v

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: str) -> str:
        v = v.strip().replace(" ", "")
        if not PHONE_RE.match(v):
            raise ValueError("Telefon raqam +998XXXXXXXXX formatida bo'lishi kerak")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Parol kamida 8 ta belgidan iborat bo'lishi kerak")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Parolda kamida bitta harf va bitta raqam bo'lishi kerak")
        return v

    @field_validator("role")
    @classmethod
    def block_self_admin(cls, v: UserRole) -> UserRole:
        if v == UserRole.admin:
            raise ValueError("Bu rolni tanlash mumkin emas")
        return v


class UserLogin(BaseModel):
    phone: str
    password: str

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: str) -> str:
        return v.strip().replace(" ", "")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    phone: str
    role: UserRole
    region: str | None
    district: str | None
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CourseCreate(BaseModel):
    title: str
    description: str | None = None
    group_link: str | None = None
    sort_order: int = 0

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Kurs nomi kamida 2 ta belgidan iborat bo'lishi kerak")
        return v


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    group_link: str | None
    is_active: bool
    sort_order: int
    created_at: datetime


class NoteCreate(BaseModel):
    note: str

    @field_validator("note")
    @classmethod
    def note_not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1:
            raise ValueError("Izoh bo'sh bo'lishi mumkin emas")
        return v


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    author_name: str
    note: str
    created_at: datetime