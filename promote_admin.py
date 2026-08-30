"""
Birinchi admin hisobni yaratish uchun bir martalik skript.
Ishlatish: python promote_admin.py +998901234567
"""
import sys

from app.database import SessionLocal
from app.models import User, UserRole


def main():
    if len(sys.argv) != 2:
        print("Ishlatish: python promote_admin.py +998901234567")
        sys.exit(1)

    phone = sys.argv[1].strip()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone == phone).first()
        if user is None:
            print(f"Xato: {phone} raqamli foydalanuvchi topilmadi. Avval saytda ro'yxatdan o'ting.")
            sys.exit(1)

        user.role = UserRole.admin
        db.commit()
        print(f"OK: {user.full_name} ({user.phone}) endi admin.")
    finally:
        db.close()


if __name__ == "__main__":
    main()