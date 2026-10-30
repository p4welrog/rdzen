# SPDX-License-Identifier: MIT OR Apache-2.0
"""Zestaw A: zadania poziomów 1–4 VeraBench (aallan/vera-bench, MIT) przeniesione do Rdzenia.

Opisy neutralne i przypadki testowe pochodzą z `dane/verabench_t1_t4.json` (licencja MIT,
`LICENSE-VeraBench`). Zmiany względem VeraBench:
- każde zadanie ma jawną dziedzinę wejść (Rdzeń ma Int 64-bitowy, a testy ukryte wykraczają
  poza 3–5 przykładów VeraBench);
- typy danych (lista, drzewo, wyrażenie) są podane w treści zamiast definiowane przez model,
  żeby wynik dało się ocenić bez heurystycznego odczytu typów;
- poziom 5 (efekty IO/State/Exn) pominięto — Rdzeń nie ma efektów.
"""
from __future__ import annotations

import json
import os

from .zadania import Dane, zadanie

_SRC = json.load(open(os.path.join(os.path.dirname(__file__), "dane", "verabench_t1_t4.json"), encoding="utf-8"))
_BY_ID = {p["id"]: p for p in _SRC["zadania"]}

LISTA = Dane("IntList", [("Nil", []), ("Cons", [("head", "Int"), ("tail", "IntList")])], "lista")
DRZEWO = Dane("Tree", [("Leaf", [("value", "Int")]), ("Branch", [("left", "Tree"), ("right", "Tree")])], "znaczniki")
WYRAZENIE = Dane("Expr", [("Lit", [("value", "Int")]), ("Add", [("left", "Expr"), ("right", "Expr")]),
                          ("Neg", [("inner", "Expr")])], "znaczniki")


def _neutral(v):
    """Wartość w formie VeraBench (JSON) → wartość neutralna."""
    if isinstance(v, dict):
        (c, args), = v.items()
        if c == "None":
            return None
        if c == "Some":
            return _neutral(args[0])
        return (c, *[_neutral(a) for a in args])
    if isinstance(v, list):
        return [_neutral(x) for x in v]
    return v


def _exp(v, wynik):
    if wynik == "Bool":
        if v in ("true", "false"):
            return v == "true"
        return bool(v)
    return _neutral(v)


def vb(vid, funkcja, parametry, wynik, wyrocznia, generator, dziedzina, brzegowe=(), opis=None, dane=(), tagi=()):
    p = _BY_ID[vid]
    testy = [(tuple(_neutral(a) for a in tc["args"]), _exp(tc["expected"], wynik)) for tc in p["test_cases"]]
    return zadanie(id="A-" + vid[3:], tytul=p["title"], opis=opis or p["description_neutral"], funkcja=funkcja,
                   parametry=list(parametry), wynik=wynik, wyrocznia=wyrocznia, generator=generator,
                   brzegowe=list(brzegowe), dziedzina=dziedzina, dane=list(dane), zrodlo=f"VeraBench {vid}",
                   testy_zrodla=testy, tagi=[f"poziom{p['tier']}", *tagi])


# ---------- generatory ----------
E9 = 10**9


def ri(r, lo=-E9, hi=E9):
    # połowa przypadków z małego zakresu (więcej równości i zer)
    return r.randint(-20, 20) if r.random() < 0.5 and lo <= -20 and hi >= 20 else r.randint(lo, hi)


def rarr(r, n=30, lo=-E9, hi=E9):
    return [ri(r, lo, hi) for _ in range(r.randint(0, n))]


ASCII = "".join(chr(c) for c in range(32, 127))


def rstr(r, n=20, alfabet=None):
    a = alfabet or (ASCII if r.random() < 0.5 else "abcab")
    return "".join(r.choice(a) for _ in range(r.randint(0, n)))


def rtree(r, d=0):
    if d > 6 or r.random() < 0.35:
        return ("Leaf", ri(r, -1000, 1000))
    return ("Branch", rtree(r, d + 1), rtree(r, d + 1))


def rexpr(r, d=0):
    x = r.random()
    if d > 6 or x < 0.35:
        return ("Lit", ri(r, -1000, 1000))
    if x < 0.7:
        return ("Add", rexpr(r, d + 1), rexpr(r, d + 1))
    return ("Neg", rexpr(r, d + 1))


def tdepth(t):
    return 1 if t[0] == "Leaf" else 1 + max(tdepth(t[1]), tdepth(t[2]))


def tsum(t):
    return t[1] if t[0] == "Leaf" else tsum(t[1]) + tsum(t[2])


def tleaves(t):
    return 1 if t[0] == "Leaf" else tleaves(t[1]) + tleaves(t[2])


def eexpr(e):
    return e[1] if e[0] == "Lit" else eexpr(e[1]) + eexpr(e[2]) if e[0] == "Add" else -eexpr(e[1])


def tdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def gcd(a, b):
    while b:
        a, b = b, a % b
    return a


D_INT = "All integers are in the range [-10^9, 10^9]."
D_LIST = "Lists have at most 50 elements; all integers are in the range [-10^9, 10^9]."
D_STR = "Strings consist of printable ASCII characters (codes 32–126) and have at most 100 characters."

# ---------- poziom 1 ----------
vb("VB-T1-001", "absolute_value", [("x", "Int")], "Nat", abs, lambda r: (ri(r),), D_INT, [(-E9,), (E9,)])
vb("VB-T1-002", "clamp_to_range", [("value", "Int"), ("lo", "Int"), ("hi", "Int")], "Int",
   lambda v, lo, hi: max(lo, min(hi, v)),
   lambda r: (lambda a, b: (ri(r), min(a, b), max(a, b)))(ri(r), ri(r)),
   D_INT + " lo <= hi.", [(5, 5, 5), (-E9, E9, E9), (E9, -E9, -E9)])
vb("VB-T1-003", "signum", [("x", "Int")], "Int", lambda x: (x > 0) - (x < 0), lambda r: (ri(r),), D_INT)
vb("VB-T1-004", "max_of_two", [("a", "Int"), ("b", "Int")], "Int", max, lambda r: (ri(r), ri(r)), D_INT)
vb("VB-T1-005", "min_of_two", [("a", "Int"), ("b", "Int")], "Int", min, lambda r: (ri(r), ri(r)), D_INT)
vb("VB-T1-006", "is_positive", [("x", "Int")], "Bool", lambda x: x > 0, lambda r: (ri(r),), D_INT)
vb("VB-T1-007", "safe_modulo", [("a", "Int"), ("b", "Int")], "Int", lambda a, b: a % b,
   lambda r: (ri(r, 0, E9), ri(r, 1, E9)), "Integers satisfy 0 <= a <= 10^9 and 1 <= b <= 10^9.",
   [(0, 1), (E9, 1), (E9, E9), (E9 - 1, E9)])
vb("VB-T1-008", "distance", [("a", "Int"), ("b", "Int")], "Nat", lambda a, b: abs(a - b),
   lambda r: (ri(r), ri(r)), D_INT, [(-E9, E9), (E9, -E9)])
vb("VB-T1-009", "max_of_three", [("a", "Int"), ("b", "Int"), ("c", "Int")], "Int", lambda a, b, c: max(a, b, c),
   lambda r: (ri(r), ri(r), ri(r)), D_INT, [(1, 3, 2), (3, 1, 2), (1, 2, 3), (2, 2, 1)])
vb("VB-T1-010", "double_or_nothing", [("x", "Int")], "Int", lambda x: 2 * x if x > 0 else 0,
   lambda r: (ri(r),), D_INT, [(E9,), (-E9,)])

# ---------- poziom 2 ----------
vb("VB-T2-001", "sum_array", [("xs", "Array<Int>")], "Int", sum, lambda r: (rarr(r),),
   "Arrays have at most 1000 elements; all integers are in the range [-10^9, 10^9].",
   [([E9] * 1000,), ([-E9] * 1000,)], opis="Sum all elements of an integer array.")
vb("VB-T2-002", "filter_positives", [("xs", "Array<Int>")], "Array<Int>", lambda xs: [x for x in xs if x > 0],
   lambda r: (rarr(r),), "Arrays have at most 1000 elements; all integers are in the range [-10^9, 10^9].",
   opis="Return a new array containing only the positive elements of an integer array, in their original order.")
vb("VB-T2-003", "greet", [("name", "Str")], "Str", lambda s: f"Hello, {s}!",
   lambda r: (rstr(r) or "x",), D_STR + " The name is non-empty.", [("a" * 100,)])
vb("VB-T2-004", "is_empty_string", [("s", "Str")], "Bool", lambda s: len(s) == 0, lambda r: (rstr(r, 3),), D_STR)
vb("VB-T2-005", "contains_substring", [("haystack", "Str"), ("needle", "Str")], "Bool", lambda h, n: n in h,
   lambda r: (lambda h: (h, h[r.randint(0, len(h)):][: r.randint(0, 4)] if r.random() < 0.5 else rstr(r, 3, "abc")))(
       rstr(r, 30, "abc")), D_STR, [("aaab", "aab"), ("ab", "abc"), ("", ""), ("abab", "bab")])
vb("VB-T2-006", "join_strings", [("parts", "Array<Str>"), ("sep", "Str")], "Str", lambda ps, s: s.join(ps),
   lambda r: ([rstr(r, 5) for _ in range(r.randint(0, 6))], rstr(r, 3)),
   D_STR + " The array has at most 20 elements.", [([""], ","), (["", ""], ",")])
vb("VB-T2-007", "double_elements", [("xs", "Array<Int>")], "Array<Int>", lambda xs: [2 * x for x in xs],
   lambda r: (rarr(r),), "Arrays have at most 1000 elements; all integers are in the range [-10^9, 10^9].",
   [([E9, -E9],)], opis="Double every element of an integer array.")
vb("VB-T2-008", "count_positives", [("xs", "Array<Int>")], "Nat", lambda xs: sum(1 for x in xs if x > 0),
   lambda r: (rarr(r),), "Arrays have at most 1000 elements; all integers are in the range [-10^9, 10^9].",
   opis="Count how many positive elements an integer array has.")
vb("VB-T2-009", "to_upper", [("s", "Str")], "Str", lambda s: "".join(c.upper() if "a" <= c <= "z" else c for c in s),
   lambda r: (rstr(r, 30, ASCII),), D_STR, [("az{`@[",)])
vb("VB-T2-010", "sum_positives", [("xs", "Array<Int>")], "Int", lambda xs: sum(x for x in xs if x > 0),
   lambda r: (rarr(r),), "Arrays have at most 1000 elements; all integers are in the range [-10^9, 10^9].",
   [([E9] * 1000,)], opis="Sum only the positive elements of an integer array.")
vb("VB-T2-011", "starts_with_prefix", [("s", "Str"), ("prefix", "Str")], "Bool", lambda s, p: s.startswith(p),
   lambda r: (lambda s: (s, s[: r.randint(0, len(s))] if r.random() < 0.5 else rstr(r, 4, "ab")))(rstr(r, 10, "ab")),
   D_STR)
vb("VB-T2-012", "ends_with_suffix", [("s", "Str"), ("suffix", "Str")], "Bool", lambda s, p: s.endswith(p),
   lambda r: (lambda s: (s, s[r.randint(0, len(s)):] if r.random() < 0.5 else rstr(r, 4, "ab")))(rstr(r, 10, "ab")),
   D_STR)
vb("VB-T2-013", "get_char_code", [("s", "Str"), ("i", "Int")], "Nat", lambda s, i: ord(s[i]),
   lambda r: (lambda s: (s, r.randint(0, len(s) - 1)))(rstr(r) or "q"),
   D_STR + " 0 <= i < length of s.", [(" ", 0), ("~", 0)])
vb("VB-T2-014", "combined_length", [("a", "Str"), ("b", "Str")], "Nat", lambda a, b: len(a) + len(b),
   lambda r: (rstr(r), rstr(r)), D_STR)
vb("VB-T2-015", "is_longer_than", [("s", "Str"), ("n", "Nat")], "Bool", lambda s, n: len(s) > n,
   lambda r: (rstr(r), r.randint(0, 25)), D_STR + " 0 <= n <= 10^9.", [("", E9)])

# ---------- poziom 3 ----------
DL = "Lists have at most 50 elements; all integers are in the range [-10^9, 10^9]."
DT = "Trees have at most 200 nodes; all integers are in the range [-1000, 1000]."
rl = lambda r: [ri(r) for _ in range(r.randint(0, 12))]  # noqa: E731

vb("VB-T3-001", "list_length", [("xs", "IntList")], "Nat", len, lambda r: (rl(r),), DL, dane=[LISTA],
   opis="Using the provided linked list type, write a function that computes the length of a list.")
vb("VB-T3-002", "tree_depth", [("t", "Tree")], "Nat", tdepth, lambda r: (rtree(r),), DT, dane=[DRZEWO],
   opis="Using the provided binary tree type, write a function that computes the depth of a tree. A leaf has depth 1.")
vb("VB-T3-003", "eval_expr", [("e", "Expr")], "Int", eexpr, lambda r: (rexpr(r),),
   "Expressions have at most 200 nodes; literals are in the range [-1000, 1000].", dane=[WYRAZENIE],
   opis="Using the provided expression type (literal, addition, negation), write a function that evaluates "
        "an expression to an integer.")
vb("VB-T3-004", "list_sum", [("xs", "IntList")], "Int", sum, lambda r: (rl(r),), DL, dane=[LISTA],
   opis="Using the provided linked list type, write a function that sums all elements of a list.")
vb("VB-T3-005", "tree_sum", [("t", "Tree")], "Int", tsum, lambda r: (rtree(r),), DT, dane=[DRZEWO],
   opis="Using the provided binary tree type, write a function that sums all leaf values.")
vb("VB-T3-006", "option_unwrap_or", [("opt", "Option<Int>"), ("default", "Int")], "Int",
   lambda o, d: d if o is None else o, lambda r: (None if r.random() < 0.4 else ri(r), ri(r)), D_INT,
   opis="Unwrap an optional integer, returning the contained value or the given default.")
vb("VB-T3-007", "list_contains", [("xs", "IntList"), ("target", "Int")], "Bool", lambda xs, t: t in xs,
   lambda r: (lambda xs: (xs, r.choice(xs) if xs and r.random() < 0.5 else ri(r, -20, 20)))(
       [ri(r, -20, 20) for _ in range(r.randint(0, 10))]), DL, dane=[LISTA],
   opis="Using the provided linked list type, write a function that returns true if the list contains a given "
        "target integer.")
vb("VB-T3-008", "tree_count_leaves", [("t", "Tree")], "Nat", tleaves, lambda r: (rtree(r),), DT, dane=[DRZEWO],
   opis="Using the provided binary tree type, write a function that counts the number of leaves. The result is "
        "always at least 1.")
vb("VB-T3-009", "list_append", [("xs", "IntList"), ("ys", "IntList")], "IntList", lambda a, b: a + b,
   lambda r: (rl(r), rl(r)), DL, dane=[LISTA],
   opis="Using the provided linked list type, write a function that concatenates two lists.")
vb("VB-T3-010", "list_last", [("xs", "IntList")], "Option<Int>", lambda xs: xs[-1] if xs else None,
   lambda r: (rl(r),), DL, dane=[LISTA],
   opis="Using the provided linked list type, write a function that returns the last element of the list, or "
        "none if the list is empty.")
vb("VB-T3-011", "safe_divide", [("a", "Int"), ("b", "Int")], "Int", lambda a, b: -1 if b == 0 else tdiv(a, b),
   lambda r: (lambda b: ((ri(r, 0, E9), b) if b >= 0 else (ri(r, 0, E9), b)))(r.choice([0, ri(r, 0, E9), ri(r, 0, 10)])),
   "All integers are in the range [-10^9, 10^9]; when b != 0 and the division is not exact, a >= 0 and b > 0.",
   [(0, 0), (E9, 1), (E9, 0)])
vb("VB-T3-012", "pair_sum", [("a", "Int"), ("b", "Int")], "Int", lambda a, b: a + b, lambda r: (ri(r), ri(r)), D_INT,
   [(E9, E9), (-E9, -E9)])
vb("VB-T3-013", "classify_sign", [("x", "Int")], "Int", lambda x: (x > 0) - (x < 0), lambda r: (ri(r),), D_INT)
vb("VB-T3-014", "color_code", [("code", "Int")], "Int", lambda c: {0: 16711680, 1: 65280, 2: 255}.get(c, 0),
   lambda r: (ri(r, -3, 5) if r.random() < 0.8 else ri(r),), D_INT)
vb("VB-T3-015", "either_select", [("a", "Int"), ("b", "Int"), ("selector", "Int")], "Int",
   lambda a, b, s: a if s > 0 else b, lambda r: (ri(r), ri(r), ri(r, -2, 2)), D_INT)

# ---------- poziom 4 ----------
vb("VB-T4-001", "fibonacci", [("n", "Nat")], "Nat", fib, lambda r: (r.randint(0, 25),), "0 <= n <= 25.", [(25,)])
vb("VB-T4-002", "gcd", [("a", "Nat"), ("b", "Nat")], "Nat", gcd, lambda r: (ri(r, 0, E9), ri(r, 0, E9)),
   "0 <= a, b <= 10^9.", [(0, 0), (E9, E9), (1, E9), (E9, 0)])
vb("VB-T4-003", "is_even", [("n", "Nat")], "Bool", lambda n: n % 2 == 0, lambda r: (r.randint(0, 300),),
   "0 <= n <= 300.", [(300,), (299,)])
vb("VB-T4-004", "power", [("base", "Nat"), ("exp", "Nat")], "Nat", pow,
   lambda r: (lambda b: (b, r.randint(0, {0: 100, 1: 100, 2: 59, 3: 37}.get(b, 18))))(r.randint(0, 10)),
   "0 <= base <= 10 and 0 <= exp <= 100, and the result is at most 10^18.", [(0, 0), (10, 18), (2, 59), (1, 100), (0, 100)])
vb("VB-T4-005", "sum_to_n", [("n", "Nat")], "Nat", lambda n: n * (n + 1) // 2, lambda r: (r.randint(0, 300),),
   "0 <= n <= 300.", [(300,)])
vb("VB-T4-006", "list_reverse", [("xs", "IntList")], "IntList", lambda xs: xs[::-1], lambda r: (rl(r),), DL,
   dane=[LISTA], opis="Using the provided linked list type, write a function that reverses a list.")
vb("VB-T4-007", "count_digits", [("n", "Nat")], "Nat", lambda n: len(str(n)),
   lambda r: (r.choice([r.randint(0, 99), r.randint(0, 10**18), 10 ** r.randint(0, 18), 10 ** r.randint(1, 18) - 1]),),
   "0 <= n <= 10^18.", [(10**18,), (10**18 - 1,), (9,), (10,)])
vb("VB-T4-008", "multiply", [("a", "Nat"), ("b", "Nat")], "Nat", lambda a, b: a * b,
   lambda r: (ri(r, 0, E9), r.randint(0, 300)), "0 <= a <= 10^9 and 0 <= b <= 300.", [(E9, 300)])
vb("VB-T4-009", "list_nth", [("xs", "IntList"), ("n", "Nat")], "Int", lambda xs, n: xs[n] if n < len(xs) else -1,
   lambda r: (lambda xs: (xs, r.randint(0, len(xs) + 2)))(rl(r)), DL + " 0 <= n <= 10^9.", [([], E9)], dane=[LISTA],
   opis="Using the provided linked list type, write a function that returns the n-th element (0-indexed), or -1 if "
        "the index is out of bounds.")
vb("VB-T4-010", "div_natural", [("a", "Nat"), ("b", "Nat")], "Nat", lambda a, b: a // b,
   lambda r: (r.randint(0, 300), r.randint(1, 50)), "0 <= a <= 300 and 1 <= b <= 300.", [(300, 1), (0, 300)])
