# SPDX-License-Identifier: MIT OR Apache-2.0
"""Generator warunków weryfikacji (rozdz. 6) w postaci wykonania symbolicznego.

Każde zobowiązanie κ jest sprawdzane przy hipotezach ścieżki, które zawierają
wszystkie wcześniejsze zobowiązania (assume-after-assert, §6.4.1).
Pętle: niezmienniki + havoc zapisywanych zmiennych; wywołania: kontrakty."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import z3

from .ast import *
from .check import RT, INT, BOOL, UNIT, subst_rt
from .smt import Enc, tdiv, trem, INT_MIN, INT_MAX
from .pp import show
from .diag import err

EXPLICIT = {"pre", "post", "inv-init", "inv-pres", "var-nn", "var-dec", "term",
            "refine", "assert", "wd", "data-inv"}


# ---------------- stan symboliczny ----------------
class State:
    __slots__ = ("env", "pc", "inductive", "tys", "facts")

    def __init__(self, env, pc, inductive, tys, facts):
        self.env, self.pc, self.inductive, self.tys, self.facts = env, pc, inductive, tys, facts

    def assume(self, c, fact=None, inductive=False):
        return State(self.env, self.pc + (c,), self.inductive or inductive, self.tys,
                     self.facts + ((fact,) if fact else ()))

    def bind(self, name, v, rt=None):
        env = dict(self.env)
        env[name] = v
        tys = self.tys
        if rt is not None:
            tys = dict(tys)
            tys[name] = rt
        return State(env, self.pc, self.inductive, tys, self.facts)


@dataclass
class R:
    outs: list = field(default_factory=list)      # [(State, value)]
    brks: list = field(default_factory=list)
    conts: list = field(default_factory=list)

    def add(self, o: "R"):
        self.outs += o.outs
        self.brks += o.brks
        self.conts += o.conts


@dataclass
class Ob:
    kind: str
    key: tuple
    span: Span
    site: Span
    text: str
    phi: object
    pc: tuple
    inductive: bool
    fn: str
    label: Optional[str] = None
    loop_info: Optional[dict] = None
    status: str = "pending"
    model: object = None


@dataclass
class FnCtx:
    decl: FnDecl
    sig: object
    t0: object = None
    old: dict = None
    scc: frozenset = frozenset()
    loops: list = field(default_factory=list)     # stos pętli: (span, writes, invariants)


@dataclass
class Fx:
    result: object = None
    old: dict = None
    self_: object = None


def merge(pairs):
    """Łączy stany z różnych ścieżek w jeden (ite na wartościach)."""
    pairs = [p for p in pairs if p is not None]
    if not pairs:
        return None
    if len(pairs) == 1:
        return pairs[0]
    pcs = [s.pc for s, _ in pairs]
    n = 0
    while all(len(p) > n for p in pcs) and all(p[n] is pcs[0][n] for p in pcs):
        n += 1
    prefix = pcs[0][:n]
    conds = [z3.And(*p[n:]) if len(p) > n else z3.BoolVal(True) for p in pcs]
    keys = set(pairs[0][0].env)
    for s, _ in pairs[1:]:
        keys &= set(s.env)
    env = {}
    for k in keys:
        vals = [s.env[k] for s, _ in pairs]
        if all(v.eq(vals[0]) for v in vals[1:]):
            env[k] = vals[0]
        else:
            t = vals[-1]
            for c, v in zip(reversed(conds[:-1]), reversed(vals[:-1])):
                t = z3.If(c, v, t)
            env[k] = t
    vals = [v for _, v in pairs]
    if all(v is None for v in vals):
        val = None
    else:
        val = vals[-1]
        for c, v in zip(reversed(conds[:-1]), reversed(vals[:-1])):
            val = z3.If(c, v, val)
    tys = {}
    for s, _ in pairs:
        tys.update(s.tys)
    common = 0
    fl = [s.facts for s, _ in pairs]
    while all(len(f) > common for f in fl) and all(f[common] == fl[0][common] for f in fl):
        common += 1
    facts = fl[0][:common]
    st = State(env, prefix + (z3.Or(*conds),), any(s.inductive for s, _ in pairs), tys, facts)
    return st, val


def writes_of(node):
    ws = set()
    for n in walk(node):
        if isinstance(n, (Assign, IndexAssign)):
            ws.add(n.name)
        elif isinstance(n, Call):
            for a in n.args:
                if a.inout:
                    ws.add(a.inout)
    return ws


def mark_tail(block):
    if block.stmts and isinstance(block.stmts[-1], ExprStmt):
        mark_tail_expr(block.stmts[-1].expr)
    for s in block.stmts:
        if isinstance(s, Return) and s.expr is not None:
            mark_tail_expr(s.expr)
        for n in walk(s):
            if isinstance(n, Return) and n.expr is not None:
                mark_tail_expr(n.expr)


def mark_tail_expr(e):
    if isinstance(e, Hole):
        e.tail = True
    elif isinstance(e, If):
        mark_tail(e.then)
        if isinstance(e.els, Block):
            mark_tail(e.els)
        elif isinstance(e.els, If):
            mark_tail_expr(e.els)
    elif isinstance(e, Match):
        for a in e.arms:
            mark_tail_expr(a.body)
    elif isinstance(e, BlockExpr):
        mark_tail(e.block)


class Verifier:
    def __init__(self, checker, rlimit=1_000_000):
        self.ch = checker
        self.enc = Enc(checker)
        self.obs: list = []
        self.holes: list = []
        self.desc = {}            # nazwa stałej -> (wyświetlana nazwa, opis)
        self.rlimit = rlimit
        self.cur: Optional[FnCtx] = None
        self.loops_by_line = {}
        Verifier._count = getattr(Verifier, "_count", 0) + 1
        self.uid = Verifier._count  # unikalne nazwy funkcji rekurencyjnych we wspólnym kontekście Z3
        self.recfuns = {}          # (spec, typy) -> RecFunction
        self.ranks = {}            # kształt typu danych -> funkcja rangi
        self.axioms = []           # rank(x) >= 1
        self.spec_axioms = {}      # spec -> [∀ args. uściślenia parametrów ⇒ uściślenie wyniku]
        self.exclude = frozenset() # specyfikacje, których aksjomatów nie wolno użyć (dowód indukcyjny)
        self.enc.inv_fn = self.inv_term
        self.tsub = {}             # podstawienie typów przy tłumaczeniu kontraktów funkcji generycznych

    def T(self, rt):
        return subst_rt(rt, self.tsub) if (self.tsub and rt is not None) else rt

    # ================= formuły =================
    def tr(self, e, env, fx: Fx):
        """Tłumaczenie formuły: zwraca (term, wd)."""
        T = z3.BoolVal(True)
        if isinstance(e, IntLit):
            return z3.IntVal(e.value), T
        if isinstance(e, BoolLit):
            return z3.BoolVal(e.value), T
        if isinstance(e, UnitLit):
            return self.enc.unit(), T
        if isinstance(e, Name):
            if e.name in env:
                return env[e.name], T
            if e.name in self.ch.consts:
                return z3.IntVal(self.ch.consts[e.name].value), T
            raise err("E1010", e.span, f"nieznana zmienna `{e.name}`", ["6.1"])
        if isinstance(e, SelfRef):
            return fx.self_, T
        if isinstance(e, ResultRef):
            return fx.result, T
        if isinstance(e, Old):
            if fx.old is not None and e.name in fx.old:
                return fx.old[e.name], T
            return env[e.name], T
        if isinstance(e, Unary):
            a, w = self.tr(e.expr, env, fx)
            return (-a if e.op == "-" else z3.Not(a)), w
        if isinstance(e, Binary):
            a, wa = self.tr(e.left, env, fx)
            b, wb = self.tr(e.right, env, fx)
            op = e.op
            if op == "&&":
                return z3.And(a, b), z3.And(wa, z3.Implies(a, wb))
            if op == "||":
                return z3.Or(a, b), z3.And(wa, z3.Implies(z3.Not(a), wb))
            w = z3.And(wa, wb)
            if op == "+": return a + b, w
            if op == "-": return a - b, w
            if op == "*": return a * b, w
            if op == "/": return tdiv(a, b), z3.And(w, b != 0)
            if op == "%": return trem(a, b), z3.And(w, b != 0)
            if op == "<": return a < b, w
            if op == "<=": return a <= b, w
            if op == ">": return a > b, w
            if op == ">=": return a >= b, w
            eq = self.eq(self.T(e.left.ty), a, b)
            return (eq if op == "==" else z3.Not(eq)), w
        if isinstance(e, Index):
            a, wa = self.tr(e.expr, env, fx)
            i, wi = self.tr(e.index, env, fx)
            ln = self.enc.arr_len(a)
            return z3.Select(self.enc.arr_data(a), i), z3.And(wa, wi, 0 <= i, i < ln)
        if isinstance(e, Field):
            a, wa = self.tr(e.expr, env, fx)
            if e.name == "len" and e.expr.ty.kind == "Array":
                return self.enc.arr_len(a), wa
            return self.field(self.T(e.expr.ty), e.name, a), wa
        if isinstance(e, Quant):
            lo, wl = self.tr(e.lo, env, fx)
            hi, wh = self.tr(e.hi, env, fx)
            k = z3.Int(f"{e.var}!q{id(e) % 100000}")
            env2 = dict(env)
            env2[e.var] = k
            b, wb = self.tr(e.body, env2, fx)
            rng = z3.And(lo <= k, k < hi)
            if e.kind == "forall":
                t = z3.ForAll([k], z3.Implies(rng, b))
            else:
                t = z3.Exists([k], z3.And(rng, b))
            return t, z3.And(wl, wh, z3.ForAll([k], z3.Implies(rng, wb)))
        if isinstance(e, Call):
            args = []
            w = T
            for a in e.args:
                t, wa = self.tr(a.expr, env, fx)
                args.append(t)
                w = z3.And(w, wa)
            if e.name in self.ch.specs and getattr(self.ch.specs[e.name], "recursive", False):
                sf = self.ch.specs[e.name]
                targs = {k: self.T(v) for k, v in (e.targs or {}).items()}
                f = self.recfun(sf, targs)
                penv = {p[0]: v for p, v in zip(sf.rparams, args)}
                conds = []
                for (pn, pt, _), v in zip(sf.rparams, args):
                    conds += self.enc.hyp(v, subst_rt(pt, targs), self.refine_fn(penv), refs_only=True)
                return f(*args), z3.And(w, *conds)
            if e.name in self.ch.specs:
                sf = self.ch.specs[e.name]
                penv = {p[0]: v for p, v in zip(sf.rparams, args)}
                saved = self.tsub
                self.tsub = {k: self.T(v) for k, v in (e.targs or {}).items()}
                try:
                    b, wb = self.tr(sf.body, penv, Fx())
                finally:
                    self.tsub = saved
                return b, z3.And(w, wb)
            return self.builtin_pure(e, args), w
        if isinstance(e, CtorCall):
            args = []
            w = T
            for a in e.args:
                t, wa = self.tr(a, env, fx)
                args.append(t)
                w = z3.And(w, wa)
            return self.enc.mk_ctor(self.T(e.ty), e.name, args), w
        if isinstance(e, Match):
            v, wv = self.tr(e.expr, env, fx)
            mrt = self.T(e.expr.ty)
            res = None
            wds = [wv]
            for arm in reversed(e.arms):
                cond, binds = self.pat(arm.pattern, v, mrt)
                env2 = dict(env)
                env2.update(binds)
                g, wg = (self.tr(arm.guard, env2, fx) if arm.guard is not None else (T, T))
                b, wb = self.tr(arm.body, env2, fx)
                c = z3.And(cond, g)
                res = b if res is None else z3.If(c, b, res)
                wds.append(z3.Implies(cond, z3.And(wg, z3.Implies(g, wb))))
            return res, z3.And(*wds)
        if isinstance(e, If):
            c, wc = self.tr(e.cond, env, fx)
            a, wa = self.tr(e.then.stmts[0].expr, env, fx)
            els = e.els
            if isinstance(els, Block):
                b, wb = self.tr(els.stmts[0].expr, env, fx)
            else:
                b, wb = self.tr(els, env, fx)
            return z3.If(c, a, b), z3.And(wc, z3.Implies(c, wa), z3.Implies(z3.Not(c), wb))
        raise err("E6101", e.span, f"konstrukcja `{type(e).__name__}` nie jest dozwolona w formule", ["6.1"])

    def eq(self, rt, a, b):
        if rt is not None and rt.kind == "Array":
            return self.enc.arr_eq(a, b)
        return a == b

    def field(self, rt, name, a):
        d = self.ch.data[rt.name]
        cname, fields = d.rctors[0]
        for j, (fn, _) in enumerate(fields):
            if fn == name:
                return self.enc.field(rt, cname, j, a)
        raise KeyError(name)

    def pat(self, p: Pattern, v, rt: RT):
        """Zwraca (warunek dopasowania, wiązania)."""
        if p.kind == "wild":
            return z3.BoolVal(True), {}
        if p.kind == "var":
            return z3.BoolVal(True), {p.name: v}
        if p.kind == "int":
            return v == p.value, {}
        if p.kind == "bool":
            return v == z3.BoolVal(p.value), {}
        d = self.ch.data[rt.name]
        fields = dict(d.rctors)[p.name]
        s = dict(zip(d.tparams, rt.args))
        conds = [self.enc.is_ctor(rt, p.name, v)]
        binds = {}
        for j, ((fn, ft), sp_) in enumerate(zip(fields, p.args)):
            fv = self.enc.field(rt, p.name, j, v)
            c, b = self.pat(sp_, fv, subst_rt(ft, s).bare())
            conds.append(c)
            binds.update(b)
        return z3.And(*conds), binds

    def builtin_pure(self, e, args):
        n = e.name
        if n == "compare":
            rt = RT("Data", "Ordering")
            a, b = args
            return z3.If(a < b, self.enc.mk_ctor(rt, "Less", []),
                         z3.If(a == b, self.enc.mk_ctor(rt, "Equal", []), self.enc.mk_ctor(rt, "Greater", [])))
        if n == "min":
            return z3.If(args[0] <= args[1], args[0], args[1])
        if n == "max":
            return z3.If(args[0] >= args[1], args[0], args[1])
        if n == "contains":
            a, v = args
            k = z3.FreshInt("k")
            return z3.Exists([k], z3.And(0 <= k, k < self.enc.arr_len(a), z3.Select(self.enc.arr_data(a), k) == v))
        if n == "filled":
            nn, v = args
            rt = self.T(e.ty)
            return self.enc.mk_arr(self.enc.sort(rt), nn, z3.K(z3.IntSort(), v))
        if n in ("checked_add", "checked_sub", "checked_mul"):
            a, b = args
            r = a + b if n == "checked_add" else a - b if n == "checked_sub" else a * b
            rt = RT("Data", "Option", [INT])
            return z3.If(z3.And(r >= INT_MIN, r <= INT_MAX), self.enc.mk_ctor(rt, "Some", [r]), self.enc.mk_ctor(rt, "None", []))
        raise err("E6102", e.span, f"funkcja `{n}` nie jest dozwolona w formule", ["6.1"])

    def refine_fn(self, env):
        def f(formula, selfv):
            t, _ = self.tr(formula, env, Fx(self_=selfv))
            return t
        return f

    # ================= zobowiązania =================
    def ob(self, kind, st: State, phi, key, span, text, site=None, label=None, loop_info=None, assume=True):
        if st is None:
            return None
        o = Ob(kind, key, span, site or span, text, phi, st.pc, st.inductive,
               self.cur.decl.name, label, loop_info)
        o.exclude = self.exclude
        self.obs.append(o)
        return st.assume(phi) if assume else st

    # ================= wyrażenia =================
    def ev(self, e, st: State) -> R:
        if isinstance(e, IntLit):
            return R([(st, z3.IntVal(e.value))])
        if isinstance(e, BoolLit):
            return R([(st, z3.BoolVal(e.value))])
        if isinstance(e, UnitLit):
            return R([(st, self.enc.unit())])
        if isinstance(e, Name):
            if e.name in st.env:
                return R([(st, st.env[e.name])])
            return R([(st, z3.IntVal(self.ch.consts[e.name].value))])
        if isinstance(e, Hole):
            self.hole(e, st)
            return R()
        if isinstance(e, Unary):
            r = self.ev(e.expr, st)
            out = R(brks=r.brks, conts=r.conts)
            for s, v in r.outs:
                if e.op == "!":
                    out.outs.append((s, z3.Not(v)))
                else:
                    s2 = self.ob("overflow", s, z3.And(-v >= INT_MIN, -v <= INT_MAX), ("overflow", e.span), e.span,
                                 f"int_min <= -{show(e.expr, prec=6)} && -{show(e.expr, prec=6)} <= int_max")
                    out.outs.append((s2, -v))
            return out
        if isinstance(e, Binary):
            return self.binary(e, st)
        if isinstance(e, Index):
            r = self.ev_seq([e.expr, e.index], st)
            out = R(brks=r.brks, conts=r.conts)
            for s, (a, i) in r.outs:
                ln = self.enc.arr_len(a)
                s2 = self.ob("bounds", s, z3.And(0 <= i, i < ln), ("bounds", e.span), e.span,
                             f"0 <= {show(e.index)} && {show(e.index)} < {show(e.expr, prec=9)}.len")
                out.outs.append((s2, z3.Select(self.enc.arr_data(a), i)))
            return out
        if isinstance(e, Field):
            r = self.ev(e.expr, st)
            out = R(brks=r.brks, conts=r.conts)
            for s, a in r.outs:
                if e.name == "len" and e.expr.ty.kind == "Array":
                    out.outs.append((s, self.enc.arr_len(a)))
                else:
                    out.outs.append((s, self.field(e.expr.ty, e.name, a)))
            return out
        if isinstance(e, ArrayLit):
            r = self.ev_seq(e.items, st)
            return R([(s, self.enc.arr_lit(e.ty, vs)) for s, vs in r.outs], r.brks, r.conts)
        if isinstance(e, CtorCall):
            r = self.ev_seq(e.args, st)
            out = R(brks=r.brks, conts=r.conts)
            d = self.ch.data[e.ty.name]
            sub = dict(zip(d.tparams, e.ty.args))
            fields = dict(d.rctors)[e.name]
            for s, vs in r.outs:
                v = self.enc.mk_ctor(e.ty, e.name, vs)
                conds, texts = [], []
                for (fn_, ft), a, av in zip(fields, e.args, vs):
                    ft2 = subst_rt(ft, sub)
                    if ft2.refs:
                        conds += self.enc.hyp(av, self.T(ft2), self.refine_fn({}), refs_only=True)
                        texts += [show(x, {"self": show(a)}) for x in ft2.refs]
                if d.where is not None:
                    conds.append(self.inv_term(e.ty, v))
                    texts.append(show(d.where, {"self": show(e)}))
                if conds:
                    s = self.ob("data-inv", s, z3.And(*conds), ("data-inv", e.span), e.span, " && ".join(texts),
                                label=f"niezmiennik / uściślenia pól `{d.name}`: {' && '.join(texts)}")
                out.outs.append((s, v))
            return out
        if isinstance(e, Try):
            return self.ev(e.desugared, st)
        if isinstance(e, Call):
            return self.call(e, st)
        if isinstance(e, If):
            return self.if_(e, st)
        if isinstance(e, Match):
            return self.match(e, st)
        if isinstance(e, BlockExpr):
            return self.block(e.block, st)
        raise err("E0099", e.span, f"nieobsługiwane wyrażenie {type(e).__name__}", [])

    def ev_seq(self, exprs, st):
        cur = [(st, [])]
        brks, conts = [], []
        for x in exprs:
            nxt = []
            for s, vs in cur:
                r = self.ev(x, s)
                brks += r.brks
                conts += r.conts
                nxt += [(s2, vs + [v]) for s2, v in r.outs]
            cur = nxt
        return R(cur, brks, conts)

    def binary(self, e, st):
        op = e.op
        if op in ("&&", "||"):
            r = self.ev(e.left, st)
            out = R(brks=r.brks, conts=r.conts)
            for s, a in r.outs:
                if op == "&&":
                    rr = self.ev(e.right, s.assume(a))
                    out.add(rr)
                    out.outs.append((s.assume(z3.Not(a)), z3.BoolVal(False)))
                else:
                    rr = self.ev(e.right, s.assume(z3.Not(a)))
                    out.add(rr)
                    out.outs.append((s.assume(a), z3.BoolVal(True)))
            m = merge(out.outs)
            out.outs = [m] if m else []
            return out
        r = self.ev_seq([e.left, e.right], st)
        out = R(brks=r.brks, conts=r.conts)
        for s, (a, b) in r.outs:
            if op in ("+", "-", "*"):
                v = a + b if op == "+" else a - b if op == "-" else a * b
                s = self.ob("overflow", s, z3.And(v >= INT_MIN, v <= INT_MAX), ("overflow", e.span), e.span,
                            f"int_min <= {show(e)} && {show(e)} <= int_max")
            elif op in ("/", "%"):
                s = self.ob("div0", s, z3.And(b != 0, z3.Not(z3.And(a == INT_MIN, b == -1))), ("div0", e.span), e.span,
                            f"{show(e.right, prec=6)} != 0 && !({show(e.left, prec=6)} == int_min && {show(e.right, prec=6)} == -1)")
                v = tdiv(a, b) if op == "/" else trem(a, b)
            elif op == "<": v = a < b
            elif op == "<=": v = a <= b
            elif op == ">": v = a > b
            elif op == ">=": v = a >= b
            else:
                v = self.eq(e.left.ty, a, b)
                if op == "!=":
                    v = z3.Not(v)
            out.outs.append((s, v))
        return out

    def if_(self, e, st):
        r = self.ev(e.cond, st)
        out = R(brks=r.brks, conts=r.conts)
        for s, c in r.outs:
            ft = show(e.cond)
            out.add(self.block(e.then, s.assume(c, ft)))
            se = s.assume(z3.Not(c), f"!({ft})")
            if e.els is None:
                out.outs.append((se, self.enc.unit()))
            elif isinstance(e.els, If):
                out.add(self.if_(e.els, se))
            else:
                out.add(self.block(e.els, se))
        m = merge(out.outs)
        out.outs = [m] if m else []
        return out

    def match(self, e, st):
        r = self.ev(e.expr, st)
        out = R(brks=r.brks, conts=r.conts)
        rt = e.expr.ty
        for s, v in r.outs:
            rem = s
            for arm in e.arms:
                cond, binds = self.pat(arm.pattern, v, rt)
                sa = rem.assume(cond, f"{show(e.expr)} is {_patstr(arm.pattern)}")
                for k, bv in binds.items():
                    sa = sa.bind(k, bv)
                sa = self.assume_pat_types(sa, arm.pattern, binds)
                if arm.guard is not None:
                    gr = self.ev(arm.guard, sa)
                    out.brks += gr.brks
                    out.conts += gr.conts
                    for sg, g in gr.outs:
                        out.add(self.ev(arm.body, sg.assume(g, show(arm.guard))))
                    gm = merge(gr.outs)
                    if gm is None:
                        break
                    sg, g = gm
                    rem = rem.assume(z3.Not(z3.And(cond, g)))
                else:
                    out.add(self.ev(arm.body, sa))
                    rem = rem.assume(z3.Not(cond))
        m = merge([(s.__class__(dict((k, val) for k, val in s.env.items() if k in st.env), s.pc, s.inductive, s.tys, s.facts), v)
                   for s, v in out.outs])
        out.outs = [m] if m else []
        return out

    # ================= wywołania =================
    def call(self, e, st):
        sig = e.callee
        targs = e.targs or {}
        val_exprs = [a.expr for a in e.args if a.inout is None]
        r = self.ev_seq(val_exprs, st)
        out = R(brks=r.brks, conts=r.conts)
        for s, vals in r.outs:
            it = iter(vals)
            args = []
            for a in e.args:
                args.append(s.env[a.inout] if a.inout else next(it))
            if sig.builtin:
                out.outs.append(self.call_builtin(e, s, args))
            else:
                res = self.call_user(e, s, args, sig, targs)
                if res is not None:
                    out.outs.append(res)
        return out

    def call_builtin(self, e, s, args):
        n = e.name
        if n == "push":
            a, v = args
            ln = self.enc.arr_len(a)
            s = self.ob("pre", s, ln < INT_MAX, ("pre", e.span, e.span), e.span, f"{e.args[0].inout}.len < int_max")
            new = self.enc.mk_arr(a.sort(), ln + 1, z3.Store(self.enc.arr_data(a), ln, v))
            return s.bind(e.args[0].inout, new), self.enc.unit()
        if n == "pop":
            a = args[0]
            ln = self.enc.arr_len(a)
            rt = e.ty
            res = z3.If(ln == 0, self.enc.mk_ctor(rt, "None", []),
                        self.enc.mk_ctor(rt, "Some", [z3.Select(self.enc.arr_data(a), ln - 1)]))
            new = z3.If(ln == 0, a, self.enc.mk_arr(a.sort(), ln - 1, self.enc.arr_data(a)))
            return s.bind(e.args[0].inout, new), res
        if n == "filled":
            s = self.ob("pre", s, args[0] >= 0, ("pre", e.span, e.span), e.span, f"{show(e.args[0].expr)} >= 0")
        return s, self.builtin_pure(e, args)

    def call_user(self, e, s, args, sig, targs):
        saved = self.tsub
        self.tsub = {k: self.T(v) for k, v in targs.items()}
        try:
            return self._call_user(e, s, args, sig, {k: self.T(v) for k, v in targs.items()})
        finally:
            self.tsub = saved

    def _call_user(self, e, s, args, sig, targs):
        decl = sig.decl
        cenv = {}
        for (pn, pt, pinout), v in zip(sig.params, args):
            cenv[pn] = v
        rf = self.refine_fn(cenv)
        # uściślenia parametrów
        for (pn, pt, pinout), v, a in zip(sig.params, args, e.args):
            pti = subst_rt(pt, targs)
            conds = self.enc.hyp(v, pti, rf, refs_only=True)
            if conds:
                text = " && ".join(show(rr, {"self": pn}) for rr in _all_refs(pti)) or str(pti)
                s = self.ob("pre", s, z3.And(*conds), ("pre", _ref_span(pt), e.span), _ref_span(pt) or a.span,
                            f"{pn}: {pti} — {text}", site=e.span)
        for q in decl.requires:
            phi, _ = self.tr(q, cenv, Fx())
            s = self.ob("pre", s, phi, ("pre", q.span, e.span), e.span, show(q), site=e.span)
        # terminacja
        if self.cur.t0 is not None and sig.name in self.cur.scc:
            tf, _ = self.tr(decl.decreases, cenv, Fx())
            tf = self.measure(tf, decl.decreases.ty)
            s = self.ob("term", s, z3.And(tf >= 0, tf < self.cur.t0), ("term", e.span), e.span,
                        f"0 <= {show(decl.decreases)} < {show(self.cur.decl.decreases)} (przy wejściu)")
        # wynik i wartości inout po wywołaniu
        line = e.span.line
        ret = subst_rt(sig.ret, targs)
        r = self.enc.fresh(f"{sig.name}()", ret)
        self.desc[str(r)] = (f"{sig.name}(…)", f"wynik wywołania `{sig.name}` z wiersza {line}")
        post_env = dict(cenv)
        oldm = {}
        upd = {}
        for (pn, pt, pinout), v, a in zip(sig.params, args, e.args):
            if pinout:
                nv = self.enc.fresh(a.inout, subst_rt(pt, targs))
                self.desc[str(nv)] = (a.inout, f"wartość po wywołaniu `{sig.name}` z wiersza {line}")
                post_env[pn] = nv
                oldm[pn] = v
                upd[a.inout] = nv
        hyps = self.enc.hyp(r, ret, self.refine_fn(post_env))
        for (pn, pt, pinout), a in zip(sig.params, e.args):
            if pinout:
                hyps += self.enc.hyp(post_env[pn], subst_rt(pt, targs), self.refine_fn(post_env))
        for q in decl.ensures:
            phi, _ = self.tr(q, post_env, Fx(result=r, old=oldm))
            hyps.append(phi)
        s2 = s.assume(z3.And(*hyps) if hyps else z3.BoolVal(True), f"postkondycja `{sig.name}`", inductive=True)
        for k, v in upd.items():
            s2 = s2.bind(k, v)
        return s2, r

    # ================= instrukcje =================
    def block(self, b: Block, st: State) -> R:
        outer = set(st.env)
        cur = [(st, self.enc.unit())]
        out = R()
        for k, stmt in enumerate(b.stmts):
            last = k == len(b.stmts) - 1
            nxt = R()
            for s, _ in cur:
                if isinstance(stmt, ExprStmt):
                    r = self.ev(stmt.expr, s)
                else:
                    r = self.stmt(stmt, s)
                nxt.add(r)
            out.brks += nxt.brks
            out.conts += nxt.conts
            m = merge(nxt.outs)
            if m is None:
                cur = []
                break
            s, v = m
            cur = [(s, v if (last and isinstance(stmt, ExprStmt)) else self.enc.unit())]
        # usunięcie zmiennych lokalnych bloku
        res = []
        for s, v in cur:
            env = {k: val for k, val in s.env.items() if k in outer}
            res.append((State(env, s.pc, s.inductive, s.tys, s.facts), v))
        out.outs = res
        out.brks = [State({k: v for k, v in s.env.items() if k in outer}, s.pc, s.inductive, s.tys, s.facts) for s in out.brks]
        out.conts = [State({k: v for k, v in s.env.items() if k in outer}, s.pc, s.inductive, s.tys, s.facts) for s in out.conts]
        return out

    def stmt(self, s, st) -> R:
        if isinstance(s, Let):
            r = self.ev(s.expr, st)
            out = R(brks=r.brks, conts=r.conts)
            for st2, v in r.outs:
                rt = s.rt
                if s.type is not None:
                    benv = dict(st2.env)
                    conds = self.enc.hyp(v, rt, self.refine_fn(benv), refs_only=True)
                    if conds:
                        txt = " && ".join(show(x, {"self": s.name}) for x in _all_refs(rt))
                        st2 = self.ob("refine", st2, z3.And(*conds), ("refine", _ref_span(rt), s.span),
                                      _ref_span(rt) or s.span, txt, site=s.span)
                out.outs.append((st2.bind(s.name, v, rt), self.enc.unit()))
            return out
        if isinstance(s, Assign):
            r = self.ev(s.expr, st)
            out = R(brks=r.brks, conts=r.conts)
            for st2, v in r.outs:
                rt = s.target_rt
                conds = self.enc.hyp(v, rt, self.refine_fn(dict(st2.env)), refs_only=True)
                if conds:
                    txt = " && ".join(show(x, {"self": s.name}) for x in _all_refs(rt))
                    st2 = self.ob("refine", st2, z3.And(*conds), ("refine", _ref_span(rt), s.span),
                                  s.span, txt, site=s.span)
                out.outs.append((st2.bind(s.name, v), self.enc.unit()))
            return out
        if isinstance(s, IndexAssign):
            r = self.ev_seq([s.index, s.expr], st)
            out = R(brks=r.brks, conts=r.conts)
            for st2, (i, v) in r.outs:
                a = st2.env[s.name]
                ln = self.enc.arr_len(a)
                st2 = self.ob("bounds", st2, z3.And(0 <= i, i < ln), ("bounds", s.span), s.span,
                              f"0 <= {show(s.index)} && {show(s.index)} < {s.name}.len")
                el = s.target_rt.args[0]
                conds = self.enc.hyp(v, el, self.refine_fn(dict(st2.env)), refs_only=True)
                if conds:
                    st2 = self.ob("refine", st2, z3.And(*conds), ("refine", _ref_span(el), s.span), s.span,
                                  " && ".join(show(x, {"self": "element"}) for x in _all_refs(el)), site=s.span)
                new = self.enc.mk_arr(a.sort(), ln, z3.Store(self.enc.arr_data(a), i, v))
                out.outs.append((st2.bind(s.name, new), self.enc.unit()))
            return out
        if isinstance(s, While):
            return self.loop(s, st)
        if isinstance(s, For):
            return self.for_(s, st)
        if isinstance(s, Return):
            if s.expr is None:
                self.post(st, self.enc.unit(), s.span)
                return R()
            r = self.ev(s.expr, st)
            for st2, v in r.outs:
                self.post(st2, v, s.span)
            return R(brks=r.brks, conts=r.conts)
        if isinstance(s, Break):
            return R(brks=[st])
        if isinstance(s, Continue):
            return R(conts=[st])
        if isinstance(s, Assert):
            phi, wd = self.tr(s.formula, st.env, Fx(old=self.cur.old))
            st = self.ob("wd", st, wd, ("wd", s.formula.span, s.span), s.formula.span, "formuła asercji jest określona", site=s.span)
            st = self.ob("assert", st, phi, ("assert", s.span), s.span, show(s.formula))
            return R([(st, self.enc.unit())])
        raise err("E0099", s.span, f"nieobsługiwana instrukcja {type(s).__name__}", [])

    # ================= pętle =================
    def havoc(self, st: State, names, loop_span, why):
        env = dict(st.env)
        hyps = []
        for w in sorted(names):
            if w not in env:
                continue
            rt = st.tys.get(w)
            nv = self.enc.fresh(w, rt)
            self.desc[str(nv)] = (w, why)
            env[w] = nv
        st2 = State(env, st.pc, True, st.tys, st.facts)
        for w in sorted(names):
            if w in env and w in st.tys:
                hyps += self.enc.hyp(env[w], st.tys[w], self.refine_fn(env))
        if hyps:
            st2 = st2.assume(z3.And(*hyps))
        return st2

    def loop(self, s: While, st: State, extra=None) -> R:
        line = s.span.line
        invs = s.invariants
        fx = Fx(old=self.cur.old)
        info = {"line": line, "writes": sorted(writes_of(s) & set(st.env)), "invariants": invs}
        self.loops_by_line[line] = invs
        for inv in invs:
            phi, wd = self.tr(inv, st.env, fx)
            st = self.ob("wd", st, wd, ("wd", inv.span, s.span), inv.span, "niezmiennik jest określony", site=s.span)
            st = self.ob("inv-init", st, phi, ("inv-init", inv.span, s.span), inv.span, show(inv), site=s.span, assume=False)
        sh = self.havoc(st, writes_of(s), s.span, f"po pętli z wiersza {line}")
        for inv in invs:
            phi, _ = self.tr(inv, sh.env, fx)
            sh = sh.assume(phi, show(inv))
        r = self.ev(s.cond, sh)
        out = R()
        for sc, c in r.outs:
            sb = sc.assume(c, show(s.cond))
            t0 = None
            if s.decreases is not None:
                t, wd = self.tr(s.decreases, sb.env, fx)
                t = self.measure(t, s.decreases.ty)
                sb = self.ob("wd", sb, wd, ("wd", s.decreases.span, s.span), s.decreases.span, "wariant jest określony", site=s.span)
                t0 = self.enc.fresh("t0", INT)
                sb = sb.assume(t0 == t)
                sb = self.ob("var-nn", sb, t0 >= 0, ("var-nn", s.decreases.span, s.span), s.decreases.span,
                             f"{show(s.decreases)} >= 0", site=s.span)
            br = self.block(s.body, sb)
            ends = [x for x, _ in br.outs] + br.conts
            m = merge([(x, None) for x in ends])
            if m is not None:
                se = m[0]
                for inv in invs:
                    phi, wd = self.tr(inv, se.env, fx)
                    se = self.ob("wd", se, wd, ("wd", inv.span, s.span), inv.span, "niezmiennik jest określony", site=s.span)
                    se = self.ob("inv-pres", se, phi, ("inv-pres", inv.span, s.span), inv.span, show(inv), site=s.span,
                                 loop_info=info)
                if t0 is not None:
                    t, _ = self.tr(s.decreases, se.env, fx)
                    t = self.measure(t, s.decreases.ty)
                    self.ob("var-dec", se, t < t0, ("var-dec", s.decreases.span, s.span), s.decreases.span,
                            f"{show(s.decreases)} maleje", site=s.span)
            out.outs.append((sc.assume(z3.Not(c), f"!({show(s.cond)})"), self.enc.unit()))
            out.outs += [(x, self.enc.unit()) for x in br.brks]
        m = merge(out.outs)
        out.outs = [m] if m else []
        return out

    def for_(self, s: For, st: State) -> R:
        line = s.span.line
        r = self.ev(s.iterable, st)
        out = R(brks=r.brks, conts=r.conts)
        arr_rt = s.iterable.ty
        fx = Fx(old=self.cur.old)
        for st0, a in r.outs:
            ln = self.enc.arr_len(a)
            sti = st0.bind("it", z3.IntVal(0), INT)
            auto = lambda env: z3.And(0 <= env["it"], env["it"] <= ln)
            for inv in s.invariants:
                phi, wd = self.tr(inv, sti.env, fx)
                sti = self.ob("wd", sti, wd, ("wd", inv.span, s.span), inv.span, "niezmiennik jest określony", site=s.span)
                sti = self.ob("inv-init", sti, phi, ("inv-init", inv.span, s.span), inv.span, show(inv), site=s.span, assume=False)
            ws = (writes_of(s.body) & set(st0.env)) | {"it"}
            info = {"line": line, "writes": sorted(ws - {"it"}), "invariants": s.invariants}
            self.loops_by_line[line] = s.invariants
            sh = self.havoc(sti, ws, s.span, f"po pętli z wiersza {line}")
            sh = sh.assume(auto(sh.env))
            for inv in s.invariants:
                phi, _ = self.tr(inv, sh.env, fx)
                sh = sh.assume(phi, show(inv))
            it = sh.env["it"]
            sb = sh.assume(it < ln, f"it < {show(s.iterable)}.len")
            sb = sb.bind(s.var, z3.Select(self.enc.arr_data(a), it), arr_rt.args[0])
            br = self.block(s.body, sb)
            ends = [x for x, _ in br.outs] + br.conts
            m = merge([(x, None) for x in ends])
            if m is not None:
                se = m[0].bind("it", m[0].env["it"] + 1)
                for inv in s.invariants:
                    phi, wd = self.tr(inv, se.env, fx)
                    se = self.ob("wd", se, wd, ("wd", inv.span, s.span), inv.span, "niezmiennik jest określony", site=s.span)
                    se = self.ob("inv-pres", se, phi, ("inv-pres", inv.span, s.span), inv.span, show(inv), site=s.span,
                                 loop_info=info)
            ex = sh.assume(z3.Not(it < ln))
            exits = [(ex, self.enc.unit())] + [(x, self.enc.unit()) for x in br.brks]
            mm = merge(exits)
            if mm:
                sx, _ = mm
                env = {k: v for k, v in sx.env.items() if k in st0.env}
                out.outs.append((State(env, sx.pc, sx.inductive, sx.tys, sx.facts), self.enc.unit()))
        m = merge(out.outs)
        out.outs = [m] if m else []
        return out

    # ================= postkondycje i dziury =================
    def post_env(self, st):
        return {k: v for k, v in st.env.items()}

    def post(self, st: State, v, site: Span):
        sig = self.cur.sig
        decl = self.cur.decl
        env = self.post_env(st)
        if decl.ret is not None:
            conds = self.enc.hyp(v, sig.ret, self.refine_fn(env), refs_only=True)
            if conds:
                txt = " && ".join(show(x, {"self": "result"}) for x in _all_refs(sig.ret))
                st = self.ob("post", st, z3.And(*conds), ("post", decl.ret.span, site), decl.ret.span, txt,
                             site=site, label=f"uściślenie wyniku: {txt}")
        for q in decl.ensures:
            phi, _ = self.tr(q, env, Fx(result=v, old=self.cur.old))
            st = self.ob("post", st, phi, ("post", q.span, site), q.span, show(q), site=site)
        for (pn, pt, pinout), p in zip(sig.params, decl.params):
            if pinout:
                conds = self.enc.hyp(env[pn], pt, self.refine_fn(env), refs_only=True)
                if conds:
                    st = self.ob("post", st, z3.And(*conds), ("post", p.type.span, site), p.type.span,
                                 f"uściślenie parametru `{pn}` na wyjściu", site=site)

    def hole(self, e: Hole, st: State):
        self.holes.append((e, st, self.cur))

    # ================= funkcje =================
    def verify_fn(self, f: FnDecl):
        sig = f.sig
        ctx = FnCtx(f, sig, scc=self.ch.scc.get(f.name, frozenset()))
        self.cur = ctx
        mark_tail(f.body)
        env, tys = {}, {}
        for (pn, pt, pinout) in sig.params:
            env[pn] = z3.Const(pn, self.enc.sort(pt))
            tys[pn] = pt
        st = State(env, (), False, tys, ())
        hyps = []
        for (pn, pt, pinout) in sig.params:
            hyps += self.enc.hyp(env[pn], pt, self.refine_fn(env))
        if hyps:
            st = st.assume(z3.And(*hyps))
        facts = []
        for q in f.requires:
            phi, wd = self.tr(q, env, Fx())
            st = self.ob("wd", st, wd, ("wd", q.span, f.span), q.span, "warunek wstępny jest określony", site=q.span)
            st = st.assume(phi, show(q))
        ctx.old = {pn: env[pn] for (pn, pt, pinout) in sig.params}
        if f.decreases is not None and not f.partial:
            t, wd = self.tr(f.decreases, env, Fx())
            st = self.ob("wd", st, wd, ("wd", f.decreases.span, f.span), f.decreases.span, "miara jest określona", site=f.span)
            ctx.t0 = self.measure(t, f.decreases.ty)
        # dobra określoność ensures
        if f.ensures:
            rv = self.enc.fresh("result", sig.ret)
            penv = dict(env)
            sp_ = st
            hy = self.enc.hyp(rv, sig.ret, self.refine_fn(penv))
            for (pn, pt, pinout) in sig.params:
                if pinout:
                    penv[pn] = self.enc.fresh(pn, pt)
                    hy += self.enc.hyp(penv[pn], pt, self.refine_fn(penv))
            if hy:
                sp_ = sp_.assume(z3.And(*hy))
            for q in f.ensures:
                phi, wd = self.tr(q, penv, Fx(result=rv, old=ctx.old))
                sp_ = self.ob("wd", sp_, wd, ("wd", q.span, f.span), q.span, "warunek końcowy jest określony", site=q.span)
                sp_ = sp_.assume(phi)
        r = self.block(f.body, st)
        last = f.body.stmts[-1] if f.body.stmts else None
        site = last.span if isinstance(last, ExprStmt) else f.body.span
        for s, v in r.outs:
            self.post(s, v, site)

    # ================= miary i rekurencyjne funkcje specyfikacyjne =================
    def measure(self, term, rt):
        rt = self.T(rt)
        if rt is not None and rt.kind == "Data":
            return self.rank(rt)(term)
        return term

    def rank(self, rt):
        """Ranga wartości typu danych: 1 + suma rang pól tego samego typu (porządek strukturalny)."""
        rt = rt.bare()
        key = rt.shape()
        if key in self.ranks:
            return self.ranks[key]
        srt = self.enc.sort(rt)
        f = z3.RecFunction(f"rank[{rt}]#{self.uid}", srt, z3.IntSort())
        self.ranks[key] = f
        x = z3.Const(f"x!rank{len(self.ranks)}", srt)
        d = self.ch.data[rt.name]
        sub = dict(zip(d.tparams, rt.args))
        body = None
        for cname, fields in reversed(d.rctors):
            parts = [z3.IntVal(1)]
            for j, (fn_, ft) in enumerate(fields):
                if subst_rt(ft, sub).bare().shape() == key:
                    parts.append(f(self.enc.field(rt, cname, j, x)))
            val = z3.Sum(*parts) if len(parts) > 1 else parts[0]
            body = val if body is None else z3.If(self.enc.is_ctor(rt, cname, x), val, body)
        z3.RecAddDefinition(f, [x], body)
        y = z3.Const(f"y!rank{len(self.ranks)}", srt)
        self.axioms.append(z3.ForAll([y], f(y) >= 1, patterns=[f(y)]))
        return f

    def inv_term(self, rt, v):
        """Niezmiennik typu danych zastosowany do wartości v."""
        d = self.ch.data[rt.name]
        saved = self.tsub
        self.tsub = {p: self.T(a) for p, a in zip(d.tparams, rt.args)}
        try:
            t, _ = self.tr(d.where, {}, Fx(self_=v))
        finally:
            self.tsub = saved
        return t

    def assume_pat_types(self, st, p, binds):
        """Zmienne wiązane wzorcem to wartości swoich typów: dodaj hipotezy h(x, τ)."""
        hyps = []
        def go(q):
            if q.kind == "var" and q.name in binds and q.ty is not None:
                hyps.extend(self.enc.hyp(binds[q.name], self.T(q.ty), self.refine_fn({})))
            for a in q.args:
                go(a)
        go(p)
        return st.assume(z3.And(*hyps)) if hyps else st

    def recfun(self, sf, targs):
        key = (sf.name, tuple(sorted((k, v.bare().shape()) for k, v in targs.items())))
        if key in self.recfuns:
            return self.recfuns[key]
        dom = [self.enc.sort(subst_rt(pt, targs)) for _, pt, _ in sf.rparams]
        rng = self.enc.sort(subst_rt(sf.rret, targs))
        tag = ",".join(str(v) for _, v in sorted(targs.items()))
        f = z3.RecFunction(sf.name + (f"<{tag}>" if tag else "") + f"#{self.uid}", *dom, rng)
        self.recfuns[key] = f
        params = [z3.Const(f"{pn}!{sf.name}", s) for (pn, _, _), s in zip(sf.rparams, dom)]
        saved = self.tsub
        self.tsub = dict(targs)
        try:
            body, _ = self.tr(sf.body, {pn: p for (pn, _, _), p in zip(sf.rparams, params)}, Fx())
        finally:
            self.tsub = saved
        z3.RecAddDefinition(f, params, body)
        rret = subst_rt(sf.rret, targs)
        if _all_refs(rret):
            xs = [z3.Const(f"{pn}!ax{sf.name}", s) for (pn, _, _), s in zip(sf.rparams, dom)]
            penv = {pn: x for (pn, _, _), x in zip(sf.rparams, xs)}
            pre = []
            for (pn, pt, _), x in zip(sf.rparams, xs):
                pre += self.enc.hyp(x, subst_rt(pt, targs), self.refine_fn(penv), refs_only=True)
            post = self.enc.hyp(f(*xs), rret, self.refine_fn(penv), refs_only=True)
            ax = z3.ForAll(xs, z3.Implies(z3.And(*pre), z3.And(*post)), patterns=[f(*xs)])
            self.spec_axioms.setdefault(sf.name, []).append(ax)
        return f

    def verify_spec(self, sf):
        """Zobowiązania rekurencyjnej funkcji specyfikacyjnej: określoność ciała i spadek miary."""
        self.cur = FnCtx(sf, None)
        env, tys = {}, {}
        for pn, pt, _ in sf.rparams:
            env[pn] = z3.Const(pn, self.enc.sort(pt))
            tys[pn] = pt
        st = State(env, (), False, tys, ())
        hyps = []
        for pn, pt, _ in sf.rparams:
            hyps += self.enc.hyp(env[pn], pt, self.refine_fn(env))
        if hyps:
            st = st.assume(z3.And(*hyps))
        t0, _ = self.tr(sf.decreases, env, Fx())
        t0 = self.measure(t0, sf.decreases.ty)
        scc = self.ch.spec_scc.get(sf.name, frozenset())
        self.exclude = scc
        # hipoteza indukcyjna: uściślenia wyników dla wywołań o mniejszej mierze
        for g in scc:
            gs = self.ch.specs[g]
            if not _all_refs(gs.rret) or gs.decreases is None:
                continue
            f = self.recfun(gs, {})
            xs = [z3.Const(f"{pn}!ih{g}", self.enc.sort(pt)) for pn, pt, _ in gs.rparams]
            penv = {pn: x for (pn, _, _), x in zip(gs.rparams, xs)}
            pre = []
            for (pn, pt, _), x in zip(gs.rparams, xs):
                pre += self.enc.hyp(x, pt, self.refine_fn(penv), refs_only=True)
            m, _ = self.tr(gs.decreases, penv, Fx())
            m = self.measure(m, gs.decreases.ty)
            post = self.enc.hyp(f(*xs), gs.rret, self.refine_fn(penv), refs_only=True)
            st = st.assume(z3.ForAll(xs, z3.Implies(z3.And(m < t0, *pre), z3.And(*post)), patterns=[f(*xs)]))
        body_t, wd = self.tr(sf.body, env, Fx())
        if _all_refs(sf.rret):
            conds = self.enc.hyp(body_t, sf.rret, self.refine_fn(env), refs_only=True)
            txt = " && ".join(show(x, {"self": "wynik"}) for x in _all_refs(sf.rret))
            self.ob("post", st, z3.And(*conds), ("post", sf.ret.span, sf.span), sf.ret.span, txt, site=sf.span)
        self.ob("wd", st, wd, ("wd", sf.body.span, sf.span), sf.body.span,
                f"ciało `{sf.name}` jest określone dla wszystkich argumentów", site=sf.span)
        scc = self.ch.spec_scc.get(sf.name, frozenset())

        def walk_(e, env, st):
            if isinstance(e, Call) and e.name in scc:
                args = [self.tr(a.expr, env, Fx())[0] for a in e.args]
                callee = self.ch.specs[e.name]
                cenv = {pn: v for (pn, _, _), v in zip(callee.rparams, args)}
                m, _ = self.tr(callee.decreases, cenv, Fx())
                m = self.measure(m, callee.decreases.ty)
                self.ob("term", st, z3.And(m >= 0, m < t0), ("term", e.span), e.span,
                        f"0 <= {show(callee.decreases)} < {show(sf.decreases)} (przy wejściu)")
                for a in e.args:
                    walk_(a.expr, env, st)
                return
            if isinstance(e, Match):
                walk_(e.expr, env, st)
                v, _ = self.tr(e.expr, env, Fx())
                rest = st
                for arm in e.arms:
                    cond, binds = self.pat(arm.pattern, v, self.T(e.expr.ty))
                    env2 = dict(env)
                    env2.update(binds)
                    sa = self.assume_pat_types(rest.assume(cond), arm.pattern, binds)
                    if arm.guard is not None:
                        walk_(arm.guard, env2, sa)
                        g, _ = self.tr(arm.guard, env2, Fx())
                        walk_(arm.body, env2, sa.assume(g))
                        rest = rest.assume(z3.Not(z3.And(cond, g)))
                    else:
                        walk_(arm.body, env2, sa)
                        rest = rest.assume(z3.Not(cond))
                return
            if isinstance(e, If):
                walk_(e.cond, env, st)
                c, _ = self.tr(e.cond, env, Fx())
                walk_(e.then.stmts[0].expr, env, st.assume(c))
                els = e.els.stmts[0].expr if isinstance(e.els, Block) else e.els
                walk_(els, env, st.assume(z3.Not(c)))
                return
            if isinstance(e, Binary) and e.op in ("&&", "||"):
                walk_(e.left, env, st)
                a, _ = self.tr(e.left, env, Fx())
                walk_(e.right, env, st.assume(a if e.op == "&&" else z3.Not(a)))
                return
            if isinstance(e, Quant):
                walk_(e.lo, env, st)
                walk_(e.hi, env, st)
                lo, _ = self.tr(e.lo, env, Fx())
                hi, _ = self.tr(e.hi, env, Fx())
                k = z3.Int(f"{e.var}!t{id(e) % 100000}")
                env2 = dict(env)
                env2[e.var] = k
                walk_(e.body, env2, st.assume(z3.And(lo <= k, k < hi)))
                return
            for k_, v_ in vars(e).items():
                if k_ in NON_CHILD:
                    continue
                for n in (v_ if isinstance(v_, list) else [v_]):
                    if isinstance(n, Arg):
                        n = n.expr
                    if isinstance(n, Node) and not isinstance(n, (Pattern, Block)):
                        walk_(n, env, st)

        walk_(sf.body, env, st)
        self.exclude = frozenset()

    def run(self):
        for sf in self.ch.specs.values():
            if getattr(sf, "recursive", False) and sf.decreases is not None:
                try:
                    self.verify_spec(sf)
                except z3.Z3Exception as ex:
                    raise err("E4999", sf.span, f"błąd wewnętrzny kodowania SMT: {ex}", [])
        for f in self.ch.user_fns:
            try:
                self.verify_fn(f)
            except z3.Z3Exception as ex:
                raise err("E4999", f.span, f"błąd wewnętrzny kodowania SMT: {ex}", [])
        for o in self.obs:
            self.solve(o)
        return self.obs

    def solve(self, o: Ob):
        s = z3.Solver()
        s.set("rlimit", self.rlimit)
        s.set("random_seed", 0)
        for ax in self.axioms_for(o.exclude):
            s.add(ax)
        for c in o.pc:
            s.add(c)
        s.add(z3.Not(o.phi))
        res = s.check()
        if res == z3.unsat:
            o.status = "proved"
        elif res == z3.sat:
            o.status = "refuted"
            o.model = s.model()
            small = self.small_model(s, list(o.pc) + [z3.Not(o.phi)])
            if small is not None:
                o.model = small
        else:
            o.status = "unknown"

    def axioms_for(self, exclude):
        out = list(self.axioms)
        for name, axs in self.spec_axioms.items():
            if name not in exclude:
                out += axs
        return out

    def small_model(self, s, exprs):
        """Próba znalezienia kontrprzykładu o małych wartościach (czytelność diagnostyki)."""
        from .driver import collect_consts
        bounds = []
        for c in collect_consts(exprs):
            srt = c.sort()
            if srt == z3.IntSort():
                bounds.append(z3.And(c >= -100, c <= 100))
            elif isinstance(srt, z3.DatatypeSortRef) and srt.name().startswith("Arr["):
                ln = srt.accessor(0, 0)(c)
                bounds.append(z3.And(ln >= 0, ln <= 5))
                data = srt.accessor(0, 1)(c)
                if data.sort().range() == z3.IntSort():
                    for i in range(5):
                        bounds.append(z3.And(z3.Select(data, i) >= -100, z3.Select(data, i) <= 100))
        if not bounds:
            return None
        s.push()
        s.add(*bounds)
        try:
            if s.check() == z3.sat:
                return s.model()
        finally:
            s.pop()
        return None

    def check_valid(self, pc, phi):
        s = z3.Solver()
        s.set("rlimit", self.rlimit)
        for ax in self.axioms_for(frozenset()):
            s.add(ax)
        for c in pc:
            s.add(c)
        s.add(z3.Not(phi))
        return s.check() == z3.unsat


def _patstr(p):
    from .pp import show_pat
    return show_pat(p)


def _all_refs(rt: RT):
    out = list(rt.refs)
    for a in rt.args:
        out += _all_refs(a)
    return out


def _ref_span(rt: RT):
    rs = _all_refs(rt)
    return rs[0].span if rs else None
