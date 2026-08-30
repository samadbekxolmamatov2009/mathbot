# MatematikaPro — Auth Backend

Ro'yxatdan o'tish va login uchun FastAPI backend. Telefon raqam (+998...) orqali
hisob ochiladi, parollar bcrypt bilan hash qilinadi, kirish uchun JWT token beriladi.

## Ishga tushirish

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # natijani SECRET_KEY ga qo'ying

uvicorn app.main:app --reload --port 8000
```

Swagger hujjatlari: `http://localhost:8000/docs`

## API

| Endpoint         | Metod | Tavsif                                  | Himoya               |
|-------------------|-------|------------------------------------------|-----------------------|
| `/auth/register`  | POST  | Yangi hisob (F.I.Sh, telefon, parol)     | 5 urinish/daqiqa (IP) |
| `/auth/login`     | POST  | Kirish, JWT token qaytaradi              | 10 urinish/daqiqa (IP)|
| `/auth/me`        | GET   | Joriy foydalanuvchi ma'lumoti            | Bearer token talab qilinadi |
| `/health`         | GET   | Server ishlayaptimi tekshirish           | —                     |

**Register so'rovi:**
```json
{
  "full_name": "Aziz Karimov",
  "phone": "+998901234567",
  "password": "kamida8ta1",
  "role": "student",
  "region": "Toshkent",
  "district": "Chilonzor"
}
```

**Login so'rovi:**
```json
{ "phone": "+998901234567", "password": "kamida8ta1" }
```
Javob: `{ "access_token": "...", "token_type": "bearer" }` — bu tokenni keyingi
so'rovlarda `Authorization: Bearer <token>` header orqali yuboriladi.

## Xavfsizlik — nima qilingan

- **Parollar hech qachon ochiq saqlanmaydi** — faqat bcrypt hash (`security.py`).
  Ma'lumotlar bazasi o'g'irlansa ham, parollarning o'zi chiqmaydi.
- **JWT maxfiy kalit** kodda emas, `.env` faylda (`.env` `.gitignore`ga qo'shilgan —
  GitHub'ga hech qachon push qilmang).
- **Umumiy xato xabarlari**: login xato bo'lganda "raqam topilmadi" va "parol xato"
  ajratilmaydi — bo'lmasa, hujumchi qaysi raqamlar ro'yxatdan o'tganini bilib olardi.
  Xuddi shu sabab bilan ro'yxatdan o'tishda ham telefon band bo'lsa umumiy xabar beriladi.
- **Rate limiting** (`slowapi`): bitta IP login/register'ga daqiqasiga cheklangan
  marta murojaat qila oladi — parol taxmin qilish (brute-force) va bot-spam sekinlashadi.
- **CORS** faqat `.env`dagi `ALLOWED_ORIGINS`ga ruxsat beradi — boshqa saytlar
  brauzerdan to'g'ridan-to'g'ri API'ga so'rov yubora olmaydi.
- **Xavfsizlik headerlari** (`X-Frame-Options`, `X-Content-Type-Options`,
  `Referrer-Policy`) har bir javobga avtomatik qo'shiladi.
- **Validatsiya**: telefon format (`+998XXXXXXXXX`), parol kamida 8 belgi + harf +
  raqam, foydalanuvchi ro'yxatdan o'tishda o'zini "admin" qilib belgilay olmaydi.

## Hali qilinmagan, lekin productionga chiqishdan oldin kerak bo'ladigan narsalar

1. **HTTPS** — serverni domenga ulaganda albatta Let's Encrypt (masalan Caddy yoki
   Nginx + certbot) bilan SSL o'rnating. HTTPS'siz parollar tarmoqda ochiq ketadi.
2. **Telefonni tasdiqlash (OTP/SMS)** — hozir istalgan raqam bilan ro'yxatdan o'tish
   mumkin. Eskiz.uz yoki Play Mobile kabi O'zbek SMS xizmati orqali kod yuborish
   qo'shilsa, soxta hisoblar oldini oladi.
3. **PostgreSQL'ga o'tish** — SQLite yagona serverga yetadi, lekin foydalanuvchilar
   ko'paysa (yoki bir nechta server bo'lsa) PostgreSQL kerak bo'ladi. `.env`dagi
   `DATABASE_URL`ni o'zgartirish yetarli, kod deyarli o'zgarmaydi.
4. **Refresh token** — hozir token 24 soatdan keyin tugaydi, foydalanuvchi qayta
   login qiladi. Uzoqroq sessiyalar kerak bo'lsa, refresh token flow qo'shiladi.
5. **Parolni unutdim** — SMS orqali parolni tiklash oqimi.
6. **Loglash/monitoring** — kim qachon kirganini kuzatish uchun (masalan Sentry).

Bularning har birini alohida so'rasangiz, keyingi bosqichda qo'shib boraveramiz —
hozircha eng zarur qismi (ro'yxatdan o'tish + login + parol xavfsizligi) tayyor va
sinovdan o'tkazildi.
