# SPDX-License-Identifier: MIT OR Apache-2.0
"""Analiza kodu widmowego (używanego tylko w dowodzie) na potrzeby generatorów kodu.

Lematy, udowodnione asercje, niezmienniki pętli i warunki końcowe bez sprawdzeń dynamicznych
są wymazywane z kodu wynikowego. Zmienne czytane wyłącznie tam (typowo kopie stanu do lematów
ramy: `let old_xs = xs`) nie muszą istnieć w czasie wykonania — ich kopiowanie jest martwym
kosztem O(n) w każdym obrocie pętli."""
from __future__ import annotations
from .ast import (Node, Assert, Call, Old, Name, Arg, While, For, Let, Field, IntLit, BoolLit, Try, NON_CHILD)


def runtime_names(f, unproved, need):
    """(nazwy czytane przez kod wykonywalny, czy `old(..)` jest tam użyte).

    `need(key)` — czy zobowiązanie `key` bieżącej funkcji pozostaje sprawdzeniem dynamicznym."""
    keys = {k[1][0] for k in unproved if k[0] == f.name}
    loops_rt = bool(keys & {"inv-init", "inv-pres", "var-dec", "var-nn"})
    names, olds = set(), [False]

    def go(n):
        if isinstance(n, (list, tuple)):
            for x in n:
                go(x)
            return
        if not isinstance(n, Node):
            return
        if isinstance(n, Assert) and not need(("assert", n.span)):
            return
        if isinstance(n, Call) and getattr(getattr(n.callee, "decl", None), "lemma", False):
            return
        if isinstance(n, Old):
            olds[0] = True
        if isinstance(n, Try) and n.desugared is not None:
            go(n.desugared)        # `?` jest emitowane jako swoje rozwinięcie do `match`
        if isinstance(n, Name):
            names.add(n.name)
        if isinstance(n, Arg) and n.inout:
            names.add(n.inout)
        for k, v in vars(n).items():
            if k in NON_CHILD:
                continue
            if isinstance(n, (While, For)) and k in ("invariants", "decreases") and not loops_rt:
                continue
            if isinstance(v, (Node, list, tuple)):
                go(v)

    go(f.body)
    if "post" in keys:
        go(f.ensures)
    return names, olds[0]


def erasable_let(s, rt_names) -> bool:
    """`let x = y` (kopia zmiennej, bez adnotacji typu), gdy `x` nie jest czytane w czasie wykonania.
    Tylko `let`: zmienna `var` może być potem zapisywana (`x = …`, `x[i] = …`), a zapis wymaga
    istniejącej zmiennej w kodzie wynikowym."""
    return (isinstance(s, Let) and not s.mutable and s.type is None and _pure(s.expr) and
            rt_names is not None and s.name not in rt_names)


def _pure(e) -> bool:
    """Wyrażenie bez efektów i bez możliwej pułapki: zmienna, literał, pole (także `.len`)."""
    if isinstance(e, (Name, IntLit, BoolLit)):
        return True
    if isinstance(e, Field):
        return _pure(e.expr)
    return False
