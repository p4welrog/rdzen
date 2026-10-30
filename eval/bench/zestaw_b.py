# SPDX-License-Identifier: MIT OR Apache-2.0
"""Zestaw B: zadania trudniejsze niż VeraBench, dobrane pod błędy, których nie widać w kilku
przykładach: przepełnienia, dzielenie obcinane i podłogowe, puste wejścia, duplikaty,
zadania z wieloma poprawnymi wynikami. Opisy są neutralne językowo (bez składni Rdzenia)."""
from __future__ import annotations

from .zadania import Dane, zadanie

E9, E12, E18 = 10**9, 10**12, 10**18
I64_MIN, I64_MAX = -2**63, 2**63 - 1
I32_MIN, I32_MAX = -2**31, 2**31 - 1

PARA = Dane("IndexPair", [("IndexPair", [("i", "Nat"), ("j", "Nat")])], "rekord")
ODCINEK = Dane("Span", [("Span", [("lo", "Int"), ("hi", "Int")])], "rekord")
BST = Dane("Tree", [("Leaf", []), ("Node", [("left", "Tree"), ("key", "Int"), ("right", "Tree")])], "znaczniki")
WYR = Dane("Expr", [("Lit", [("value", "Int")]), ("Add", [("left", "Expr"), ("right", "Expr")]),
                    ("Mul", [("left", "Expr"), ("right", "Expr")]), ("Div", [("left", "Expr"), ("right", "Expr")])],
           "znaczniki")


def B(nr, funkcja, tytul, opis, parametry, wynik, wyrocznia, generator, dziedzina, brzegowe, tagi=(), dane=(),
      sprawdz=None, n_losowych=200):
    return zadanie(id=f"B-{nr:02d}", tytul=tytul, opis=opis, funkcja=funkcja, parametry=list(parametry), wynik=wynik,
                   wyrocznia=wyrocznia, generator=generator, dziedzina=dziedzina, brzegowe=list(brzegowe),
                   tagi=list(tagi), dane=list(dane), sprawdz=sprawdz, n_losowych=n_losowych)


# ---------- pomocnicze ----------

def ri(r, lo, hi):
    x = r.random()
    if x < 0.3 and lo <= -10 and hi >= 10:
        return r.randint(-10, 10)
    if x < 0.4:
        return r.choice([lo, hi, lo + 1, hi - 1])
    return r.randint(lo, hi)


def arr(r, n, lo, hi):
    k = r.choice([0, 1, 2, r.randint(0, 8), r.randint(0, n)])
    if r.random() < 0.3:          # mało różnych wartości → duplikaty
        pool = [ri(r, lo, hi) for _ in range(3)]
        return [r.choice(pool) for _ in range(k)]
    return [ri(r, lo, hi) for _ in range(k)]


def tdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def rstr(r, n, alfabet):
    return "".join(r.choice(alfabet) for _ in range(r.randint(0, n)))


ASCII = "".join(chr(c) for c in range(32, 127))

# ---------- tablice ----------

D_SORTED = ("The array has at most 1000 elements, is sorted in non-decreasing order, and all values are in "
            "the range [-10^9, 10^9].")


def first_index_of(xs, t):
    for i, x in enumerate(xs):
        if x == t:
            return i
    return -1


def g_sorted_target(r):
    xs = sorted(arr(r, 1000, -E9, E9))
    t = r.choice(xs) if xs and r.random() < 0.6 else ri(r, -E9, E9)
    return (xs, t)


B(1, "first_index_of", "First occurrence in a sorted array",
  "Given an array sorted in non-decreasing order and a target value, return the index of the first occurrence "
  "of the target, or -1 if it does not occur. Example: ([1, 2, 2, 2, 5], 2) -> 1.",
  [("xs", "Array<Int>"), ("target", "Int")], "Int", first_index_of, g_sorted_target,
  D_SORTED + " The target is in the range [-10^9, 10^9].",
  [([], 0), ([7], 7), ([7], 8), ([2, 2, 2, 2], 2), ([1, 1, 3, 3], 2), ([-E9, E9], E9), ([1, 2, 3], 0), ([1, 2, 3], 4), ([0] * 1000, 0), (list(range(-500, 500)), 499), (list(range(1000)), -1)],
  tagi=["wyszukiwanie"])


def merge_sorted(a, b):
    return sorted(a + b)


B(2, "merge_sorted", "Merge two sorted arrays",
  "Merge two arrays, each sorted in non-decreasing order, into one array sorted in non-decreasing order that "
  "contains all elements of both (with multiplicities).",
  [("a", "Array<Int>"), ("b", "Array<Int>")], "Array<Int>", merge_sorted,
  lambda r: (sorted(arr(r, 1000, -E9, E9)), sorted(arr(r, 1000, -E9, E9))),
  "Each array has at most 1000 elements, all values are in the range [-10^9, 10^9].",
  [([], []), ([1], []), ([], [1]), ([1, 1], [1]), ([5, 6], [1, 2]), ([1, 3, 5], [2, 4, 6]), (list(range(1000)), list(range(1000))), ([E9] * 1000, [-E9] * 1000)], tagi=["scalanie"])


def dedup(xs):
    return [x for i, x in enumerate(xs) if i == 0 or xs[i - 1] != x]


B(3, "dedup_sorted", "Remove duplicates from a sorted array",
  "Given an array sorted in non-decreasing order, return the array of its distinct values in increasing order.",
  [("xs", "Array<Int>")], "Array<Int>", dedup, lambda r: (sorted(arr(r, 1000, -E9, E9)),), D_SORTED,
  [([],), ([3],), ([3, 3, 3],), ([1, 2, 2, 3, 3, 3],), ([-E9, -E9, E9, E9],), (list(range(1000)),), ([5] * 1000,)], tagi=["tablice"])


def rotate_left(xs, k):
    if not xs:
        return []
    k %= len(xs)
    return xs[k:] + xs[:k]


B(4, "rotate_left", "Rotate left",
  "Rotate an array left by k positions: the element at index (i + k) mod n moves to index i, where n is the "
  "length. k may be much larger than n. Example: ([1, 2, 3, 4], 1) -> [2, 3, 4, 1].",
  [("xs", "Array<Int>"), ("k", "Nat")], "Array<Int>", rotate_left,
  lambda r: (arr(r, 1000, -E9, E9), r.choice([r.randint(0, 5), r.randint(0, E18), E18])),
  "The array has at most 1000 elements with values in [-10^9, 10^9]; 0 <= k <= 10^18.",
  [([], 0), ([], 5), ([1], E18), ([1, 2, 3], 3), ([1, 2, 3], 4), ([1, 2, 3], E18), (list(range(1000)), E18 - 1)], tagi=["tablice", "modulo"])


def max_subarray(xs):
    best = cur = xs[0]
    for x in xs[1:]:
        cur = max(x, cur + x)
        best = max(best, cur)
    return best


B(5, "max_subarray_sum", "Maximum subarray sum",
  "Return the largest sum of a non-empty contiguous subarray of the given non-empty array.",
  [("xs", "Array<Int>")], "Int", max_subarray,
  lambda r: ([ri(r, -E9, E9) for _ in range(r.randint(1, 1000))],),
  "The array has between 1 and 1000 elements, all values are in the range [-10^9, 10^9].",
  [([-5],), ([-3, -1, -2],), ([E9] * 1000,), ([-E9] * 1000,), ([2, -1, 2],), ([0],), ([-E9, E9] * 500,)], tagi=["programowanie dynamiczne"])


def second_largest(xs):
    s = sorted(set(xs))
    return s[-2] if len(s) >= 2 else None


B(6, "second_largest", "Second largest distinct value",
  "Return the second largest distinct value of the array, or none if the array has fewer than two distinct "
  "values. Example: [5, 5, 3] -> 3; [5, 5] -> none.",
  [("xs", "Array<Int>")], "Option<Int>", second_largest, lambda r: (arr(r, 1000, -E9, E9),),
  "The array has at most 1000 elements, all values are in the range [-10^9, 10^9].",
  [([],), ([1],), ([2, 2],), ([1, 2],), ([2, 1],), ([3, 3, 1, 1],), ([-E9, E9],), ([E9, E9, -E9],), (list(range(1000)),), ([E9] * 999 + [-E9],)],
  tagi=["tablice", "opcja"])


def lir(xs):
    best = cur = 0
    for i, x in enumerate(xs):
        cur = cur + 1 if i > 0 and xs[i - 1] < x else 1
        best = max(best, cur)
    return best


B(7, "longest_increasing_run", "Longest strictly increasing run",
  "Return the length of the longest contiguous run of strictly increasing elements (0 for an empty array). "
  "Example: [1, 2, 2, 3, 4, 1] -> 3.",
  [("xs", "Array<Int>")], "Nat", lir, lambda r: (arr(r, 1000, -50, 50),),
  "The array has at most 1000 elements, all values are in the range [-10^9, 10^9].",
  [([],), ([4],), ([1, 1, 1],), ([1, 2, 3],), ([3, 2, 1],), ([1, 2, 1, 2, 3],), (list(range(1000)),), (list(range(1000, 0, -1)),)], tagi=["tablice"])


def majority(xs):
    for x in set(xs):
        if 2 * xs.count(x) > len(xs):
            return x
    return None


def g_major(r):
    n = r.randint(0, 60)
    m = ri(r, -E9, E9)
    k = r.choice([n // 2, n // 2 + 1, n, r.randint(0, n)])
    xs = [m] * k + [ri(r, -3, 3) for _ in range(n - k)]
    r.shuffle(xs)
    return (xs,)


B(8, "majority_element", "Majority element",
  "Return the value that occurs strictly more than n/2 times in an array of length n, or none if there is "
  "no such value.",
  [("xs", "Array<Int>")], "Option<Int>", majority, g_major,
  "The array has at most 1000 elements, all values are in the range [-10^9, 10^9].",
  [([],), ([1],), ([1, 2],), ([1, 1, 2],), ([1, 2, 1, 2],), ([2, 1, 2, 1, 2],), ([7] * 501 + [1] * 499,), ([7] * 500 + [1] * 500,)], tagi=["tablice", "opcja"])


def inversions(xs):
    return sum(1 for i in range(len(xs)) for j in range(i + 1, len(xs)) if xs[i] > xs[j])


B(9, "count_inversions", "Count inversions",
  "Count pairs of indices (i, j) with i < j and xs[i] > xs[j].",
  [("xs", "Array<Int>")], "Nat", inversions, lambda r: (arr(r, 200, -E9, E9),),
  "The array has at most 200 elements, all values are in the range [-10^9, 10^9].",
  [([],), ([1],), ([2, 1],), ([1, 1],), (list(range(200, 0, -1)),), (list(range(200)),)], tagi=["tablice"])

B(10, "sort_array", "Sort",
  "Return the elements of the array sorted in non-decreasing order (same multiset of values).",
  [("xs", "Array<Int>")], "Array<Int>", sorted, lambda r: (arr(r, 200, -E9, E9),),
  "The array has at most 200 elements, all values are in the range [-10^9, 10^9].",
  [([],), ([1],), ([2, 1],), ([1, 1, 1],), ([3, -1, 3, -1],), ([E9, -E9, 0],), (list(range(200, 0, -1)),), ([E9, -E9] * 100,)], tagi=["sortowanie"])

B(11, "evens_first", "Stable even/odd partition",
  "Return an array with all even elements first and then all odd elements, each group keeping the original "
  "relative order. Negative numbers follow the usual parity: -4 is even, -3 is odd.",
  [("xs", "Array<Int>")], "Array<Int>", lambda xs: [x for x in xs if x % 2 == 0] + [x for x in xs if x % 2],
  lambda r: (arr(r, 1000, -E9, E9),), "The array has at most 1000 elements, all values are in the range [-10^9, 10^9].",
  [([],), ([-3, -2, -1, 0, 1, 2],), ([1, 3],), ([2, 4],), ([-E9, E9 - 1, -E9 + 1],), (list(range(-500, 500)),)], tagi=["tablice", "parzystość"])


def ok_two_sum(args, res):
    xs, t = args
    if res is None:
        return not any(xs[i] + xs[j] == t for i in range(len(xs)) for j in range(i + 1, len(xs)))
    if not (isinstance(res, tuple) and len(res) == 2):
        return False
    i, j = res
    return 0 <= i < j < len(xs) and xs[i] + xs[j] == t


def g_two_sum(r):
    xs = arr(r, 200, -E9, E9)
    if len(xs) >= 2 and r.random() < 0.6:
        i, j = r.sample(range(len(xs)), 2)
        return (xs, xs[i] + xs[j])
    return (xs, ri(r, -2 * E9, 2 * E9))


def two_sum_ref(xs, t):
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            if xs[i] + xs[j] == t:
                return (i, j)
    return None


B(12, "two_sum", "Two sum (unsorted)",
  "Given an array (not necessarily sorted) and a target, return a pair of indices (i, j) with i < j and "
  "xs[i] + xs[j] == target, or none if no such pair exists. Any valid pair is accepted.",
  [("xs", "Array<Int>"), ("target", "Int")], "Option<IndexPair>", two_sum_ref, g_two_sum,
  "The array has at most 200 elements with values in [-10^9, 10^9]; the target is in [-2*10^9, 2*10^9].",
  [([], 0), ([1], 2), ([1, 1], 2), ([3, 3, 3], 6), ([E9, E9], 2 * E9), ([-E9, -E9], -2 * E9), ([1, 2], 4), (list(range(200)), 397), (list(range(200)), 398), ([E9] * 200, 2 * E9)],
  tagi=["tablice", "wiele odpowiedzi"], dane=[PARA], sprawdz=ok_two_sum)


def next_perm(xs):
    a = list(xs)
    i = len(a) - 2
    while i >= 0 and a[i] >= a[i + 1]:
        i -= 1
    if i < 0:
        return sorted(a)
    j = len(a) - 1
    while a[j] <= a[i]:
        j -= 1
    a[i], a[j] = a[j], a[i]
    a[i + 1:] = reversed(a[i + 1:])
    return a


B(13, "next_permutation", "Next permutation",
  "Return the lexicographically next arrangement of the array's elements (the smallest arrangement that is "
  "lexicographically greater). If none exists, return the elements in non-decreasing order. Elements may repeat. "
  "Example: [1, 3, 2] -> [2, 1, 3]; [3, 2, 1] -> [1, 2, 3]; [1, 1, 5] -> [1, 5, 1].",
  [("xs", "Array<Int>")], "Array<Int>", next_perm, lambda r: ([r.randint(0, 4) for _ in range(r.randint(0, 8))],),
  "The array has at most 100 elements, all values are in the range [-10^9, 10^9].",
  [([],), ([1],), ([1, 1],), ([1, 2],), ([2, 1],), ([1, 5, 1],), ([5, 1, 1],), ([2, 3, 1, 3, 3],), (list(range(100)),), (list(range(100, 0, -1)),)], tagi=["permutacje"])


def merge_spans(sp):
    out = []
    for lo, hi in sp:
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def g_spans(r):
    sp = []
    for _ in range(r.choice([0, 1, 2, r.randint(0, 30)])):
        lo = ri(r, -100, 100) if r.random() < 0.7 else ri(r, -E9, E9)
        sp.append((lo, lo + r.choice([0, 0, r.randint(0, 20), r.randint(0, E9)])))
    sp = [(lo, min(hi, E9)) for lo, hi in sp]
    return (sorted(sp),)


B(14, "merge_intervals", "Merge intervals",
  "Given closed integer intervals [lo, hi] sorted by lo (then by hi), merge every group of intervals that "
  "overlap or share an endpoint and return the merged intervals sorted by lo. Intervals [1, 2] and [3, 4] do not "
  "overlap and stay separate; [1, 3] and [3, 5] become [1, 5].",
  [("spans", "Array<Span>")], "Array<Span>", merge_spans, g_spans,
  "There are at most 200 intervals; for each, -10^9 <= lo <= hi <= 10^9.",
  [([],), ([(1, 1)],), ([(1, 3), (3, 5)],), ([(1, 2), (3, 4)],), ([(1, 10), (2, 3), (4, 5)],), ([(0, 0), (0, 0)],),
   ([(-E9, E9), (0, 1)],), ([(k, k) for k in range(200)],), ([(0, E9)] * 200,), ([(-E9, -E9 + 1), (E9 - 1, E9)],)], tagi=["przedziały"], dane=[ODCINEK])

# ---------- arytmetyka ----------


def isqrt(n):
    import math
    return math.isqrt(n)


B(15, "isqrt", "Integer square root",
  "Return the largest integer r >= 0 such that r * r <= n.",
  [("n", "Nat")], "Nat", isqrt,
  lambda r: (r.choice([r.randint(0, 100), r.randint(0, I64_MAX), r.randint(0, 3037000499) ** 2,
                       r.randint(1, 3037000499) ** 2 - 1, I64_MAX - r.randint(0, 10)]),),
  "0 <= n <= 9223372036854775807 (2^63 - 1).",
  [(0,), (1,), (2,), (3,), (4,), (I64_MAX,), (3037000499 ** 2,), (3037000499 ** 2 - 1,), (3037000499 ** 2 + 1,)],
  tagi=["przepełnienie"])

B(16, "pow_mod", "Modular exponentiation",
  "Return (base ^ exp) mod m, where 0^0 = 1. The result is in the range [0, m - 1]. "
  "The exponent can be very large, so the computation must take O(log exp) steps.",
  [("base", "Nat"), ("exp", "Nat"), ("m", "Nat")], "Nat", pow,
  lambda r: (r.choice([ri(r, 0, 10), r.randint(0, E18)]), r.choice([r.randint(0, 20), r.randint(0, E18)]),
             r.choice([1, 2, r.randint(1, E9), E9])),
  "0 <= base <= 10^18, 0 <= exp <= 10^18, 1 <= m <= 10^9.",
  [(0, 0, 1), (5, 0, 1), (5, 0, 7), (0, 0, 7), (E18, E18, E9), (E9 - 1, E18, E9), (2, 62, E9)], tagi=["przepełnienie"])


def rev32(x):
    s = int(str(abs(x))[::-1])
    v = -s if x < 0 else s
    return v if I32_MIN <= v <= I32_MAX else None


B(17, "reverse_digits", "Reverse digits (32-bit)",
  "Reverse the decimal digits of x, keeping its sign and dropping leading zeros of the result "
  "(120 -> 21, -45 -> -54). Return none if the reversed value is outside the 32-bit signed range "
  "[-2147483648, 2147483647].",
  [("x", "Int")], "Option<Int>", rev32,
  lambda r: (r.choice([ri(r, -1000, 1000), r.randint(I32_MIN, I32_MAX), r.randint(10**9, I32_MAX),
                       -r.randint(10**9, 2**31)]),),
  "-2147483648 <= x <= 2147483647.",
  [(0,), (10,), (-10,), (I32_MAX,), (I32_MIN,), (1463847412,), (-1463847412,), (1563847412,), (-1563847412,),
   (2147483641,), (-2147483641,), (1000000003,)], tagi=["przepełnienie", "opcja"])


def sat_add(a, b):
    return max(I64_MIN, min(I64_MAX, a + b))


B(18, "saturating_add", "Saturating 64-bit addition",
  "Return a + b clamped to the signed 64-bit range [-9223372036854775808, 9223372036854775807].",
  [("a", "Int"), ("b", "Int")], "Int", sat_add,
  lambda r: (r.choice([ri(r, -10, 10), r.randint(I64_MIN, I64_MAX), I64_MAX - r.randint(0, 5), I64_MIN + r.randint(0, 5)]),
             r.choice([ri(r, -10, 10), r.randint(I64_MIN, I64_MAX), I64_MAX - r.randint(0, 5), I64_MIN + r.randint(0, 5)])),
  "a and b are signed 64-bit integers.",
  [(I64_MAX, 1), (I64_MIN, -1), (I64_MAX, I64_MAX), (I64_MIN, I64_MIN), (I64_MAX, I64_MIN), (I64_MIN, I64_MAX),
   (0, 0), (I64_MAX, 0), (-1, I64_MIN + 1)], tagi=["przepełnienie"])

B(19, "floor_average", "Floor of the average",
  "Return the arithmetic mean of a non-empty array rounded down, i.e. the largest integer q with "
  "q * n <= sum. Example: [-1, 0] -> -1; [1, 2] -> 1.",
  [("xs", "Array<Int>")], "Int", lambda xs: sum(xs) // len(xs),
  lambda r: ([ri(r, -E12, E12) for _ in range(r.randint(1, r.choice([3, 1000])))],),
  "The array has between 1 and 1000 elements, all values are in the range [-10^12, 10^12].",
  [([-1, 0],), ([-1, -2],), ([-3],), ([1, 2],), ([E12] * 1000,), ([-E12] * 1000,), ([-E12, -E12 + 1],), ([E12, -E12] * 500,), ([-E12] * 999 + [E12 - 1],)],
  tagi=["dzielenie"])


def leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def doy(y, m, d):
    dm = [31, 29 if leap(y) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if not (1 <= m <= 12 and 1 <= d <= dm[m - 1]):
        return None
    return sum(dm[: m - 1]) + d


B(20, "day_of_year", "Day of year",
  "Given a date (year, month, day) in the proleptic Gregorian calendar, return its ordinal day in the year "
  "(1 January -> 1), or none if the date does not exist. Leap years: divisible by 4, except years divisible by 100 "
  "that are not divisible by 400.",
  [("year", "Int"), ("month", "Int"), ("day", "Int")], "Option<Int>", doy,
  lambda r: (r.choice([r.randint(1, 9999), 1900, 2000, 2024, 2100, 2400]), r.choice([r.randint(1, 12), ri(r, -100, 100)]),
             r.choice([r.randint(1, 31), r.randint(28, 31), ri(r, -100, 100)])),
  "1 <= year <= 9999; month and day are arbitrary integers in [-100, 100].",
  [(2024, 2, 29), (2023, 2, 29), (1900, 2, 29), (2000, 2, 29), (2023, 12, 31), (2024, 12, 31), (2023, 0, 1),
   (2023, 13, 1), (2023, 4, 31), (2023, 1, 0), (2023, -1, -1)], tagi=["daty", "opcja"])


def lcm_all(xs):
    from math import gcd
    acc = 1
    for x in xs:
        acc = acc * x // gcd(acc, x)
        if acc > I64_MAX:
            return None
    return acc


B(21, "lcm_all", "Least common multiple of an array",
  "Return the least common multiple of the array's elements (1 for an empty array), or none if it exceeds "
  "9223372036854775807 (2^63 - 1).",
  [("xs", "Array<Nat>")], "Option<Nat>", lcm_all,
  lambda r: ([r.choice([r.randint(1, 20), r.randint(1, E9)]) for _ in range(r.randint(0, 20))],),
  "The array has at most 20 elements, each in the range [1, 10^9].",
  [([],), ([1],), ([E9],), ([E9, E9 - 1],), ([E9, E9 - 1, E9 - 3],), ([2, 3, 4, 5, 6],), ([4, 6],),
   ([999999937, 999999929, 9],), ([E9 - k for k in range(20)],), ([1] * 20,)], tagi=["przepełnienie", "opcja"])

# ---------- napisy ----------


def parse_int(s):
    t = s[1:] if s[:1] in ("+", "-") else s
    if not t or not all("0" <= c <= "9" for c in t):
        return None
    v = int(s)
    return v if I64_MIN <= v <= I64_MAX else None


B(22, "parse_int", "Parse a signed integer",
  "Parse a decimal integer: an optional '+' or '-' followed by one or more digits '0'-'9', and nothing else "
  "(no spaces). Leading zeros are allowed. Return none if the string is not of this form or the value is "
  "outside the signed 64-bit range [-9223372036854775808, 9223372036854775807].",
  [("s", "Str")], "Option<Int>", parse_int,
  lambda r: (r.choice([rstr(r, 6, "0123456789+- a"), str(r.randint(I64_MIN, I64_MAX)), str(r.randint(I64_MAX, 10**20)),
                       "-" + str(r.randint(2**63 - 3, 2**63 + 3)), "+" + "0" * r.randint(0, 25) + str(r.randint(0, 99))]),),
  "The string consists of printable ASCII characters and has at most 30 characters.",
  [("",), ("+",), ("-",), ("0",), ("-0",), ("007",), ("+12",), ("1 ",), (" 1",), ("1-",), ("9223372036854775807",),
   ("9223372036854775808",), ("-9223372036854775808",), ("-9223372036854775809",), ("00000000000000000000000001",),
   ("99999999999999999999",), ("-" + "0" * 29,), ("+" + "9" * 29,)], tagi=["napisy", "przepełnienie", "opcja"])


def pal(s):
    t = [c.lower() for c in s if c.isascii() and c.isalnum()]
    return t == t[::-1]


B(23, "is_palindrome_alnum", "Alphanumeric palindrome",
  "Return true if the string reads the same forwards and backwards when only ASCII letters and digits are "
  "considered and letter case is ignored. Example: \"A man, a plan, a canal: Panama\" -> true.",
  [("s", "Str")], "Bool", pal,
  lambda r: (lambda h: (h + (h[::-1] if r.random() < 0.5 else rstr(r, 3, "aB1")),))(rstr(r, 20, "aAbB1 ,.:")),
  "The string consists of printable ASCII characters and has at most 200 characters.",
  [("",), (" ",), ("a",), ("ab",), ("Aa",), ("0P",), ("a.",), (".,",), ("ab1Ba",), ("race a car",), ("a" * 199 + "b",), ("Ab" * 50 + "bA" * 50,)], tagi=["napisy"])


def balanced(s):
    st, para = [], {")": "(", "]": "[", "}": "{"}
    for c in s:
        if c in "([{":
            st.append(c)
        elif c in para:
            if not st or st.pop() != para[c]:
                return False
    return not st


B(24, "balanced_brackets", "Balanced brackets",
  "Return true if the brackets (), [] and {} in the string are balanced and properly nested. All other "
  "characters are ignored.",
  [("s", "Str")], "Bool", balanced, lambda r: (rstr(r, r.choice([4, 12, 40]), "()[]{}x"),),
  "The string consists of printable ASCII characters and has at most 200 characters.",
  [("",), ("x",), ("(",), (")",), ("()",), ("(]",), ("([)]",), ("{[]}",), (")(",), ("(()",), ("(" * 100 + ")" * 100,), ("(" * 200,), ("[" * 100 + "]" * 99 + ")",)], tagi=["napisy", "stos"])


def compress(s):
    out, i = [], 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]:
            j += 1
        out.append(s[i] + (str(j - i) if j - i > 1 else ""))
        i = j
    return "".join(out)


B(25, "compress", "Run-length compression",
  "Compress a string of lowercase letters by replacing each maximal run of a repeated letter with the letter "
  "followed by the run length in decimal; runs of length 1 are written as the letter alone. "
  "Example: \"aaabccddddddddddd\" -> \"a3bc2d11\".",
  [("s", "Str")], "Str", compress,
  lambda r: ("".join(r.choice("ab") * r.choice([1, 1, 2, r.randint(1, 12), r.randint(1, 120)]) for _ in range(r.randint(0, 6)))[:200],),
  "The string consists of lowercase letters 'a'-'z' and has at most 200 characters.",
  [("",), ("a",), ("aa",), ("ab",), ("a" * 10,), ("a" * 100,), ("a" * 200,), ("abbbbbbbbbbc",)], tagi=["napisy"])


def caesar(s, k):
    return "".join(chr((ord(c) - 97 + k) % 26 + 97) if "a" <= c <= "z" else c for c in s)


B(26, "caesar", "Caesar shift",
  "Shift every lowercase letter 'a'-'z' by k positions in the alphabet with wrap-around (k may be negative or "
  "larger than 26); leave all other characters unchanged. Example: (\"az-Z\", 1) -> \"ba-Z\"; (\"a\", -1) -> \"z\".",
  [("s", "Str"), ("k", "Int")], "Str", caesar,
  lambda r: (rstr(r, 30, "abxyz AZ!"), r.choice([ri(r, -30, 30), r.randint(-E18, E18)])),
  "The string consists of printable ASCII characters and has at most 100 characters; -10^18 <= k <= 10^18.",
  [("abc", 0), ("a", -1), ("z", 1), ("a", -27), ("a", 26), ("a", -E18), ("a", E18), ("AZ{}`", 5), ("", 3), (ASCII[:100], -E18 + 1)],
  tagi=["napisy", "modulo"])


def roman(n):
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
            (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = []
    for v, s in vals:
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)


B(27, "int_to_roman", "Integer to Roman numeral",
  "Convert an integer to a standard Roman numeral using subtractive notation (4 -> \"IV\", 9 -> \"IX\", "
  "40 -> \"XL\", 90 -> \"XC\", 400 -> \"CD\", 900 -> \"CM\").",
  [("n", "Int")], "Str", roman, lambda r: (r.randint(1, 3999),), "1 <= n <= 3999.",
  [(1,), (4,), (9,), (14,), (40,), (90,), (400,), (944,), (1994,), (3999,), (3888,)], tagi=["napisy"])


def words(s):
    return len(s.split())


B(28, "word_count", "Word count",
  "Return the number of words in the string, where a word is a maximal non-empty sequence of characters other "
  "than space, tab and newline.",
  [("s", "Str")], "Nat", words, lambda r: (rstr(r, 40, "ab  \t\n"),),
  "The string consists of printable ASCII characters, tabs and newlines and has at most 200 characters.",
  [("",), (" ",), ("a",), (" a",), ("a ",), ("a  b",), ("\t\n",), ("a\tb\nc",), ("a " * 100,), (" " * 200,), ("a" * 200,)], tagi=["napisy"])


def edit(a, b):
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
        prev = cur
    return prev[-1]


B(29, "edit_distance", "Edit distance",
  "Return the Levenshtein distance between two strings: the minimum number of single-character insertions, "
  "deletions and substitutions that turn the first string into the second.",
  [("a", "Str"), ("b", "Str")], "Nat", edit, lambda r: (rstr(r, 12, "abc"), rstr(r, 12, "abc")),
  "Both strings consist of printable ASCII characters and have at most 30 characters.",
  [("", ""), ("a", ""), ("", "abc"), ("kitten", "sitting"), ("abc", "abc"), ("ab", "ba"), ("a" * 30, "b" * 30), ("ab" * 15, "ba" * 15), ("x" * 30, "")],
  tagi=["napisy", "programowanie dynamiczne"])


def lis(xs):
    best = [1] * len(xs)
    for i in range(len(xs)):
        for j in range(i):
            if xs[j] < xs[i]:
                best[i] = max(best[i], best[j] + 1)
    return max(best, default=0)


B(30, "lis_length", "Longest increasing subsequence",
  "Return the length of the longest strictly increasing subsequence (not necessarily contiguous).",
  [("xs", "Array<Int>")], "Nat", lis, lambda r: (arr(r, 200, -E9, E9),),
  "The array has at most 200 elements, all values are in the range [-10^9, 10^9].",
  [([],), ([5],), ([2, 2],), ([3, 1, 2],), ([10, 9, 2, 5, 3, 7, 101, 18],), (list(range(200)),), (list(range(200, 0, -1)),)], tagi=["programowanie dynamiczne"])

# ---------- typy danych ----------


def is_bst(t, lo=None, hi=None):
    if t[0] == "Leaf":
        return True
    _, l, k, r = t
    if (lo is not None and k <= lo) or (hi is not None and k >= hi):
        return False
    return is_bst(l, lo, k) and is_bst(r, k, hi)


def bst_from(keys):
    t = ("Leaf",)
    for k in keys:
        t = _ins(t, k)
    return t


def _ins(t, k):
    if t[0] == "Leaf":
        return ("Node", ("Leaf",), k, ("Leaf",))
    _, l, x, r = t
    if k < x:
        return ("Node", _ins(l, k), x, r)
    if k > x:
        return ("Node", l, x, _ins(r, k))
    return t


def _perturb(t, r):
    """Zmienia jeden klucz; często zachowuje porządek względem rodzica, a łamie względem przodka."""
    if t[0] == "Leaf":
        return t
    _, l, k, rr = t
    x = r.random()
    if x < 0.3:
        return ("Node", l, k + r.choice([-2, -1, 1, 2, 50, -50]), rr)
    if x < 0.65:
        return ("Node", _perturb(l, r), k, rr)
    return ("Node", l, k, _perturb(rr, r))


def g_bst(r):
    t = bst_from([ri(r, -100, 100) for _ in range(r.randint(0, 25))])
    return (_perturb(t, r) if r.random() < 0.6 else t,)


L = ("Leaf",)


def N(l, k, r):
    return ("Node", l, k, r)


B(31, "is_bst", "Binary search tree check",
  "Return true if the tree is a binary search tree with strictly ordered keys: for every node, all keys in its "
  "left subtree are smaller than its key and all keys in its right subtree are greater.",
  [("t", "Tree")], "Bool", is_bst, g_bst, "Trees have at most 100 nodes; keys are in the range [-10^9, 10^9].",
  [(L,), (N(L, 1, L),), (N(N(L, 1, L), 1, L),), (N(N(L, 1, N(L, 5, L)), 3, L),), (N(L, 3, N(N(L, 2, L), 5, L)),),
   (N(N(L, 1, N(L, 2, L)), 3, N(L, 4, L)),)], tagi=["drzewa"], dane=[BST])


def ev(e):
    c = e[0]
    if c == "Lit":
        return e[1]
    a, b = ev(e[1]), ev(e[2])
    if a is None or b is None:
        return None
    if c == "Add":
        v = a + b
    elif c == "Mul":
        v = a * b
    else:
        if b == 0:
            return None
        v = tdiv(a, b)
    return v if I64_MIN <= v <= I64_MAX else None


def g_expr(r, d=0):
    x = r.random()
    if d >= 4 or x < 0.3:
        return ("Lit", r.choice([ri(r, -10, 10), r.randint(I64_MIN, I64_MAX), I64_MIN, I64_MAX, -1, 0]))
    return (r.choice(["Add", "Mul", "Div", "Div"]), g_expr(r, d + 1), g_expr(r, d + 1))


def lit(v):
    return ("Lit", v)


B(32, "eval_checked", "Checked expression evaluation",
  "Evaluate an expression over signed 64-bit integers built from literals, addition, multiplication and "
  "division. Division truncates toward zero (7 / -2 = -3, -7 / 2 = -3). Return none if any division has a zero "
  "divisor or if the exact value of any subexpression is outside [-9223372036854775808, 9223372036854775807].",
  [("e", "Expr")], "Option<Int>", ev, lambda r: (g_expr(r),),
  "Expressions have at most 100 nodes; literals are signed 64-bit integers.",
  [(("Div", lit(7), lit(-2)),), (("Div", lit(-7), lit(2)),), (("Div", lit(1), lit(0)),), (("Div", lit(I64_MIN), lit(-1)),),
   (("Add", lit(I64_MAX), lit(1)),), (("Mul", lit(2**32), lit(2**31)),), (("Mul", lit(-(2**32)), lit(2**31)),),
   (("Add", ("Div", lit(1), lit(0)), lit(0)),), (("Mul", ("Div", lit(1), lit(0)), lit(0)),)],
  tagi=["drzewa", "przepełnienie", "dzielenie", "opcja"], dane=[WYR])
