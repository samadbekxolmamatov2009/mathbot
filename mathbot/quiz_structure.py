"""Test savollari tuzilishi.

Har bir test o'z savollar sonini o'zi belgilaydi (admin mini appda +/- orqali
o'zgartiriladi, standart 30 ta). Barcha savollar bir xil, 4 variantli
(A-D) bo'ladi.
"""

DEFAULT_TOTAL_QUESTIONS = 30


def options_for(question_no: int):
    return ["A", "B", "C", "D"]


def all_questions(total_questions: int = DEFAULT_TOTAL_QUESTIONS):
    return [
        {"number": q, "options": options_for(q)}
        for q in range(1, total_questions + 1)
    ]
