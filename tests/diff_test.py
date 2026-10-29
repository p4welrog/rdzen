# SPDX-License-Identifier: MIT OR Apache-2.0
"""Testy różnicowe: wygenerowany moduł Pythona vs interpreter jądra.

Dla każdej funkcji generuje losowe argumenty spełniające warunki wstępne
i porównuje wynik, końcowe wartości parametrów inout oraz rodzaj pułapki."""
import glob, os, sys, random, importlib.util, tempfile, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.setrecursionlimit(10000)
from rdzen.driver import compile_source, gen_value, _FAIL
from rdzen.emit_py import emit, Unsupported, esc
from rdzen.interp import Interp, Violation, BudgetExceeded, fmt

N = int(os.environ.get("N", 150))


def pystr(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if v is None:
        return "()"
    if isinstance(v, list):
        return "[" + ", ".join(pystr(x) for x in v) + "]"
    name = type(v).__name__.rstrip("_")
    if not v._fields:
        return name
    return name + "(" + ", ".join(pystr(getattr(v, f)) for f in v._fields) + ")"


def run_file(path, tmp):
    src = open(path, encoding="utf-8").read()
    res = compile_source(src, run_examples=False, rlimit=int(os.environ.get("RLIMIT", 1_000_000)))
    if any(d.severity in ("error", "hole") for d in res.diags):
        return None
    try:
        code = emit(res, os.path.basename(path))
    except Unsupported as e:
        return f"pominięto ({e})"
    mod_path = os.path.join(tmp, os.path.basename(path).replace(".rz", "_rz.py"))
    open(mod_path, "w").write(code)
    spec = importlib.util.spec_from_file_location(os.path.basename(mod_path)[:-3], mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ch = res.checker
    stats = {"zgodne": 0, "pułapki": 0, "pominięte": 0}
    rng = random.Random(1234)
    for f in ch.user_fns:
        if f.lemma:
            continue
        sig = f.sig
        pyf = getattr(mod, esc(f.name))
        for _ in range(N):
            vals = []
            for (pn, pt, _) in sig.params:
                from rdzen.check import subst_rt, INT
                v = gen_value(ch, subst_rt(pt, {t: INT for t in sig.tparams}), rng, {})
                if v is _FAIL:
                    break
                vals.append(v)
            if len(vals) != len(sig.params):
                stats["pominięte"] += 1
                continue
            try:
                r, outs = Interp(ch, budget=300_000).call_fn(sig, [__import__("copy").deepcopy(x) for x in vals], None)
                expect = ("ok", fmt(r), [fmt(o) for o in outs])
            except Violation as v:
                if v.kind == "pre" and v.key[2] is None:
                    stats["pominięte"] += 1
                    continue
                expect = ("trap", v.kind)
            except (BudgetExceeded, RecursionError):
                stats["pominięte"] += 1
                continue
            pyvals = [to_py(mod, x) for x in vals]
            try:
                out = pyf(*pyvals)
                inouts = [p for p in sig.params if p[2]]
                if inouts:
                    got = ("ok", pystr(out[0]) if sig.decl.ret is not None else "()", [pystr(o) for o in out[1:]])
                else:
                    got = ("ok", pystr(out) if sig.decl.ret is not None else "()", [])
            except mod.RdzenTrap as t:
                got = ("trap", t.kind)
            except RecursionError:
                stats["pominięte"] += 1
                continue
            if got != expect:
                return f"ROZBIEŻNOŚĆ w {f.name}{tuple(fmt(x) for x in vals)}: interpreter {expect}, Python {got}"
            stats["zgodne" if got[0] == "ok" else "pułapki"] += 1
    return stats


def to_py(mod, v):
    from rdzen.interp import Ctor, UnitV
    if isinstance(v, list):
        return [to_py(mod, x) for x in v]
    if isinstance(v, Ctor):
        name = v.name + "_" if v.name in ("None", "True", "False") else v.name
        return getattr(mod, name)(*[to_py(mod, x) for x in v.fields])
    if isinstance(v, UnitV):
        return None
    return v


def main():
    root = os.path.join(os.path.dirname(__file__), "..")
    files = sorted(glob.glob(os.path.join(root, "examples", "*.rz")) + glob.glob(os.path.join(root, "tests", "cases", "*.rz")))
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        sys.path.insert(0, tmp)
        for p in files:
            try:
                r = run_file(p, tmp)
            except Exception:
                r = "WYJĄTEK\n" + traceback.format_exc()
            if r is None:
                continue
            bad = isinstance(r, str) and (r.startswith("ROZB") or r.startswith("WYJ"))
            ok &= not bad
            print(f"{'FAIL' if bad else 'PASS'}  {os.path.basename(p):20} {r}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
