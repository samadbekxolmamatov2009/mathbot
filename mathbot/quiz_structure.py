"""Test savollari tuzilishi.

Har bir test o'z savollar sonini o'zi belgilaydi (admin mini appda +/- orqali
o'zgartiriladi, standart 35 ta). 33-35-savollar har doim 5 variantli (A-E);
admin qo'shgan qo'shimcha savollar (36+) va qolgan barcha savollar 4
variantli (A-D) bo'ladi.
"""

DEFAULT_TOTAL_QUESTIONS = 35
EXTENDED_FROM = 33
EXTENDED_TO = 35


def options_for(question_no: int):
    if EXTENDED_FROM <= question_no <= EXTENDED_TO:
        return ["A", "B", "C", "D", "E"]
    return ["A", "B", "C", "D"]


def all_questions(total_questions: int = DEFAULT_TOTAL_QUESTIONS):
    return [
        {"number": q, "options": options_for(q)}
        for q in range(1, total_questions + 1)
    ]
