# SPDX-License-Identifier: MIT OR Apache-2.0
"""Pamięć wyników weryfikacji i `--fn` (rdzen/cache.py).

Najważniejsza własność: pamięć nie ukrywa błędów. Zmiana ciała funkcji wymusza jej ponowne
sprawdzenie (i tylko jej); zmiana kontraktu, typu lub `spec fn` — sprawdzenie wszystkiego;
wynik z pamięci jest identyczny jak bez niej."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rdzen.driver import compile_source

BASE = '''data Box { Box(v: Int) }

spec fn small(x: Int) -> Bool =
    -1000 <= x && x <= 1000

fn inc(x: Int) -> Int
    requires small(x)
    ensures result == x + 1
{
    x + 1
}

fn twice(x: Int) -> Int
    requires small(x) && x < 1000
    ensures result == x + 2
{
    let y = inc(x)
    inc(y)
}

fn unbox(b: Box) -> Int {
    b.v
}
'''

FAILS = 0


def check(cond, msg):
    global FAILS
    print(("PASS  " if cond else "FAIL  ") + msg)
    FAILS += 0 if cond else 1


def run(src, **kw):
    r = compile_source(src, run_examples=False, canon=False, **kw)
    codes = sorted(d.code for d in r.diags if d.severity in ("error", "warning"))
    return r, codes


def main():
    with tempfile.TemporaryDirectory() as d:
        os.environ["RZ_CACHE"] = d
        r0, c0 = run(BASE, cache=True)
        check(r0.summary["units"]["from_cache"] == [] and c0 == [], "zimny przebieg: nic z pamięci, brak błędów")
        r1, c1 = run(BASE, cache=True)
        check(set(r1.summary["units"]["from_cache"]) == {"inc", "twice", "unbox"}, "ciepły przebieg: wszystko z pamięci")
        check(r1.summary["obligations"] == r0.summary["obligations"], "te same liczby zobowiązań z pamięcią i bez")

        body = BASE.replace("    let y = inc(x)\n    inc(y)", "    let y = inc(x)\n    inc(y) + 0")
        r2, c2 = run(body, cache=True)
        check(set(r2.summary["units"]["from_cache"]) == {"inc", "unbox"} and c2 == [],
              "zmiana ciała: ponownie sprawdzana tylko zmieniona funkcja")

        bug = BASE.replace("    let y = inc(x)\n    inc(y)", "    let y = inc(x)\n    inc(y) + 1")
        r3, c3 = run(bug, cache=True)
        check("E4020" in c3 and "twice" not in r3.summary["units"]["from_cache"],
              "błąd w ciele nie jest ukryty przez pamięć")

        callee_bug = BASE.replace("{\n    x + 1\n}", "{\n    x + 2\n}")
        r4, c4 = run(callee_bug, cache=True)
        check("E4020" in c4 and set(r4.summary["units"]["from_cache"]) == {"twice", "unbox"},
              "błąd w wywoływanej funkcji: wywołujące z pamięci (wywołania modularne), błąd zgłoszony")

        contract = BASE.replace("ensures result == x + 1", "ensures result == x + 2")
        r5, c5 = run(contract, cache=True)
        check(r5.summary["units"]["from_cache"] == [] and "E4020" in c5,
              "zmiana kontraktu: nic z pamięci, błędy zgłoszone")

        spec = BASE.replace("-1000 <= x && x <= 1000", "-1000 <= x && x <= int_max")
        r6, c6 = run(spec, cache=True)
        check(r6.summary["units"]["from_cache"] == [] and "E4120" in c6,
              "zmiana `spec fn`: nic z pamięci, przepełnienie zgłoszone")

        r7, c7 = run(BASE, only=["twice"])
        check(r7.summary["units"]["checked"] == ["twice"] and c7 == [], "--fn: sprawdzana tylko wskazana funkcja")
        r8, c8 = run(callee_bug, only=["twice"])
        check(c8 == [], "--fn: błędy innych funkcji nie są zgłaszane")
        r9, c9 = run(callee_bug, only=["inc"])
        check(c9 == ["E4020"], "--fn: błąd wskazanej funkcji zgłoszony")
        r10, c10 = run(BASE, only=["nie_ma"])
        check(c10 == ["E1013"], "--fn: nieznana nazwa → E1013")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
