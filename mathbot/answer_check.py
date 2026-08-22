"""A+ (yozma javobli) testlar uchun javoblarni solishtirish.

O'quvchi javobini matn sifatida emas, iloji bo'lsa SON sifatida baholaydi -
"0.5", "0,5", "1/2" barchasi bir xil qiymat sifatida to'g'ri hisoblanadi;
"sqrt(4)" yoki "4 dan ildiz" kabi oddiy arifmetik ifodalar ham hisoblab
solishtiriladi (masalan natija "2" bilan mos keladi).

Ifodani xavfsiz baholash uchun `eval()` ISHLATILMAYDI - faqat ruxsat etilgan
AST tugunlari (son, +-*/^. qavslar, sqrt/abs funksiyalari) qabul qilinadi,
qolgani rad etiladi.
"""

import ast
import math
import operator
import re

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}
_ALLOWED_FUNCS = {"sqrt": math.sqrt, "abs": abs}


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_eval_node(node.operand))
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _ALLOWED_FUNCS
        and not node.keywords
    ):
        args = [_eval_node(a) for a in node.args]
        return _ALLOWED_FUNCS[node.func.id](*args)
    raise ValueError("invalid expression")


_BARE_SQRT_RE = re.compile(r"√(\d+(?:\.\d+)?)")


def _normalize_text(s: str) -> str:
    s = s.strip().lower()
    s = s.replace(" ", "")
    s = s.replace(",", ".")
    # "√4" -> "sqrt(4)"; "√(4+5)" ning qavslari allaqachon bor, keyingi qatorda
    # qolgan "√" belgisi shunchaki "sqrt" ga almashtiriladi.
    s = _BARE_SQRT_RE.sub(lambda m: f"sqrt({m.group(1)})", s)
    s = s.replace("√", "sqrt")
    s = s.replace("^", "**")
    return s


def _try_eval(s: str):
    try:
        tree = ast.parse(_normalize_text(s), mode="eval")
        return _eval_node(tree)
    except Exception:
        return None


def answers_equivalent(correct: str, submitted: str) -> bool:
    """Ikki matnli javobni solishtiradi: avval normalizatsiya qilingan matn
    sifatida, keyin (agar ikkalasi ham son/ifoda bo'lsa) hisoblangan qiymat
    sifatida taqqoslaydi."""
    if correct is None or submitted is None:
        return False

    norm_correct = _normalize_text(correct)
    norm_submitted = _normalize_text(submitted)
    if not norm_submitted:
        return False
    if norm_correct == norm_submitted:
        return True

    value_correct = _try_eval(correct)
    value_submitted = _try_eval(submitted)
    if value_correct is not None and value_submitted is not None:
        return math.isclose(value_correct, value_submitted, rel_tol=1e-6, abs_tol=1e-9)

    return False
