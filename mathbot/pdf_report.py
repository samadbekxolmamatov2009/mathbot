"""Haftalik hisobot PDF generatori.

Hozircha talabalar ballari statik namuna sifatida keltirilgan
(SAMPLE_SCORES). Kelajakda bu ma'lumotlar bazadan yoki tashqi
fayldan o'qib olinadigan qilib almashtirilishi mumkin.
"""

from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

MONTHS_UZ = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr",
]

HEADER_BLUE = colors.HexColor("#2E5C8C")
HEADER_GREEN = colors.HexColor("#2F7D4F")
TITLE_COLOR = colors.HexColor("#1F3864")
SUBTITLE_COLOR = colors.HexColor("#555555")
ROW_ALT = colors.HexColor("#EAF2FB")
ROW_WHITE = colors.white
BORDER = colors.HexColor("#B7C6D9")
TEXT_DARK = colors.HexColor("#1A1A1A")

COLUMNS = [
    ("Talaba", "horizontal"),
    ("1-mavzu (1-2-mbtlar)", "vertical"),
    ("2-mavzu (3-4-mbtlar)", "vertical"),
    ("3-vazifa (5-6-7 MS mbtlar)", "vertical"),
    ("Umumiy o'rtacha", "horizontal"),
]

# (Ism, 1-mavzu, 2-mavzu, 3-vazifa)
SAMPLE_SCORES = [
    ("Achilova Mohinur", 29, 30, 27),
    ("Serjanov Davronbek Kengesbayevich", 29, 30, 27),
    ("Qurbonova Shahzoda Alisher qizi", 26, 30, 29),
    ("Istamova Sunbulxonim Jasurovna", 26, 28, 30),
    ("Abdujamilov Azizbek Abror o'g'li", 24, 29, 28),
    ("Nasullayeva Nigora Zokirovna", 28, 30, 23),
    ("Oltiyev Quvonch O'ktamovich", 24, 29, 28),
    ("Rejabova Nigina Rashid qizi", 21, 30, 30),
    ("Mirabdullayev Asadbek", 28, 28, 24),
    ("Navro'zova Gulbahor", 26, 30, 24),
    ("Xamdullayeva Nargiza", 27, 30, 23),
    ("Nurillayeva Kamola", 27, 28, 22),
    ("Egamberdiyev Mansurbek Tursunovich", 23, 26, 27),
    ("Normuradova Binafsha Nodirbekovna", 20, 26, 29),
    ("Murotqobilova Bahora", 23, 28, 24),
    ("Bahodirov Behruz Oybekovich", 23, 23, 28),
    ("Asilbek Ismoilov", 21, 26, 27),
    ("Abrorbek Eshnazarov Xurshidovich", 26, 27, 20),
    ("Sharipova Nafosat", 25, 28, 20),
    ("Mamatqulova Muhiba", 19, 26, 28),
    ("Tursunova Zohida", 24, 22, 27),
    ("Shaxzod Umarov Ulug'bekovich", 24, 24, 23),
    ("Umarova Mahtuma Rustamovna", 25, 20, 26),
]


def _wrap_text(c: canvas.Canvas, text: str, font: str, size: int, max_width: float):
    words = text.split()
    lines = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if c.stringWidth(candidate, font, size) <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def generate_period_report(
    output_path: str,
    rows,
    since: datetime,
    until: datetime = None,
    group: str = "Turbo 4.0 Muhokama",
    course: str = "Turbo 4.0 MS",
) -> str:
    """Berilgan davr ichida (since - until) topshirilgan test/A+ natijalari
    asosida haqiqiy "Haftalik hisobot" PDF yaratadi.

    rows: database.get_submissions_since() natijasi - har biri (kind,
    test_id, test_name, telegram_id, full_name, score, max_score,
    submitted_at) maydonlariga ega. Har bir noyob test_name bitta "mavzu"
    ustuni bo'ladi (nechta mavzu bo'lsa - shuncha ustun, statik emas).
    """
    until = until or datetime.now()
    date_str = until.strftime("%d.%m.%Y")
    period = f"{since.strftime('%d.%m.%Y')} — {until.strftime('%d.%m.%Y')}"

    # Mavzularni (testlarni) birinchi paydo bo'lish tartibida yig'amiz.
    topic_order: list[str] = []
    for r in rows:
        if r["test_name"] not in topic_order:
            topic_order.append(r["test_name"])

    # Talaba -> {mavzu_nomi: ball}
    students: dict[int, dict] = {}
    for r in rows:
        tid = r["telegram_id"]
        if tid not in students:
            students[tid] = {"name": r["full_name"] or f"ID {tid}", "scores": {}}
        # Bir talaba bitta mavzuni faqat bir marta topshiradi (UNIQUE
        # constraint), shuning uchun to'g'ridan-to'g'ri yozib qo'yamiz.
        students[tid]["scores"][r["test_name"]] = r["score"]

    if not topic_order or not students:
        # Ma'lumot yo'q bo'lsa ham, bo'sh (lekin tushunarli) PDF chiqaramiz.
        topic_order = topic_order or ["Mavzu yo'q"]

    rows_out = []
    for tid, data in students.items():
        scores = [data["scores"].get(topic) for topic in topic_order]
        total = sum(s for s in scores if s is not None)
        rows_out.append((data["name"], scores, total))
    rows_out.sort(key=lambda r: -r[2])

    columns = [("Talaba", "horizontal")] + [(t, "vertical") for t in topic_order] + [("Jami ball", "horizontal")]

    page_w, page_h = landscape(A4)
    margin = 30
    table_w = page_w - 2 * margin
    name_w = table_w * 0.30
    total_w = table_w * 0.12
    other_count = len(topic_order)
    other_w = (table_w - name_w - total_w) / max(other_count, 1)
    col_widths = [name_w] + [other_w] * other_count + [total_w]

    header_h = 100
    row_h = 16
    title_h = 26

    table_top = page_h - margin - title_h - 20
    table_left = margin

    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    c.setStrokeColor(BORDER)

    c.setFillColor(TITLE_COLOR)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(page_w / 2, page_h - margin - 14, "HAFTALIK HISOBOT")

    c.setFillColor(SUBTITLE_COLOR)
    c.setFont("Helvetica", 9)
    subtitle = f"Guruh: {group} | Kurs: {course} | Davr: {period} | Sana: {date_str}"
    c.drawCentredString(page_w / 2, page_h - margin - title_h, subtitle)

    y = table_top
    x = table_left
    for (label, orientation), w in zip(columns, col_widths):
        c.setFillColor(HEADER_GREEN if label == "Jami ball" else HEADER_BLUE)
        c.rect(x, y - header_h, w, header_h, fill=1, stroke=1)

        c.setFillColor(colors.white)
        if orientation == "horizontal":
            c.setFont("Helvetica-Bold", 8)
            lines = _wrap_text(c, label, "Helvetica-Bold", 8, w - 10)
            total_h = len(lines) * 10
            start_y = y - header_h / 2 + total_h / 2 - 8
            for i, line in enumerate(lines):
                c.drawCentredString(x + w / 2, start_y - i * 10, line)
        else:
            c.setFont("Helvetica-Bold", 7)
            c.saveState()
            c.translate(x + w / 2, y - header_h / 2)
            c.rotate(90)
            c.drawCentredString(0, 0, label[:40])
            c.restoreState()
        x += w

    y = table_top - header_h
    for idx, (name, scores, total) in enumerate(rows_out):
        band = ROW_ALT if idx % 2 == 0 else ROW_WHITE
        x = table_left
        values = [name] + [("-" if s is None else str(s)) for s in scores] + [str(total)]
        for col_idx, (w, value) in enumerate(zip(col_widths, values)):
            c.setFillColor(band)
            c.rect(x, y - row_h, w, row_h, fill=1, stroke=1)
            c.setFillColor(TEXT_DARK)
            c.setFont("Helvetica", 8)
            if col_idx == 0:
                c.drawString(x + 6, y - row_h + 5, value[:45])
            else:
                c.drawCentredString(x + w / 2, y - row_h + 5, value)
            x += w
        y -= row_h

        if y - row_h < margin:
            c.showPage()
            c.setStrokeColor(BORDER)
            y = page_h - margin

    c.showPage()
    c.save()
    return output_path


def generate_weekly_report(
    output_path: str,
    group: str = "Turbo 4.0 Muhokama",
    course: str = "Turbo 4.0 MS",
    generated_at: datetime = None,
) -> str:
    """ESKI (namuna ma'lumotli) hisobot - endi ishlatilmaydi, faqat orqaga
    moslik uchun saqlangan. Haqiqiy hisobot uchun generate_period_report()
    ishlatiladi (main.py'dagi report_schedule loop shuni chaqiradi)."""
    generated_at = generated_at or datetime.now()
    period = f"{MONTHS_UZ[generated_at.month - 1]} {generated_at.year}"
    date_str = generated_at.strftime("%d.%m.%Y")

    rows = [
        (name, m1, m2, m3, round((m1 + m2 + m3) / 3, 1))
        for name, m1, m2, m3 in SAMPLE_SCORES
    ]

    page_w, page_h = landscape(A4)
    margin = 30
    table_w = page_w - 2 * margin
    name_w = table_w * 0.34
    other_w = (table_w - name_w) / 4
    col_widths = [name_w, other_w, other_w, other_w, other_w]

    header_h = 100
    row_h = 16
    title_h = 26

    table_top = page_h - margin - title_h - 20
    table_left = margin

    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    c.setStrokeColor(BORDER)

    # Sarlavha
    c.setFillColor(TITLE_COLOR)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(page_w / 2, page_h - margin - 14, "HAFTALIK HISOBOT")

    c.setFillColor(SUBTITLE_COLOR)
    c.setFont("Helvetica", 9)
    subtitle = f"Guruh: {group} | Kurs: {course} | Davr: {period} | Sana: {date_str}"
    c.drawCentredString(page_w / 2, page_h - margin - title_h, subtitle)

    # Header qatori
    y = table_top
    x = table_left
    for (label, orientation), w in zip(COLUMNS, col_widths):
        c.setFillColor(HEADER_GREEN if label == "Umumiy o'rtacha" else HEADER_BLUE)
        c.rect(x, y - header_h, w, header_h, fill=1, stroke=1)

        c.setFillColor(colors.white)
        if orientation == "horizontal":
            c.setFont("Helvetica-Bold", 8)
            lines = _wrap_text(c, label, "Helvetica-Bold", 8, w - 10)
            total_h = len(lines) * 10
            start_y = y - header_h / 2 + total_h / 2 - 8
            for i, line in enumerate(lines):
                c.drawCentredString(x + w / 2, start_y - i * 10, line)
        else:
            c.setFont("Helvetica-Bold", 7)
            c.saveState()
            c.translate(x + w / 2, y - header_h / 2)
            c.rotate(90)
            c.drawCentredString(0, 0, label)
            c.restoreState()
        x += w

    # Ma'lumot qatorlari
    y = table_top - header_h
    for idx, (name, m1, m2, m3, avg) in enumerate(rows):
        band = ROW_ALT if idx % 2 == 0 else ROW_WHITE
        x = table_left
        values = [name, str(m1), str(m2), str(m3), str(avg)]
        for col_idx, (w, value) in enumerate(zip(col_widths, values)):
            c.setFillColor(band)
            c.rect(x, y - row_h, w, row_h, fill=1, stroke=1)
            c.setFillColor(TEXT_DARK)
            c.setFont("Helvetica", 8)
            if col_idx == 0:
                c.drawString(x + 6, y - row_h + 5, value)
            else:
                c.drawCentredString(x + w / 2, y - row_h + 5, value)
            x += w
        y -= row_h

    c.showPage()
    c.save()
    return output_path


def generate_attendance_report(
    output_path: str,
    rows,
    generated_at: datetime = None,
) -> str:
    """Davomat hisobotini PDF qilib yaratadi.

    rows: (full_name, course_name, attended: bool) tuple'lari ro'yxati.
    """
    generated_at = generated_at or datetime.now()
    date_str = generated_at.strftime("%d.%m.%Y %H:%M")

    total = len(rows)
    attended_count = sum(1 for _, _, attended in rows if attended)

    page_w, page_h = A4
    margin = 30
    table_w = page_w - 2 * margin
    name_w = table_w * 0.45
    course_w = table_w * 0.30
    status_w = table_w - name_w - course_w
    col_widths = [name_w, course_w, status_w]

    header_h = 26
    row_h = 16
    title_h = 24

    GREEN_TEXT = colors.HexColor("#2F7D4F")
    RED_TEXT = colors.HexColor("#B03A2E")

    c = canvas.Canvas(output_path, pagesize=A4)
    c.setStrokeColor(BORDER)

    def draw_title():
        c.setFillColor(TITLE_COLOR)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(page_w / 2, page_h - margin - 14, "DAVOMAT HISOBOTI")
        c.setFillColor(SUBTITLE_COLOR)
        c.setFont("Helvetica", 9)
        c.drawCentredString(
            page_w / 2,
            page_h - margin - title_h,
            f"Sana: {date_str}  |  Qatnashdi: {attended_count}/{total}",
        )

    def draw_table_header(y):
        x = margin
        for label, w in zip(["Talaba", "Kurs", "Holati"], col_widths):
            c.setFillColor(HEADER_GREEN if label == "Holati" else HEADER_BLUE)
            c.rect(x, y - header_h, w, header_h, fill=1, stroke=1)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(x + w / 2, y - header_h / 2 - 3, label)
            x += w
        return y - header_h

    draw_title()
    y = page_h - margin - title_h - 20
    y = draw_table_header(y)

    for idx, (name, course, attended) in enumerate(rows):
        if y - row_h < margin:
            c.showPage()
            c.setStrokeColor(BORDER)
            y = page_h - margin
            y = draw_table_header(y)

        band = ROW_ALT if idx % 2 == 0 else ROW_WHITE
        status_text = "Qatnashdi" if attended else "Qatnashmadi"
        status_color = GREEN_TEXT if attended else RED_TEXT
        columns = [
            (name, name_w, "left", TEXT_DARK),
            (course, course_w, "center", TEXT_DARK),
            (status_text, status_w, "center", status_color),
        ]

        x = margin
        for value, w, align, color in columns:
            c.setFillColor(band)
            c.rect(x, y - row_h, w, row_h, fill=1, stroke=1)
            c.setFillColor(color)
            c.setFont("Helvetica", 8)
            if align == "left":
                c.drawString(x + 6, y - row_h + 5, value)
            else:
                c.drawCentredString(x + w / 2, y - row_h + 5, value)
            x += w
        y -= row_h

    c.showPage()
    c.save()
    return output_path


def generate_attendance_matrix_report(
    output_path: str,
    session_labels,
    rows,
    generated_at: datetime = None,
) -> str:
    """Davomat jadvali (matritsa): qatorlar = o'quvchilar, ustunlar = davomat
    sessiyalari.

    session_labels: har bir ustun uchun qisqa yorliq (masalan "17.08 09:15").
    rows: (full_name, statuses) juftliklari; statuses - har bir sessiya uchun
    "in" (qatnashdi - yashil), "out" (qatnashmadi - qizil) yoki "na" (o'sha
    payt botda hali ro'yxatdan o'tmagan edi - kulrang) qiymatlaridan biri,
    session_labels bilan bir xil uzunlikda.
    """
    generated_at = generated_at or datetime.now()
    date_str = generated_at.strftime("%d.%m.%Y %H:%M")

    GREEN_BG = colors.HexColor("#DCF3E3")
    RED_BG = colors.HexColor("#FBE0DC")
    NA_BG = colors.HexColor("#E3E3E3")
    GREEN_TEXT = colors.HexColor("#2F7D4F")
    RED_TEXT = colors.HexColor("#B03A2E")
    NA_TEXT = colors.HexColor("#333333")

    STATUS_STYLE = {
        "in": (GREEN_BG, GREEN_TEXT, "✓"),
        "out": (RED_BG, RED_TEXT, "✗"),
        "na": (NA_BG, NA_TEXT, "—"),
    }

    page_w, page_h = landscape(A4)
    margin = 30
    name_w = 130
    header_h = 46
    row_h = 16
    title_h = 24

    max_cols_per_page = max(1, int((page_w - 2 * margin - name_w) / 28))
    col_count = len(session_labels) or 1
    col_w = (page_w - 2 * margin - name_w) / min(col_count, max_cols_per_page)

    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    c.setStrokeColor(BORDER)

    chunks = [
        list(range(i, min(i + max_cols_per_page, len(session_labels))))
        for i in range(0, len(session_labels), max_cols_per_page)
    ] or [[]]

    def draw_title(chunk_idx):
        c.setFillColor(TITLE_COLOR)
        c.setFont("Helvetica-Bold", 15)
        c.drawCentredString(page_w / 2, page_h - margin - 14, "DAVOMAT JADVALI")
        c.setFillColor(SUBTITLE_COLOR)
        c.setFont("Helvetica", 9)
        suffix = f"  |  {chunk_idx + 1}/{len(chunks)}-qism" if len(chunks) > 1 else ""
        c.drawCentredString(page_w / 2, page_h - margin - title_h, f"Sana: {date_str}{suffix}")

    def draw_header(y, col_indices):
        x = margin
        c.setFillColor(HEADER_BLUE)
        c.rect(x, y - header_h, name_w, header_h, fill=1, stroke=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 6, y - header_h / 2 - 3, "Talaba")
        x += name_w
        for idx in col_indices:
            c.setFillColor(HEADER_BLUE)
            c.rect(x, y - header_h, col_w, header_h, fill=1, stroke=1)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 6.5)
            c.saveState()
            c.translate(x + col_w / 2, y - header_h / 2)
            c.rotate(90)
            c.drawCentredString(0, -2, session_labels[idx])
            c.restoreState()
            x += col_w
        return y - header_h

    for chunk_idx, col_indices in enumerate(chunks):
        draw_title(chunk_idx)
        y = page_h - margin - title_h - 16
        y = draw_header(y, col_indices)

        for row_idx, (name, statuses) in enumerate(rows):
            if y - row_h < margin:
                c.showPage()
                c.setStrokeColor(BORDER)
                draw_title(chunk_idx)
                y = page_h - margin - title_h - 16
                y = draw_header(y, col_indices)

            band = ROW_ALT if row_idx % 2 == 0 else ROW_WHITE
            x = margin
            c.setFillColor(band)
            c.rect(x, y - row_h, name_w, row_h, fill=1, stroke=1)
            c.setFillColor(TEXT_DARK)
            c.setFont("Helvetica", 7.5)
            c.drawString(x + 6, y - row_h + 4, (name or "Noma'lum")[:26])
            x += name_w

            for idx in col_indices:
                bg, text_color, symbol = STATUS_STYLE[statuses[idx]]
                c.setFillColor(bg)
                c.rect(x, y - row_h, col_w, row_h, fill=1, stroke=1)
                c.setFillColor(text_color)
                c.setFont("Helvetica-Bold", 8)
                c.drawCentredString(x + col_w / 2, y - row_h + 4, symbol)
                x += col_w

            y -= row_h

        c.showPage()
        c.setStrokeColor(BORDER)

    c.save()
    return output_path


def generate_test_results_report(
    output_path: str,
    code: str,
    name: str,
    total_questions: int,
    rows,
    generated_at: datetime = None,
) -> str:
    """Test natijalari PDF hisobotini yaratadi.

    rows: (full_name, score) tuple'lari ro'yxati, ball bo'yicha kamayish tartibida.
    """
    generated_at = generated_at or datetime.now()
    date_str = generated_at.strftime("%d.%m.%Y %H:%M")

    page_w, page_h = A4
    margin = 30
    table_w = page_w - 2 * margin
    rank_w = table_w * 0.12
    name_w = table_w * 0.58
    score_w = table_w - rank_w - name_w
    col_widths = [rank_w, name_w, score_w]

    header_h = 26
    row_h = 16
    title_h = 24

    title = f"TEST NATIJALARI — {name}" if name else f"TEST NATIJALARI (kod: {code})"

    c = canvas.Canvas(output_path, pagesize=A4)
    c.setStrokeColor(BORDER)

    def draw_title():
        c.setFillColor(TITLE_COLOR)
        c.setFont("Helvetica-Bold", 15)
        c.drawCentredString(page_w / 2, page_h - margin - 14, title)
        c.setFillColor(SUBTITLE_COLOR)
        c.setFont("Helvetica", 9)
        c.drawCentredString(
            page_w / 2,
            page_h - margin - title_h,
            f"Kod: {code}  |  Sana: {date_str}  |  Ishtirokchilar: {len(rows)}",
        )

    def draw_table_header(y):
        x = margin
        for label, w in zip(["O'rin", "Talaba", f"Ball / {total_questions}"], col_widths):
            c.setFillColor(HEADER_BLUE)
            c.rect(x, y - header_h, w, header_h, fill=1, stroke=1)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(x + w / 2, y - header_h / 2 - 3, label)
            x += w
        return y - header_h

    draw_title()
    y = page_h - margin - title_h - 20
    y = draw_table_header(y)

    if not rows:
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica", 10)
        c.drawCentredString(page_w / 2, y - 20, "Hech kim testni topshirmadi.")

    for idx, (full_name, score) in enumerate(rows):
        if y - row_h < margin:
            c.showPage()
            c.setStrokeColor(BORDER)
            y = page_h - margin
            y = draw_table_header(y)

        band = ROW_ALT if idx % 2 == 0 else ROW_WHITE
        values = [str(idx + 1), full_name or "Noma'lum", str(score)]
        x = margin
        for col_idx, (w, value) in enumerate(zip(col_widths, values)):
            c.setFillColor(band)
            c.rect(x, y - row_h, w, row_h, fill=1, stroke=1)
            c.setFillColor(TEXT_DARK)
            c.setFont("Helvetica", 8)
            if col_idx == 1:
                c.drawString(x + 6, y - row_h + 5, value)
            else:
                c.drawCentredString(x + w / 2, y - row_h + 5, value)
            x += w
        y -= row_h

    c.showPage()
    c.save()
    return output_path


if __name__ == "__main__":
    generate_weekly_report("haftalik_hisobot.pdf")
