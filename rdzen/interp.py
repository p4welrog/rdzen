# SPDX-License-Identifier: MIT OR Apache-2.0
"""Interpreter jądra z sprawdzeniami czasu wykonania (rozdz. 7).

Służy do: obliczania bloków `examples`, testów właściwości `forall`
i odtwarzania kontrprzykładów (§6.6). Klucze naruszeń są zgodne
z kluczami zobowiązań generatora warunków (vcgen)."""
from __future__ import annotations
import copy
from .ast import *
from .check import RT, subst_rt

INT_MIN, INT_MAX = -2**63, 2**63 - 1


class Ctor:
    __slots__ = ("name", "fields")

    def __init__(self, name, fields):
        self.name, self.fields = name, tuple(fields)

    def __eq__(self, o):
        return isinstance(o, Ctor) and o.name == self.name and o.fields == self.fields

    def __hash__(self):
        return hash((self.name, self.fields))

    def __repr__(self):
        return fmt(self)


class UnitV:
    def __repr__(self):
        return "()"

    def __eq__(self, o):
        return isinstance(o, UnitV)

    def __hash__(self):
        return 0


UNITV = UnitV()


def fmt(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(fmt(x) for x in v) + "]"
    if isinstance(v, Ctor):
        return v.name + ("(" + ", ".join(fmt(x) for x in v.fields) + ")" if v.fields else "")
    if isinstance(v, UnitV):
        return "()"
    return str(v)


class Violation(Exception):
    def __init__(self, kind, key, span, detail=""):
        super().__init__(detail)
        self.kind, self.key, self.span, self.detail = kind, key, span, detail


class BudgetExceeded(Exception):
    pass


class HoleHit(Exception):
    def __init__(self, name):
        self.name = name


class ReturnEx(Exception):
    def __init__(self, v, site):
        self.v, self.site = v, site


class BreakEx(Exception):
    pass


class ContinueEx(Exception):
    pass


def _ref_span(rt: RT):
    def all_refs(t):
        out = list(t.refs)
        for a in t.args:
            out += all_refs(a)
        return out
    rs = all_refs(rt)
    return rs[0].span if rs else None


def tdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


class Frame:
    def __init__(self, decl, t0, old):
        self.decl, self.t0, self.old = decl, t0, old


class Interp:
    def __init__(self, checker, budget=2_000_000):
        self.ch = checker
        self.budget = budget
        self.steps = 0
        self.frames = []
        self.trace = []

    def tick(self):
        self.steps += 1
        if self.steps > self.budget:
            raise BudgetExceeded()

    # ---------- formuły ----------
    def formula(self, e, env, root, site, result=None, old=None, selfv=None):
        """Wartościowanie formuły (liczby całkowite matematyczne). Naruszenie wd → Violation('wd')."""
        F = lambda x, en=env: self.formula(x, en, root, site, result, old, selfv)
        self.tick()
        if isinstance(e, IntLit):
            return e.value
        if isinstance(e, BoolLit):
            return e.value
        if isinstance(e, UnitLit):
            return UNITV
        if isinstance(e, Name):
            if e.name in env:
                return env[e.name]
            return self.ch.consts[e.name].value
        if isinstance(e, SelfRef):
            return selfv
        if isinstance(e, ResultRef):
            return result
        if isinstance(e, Old):
            return (old or {}).get(e.name, env.get(e.name))
        if isinstance(e, Unary):
            v = F(e.expr)
            return -v if e.op == "-" else (not v)
        if isinstance(e, Binary):
            op = e.op
            if op == "&&":
                return F(e.left) and F(e.right)
            if op == "||":
                return F(e.left) or F(e.right)
            a, b = F(e.left), F(e.right)
            if op in ("/", "%"):
                if b == 0:
                    raise Violation("wd", ("wd", root.span, site), e.span, "dzielenie przez zero w formule")
                q = tdiv(a, b)
                return q if op == "/" else a - b * q
            return _binop(op, a, b)
        if isinstance(e, Index):
            a, i = F(e.expr), F(e.index)
            if not (0 <= i < len(a)):
                raise Violation("wd", ("wd", root.span, site), e.span, "indeks poza zakresem w formule")
            return a[i]
        if isinstance(e, Field):
            a = F(e.expr)
            if e.name == "len" and isinstance(a, list):
                return len(a)
            return self.field(e.expr.ty, e.name, a)
        if isinstance(e, Quant):
            lo, hi = F(e.lo), F(e.hi)
            if hi - lo > 1_000_000:
                raise BudgetExceeded()
            env2 = dict(env)
            for k in range(lo, hi):
                env2[e.var] = k
                v = F(e.body, env2)
                if e.kind == "forall" and not v:
                    return False
                if e.kind == "exists" and v:
                    return True
            return e.kind == "forall"
        if isinstance(e, Call):
            args = [F(a.expr) for a in e.args]
            if e.name in self.ch.specs:
                sf = self.ch.specs[e.name]
                penv = {p[0]: v for p, v in zip(sf.rparams, args)}
                return self.formula(sf.body, penv, root, site)
            if e.callee is not None and not e.callee.builtin:
                return self.call_fn(e.callee, args, e.span, targs=e.targs or {})[0]
            return self.builtin_pure(e.name, args)
        if isinstance(e, CtorCall):
            return Ctor(e.name, [F(a) for a in e.args])
        if isinstance(e, Match):
            v = F(e.expr)
            for arm in e.arms:
                b = self.pmatch(arm.pattern, v)
                if b is None:
                    continue
                env2 = dict(env)
                env2.update(b)
                if arm.guard is not None and not F(arm.guard, env2):
                    continue
                return F(arm.body, env2)
            raise Violation("unreach", ("unreach", e.span), e.span)
        if isinstance(e, If):
            c = F(e.cond)
            if c:
                return F(e.then.stmts[0].expr)
            els = e.els
            return F(els.stmts[0].expr if isinstance(els, Block) else els)
        raise NotImplementedError(type(e).__name__)

    def field(self, rt, name, v):
        d = self.ch.data[rt.name]
        cname, fields = d.rctors[0]
        for j, (fn, _) in enumerate(fields):
            if fn == name:
                return v.fields[j]
        raise KeyError(name)

    def pmatch(self, p, v):
        if p.kind == "wild":
            return {}
        if p.kind == "var":
            return {p.name: v}
        if p.kind in ("int", "bool"):
            return {} if v == p.value and type(v) == type(p.value) else None
        if not isinstance(v, Ctor) or v.name != p.name:
            return None
        out = {}
        for sp_, fv in zip(p.args, v.fields):
            b = self.pmatch(sp_, fv)
            if b is None:
                return None
            out.update(b)
        return out

    def check_type(self, v, rt: RT, env, depth=0) -> bool:
        """h(v, τ) dla uściśleń (bez zakresów, które gwarantuje semantyka)."""
        for r in rt.refs:
            if not self.formula(r, env, r, None, selfv=v):
                return False
        if rt.kind == "Array" and depth < 3:
            return all(self.check_type(x, rt.args[0], env, depth + 1) for x in v)
        if rt.kind == "Data" and depth < 3 and isinstance(v, Ctor):
            d = self.ch.data[rt.name]
            s = dict(zip(d.tparams, rt.args))
            fields = dict(d.rctors)[v.name]
            for (fn, ft), fv in zip(fields, v.fields):
                ft2 = subst_rt(ft, s)
                if ft2.bare().shape() == rt.bare().shape():
                    continue
                if not self.check_type(fv, ft2, env, depth + 1):
                    return False
        return True

    def builtin_pure(self, n, args):
        if n == "compare":
            a, b = args
            return Ctor("Less" if a < b else "Equal" if a == b else "Greater", [])
        if n == "min":
            return min(args)
        if n == "max":
            return max(args)
        if n == "contains":
            return args[1] in args[0]
        if n == "filled":
            if args[0] > 100_000:
                raise BudgetExceeded()
            return [copy.deepcopy(args[1]) for _ in range(args[0])]
        if n in ("checked_add", "checked_sub", "checked_mul"):
            a, b = args
            r = a + b if n == "checked_add" else a - b if n == "checked_sub" else a * b
            return Ctor("Some", [r]) if INT_MIN <= r <= INT_MAX else Ctor("None", [])
        raise NotImplementedError(n)

    # ---------- kod ----------
    def ev(self, e, env):
        self.tick()
        if isinstance(e, (IntLit, BoolLit)):
            return e.value
        if isinstance(e, UnitLit):
            return UNITV
        if isinstance(e, Name):
            if e.name in env:
                return env[e.name]
            return self.ch.consts[e.name].value
        if isinstance(e, Hole):
            raise HoleHit(e.name)
        if isinstance(e, Unary):
            v = self.ev(e.expr, env)
            if e.op == "!":
                return not v
            return self.ovf(-v, e)
        if isinstance(e, Binary):
            op = e.op
            if op == "&&":
                return self.ev(e.left, env) and self.ev(e.right, env)
            if op == "||":
                return self.ev(e.left, env) or self.ev(e.right, env)
            a = self.ev(e.left, env)
            b = self.ev(e.right, env)
            if op in ("+", "-", "*"):
                return self.ovf(_binop(op, a, b), e)
            if op in ("/", "%"):
                if b == 0 or (a == INT_MIN and b == -1):
                    raise Violation("div0", ("div0", e.span), e.span, f"{a} {op} {b}")
                q = tdiv(a, b)
                return q if op == "/" else a - b * q
            return _binop(op, a, b)
        if isinstance(e, Index):
            a = self.ev(e.expr, env)
            i = self.ev(e.index, env)
            if not (0 <= i < len(a)):
                raise Violation("bounds", ("bounds", e.span), e.span, f"indeks {i}, długość {len(a)}")
            return a[i]
        if isinstance(e, Field):
            a = self.ev(e.expr, env)
            if e.name == "len" and isinstance(a, list):
                return len(a)
            return self.field(e.expr.ty, e.name, a)
        if isinstance(e, ArrayLit):
            return [copy.deepcopy(self.ev(x, env)) for x in e.items]
        if isinstance(e, CtorCall):
            return Ctor(e.name, [copy.deepcopy(self.ev(x, env)) for x in e.args])
        if isinstance(e, Call):
            return self.call(e, env)
        if isinstance(e, If):
            if self.ev(e.cond, env):
                return self.block(e.then, env)
            if e.els is None:
                return UNITV
            if isinstance(e.els, If):
                return self.ev(e.els, env)
            return self.block(e.els, env)
        if isinstance(e, Match):
            v = self.ev(e.expr, env)
            for arm in e.arms:
                b = self.pmatch(arm.pattern, v)
                if b is None:
                    continue
                keys = set(env)
                env.update(b)
                try:
                    if arm.guard is not None and not self.ev(arm.guard, env):
                        continue
                    return self.ev(arm.body, env)
                finally:
                    for k in list(env):
                        if k not in keys:
                            del env[k]
            raise Violation("unreach", ("unreach", e.span), e.span)
        if isinstance(e, BlockExpr):
            return self.block(e.block, env)
        raise NotImplementedError(type(e).__name__)

    def ovf(self, v, e):
        if not (INT_MIN <= v <= INT_MAX):
            raise Violation("overflow", ("overflow", e.span), e.span, f"wynik {v}")
        return v

    def call(self, e, env):
        if e.name in self.ch.specs:
            sf = self.ch.specs[e.name]
            args = [self.ev(a.expr, env) for a in e.args]
            penv = {p[0]: v for p, v in zip(sf.rparams, args)}
            return self.formula(sf.body, penv, e, e.span)
        sig = e.callee
        vals = []
        for a in e.args:
            vals.append(env[a.inout] if a.inout else copy.deepcopy(self.ev(a.expr, env)))
        if sig.builtin:
            n = e.name
            if n == "push":
                if len(vals[0]) >= INT_MAX:
                    raise Violation("pre", ("pre", e.span, e.span), e.span)
                env[e.args[0].inout].append(vals[1])
                return UNITV
            if n == "pop":
                a = env[e.args[0].inout]
                return Ctor("Some", [a.pop()]) if a else Ctor("None", [])
            if n == "filled" and vals[0] < 0:
                raise Violation("pre", ("pre", e.span, e.span), e.span)
            return self.builtin_pure(n, vals)
        res, outs = self.call_fn(sig, vals, e.span, targs=e.targs or {})
        k = 0
        for (pn, pt, pinout), a in zip(sig.params, e.args):
            if pinout:
                env[a.inout] = outs[k]
                k += 1
        return res

    def call_fn(self, sig, vals, call_span, targs=None, check_pre=True):
        decl = sig.decl
        penv = {pn: v for (pn, pt, pinout), v in zip(sig.params, vals)}
        if check_pre:
            for (pn, pt, pinout), v in zip(sig.params, vals):
                if not self.check_type(v, pt, penv):
                    raise Violation("pre", ("pre", _ref_span(pt), call_span), call_span, f"argument `{pn}` = {fmt(v)}")
            for q in decl.requires:
                if not self.formula(q, penv, q, call_span):
                    raise Violation("pre", ("pre", q.span, call_span), call_span)
            if self.frames:
                fr = self.frames[-1]
                scc = self.ch.scc.get(fr.decl.name, frozenset())
                if fr.t0 is not None and decl.name in scc:
                    t = self.formula(decl.decreases, penv, decl.decreases, call_span)
                    if not (0 <= t < fr.t0):
                        raise Violation("term", ("term", call_span), call_span, f"miara {t}, przy wejściu {fr.t0}")
        old = {k: copy.deepcopy(v) for k, v in penv.items()}
        t0 = None
        if decl.decreases is not None and not decl.partial:
            t0 = self.formula(decl.decreases, penv, decl.decreases, decl.span)
        self.frames.append(Frame(decl, t0, old))
        if len(self.frames) > 2000:
            raise BudgetExceeded()
        env = dict(penv)
        last = decl.body.stmts[-1] if decl.body.stmts else None
        site = last.span if isinstance(last, ExprStmt) else decl.body.span
        try:
            v = self.block(decl.body, env)
        except ReturnEx as r:
            v, site = r.v, r.site
        finally:
            self.frames.pop()
        if decl.ret is None:
            v = UNITV
        # postkondycje
        if decl.ret is not None and not self.check_type(v, sig.ret, env):
            raise Violation("post", ("post", decl.ret.span, site), site, f"wynik {fmt(v)}")
        for q in decl.ensures:
            if not self.formula(q, env, q, site, result=v, old=old):
                raise Violation("post", ("post", q.span, site), site, f"wynik {fmt(v)}")
        outs = []
        for (pn, pt, pinout), p in zip(sig.params, decl.params):
            if pinout:
                if not self.check_type(env[pn], pt, env):
                    raise Violation("post", ("post", p.type.span, site), site)
                outs.append(env[pn])
        return v, outs

    def block(self, b: Block, env):
        keys = set(env)
        v = UNITV
        try:
            for k, s in enumerate(b.stmts):
                last = k == len(b.stmts) - 1
                if isinstance(s, ExprStmt):
                    r = self.ev(s.expr, env)
                    v = r if last else UNITV
                else:
                    self.stmt(s, env)
                    v = UNITV
        finally:
            for k in list(env):
                if k not in keys:
                    del env[k]
        return v

    def stmt(self, s, env):
        self.tick()
        if isinstance(s, Let):
            v = copy.deepcopy(self.ev(s.expr, env))
            if s.type is not None and not self.check_type(v, s.rt, env):
                raise Violation("refine", ("refine", _ref_span(s.rt), s.span), s.span, f"{s.name} = {fmt(v)}")
            env[s.name] = v
            return
        if isinstance(s, Assign):
            v = copy.deepcopy(self.ev(s.expr, env))
            if not self.check_type(v, s.target_rt, env):
                raise Violation("refine", ("refine", _ref_span(s.target_rt), s.span), s.span, f"{s.name} = {fmt(v)}")
            env[s.name] = v
            return
        if isinstance(s, IndexAssign):
            i = self.ev(s.index, env)
            v = copy.deepcopy(self.ev(s.expr, env))
            a = env[s.name]
            if not (0 <= i < len(a)):
                raise Violation("bounds", ("bounds", s.span), s.span, f"indeks {i}, długość {len(a)}")
            if not self.check_type(v, s.target_rt.args[0], env):
                raise Violation("refine", ("refine", _ref_span(s.target_rt.args[0]), s.span), s.span)
            a[i] = v
            return
        if isinstance(s, While):
            old = self.frames[-1].old if self.frames else {}
            for inv in s.invariants:
                if not self.formula(inv, env, inv, s.span, old=old):
                    raise Violation("inv-init", ("inv-init", inv.span, s.span), inv.span)
            while True:
                self.tick()
                if not self.ev(s.cond, env):
                    break
                t0 = None
                if s.decreases is not None:
                    t0 = self.formula(s.decreases, env, s.decreases, s.span)
                    if t0 < 0:
                        raise Violation("var-nn", ("var-nn", s.decreases.span, s.span), s.decreases.span, f"wariant = {t0}")
                try:
                    self.block(s.body, env)
                except ContinueEx:
                    pass
                except BreakEx:
                    break
                for inv in s.invariants:
                    if not self.formula(inv, env, inv, s.span, old=old):
                        raise Violation("inv-pres", ("inv-pres", inv.span, s.span), inv.span)
                if t0 is not None:
                    t = self.formula(s.decreases, env, s.decreases, s.span)
                    if not t < t0:
                        raise Violation("var-dec", ("var-dec", s.decreases.span, s.span), s.decreases.span, f"{t0} → {t}")
            return
        if isinstance(s, For):
            old = self.frames[-1].old if self.frames else {}
            a0 = copy.deepcopy(self.ev(s.iterable, env))
            had_it = "it" in env
            env["it"] = 0
            try:
                for inv in s.invariants:
                    if not self.formula(inv, env, inv, s.span, old=old):
                        raise Violation("inv-init", ("inv-init", inv.span, s.span), inv.span)
                while env["it"] < len(a0):
                    self.tick()
                    env[s.var] = copy.deepcopy(a0[env["it"]])
                    try:
                        self.block(s.body, env)
                    except ContinueEx:
                        pass
                    except BreakEx:
                        break
                    finally:
                        env.pop(s.var, None)
                    env["it"] += 1
                    for inv in s.invariants:
                        if not self.formula(inv, env, inv, s.span, old=old):
                            raise Violation("inv-pres", ("inv-pres", inv.span, s.span), inv.span)
            finally:
                if not had_it:
                    env.pop("it", None)
            return
        if isinstance(s, Return):
            v = self.ev(s.expr, env) if s.expr is not None else UNITV
            raise ReturnEx(v, s.span)
        if isinstance(s, Break):
            raise BreakEx()
        if isinstance(s, Continue):
            raise ContinueEx()
        if isinstance(s, Assert):
            old = self.frames[-1].old if self.frames else {}
            if not self.formula(s.formula, env, s.formula, s.span, old=old):
                raise Violation("assert", ("assert", s.span), s.span)
            return
        raise NotImplementedError(type(s).__name__)


def _binop(op, a, b):
    if op == "+": return a + b
    if op == "-": return a - b
    if op == "*": return a * b
    if op == "<": return a < b
    if op == "<=": return a <= b
    if op == ">": return a > b
    if op == ">=": return a >= b
    if op == "==": return a == b and type(a) == type(b) if isinstance(a, bool) or isinstance(b, bool) else a == b
    if op == "!=": return not _binop("==", a, b)
    raise ValueError(op)
