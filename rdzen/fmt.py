# SPDX-License-Identifier: MIT OR Apache-2.0
"""Formatter kanoniczny (§2.5): fmt(parse(P)) jest postacią kanoniczną programu P.

Zasady (deterministyczne, zależne wyłącznie od AST, komentarzy i szerokości 100 znaków):
- wcięcie 4 spacje, jedna spacja wokół operatorów dwuargumentowych, nawiasy tylko tam,
  gdzie są potrzebne do zachowania drzewa (grupowanie użytkownika jest zachowane);
- klauzule `requires`/`ensures`/`decreases`/`examples` i adnotacje pętli w osobnych wierszach
  z wcięciem o jeden poziom; klamra ciała w osobnym wierszu, jeśli jest co najmniej jedna
  klauzula, w przeciwnym razie na końcu wiersza nagłówka;
- `if` i `match` w pozycji instrukcji zawsze wielowierszowe; w pozycji wyrażenia jednowierszowe,
  jeśli się mieszczą, nie zawierają bloków ani komentarzy;
- deklaracje oddzielone jednym pustym wierszem; wewnątrz bloków zachowywany jest najwyżej
  jeden pusty wiersz między instrukcjami;
- komentarze zachowują pozycję względem jednostek (deklaracja, klauzula, instrukcja, gałąź,
  konstruktor): komentarz w osobnym wierszu poprzedza jednostkę, komentarz na końcu wiersza
  zostaje na końcu wiersza tej jednostki;
- wiersz dłuższy niż 100 znaków jest łamany po operatorach `&&`/`||`, po argumentach
  wywołania (jeden na wiersz) albo po dwukropku kwantyfikatora / strzałce domknięcia.
"""
from __future__ import annotations
from .ast import *
from .parser import parse

W = 100
PREC = {"||": 1, "&&": 2, "==": 3, "!=": 3, "<": 3, "<=": 3, ">": 3, ">=": 3,
        "+": 4, "-": 4, "*": 5, "/": 5, "%": 5}
CMP = {"==", "!=", "<", "<=", ">", ">="}


class NotFlat(Exception):
    """Węzła nie da się zapisać w jednym wierszu (np. pętla wewnątrz bloku-wyrażenia)."""


class Fmt:
    def __init__(self, src: str, prog: Program):
        self.lines = src.split("\n")
        self.comments = sorted(getattr(prog, "comments", []))
        self.used = set()
        self.out: list[str] = []
        self.last_src = 0

    # ------------------------------------------------------------ komentarze
    def blank_between(self, a, b):
        return any(not self.lines[k - 1].strip() for k in range(a + 1, b) if 0 < k <= len(self.lines))

    def opening(self):
        if not self.out:
            return True
        t = self.out[-1].rstrip()
        return t == "" or t.endswith(("{", "(", "=", "=>"))

    def sep(self, line, allow_blank=True):
        if allow_blank and not self.opening() and self.blank_between(self.last_src, line):
            self.out.append("")

    def lead(self, line, ind, guard=None, allow_blank=True):
        """Komentarze z wierszy < `line` jeszcze nie wypisane, każdy w osobnym wierszu.
        Komentarze końcowe z wierszy >= `guard` zostają dla jednostki (trafią na koniec jej wiersza)."""
        guard = line if guard is None else guard
        for k, (ln, _col, text, own) in enumerate(self.comments):
            if k in self.used or ln >= line or (not own and ln >= guard):
                continue
            self.sep(ln, allow_blank)
            self.out.append(" " * ind + text)
            self.used.add(k)
            self.last_src = max(self.last_src, ln)
        self.sep(line, allow_blank)

    def emit(self, ind, text, lo, hi):
        """Wiersz kodu odpowiadający wierszom źródła lo..hi; dołącza komentarz końcowy z tego zakresu."""
        line = " " * ind + text
        for k, (ln, _col, ctext, own) in enumerate(self.comments):
            if k not in self.used and not own and lo <= ln <= hi:
                line += "  " + ctext
                self.used.add(k)
                break
        self.out.append(line.rstrip())
        self.last_src = max(self.last_src, hi)

    def has_comments(self, span):
        return any(span.line <= ln <= span.end_line and k not in self.used
                   for k, (ln, _c, _t, _o) in enumerate(self.comments)) and span.end_line > span.line

    # ------------------------------------------------------------ typy
    def ty(self, t) -> str:
        if isinstance(t, TName):
            return t.name + ("<" + ", ".join(self.ty(a) for a in t.args) + ">" if t.args else "")
        if isinstance(t, TRefine):
            return self.ty(t.base) + " where " + self.flat(t.formula, 0, True)
        if isinstance(t, TFn):
            ps = ", ".join((f"{n}: " if n else "") + self.ty(p) for n, p in t.params)
            return f"fn({ps}) -> {self.ty(t.ret)}"
        raise NotFlat(type(t).__name__)

    def tparams(self, node):
        if not node.tparams:
            return ""
        b = getattr(node, "tbounds", {}) or {}
        return "<" + ", ".join(p + (f": {b[p]}" if p in b else "") for p in node.tparams) + ">"

    def param(self, p):
        return ("inout " if p.inout else "") + p.name + ": " + self.ty(p.type)

    # ------------------------------------------------------------ wyrażenia jednowierszowe
    @staticmethod
    def prec(e):
        if isinstance(e, Binary):
            return PREC[e.op]
        if isinstance(e, Unary):
            return 6
        if isinstance(e, (Quant, Lambda)):
            return 0
        return 9

    def flat(self, e, prec=0, tail=True) -> str:
        s = self._flat(e, tail)
        p = self.prec(e)
        need = (prec > 0 or not tail) if p == 0 else p < prec
        return f"({s})" if need else s

    def _flat(self, e, tail):
        F = self.flat
        if isinstance(e, IntLit):
            return getattr(e, "text", None) or str(e.value)
        if isinstance(e, BoolLit):
            return "true" if e.value else "false"
        if isinstance(e, UnitLit):
            return "()"
        if isinstance(e, Name):
            return e.name
        if isinstance(e, SelfRef):
            return "self"
        if isinstance(e, ResultRef):
            return "result"
        if isinstance(e, Old):
            return f"old({e.name})"
        if isinstance(e, Hole):
            return f"?{e.name}"
        if isinstance(e, Try):
            return F(e.expr, 9, False) + "?"
        if isinstance(e, Unary):
            inner = F(e.expr, 6, False)
            if e.op == "-" and inner.startswith("-"):
                inner = f"({inner})"            # nie `--a`
            return e.op + inner
        if isinstance(e, Binary):
            p = PREC[e.op]
            lp, rp = (p + 1, p + 1) if e.op in CMP else (p, p + 1)
            left = F(e.left, 10 if self.forced(e.op, e.left) else lp, False)
            if e.op in ("&&", "||") and isinstance(e.right, (Quant, Lambda)):
                right = F(e.right, 0, tail)
            else:
                right = F(e.right, 10 if self.forced(e.op, e.right) else rp, tail)
            return f"{left} {e.op} {right}"
        if isinstance(e, Index):
            return f"{F(e.expr, 9, False)}[{F(e.index)}]"
        if isinstance(e, Field):
            return f"{F(e.expr, 9, False)}.{e.name}"
        if isinstance(e, Call):
            return f"{e.name}(" + ", ".join(self.arg(a) for a in e.args) + ")"
        if isinstance(e, CtorCall):
            return e.name + ("(" + ", ".join(F(a) for a in e.args) + ")" if e.args else "")
        if isinstance(e, StrLit):
            return e.text
        if isinstance(e, ArrayLit):
            return "[" + ", ".join(F(a) for a in e.items) + "]"
        if isinstance(e, Quant):
            return (f"{e.kind} {e.var} in {F(e.lo, 4, False)}..{F(e.hi, 4, False)}: "
                    f"{F(e.body, 0, tail)}")
        if isinstance(e, Lambda):
            return self.lam_head(e) + " " + F(e.body, 0, tail)
        if isinstance(e, Match):
            arms = ", ".join(self.arm_head(a) + F(a.body) for a in e.arms)
            return f"match {F(e.expr, 0, False)} {{ {arms} }}"
        if isinstance(e, If):
            s = f"if {F(e.cond, 0, False)} {self.flat_block(e.then)}"
            if isinstance(e.els, If):
                s += " else " + self._flat(e.els, True)
            elif e.els is not None:
                s += " else " + self.flat_block(e.els)
            return s
        if isinstance(e, BlockExpr):
            return self.flat_block(e.block)
        raise NotFlat(type(e).__name__)

    @staticmethod
    def forced(op, operand):
        """Nawiasy dla czytelności (nie zmieniają drzewa): `&&` wewnątrz `||` oraz `if`/`match`
        jako argument operatora."""
        if op == "||" and isinstance(operand, Binary) and operand.op == "&&":
            return True
        return isinstance(operand, (If, Match))

    def arg(self, a):
        return "&" + a.inout if a.inout else self.flat(a.expr)

    def lam_head(self, e):
        ps = ", ".join(n + (": " + self.ty(t) if t is not None else "") for n, t in e.params)
        return f"fn({ps})" + (f" -> {self.ty(e.ret)}" if e.ret is not None else "") + " =>"

    def arm_head(self, a):
        g = f" if {self.flat(a.guard, 0, False)}" if a.guard is not None else ""
        return f"{self.pat(a.pattern)}{g} => "

    def pat(self, p):
        if p.kind == "wild":
            return "_"
        if p.kind == "var":
            return p.name
        if p.kind == "int":
            return getattr(p, "text", None) or str(p.value)
        if p.kind == "bool":
            return "true" if p.value else "false"
        return p.name + ("(" + ", ".join(self.pat(a) for a in p.args) + ")" if p.args else "")

    def flat_block(self, b):
        if not b.stmts:
            return "{ }"
        return "{ " + "; ".join(self.flat_stmt(s) for s in b.stmts) + " }"

    def flat_stmt(self, s):
        if isinstance(s, Let):
            return self.let_prefix(s) + self.flat(s.expr)
        if isinstance(s, Assign):
            return f"{s.name} = {self.flat(s.expr)}"
        if isinstance(s, IndexAssign):
            return f"{s.name}[{self.flat(s.index)}] = {self.flat(s.expr)}"
        if isinstance(s, ExprStmt):
            return self.flat(s.expr)
        if isinstance(s, Return):
            return "return" + (" " + self.flat(s.expr) if s.expr is not None else "")
        if isinstance(s, Break):
            return "break"
        if isinstance(s, Continue):
            return "continue"
        if isinstance(s, Assert):
            return "assert " + self.flat(s.formula)
        raise NotFlat(type(s).__name__)

    def let_prefix(self, s):
        return ("var " if s.mutable else "let ") + s.name + (": " + self.ty(s.type) if s.type else "") + " = "

    # ------------------------------------------------------------ wyrażenia wielowierszowe
    @staticmethod
    def simple_block(b):
        """Blok zapisywalny w jednym wierszu: pusty albo jedna prosta instrukcja (`{ n = v }`)."""
        if not b.stmts:
            return True
        if len(b.stmts) > 1:
            return False
        st = b.stmts[0]
        if isinstance(st, ExprStmt):
            return not isinstance(st.expr, (If, Match, BlockExpr))
        return isinstance(st, (Assign, IndexAssign, Return, Break, Continue, Assert))

    def needs_block(self, e):
        """Bloki złożone (więcej niż jedna instrukcja, pętla, zagnieżdżone sterowanie)
        wymuszają postać wielowierszową."""
        if isinstance(e, BlockExpr):
            return not self.simple_block(e.block)
        if isinstance(e, Match):
            return any(isinstance(a.body, BlockExpr) and not self.simple_block(a.body.block) for a in e.arms)
        if isinstance(e, If):
            bs = [e.then]
            cur = e
            while isinstance(cur.els, If):
                cur = cur.els
                bs.append(cur.then)
            if cur.els is not None:
                bs.append(cur.els)
            return not all(len(b.stmts) == 1 and isinstance(b.stmts[0], ExprStmt) and
                           not isinstance(b.stmts[0].expr, (If, Match, BlockExpr)) for b in bs)
        return False

    def xemit(self, e, ind, prefix, suffix, lo, hi, stmt=False, prec=0, tail=True):
        multi = isinstance(e, (If, Match, BlockExpr)) and (
            stmt or self.needs_block(e) or self.has_comments(e.span))
        if isinstance(e, BlockExpr) and not e.block.stmts:
            multi = False
        if isinstance(e, (If, Match)) and prec > 9:
            multi = False          # w nawiasach jako argument operatora — tylko jednowierszowo
        s = None
        if not multi:
            try:
                s = self.flat(e, prec, tail)
            except NotFlat:
                s = None
            if s is not None and ind + len(prefix) + len(s) + len(suffix) <= W:
                self.lead(hi + 1, ind, guard=lo)
                self.emit(ind, prefix + s + suffix, lo, hi)
                return
        need_parens = (prec > 0 or not tail) if self.prec(e) == 0 else self.prec(e) < prec
        if not need_parens:
            if isinstance(e, Match):
                return self.match_multi(e, ind, prefix, suffix, lo)
            if isinstance(e, If):
                return self.if_multi(e, ind, prefix, suffix, lo)
            if isinstance(e, BlockExpr):
                self.emit(ind, prefix + "{", lo, e.block.span.line)
                self.block_body(e.block, ind + 4)
                self.emit(ind, "}" + suffix, e.span.end_line, e.span.end_line)
                return
            if isinstance(e, Binary) and e.op in ("&&", "||"):
                return self.chain(e, ind, prefix, suffix, lo, hi, tail)
            if isinstance(e, (Call, CtorCall)) and e.args and not any(
                    getattr(a, "inout", None) for a in e.args):
                return self.call_multi(e, ind, prefix, suffix, lo, hi)
            if isinstance(e, Quant):
                head = f"{e.kind} {e.var} in {self.flat(e.lo, 4, False)}..{self.flat(e.hi, 4, False)}:"
                self.emit(ind, prefix + head, lo, e.body.span.line - 1 if e.body.span.line > lo else lo)
                return self.xemit(e.body, ind + 4, "", suffix, e.body.span.line, hi, tail=tail)
            if isinstance(e, Lambda):
                self.emit(ind, prefix + self.lam_head(e), lo, e.body.span.line - 1 if e.body.span.line > lo else lo)
                return self.xemit(e.body, ind + 4, "", suffix, e.body.span.line, hi, tail=tail)
        if s is None:
            raise NotFlat(type(e).__name__)
        self.lead(hi + 1, ind, guard=lo)
        self.emit(ind, prefix + s + suffix, lo, hi)

    def chain(self, e, ind, prefix, suffix, lo, hi, tail):
        ops = []
        cur = e
        while isinstance(cur, Binary) and cur.op == e.op:
            ops.append(cur.right)
            cur = cur.left
        ops.append(cur)
        ops.reverse()
        p = PREC[e.op]
        cont = ind if prefix == "" else ind + 4      # kolejne człony pod pierwszym albo z wcięciem
        for k, o in enumerate(ops):
            last = k == len(ops) - 1
            olo = lo if k == 0 else o.span.line
            ohi = o.span.end_line if not last else max(hi, o.span.end_line)
            req = 10 if self.forced(e.op, o) else (p if k == 0 else p + 1)
            if k > 0:
                self.lead(o.span.line, cont, allow_blank=False)
            if k == 0:
                self.xemit(o, ind, prefix, f" {e.op}", olo, ohi, prec=req, tail=False)
            elif not last:
                self.xemit(o, cont, "", f" {e.op}", olo, ohi, prec=req, tail=False)
            elif isinstance(o, (Quant, Lambda)):
                self.xemit(o, cont, "", suffix, olo, ohi, prec=0, tail=tail)
            else:
                self.xemit(o, cont, "", suffix, olo, ohi, prec=req, tail=tail)

    def call_multi(self, e, ind, prefix, suffix, lo, hi):
        exprs = [a.expr for a in e.args] if isinstance(e, Call) else list(e.args)
        self.emit(ind, prefix + e.name + "(", lo, lo)
        for a in exprs:
            self.lead(a.span.line, ind + 4, allow_blank=False)
            self.xemit(a, ind + 4, "", ",", a.span.line, a.span.end_line)
        self.lead(e.span.end_line, ind + 4, allow_blank=False)
        self.emit(ind, ")" + suffix, e.span.end_line, e.span.end_line)

    def match_multi(self, e, ind, prefix, suffix, lo):
        first = e.arms[0].span.line if e.arms else e.span.end_line
        self.emit(ind, prefix + f"match {self.flat(e.expr, 0, False)} {{", lo, first - 1)
        for a in e.arms:
            self.lead(a.span.line, ind + 4)
            self.xemit(a.body, ind + 4, self.arm_head(a), ",", a.span.line, a.span.end_line)
        self.lead(e.span.end_line, ind + 4, allow_blank=False)
        self.emit(ind, "}" + suffix, e.span.end_line, e.span.end_line)

    def if_multi(self, e, ind, prefix, suffix, lo):
        self.emit(ind, prefix + f"if {self.flat(e.cond, 0, False)} {{", lo, e.then.span.line)
        self.block_body(e.then, ind + 4)
        cur = e
        while True:
            els = cur.els
            if isinstance(els, If):
                self.lead(cur.then.span.end_line, ind + 4, allow_blank=False)
                self.emit(ind, f"}} else if {self.flat(els.cond, 0, False)} {{", cur.then.span.end_line, els.then.span.line)
                self.block_body(els.then, ind + 4)
                cur = els
                continue
            if els is not None:
                self.lead(cur.then.span.end_line, ind + 4, allow_blank=False)
                self.emit(ind, "} else {", cur.then.span.end_line, els.span.line)
                self.block_body(els, ind + 4)
                end = els.span.end_line
            else:
                end = cur.then.span.end_line
            self.lead(end, ind + 4, allow_blank=False)
            self.emit(ind, "}" + suffix, end, end)
            return

    # ------------------------------------------------------------ instrukcje
    def block_body(self, b, ind):
        for s in b.stmts:
            self.stmt(s, ind)
        self.lead(b.span.end_line, ind, allow_blank=False)

    def body_block(self, b, ind, header_lo, header_hi, header_text):
        """Nagłówek z klamrą na końcu (`header {`) albo klamra w osobnym wierszu (header_text=None)."""
        if header_text is not None:
            if not b.stmts:
                self.emit(ind, header_text + " { }", header_lo, b.span.end_line)
                return
            self.emit(ind, header_text + " {", header_lo, header_hi)
        else:
            self.lead(b.span.line, ind, allow_blank=False)
            if not b.stmts:
                self.emit(ind, "{ }", b.span.line, b.span.end_line)
                return
            self.emit(ind, "{", b.span.line, b.span.line)
        self.block_body(b, ind + 4)
        self.emit(ind, "}", b.span.end_line, b.span.end_line)

    def stmt(self, s, ind):
        self.lead(s.span.line, ind)
        lo, hi = s.span.line, s.span.end_line
        if isinstance(s, Let):
            return self.xemit(s.expr, ind, self.let_prefix(s), "", lo, hi)
        if isinstance(s, Assign):
            return self.xemit(s.expr, ind, f"{s.name} = ", "", lo, hi)
        if isinstance(s, IndexAssign):
            return self.xemit(s.expr, ind, f"{s.name}[{self.flat(s.index)}] = ", "", lo, hi)
        if isinstance(s, ExprStmt):
            return self.xemit(s.expr, ind, "", "", lo, hi, stmt=True)
        if isinstance(s, Return):
            if s.expr is None:
                return self.emit(ind, "return", lo, hi)
            return self.xemit(s.expr, ind, "return ", "", lo, hi)
        if isinstance(s, (Break, Continue)):
            return self.emit(ind, "break" if isinstance(s, Break) else "continue", lo, hi)
        if isinstance(s, Assert):
            return self.xemit(s.formula, ind, "assert ", "", lo, hi)
        if isinstance(s, (While, For)):
            head = (f"while {self.flat(s.cond, 0, False)}" if isinstance(s, While)
                    else f"for {s.var} in {self.flat(s.iterable, 0, False)}")
            anns = [("invariant ", f) for f in s.invariants]
            if s.decreases is not None:
                anns.append(("decreases ", s.decreases))
            if not anns:
                return self.body_block(s.body, ind, lo, s.body.span.line, head)
            self.emit(ind, head, lo, anns[0][1].span.line - 1)
            for kw, f in anns:
                self.lead(f.span.line, ind + 4, allow_blank=False)
                self.xemit(f, ind + 4, kw, "", f.span.line, f.span.end_line)
            return self.body_block(s.body, ind, 0, 0, None)
        raise NotFlat(type(s).__name__)

    # ------------------------------------------------------------ deklaracje
    def item(self, it):
        """Deklaracje oddziela pusty wiersz; kolejne deklaracje jednowierszowe bez pustego wiersza
        w źródle pozostają zgrupowane."""
        start, prev_end = len(self.out), self.last_src
        self._item(it)
        lines = self.out[start:]
        code = [l for l in lines if l.strip() and not l.lstrip().startswith("//")]
        single = len(code) == 1
        commented = len(code) != len([l for l in lines if l.strip()])
        grouped = (getattr(self, "prev_single", False) and single and not commented
                   and not self.blank_between(prev_end, it.span.line))
        if start > 0 and not grouped and self.out[start] != "" and self.out[start - 1] != "":
            self.out.insert(start, "")
        self.prev_single = single

    def _item(self, it):
        self.lead(it.span.line, 0)
        lo = it.span.line
        if isinstance(it, FnDecl):
            return self.fn_decl(it)
        if isinstance(it, SpecFn):
            head = f"spec fn {it.name}{self.tparams(it)}(" + ", ".join(self.param(p) for p in it.params) + \
                f") -> {self.ty(it.ret)}"
            if it.decreases is None:
                self.emit(0, head + " =", lo, it.body.span.line - 1)
            else:
                self.emit(0, head, lo, it.decreases.span.line - 1)
                self.lead(it.decreases.span.line, 4, allow_blank=False)
                self.xemit(it.decreases, 4, "decreases ", "", it.decreases.span.line, it.decreases.span.end_line)
                self.out.append("=")
            self.lead(it.body.span.line, 4, allow_blank=False)
            return self.xemit(it.body, 4, "", "", it.body.span.line, it.body.span.end_line)
        if isinstance(it, DataDecl):
            return self.data_decl(it)
        if isinstance(it, TypeAlias):
            return self.emit(0, f"type {it.name}{self.tparams(it)} = {self.ty(it.type)}", lo, it.span.end_line)
        if isinstance(it, ConstDecl):
            return self.xemit(it.expr, 0, f"const {it.name}: {self.ty(it.type)} = ", "", lo, it.span.end_line)
        raise NotFlat(type(it).__name__)

    def fn_decl(self, f):
        mods = ("pub " if f.pub else "") + ("lemma " if f.lemma else "") + ("partial " if f.partial else "")
        name = f"{mods}fn {f.name}{self.tparams(f)}"
        ret = f" -> {self.ty(f.ret)}" if f.ret is not None else ""
        params = [self.param(p) for p in f.params]
        clauses = ([("requires ", q) for q in f.requires] + [("ensures ", q) for q in f.ensures] +
                   ([("decreases ", f.decreases)] if f.decreases is not None else []))
        first_child = (clauses[0][1].span.line if clauses else
                       f.examples[0].span.line - 1 if f.examples else f.body.span.line)
        lo = f.span.line
        one = f"{name}(" + ", ".join(params) + ")" + ret
        has_cl = bool(clauses or f.examples)
        if len(one) + (0 if has_cl else 2) <= W:
            if not has_cl:
                return self.body_block(f.body, 0, lo, f.body.span.line, one)
            self.emit(0, one, lo, first_child - 1)
        else:
            self.emit(0, f"{name}(", lo, lo)
            for p, pt in zip(params, f.params):
                self.emit(4, p + ",", pt.span.line, pt.span.end_line)
            if not has_cl:
                return self.body_block(f.body, 0, lo, f.body.span.line, ")" + ret)
            self.emit(0, ")" + ret, lo, first_child - 1)
        for kw, q in clauses:
            self.lead(q.span.line, 4, allow_blank=False)
            self.xemit(q, 4, kw, "", q.span.line, q.span.end_line)
        if f.examples:
            self.lead(f.examples[0].span.line - 1, 4, allow_blank=False)
            self.emit(4, "examples {", f.examples[0].span.line - 1, f.examples[0].span.line - 1)
            for ex in f.examples:
                self.lead(ex.span.line, 8, allow_blank=False)
                pre = ""
                if ex.binders:
                    pre = "forall " + ", ".join(f"{n}: {self.ty(t)}" for n, t in ex.binders) + ": "
                self.xemit(ex.expr, 8, pre, "", ex.span.line, ex.span.end_line)
            self.lead(f.body.span.line, 8, allow_blank=False)
            self.out.append("    }")
        self.body_block(f.body, 0, 0, 0, None)

    def data_decl(self, d):
        lo = d.span.line
        ctors = [c.name + ("(" + ", ".join(f"{n}: {self.ty(t)}" for n, t in c.fields) + ")" if c.fields else "")
                 for c in d.ctors]
        head = f"data {d.name}{self.tparams(d)}"
        one = head + " { " + ", ".join(ctors) + " }"
        where = f" where {self.flat(d.where, 0, True)}" if d.where is not None else ""
        body_end = d.where.span.line - 1 if d.where is not None else d.span.end_line
        inner_comments = any(lo <= ln <= body_end and k not in self.used and (ln > lo or own)
                             for k, (ln, _c, _t, own) in enumerate(self.comments)) and body_end > lo
        if not inner_comments and len(one) <= W:
            if d.where is None:
                return self.emit(0, one, lo, d.span.end_line)
            if len(one + where) <= W:
                return self.emit(0, one + where, lo, d.span.end_line)
            self.emit(0, one, lo, d.where.span.line - 1)
        else:
            self.emit(0, head + " {", lo, d.ctors[0].span.line - 1 if d.ctors else lo)
            for c, txt in zip(d.ctors, ctors):
                self.lead(c.span.line, 4, allow_blank=False)
                self.emit(4, txt + ",", c.span.line, c.span.line)
            self.lead(body_end + 1, 4, allow_blank=False)
            if d.where is None:
                return self.emit(0, "}", body_end, body_end)
            if len("}" + where) <= W:
                return self.emit(0, "}" + where, body_end, d.span.end_line)
            self.emit(0, "}", body_end, body_end)
        self.lead(d.where.span.line, 4, allow_blank=False)
        self.xemit(d.where, 4, "where ", "", d.where.span.line, d.where.span.end_line)

    def program(self, prog):
        for it in prog.items:
            self.item(it)
        self.lead(10 ** 9, 0)
        while self.out and self.out[-1] == "":
            self.out.pop()
        return "\n".join(self.out) + "\n"


def format_source(src: str) -> str:
    """Postać kanoniczna; zgłasza CompileError przy błędzie składni, NotFlat przy konstrukcji,
    której formatter nie obsługuje."""
    prog = parse(src)
    return Fmt(src, prog).program(prog)


# ------------------------------------------------------------ porównanie drzew (testy, kontrola)
def same_ast(a, b) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, list) or isinstance(a, tuple):
        return len(a) == len(b) and all(same_ast(x, y) for x, y in zip(a, b))
    if isinstance(a, Node):
        va, vb = vars(a), vars(b)
        for k in set(va) | set(vb):
            if k in NON_CHILD or k in ("text", "comments"):
                continue
            if not same_ast(va.get(k), vb.get(k)):
                return False
        return True
    return a == b


def check_format(src: str):
    """(postać kanoniczna, czy zachowuje drzewo i komentarze)."""
    out = format_source(src)
    ok = same_ast(parse(src), parse(out))
    from .lexer import lex
    c1, c2 = [], []
    lex(src, c1)
    lex(out, c2)
    ok = ok and sorted(t for *_, t, _o in c1) == sorted(t for *_, t, _o in c2)
    return out, ok
