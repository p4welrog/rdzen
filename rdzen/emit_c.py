# SPDX-License-Identifier: MIT OR Apache-2.0
"""Backend C (§1.1): program Rdzenia → jednostka kompilacji C (GCC/Clang, C11 + rozszerzenia GNU).

Zasady tłumaczenia (zgodne z backendem Pythona, `emit_py.py`):
- przekształcenie R (§6.6): sprawdzenie czasu wykonania tylko dla zobowiązań bez dowodu;
- `Int` → int64_t; arytmetyka z udowodnionym brakiem przepełnienia jest zwykłą arytmetyką C,
  pozostała — przez `__builtin_*_overflow` z pułapką `overflow`;
- `Array<T>` → struktura {len, cap, d}; semantyka wartości przez kopie w tych samych miejscach,
  w których backend Pythona wywołuje `_cp` (wiązanie zmiennej mutowalnej, odczyt całej zmiennej
  mutowalnej, przechwycenie przez domknięcie); parametry `inout` → wskaźniki;
- typy danych → niemutowalne struktury z etykietą na stercie (współdzielone bez kopiowania);
- generyczność → monomorfizacja; typy funkcyjne → para {env, f}; domknięcie → środowisko
  z migawką przechwyconych wartości;
- formuły w sprawdzeniach dynamicznych liczone w arytmetyce 128-bitowej (jak w interpreterze nie
  przepełniają się dla wartości z programu; przekroczenie 128 bitów → pułapka `wd`);
- pułapka: `rz_trap(rodzaj, miejsce)` — `longjmp`, jeśli ustawiono `rz_jb`, w przeciwnym razie
  komunikat i `exit(3)`;
- pamięć nie jest zwalniana (prototyp).
"""
from __future__ import annotations
import json
from contextlib import contextmanager
from .ast import *
from .check import has_array, RT, subst_rt, INT
from .emit_py import Unsupported, needs_stmts, _all_refs, _all_refs_top, _ref_span

C_KEYWORDS = set("""auto break case char const continue default do double else enum extern float for goto
if inline int long register restrict return short signed sizeof static struct switch typedef union
unsigned void volatile while bool true false main""".split())

RUNTIME = r'''
/* ---- środowisko wykonawcze Rdzenia ----
   Ten fragment jest objęty licencją 0BSD (SPDX-License-Identifier: 0BSD) — można go
   używać i rozpowszechniać bez podawania autorstwa; reszta pliku należy do autora programu. */
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>

typedef int8_t rz_unit;
typedef __int128 rz_i128;

static jmp_buf* rz_jb = NULL;              /* ustawione: pułapka wraca przez longjmp */
static const char* rz_trap_kind = "";
static const char* rz_trap_loc = "";

__attribute__((noreturn)) static void rz_trap(const char* kind, const char* loc) {
    rz_trap_kind = kind;
    rz_trap_loc = loc;
    if (rz_jb) longjmp(*rz_jb, 1);
    fprintf(stderr, "pułapka Rdzenia: %s @ %s\n", kind, loc);
    exit(3);
}

static void* rz_alloc(size_t n) {
    void* p = malloc(n ? n : 1);
    if (!p) { fprintf(stderr, "brak pamięci\n"); exit(4); }
    return p;
}

static inline int64_t rz_add(int64_t a, int64_t b, const char* loc) {
    int64_t r;
    if (__builtin_add_overflow(a, b, &r)) { rz_trap("overflow", loc); }
    return r;
}
static inline int64_t rz_sub(int64_t a, int64_t b, const char* loc) {
    int64_t r;
    if (__builtin_sub_overflow(a, b, &r)) { rz_trap("overflow", loc); }
    return r;
}
static inline int64_t rz_mul(int64_t a, int64_t b, const char* loc) {
    int64_t r;
    if (__builtin_mul_overflow(a, b, &r)) { rz_trap("overflow", loc); }
    return r;
}
static inline int64_t rz_neg(int64_t a, const char* loc) {
    if (a == INT64_MIN) { rz_trap("overflow", loc); }
    return -a;
}
static inline int64_t rz_div(int64_t a, int64_t b, const char* loc) {
    if (b == 0 || (a == INT64_MIN && b == -1)) { rz_trap("div0", loc); }
    return a / b;
}
static inline int64_t rz_rem(int64_t a, int64_t b, const char* loc) {
    if (b == 0 || (a == INT64_MIN && b == -1)) { rz_trap("div0", loc); }
    return a % b;
}
static inline int64_t rz_min(int64_t a, int64_t b) { return a < b ? a : b; }
static inline int64_t rz_max(int64_t a, int64_t b) { return a > b ? a : b; }
static inline bool rz_is_digit(rz_i128 c) { return 48 <= c && c <= 57; }
static inline bool rz_is_lower(rz_i128 c) { return 97 <= c && c <= 122; }
static inline bool rz_is_upper(rz_i128 c) { return 65 <= c && c <= 90; }
static inline bool rz_is_alpha(rz_i128 c) { return rz_is_lower(c) || rz_is_upper(c); }
static inline bool rz_is_space(rz_i128 c) { return c == 32 || c == 9 || c == 10 || c == 13; }
static inline void rz_chk(bool c, const char* kind, const char* loc) { if (!c) { rz_trap(kind, loc); } }

/* arytmetyka formuł (128 bitów) */
static inline rz_i128 rz_fadd(rz_i128 a, rz_i128 b) {
    rz_i128 r;
    if (__builtin_add_overflow(a, b, &r)) { rz_trap("wd", "formuła"); }
    return r;
}
static inline rz_i128 rz_fsub(rz_i128 a, rz_i128 b) {
    rz_i128 r;
    if (__builtin_sub_overflow(a, b, &r)) { rz_trap("wd", "formuła"); }
    return r;
}
static inline rz_i128 rz_fmul(rz_i128 a, rz_i128 b) {
    rz_i128 r;
    if (__builtin_mul_overflow(a, b, &r)) { rz_trap("wd", "formuła"); }
    return r;
}
static inline rz_i128 rz_fneg(rz_i128 a) { return rz_fsub(0, a); }
static inline rz_i128 rz_fdiv(rz_i128 a, rz_i128 b) { if (b == 0) { rz_trap("wd", "formuła"); } return a / b; }
static inline rz_i128 rz_frem(rz_i128 a, rz_i128 b) { if (b == 0) { rz_trap("wd", "formuła"); } return a % b; }
static inline rz_i128 rz_fmin(rz_i128 a, rz_i128 b) { return a < b ? a : b; }
static inline rz_i128 rz_fmax(rz_i128 a, rz_i128 b) { return a > b ? a : b; }
static inline int64_t rz_n64(rz_i128 a) {
    if (a < INT64_MIN || a > INT64_MAX) { rz_trap("wd", "formuła"); }
    return (int64_t)a;
}
static inline void rz_pr_int(int64_t v) { printf("%lld", (long long)v); }
static inline void rz_pr_bool(bool v) { fputs(v ? "true" : "false", stdout); }
static inline void rz_pr_unit(rz_unit v) { (void)v; fputs("()", stdout); }
/* ---- koniec środowiska wykonawczego ---- */
'''


def cstr(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def lit(v: int) -> str:
    if v == -2**63:
        return "INT64_MIN"
    return f"{v}LL" if v >= 0 else f"({v}LL)"


def cid(n: str) -> str:
    return n if n not in C_KEYWORDS else n + "_"


class CEmitter:
    def __init__(self, checker, unproved, file):
        self.ch = checker
        self.unproved = unproved
        self.file = file
        self.S = {}                  # bieżące podstawienie parametrów typowych (monomorfizacja)
        self.types = {}              # nazwa C → RT
        self.order = []
        self.fn_insts = {}           # (nazwa, klucz typów) → nazwa C
        self.spec_insts = {}
        self.work = []
        self.protos = []
        self.defs = []
        self.wrappers = set()
        self.uses = set()            # pomocnicze: compare, checked
        self.tmp = 0
        self.buf = []
        self.ind = 0
        self.fn = None
        self.scopes = []
        self.loops = []
        self.olds = {}
        self.names = set()

    # ------------------------------------------------------------ narzędzia
    def w(self, line):
        self.buf.append("    " * self.ind + line)

    def fresh(self, base="t"):
        self.tmp += 1
        return f"_{base}{self.tmp}"

    def loc(self, span):
        return cstr(f"{self.file}:{span.line}:{span.col}")

    def need(self, key) -> bool:
        return self.fn is not None and (self.fn.name, key) in self.unproved

    @contextmanager
    def subst(self, s):
        saved = self.S
        self.S = s
        try:
            yield
        finally:
            self.S = saved

    @contextmanager
    def buffer(self):
        saved = (self.buf, self.ind, self.loops)
        self.buf, self.ind, self.loops = [], 0, []
        try:
            yield
        finally:
            self.buf, self.ind, self.loops = saved

    def T(self, rt) -> RT:
        if rt is None:
            return RT("Unit")
        return subst_rt(rt, self.S).bare()

    def has_arr(self, rt):
        return rt is not None and has_array(self.T(rt), self.ch.data)

    # ------------------------------------------------------------ typy
    def mangle(self, rt: RT) -> str:
        k = rt.kind
        if k in ("Int", "Bool", "Unit"):
            return k
        if k == "Never":
            return "Unit"
        if k == "Array":
            return "A_" + self.mangle(rt.args[0]) + "_"
        if k == "Data":
            return "D_" + rt.name + ("_" + "_".join(self.mangle(a) for a in rt.args) + "_" if rt.args else "")
        if k == "Fn":
            return "F_" + "_".join(self.mangle(a) for a in rt.args) + "_"
        raise Unsupported(f"typ bez ukonkretnienia: {rt}")

    def ct(self, rt) -> str:
        rt = self.T(rt)
        k = rt.kind
        if k == "Int":
            return "int64_t"
        if k == "Bool":
            return "bool"
        if k in ("Unit", "Never"):
            return "rz_unit"
        return self.reg(rt)

    def reg(self, rt: RT) -> str:
        m = self.mangle(rt)
        if m in self.types:
            return m
        self.types[m] = rt
        self.order.append(m)
        if rt.kind == "Array":
            self.ct(rt.args[0])
        elif rt.kind == "Fn":
            for a in rt.args:
                self.ct(a)
        elif rt.kind == "Data":
            for _, fs in self.data_fields(rt):
                for _, ft in fs:
                    self.ct(ft)
        return m

    def data_fields(self, rt):
        d = self.ch.data[rt.name]
        s = dict(zip(d.tparams, rt.args))
        return [(c, [(fn, subst_rt(ft, s).bare()) for fn, ft in fs]) for c, fs in d.rctors]

    def cp(self, expr, rt):
        """Kopia wartości (semantyka wartości tablic)."""
        rt = self.T(rt)
        if rt.kind == "Array":
            return f"{self.ct(rt)}_cp({expr})"
        return expr

    def eq(self, a, b, rt):
        rt = self.T(rt)
        if rt.kind in ("Int", "Bool"):
            return f"({a} == {b})"
        if rt.kind in ("Unit", "Never"):
            return "true"
        return f"{self.ct(rt)}_eq({a}, {b})"

    def zero(self, rt):
        return "{0}"

    def field(self, obj, rt, name):
        rt = self.T(rt)
        if rt.kind == "Array" and name == "len":
            return f"({obj}).len"
        cname, fs = self.data_fields(rt)[0]
        return f"({obj})->u.c_{cname}.f_{cid(name)}"

    # ------------------------------------------------------------ zasięgi nazw
    def lookup(self, name):
        for sc in reversed(self.scopes):
            if name in sc:
                return sc[name]
        raise KeyError(name)

    def bind(self, name, mutable=False, rt=None, cexpr=None):
        if cexpr is None:
            base = "v_" + name
            c = base
            k = 1
            while c in self.names:
                k += 1
                c = f"{base}_{k}"
            self.names.add(c)
        else:
            c = cexpr
        self.scopes[-1][name] = (c, mutable, rt)
        return c

    def ptr(self, cexpr):
        if cexpr.startswith("(*") and cexpr.endswith(")"):
            return cexpr[2:-1]
        return "&" + cexpr

    # ------------------------------------------------------------ formuły (128 bitów)
    def f(self, e, env, result=None, selfv=None) -> str:
        F = lambda x, en=None: self.f(x, en if en is not None else env, result, selfv)
        if isinstance(e, IntLit):
            return lit(e.value)
        if isinstance(e, BoolLit):
            return "true" if e.value else "false"
        if isinstance(e, UnitLit):
            return "0"
        if isinstance(e, Name):
            if e.name in env:
                return env[e.name]
            if getattr(e, "fnref", None) is not None:
                return self.fn_value(e)
            return lit(self.ch.consts[e.name].value)
        if isinstance(e, SelfRef):
            return selfv
        if isinstance(e, ResultRef):
            return result
        if isinstance(e, Old):
            return env.get(("old", e.name), env.get(e.name))
        if isinstance(e, Unary):
            return f"rz_fneg({F(e.expr)})" if e.op == "-" else f"(!{F(e.expr)})"
        if isinstance(e, Binary):
            a, b = F(e.left), F(e.right)
            op = e.op
            if op == "&&":
                return f"({a} && {b})"
            if op == "||":
                return f"({a} || {b})"
            if op in ("+", "-", "*", "/", "%"):
                fn = {"+": "rz_fadd", "-": "rz_fsub", "*": "rz_fmul", "/": "rz_fdiv", "%": "rz_frem"}[op]
                return f"{fn}({a}, {b})"
            if op in ("==", "!="):
                t = self.T(e.left.ty)
                r = f"({a} == {b})" if t.kind in ("Int", "Bool") else self.eq(a, b, t)
                return r if op == "==" else f"(!{r})"
            return f"({a} {op} {b})"
        if isinstance(e, Index):
            arr = self.T(e.expr.ty)
            return f"{self.ct(arr)}_fget({F(e.expr)}, {F(e.index)})"
        if isinstance(e, Field):
            return self.field(F(e.expr), e.expr.ty, e.name)
        if isinstance(e, Quant):
            v = self.fresh("q")
            h = self.fresh("h")
            env2 = dict(env)
            env2[e.var] = v
            body = F(e.body, env2)
            if e.kind == "forall":
                return (f"({{ bool _r{v} = true; for (rz_i128 {v} = {F(e.lo)}, {h} = {F(e.hi)}; {v} < {h}; {v}++) "
                        f"if (!({body})) {{ _r{v} = false; break; }} _r{v}; }})")
            return (f"({{ bool _r{v} = false; for (rz_i128 {v} = {F(e.lo)}, {h} = {F(e.hi)}; {v} < {h}; {v}++) "
                    f"if ({body}) {{ _r{v} = true; break; }} _r{v}; }})")
        if isinstance(e, Call):
            args = [self.f_arg(a.expr, env, result, selfv) for a in e.args]
            if getattr(e, "closure", None) is not None:
                c = env[e.name]
                return f"({c}).f(({c}).env{''.join(', ' + x for x in args)})"
            if e.name in self.ch.specs:
                sf = self.ch.specs[e.name]
                s = {k: self.T(v) for k, v in (e.targs or {}).items()}
                return f"{self.spec_inst(sf, s)}({', '.join(args)})"
            return self.builtin(e.name, [F(a.expr) for a in e.args], e, formula=True)
        if isinstance(e, CtorCall):
            rt = self.T(e.ty)
            fields = dict(self.data_fields(rt))[e.name]
            args = [self.n64(F(a), ft) for a, (_, ft) in zip(e.args, fields)]
            return f"{self.ct(rt)}_{e.name}({', '.join(args)})"
        if isinstance(e, ArrayLit):
            rt = self.T(e.ty)
            el = rt.args[0]
            items = [self.n64(F(a), el) for a in e.items]
            return self.arr_lit(rt, items)
        if isinstance(e, Match):
            subj_t = self.T(e.expr.ty)
            res_t = self.T(e.ty)
            m = self.fresh("m")
            r = self.fresh("r")
            parts = [f"({{ {self.ct(subj_t)} {m} = {F(e.expr)}; {self.ct(res_t)} {r} = {{0}};"]
            first = True
            for arm in e.arms:
                conds, binds = self.pat(arm.pattern, m, subj_t)
                env2 = dict(env)
                decl = ""
                for name, (cx, bt) in binds.items():
                    v = self.fresh("b")
                    decl += f"{self.ct(bt)} {v} = {cx}; "
                    env2[name] = v
                c = " && ".join(conds) or "true"
                guard = F(arm.guard, env2) if arm.guard is not None else None
                body = self.n64(F(arm.body, env2), res_t)
                inner = f"{decl}{r} = {body};"
                if guard is not None:
                    # strażnik: dopasowanie bez strażnika nie kończy wyboru
                    parts.append(f"{'' if first else 'else '}if (({c}) && ({{ {decl}{guard}; }})) {{ {inner} }}")
                else:
                    parts.append(f"{'' if first else 'else '}if ({c}) {{ {inner} }}")
                first = False
            parts.append(f"else rz_trap(\"unreach\", \"formuła\"); {r}; }})")
            return " ".join(parts)
        if isinstance(e, If):
            th = e.then.stmts[0].expr
            els = e.els.stmts[0].expr if isinstance(e.els, Block) else e.els
            return f"(({F(e.cond)}) ? ({F(th)}) : ({F(els)}))"
        raise Unsupported(f"formuła {type(e).__name__}")

    def f_arg(self, x, env, result, selfv):
        return self.n64(self.f(x, env, result, selfv), x.ty)

    def n64(self, expr, rt):
        """Wartość formuły w miejscu wymagającym 64-bitowego Int."""
        return f"rz_n64({expr})" if rt is not None and self.T(rt).kind == "Int" else expr

    def m(self, e, env):
        """Miara jako liczba: typ danych → ranga strukturalna."""
        v = self.f(e, env)
        t = self.T(e.ty) if e.ty is not None else INT
        return f"{self.ct(t)}_rank({v})" if t.kind == "Data" else v

    def pat(self, p, subj, rt):
        """Wzorzec → (warunki, wiązania nazwa → (wyrażenie, typ))."""
        rt = self.T(rt)
        if p.kind == "wild":
            return [], {}
        if p.kind == "var":
            return [], {p.name: (subj, rt)}
        if p.kind == "int":
            return [f"(({subj}) == {lit(p.value)})"], {}
        if p.kind == "bool":
            return [f"(({subj}) == {'true' if p.value else 'false'})"], {}
        conds = [f"({subj})->tag == TAG_{rt.name}_{p.name}"]
        binds = {}
        fields = dict(self.data_fields(rt))[p.name]
        for (fn, ft), sp_ in zip(fields, p.args):
            c, b = self.pat(sp_, f"({subj})->u.c_{p.name}.f_{cid(fn)}", ft)
            conds += c
            binds.update(b)
        return conds, binds

    def builtin(self, n, a, e, formula=False):
        if n in ("is_digit", "is_lower", "is_upper", "is_alpha", "is_space"):
            return f"rz_{n}({a[0]})"
        if n in ("min", "max"):
            return f"rz_{'f' if formula else ''}{n}({a[0]}, {a[1]})"
        if n == "compare":
            self.uses.add("compare")
            self.reg(RT("Data", "Ordering", []))
            return f"rz_compare({a[0]}, {a[1]})"
        if n in ("checked_add", "checked_sub", "checked_mul"):
            self.uses.add("checked")
            self.reg(RT("Data", "Option", [INT]))
            return f"rz_{n}({a[0]}, {a[1]})"
        arr = self.T(e.args[0].expr.ty) if e.args[0].expr is not None else None
        if n == "concat":
            return f"{self.ct(arr)}_concat({a[0]}, {a[1]})"
        if n == "slice":
            if formula:
                return f"{self.ct(arr)}_slice({a[0]}, rz_n64({a[1]}), rz_n64({a[2]}))"
            return f"{self.ct(arr)}_slice({a[0]}, {a[1]}, {a[2]})"
        if n == "contains":
            el = arr.args[0]
            return f"{self.ct(arr)}_contains({a[0]}, {self.n64(a[1], el) if formula else a[1]})"
        if n == "filled":
            rt = self.T(e.ty)
            el = rt.args[0]
            if formula:
                return f"{self.ct(rt)}_filled(rz_n64({a[0]}), {self.n64(a[1], el)})"
            return f"{self.ct(rt)}_filled({a[0]}, {a[1]})"
        raise Unsupported(n)

    def arr_lit(self, rt, items):
        c = self.ct(rt)
        if not items:
            return f"{c}_new(0)"
        el = self.ct(rt.args[0])
        return f"{c}_from({len(items)}, ({el}[]){{{', '.join(items)}}})"

    # ------------------------------------------------------------ instancje funkcji
    def key_of(self, s):
        return tuple((k, self.mangle(v)) for k, v in sorted(s.items()))

    def fn_inst(self, decl, s):
        key = (decl.name, self.key_of(s))
        if key not in self.fn_insts:
            name = "fn_" + decl.name + ("__" + "_".join(m for _, m in key[1]) if key[1] else "")
            self.fn_insts[key] = name
            self.work.append(("fn", decl, dict(s), name))
        return self.fn_insts[key]

    def spec_inst(self, sf, s):
        key = (sf.name, self.key_of(s))
        if key not in self.spec_insts:
            name = "sp_" + sf.name + ("__" + "_".join(m for _, m in key[1]) if key[1] else "")
            self.spec_insts[key] = name
            self.work.append(("spec", sf, dict(s), name))
        return self.spec_insts[key]

    def fn_value(self, e):
        """Funkcja nazwana jako wartość: domknięcie z pustym środowiskiem i funkcją-opakowaniem."""
        sig = e.fnref
        name = self.fn_inst(sig.decl, {})
        ft = self.T(e.fty)
        fc = self.ct(ft)
        wn = "fw_" + sig.name
        if wn not in self.wrappers:
            self.wrappers.add(wn)
            ps = [f"{self.ct(pt)} a{i}" for i, (_, pt, _) in enumerate(sig.params)]
            self.protos.append(f"static {self.ct(sig.ret)} {wn}(void* _env{''.join(', ' + p for p in ps)});")
            self.defs.append(f"static {self.ct(sig.ret)} {wn}(void* _env{''.join(', ' + p for p in ps)}) {{\n"
                             f"    (void)_env;\n    return {name}({', '.join(f'a{i}' for i in range(len(ps)))});\n}}\n")
        return f"(({fc}){{NULL, {wn}}})"

    # ------------------------------------------------------------ wyrażenia kodu
    def is_mut_name(self, e):
        if isinstance(e, Name):
            try:
                return self.lookup(e.name)[1]
            except KeyError:
                return False
        return False

    def val(self, e, bind=False):
        s = self._val(e)
        if bind and e.ty is not None and self.has_arr(e.ty) and not isinstance(e, (ArrayLit, CtorCall, Call)):
            if not (isinstance(e, Name) and self.is_mut_name(e)):
                s = self.cp(s, e.ty)
        return s

    def tmpvar(self, rt, value):
        t = self.fresh()
        self.w(f"{self.ct(rt)} {t} = {value};")
        return t

    def seq(self, exprs, bind=False):
        needs = [needs_stmts(x) for x in exprs]
        out = []
        for i, x in enumerate(exprs):
            v = self.val(x, bind)
            if any(needs[i + 1:]) and not _atomic(v):
                v = self.tmpvar(x.ty, v)
            out.append(v)
        return out

    def _val(self, e):
        if isinstance(e, IntLit):
            return lit(e.value)
        if isinstance(e, BoolLit):
            return "true" if e.value else "false"
        if isinstance(e, UnitLit):
            return "0"
        if isinstance(e, Name):
            try:
                c, mut, rt = self.lookup(e.name)
            except KeyError:
                if getattr(e, "fnref", None) is not None:
                    return self.fn_value(e)
                return lit(self.ch.consts[e.name].value)
            if mut and self.has_arr(e.ty):
                return self.cp(c, e.ty)
            return c
        if isinstance(e, Hole):
            raise Unsupported("program zawiera dziurę")
        if isinstance(e, Lambda):
            return self.lambda_(e)
        if isinstance(e, Unary):
            a = self.val(e.expr)
            if e.op == "!":
                return f"(!{a})"
            if self.need(("overflow", e.span)):
                return f"rz_neg({a}, {self.loc(e.span)})"
            return f"(-{a})"
        if isinstance(e, Binary):
            op = e.op
            if op in ("&&", "||"):
                if not needs_stmts(e.right):
                    a, b = self.val(e.left), self.val(e.right)
                    return f"({a} {op} {b})"
                t = self.fresh()
                self.w(f"bool {t} = {self.val(e.left)};")
                self.w(f"if ({'' if op == '&&' else '!'}{t}) {{")
                self.ind += 1
                self.w(f"{t} = {self.val(e.right)};")
                self.ind -= 1
                self.w("}")
                return t
            a, b = self.seq([e.left, e.right])
            if op in ("+", "-", "*"):
                if self.need(("overflow", e.span)):
                    fn = {"+": "rz_add", "-": "rz_sub", "*": "rz_mul"}[op]
                    return f"{fn}({a}, {b}, {self.loc(e.span)})"
                return f"({a} {op} {b})"
            if op in ("/", "%"):
                if self.need(("div0", e.span)):
                    return f"rz_{'div' if op == '/' else 'rem'}({a}, {b}, {self.loc(e.span)})"
                return f"({a} {op} {b})"
            if op in ("==", "!="):
                r = self.eq(a, b, e.left.ty)
                return r if op == "==" else f"(!{r})"
            return f"({a} {op} {b})"
        if isinstance(e, Index):
            if self.is_mut_name(e.expr):
                a, i = self.lookup(e.expr.name)[0], self.val(e.index)
            else:
                a, i = self.seq([e.expr, e.index])
            if self.need(("bounds", e.span)):
                return f"{self.ct(e.expr.ty)}_get({a}, {i}, {self.loc(e.span)})"
            return f"({a}).d[{i}]"
        if isinstance(e, Field):
            a = self.lookup(e.expr.name)[0] if self.is_mut_name(e.expr) else self.val(e.expr)
            return self.field(a, e.expr.ty, e.name)
        if isinstance(e, ArrayLit):
            return self.arr_lit(self.T(e.ty), self.seq(e.items))
        if isinstance(e, CtorCall):
            rt = self.T(e.ty)
            args = self.seq(e.args)
            mk = f"{self.ct(rt)}_{e.name}"
            if not self.need(("data-inv", e.span)):
                return f"{mk}({', '.join(args)})"
            d = self.ch.data[rt.name]
            fields = dict(self.data_fields(rt))[e.name]
            names = [a if _atomic(a) else self.tmpvar(ft, a) for a, (_, ft) in zip(args, fields)]
            v = self.tmpvar(rt, f"{mk}({', '.join(names)})")
            conds = []
            with self.subst(dict(zip(d.tparams, rt.args))):
                raw = dict(d.rctors)[e.name]
                for (_, ft), a in zip(raw, names):
                    conds += [self.f(r, {}, selfv=a) for r in ft.refs]
                if d.where is not None:
                    conds.append(self.f(d.where, {}, selfv=v))
            self.w(f"rz_chk({' && '.join(conds) or 'true'}, \"data-inv\", {self.loc(e.span)});")
            return v
        if isinstance(e, Try):
            return self._val(e.desugared)
        if isinstance(e, Call):
            return self.call(e)
        if isinstance(e, (If, Match, BlockExpr)):
            t = self.fresh()
            self.w(f"{self.ct(e.ty)} {t} = {{0}};")
            self.valued(e, ("assign", t))
            return t
        raise Unsupported(type(e).__name__)

    def lambda_(self, e):
        """Domknięcie: funkcja na poziomie pliku + środowisko z migawką przechwyconych wartości."""
        params = {pn for pn, _ in e.params}
        captured = []
        for n in walk(e.body):
            if isinstance(n, Name) and n.name not in params and n.name not in [c[0] for c in captured]:
                try:
                    c, mut, rt = self.lookup(n.name)
                except KeyError:
                    continue
                captured.append((n.name, c, mut, rt))
        k = self.fresh("lam")
        ft = self.T(e.fty)
        fc = self.ct(ft)
        env_t = f"struct env{k}"
        fields = []
        for i, (n, c, mut, rt) in enumerate(captured):
            fields.append((f"c{i}", self.ct(rt if rt is not None else RT("Int")), n, rt, mut, c))
        # definicja funkcji domknięcia
        saved_scopes, saved_olds = self.scopes, self.olds
        with self.buffer():
            self.scopes = [{}]
            for fname, ctype, n, rt, mut, c in fields:
                self.scopes[0][n] = (f"_env->{fname}", False, rt)
            self.push_scope()
            pcs = [self.bind(pn, False, pt) for (pn, _), pt in zip(e.params, e.ptys)]
            ret_t = ft.args[-1]
            sigp = ", ".join(f"{self.ct(pt)} {pc}" for pt, pc in zip(e.ptys, pcs))
            proto = f"static {self.ct(ret_t)} {k}(void* _envp{', ' + sigp if sigp else ''})"
            self.w(proto + " {")
            self.ind += 1
            self.w(f"{env_t}* _env = _envp; (void)_env;")
            r = self.fresh("r")
            self.w(f"{self.ct(ret_t)} {r} = {{0}};")
            self.valued(e.body, ("assign", r))
            if e.ret_full is not None and e.ret_full.refs and self.need(("refine", _ref_span(e.ret_full), e.span)):
                env = dict(self.fenv())
                env.update(zip(getattr(e, "alias_pnames", ()), pcs))
                for q in e.ret_full.refs:
                    self.w(f"rz_chk({self.f(q, env, selfv=r)}, \"refine\", {self.loc(e.span)});")
            self.w(f"return {r};")
            self.ind -= 1
            self.w("}")
            body = self.buf
        self.scopes, self.olds = saved_scopes, saved_olds
        decl = env_t + " { " + " ".join(f"{ct_} {fn_};" for fn_, ct_, *_ in fields) + (" char _;" if not fields else "") + " };"
        self.protos.append(decl)
        self.protos.append(proto + ";")
        self.defs.append("\n".join(body) + "\n")
        ev = self.fresh("env")
        self.w(f"{env_t}* {ev} = rz_alloc(sizeof *{ev});")
        for fname, ctype, n, rt, mut, c in fields:
            v = self.cp(c, rt) if mut and rt is not None and self.has_arr(rt) else c
            self.w(f"{ev}->{fname} = {v};")
        clo = self.fresh("clo")
        self.w(f"{fc} {clo} = {{{ev}, {k}}};")
        return clo

    def call(self, e):
        if getattr(e, "closure", None) is not None:
            vals = self.seq([a.expr for a in e.args])
            ft = e.closure
            names = []
            for v, a, pt in zip(vals, e.args, ft.args[:-1]):
                if not _atomic(v) and any(p.refs for p in ft.args[:-1]):
                    v = self.tmpvar(a.expr.ty, v)
                names.append(v)
            penv = dict(zip(ft.pnames, names))
            for v, pt in zip(names, ft.args[:-1]):
                if pt.refs and self.need(("pre", _ref_span(pt), e.span)):
                    for q in pt.refs:
                        self.w(f"rz_chk({self.f(q, penv, selfv=v)}, \"pre\", {self.loc(e.span)});")
            c = self.lookup(e.name)[0]
            return f"({c}).f(({c}).env{''.join(', ' + n for n in names)})"
        sig = e.callee
        if getattr(getattr(sig, "decl", None), "lemma", False):
            return "0"
        vals = self.seq([a.expr for a in e.args if a.inout is None])
        if sig.builtin:
            n = e.name
            if n == "push":
                tgt = self.lookup(e.args[0].inout)[0]
                arr = self.T(self.lookup(e.args[0].inout)[2])
                if self.need(("pre", e.span, e.span)):
                    self.w(f"rz_chk(({tgt}).len < INT64_MAX, \"pre\", {self.loc(e.span)});")
                self.w(f"{self.ct(arr)}_push({self.ptr(tgt)}, {vals[0]});")
                return "0"
            if n == "pop":
                tgt = self.lookup(e.args[0].inout)[0]
                arr = self.T(self.lookup(e.args[0].inout)[2])
                self.reg(RT("Data", "Option", [arr.args[0]]))
                return self.tmpvar(e.ty, f"{self.ct(arr)}_pop({self.ptr(tgt)})")
            if n == "filled" and self.need(("pre", e.span, e.span)):
                vals = [v if _atomic(v) else self.tmpvar(a.expr.ty, v) for v, a in zip(vals, e.args)]
                self.w(f"rz_chk({vals[0]} >= 0, \"pre\", {self.loc(e.span)});")
            if n == "slice" and self.need(("pre", e.span, e.span)):
                vals = [v if _atomic(v) else self.tmpvar(a.expr.ty, v) for v, a in zip(vals, e.args)]
                self.w(f"rz_chk(0 <= {vals[1]} && {vals[1]} <= {vals[2]} && {vals[2]} <= ({vals[0]}).len, "
                       f"\"pre\", {self.loc(e.span)});")
            return self.builtin(n, vals, e)
        decl = sig.decl
        cs = {k: self.T(v) for k, v in (e.targs or {}).items()}
        cname = self.fn_inst(decl, cs)
        it = iter(vals)
        args, penv = [], {}
        need_pre = any(self.need(("pre", q.span, e.span)) for q in decl.requires) or \
            any(self.need(("pre", _ref_span(pt), e.span)) for _, pt, _ in sig.params if _all_refs(pt)) or \
            self.need(("term", e.span)) or \
            any(self.need(("pre-fn", a.span)) for a in e.args)
        for (pn, pt, pinout), a in zip(sig.params, e.args):
            if pinout:
                v = self.lookup(a.inout)[0]
            else:
                v = next(it)
                if need_pre and not _atomic(v):
                    v = self.tmpvar(a.expr.ty, v)
            args.append(v)
            penv[pn] = v
        with self.subst(cs):
            for i, ((pn, pt, pinout), v, a) in enumerate(zip(sig.params, args, e.args)):
                if pt.kind == "Fn":
                    args[i] = penv[pn] = self.fn_monitor(v, pt, a, e, cs)
                    continue
                if _all_refs(pt) and self.need(("pre", _ref_span(pt), e.span)):
                    for r in _all_refs_top(pt):
                        self.w(f"rz_chk({self.f(r, penv, selfv=v)}, \"pre\", {self.loc(e.span)});")
            for q in decl.requires:
                if self.need(("pre", q.span, e.span)):
                    self.w(f"rz_chk({self.f(q, penv)}, \"pre\", {self.loc(e.span)});")
            if self.need(("term", e.span)):
                self.w(f"rz_chk(0 <= {self.m(decl.decreases, penv)} && {self.m(decl.decreases, penv)} < _t0, "
                       f"\"term\", {self.loc(e.span)});")
        cargs = [self.ptr(v) if pinout else v for v, (_, _, pinout) in zip(args, sig.params)]
        return f"{cname}({', '.join(cargs)})"

    def fn_monitor(self, v, dst, a, e, cs):
        """Monitor kontraktu wyższego rzędu (jak w backendzie Pythona)."""
        src = getattr(a.expr, "fty", None)
        contra = src is not None and any(p.refs for p in src.args[:-1]) and self.need(("pre-fn", a.span))
        cov = bool(dst.args[-1].refs) and self.need(("pre", _ref_span(dst), e.span))
        if not (contra or cov):
            return v
        dt = self.T(dst)
        fc = self.ct(dt)
        k = self.fresh("mon")
        env_t = f"struct menv{k}"
        with self.buffer():
            xs = [self.fresh("x") for _ in dt.args[:-1]]
            sigp = ", ".join(f"{self.ct(pt)} {x}" for pt, x in zip(dt.args[:-1], xs))
            proto = f"static {self.ct(dt.args[-1])} {k}(void* _envp{', ' + sigp if sigp else ''})"
            self.w(proto + " {")
            self.ind += 1
            self.w(f"{env_t}* _env = _envp;")
            if contra:
                with self.subst(self.S_outer):
                    senv = dict(zip(src.pnames, xs))
                    for x, p in zip(xs, src.args[:-1]):
                        for q in p.refs:
                            self.w(f"rz_chk({self.f(q, senv, selfv=x)}, \"pre\", {self.loc(e.span)});")
            r = self.fresh("r")
            self.w(f"{self.ct(dt.args[-1])} {r} = _env->in.f(_env->in.env{''.join(', ' + x for x in xs)});")
            if cov:
                denv = dict(zip(dst.pnames, xs))
                for q in dst.args[-1].refs:
                    self.w(f"rz_chk({self.f(q, denv, selfv=r)}, \"pre\", {self.loc(e.span)});")
            self.w(f"return {r};")
            self.ind -= 1
            self.w("}")
            body = self.buf
        self.protos.append(f"{env_t} {{ {fc} in; }};")
        self.protos.append(proto + ";")
        self.defs.append("\n".join(body) + "\n")
        ev = self.fresh("menv")
        self.w(f"{env_t}* {ev} = rz_alloc(sizeof *{ev});")
        self.w(f"{ev}->in = {v};")
        clo = self.fresh("clo")
        self.w(f"{fc} {clo} = {{{ev}, {k}}};")
        return clo

    # ------------------------------------------------------------ wartości docelowe
    def valued(self, e, mode):
        if isinstance(e, If):
            c = self.val(e.cond)
            self.w(f"if ({c}) {{")
            self.ind += 1
            self.block(e.then, mode)
            self.ind -= 1
            if e.els is not None:
                self.w("} else {")
                self.ind += 1
                if isinstance(e.els, If):
                    self.valued(e.els, mode)
                else:
                    self.block(e.els, mode)
                self.ind -= 1
                self.w("}")
            elif mode[0] != "discard":
                self.w("} else {")
                self.ind += 1
                self.sink("0", mode)
                self.ind -= 1
                self.w("}")
            else:
                self.w("}")
            return
        if isinstance(e, Match):
            st = self.T(e.expr.ty)
            m = self.tmpvar(st, self.val(e.expr))
            guards = any(a.guard is not None for a in e.arms)
            if not guards:
                for k, arm in enumerate(e.arms):
                    conds, binds = self.pat(arm.pattern, m, st)
                    c = " && ".join(conds) or "true"
                    self.w(("if (" if k == 0 else "} else if (") + c + ") {")
                    self.ind += 1
                    self.arm(arm, binds, mode)
                    self.ind -= 1
                self.w("} else {")
                self.w(f"    rz_trap(\"unreach\", {self.loc(e.span)});")
                self.w("}")
                return
            done = self.fresh("done")
            self.w(f"bool {done} = false;")
            for arm in e.arms:
                conds, binds = self.pat(arm.pattern, m, st)
                c = " && ".join(conds) or "true"
                self.w(f"if (!{done} && {c}) {{")
                self.ind += 1
                self.push_scope()
                for k, (cx, bt) in binds.items():
                    py = self.bind(k, False, bt)
                    self.w(f"{self.ct(bt)} {py} = {cx};")
                if arm.guard is not None:
                    if needs_stmts(arm.guard):
                        raise Unsupported("strażnik wymagający instrukcji")
                    self.w(f"if ({self.val(arm.guard)}) {{")
                    self.ind += 1
                self.w(f"{done} = true;")
                self.valued_expr(arm.body, mode)
                if arm.guard is not None:
                    self.ind -= 1
                    self.w("}")
                self.pop_scope()
                self.ind -= 1
                self.w("}")
            self.w(f"if (!{done}) rz_trap(\"unreach\", {self.loc(e.span)});")
            return
        if isinstance(e, BlockExpr):
            self.w("{")
            self.ind += 1
            self.block(e.block, mode)
            self.ind -= 1
            self.w("}")
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
        for k, (cx, bt) in binds.items():
            c = self.bind(k, False, bt)
            self.w(f"{self.ct(bt)} {c} = {cx};")
        self.valued_expr(arm.body, mode)
        self.pop_scope()

    def sink(self, v, mode):
        if mode[0] == "assign":
            self.w(f"{mode[1]} = {v};")
        elif mode[0] == "discard":
            if v != "0" and not _atomic(v):
                self.w(f"(void)({v});")
        else:
            self.ret(v, mode[1])

    def ret(self, v, site):
        decl, sig = self.fn, self.fn.sig
        r = self.fresh("res")
        self.w(f"{self.ct(sig.ret)} {r} = {v};")
        env = self.fenv()
        if decl.ret is not None and _all_refs(sig.ret) and self.need(("post", decl.ret.span, site)):
            for q in _all_refs_top(sig.ret):
                self.w(f"rz_chk({self.f(q, env, selfv=r)}, \"post\", {self.loc(site)});")
        for q in decl.ensures:
            if self.need(("post", q.span, site)):
                self.w(f"rz_chk({self.f(q, env, result=r)}, \"post\", {self.loc(site)});")
        for (pn, pt, _), p in zip(sig.params, decl.params):
            if p.inout and _all_refs(pt) and self.need(("post", p.type.span, site)):
                for q in _all_refs_top(pt):
                    self.w(f"rz_chk({self.f(q, env, selfv=self.lookup(pn)[0])}, \"post\", {self.loc(site)});")
        self.w(f"return {r};")

    def fenv(self):
        env = {}
        for sc in self.scopes:
            for k, (c, mut, rt) in sc.items():
                env[k] = c
        for k, v in self.olds.items():
            env[("old", k)] = v
        return env

    def push_scope(self):
        self.scopes.append({})

    def pop_scope(self):
        self.scopes.pop()

    def refine_checks(self, rt, value, kind, key, span):
        if rt is None or not self.need(key):
            return
        env = self.fenv()
        for r in _all_refs_top(rt):
            self.w(f"rz_chk({self.f(r, env, selfv=value)}, \"{kind}\", {self.loc(span)});")
        if rt.kind == "Array" and _all_refs(rt.args[0]):
            i = self.fresh("i")
            el = f"({value}).d[{i}]"
            conds = " && ".join(self.f(r, env, selfv=el) for r in _all_refs(rt.args[0]))
            self.w(f"for (int64_t {i} = 0; {i} < ({value}).len; {i}++) rz_chk({conds}, \"{kind}\", {self.loc(span)});")

    # ------------------------------------------------------------ instrukcje
    def block(self, b: Block, mode):
        self.push_scope()
        n = len(b.stmts)
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
                self.sink("0", mode)
        self.pop_scope()

    def stmt(self, s):
        if isinstance(s, Let):
            if isinstance(s.expr, (If, Match, BlockExpr)):
                t = self.fresh()
                self.w(f"{self.ct(s.expr.ty)} {t} = {{0}};")
                self.valued(s.expr, ("assign", t))
                v = t
                if s.mutable and self.has_arr(s.rt):
                    v = self.cp(v, s.rt)
            else:
                v = self.val(s.expr, bind=s.mutable)
            c = self.bind(s.name, s.mutable, s.rt)
            self.w(f"{self.ct(s.rt)} {c} = {v};")
            if s.type is not None:
                self.refine_checks(s.rt, c, "refine", ("refine", _ref_span(s.rt), s.span), s.span)
            return
        if isinstance(s, Assign):
            c, mut, rt = self.lookup(s.name)
            if isinstance(s.expr, (If, Match, BlockExpr)):
                t = self.fresh()
                self.w(f"{self.ct(s.expr.ty)} {t} = {{0}};")
                self.valued(s.expr, ("assign", t))
                v = t
            else:
                v = self.val(s.expr, bind=True)
            if _all_refs(s.target_rt) and self.need(("refine", _ref_span(s.target_rt), s.span)):
                v = self.tmpvar(s.target_rt, v)
                self.refine_checks(s.target_rt, v, "refine", ("refine", _ref_span(s.target_rt), s.span), s.span)
            self.w(f"{c} = {v};")
            return
        if isinstance(s, IndexAssign):
            c = self.lookup(s.name)[0]
            i, v = self.seq([s.index, s.expr])
            if self.need(("bounds", s.span)):
                if not _atomic(i):
                    i = self.tmpvar(INT, i)
                self.w(f"rz_chk(0 <= {i} && {i} < ({c}).len, \"bounds\", {self.loc(s.span)});")
            el = s.target_rt.args[0]
            if _all_refs(el) and self.need(("refine", _ref_span(el), s.span)):
                v = self.tmpvar(el, v)
                self.refine_checks(el, v, "refine", ("refine", _ref_span(el), s.span), s.span)
            self.w(f"({c}).d[{i}] = {v};")
            return
        if isinstance(s, While):
            return self.while_(s)
        if isinstance(s, For):
            return self.for_(s)
        if isinstance(s, Return):
            if s.expr is None:
                self.ret("0", s.span)
            else:
                self.valued_expr(s.expr, ("return", s.span))
            return
        if isinstance(s, Break):
            self.w("break;")
            return
        if isinstance(s, Continue):
            lp = self.loops[-1]
            self.w(f"goto {lp};")
            return
        if isinstance(s, Assert):
            if self.need(("assert", s.span)):
                self.w(f"rz_chk({self.f(s.formula, self.fenv())}, \"assert\", {self.loc(s.span)});")
            return
        raise Unsupported(type(s).__name__)

    def loop_checks(self, invs, loop_span, kind):
        env = self.fenv()
        for inv in invs:
            if self.need((kind, inv.span, loop_span)):
                self.w(f"rz_chk({self.f(inv, env)}, \"{kind}\", {self.loc(inv.span)});")

    def while_(self, s: While):
        self.loop_checks(s.invariants, s.span, "inv-init")
        pres = any(self.need(("inv-pres", inv.span, s.span)) for inv in s.invariants)
        dec = s.decreases is not None and (self.need(("var-dec", s.decreases.span, s.span)) or
                                           self.need(("var-nn", s.decreases.span, s.span)))
        label = self.fresh("cont")
        if needs_stmts(s.cond):
            self.w("while (1) {")
            self.ind += 1
            c = self.val(s.cond)
            self.w(f"if (!({c})) break;")
        else:
            self.w(f"while ({self.val(s.cond)}) {{")
            self.ind += 1
        t0 = None
        if dec:
            t0 = self.fresh("v")
            self.w(f"rz_i128 {t0} = {self.m(s.decreases, self.fenv())};")
            if self.need(("var-nn", s.decreases.span, s.span)):
                self.w(f"rz_chk({t0} >= 0, \"var-nn\", {self.loc(s.decreases.span)});")
        self.loops.append(label)
        self.w("{")
        self.ind += 1
        self.block(s.body, ("discard",))
        self.ind -= 1
        self.w("}")
        self.loops.pop()
        self.w(f"{label}: ;")
        if pres:
            self.loop_checks(s.invariants, s.span, "inv-pres")
        if t0 is not None and self.need(("var-dec", s.decreases.span, s.span)):
            self.w(f"rz_chk({self.m(s.decreases, self.fenv())} < {t0}, \"var-dec\", {self.loc(s.decreases.span)});")
        self.ind -= 1
        self.w("}")

    def for_(self, s: For):
        arr_t = self.T(s.iterable.ty)
        arr = self.tmpvar(arr_t, self.val(s.iterable))
        self.push_scope()
        it = self.bind("it", False, INT)
        self.w(f"int64_t {it} = 0;")
        self.loop_checks(s.invariants, s.span, "inv-init")
        pres = any(self.need(("inv-pres", inv.span, s.span)) for inv in s.invariants)
        label = self.fresh("cont")
        self.w(f"while ({it} < ({arr}).len) {{")
        self.ind += 1
        self.push_scope()
        x = self.bind(s.var, False, arr_t.args[0])
        self.w(f"{self.ct(arr_t.args[0])} {x} = ({arr}).d[{it}];")
        self.loops.append(label)
        self.w("{")
        self.ind += 1
        self.block(s.body, ("discard",))
        self.ind -= 1
        self.w("}")
        self.loops.pop()
        self.pop_scope()
        self.w(f"{label}: ;")
        self.w(f"{it}++;")
        if pres:
            self.loop_checks(s.invariants, s.span, "inv-pres")
        self.ind -= 1
        self.w("}")
        self.pop_scope()

    # ------------------------------------------------------------ deklaracje
    def proto_of(self, f, name, s):
        with self.subst(s):
            ps = []
            for (pn, pt, pinout) in f.sig.params:
                ps.append(f"{self.ct(pt)}{'*' if pinout else ''} {'p_' if pinout else 'v_'}{pn}")
            return f"{self.ct(f.sig.ret)} {name}({', '.join(ps) or 'void'})"

    def function(self, f, s, name):
        self.fn = f
        self.S = s
        self.S_outer = s
        self.scopes = [{}]
        self.olds = {}
        self.names = set()
        self.loops = []
        sig = f.sig
        proto = self.proto_of(f, name, s)
        static = "static " if (sig.tparams or self.static_all) else ""
        self.protos.append(static + proto + ";")
        self.buf = []
        self.ind = 0
        self.w(f"/* Rdzeń: {f.name} (wiersz {f.span.line}) */")
        self.w(static + proto + " {")
        self.ind += 1
        for (pn, pt, pinout) in sig.params:
            if pinout:
                self.names.add("p_" + pn)
                self.bind(pn, True, pt, cexpr=f"(*p_{pn})")
            else:
                self.names.add("v_" + pn)
                self.bind(pn, False, pt, cexpr=f"v_{pn}")
        uses_old = any(isinstance(n, Old) for n in walk([f.ensures, f.body]))
        if uses_old:
            for (pn, pt, pinout) in sig.params:
                if pinout:
                    o = f"_old_{pn}"
                    self.w(f"{self.ct(pt)} {o} = {self.cp(self.lookup(pn)[0], pt)};")
                    self.olds[pn] = o
        if f.decreases is not None and not f.partial and any(k[0] == f.name and k[1][0] == "term" for k in self.unproved):
            self.w(f"rz_i128 _t0 = {self.m(f.decreases, self.fenv())};")
        last = f.body.stmts[-1] if f.body.stmts else None
        site = last.span if isinstance(last, ExprStmt) else f.body.span
        self.block(f.body, ("return", site))
        self.w("__builtin_unreachable();")
        self.ind -= 1
        self.w("}")
        self.defs.append("\n".join(self.buf) + "\n")
        self.fn = None

    def spec(self, sf, s, name):
        with self.subst(s):
            self.fn = None
            params = [f"{self.ct(pt)} s_{pn}" for pn, pt, _ in sf.rparams]
            env = {pn: f"s_{pn}" for pn, _, _ in sf.rparams}
            ret = self.T(sf.rret)
            body = self.n64(self.f(sf.body, env), ret)
            proto = f"static {self.ct(ret)} {name}({', '.join(params) or 'void'})"
            self.protos.append(proto + ";")
            self.defs.append(f"{proto} {{\n    return {body};\n}}\n")

    def drain(self):
        while self.work:
            kind, decl, s, name = self.work.pop(0)
            if kind == "fn":
                self.function(decl, s, name)
            else:
                self.spec(decl, s, name)

    # ------------------------------------------------------------ typy i funkcje pomocnicze
    def type_code(self):
        fwd, bodies_a, bodies_f, bodies_d, helpers, tags = [], [], [], [], [], []
        seen_tags = set()
        done = set()
        k = 0
        while k < len(self.order):         # pomocnicze funkcje mogą rejestrować nowe typy
            m = self.order[k]
            k += 1
            rt = self.types[m]
            if rt.kind == "Array":
                fwd.append(f"typedef struct {m} {m};")
                el = self.ct(rt.args[0])
                bodies_a.append(f"struct {m} {{ int64_t len, cap; {el}* d; }};")
            elif rt.kind == "Fn":
                fwd.append(f"typedef struct {m} {m};")
                args = "".join(", " + self.ct(a) for a in rt.args[:-1])
                bodies_f.append(f"struct {m} {{ void* env; {self.ct(rt.args[-1])} (*f)(void*{args}); }};")
            elif rt.kind == "Data":
                fwd.append(f"typedef struct S_{m}* {m};")
                if rt.name not in seen_tags:
                    seen_tags.add(rt.name)
                    for i, (c, _) in enumerate(self.ch.data[rt.name].rctors):
                        tags.append(f"#define TAG_{rt.name}_{c} {i}")
                members = []
                for c, fs in self.data_fields(rt):
                    if fs:
                        members.append("struct { " + " ".join(f"{self.ct(ft)} f_{cid(fn)};" for fn, ft in fs) + f" }} c_{c};")
                union = (" union { " + " ".join(members) + " } u;") if members else ""
                bodies_d.append(f"struct S_{m} {{ int tag;{union} }};")
        for m in self.order:
            helpers.append(self.helpers_for(m, self.types[m]))
        extra = []
        if "compare" in self.uses:
            o = self.ct(RT("Data", "Ordering", []))
            extra.append(f"static {o} rz_compare(rz_i128 a, rz_i128 b) {{ return a < b ? {o}_Less() : a == b ? {o}_Equal() : {o}_Greater(); }}")
        if "checked" in self.uses:
            o = self.ct(RT("Data", "Option", [INT]))
            for n, op in (("add", "+"), ("sub", "-"), ("mul", "*")):
                extra.append(f"static {o} rz_checked_{n}(rz_i128 a, rz_i128 b) {{ rz_i128 r = a {op} b; "
                             f"return (r < INT64_MIN || r > INT64_MAX) ? {o}_None() : {o}_Some((int64_t)r); }}")
        defs = "\n".join(helpers + extra).split("\n")
        protos = [l[:l.index(") {") + 1] + ";" for l in defs if l.startswith("static ") and ") {" in l]
        return "\n".join(tags + fwd + bodies_a + bodies_f + bodies_d) + "\n\n" + "\n".join(protos + defs) + "\n"

    def el_ops(self, rt):
        """(kopia, równość, wypisanie) dla wartości typu rt jako wzorce z {}."""
        k = rt.kind
        if k == "Int":
            return "{}", "({} == {})", "rz_pr_int({})"
        if k == "Bool":
            return "{}", "({} == {})", "rz_pr_bool({})"
        if k in ("Unit", "Never"):
            return "{}", "true", "rz_pr_unit({})"
        m = self.ct(rt)
        if k == "Array":
            return f"{m}_cp({{}})", f"{m}_eq({{}}, {{}})", f"{m}_pr({{}})"
        if k == "Fn":
            return "{}", "false", "fputs(\"‹funkcja›\", stdout)"
        return "{}", f"{m}_eq({{}}, {{}})", f"{m}_pr({{}})"

    def helpers_for(self, m, rt):
        out = []
        if rt.kind == "Array":
            el = rt.args[0]
            e = self.ct(el)
            cp, eq, pr = self.el_ops(el)
            out.append(f"""static {m} {m}_new(int64_t n) {{ {m} a; a.len = n; a.cap = n > 4 ? n : 4; a.d = rz_alloc(sizeof({e}) * (size_t)a.cap); return a; }}
static {m} {m}_from(int64_t n, const {e}* s) {{ {m} a = {m}_new(n); for (int64_t i = 0; i < n; i++) a.d[i] = s[i]; return a; }}
static {m} {m}_cp({m} a) {{ {m} b = {m}_new(a.len); for (int64_t i = 0; i < a.len; i++) b.d[i] = {cp.format('a.d[i]')}; return b; }}
static bool {m}_eq({m} a, {m} b) {{ if (a.len != b.len) return false; for (int64_t i = 0; i < a.len; i++) if (!{eq.format('a.d[i]', 'b.d[i]')}) return false; return true; }}
static void {m}_pr({m} a) {{ putchar('['); for (int64_t i = 0; i < a.len; i++) {{ if (i) fputs(", ", stdout); {pr.format('a.d[i]')}; }} putchar(']'); }}
static void {m}_push({m}* a, {e} v) {{ if (a->len == a->cap) {{ a->cap = a->cap * 2 + 4; {e}* d = rz_alloc(sizeof({e}) * (size_t)a->cap); if (a->len) memcpy(d, a->d, sizeof({e}) * (size_t)a->len); a->d = d; }} a->d[a->len++] = v; }}
static {m} {m}_concat({m} a, {m} b) {{ {m} r = {m}_new(a.len + b.len); for (int64_t i = 0; i < a.len; i++) r.d[i] = {cp.format('a.d[i]')}; for (int64_t i = 0; i < b.len; i++) r.d[a.len + i] = {cp.format('b.d[i]')}; return r; }}
static {m} {m}_slice({m} a, int64_t lo, int64_t hi) {{ if (lo < 0 || hi < lo || hi > a.len) rz_trap("wd", "slice"); {m} r = {m}_new(hi - lo); for (int64_t i = lo; i < hi; i++) r.d[i - lo] = {cp.format('a.d[i]')}; return r; }}
static bool {m}_contains({m} a, {e} v) {{ for (int64_t i = 0; i < a.len; i++) if ({eq.format('a.d[i]', 'v')}) return true; return false; }}
static {m} {m}_filled(int64_t n, {e} v) {{ if (n < 0) rz_trap("wd", "filled"); {m} r = {m}_new(n); for (int64_t i = 0; i < n; i++) r.d[i] = {cp.format('v')}; return r; }}
static {e} {m}_get({m} a, int64_t i, const char* loc) {{ if (i < 0 || i >= a.len) rz_trap("bounds", loc); return a.d[i]; }}
static {e} {m}_fget({m} a, rz_i128 i) {{ if (i < 0 || i >= a.len) rz_trap("wd", "formuła"); return a.d[(int64_t)i]; }}""")
            opt = self.mangle(RT("Data", "Option", [el]))
            if opt in self.types:
                out.append(f"static {opt} {m}_pop({m}* a) {{ if (a->len == 0) return {opt}_None(); "
                           f"return {opt}_Some(a->d[--a->len]); }}")
        elif rt.kind == "Data":
            fields = self.data_fields(rt)
            for c, fs in fields:
                ps = ", ".join(f"{self.ct(ft)} a{i}" for i, (_, ft) in enumerate(fs)) or "void"
                sets = " ".join(f"v->u.c_{c}.f_{cid(fn)} = a{i};" for i, (fn, _) in enumerate(fs))
                out.append(f"static {m} {m}_{c}({ps}) {{ {m} v = rz_alloc(sizeof *v); v->tag = TAG_{rt.name}_{c}; {sets} return v; }}")
            eqs, prs, ranks = [], [], []
            for c, fs in fields:
                conds = []
                prints = [f"fputs({cstr(c)}, stdout);"]
                rk = []
                if fs:
                    prints.append("putchar('(');")
                for i, (fn, ft) in enumerate(fs):
                    _, eq, pr = self.el_ops(ft)
                    a, b = f"a->u.c_{c}.f_{cid(fn)}", f"b->u.c_{c}.f_{cid(fn)}"
                    conds.append(eq.format(a, b))
                    if i:
                        prints.append("fputs(\", \", stdout);")
                    prints.append(pr.format(a) + ";")
                    if self.mangle(ft) == m:
                        rk.append(f"{m}_rank({a})")
                if fs:
                    prints.append("putchar(')');")
                eqs.append(f"case TAG_{rt.name}_{c}: return {' && '.join(conds) or 'true'};")
                prs.append(f"case TAG_{rt.name}_{c}: {' '.join(prints)} break;")
                ranks.append(f"case TAG_{rt.name}_{c}: return 1{''.join(' + ' + x for x in rk)};")
            out.append(f"static bool {m}_eq({m} a, {m} b) {{ if (a->tag != b->tag) return false; switch (a->tag) {{ {' '.join(eqs)} }} return true; }}")
            out.append(f"static void {m}_pr({m} a) {{ switch (a->tag) {{ {' '.join(prs)} }} }}")
            out.append(f"static rz_i128 {m}_rank({m} a) {{ switch (a->tag) {{ {' '.join(ranks)} }} return 1; }}")
        return "\n".join(out)

    # ------------------------------------------------------------ program
    def program(self, harness=None, static_all=False):
        self.static_all = static_all
        for f in self.ch.user_fns:
            if not f.lemma and not f.sig.tparams:
                self.fn_inst(f, {})
        self.drain()
        main = []
        if harness is not None:
            main = self.harness(harness)
            self.drain()
        types = self.type_code()          # rejestruje też typy pomocnicze — ostatnie
        head = [f"/* Moduł wygenerowany przez rzc z programu w języku Rdzeń ({self.file}). Nie edytować ręcznie. */",
                RUNTIME]
        return "\n".join(head + [types] + self.protos + [""] + self.defs + main) + "\n"

    # ------------------------------------------------------------ harness testów różnicowych
    def cval(self, v, rt):
        from .interp import Ctor, UnitV
        rt = self.T(rt)
        if rt.kind == "Int":
            return lit(v)
        if rt.kind == "Bool":
            return "true" if v else "false"
        if rt.kind in ("Unit", "Never"):
            return "0"
        if rt.kind == "Array":
            return self.arr_lit(rt, [self.cval(x, rt.args[0]) for x in v])
        if rt.kind == "Data":
            fields = dict(self.data_fields(rt))[v.name]
            return f"{self.ct(rt)}_{v.name}(" + ", ".join(self.cval(x, ft) for x, (_, ft) in zip(v.fields, fields)) + ")"
        raise Unsupported(f"wartość typu {rt}")

    def harness(self, cases):
        """cases: [(decl, mapa typów, [wartości])] → funkcja main wypisująca wynik każdego przypadku."""
        lines = ["int main(void) {", "    setvbuf(stdout, NULL, _IOFBF, 1 << 16);"]
        for decl, s, vals in cases:
            name = self.fn_inst(decl, s)
            with self.subst(s):
                sig = decl.sig
                lines.append("    {")
                lines.append("        jmp_buf jb; rz_jb = &jb;")
                lines.append("        if (setjmp(jb) == 0) {")
                args = []
                outs = []
                for i, ((pn, pt, pinout), v) in enumerate(zip(sig.params, vals)):
                    lines.append(f"            {self.ct(pt)} a{i} = {self.cval(v, pt)};")
                    args.append(f"&a{i}" if pinout else f"a{i}")
                    if pinout:
                        outs.append((f"a{i}", pt))
                lines.append(f"            {self.ct(sig.ret)} r = {name}({', '.join(args)});")
                _, _, pr = self.el_ops(self.T(sig.ret))
                lines.append(f"            fputs(\"R \", stdout); {pr.format('r')};")
                for a, pt in outs:
                    _, _, pr = self.el_ops(self.T(pt))
                    lines.append(f"            fputs(\" | \", stdout); {pr.format(a)};")
                lines.append("            putchar('\\n');")
                lines.append("        } else {")
                lines.append("            printf(\"T %s\\n\", rz_trap_kind);")
                lines.append("        }")
                lines.append("        rz_jb = NULL;")
                lines.append("    }")
        lines.append("    return 0;")
        lines.append("}")
        return ["\n".join(lines)]


def _atomic(v: str) -> bool:
    return v.replace("_", "").replace("->", "").replace(".", "").isalnum() and not v[0].isdigit() \
        or v in ("0", "true", "false") or v.rstrip("L").lstrip("-").isdigit() or v == "INT64_MIN" \
        or (v.startswith("(-") and v.endswith("LL)"))


def emit_c(res, file="program.rz", harness=None) -> str:
    if res.checker is None:
        raise Unsupported("program nie przeszedł weryfikacji")
    return CEmitter(res.checker, res.unproved, file).program(harness, static_all=harness is not None)
