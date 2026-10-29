# SPDX-License-Identifier: MIT OR Apache-2.0
"""Wypisywanie formuł i wyrażeń w składni Rdzenia (do diagnostyki)."""
from .ast import *

PREC = {"||": 1, "&&": 2, "==": 3, "!=": 3, "<": 3, "<=": 3, ">": 3, ">=": 3,
        "+": 4, "-": 4, "*": 5, "/": 5, "%": 5}


def show(e, subst=None, prec=0) -> str:
    subst = subst or {}
    s = _show(e, subst)
    p = _prec(e)
    return f"({s})" if p < prec else s


def _prec(e):
    if isinstance(e, Binary):
        return PREC[e.op]
    if isinstance(e, (Quant,)):
        return 0
    if isinstance(e, Unary):
        return 6
    return 9


def _show(e, sub):
    if isinstance(e, IntLit):
        return str(e.value)
    if isinstance(e, BoolLit):
        return "true" if e.value else "false"
    if isinstance(e, UnitLit):
        return "()"
    if isinstance(e, Name):
        return sub.get(e.name, e.name)
    if isinstance(e, SelfRef):
        return sub.get("self", "self")
    if isinstance(e, ResultRef):
        return sub.get("result", "result")
    if isinstance(e, Old):
        return f"old({e.name})"
    if isinstance(e, Hole):
        return f"?{e.name}"
    if isinstance(e, Unary):
        return e.op + show(e.expr, sub, 6)
    if isinstance(e, Binary):
        p = PREC[e.op]
        rp = p + 1 if e.op not in ("&&", "||") else p
        return f"{show(e.left, sub, p)} {e.op} {show(e.right, sub, rp)}"
    if isinstance(e, Index):
        return f"{show(e.expr, sub, 9)}[{show(e.index, sub)}]"
    if isinstance(e, Field):
        return f"{show(e.expr, sub, 9)}.{e.name}"
    if isinstance(e, Call):
        return f"{e.name}(" + ", ".join(("&" + a.inout) if a.inout else show(a.expr, sub) for a in e.args) + ")"
    if isinstance(e, CtorCall):
        return e.name + ("(" + ", ".join(show(a, sub) for a in e.args) + ")" if e.args else "")
    if isinstance(e, ArrayLit):
        return "[" + ", ".join(show(a, sub) for a in e.items) + "]"
    if isinstance(e, Quant):
        inner = dict(sub)
        inner.pop(e.var, None)
        return f"{e.kind} {e.var} in {show(e.lo, sub, 4)}..{show(e.hi, sub, 4)}: {show(e.body, inner)}"
    if isinstance(e, Match):
        arms = ", ".join(f"{show_pat(a.pattern)} => {show(a.body, sub)}" for a in e.arms)
        return f"match {show(e.expr, sub)} {{ {arms} }}"
    if isinstance(e, If):
        th = e.then.stmts[0].expr if e.then.stmts else UnitLit()
        el = e.els
        if isinstance(el, Block):
            el = el.stmts[0].expr if el.stmts else UnitLit()
        return f"if {show(e.cond, sub)} {{ {show(th, sub)} }} else {{ {show(el, sub)} }}"
    if isinstance(e, BlockExpr):
        return "{ … }"
    return "…"


def show_pat(p):
    if p.kind == "wild":
        return "_"
    if p.kind == "var":
        return p.name
    if p.kind == "int":
        return str(p.value)
    if p.kind == "bool":
        return "true" if p.value else "false"
    return p.name + ("(" + ", ".join(show_pat(a) for a in p.args) + ")" if p.args else "")
