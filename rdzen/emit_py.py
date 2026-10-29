# SPDX-License-Identifier: MIT OR Apache-2.0
"""Backend: generowanie modułu Pythona z programu Rdzenia (zamiast C z §1.1).

Zasada (przekształcenie R, §6.6): sprawdzenie czasu wykonania jest emitowane
wyłącznie dla zobowiązań bez dowodu (`unknown`, `refuted-inductive`).
Semantyka wartości: tablice są kopiowane przy wiązaniu i przy odczycie zmiennej
mutowalnej jako całości; parametry `inout` są zwracane w krotce i ponownie wiązane."""
from __future__ import annotations
import keyword
from .ast import *
from .check import has_array, RT
from .vcgen import writes_of

RESERVED = set(keyword.kwlist) | {"len", "range", "all", "any", "isinstance", "print", "int",
                                  "list", "bool", "object", "type", "copy", "min", "max", "self"}

RUNTIME = r'''
# ---- środowisko wykonawcze Rdzenia ----
# Ten fragment jest objęty licencją 0BSD (SPDX-License-Identifier: 0BSD) — można go
# używać i rozpowszechniać bez podawania autorstwa; reszta modułu należy do autora programu.
class RdzenTrap(Exception):
    """Pułapka czasu wykonania: naruszenie nieudowodnionego zobowiązania."""
    def __init__(self, kind, loc):
        super().__init__(f"{kind} @ {loc}")
        self.kind, self.loc = kind, loc

_INT_MIN, _INT_MAX = -2**63, 2**63 - 1

def _trap(kind, loc):
    raise RdzenTrap(kind, loc)

def _check(c, kind, loc):
    if not c:
        raise RdzenTrap(kind, loc)

def _ovf(v, loc):
    if v < _INT_MIN or v > _INT_MAX:
        raise RdzenTrap("overflow", loc)
    return v

def _get(a, i, loc):
    if i < 0 or i >= len(a):
        raise RdzenTrap("bounds", loc)
    return a[i]

def _fget(a, i):
    if i < 0 or i >= len(a):
        raise RdzenTrap("wd", "formuła")
    return a[i]

def _tdiv(a, b, loc=None):
    if loc is not None and (b == 0 or (a == _INT_MIN and b == -1)):
        raise RdzenTrap("div0", loc)
    if b == 0:
        raise RdzenTrap("wd", "formuła")
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q

def _trem(a, b, loc=None):
    return a - b * _tdiv(a, b, loc)

def _rank(v):
    base = type(v).__mro__[1]
    return 1 + sum(_rank(getattr(v, f)) for f in v._fields if isinstance(getattr(v, f), base))

def rz_str(s):
    """Napis Pythona → wartość typu Str (bajty UTF-8)."""
    return list(s.encode("utf-8"))

def py_str(b):
    """Wartość typu Str → napis Pythona."""
    return bytes(b).decode("utf-8", errors="replace")

def _cp(v):
    if isinstance(v, list):
        return [_cp(x) for x in v]
    return v

class _Data:
    __slots__ = ()
    _fields = ()
    def __eq__(self, o):
        return type(self) is type(o) and all(getattr(self, f) == getattr(o, f) for f in self._fields)
    def __hash__(self):
        return hash((type(self).__name__,) + tuple(getattr(self, f) for f in self._fields))
    def __repr__(self):
        n = type(self).__name__.rstrip("_")
        if not self._fields:
            return n
        return n + "(" + ", ".join(repr(getattr(self, f)) for f in self._fields) + ")"

def _ctor(name, base, fields):
    def __init__(self, *args):
        for f, a in zip(fields, args):
            object.__setattr__(self, f, a)
    def __setattr__(self, k, v):
        raise AttributeError("wartości Rdzenia są niemutowalne")
    return type(name, (base,), {"__slots__": tuple(fields), "_fields": tuple(fields),
                                "__init__": __init__, "__setattr__": __setattr__})
'''


def esc(n: str) -> str:
    if n.startswith("_"):
        n = "u" + n
    if n in RESERVED:
        n = n + "_"
    return n


def esc_ctor(n: str) -> str:
    return n + "_" if n in ("None", "True", "False") else n


class Unsupported(Exception):
    pass


def needs_stmts(e) -> bool:
    for n in walk(e):
        if isinstance(n, (If, Match, BlockExpr, Hole, Try)):
            return True
        if isinstance(n, Call) and any(a.inout for a in n.args):
            return True
    return False


class Emitter:
    def __init__(self, checker, unproved, file):
        self.ch = checker
        self.unproved = unproved
        self.file = file
        self.out = []
        self.ind = 0
        self.tmp = 0
        self.fn = None
        self.scopes = []
        self.loops = []
        self.user_inout = {f.name: [p for p in f.sig.params if p[2]] for f in checker.user_fns}

    # ---------- narzędzia ----------
    def w(self, line):
        self.out.append("    " * self.ind + line)

    def fresh(self, base="t"):
        self.tmp += 1
        return f"_{base}{self.tmp}"

    def loc(self, span):
        return repr(f"{self.file}:{span.line}:{span.col}")

    def need(self, key) -> bool:
        return (self.fn.name, key) in self.unproved

    def lookup(self, name):
        for sc in reversed(self.scopes):
            if name in sc:
                return sc[name]
        raise KeyError(name)

    def bind(self, name, mutable=False, rt=None):
        used = {v[0] for sc in self.scopes for v in sc.values()} | self.fn_names
        py = esc(name)
        k = 1
        while py in used:
            k += 1
            py = f"{esc(name)}_{k}"
        self.scopes[-1][name] = (py, mutable, rt)
        self.fn_names.add(py)
        return py

    def push_scope(self):
        self.scopes.append({})

    def pop_scope(self):
        self.scopes.pop()

    # ---------- formuły ----------
    def f(self, e, env, result=None, selfv=None):
        """Formuła → wyrażenie Pythona. env: nazwa Rdzenia → wyrażenie Pythona."""
        F = lambda x, en=None: self.f(x, en if en is not None else env, result, selfv)
        if isinstance(e, IntLit):
            return str(e.value)
        if isinstance(e, BoolLit):
            return "True" if e.value else "False"
        if isinstance(e, UnitLit):
            return "None"
        if isinstance(e, Name):
            if e.name in env:
                return env[e.name]
            return str(self.ch.consts[e.name].value)
        if isinstance(e, SelfRef):
            return selfv
        if isinstance(e, ResultRef):
            return result
        if isinstance(e, Old):
            return env.get(("old", e.name), env.get(e.name))
        if isinstance(e, Unary):
            return f"(-{F(e.expr)})" if e.op == "-" else f"(not {F(e.expr)})"
        if isinstance(e, Binary):
            a, b = F(e.left), F(e.right)
            op = e.op
            if op == "&&": return f"({a} and {b})"
            if op == "||": return f"({a} or {b})"
            if op == "/": return f"_tdiv({a}, {b})"
            if op == "%": return f"_trem({a}, {b})"
            return f"({a} {op} {b})"
        if isinstance(e, Index):
            return f"_fget({F(e.expr)}, {F(e.index)})"
        if isinstance(e, Field):
            if e.name == "len" and e.expr.ty.kind == "Array":
                return f"len({F(e.expr)})"
            return f"{F(e.expr)}.{esc(e.name)}"
        if isinstance(e, Quant):
            v = self.fresh("q")
            env2 = dict(env)
            env2[e.var] = v
            fn = "all" if e.kind == "forall" else "any"
            return f"{fn}({F(e.body, env2)} for {v} in range({F(e.lo)}, {F(e.hi)}))"
        if isinstance(e, Call):
            args = ", ".join(F(a.expr) for a in e.args)
            if e.name in self.ch.specs:
                return f"_spec_{e.name}({args})"
            return self.builtin(e.name, [F(a.expr) for a in e.args])
        if isinstance(e, CtorCall):
            return f"{esc_ctor(e.name)}(" + ", ".join(F(a) for a in e.args) + ")"
        if isinstance(e, ArrayLit):
            return "[" + ", ".join(F(a) for a in e.items) + "]"
        if isinstance(e, Match):
            subj = F(e.expr)
            v = self.fresh("m")
            res = "_trap('unreach', 'formuła')"
            for arm in reversed(e.arms):
                conds, binds = self.pat(arm.pattern, v)
                env2 = dict(env)
                env2.update(binds)
                c = " and ".join(conds) or "True"
                if arm.guard is not None:
                    c = f"({c}) and ({F(arm.guard, env2)})"
                res = f"({F(arm.body, env2)} if {c} else {res})"
            return f"(lambda {v}: {res})({subj})"
        if isinstance(e, If):
            th = F(e.then.stmts[0].expr)
            els = e.els.stmts[0].expr if isinstance(e.els, Block) else e.els
            return f"({th} if {F(e.cond)} else {F(els)})"
        raise Unsupported(f"formuła {type(e).__name__}")

    def m(self, e, env):
        """Miara jako liczba: typ danych → ranga strukturalna."""
        v = self.f(e, env)
        return f"_rank({v})" if e.ty is not None and e.ty.kind == "Data" else v

    def builtin(self, n, a):
        if n == "is_digit":
            return f"(48 <= {a[0]} <= 57)"
        if n == "is_lower":
            return f"(97 <= {a[0]} <= 122)"
        if n == "is_upper":
            return f"(65 <= {a[0]} <= 90)"
        if n == "is_alpha":
            return f"(65 <= {a[0]} <= 90 or 97 <= {a[0]} <= 122)"
        if n == "is_space":
            return f"({a[0]} in (32, 9, 10, 13))"
        if n == "concat":
            return f"({a[0]} + {a[1]})"
        if n == "slice":
            return f"{a[0]}[{a[1]}:{a[2]}]"
        if n == "compare":
            return f"_compare({a[0]}, {a[1]})"
        if n == "min":
            return f"min({a[0]}, {a[1]})"
        if n == "max":
            return f"max({a[0]}, {a[1]})"
        if n == "contains":
            return f"({a[1]} in {a[0]})"
        if n == "filled":
            return f"[_cp({a[1]}) for _ in range({a[0]})]"
        if n in ("checked_add", "checked_sub", "checked_mul"):
            op = {"checked_add": "+", "checked_sub": "-", "checked_mul": "*"}[n]
            return f"_checked({a[0]} {op} {a[1]})"
        raise Unsupported(n)

    def pat(self, p, subj):
        """Wzorzec → (lista warunków, wiązania nazwa → wyrażenie)."""
        if p.kind == "wild":
            return [], {}
        if p.kind == "var":
            return [], {p.name: subj}
        if p.kind == "int":
            return [f"{subj} == {p.value}"], {}
        if p.kind == "bool":
            return [f"{subj} is {p.value}"], {}
        conds = [f"isinstance({subj}, {esc_ctor(p.name)})"]
        binds = {}
        fields = dict(p.data.rctors)[p.name]
        for (fn, _), sp_ in zip(fields, p.args):
            c, b = self.pat(sp_, f"{subj}.{esc(fn)}")
            conds += c
            binds.update(b)
        return conds, binds

    def fenv(self):
        env = {}
        for sc in self.scopes:
            for k, (py, mut, rt) in sc.items():
                env[k] = py
        for k, v in self.olds.items():
            env[("old", k)] = v
        return env

    def refine_checks(self, rt: RT, value_py, kind, key, span):
        if rt is None or not self.need(key):
            return
        env = self.fenv()
        for r in _all_refs_top(rt):
            self.w(f"_check({self.f(r, env, selfv=value_py)}, {kind!r}, {self.loc(span)})")
        if rt.kind == "Array" and _all_refs(rt.args[0]):
            el = self.fresh("e")
            conds = " and ".join(self.f(r, env, selfv=el) for r in _all_refs(rt.args[0]))
            self.w(f"_check(all({conds} for {el} in {value_py}), {kind!r}, {self.loc(span)})")

    # ---------- wyrażenia kodu ----------
    def is_mut_name(self, e):
        if isinstance(e, Name):
            try:
                py, mut, rt = self.lookup(e.name)
            except KeyError:
                return False
            return mut
        return False

    def val(self, e, bind=False):
        """Wyrażenie kodu → wyrażenie Pythona (może emitować instrukcje pomocnicze)."""
        s = self._val(e)
        if bind and e.ty is not None and has_array(e.ty, self.ch.data) and not isinstance(e, (ArrayLit, CtorCall, Call)):
            if not (isinstance(e, Name) and self.is_mut_name(e)):
                s = f"_cp({s})"
        return s

    def seq(self, exprs, bind=False):
        needs = [needs_stmts(x) for x in exprs]
        out = []
        for i, x in enumerate(exprs):
            v = self.val(x, bind)
            if any(needs[i + 1:]) and not _atomic(v):
                t = self.fresh()
                self.w(f"{t} = {v}")
                v = t
            out.append(v)
        return out

    def _val(self, e):
        if isinstance(e, IntLit):
            return str(e.value)
        if isinstance(e, BoolLit):
            return "True" if e.value else "False"
        if isinstance(e, UnitLit):
            return "None"
        if isinstance(e, Name):
            try:
                py, mut, rt = self.lookup(e.name)
            except KeyError:
                return str(self.ch.consts[e.name].value)
            if mut and e.ty is not None and has_array(e.ty, self.ch.data):
                return f"_cp({py})"
            return py
        if isinstance(e, Hole):
            raise Unsupported("program zawiera dziurę")
        if isinstance(e, Unary):
            a = self.val(e.expr)
            if e.op == "!":
                return f"(not {a})"
            if self.need(("overflow", e.span)):
                return f"_ovf(-{a}, {self.loc(e.span)})"
            return f"(-{a})"
        if isinstance(e, Binary):
            op = e.op
            if op in ("&&", "||"):
                if not needs_stmts(e.right):
                    a, b = self.val(e.left), self.val(e.right)
                    return f"({a} {'and' if op == '&&' else 'or'} {b})"
                t = self.fresh()
                self.w(f"{t} = {self.val(e.left)}")
                self.w(f"if {'' if op == '&&' else 'not '}{t}:")
                self.ind += 1
                self.w(f"{t} = {self.val(e.right)}")
                self.ind -= 1
                return t
            a, b = self.seq([e.left, e.right])
            if op in ("+", "-", "*"):
                if self.need(("overflow", e.span)):
                    return f"_ovf({a} {op} {b}, {self.loc(e.span)})"
                return f"({a} {op} {b})"
            if op in ("/", "%"):
                fn = "_tdiv" if op == "/" else "_trem"
                if self.need(("div0", e.span)):
                    return f"{fn}({a}, {b}, {self.loc(e.span)})"
                return f"{fn}({a}, {b})"
            return f"({a} {op} {b})"
        if isinstance(e, Index):
            a, i = self.seq([e.expr, e.index]) if not self.is_mut_name(e.expr) else (self.lookup(e.expr.name)[0], self.val(e.index))
            if self.need(("bounds", e.span)):
                return f"_get({a}, {i}, {self.loc(e.span)})"
            return f"{a}[{i}]"
        if isinstance(e, Field):
            a = self.lookup(e.expr.name)[0] if self.is_mut_name(e.expr) else self.val(e.expr)
            if e.name == "len" and e.expr.ty.kind == "Array":
                return f"len({a})"
            return f"{a}.{esc(e.name)}"
        if isinstance(e, ArrayLit):
            return "[" + ", ".join(self.seq(e.items)) + "]"
        if isinstance(e, CtorCall):
            args = self.seq(e.args)
            if not self.need(("data-inv", e.span)):
                return f"{esc_ctor(e.name)}(" + ", ".join(args) + ")"
            d = self.ch.data[e.ty.name]
            fields = dict(d.rctors)[e.name]
            names = []
            for a in args:
                if _atomic(a):
                    names.append(a)
                else:
                    t = self.fresh()
                    self.w(f"{t} = {a}")
                    names.append(t)
            v = self.fresh("c")
            self.w(f"{v} = {esc_ctor(e.name)}(" + ", ".join(names) + ")")
            conds = []
            for (fn_, ft), a in zip(fields, names):
                conds += [self.f(r, {}, selfv=a) for r in ft.refs]
            if d.where is not None:
                conds.append(self.f(d.where, {}, selfv=v))
            self.w(f"_check({' and '.join(conds) or 'True'}, 'data-inv', {self.loc(e.span)})")
            return v
        if isinstance(e, Try):
            return self._val(e.desugared)
        if isinstance(e, Call):
            return self.call(e)
        if isinstance(e, (If, Match, BlockExpr)):
            t = self.fresh()
            self.valued(e, ("assign", t))
            return t
        raise Unsupported(type(e).__name__)

    def call(self, e):
        sig = e.callee
        if getattr(getattr(sig, "decl", None), "lemma", False):
            return "None"          # lematy są wymazywane (całkowite, bez efektów)
        if e.name in self.ch.specs:
            return f"_spec_{e.name}(" + ", ".join(self.seq([a.expr for a in e.args])) + ")"
        vals = self.seq([a.expr for a in e.args if a.inout is None])
        if sig.builtin:
            if e.name == "push":
                tgt = self.lookup(e.args[0].inout)[0]
                if self.need(("pre", e.span, e.span)):
                    self.w(f"_check(len({tgt}) < _INT_MAX, 'pre', {self.loc(e.span)})")
                self.w(f"{tgt}.append({vals[0]})")
                return "None"
            if e.name == "pop":
                tgt = self.lookup(e.args[0].inout)[0]
                t = self.fresh()
                self.w(f"{t} = Some({tgt}.pop()) if {tgt} else None_()")
                return t
            if e.name == "filled" and self.need(("pre", e.span, e.span)):
                self.w(f"_check({vals[0]} >= 0, 'pre', {self.loc(e.span)})")
            if e.name == "slice" and self.need(("pre", e.span, e.span)):
                ts = []
                for v in vals:
                    if not _atomic(v):
                        t = self.fresh()
                        self.w(f"{t} = {v}")
                        v = t
                    ts.append(v)
                vals = ts
                self.w(f"_check(0 <= {vals[1]} <= {vals[2]} <= len({vals[0]}), 'pre', {self.loc(e.span)})")
            return self.builtin(e.name, vals)
        # argumenty do zmiennych, jeśli potrzebne są sprawdzenia warunków wstępnych
        decl = sig.decl
        it = iter(vals)
        args, penv = [], {}
        need_pre = any(self.need(("pre", q.span, e.span)) for q in decl.requires) or \
            any(self.need(("pre", _ref_span(pt), e.span)) for _, pt, _ in sig.params if _all_refs(pt)) or \
            self.need(("term", e.span))
        for (pn, pt, pinout), a in zip(sig.params, e.args):
            if pinout:
                v = self.lookup(a.inout)[0]
            else:
                v = next(it)
                if need_pre and not _atomic(v):
                    t = self.fresh()
                    self.w(f"{t} = {v}")
                    v = t
            args.append(v)
            penv[pn] = v
        for (pn, pt, pinout), v in zip(sig.params, args):
            if _all_refs(pt) and self.need(("pre", _ref_span(pt), e.span)):
                for r in _all_refs_top(pt):
                    self.w(f"_check({self.f(r, penv, selfv=v)}, 'pre', {self.loc(e.span)})")
        for q in decl.requires:
            if self.need(("pre", q.span, e.span)):
                self.w(f"_check({self.f(q, penv)}, 'pre', {self.loc(e.span)})")
        if self.need(("term", e.span)):
            self.w(f"_check(0 <= {self.m(decl.decreases, penv)} < _t0, 'term', {self.loc(e.span)})")
        call = f"{esc(e.name)}(" + ", ".join(args) + ")"
        inouts = [a.inout for a in e.args if a.inout]
        if not inouts:
            return call
        t = self.fresh("r")
        tg = ", ".join(self.lookup(n)[0] for n in inouts)
        self.w(f"{t}, {tg} = {call}")
        return t

    # ---------- wyrażenia z wartością docelową ----------
    def valued(self, e, mode):
        """Emituje wyrażenie e tak, że jego wartość trafia do celu `mode`:
        ('assign', nazwa) | ('discard',) | ('return', site)."""
        if isinstance(e, If):
            c = self.val(e.cond)
            self.w(f"if {c}:")
            self.ind += 1
            self.block(e.then, mode)
            self.ind -= 1
            if e.els is not None:
                self.w("else:")
                self.ind += 1
                if isinstance(e.els, If):
                    self.valued(e.els, mode)
                else:
                    self.block(e.els, mode)
                self.ind -= 1
            elif mode[0] != "discard":
                self.w("else:")
                self.ind += 1
                self.sink("None", mode)
                self.ind -= 1
            return
        if isinstance(e, Match):
            subj = self.val(e.expr)
            m = self.fresh("m")
            self.w(f"{m} = {subj}")
            guards = any(a.guard is not None for a in e.arms)
            if not guards:
                for k, arm in enumerate(e.arms):
                    conds, binds = self.pat(arm.pattern, m)
                    c = " and ".join(conds) or "True"
                    self.w(("if " if k == 0 else "elif ") + c + ":")
                    self.ind += 1
                    self.arm(arm, binds, mode)
                    self.ind -= 1
                self.w("else:")
                self.ind += 1
                self.w(f"_trap('unreach', {self.loc(e.span)})")
                self.ind -= 1
                return
            done = self.fresh("done")
            self.w(f"{done} = False")
            for arm in e.arms:
                conds, binds = self.pat(arm.pattern, m)
                c = " and ".join(conds) or "True"
                self.w(f"if not {done} and {c}:")
                self.ind += 1
                self.push_scope()
                env_binds = {}
                for k, v in binds.items():
                    py = self.bind(k)
                    self.w(f"{py} = {v}")
                if arm.guard is not None:
                    if needs_stmts(arm.guard):
                        raise Unsupported("strażnik wymagający instrukcji")
                    self.w(f"if {self.val(arm.guard)}:")
                    self.ind += 1
                self.w(f"{done} = True")
                self.valued_expr(arm.body, mode)
                if arm.guard is not None:
                    self.ind -= 1
                self.pop_scope()
                self.ind -= 1
            self.w(f"if not {done}:")
            self.ind += 1
            self.w(f"_trap('unreach', {self.loc(e.span)})")
            self.ind -= 1
            return
        if isinstance(e, BlockExpr):
            self.block(e.block, mode)
            return
        if isinstance(e, Try):
            self.valued(e.desugared, mode)
            return
        self.sink(self.val(e), mode)

    def valued_expr(self, e, mode):
        if isinstance(e, Try):
            e = e.desugared
        if isinstance(e, (If, Match, BlockExpr)):
            self.valued(e, mode)
        else:
            self.sink(self.val(e), mode)

    def arm(self, arm, binds, mode):
        self.push_scope()
        for k, v in binds.items():
            py = self.bind(k)
            self.w(f"{py} = {v}")
        self.valued_expr(arm.body, mode)
        self.pop_scope()

    def sink(self, v, mode):
        if mode[0] == "assign":
            self.w(f"{mode[1]} = {v}")
        elif mode[0] == "discard":
            if v not in ("None",) and not _atomic(v):
                self.w(v)
        else:
            self.ret(v, mode[1])

    def ret(self, v, site):
        decl, sig = self.fn, self.fn.sig
        r = "__r"
        self.w(f"{r} = {v}")
        env = self.fenv()
        if decl.ret is not None and _all_refs(sig.ret) and self.need(("post", decl.ret.span, site)):
            for q in _all_refs_top(sig.ret):
                self.w(f"_check({self.f(q, env, selfv=r)}, 'post', {self.loc(site)})")
        for q in decl.ensures:
            if self.need(("post", q.span, site)):
                self.w(f"_check({self.f(q, env, result=r)}, 'post', {self.loc(site)})")
        inouts = [p for p in sig.params if p[2]]
        for (pn, pt, _), p in zip(sig.params, decl.params):
            if p.inout and _all_refs(pt) and self.need(("post", p.type.span, site)):
                for q in _all_refs_top(pt):
                    self.w(f"_check({self.f(q, env, selfv=self.lookup(pn)[0])}, 'post', {self.loc(site)})")
        if inouts:
            self.w("return (" + ", ".join([r] + [self.lookup(pn)[0] for pn, _, _ in inouts]) + ",)")
        else:
            self.w(f"return {r}")

    # ---------- bloki i instrukcje ----------
    def block(self, b: Block, mode):
        self.push_scope()
        n = len(b.stmts)
        start = len(self.out)
        for k, s in enumerate(b.stmts):
            last = k == n - 1
            if isinstance(s, ExprStmt):
                if last:
                    self.valued_expr(s.expr, mode)
                    mode = None
                else:
                    self.valued_expr(s.expr, ("discard",))
            else:
                self.stmt(s)
        if mode is not None and mode[0] != "discard":
            terminal = n > 0 and isinstance(b.stmts[-1], (Return, Break, Continue))
            if not terminal:
                self.sink("None", mode)
        if len(self.out) == start:
            self.w("pass")
        self.pop_scope()

    def stmt(self, s):
        if isinstance(s, Let):
            if isinstance(s.expr, (If, Match, BlockExpr)):
                py_tmp = self.fresh()
                self.valued(s.expr, ("assign", py_tmp))
                v = py_tmp
                if s.mutable and has_array(s.rt, self.ch.data):
                    v = f"_cp({v})"
            else:
                v = self.val(s.expr, bind=s.mutable)
            py = self.bind(s.name, s.mutable, s.rt)
            self.w(f"{py} = {v}")
            if s.type is not None:
                self.refine_checks(s.rt, py, "refine", ("refine", _ref_span(s.rt), s.span), s.span)
            return
        if isinstance(s, Assign):
            py, mut, rt = self.lookup(s.name)
            if isinstance(s.expr, (If, Match, BlockExpr)):
                t = self.fresh()
                self.valued(s.expr, ("assign", t))
                v = t
            else:
                v = self.val(s.expr, bind=True)
            if _all_refs(s.target_rt) and self.need(("refine", _ref_span(s.target_rt), s.span)):
                t = self.fresh()
                self.w(f"{t} = {v}")
                self.refine_checks(s.target_rt, t, "refine", ("refine", _ref_span(s.target_rt), s.span), s.span)
                v = t
            self.w(f"{py} = {v}")
            return
        if isinstance(s, IndexAssign):
            py = self.lookup(s.name)[0]
            i, v = self.seq([s.index, s.expr])
            if self.need(("bounds", s.span)):
                self.w(f"_check(0 <= {i} < len({py}), 'bounds', {self.loc(s.span)})")
            el = s.target_rt.args[0]
            if _all_refs(el) and self.need(("refine", _ref_span(el), s.span)):
                t = self.fresh()
                self.w(f"{t} = {v}")
                self.refine_checks(el, t, "refine", ("refine", _ref_span(el), s.span), s.span)
                v = t
            self.w(f"{py}[{i}] = {v}")
            return
        if isinstance(s, While):
            return self.while_(s)
        if isinstance(s, For):
            return self.for_(s)
        if isinstance(s, Return):
            if s.expr is None:
                self.ret("None", s.span)
            else:
                self.valued_expr(s.expr, ("return", s.span))
            return
        if isinstance(s, Break):
            lp = self.loops[-1]
            if lp["oneshot"]:
                self.w(f"{lp['flag']} = True")
            self.w("break")
            return
        if isinstance(s, Continue):
            self.w("break" if self.loops[-1]["oneshot"] else "continue")
            return
        if isinstance(s, Assert):
            if self.need(("assert", s.span)):
                self.w(f"_check({self.f(s.formula, self.fenv())}, 'assert', {self.loc(s.span)})")
            return
        raise Unsupported(type(s).__name__)

    def loop_checks(self, invs, loop_span, kind):
        env = self.fenv()
        for inv in invs:
            if self.need((kind, inv.span, loop_span)):
                self.w(f"_check({self.f(inv, env)}, {kind!r}, {self.loc(inv.span)})")

    def while_(self, s: While):
        self.loop_checks(s.invariants, s.span, "inv-init")
        pres = any(self.need(("inv-pres", inv.span, s.span)) for inv in s.invariants)
        dec = s.decreases is not None and (self.need(("var-dec", s.decreases.span, s.span)) or
                                           self.need(("var-nn", s.decreases.span, s.span)))
        oneshot = pres or dec
        flag = self.fresh("brk") if oneshot else None
        if needs_stmts(s.cond):
            self.w("while True:")
            self.ind += 1
            c = self.val(s.cond)
            self.w(f"if not {c}:")
            self.ind += 1
            self.w("break")
            self.ind -= 1
        else:
            self.w(f"while {self.val(s.cond)}:")
            self.ind += 1
        t0 = self.loop_body(s, oneshot, flag, dec, pres)
        if pres:
            self.loop_checks(s.invariants, s.span, "inv-pres")
        if t0 is not None and self.need(("var-dec", s.decreases.span, s.span)):
            self.w(f"_check({self.m(s.decreases, self.fenv())} < {t0}, 'var-dec', {self.loc(s.decreases.span)})")
        self.ind -= 1

    def loop_body(self, s, oneshot, flag, dec, pres):
        t0 = None
        if dec:
            t0 = self.fresh("v")
            self.w(f"{t0} = {self.m(s.decreases, self.fenv())}")
            if self.need(("var-nn", s.decreases.span, s.span)):
                self.w(f"_check({t0} >= 0, 'var-nn', {self.loc(s.decreases.span)})")
        self.loops.append({"oneshot": oneshot, "flag": flag})
        if oneshot:
            self.w(f"{flag} = False")
            self.w("for _ in (0,):")
            self.ind += 1
            self.block(s.body, ("discard",))
            self.ind -= 1
            self.w(f"if {flag}:")
            self.ind += 1
            self.w("break")
            self.ind -= 1
        else:
            self.block(s.body, ("discard",))
        self.loops.pop()
        return t0

    def for_(self, s: For):
        arr = self.fresh("a")
        self.w(f"{arr} = {self.val(s.iterable)}")
        self.push_scope()
        it = self.bind("it", False, None)
        if any(self.need(("inv-init", inv.span, s.span)) for inv in s.invariants):
            self.w(f"{it} = 0")
        self.loop_checks(s.invariants, s.span, "inv-init")
        pres = any(self.need(("inv-pres", inv.span, s.span)) for inv in s.invariants)
        if not pres:
            self.push_scope()
            x = self.bind(s.var, False, None)
            self.w(f"for {it}, {x} in enumerate({arr}):")
            self.ind += 1
            self.loops.append({"oneshot": False, "flag": None})
            self.block(s.body, ("discard",))
            self.loops.pop()
            self.ind -= 1
            self.pop_scope()
            self.pop_scope()
            return
        flag = self.fresh("brk")
        self.w(f"{it} = 0")
        self.w(f"while {it} < len({arr}):")
        self.ind += 1
        self.push_scope()
        x = self.bind(s.var, False, None)
        self.w(f"{x} = {arr}[{it}]")
        self.loops.append({"oneshot": True, "flag": flag})
        lp = self.loops[-1]
        self.w(f"{lp['flag']} = False")
        self.w("for _ in (0,):")
        self.ind += 1
        self.block(s.body, ("discard",))
        self.ind -= 1
        self.loops.pop()
        self.pop_scope()
        self.w(f"if {lp['flag']}:")
        self.ind += 1
        self.w("break")
        self.ind -= 1
        self.w(f"{it} += 1")
        if pres:
            self.loop_checks(s.invariants, s.span, "inv-pres")
        self.ind -= 1
        self.pop_scope()

    # ---------- deklaracje ----------
    def function(self, f: FnDecl):
        self.fn = f
        self.fn_names = set()
        self.scopes = [{}]
        self.olds = {}
        sig = f.sig
        params = []
        for (pn, pt, pinout) in sig.params:
            params.append(self.bind(pn, pinout, pt))
        self.w(f"def {esc(f.name)}({', '.join(params)}):")
        self.ind += 1
        doc = f"Rdzeń: {f.name} (wiersz {f.span.line})"
        self.w(repr(doc))
        uses_old = any(isinstance(n, Old) for n in walk([f.ensures, f.body]))
        if uses_old:
            for (pn, pt, pinout) in sig.params:
                if pinout:
                    o = f"_old_{self.lookup(pn)[0]}"
                    self.w(f"{o} = _cp({self.lookup(pn)[0]})")
                    self.olds[pn] = o
        if f.decreases is not None and not f.partial and any(k[0] == f.name and k[1][0] == "term" for k in self.unproved):
            self.w(f"_t0 = {self.m(f.decreases, self.fenv())}")
        last = f.body.stmts[-1] if f.body.stmts else None
        site = last.span if isinstance(last, ExprStmt) else f.body.span
        self.block(f.body, ("return", site))
        self.ind -= 1
        self.w("")

    def program(self, items):
        self.w('"""Moduł wygenerowany przez rzc z programu w języku Rdzeń. Nie edytować ręcznie."""')
        self.out.append(RUNTIME)
        for it in self.ch.items:
            if isinstance(it, DataDecl):
                self.w(f"class {it.name}(_Data):")
                self.w("    __slots__ = ()")
                for c in it.ctors:
                    fields = [esc(fn) for fn, _ in c.fields]
                    self.w(f"{esc_ctor(c.name)} = _ctor({esc_ctor(c.name)!r}, {it.name}, {fields!r})")
                self.w("")
        self.w("def _compare(a, b):")
        self.w("    return Less() if a < b else Equal() if a == b else Greater()")
        self.w("")
        self.w("def _checked(r):")
        self.w("    return Some(r) if _INT_MIN <= r <= _INT_MAX else None_()")
        self.w("")
        for it in self.ch.items:
            if isinstance(it, ConstDecl):
                self.w(f"{esc(it.name)} = {it.value}")
        self.w("")
        for sf in self.ch.specs.values():
            params = [esc(p[0]) for p in sf.rparams]
            env = {p[0]: esc(p[0]) for p in sf.rparams}
            self.fn = None
            self.w(f"def _spec_{sf.name}({', '.join(params)}):")
            self.w(f"    return {self.f(sf.body, env)}")
            self.w("")
        for f in self.ch.user_fns:
            if not f.lemma:
                self.function(f)
        return "\n".join(self.out) + "\n"


def _atomic(v: str) -> bool:
    return v.replace("_", "").isalnum() or v in ("None", "True", "False") or (v.startswith("-") and v[1:].isdigit())


def _all_refs(rt):
    out = list(rt.refs)
    for a in rt.args:
        out += _all_refs(a)
    return out


def _all_refs_top(rt):
    return list(rt.refs)


def _ref_span(rt):
    rs = _all_refs(rt)
    return rs[0].span if rs else None


def emit(res, file="program.rz") -> str:
    if res.checker is None:
        raise Unsupported("program nie przeszedł weryfikacji")
    return Emitter(res.checker, res.unproved, file).program(res.checker.items)
