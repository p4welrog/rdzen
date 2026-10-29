# SPDX-License-Identifier: MIT OR Apache-2.0
"""Kodowanie typów i wartości Rdzenia w Z3 (sorty logiki F, §6.1)."""
from __future__ import annotations
import z3
from .check import RT, subst_rt
from .diag import err

INT_MIN, INT_MAX = -2**63, 2**63 - 1


class Enc:
    def __init__(self, checker):
        self.ch = checker
        self.sorts = {}         # shape -> sort
        self.dts = {}           # shape -> (datatype sort, data decl, args)
        self.unit_sort = None
        self.defaults = {}
        self.counter = 0

    # ---------- sorty ----------
    def sort(self, rt: RT):
        key = rt.bare().shape()
        if key in self.sorts:
            return self.sorts[key]
        k = rt.kind
        if k == "Int":
            s = z3.IntSort()
        elif k == "Bool":
            s = z3.BoolSort()
        elif k == "Unit":
            dt = z3.Datatype("Unit")
            dt.declare("unit")
            s = dt.create()
            self.unit_sort = s
        elif k == "Var":
            s = z3.DeclareSort("T_" + rt.name)
        elif k == "Array":
            el = self.sort(rt.args[0])
            dt = z3.Datatype(f"Arr[{rt.args[0]}]")
            dt.declare("mk", ("len", z3.IntSort()), ("data", z3.ArraySort(z3.IntSort(), el)))
            s = dt.create()
        elif k == "Data":
            s = self._data_sort(rt)
        elif k == "Fn":
            s = z3.ArraySort(*[self.sort(a) for a in rt.args])
        else:
            raise ValueError(f"brak sortu dla {rt}")
        self.sorts[key] = s
        return s

    def _data_sort(self, rt: RT):
        d = self.ch.data[rt.name]
        subst = dict(zip(d.tparams, rt.args))
        name = str(rt.bare())
        dt = z3.Datatype(name)
        key = rt.bare().shape()
        for cname, fields in d.rctors:
            fs = []
            for fname, ft in fields:
                ft2 = subst_rt(ft, subst).bare()
                if ft2.shape() == key:
                    fs.append((f"{cname}.{fname}", dt))
                else:
                    if _mentions(ft2, key):
                        raise err("E2050", d.span, f"typ `{name}`: rekursja przez tablicę lub inny typ nie jest obsługiwana w prototypie", ["3.4"])
                    fs.append((f"{cname}.{fname}", self.sort(ft2)))
            dt.declare(cname, *fs)
        s = dt.create()
        self.dts[key] = (s, d, rt.args)
        return s

    def unit(self):
        s = self.sort(RT("Unit"))
        return s.constructor(0)()

    def default(self, sort):
        k = sort.sexpr()
        if k not in self.defaults:
            self.defaults[k] = z3.Const(f"dflt!{len(self.defaults)}", sort)
        return self.defaults[k]

    # ---------- tablice ----------
    def arr_len(self, a):
        return a.sort().accessor(0, 0)(a)

    def arr_data(self, a):
        return a.sort().accessor(0, 1)(a)

    def mk_arr(self, sort, ln, data):
        return sort.constructor(0)(ln, data)

    def arr_lit(self, rt: RT, items):
        s = self.sort(rt)
        el = self.sort(rt.args[0])
        data = z3.K(z3.IntSort(), self.default(el))
        for i, v in enumerate(items):
            data = z3.Store(data, i, v)
        return self.mk_arr(s, z3.IntVal(len(items)), data)

    def arr_eq(self, a, b):
        k = z3.FreshInt("k")
        return z3.And(self.arr_len(a) == self.arr_len(b),
                      z3.ForAll([k], z3.Implies(z3.And(0 <= k, k < self.arr_len(a)),
                                                z3.Select(self.arr_data(a), k) == z3.Select(self.arr_data(b), k))))

    # ---------- dane ----------
    def ctor(self, rt: RT, cname):
        s = self.sort(rt)
        for i in range(s.num_constructors()):
            if s.constructor(i).name() == cname:
                return s, i
        raise KeyError(cname)

    def mk_ctor(self, rt: RT, cname, args):
        s, i = self.ctor(rt, cname)
        return s.constructor(i)(*args)

    def is_ctor(self, rt: RT, cname, v):
        s, i = self.ctor(rt, cname)
        return s.recognizer(i)(v)

    def field(self, rt: RT, cname, j, v):
        s, i = self.ctor(rt, cname)
        return s.accessor(i, j)(v)

    # ---------- hipotezy typów h(x, τ) (§6.3) ----------
    def hyp(self, v, rt: RT, refine_fn, depth=0, refs_only=False):
        """Zwraca listę formuł h(v, τ). refine_fn(formula_ast, self_term) -> z3 term.
        refs_only=True pomija zakresy Int i długości tablic (tylko uściślenia)."""
        out = []
        k = rt.kind
        if k == "Int":
            if not refs_only:
                out.append(z3.And(v >= INT_MIN, v <= INT_MAX))
        elif k == "Array" and depth < 2:
            ln = self.arr_len(v)
            if not refs_only:
                out.append(z3.And(ln >= 0, ln <= INT_MAX))
            j = z3.FreshInt("k")
            inner = self.hyp(z3.Select(self.arr_data(v), j), rt.args[0], refine_fn, depth + 1, refs_only)
            if inner:
                out.append(z3.ForAll([j], z3.Implies(z3.And(0 <= j, j < ln), z3.And(*inner))))
        elif k == "Fn":
            t = self.fn_hyp_fn(v, rt) if getattr(self, "fn_hyp_fn", None) else None
            if t is not None:
                out.append(t)
        elif k == "Data" and depth < 2:
            d = self.ch.data[rt.name]
            subst = dict(zip(d.tparams, rt.args))
            key = rt.bare().shape()
            for cname, fields in d.rctors:
                conds = []
                for j, (fname, ft) in enumerate(fields):
                    ft2 = subst_rt(ft, subst)
                    if ft2.bare().shape() == key:
                        continue
                    conds += self.hyp(self.field(rt, cname, j, v), ft2, refine_fn, depth + 1, refs_only)
                if conds:
                    out.append(z3.Implies(self.is_ctor(rt, cname, v), z3.And(*conds)))
            # niezmiennik typu danych (§6.3): hipoteza, nie zobowiązanie
            if not refs_only and d.where is not None and getattr(self, "inv_fn", None):
                out.append(self.inv_fn(rt, v))
        for r in rt.refs:
            out.append(refine_fn(r, v))
        return out

    def fresh(self, name, rt: RT):
        self.counter += 1
        return z3.Const(f"{name}@{self.counter}", self.sort(rt))


def _mentions(rt: RT, key) -> bool:
    if rt.shape() == key:
        return True
    return any(_mentions(a, key) for a in rt.args)


def tdiv(a, b):
    """Dzielenie obcinane w stronę zera (§2.6) wyrażone przez div z SMT-LIB."""
    return z3.If(a >= 0, a / b, -((-a) / b))


def trem(a, b):
    return a - b * tdiv(a, b)
