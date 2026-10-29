# SPDX-License-Identifier: MIT OR Apache-2.0
"""Statyczna semantyka prototypu (rozdz. 5): typy kształtu, mutowalność,
wyłączność, wyczerpywalność, totalność. Nadaje węzłom pole `.ty`."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .ast import *
from .diag import Diagnostic, CompileError, err

INT_MIN, INT_MAX = -2**63, 2**63 - 1


# ---------------- typy ----------------
@dataclass
class RT:
    """Typ z uściśleniami: kind ∈ Int, Bool, Unit, Array, Data, Var, Never."""
    kind: str
    name: Optional[str] = None
    args: list = field(default_factory=list)
    refs: list = field(default_factory=list)      # formuły z `self`
    pnames: tuple = ()                            # Fn: nazwy parametrów (uściślenia zależne)

    def shape(self):
        return (self.kind, self.name, tuple(a.shape() for a in self.args))

    def bare(self) -> "RT":
        return RT(self.kind, self.name, [a.bare() for a in self.args], [], self.pnames)

    def __str__(self):
        if self.kind in ("Int", "Bool", "Unit", "Never"):
            s = self.kind
        elif self.kind == "Array":
            s = f"Array<{self.args[0]}>"
        elif self.kind == "Var":
            s = self.name
        elif self.kind == "Fn":
            s = "fn(" + ", ".join(map(str, self.args[:-1])) + f") -> {self.args[-1]}"
        else:
            s = self.name + (f"<{', '.join(map(str, self.args))}>" if self.args else "")
        return s


INT, BOOL, UNIT, NEVER = RT("Int"), RT("Bool"), RT("Unit"), RT("Never")


def same(a: RT, b: RT) -> bool:
    if a.kind == "Never" or b.kind == "Never":
        return True
    return a.shape() == b.shape()


def subst_rt(t: RT, s: dict) -> RT:
    if t.kind == "Var" and t.name in s:
        r = s[t.name]
        return RT(r.kind, r.name, r.args, r.refs + t.refs, r.pnames)
    return RT(t.kind, t.name, [subst_rt(a, s) for a in t.args], t.refs, t.pnames)


def unify(pat: RT, act: RT, s: dict, tvars: set) -> bool:
    if act.kind == "Never":
        return True
    if pat.kind == "Var" and pat.name in tvars:
        if pat.name in s:
            return same(s[pat.name], act)
        s[pat.name] = act.bare()
        return True
    if pat.kind != act.kind or pat.name != act.name or len(pat.args) != len(act.args):
        return False
    return all(unify(p, a, s, tvars) for p, a in zip(pat.args, act.args))


def has_array(t: RT, data, seen=None) -> bool:
    seen = seen or set()
    if t.kind == "Array":
        return True
    if t.kind == "Data":
        key = t.shape()
        if key in seen:
            return False
        seen.add(key)
        d = data[t.name]
        s = dict(zip(d.tparams, t.args))
        return any(has_array(subst_rt(ft, s), data, seen) for c in d.rctors for _, ft in c[1])
    return False


# ---------------- informacje o deklaracjach ----------------
@dataclass
class VarInfo:
    rt: RT
    kind: str          # let | var | param | inout | quant | const | pat


@dataclass
class FnSig:
    name: str
    tparams: list
    params: list       # [(name, RT, inout)]
    ret: RT
    requires: list
    ensures: list
    decreases: object
    partial: bool
    builtin: bool
    pure: bool         # dozwolona w formułach
    decl: object = None


def _param(name, rt, inout=False):
    return (name, rt, inout)


def V(n):
    return RT("Var", n)


def builtin_sigs():
    T = V("T")
    arr = RT("Array", None, [T])
    opt = lambda t: RT("Data", "Option", [t])
    ordering = RT("Data", "Ordering")
    nat = RT("Int", refs=[Binary(">=", SelfRef(), IntLit(0))])
    sigs = [
        FnSig("push", ["T"], [_param("a", arr, True), _param("v", T)], UNIT, [], [], None, False, True, False),
        FnSig("pop", ["T"], [_param("a", arr, True)], opt(T), [], [], None, False, True, False),
        FnSig("compare", [], [_param("a", INT), _param("b", INT)], ordering, [], [], None, False, True, True),
        FnSig("min", [], [_param("a", INT), _param("b", INT)], INT, [], [], None, False, True, True),
        FnSig("max", [], [_param("a", INT), _param("b", INT)], INT, [], [], None, False, True, True),
        FnSig("contains", ["T"], [_param("a", arr), _param("v", T)], BOOL, [], [], None, False, True, True),
        FnSig("filled", ["T"], [_param("n", nat), _param("v", T)], arr, [], [], None, False, True, True),
        FnSig("checked_add", [], [_param("a", INT), _param("b", INT)], opt(INT), [], [], None, False, True, True),
        FnSig("checked_sub", [], [_param("a", INT), _param("b", INT)], opt(INT), [], [], None, False, True, True),
        FnSig("checked_mul", [], [_param("a", INT), _param("b", INT)], opt(INT), [], [], None, False, True, True),
        # napisy (Str = Array<Byte>): klasy znaków ASCII
        FnSig("is_digit", [], [_param("c", INT)], BOOL, [], [], None, False, True, True),
        FnSig("is_alpha", [], [_param("c", INT)], BOOL, [], [], None, False, True, True),
        FnSig("is_lower", [], [_param("c", INT)], BOOL, [], [], None, False, True, True),
        FnSig("is_upper", [], [_param("c", INT)], BOOL, [], [], None, False, True, True),
        FnSig("is_space", [], [_param("c", INT)], BOOL, [], [], None, False, True, True),
        FnSig("concat", ["T"], [_param("a", arr), _param("b", arr)], arr, [], [], None, False, True, True),
        FnSig("slice", ["T"], [_param("a", arr), _param("lo", INT), _param("hi", INT)], arr, [], [], None, False, True, True),
    ]
    return {s.name: s for s in sigs}


@dataclass
class Ctx:
    fn: Optional[FnSig]
    formula: bool = False
    allow_result: bool = False
    allow_old: bool = False
    allow_self: Optional[RT] = None
    in_loop: bool = False


class Checker:
    def __init__(self, program: Program, prelude: Program):
        self.diags: list = []
        self.data: dict = {}
        self.aliases: dict = {}
        self.consts: dict = {}
        self.specs: dict = {}
        self.fns: dict = builtin_sigs()
        self.user_fns: list = []
        self.ctor_of: dict = {}       # ctor name -> data decl
        self.holes: list = []
        self.items = prelude.items + program.items
        self.user_items = program.items

    def error(self, e: CompileError):
        self.diags.append(e.diag)

    # ---------- typy z wyrażeń typowych ----------
    def resolve(self, t: Node, tvars: list) -> RT:
        if isinstance(t, TFn):
            ps = [self.resolve(pt, tvars) for _, pt in t.params]
            ret = self.resolve(t.ret, tvars)
            for x in ps + [ret]:
                if contains_fn(x):
                    raise err("E2015", t.span, "typ funkcyjny nie może zawierać typów funkcyjnych (prototyp: funkcje tylko pierwszego rzędu jako argumenty)", ["3.1"])
            names = tuple(n if n is not None else f"_{i}" for i, (n, _) in enumerate(t.params))
            return RT("Fn", None, ps + [ret], [], names)
        if isinstance(t, TRefine):
            base = self.resolve(t.base, tvars)
            return RT(base.kind, base.name, base.args, base.refs + [t.formula])
        assert isinstance(t, TName)
        n = t.name
        if n in tvars:
            if t.args:
                raise err("E2001", t.span, f"parametr typowy `{n}` nie przyjmuje argumentów", ["5.5"])
            return V(n)
        args = [self.resolve(a, tvars) for a in t.args]
        if n in ("Int", "Bool", "Unit"):
            if args:
                raise err("E2001", t.span, f"typ `{n}` nie przyjmuje argumentów", ["3.1"])
            return RT(n)
        if any(contains_fn(a) for a in args):
            raise err("E2015", t.span, "typ funkcyjny nie może być argumentem typu (tablice i typy danych funkcji nie są obsługiwane)", ["3.1"])
        if n == "Array":
            if len(args) != 1:
                raise err("E2001", t.span, "typ `Array` przyjmuje dokładnie jeden argument", ["3.1"])
            return RT("Array", None, args)
        if n in self.aliases:
            al = self.aliases[n]
            if len(args) != len(al.tparams):
                raise err("E2001", t.span, f"typ `{n}` przyjmuje {len(al.tparams)} argumentów", ["3.1"])
            base = self.resolve(al.type, al.tparams)
            return subst_rt(base, dict(zip(al.tparams, args)))
        if n in self.data:
            d = self.data[n]
            if len(args) != len(d.tparams):
                raise err("E2001", t.span, f"typ `{n}` przyjmuje {len(d.tparams)} argumentów", ["3.1"])
            return RT("Data", n, args)
        if n in ("F64", "Cap", "Chan", "Mailbox"):
            raise err("E2002", t.span, f"typ `{n}` nie jest obsługiwany w prototypie", ["3.1"])
        raise err("E1001", t.span, f"nieznany typ `{n}`", ["3.1"])

    # ---------- zbieranie deklaracji ----------
    def collect(self):
        self._collect()
        al = self.aliases.get("Byte")
        self.byte_ref = al.type.formula if al is not None and isinstance(al.type, TRefine) else None

    def _collect(self):
        for it in self.items:
            if isinstance(it, DataDecl):
                if it.name in self.data:
                    self.error(err("E1002", it.span, f"typ `{it.name}` zadeklarowano wielokrotnie", ["3.4"]))
                self.data[it.name] = it
            elif isinstance(it, TypeAlias):
                self.aliases[it.name] = it
        for it in self.items:
            if isinstance(it, DataDecl):
                try:
                    it.rctors = [(c.name, [(fn, self.resolve(ft, it.tparams)) for fn, ft in c.fields]) for c in it.ctors]
                    if any(contains_fn(ft) for _, fs in it.rctors for _, ft in fs):
                        raise err("E2015", it.span, "pole typu danych nie może mieć typu funkcyjnego", ["3.1"])
                    for c in it.ctors:
                        if c.name in self.ctor_of:
                            raise err("E1003", c.span, f"konstruktor `{c.name}` zadeklarowano wielokrotnie", ["3.4"])
                        self.ctor_of[c.name] = it
                except CompileError as e:
                    self.error(e)
                    it.rctors = []
        for it in self.items:
            try:
                if isinstance(it, ConstDecl):
                    self.consts[it.name] = it
                    it.rt = self.resolve(it.type, [])
                    it.value = self.const_eval(it.expr)
                    if not (INT_MIN <= it.value <= INT_MAX):
                        raise err("E2003", it.expr.span, "stała poza zakresem `Int`", ["3.1"])
                elif isinstance(it, SpecFn):
                    it.rparams = [(p.name, self.resolve(p.type, it.tparams), False) for p in it.params]
                    it.rret = self.resolve(it.ret, it.tparams)
                    self.specs[it.name] = it
                elif isinstance(it, FnDecl):
                    if it.name in self.fns:
                        raise err("E1004", it.span, f"funkcja `{it.name}` jest już zdefiniowana", ["3.4"])
                    params = [(p.name, self.resolve(p.type, it.tparams), p.inout) for p in it.params]
                    names = [p[0] for p in params]
                    if len(set(names)) != len(names):
                        raise err("E1005", it.span, "powtórzona nazwa parametru", ["3.4"])
                    ret = self.resolve(it.ret, it.tparams) if it.ret else UNIT
                    if contains_fn(ret):
                        raise err("E2015", it.ret.span, "funkcja nie może zwracać funkcji (prototyp)", ["3.1"])
                    if any(contains_fn(p[1]) and p[2] for p in params):
                        raise err("E2015", it.span, "parametr typu funkcyjnego nie może być `inout`", ["3.1"])
                    sig = FnSig(it.name, it.tparams, params, ret, it.requires, it.ensures,
                                it.decreases, it.partial, False, False, it)
                    it.sig = sig
                    self.fns[it.name] = sig
                    self.user_fns.append(it)
            except CompileError as e:
                self.error(e)

    def const_eval(self, e):
        if isinstance(e, IntLit):
            return e.value
        if isinstance(e, Name) and e.name in self.consts:
            return self.consts[e.name].value
        if isinstance(e, Unary) and e.op == "-":
            return -self.const_eval(e.expr)
        if isinstance(e, Binary) and e.op in "+-*":
            a, b = self.const_eval(e.left), self.const_eval(e.right)
            return a + b if e.op == "+" else a - b if e.op == "-" else a * b
        raise err("E2004", e.span, "wyrażenie stałej musi być stałą arytmetyczną", ["2.3"])

    # ---------- główna procedura ----------
    def run(self):
        self.collect()
        # rekurencyjne funkcje specyfikacyjne (§6.1): silnie spójne składowe grafu wywołań
        deps = {n: {c.name for c in walk([sf.body, sf.decreases]) if isinstance(c, Call) and c.name in self.specs}
                for n, sf in self.specs.items()}
        def reach(a, b, seen):
            for c in deps[a]:
                if c == b or (c not in seen and (seen.add(c) or reach(c, b, seen))):
                    return True
            return False
        self.spec_scc = {}
        for n, sf in self.specs.items():
            sf.recursive = reach(n, n, set())
            self.spec_scc[n] = frozenset(m for m in self.specs if m == n or (reach(n, m, set()) and reach(m, n, set())))
            if sf.recursive and sf.decreases is None:
                self.error(err("E3013", sf.span, f"rekurencyjna funkcja specyfikacyjna `{n}` wymaga miary `decreases`", ["6.1"],
                               notes=["np. `decreases t` dla parametru typu danych albo `decreases n` dla `Nat`"]))
        for d in self.data.values():
            if d.where is not None:
                try:
                    st = RT("Data", d.name, [V(p) for p in d.tparams])
                    t = self.infer(d.where, {}, Ctx(None, formula=True, allow_self=st), BOOL)
                    self.expect_ty(d.where, t, BOOL)
                except CompileError as e:
                    self.error(e)
        for it in self.items:
            if isinstance(it, SpecFn):
                try:
                    env = {n: VarInfo(t, "param") for n, t, _ in it.rparams}
                    t = self.infer(it.body, env, Ctx(None, formula=True), it.rret.bare())
                    self.expect_ty(it.body, t, it.rret.bare())
                    if it.decreases is not None:
                        self.check_measure(it.decreases, env, Ctx(None, formula=True))
                except CompileError as e:
                    self.error(e)
        for f in self.user_fns:
            try:
                self.check_fn(f)
            except CompileError as e:
                self.error(e)
        self.check_recursion()
        return self.diags

    def check_refs(self, rt: RT, env, fn):
        if rt.kind == "Fn":
            env2 = dict(env)
            for pn, pt in zip(rt.pnames, rt.args[:-1]):
                self.check_refs(pt, env, fn)
                env2[pn] = VarInfo(pt, "param")
            self.check_refs(rt.args[-1], env2, fn)
            return
        for r in rt.refs:
            t = self.infer(r, env, Ctx(fn, formula=True, allow_self=rt.bare()), BOOL)
            self.expect_ty(r, t, BOOL)
        for a in rt.args:
            self.check_refs(a, env, fn)

    def check_fn(self, f: FnDecl):
        sig = f.sig
        env = {}
        for n, t, inout in sig.params:
            env[n] = VarInfo(t, "inout" if inout else "param")
        for n, t, _ in sig.params:
            self.check_refs(t, env, sig)
        self.check_refs(sig.ret, env, sig)
        for r in f.requires:
            self.expect_ty(r, self.infer(r, env, Ctx(sig, formula=True), BOOL), BOOL)
        for r in f.ensures:
            self.expect_ty(r, self.infer(r, env, Ctx(sig, formula=True, allow_result=True, allow_old=True), BOOL), BOOL)
        if f.decreases is not None:
            self.check_measure(f.decreases, env, Ctx(sig, formula=True))
        if f.lemma:
            if any(p[2] for p in sig.params) or f.ret is not None:
                raise err("E3014", f.span, "lemat nie może mieć parametrów `inout` ani wyniku", ["5.3"])
        for ex in f.examples:
            eenv = {}
            if ex.binders:
                for n, t in ex.binders:
                    eenv[n] = VarInfo(self.resolve(t, []), "let")
            try:
                self.expect_ty(ex.expr, self.infer(ex.expr, eenv, Ctx(None, formula=False), BOOL), BOOL)
            except CompileError as e:
                self.error(e)
        body_ty = self.block(f.body, dict(env), Ctx(sig), sig.ret)
        if sig.ret.kind != "Unit" and not same(body_ty, sig.ret):
            raise err("E2010", f.body.span, "typ wartości ciała funkcji nie zgadza się z typem wyniku",
                      ["5.3"], expected=str(sig.ret), found=str(body_ty))

    def check_measure(self, e, env, ctx):
        """Miara: `Int` albo wartość typu danych (porządek strukturalny, ranga)."""
        t = self.infer(e, env, ctx, None)
        if t.kind not in ("Int", "Data"):
            raise err("E2014", e.span, "miara `decreases` musi być typu `Int` albo typem danych", ["5.3"], found=str(t))
        return t

    # ---------- pomocnicze ----------
    def expect_ty(self, node, got: RT, want: RT):
        if not same(got, want):
            raise err("E2011", node.span, "niezgodność typów", ["5.2"], expected=str(want.bare()), found=str(got.bare()))

    def set(self, node, t: RT) -> RT:
        node.ty = t
        return t

    # ---------- bloki i instrukcje ----------
    def block(self, b: Block, env: dict, ctx: Ctx, expected: Optional[RT]) -> RT:
        env = dict(env)
        result = UNIT
        for k, s in enumerate(b.stmts):
            last = k == len(b.stmts) - 1
            try:
                r = self.stmt(s, env, ctx, expected if last else None)
            except CompileError as e:
                self.error(e)
                r = NEVER
            if last and isinstance(s, ExprStmt):
                result = r
            else:
                result = NEVER if r.kind == "Never" else UNIT
        b.ty = result
        return result

    def stmt(self, s, env, ctx: Ctx, expected) -> RT:
        if isinstance(s, Let):
            want = self.resolve(s.type, ctx.fn.tparams if ctx.fn else []) if s.type else None
            if want is not None:
                self.check_refs(want, {**env, s.name: VarInfo(want, "let")}, ctx.fn)
            try:
                t = self.infer(s.expr, env, ctx, want)
            except CompileError:
                # brak kaskady (§9.3): zmienna z błędnym inicjalizatorem jest „skażona”
                env[s.name] = VarInfo(want or NEVER, "var" if s.mutable else "let")
                raise
            if t.kind == "Never":
                return NEVER
            if t.kind == "Unit" and want is None and not isinstance(s.expr, (UnitLit,)):
                pass
            if want is not None:
                self.expect_ty(s.expr, t, want)
                t = want
            if t.kind == "Fn":
                if s.mutable:
                    raise err("E2015", s.span, "zmienna typu funkcyjnego musi być niemutowalna (`let`)", ["3.1"])
                if want is None and getattr(s.expr, "fty", None) is not None:
                    t = s.expr.fty
            s.rt = t
            env[s.name] = VarInfo(t, "var" if s.mutable else "let")
            return UNIT
        if isinstance(s, Assign):
            vi = env.get(s.name)
            if vi is None:
                raise err("E1010", s.span, f"nieznana zmienna `{s.name}`", ["5.2"])
            if vi.kind == "cap":
                raise err("E6010", s.span, f"domknięcie nie może zmieniać przechwyconej zmiennej `{s.name}`", ["4.6"])
            if vi.kind not in ("var", "inout"):
                raise err("E2110", s.span, f"przypisanie do zmiennej niemutowalnej `{s.name}`", ["5.2"],
                          fix={"patch": f"zadeklaruj `{s.name}` przez `var` zamiast `let`", "confidence": "suggested"})
            t = self.infer(s.expr, env, ctx, vi.rt)
            self.expect_ty(s.expr, t, vi.rt)
            s.target_rt = vi.rt
            return UNIT
        if isinstance(s, IndexAssign):
            vi = env.get(s.name)
            if vi is None:
                raise err("E1010", s.span, f"nieznana zmienna `{s.name}`", ["5.2"])
            if vi.kind not in ("var", "inout"):
                raise err("E2110", s.span, f"zapis elementu niemutowalnej tablicy `{s.name}`", ["5.2"])
            if vi.rt.kind != "Array":
                raise err("E2011", s.span, f"`{s.name}` nie jest tablicą", ["5.2"], found=str(vi.rt))
            self.expect_ty(s.index, self.infer(s.index, env, ctx, INT), INT)
            el = vi.rt.args[0]
            self.expect_ty(s.expr, self.infer(s.expr, env, ctx, el), el)
            s.target_rt = vi.rt
            return UNIT
        if isinstance(s, (While, For)):
            if isinstance(s, While):
                self.expect_ty(s.cond, self.infer(s.cond, env, ctx, BOOL), BOOL)
                self.require_pure(s.cond, "warunek pętli")
                benv = dict(env)
            else:
                it = self.infer(s.iterable, env, ctx, None)
                if it.kind != "Array":
                    raise err("E2011", s.iterable.span, "pętla `for` iteruje po tablicy", ["4.3"], found=str(it))
                benv = dict(env)
                benv["it"] = VarInfo(INT, "let")
            fenv = dict(benv)
            for inv in s.invariants:
                self.expect_ty(inv, self.infer(inv, fenv, Ctx(ctx.fn, formula=True, allow_old=True), BOOL), BOOL)
            if isinstance(s, While):
                if s.decreases is not None:
                    self.check_measure(s.decreases, fenv, Ctx(ctx.fn, formula=True))
                elif ctx.fn and not ctx.fn.partial:
                    raise err("E3010", s.span, "pętla bez `decreases` w funkcji totalnej", ["5.3"],
                              notes=["dodaj wariant `decreases t` albo oznacz funkcję jako `partial`"])
            if isinstance(s, For):
                benv[s.var] = VarInfo(it.args[0], "let")
            self.block(s.body, benv, Ctx(ctx.fn, in_loop=True), None)
            return UNIT
        if isinstance(s, Return):
            if ctx.fn is None:
                raise err("E2120", s.span, "`return` poza funkcją", ["5.2"])
            if s.expr is None:
                if ctx.fn.ret.kind != "Unit":
                    raise err("E2011", s.span, "brak wartości w `return`", ["5.2"], expected=str(ctx.fn.ret))
            else:
                self.expect_ty(s.expr, self.infer(s.expr, env, ctx, ctx.fn.ret), ctx.fn.ret)
            return NEVER
        if isinstance(s, (Break, Continue)):
            if not ctx.in_loop:
                raise err("E2121", s.span, "`break`/`continue` poza pętlą", ["5.2"])
            return NEVER
        if isinstance(s, Assert):
            self.expect_ty(s.formula, self.infer(s.formula, env, Ctx(ctx.fn, formula=True, allow_old=True), BOOL), BOOL)
            return UNIT
        if isinstance(s, ExprStmt):
            return self.infer(s.expr, env, ctx, expected)
        raise err("E0099", s.span, f"nieobsługiwana instrukcja {type(s).__name__}", [])

    def require_pure(self, e, what):
        for n in walk(e):
            if isinstance(n, Call) and n.callee is not None and not n.callee.pure:
                raise err("E3020", n.span, f"{what} musi być czysty: wywołanie `{n.name}` jest niedozwolone w prototypie", ["5.2"])

    # ---------- wyrażenia ----------
    def infer(self, e, env, ctx: Ctx, expected: Optional[RT]) -> RT:
        t = self._infer(e, env, ctx, expected)
        e.ty = t
        return t

    def _infer(self, e, env, ctx: Ctx, expected):
        if isinstance(e, IntLit):
            if e.value > INT_MAX:
                raise err("E2003", e.span, "literał poza zakresem `Int`", ["3.1"])
            return INT
        if isinstance(e, BoolLit):
            return BOOL
        if isinstance(e, UnitLit):
            return UNIT
        if isinstance(e, Name):
            if e.name in env:
                rt = env[e.name].rt
                if rt.kind == "Fn":
                    e.fty = rt
                return rt.bare()
            if e.name in self.consts:
                return INT
            sig = self.fns.get(e.name)
            if sig is not None and not sig.builtin:
                return self.fn_ref(e, sig, ctx)
            raise err("E1010", e.span, f"nieznana zmienna `{e.name}`", ["5.2"])
        if isinstance(e, Lambda):
            return self.lambda_(e, env, ctx, expected)
        if isinstance(e, SelfRef):
            if ctx.allow_self is None:
                raise err("E2130", e.span, "`self` dozwolone tylko w uściśleniu typu", ["6.1"])
            return ctx.allow_self
        if isinstance(e, ResultRef):
            if not ctx.allow_result:
                raise err("E2131", e.span, "`result` dozwolone tylko w `ensures`", ["6.1"])
            return ctx.fn.ret.bare()
        if isinstance(e, Old):
            if not ctx.allow_old:
                raise err("E2132", e.span, "`old(…)` dozwolone tylko w `ensures`, niezmiennikach i asercjach", ["6.1"])
            if e.name not in env:
                raise err("E1010", e.span, f"nieznana zmienna `{e.name}`", ["6.1"])
            return env[e.name].rt.bare()
        if isinstance(e, Try):
            return self.try_(e, env, ctx, expected)
        if isinstance(e, Hole):
            if ctx.formula:
                raise err("E7001", e.span, "dziura nie może wystąpić w formule", ["9.5"])
            if expected is None:
                raise err("E7002", e.span, "nie można ustalić typu dziury — dodaj adnotację typu", ["9.5"])
            e.env = dict(env)
            e.fn = ctx.fn
            self.holes.append(e)
            return expected.bare()
        if isinstance(e, Unary):
            if e.op == "-":
                self.expect_ty(e.expr, self.infer(e.expr, env, ctx, INT), INT)
                return INT
            self.expect_ty(e.expr, self.infer(e.expr, env, ctx, BOOL), BOOL)
            return BOOL
        if isinstance(e, Binary):
            return self.binary(e, env, ctx)
        if isinstance(e, Quant):
            if not ctx.formula:
                raise err("E6103", e.span, f"kwantyfikator `{e.kind}` dozwolony tylko w formułach", ["6.1"])
            self.expect_ty(e.lo, self.infer(e.lo, env, ctx, INT), INT)
            self.expect_ty(e.hi, self.infer(e.hi, env, ctx, INT), INT)
            benv = dict(env)
            benv[e.var] = VarInfo(INT, "quant")
            self.expect_ty(e.body, self.infer(e.body, benv, ctx, BOOL), BOOL)
            return BOOL
        if isinstance(e, Field):
            t = self.infer(e.expr, env, ctx, None)
            if t.kind == "Array" and e.name == "len":
                return INT
            if t.kind == "Data":
                d = self.data[t.name]
                if len(d.rctors) == 1:
                    s = dict(zip(d.tparams, t.args))
                    for fn, ft in d.rctors[0][1]:
                        if fn == e.name:
                            return subst_rt(ft, s).bare()
            raise err("E2040", e.span, f"typ `{t}` nie ma pola `{e.name}`", ["4.1"])
        if isinstance(e, Index):
            t = self.infer(e.expr, env, ctx, None)
            if t.kind != "Array":
                raise err("E2011", e.expr.span, "indeksować można tylko tablice", ["5.2"], found=str(t))
            self.expect_ty(e.index, self.infer(e.index, env, ctx, INT), INT)
            return t.args[0]
        if isinstance(e, ArrayLit):
            el = expected.args[0] if expected is not None and expected.kind == "Array" else None
            if el is None and isinstance(e, StrLit):
                el = self.resolve(TName("Byte", []), [])
            for it in e.items:
                t = self.infer(it, env, ctx, el)
                if el is None:
                    el = t
                self.expect_ty(it, t, el)
            if el is None:
                raise err("E2012", e.span, "nie można wywnioskować typu elementów pustej tablicy — dodaj adnotację", ["5.5"])
            return RT("Array", None, [el.bare()])
        if isinstance(e, CtorCall):
            return self.ctor_call(e, env, ctx, expected)
        if isinstance(e, Call):
            return self.call(e, env, ctx, expected)
        if isinstance(e, If):
            if ctx.formula and not isinstance(e.then, Block):
                pass
            self.expect_ty(e.cond, self.infer(e.cond, env, ctx, BOOL), BOOL)
            t1 = self.block_or_formula(e.then, env, ctx, expected)
            if e.els is None:
                return UNIT
            t2 = self.infer(e.els, env, ctx, expected) if isinstance(e.els, If) else self.block_or_formula(e.els, env, ctx, expected)
            if not same(t1, t2):
                raise err("E2011", e.span, "gałęzie `if` mają różne typy", ["5.2"], expected=str(t1), found=str(t2))
            return t2 if t1.kind == "Never" else t1
        if isinstance(e, Match):
            return self.match(e, env, ctx, expected)
        if isinstance(e, BlockExpr):
            if ctx.formula:
                raise err("E6104", e.span, "bloki nie są dozwolone w formułach", ["6.1"])
            return self.block(e.block, env, ctx, expected)
        raise err("E0099", e.span, f"nieobsługiwane wyrażenie {type(e).__name__}", [])

    # ---------- funkcje jako wartości ----------
    def fn_type_of_sig(self, sig):
        return RT("Fn", None, [pt for _, pt, _ in sig.params] + [sig.ret], [], tuple(pn for pn, _, _ in sig.params))

    def fn_ref(self, e, sig, ctx):
        """Nazwa funkcji globalnej użyta jako wartość."""
        d = sig.decl
        why = None
        if d.lemma:
            why = "lemat"
        elif sig.partial:
            why = "funkcja częściowa"
        elif sig.tparams:
            why = "funkcja generyczna"
        elif any(p[2] for p in sig.params):
            why = "funkcja z parametrem `inout`"
        elif d.requires:
            why = "funkcja z `requires` (zapisz warunek w typie parametru, np. `x: Int where self > 0`)"
        elif any(contains_fn(p[1]) for p in sig.params):
            why = "funkcja wyższego rzędu"
        if why:
            raise err("E3016", e.span, f"`{e.name}` nie może być użyta jako wartość: {why}", ["4.6"])
        e.fnref = sig
        e.fty = self.fn_type_of_sig(sig)
        return e.fty.bare()

    def lambda_(self, e, env, ctx, expected):
        if ctx.formula:
            raise err("E6104", e.span, "domknięcia nie są dozwolone w formułach", ["6.1"])
        exp = expected if expected is not None and expected.kind == "Fn" else None
        if exp is not None and len(exp.args) - 1 != len(e.params):
            raise err("E2013", e.span, f"domknięcie ma {len(e.params)} parametrów, oczekiwano {len(exp.args) - 1}", ["5.2"])
        tvars = ctx.fn.tparams if ctx.fn else []
        ptys = []
        for i, (pn, pt) in enumerate(e.params):
            if pt is not None:
                t = self.resolve(pt, tvars)
                if exp is not None and not same(t.bare(), exp.args[i].bare()):
                    raise err("E2011", pt.span, f"typ parametru `{pn}` niezgodny z oczekiwanym", ["5.2"],
                              expected=str(exp.args[i]), found=str(t))
                if exp is not None and t.refs and [id(r) for r in t.refs] != [id(r) for r in exp.args[i].refs]:
                    raise err("E2141", pt.span, f"parametr domknięcia `{pn}` ma uściślenie inne niż typ oczekiwany — "
                              "pomiń adnotację, typ zostanie przejęty z kontekstu", ["4.6"], expected=str(exp.args[i]))
            elif exp is not None:
                t = exp.args[i]
                if any(n.kind == "Var" for n in _iter_rt(t)):
                    raise err("E2012", e.span, f"nie można wywnioskować typu parametru `{pn}` — dodaj adnotację", ["5.5"])
            else:
                raise err("E2012", e.span, f"brak typu parametru `{pn}` domknięcia — dodaj adnotację", ["5.5"])
            if contains_fn(t):
                raise err("E2015", e.span, "parametr domknięcia nie może być funkcją (prototyp)", ["3.1"])
            ptys.append(t)
        for n in walk(e.body):
            bad = None
            if isinstance(n, (While, For)):
                bad = "pętle"
            elif isinstance(n, (Return, Break, Continue)):
                bad = "`return`/`break`/`continue`"
            elif isinstance(n, (Assign, IndexAssign)):
                bad = "przypisania"
            elif isinstance(n, Call) and any(a.inout for a in n.args):
                bad = "argumenty `inout`"
            elif isinstance(n, Lambda):
                bad = "zagnieżdżone domknięcia"
            if bad:
                raise err("E3015", n.span, f"ciało domknięcia jest wyrażeniem bez efektów: {bad} są niedozwolone "
                          "(użyj nazwanej funkcji)", ["4.6"])
        benv = {k: VarInfo(v.rt, "cap" if v.kind in ("var", "inout") else "let") for k, v in env.items()}
        for (pn, _), t in zip(e.params, ptys):
            benv[pn] = VarInfo(t, "param")
        ret_full = self.resolve(e.ret, tvars) if e.ret is not None else None
        if ret_full is not None:
            self.check_refs(ret_full, {**benv, "result": None} if False else benv, ctx.fn)
        want = ret_full.bare() if ret_full is not None else (exp.args[-1].bare() if exp is not None and not any(
            n.kind == "Var" for n in _iter_rt(exp.args[-1])) else None)
        bt = self.infer(e.body, benv, Ctx(ctx.fn, formula=False, in_loop=False), want)
        if want is not None:
            self.expect_ty(e.body, bt, want)
        if contains_fn(bt):
            raise err("E2015", e.span, "domknięcie nie może zwracać funkcji (prototyp)", ["3.1"])
        if exp is not None and not any(n.kind == "Var" for n in _iter_rt(exp.args[-1])):
            # typ oczekiwany wyznacza typ domknięcia; uściślenie wyniku z kontekstu jest
            # dowodzone w ciele domknięcia (nie przy przekazaniu)
            if ret_full is None and exp.args[-1].refs:
                ret_full = exp.args[-1]
            elif ret_full is not None and ret_full.refs and exp.args[-1].refs and \
                    [id(r) for r in ret_full.refs] != [id(r) for r in exp.args[-1].refs]:
                raise err("E2141", e.ret.span, "wynik domknięcia ma uściślenie inne niż typ oczekiwany — "
                          "pomiń adnotację, typ zostanie przejęty z kontekstu", ["4.6"], expected=str(exp.args[-1]))
        e.alias_pnames = tuple(exp.pnames) if exp is not None and len(exp.pnames) == len(e.params) else ()
        rt_ = ret_full if ret_full is not None else bt.bare()
        e.fty = RT("Fn", None, ptys + [rt_], [], e.alias_pnames or tuple(pn for pn, _ in e.params))
        e.ptys = ptys
        e.ret_full = ret_full
        return e.fty.bare()

    def closure_call(self, e, env, ctx):
        ft = env[e.name].rt
        if len(e.args) != len(ft.args) - 1:
            raise err("E2013", e.span, f"`{e.name}` przyjmuje {len(ft.args) - 1} argumentów, podano {len(e.args)}", ["5.2"])
        for a, pt in zip(e.args, ft.args[:-1]):
            if a.inout:
                raise err("E6003", a.span, "funkcje-wartości nie przyjmują argumentów `inout`", ["5.4"])
            self.expect_ty(a.expr, self.infer(a.expr, env, ctx, pt.bare()), pt.bare())
        e.callee = None
        e.closure = ft
        return ft.args[-1].bare()

    def try_(self, e, env, ctx, expected):
        """`e?` (§4.2): elaboracja do `match` z wczesnym powrotem."""
        if ctx.formula or ctx.fn is None:
            raise err("E2140", e.span, "operator `?` jest dozwolony tylko w ciele funkcji", ["4.2"])
        t = self.infer(e.expr, env, ctx, None)
        ret = ctx.fn.ret
        sp_ = e.span
        self.try_count = getattr(self, "try_count", 0) + 1
        v = f"_try{self.try_count}"
        if t.kind == "Data" and t.name == "Option" and ret.kind == "Data" and ret.name == "Option":
            arms = [Arm(Pattern("ctor", name="Some", args=[Pattern("var", name=v, span=sp_)], span=sp_), None, Name(v, sp_), sp_),
                    Arm(Pattern("ctor", name="None", span=sp_), None,
                        BlockExpr(Block([Return(CtorCall("None", [], sp_), sp_)], sp_), sp_), sp_)]
        elif (t.kind == "Data" and t.name == "Result" and ret.kind == "Data" and ret.name == "Result"
              and same(t.args[1], ret.args[1])):
            w = v + "e"
            arms = [Arm(Pattern("ctor", name="Ok", args=[Pattern("var", name=v, span=sp_)], span=sp_), None, Name(v, sp_), sp_),
                    Arm(Pattern("ctor", name="Err", args=[Pattern("var", name=w, span=sp_)], span=sp_), None,
                        BlockExpr(Block([Return(CtorCall("Err", [Name(w, sp_)], sp_), sp_)], sp_), sp_), sp_)]
        else:
            raise err("E2140", e.span, "operator `?` wymaga `Option` w funkcji zwracającej `Option` "
                      "albo `Result<_, E>` w funkcji zwracającej `Result<_, E>` (ten sam typ błędu)", ["4.2"],
                      expected=str(ret), found=str(t))
        m = Match(e.expr, arms, sp_)
        e.desugared = m
        return self.infer(m, env, ctx, expected)

    def block_or_formula(self, b, env, ctx, expected):
        if ctx.formula:
            if len(b.stmts) != 1 or not isinstance(b.stmts[0], ExprStmt):
                raise err("E6104", b.span, "w formule gałąź `if` musi być pojedynczym wyrażeniem", ["6.1"])
            t = self.infer(b.stmts[0].expr, env, ctx, expected)
            b.ty = t
            return t
        return self.block(b, env, ctx, expected)

    def binary(self, e, env, ctx):
        op = e.op
        if op in ("&&", "||"):
            self.expect_ty(e.left, self.infer(e.left, env, ctx, BOOL), BOOL)
            self.expect_ty(e.right, self.infer(e.right, env, ctx, BOOL), BOOL)
            return BOOL
        if op in ("+", "-", "*", "/", "%"):
            self.expect_ty(e.left, self.infer(e.left, env, ctx, INT), INT)
            self.expect_ty(e.right, self.infer(e.right, env, ctx, INT), INT)
            return INT
        if op in ("<", "<=", ">", ">="):
            self.expect_ty(e.left, self.infer(e.left, env, ctx, INT), INT)
            self.expect_ty(e.right, self.infer(e.right, env, ctx, INT), INT)
            return BOOL
        # == !=
        tl = self.infer(e.left, env, ctx, None) if not isinstance(e.left, (CtorCall, ArrayLit)) else None
        if tl is None:
            tr = self.infer(e.right, env, ctx, None)
            tl = self.infer(e.left, env, ctx, tr)
        else:
            tr = self.infer(e.right, env, ctx, tl)
        self.expect_ty(e.right, tr, tl)
        if tl.kind == "Fn":
            raise err("E2031", e.span, "funkcji nie można porównywać `==`", ["5.5"])
        inner = tl.args[0] if tl.kind == "Array" else tl
        if has_array(inner, self.data):
            raise err("E2030", e.span, "porównanie `==` typów złożonych zawierających tablice nie jest obsługiwane w prototypie", ["5.5"],
                      notes=["dozwolone: typy bez tablic oraz `Array<T>` z `T` bez tablic"])
        return BOOL

    def ctor_call(self, e, env, ctx, expected):
        d = self.ctor_of.get(e.name)
        if d is None:
            raise err("E1011", e.span, f"nieznany konstruktor `{e.name}`", ["3.4"])
        fields = dict(d.rctors)[e.name]
        if len(fields) != len(e.args):
            raise err("E2013", e.span, f"konstruktor `{e.name}` przyjmuje {len(fields)} argumentów", ["5.2"])
        s = {}
        if expected is not None and expected.kind == "Data" and expected.name == d.name:
            s = dict(zip(d.tparams, [a.bare() for a in expected.args]))
        for (fn, ft), a in zip(fields, e.args):
            want = subst_rt(ft, s)
            known = not any(n.kind == "Var" and n.name in d.tparams for n in _iter_rt(want))
            t = self.infer(a, env, ctx, want if known else None)
            if not unify(ft, t, s, set(d.tparams)):
                raise err("E2011", a.span, "niezgodność typu argumentu konstruktora", ["5.2"], expected=str(subst_rt(ft, s)), found=str(t))
        missing = [p for p in d.tparams if p not in s]
        if missing:
            raise err("E2012", e.span, f"nie można wywnioskować argumentu typowego `{missing[0]}` dla `{e.name}` — dodaj adnotację typu", ["5.5"])
        e.data = d
        e.targs = [s[p] for p in d.tparams]
        return RT("Data", d.name, e.targs)

    def call(self, e, env, ctx, expected):
        if e.name in self.specs:
            if not ctx.formula and ctx.fn is not None:
                raise err("E6105", e.span, f"funkcja specyfikacyjna `{e.name}` może być użyta tylko w formułach i przykładach", ["6.1"])
            sf = self.specs[e.name]
            if len(sf.rparams) != len(e.args):
                raise err("E2013", e.span, f"`{e.name}` przyjmuje {len(sf.rparams)} argumentów", ["5.2"])
            s = {}
            for (pn, pt, _), a in zip(sf.rparams, e.args):
                t = self.infer(a.expr, env, ctx, pt if not sf.tparams else None)
                if not unify(pt.bare(), t, s, set(sf.tparams)):
                    raise err("E2011", a.span, "niezgodność typu argumentu", ["5.2"], expected=str(pt), found=str(t))
            if expected is not None:
                unify(sf.rret.bare(), expected, s, set(sf.tparams))
            missing = [p for p in sf.tparams if p not in s]
            if missing:
                raise err("E2012", e.span, f"nie można wywnioskować argumentu typowego `{missing[0]}` dla `{e.name}`", ["5.5"])
            e.callee = sf
            e.targs = s
            return subst_rt(sf.rret, s).bare()
        if e.name in env and env[e.name].rt.kind == "Fn":
            return self.closure_call(e, env, ctx)
        if e.name in env and env[e.name].rt.kind == "Never":
            return NEVER          # zmienna skażona wcześniejszym błędem — bez kaskady
        sig = self.fns.get(e.name)
        if sig is None:
            raise err("E1012", e.span, f"nieznana funkcja `{e.name}`", ["5.2"])
        e.callee = sig
        if ctx.formula and not sig.pure:
            raise err("E6102", e.span, f"w formule można wywoływać tylko funkcje specyfikacyjne i czyste funkcje preludium; `{e.name}` nie jest czysta", ["6.1"])
        if len(sig.params) != len(e.args):
            raise err("E2013", e.span, f"`{e.name}` przyjmuje {len(sig.params)} argumentów, podano {len(e.args)}", ["5.2"])
        s = {}
        tv = set(sig.tparams)
        inouts = []
        for (pn, pt, pinout), a in zip(sig.params, e.args):
            if pinout != (a.inout is not None):
                raise err("E6003", a.span,
                          f"parametr `{pn}` funkcji `{e.name}` " + ("jest `inout` — przekaż `&zmienna`" if pinout else "nie jest `inout` — usuń `&`"),
                          ["5.4"])
            if pinout:
                vi = env.get(a.inout)
                if vi is None:
                    raise err("E1010", a.span, f"nieznana zmienna `{a.inout}`", ["5.2"])
                if vi.kind not in ("var", "inout"):
                    raise err("E6001", a.span, f"argument inout `&{a.inout}` musi być zmienną mutowalną (`var` lub parametrem `inout`)", ["5.4"])
                if a.inout in inouts:
                    raise err("E6002", a.span, f"naruszenie prawa wyłączności: `{a.inout}` przekazano dwukrotnie jako inout", ["5.4"])
                inouts.append(a.inout)
                t = vi.rt.bare()
            else:
                want = subst_rt(pt, s).bare()
                known = not any(n.kind == "Var" and n.name in tv for n in _iter_rt(want))
                if isinstance(a.expr, Lambda):
                    t = self.infer(a.expr, env, ctx, subst_rt(pt, s))
                else:
                    t = self.infer(a.expr, env, ctx, want if known else None)
            if not unify(pt.bare(), t, s, tv):
                raise err("E2011", a.span, f"niezgodność typu argumentu `{pn}`", ["5.2"], expected=str(subst_rt(pt, s).bare()), found=str(t))
        if expected is not None:
            unify(sig.ret.bare(), expected, s, tv)
        missing = [p for p in sig.tparams if p not in s]
        if missing:
            raise err("E2012", e.span, f"nie można wywnioskować argumentu typowego `{missing[0]}` dla `{e.name}`", ["5.5"])
        e.targs = s
        if ctx.fn is not None and not ctx.fn.partial and sig.partial:
            raise err("E3012", e.span, f"funkcja totalna nie może wywołać funkcji częściowej `{e.name}`", ["5.3"])
        return subst_rt(sig.ret, s).bare()

    def match(self, e, env, ctx, expected):
        st = self.infer(e.expr, env, ctx, None)
        result = None
        covered = set()
        catch_all = False
        for arm in e.arms:
            if catch_all:
                self.diags.append(Diagnostic("W5002", "warning", arm.span, "gałąź nieosiągalna — poprzednie gałęzie pokrywają wszystkie przypadki", ["5.6"]))
            aenv = dict(env)
            irrefutable = self.pattern(arm.pattern, st, aenv)
            if arm.guard is not None:
                self.expect_ty(arm.guard, self.infer(arm.guard, aenv, ctx, BOOL), BOOL)
            else:
                if arm.pattern.kind in ("wild", "var"):
                    catch_all = True
                elif arm.pattern.kind == "ctor" and irrefutable:
                    covered.add(arm.pattern.name)
                elif arm.pattern.kind == "bool":
                    covered.add(arm.pattern.value)
            if isinstance(arm.body, BlockExpr) and ctx.formula:
                raise err("E6104", arm.body.span, "bloki nie są dozwolone w formułach", ["6.1"])
            t = self.infer(arm.body, aenv, ctx, expected if expected is not None else (result if result and result.kind != "Never" else None))
            if result is None or result.kind == "Never":
                result = t
            elif not same(result, t):
                raise err("E2011", arm.body.span, "gałęzie `match` mają różne typy", ["5.2"], expected=str(result), found=str(t))
        rows = [[a.pattern] for a in e.arms if a.guard is None]
        w = self.witness(rows, [st])
        if w is not None:
            missing = w[0]
            guarded = [a for a in e.arms if a.guard is not None]
            notes = []
            if guarded:
                notes.append("gałęzie ze strażnikiem (`if …`) nie liczą się do pokrycia")
            raise err("E5001", e.span, "dopasowanie nie jest wyczerpujące", ["5.6"],
                      found=None, notes=[f"brakujący przypadek: {missing}"] + notes,
                      fix={"patch": f"+ {missing} => ?todo,", "confidence": "unique"})
        return result if result is not None else UNIT

    def witness(self, rows, tys):
        """Algorytm użyteczności (Maranget, §5.6): zwraca listę wzorców-świadków
        wartości nieobjętej żadnym wierszem albo None, gdy pokrycie jest pełne."""
        if not tys:
            return None if rows else []
        if any(all(p.kind in ("wild", "var") for p in r) for r in rows):
            return None
        if not rows:
            return ["_"] * len(tys)
        t, rest = tys[0], tys[1:]
        if t.kind == "Data":
            d = self.data[t.name]
            sub = dict(zip(d.tparams, t.args))
            for cname, fields in d.rctors:
                ftys = [subst_rt(ft, sub).bare() for _, ft in fields]
                srows = []
                for r in rows:
                    p0 = r[0]
                    if p0.kind in ("wild", "var"):
                        srows.append([Pattern("wild")] * len(ftys) + r[1:])
                    elif p0.kind == "ctor" and p0.name == cname:
                        srows.append(list(p0.args) + r[1:])
                w = self.witness(srows, ftys + rest)
                if w is not None:
                    k = len(ftys)
                    head = cname + ("(" + ", ".join(w[:k]) + ")" if k else "")
                    return [head] + w[k:]
            return None
        if t.kind == "Bool":
            for v in (True, False):
                srows = [r[1:] for r in rows if r[0].kind in ("wild", "var") or (r[0].kind == "bool" and r[0].value == v)]
                w = self.witness(srows, rest)
                if w is not None:
                    return ["true" if v else "false"] + w
            return None
        # typy nieskończone: tylko wiersze z wzorcem ogólnym w pierwszej kolumnie
        srows = [r[1:] for r in rows if r[0].kind in ("wild", "var")]
        w = self.witness(srows, rest)
        return None if w is None else ["_"] + w

    def pattern(self, p: Pattern, t: RT, env) -> bool:
        """Zwraca True, gdy wzorzec jest nieodrzucalny względem konstruktora (podwzorce)."""
        p.ty = t
        if p.kind == "wild":
            return True
        if p.kind == "var":
            env[p.name] = VarInfo(t, "pat")
            return True
        if p.kind == "int":
            if t.kind != "Int":
                raise err("E2011", p.span, "wzorzec liczbowy dla typu niecałkowitego", ["5.2"], found=str(t))
            return False
        if p.kind == "bool":
            if t.kind != "Bool":
                raise err("E2011", p.span, "wzorzec logiczny dla typu nielogicznego", ["5.2"], found=str(t))
            return False
        d = self.ctor_of.get(p.name)
        if d is None or t.kind != "Data" or d.name != t.name:
            raise err("E2011", p.span, f"konstruktor `{p.name}` nie należy do typu `{t}`", ["5.2"])
        fields = dict(d.rctors)[p.name]
        if len(fields) != len(p.args):
            raise err("E2013", p.span, f"`{p.name}` ma {len(fields)} pól", ["5.2"])
        s = dict(zip(d.tparams, t.args))
        irr = True
        for (fn, ft), sp_ in zip(fields, p.args):
            if not self.pattern(sp_, subst_rt(ft, s).bare(), env):
                irr = False
            if sp_.kind == "ctor":
                irr = False
        p.data = d
        return irr

    # ---------- rekursja i totalność ----------
    def check_recursion(self):
        graph = {f.name: set() for f in self.user_fns}
        refs = {f.name: [] for f in self.user_fns}
        for f in self.user_fns:
            for n in walk(f.body):
                if isinstance(n, Call) and n.name in graph:
                    graph[f.name].add(n.name)
                if isinstance(n, Name) and getattr(n, "fnref", None) is not None and n.name in graph:
                    graph[f.name].add(n.name)
                    refs[f.name].append(n)
        # Tarjan
        index, low, stack, on, comps, cnt = {}, {}, [], set(), [], [0]

        def sc(v):
            index[v] = low[v] = cnt[0]; cnt[0] += 1
            stack.append(v); on.add(v)
            for w in graph[v]:
                if w not in index:
                    sc(w); low[v] = min(low[v], low[w])
                elif w in on:
                    low[v] = min(low[v], index[w])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop(); on.discard(w); comp.append(w)
                    if w == v:
                        break
                comps.append(comp)
        for v in graph:
            if v not in index:
                sc(v)
        self.scc = {}
        for comp in comps:
            for v in comp:
                self.scc[v] = frozenset(comp)
        for f in self.user_fns:
            for n in refs[f.name]:
                if n.name in self.scc[f.name]:
                    self.error(err("E3016", n.span, f"`{n.name}` nie może być użyta jako wartość wewnątrz własnej "
                                   "składowej rekurencji (brak dowodu terminacji)", ["4.6"]))
            rec = len(self.scc[f.name]) > 1 or f.name in graph[f.name]
            f.recursive = rec
            if rec and not f.partial and f.decreases is None:
                self.error(err("E3011", f.span, f"funkcja rekurencyjna `{f.name}` bez `decreases` w funkcji totalnej", ["5.3"],
                               notes=["dodaj miarę `decreases t` albo oznacz funkcję jako `partial`"]))


def contains_fn(t: RT) -> bool:
    return t.kind == "Fn" or any(contains_fn(a) for a in t.args)


def _iter_rt(t: RT):
    yield t
    for a in t.args:
        yield from _iter_rt(a)
