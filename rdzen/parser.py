# SPDX-License-Identifier: MIT OR Apache-2.0
"""Parser Rdzenia (§2.3) — podzbiór prototypu."""
from __future__ import annotations
from .lexer import lex, Tok
from .ast import *
from .diag import err


def sp(a: Span, b: Span) -> Span:
    return Span(a.line, a.col, b.end_line, b.end_col)


class Parser:
    def __init__(self, src: str):
        self.comments = []
        self.toks = lex(src, self.comments)
        self.i = 0
        self.bounds = {}

    # ---------- narzędzia ----------
    @property
    def t(self) -> Tok:
        return self.toks[self.i]

    def peek(self, k=1) -> Tok:
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def at(self, *kinds) -> bool:
        return self.t.kind in kinds

    def adv(self) -> Tok:
        t = self.t
        self.i += 1
        return t

    def expect(self, kind, what=None) -> Tok:
        if self.t.kind != kind:
            found = "koniec wiersza" if (self.t.kind == ";" and self.t.implicit) else (self.t.text or self.t.kind)
            raise err("E0002", self.t.span, f"oczekiwano {what or '`' + kind + '`'}, znaleziono `{found}`", ["2.3"])
        return self.adv()

    def skip_semis(self):
        while self.at(";"):
            self.adv()

    def accept(self, kind) -> bool:
        if self.at(kind):
            self.adv()
            return True
        return False

    # ---------- program ----------
    def program(self) -> Program:
        items = []
        self.skip_semis()
        while not self.at("EOF"):
            items.append(self.item())
            self.skip_semis()
        return Program(items)

    def item(self):
        pub = self.accept("pub")
        if self.at("fn", "partial", "lemma"):
            return self.fn_decl(pub)
        if self.at("data"):
            return self.data_decl()
        if self.at("type"):
            return self.type_alias()
        if self.at("spec"):
            return self.spec_fn()
        if self.at("const"):
            return self.const_decl()
        if self.at("extern", "actor", "import"):
            raise err("E0003", self.t.span, f"`{self.t.text}` nie jest obsługiwane w prototypie", ["2.3"])
        raise err("E0002", self.t.span, f"oczekiwano deklaracji, znaleziono `{self.t.text}`", ["2.3"])

    def tparams(self):
        ps = []
        self.bounds = {}
        if self.accept("<"):
            while True:
                ps.append(self.expect("TIDENT", "parametru typowego").text)
                if self.accept(":"):
                    self.bounds[ps[-1]] = self.expect("TIDENT").text   # Eq/Ord — akceptowane
                if not self.accept(","):
                    break
            self.expect(">")
        return ps

    def params(self):
        ps = []
        self.expect("(")
        self.skip_semis()
        while not self.at(")"):
            start = self.t.span
            inout = self.accept("inout")
            name = self.expect("IDENT", "nazwy parametru").text
            self.expect(":")
            ty = self.type_()
            ps.append(Param(name, ty, inout, sp(start, ty.span)))
            self.skip_semis()
            if not self.accept(","):
                break
            self.skip_semis()
        self.expect(")")
        return ps

    def fn_decl(self, pub):
        start = self.t.span
        lemma = self.accept("lemma")
        partial = False if lemma else self.accept("partial")
        self.expect("fn")
        name = self.expect("IDENT", "nazwy funkcji").text
        tps = self.tparams()
        bounds = self.bounds
        params = self.params()
        ret = None
        if self.accept("->"):
            ret = self.type_()
        if self.accept("!"):
            self.expect("{")
            while not self.at("}"):
                self.adv()
            self.expect("}")
        self.skip_semis()
        requires, ensures, decreases, examples = [], [], None, []
        while self.at("requires", "ensures", "decreases"):
            kw = self.adv().kind
            f = self.expr()
            if kw == "requires":
                requires.append(f)
            elif kw == "ensures":
                ensures.append(f)
            else:
                decreases = f
            self.skip_semis()
        if self.at("examples"):
            examples = self.examples()
            self.skip_semis()
        body = self.block()
        f = FnDecl(name, tps, params, ret, requires, ensures, decreases, examples,
                   body, partial, pub, sp(start, body.span))
        f.lemma = lemma
        f.tbounds = bounds
        return f

    def examples(self):
        self.expect("examples")
        self.expect("{")
        exs = []
        self.skip_semis()
        while not self.at("}"):
            start = self.t.span
            if self.at("forall") and self.peek().kind == "IDENT" and self.peek(2).kind == ":":
                self.adv()
                binders = []
                while True:
                    nm = self.expect("IDENT").text
                    self.expect(":")
                    binders.append((nm, self.type_()))
                    if not self.accept(","):
                        break
                self.expect(":")
                self.skip_semis()
                e = self.expr()
                exs.append(Example(e, binders, sp(start, e.span)))
            else:
                e = self.expr()
                exs.append(Example(e, None, sp(start, e.span)))
            self.skip_semis()
        self.expect("}")
        return exs

    def data_decl(self):
        start = self.expect("data").span
        name = self.expect("TIDENT", "nazwy typu").text
        tps = self.tparams()
        bounds = self.bounds
        self.expect("{")
        ctors = []
        self.skip_semis()
        while not self.at("}"):
            cs = self.t.span
            cname = self.expect("TIDENT", "konstruktora").text
            fields = []
            if self.accept("("):
                self.skip_semis()
                while not self.at(")"):
                    fname = self.expect("IDENT", "nazwy pola").text
                    self.expect(":")
                    fields.append((fname, self.type_()))
                    self.skip_semis()
                    if not self.accept(","):
                        break
                    self.skip_semis()
                self.expect(")")
            ctors.append(Ctor(cname, fields, cs))
            self.skip_semis()
            if not self.accept(","):
                break
            self.skip_semis()
        end = self.expect("}").span
        where = None
        if self.at(";") and self.peek().kind == "where":
            self.adv()
        if self.accept("where"):
            self.skip_semis()
            where = self.expr()
            end = where.span
        d = DataDecl(name, tps, ctors, where, sp(start, end))
        d.tbounds = bounds
        return d

    def type_alias(self):
        start = self.expect("type").span
        name = self.expect("TIDENT").text
        tps = self.tparams()
        self.expect("=")
        bounds = self.bounds
        ty = self.type_()
        t = TypeAlias(name, tps, ty, sp(start, ty.span))
        t.tbounds = bounds
        return t

    def spec_fn(self):
        start = self.expect("spec").span
        self.expect("fn")
        name = self.expect("IDENT").text
        tps = self.tparams()
        bounds = self.bounds
        params = self.params()
        self.expect("->")
        ret = self.type_()
        self.skip_semis()
        dec = None
        if self.accept("decreases"):
            dec = self.expr()
            self.skip_semis()
        self.expect("=")
        self.skip_semis()
        body = self.expr()
        s = SpecFn(name, tps, params, body, sp(start, body.span), ret, dec)
        s.tbounds = bounds
        return s

    def const_decl(self):
        start = self.expect("const").span
        name = self.expect("IDENT").text
        self.expect(":")
        ty = self.type_()
        self.expect("=")
        e = self.expr()
        return ConstDecl(name, ty, e, sp(start, e.span))

    # ---------- typy ----------
    def type_(self):
        start = self.t.span
        if self.at("fn"):
            self.adv()
            self.expect("(")
            ps = []
            while not self.at(")"):
                pname = None
                if self.at("IDENT") and self.peek().kind == ":":
                    pname = self.adv().text
                    self.adv()
                ps.append((pname, self.type_()))
                if not self.accept(","):
                    break
            self.expect(")")
            self.expect("->", "`->` w typie funkcyjnym")
            ret = self.type_()
            return TFn(ps, ret, sp(start, ret.span))
        name = self.expect("TIDENT", "typu").text
        args = []
        if self.accept("<"):
            while True:
                args.append(self.type_())
                if not self.accept(","):
                    break
            self.expect(">")
        base = TName(name, args, sp(start, self.toks[self.i - 1].span))
        if self.at("where"):
            self.adv()
            f = self.expr()
            return TRefine(base, f, sp(start, f.span))
        return base

    # ---------- bloki i instrukcje ----------
    def block(self) -> Block:
        start = self.expect("{", "`{`").span
        stmts = []
        self.skip_semis()
        while not self.at("}"):
            stmts.append(self.stmt())
            if not self.at("}"):
                self.expect(";", "końca instrukcji")
            self.skip_semis()
        end = self.expect("}").span
        return Block(stmts, sp(start, end))

    def loop_anns(self):
        invs, dec = [], None
        self.skip_semis()
        while self.at("invariant", "decreases"):
            kw = self.adv().kind
            f = self.expr()
            if kw == "invariant":
                invs.append(f)
            else:
                dec = f
            self.skip_semis()
        return invs, dec

    def stmt(self):
        start = self.t.span
        if self.at("let", "var"):
            mutable = self.adv().kind == "var"
            name = self.expect("IDENT", "nazwy zmiennej").text
            ty = None
            if self.accept(":"):
                ty = self.type_()
            self.expect("=")
            e = self.expr()
            return Let(name, ty, e, mutable, sp(start, e.span))
        if self.at("while"):
            self.adv()
            cond = self.expr()
            invs, dec = self.loop_anns()
            body = self.block()
            return While(cond, invs, dec, body, sp(start, body.span))
        if self.at("for"):
            self.adv()
            var = self.expect("IDENT").text
            self.expect("in")
            it = self.expr()
            invs, dec = self.loop_anns()
            if dec is not None:
                raise err("E0004", dec.span, "pętla `for` ma wariant automatyczny; `decreases` jest niedozwolone", ["4.3"])
            body = self.block()
            return For(var, it, invs, dec, body, sp(start, body.span))
        if self.at("return"):
            self.adv()
            e = None
            if not self.at(";", "}"):
                e = self.expr()
            return Return(e, sp(start, e.span if e else start))
        if self.at("break"):
            self.adv()
            return Break(start)
        if self.at("continue"):
            self.adv()
            return Continue(start)
        if self.at("assert"):
            self.adv()
            f = self.expr()
            return Assert(f, sp(start, f.span))
        e = self.expr()
        if self.at("="):
            self.adv()
            rhs = self.expr()
            if isinstance(e, Name):
                return Assign(e.name, rhs, sp(start, rhs.span))
            if isinstance(e, Index) and isinstance(e.expr, Name):
                return IndexAssign(e.expr.name, e.index, rhs, sp(start, rhs.span))
            raise err("E0005", e.span, "po lewej stronie `=` musi stać zmienna lub element tablicy", ["2.3"])
        return ExprStmt(e, e.span)

    # ---------- wyrażenia ----------
    def expr(self):
        if self.at("forall", "exists"):
            start = self.t.span
            kind = self.adv().kind
            var = self.expect("IDENT", "zmiennej kwantyfikowanej").text
            self.expect("in")
            lo = self.add_expr()
            self.expect("..")
            hi = self.add_expr()
            self.expect(":")
            body = self.expr()
            return Quant(kind, var, lo, hi, body, sp(start, body.span))
        return self.or_expr()

    def or_expr(self):
        e = self.and_expr()
        while self.at("||"):
            self.adv()
            r = self.and_expr() if not self.at("forall", "exists") else self.expr()
            e = Binary("||", e, r, sp(e.span, r.span))
        return e

    def and_expr(self):
        e = self.cmp_expr()
        while self.at("&&"):
            self.adv()
            r = self.cmp_expr() if not self.at("forall", "exists") else self.expr()
            e = Binary("&&", e, r, sp(e.span, r.span))
        return e

    def cmp_expr(self):
        e = self.add_expr()
        if self.at("==", "!=", "<", "<=", ">", ">="):
            op = self.adv().kind
            r = self.add_expr()
            e = Binary(op, e, r, sp(e.span, r.span))
            if self.at("==", "!=", "<", "<=", ">", ">="):
                raise err("E0006", self.t.span, "porównania są niełączne — użyj nawiasów lub `&&`", ["2.4"])
        return e

    def add_expr(self):
        e = self.mul_expr()
        while self.at("+", "-"):
            op = self.adv().kind
            r = self.mul_expr()
            e = Binary(op, e, r, sp(e.span, r.span))
        return e

    def mul_expr(self):
        e = self.unary()
        while self.at("*", "/", "%"):
            op = self.adv().kind
            r = self.unary()
            e = Binary(op, e, r, sp(e.span, r.span))
        return e

    def unary(self):
        if self.at("-", "!"):
            t = self.adv()
            e = self.unary()
            return Unary(t.kind, e, sp(t.span, e.span))
        return self.postfix()

    def args(self):
        args = []
        self.expect("(")
        self.skip_semis()
        while not self.at(")"):
            start = self.t.span
            if self.accept("&"):
                nm = self.expect("IDENT", "zmiennej dla argumentu inout")
                args.append(Arg(None, nm.text, sp(start, nm.span)))
            else:
                e = self.expr()
                args.append(Arg(e, None, e.span))
            self.skip_semis()
            if not self.accept(","):
                break
            self.skip_semis()
        end = self.expect(")").span
        return args, end

    def postfix(self):
        e = self.primary()
        while True:
            if self.at("[") :
                self.adv()
                idx = self.expr()
                end = self.expect("]").span
                e = Index(e, idx, sp(e.span, end))
            elif self.at("."):
                self.adv()
                nm = self.expect("IDENT", "nazwy pola")
                e = Field(e, nm.text, sp(e.span, nm.span))
            elif self.at("?"):
                q = self.adv()
                e = Try(e, sp(e.span, q.span))
            else:
                return e

    def primary(self):
        t = self.t
        if t.kind == "INT":
            self.adv()
            lit = IntLit(t.value, t.span)
            lit.text = t.text         # zapis źródłowy (0x…, 1_000, b'a') dla formatera
            return lit
        if t.kind in ("true", "false"):
            self.adv()
            return BoolLit(t.kind == "true", t.span)
        if t.kind == "HOLE":
            self.adv()
            return Hole(t.value, t.span)
        if t.kind == "result":
            self.adv()
            return ResultRef(t.span)
        if t.kind == "self":
            self.adv()
            return SelfRef(t.span)
        if t.kind == "old":
            self.adv()
            self.expect("(")
            nm = self.expect("IDENT")
            end = self.expect(")").span
            return Old(nm.text, sp(t.span, end))
        if t.kind == "IDENT":
            self.adv()
            if self.at("("):
                args, end = self.args()
                return Call(t.text, args, sp(t.span, end))
            return Name(t.text, t.span)
        if t.kind == "TIDENT":
            self.adv()
            if self.at("("):
                args, end = self.args()
                for a in args:
                    if a.inout:
                        raise err("E0007", a.span, "konstruktor nie przyjmuje argumentów inout", ["3.2"])
                return CtorCall(t.text, [a.expr for a in args], sp(t.span, end))
            return CtorCall(t.text, [], t.span)
        if t.kind == "(":
            self.adv()
            if self.at(")"):
                end = self.adv().span
                return UnitLit(sp(t.span, end))
            e = self.expr()
            self.expect(")")
            return e
        if t.kind == "[":
            self.adv()
            items = []
            self.skip_semis()
            while not self.at("]"):
                items.append(self.expr())
                self.skip_semis()
                if not self.accept(","):
                    break
                self.skip_semis()
            end = self.expect("]").span
            return ArrayLit(items, sp(t.span, end))
        if t.kind == "{":
            b = self.block()
            return BlockExpr(b, b.span)
        if t.kind == "fn":
            self.adv()
            self.expect("(")
            ps = []
            while not self.at(")"):
                pn = self.expect("IDENT", "nazwy parametru domknięcia").text
                pt = self.type_() if self.accept(":") else None
                ps.append((pn, pt))
                if not self.accept(","):
                    break
            self.expect(")")
            ret = self.type_() if self.accept("->") else None
            self.expect("=>", "`=>` w domknięciu")
            self.skip_semis()
            body = self.expr()
            return Lambda(ps, ret, body, sp(t.span, body.span))
        if t.kind == "if":
            return self.if_expr()
        if t.kind == "match":
            return self.match_expr()
        if t.kind == "STR":
            self.adv()
            return StrLit([IntLit(b, t.span) for b in t.value], t.span, t.text)
        found = "koniec wiersza" if (t.kind == ";" and t.implicit) else (t.text or t.kind)
        raise err("E0002", t.span, f"oczekiwano wyrażenia, znaleziono `{found}`", ["2.3"])

    def if_expr(self):
        start = self.expect("if").span
        cond = self.expr()
        then = self.block()
        els = None
        end = then.span
        if self.at("else"):
            self.adv()
            if self.at("if"):
                els = self.if_expr()
            else:
                els = self.block()
            end = els.span
        return If(cond, then, els, sp(start, end))

    def pattern(self):
        t = self.t
        if t.kind == "IDENT":
            self.adv()
            if t.text == "_":
                return Pattern("wild", span=t.span)
            return Pattern("var", name=t.text, span=t.span)
        if t.kind == "INT":
            self.adv()
            p = Pattern("int", value=t.value, span=t.span)
            p.text = t.text
            return p
        if t.kind == "-" and self.peek().kind == "INT":
            self.adv()
            v = self.adv()
            p = Pattern("int", value=-v.value, span=sp(t.span, v.span))
            p.text = "-" + v.text
            return p
        if t.kind in ("true", "false"):
            self.adv()
            return Pattern("bool", value=(t.kind == "true"), span=t.span)
        if t.kind == "TIDENT":
            self.adv()
            args = []
            end = t.span
            if self.accept("("):
                while not self.at(")"):
                    args.append(self.pattern())
                    if not self.accept(","):
                        break
                end = self.expect(")").span
            return Pattern("ctor", name=t.text, args=args, span=sp(t.span, end))
        raise err("E0002", t.span, f"oczekiwano wzorca, znaleziono `{t.text}`", ["2.3"])

    def match_expr(self):
        start = self.expect("match").span
        scrut = self.expr()
        self.expect("{")
        arms = []
        self.skip_semis()
        while not self.at("}"):
            ps = self.t.span
            pat = self.pattern()
            guard = None
            if self.accept("if"):
                guard = self.expr()
            self.expect("=>")
            self.skip_semis()
            body = self.expr()
            arms.append(Arm(pat, guard, body, sp(ps, body.span)))
            self.skip_semis()
            if not self.accept(","):
                break
            self.skip_semis()
        end = self.expect("}").span
        return Match(scrut, arms, sp(start, end))


def parse(src: str) -> Program:
    p = Parser(src)
    prog = p.program()
    prog.comments = p.comments
    return prog
