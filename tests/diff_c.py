# SPDX-License-Identifier: MIT OR Apache-2.0
"""Testy różnicowe backendu C: skompilowany program C vs interpreter jądra.

Dla każdej funkcji generuje losowe argumenty spełniające warunki wstępne, liczy wynik
interpreterem i dołącza przypadek do programu testowego w C (jedna kompilacja na plik,
pułapki przez longjmp). Program jest kompilowany z UBSan i ASan: niezdefiniowane zachowanie
(np. przepełnienie w arytmetyce, której brak przepełnienia rzekomo udowodniono) jest błędem.
RLIMIT=1 wymusza wszystkie sprawdzenia dynamiczne."""
import copy, glob, os, random, subprocess, sys, tempfile, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.setrecursionlimit(10000)
from rdzen.driver import compile_source, gen_value, _FAIL
from rdzen.emit_c import emit_c
from rdzen.emit_py import Unsupported
from rdzen.interp import Interp, Violation, BudgetExceeded, fmt
from rdzen.check import subst_rt, INT

N = int(os.environ.get("N", 100))
CC = os.environ.get("CC", "gcc")
SAN = os.environ.get("SAN", "1") == "1"


def cases_for(res):
    ch = res.checker
    rng = random.Random(1234)
    cases, expect, skipped = [], [], 0
    for f in ch.user_fns:
        if f.lemma:
            continue
        sig = f.sig
        s = {t: INT for t in sig.tparams}
        for _ in range(N):
            vals = []
            for (pn, pt, _) in sig.params:
                v = gen_value(ch, subst_rt(pt, s), rng, {})
                if v is _FAIL:
                    break
                vals.append(v)
            if len(vals) != len(sig.params):
                skipped += 1
                continue
            try:
                r, outs = Interp(ch, budget=300_000).call_fn(sig, [copy.deepcopy(x) for x in vals], None)
                exp = "R " + fmt(r) + "".join(" | " + fmt(o) for o in outs)
            except Violation as v:
                if v.kind == "pre" and v.key[2] is None:
                    skipped += 1
                    continue
                exp = "T " + v.kind
            except (BudgetExceeded, RecursionError):
                skipped += 1
                continue
            cases.append((f, s, vals))
            expect.append((f.name, vals, exp))
    return cases, expect, skipped


def run_file(path, tmp):
    src = open(path, encoding="utf-8").read()
    res = compile_source(src, run_examples=False, canon=False,
                         rlimit=int(os.environ.get("RLIMIT", 1_000_000)))
    if res.checker is None or any(d.severity == "hole" for d in res.diags):
        return None
    if os.environ.get("ERRORS") != "1" and any(d.severity == "error" for d in res.diags):
        return None     # ERRORS=1: także programy z obalonymi zobowiązaniami (ćwiczy pułapki)
    cases, expect, skipped = cases_for(res)
    try:
        code = emit_c(res, os.path.basename(path), harness=cases)
    except Unsupported as e:
        return f"pominięto ({e})"
    base = os.path.join(tmp, os.path.basename(path)[:-3])
    open(base + ".c", "w").write(code)
    flags = ["-std=gnu11", "-O1", "-w"]
    if SAN:
        flags += ["-fsanitize=undefined,address", "-fno-sanitize-recover=undefined"]
    r = subprocess.run([CC, *flags, base + ".c", "-o", base], capture_output=True, text=True)
    if r.returncode != 0:
        return "BŁĄD KOMPILACJI C\n" + r.stderr[:2000]
    env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0", UBSAN_OPTIONS="print_stacktrace=1")
    r = subprocess.run([base], capture_output=True, text=True, env=env, timeout=600)
    if r.returncode != 0:
        return f"BŁĄD WYKONANIA C (kod {r.returncode})\n" + r.stderr[:2000]
    got = r.stdout.split("\n")
    stats = {"zgodne": 0, "pułapki": 0, "pominięte": skipped}
    for k, (name, vals, exp) in enumerate(expect):
        g = got[k] if k < len(got) else "‹brak›"
        if g != exp:
            return f"ROZBIEŻNOŚĆ w {name}{tuple(fmt(x) for x in vals)}: interpreter `{exp}`, C `{g}`"
        stats["zgodne" if exp.startswith("R") else "pułapki"] += 1
    return stats


def main():
    root = os.path.join(os.path.dirname(__file__), "..")
    files = sys.argv[1:] or sorted(glob.glob(os.path.join(root, "examples", "*.rz")) +
                                   glob.glob(os.path.join(root, "tests", "cases", "*.rz")) +
                                   glob.glob(os.path.join(root, "eval", "*.rz")))
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        for p in files:
            try:
                r = run_file(p, tmp)
            except Exception:
                r = "WYJĄTEK\n" + traceback.format_exc()
            if r is None:
                continue
            bad = isinstance(r, str) and r.startswith(("ROZB", "WYJ", "BŁĄD"))
            ok &= not bad
            print(f"{'FAIL' if bad else 'PASS'}  {os.path.basename(p):22} {r}", flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
