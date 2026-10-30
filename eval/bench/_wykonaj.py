# SPDX-License-Identifier: MIT OR Apache-2.0
"""Proces roboczy oceniacza (uruchamiany przez ocen.py z limitem czasu).

python3 -I _wykonaj.py python ID PLIK.py     — testy ukryte rozwiązania w Pythonie
python3 -I _wykonaj.py rdzen  ID PLIK.rz     — testy ukryte programu w Rdzeniu (emisja Pythona)
Wynik: jeden obiekt JSON na stdout."""
import json
import os
import sys
import types

KORZEN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path[:0] = [KORZEN, os.path.join(KORZEN, "eval")]
sys.setrecursionlimit(10000)

from bench.zadania import (ZlyWynik, do_interp, do_modulu, do_pythona, parse_ty, wszystkie,  # noqa: E402
                           z_modulu, z_pythona)


def _modul():
    """Przestrzeń nazw rozwiązania jako zarejestrowany moduł (wymagają tego np. dataclasses)."""
    m = types.ModuleType("rozwiazanie")
    sys.modules["rozwiazanie"] = m
    return m.__dict__


def skrot(v, n=200):
    s = repr(v)
    return s if len(s) <= n else s[:n] + "…"


def uruchom(z, wywolaj, pre=None):
    """wywolaj(args) → wartość neutralna albo wyjątek; pre(args) → None albo opis odrzucenia."""
    przypadki = z.przypadki()
    zrodlowe = {repr(tuple(a)) for a, _ in z.testy_zrodla}
    zdane = zdane_zr = 0
    bledy = []
    for a in przypadki:
        if pre is not None:
            odrzut = pre(a)
            if odrzut:
                bledy.append({"args": skrot(a), "rodzaj": "requires-za-silny", "opis": odrzut})
                continue
        try:
            w = wywolaj(a)
        except ZlyWynik as e:
            bledy.append({"args": skrot(a), "rodzaj": "zly-typ-wyniku", "opis": str(e)})
            continue
        except RecursionError:
            bledy.append({"args": skrot(a), "rodzaj": "rekursja"})
            continue
        except Exception as e:  # noqa: BLE001
            bledy.append({"args": skrot(a), "rodzaj": "wyjatek", "opis": f"{type(e).__name__}: {e}"[:300]})
            continue
        if z.poprawny(a, w):
            zdane += 1
            zdane_zr += repr(tuple(a)) in zrodlowe
        else:
            bledy.append({"args": skrot(a), "rodzaj": "zly-wynik", "otrzymano": skrot(w),
                          "oczekiwano": skrot(z.wyrocznia(*a))})
    return {"przypadki": len(przypadki), "zdane": zdane, "bledy": bledy[:5], "liczba_bledow": len(bledy),
            "rodzaje": sorted({b["rodzaj"] for b in bledy}),
            "zrodlowe": len(zrodlowe), "zrodlowe_zdane": zdane_zr}


def tryb_python(z, plik):
    src = open(plik, encoding="utf-8").read()
    ns = _modul()
    try:
        exec(compile(z.python_preambula() + src, plik, "exec"), ns)
    except Exception as e:  # noqa: BLE001
        return {"etap": "import", "blad": f"{type(e).__name__}: {e}"[:500]}
    f = ns.get(z.funkcja)
    if not callable(f):
        return {"etap": "import", "blad": f"brak funkcji {z.funkcja}"}
    dm = z.dane_map
    pts = [parse_ty(t) for _, t in z.parametry]
    rt = parse_ty(z.wynik)

    def wywolaj(a):
        return z_pythona(f(*[do_pythona(x, t, ns, dm) for x, t in zip(a, pts)]), rt, dm)

    return {"etap": "testy", **uruchom(z, wywolaj)}


GOLE = {"Nat": "Int", "Str": "Array<Int>", "Byte": "Int"}


def goly(t):
    n = GOLE.get(t.name, t.name)
    if n == "Array<Int>":
        return n
    return n + (f"<{', '.join(goly(a) for a in t.args)}>" if t.args else "")


def _pre_python(res, ch, sig, plik, mod):
    """`requires` i uściślenia parametrów funkcji wejściowej skompilowane do Pythona emiterem rzc."""
    from rdzen.emit_py import Emitter, Unsupported, esc
    em = Emitter(ch, res.unproved, os.path.basename(plik))
    env = {pn: esc(pn) for pn, _, _ in sig.params}

    def ref(rt, v, d):
        conds = [em.f(r, env, selfv=v) for r in rt.refs]
        if rt.kind == "Array":
            el = f"_e{d}"
            inner = ref(rt.args[0], el, d + 1)
            if inner != "True":
                conds.append(f"all({inner} for {el} in {v})")
        return " and ".join(f"({c})" for c in conds) or "True"

    try:
        conds = [ref(pt, env[pn], 0) for pn, pt, _ in sig.params]
        conds += [em.f(q, env) for q in sig.decl.requires]
    except (Unsupported, KeyError, AttributeError):
        return None
    kod = f"lambda {', '.join(env.values())}: " + " and ".join(f"({c})" for c in conds) if conds else "lambda *a: True"
    return eval(kod, mod.__dict__)


def tryb_rdzen(z, plik):
    from rdzen.driver import compile_source
    from rdzen.emit_py import emit
    from rdzen.interp import Interp, Violation

    src = open(plik, encoding="utf-8").read()
    res = compile_source(src, run_examples=False)
    if any(d.severity == "error" for d in res.diags):
        return {"etap": "kompilacja", "blad": "program nie przechodzi rzc check"}
    ch = res.checker
    sig = ch.fns.get(z.funkcja)
    if sig is None or sig.builtin:
        return {"etap": "sygnatura", "blad": f"brak funkcji {z.funkcja}"}
    want = [goly(parse_ty(t)) for _, t in z.parametry]
    got = [str(pt.bare()) for _, pt, _ in sig.params]
    inout = [pn for pn, _, io in sig.params if io]
    if got != want or inout or str(sig.ret.bare()) != goly(parse_ty(z.wynik)):
        return {"etap": "sygnatura", "blad": f"parametry {got} -> {sig.ret.bare()}, oczekiwano {want} -> "
                                             f"{goly(parse_ty(z.wynik))}" + (f"; inout: {inout}" if inout else "")}
    mod = types.ModuleType("rz_rozwiazanie")
    exec(compile(emit(res, os.path.basename(plik)), plik + ".py", "exec"), mod.__dict__)
    f = getattr(mod, z.funkcja)
    dm = z.dane_map
    pts = [parse_ty(t) for _, t in z.parametry]
    rt = parse_ty(z.wynik)
    pnames = [pn for pn, _, _ in sig.params]

    pre_py = _pre_python(res, ch, sig, plik, mod)

    def pre(a):
        if pre_py is not None:
            try:
                ok = pre_py(*[do_modulu(x, t, mod, dm) for x, t in zip(a, pts)])
            except Exception as e:  # noqa: BLE001  (np. indeks poza zakresem w formule)
                return f"requires nieokreślone ({type(e).__name__})"
            return None if ok else "requires lub uściślenie parametru"
        it = Interp(ch, budget=10**8)
        vals = [do_interp(x, t, dm) for x, t in zip(a, pts)]
        penv = dict(zip(pnames, vals))
        try:
            for (pn, pt, _), v in zip(sig.params, vals):
                if not it.check_type(v, pt, penv):
                    return f"uściślenie parametru `{pn}`"
            for q in sig.decl.requires:
                if not it.formula(q, penv, q, None):
                    return f"requires w wierszu {q.span.line}"
        except Violation as e:
            return f"requires nieokreślone ({e.kind})"
        return None

    def wywolaj(a):
        return z_modulu(f(*[do_modulu(x, t, mod, dm) for x, t in zip(a, pts)]), rt, dm)

    wynik = uruchom(z, wywolaj, pre)
    wynik["etap"] = "testy"
    return wynik


def bramka_rdzen(plik):
    """To, co widzi model w wariancie R: rzc fmt -w, potem rzc check (bez pamięci wyników)."""
    from rdzen.diag import CompileError, render_text
    from rdzen.driver import compile_source
    from rdzen.fmt import check_format

    src = open(plik, encoding="utf-8").read()
    try:
        out, ok = check_format(src)
        if ok and out != src:
            src = out
            open(plik, "w", encoding="utf-8").write(src)
    except CompileError:
        pass                                  # błąd składni zgłosi check
    res = compile_source(src, cache=False)
    lines = src.split("\n")
    tekst = "\n\n".join(render_text(d, os.path.basename(plik), lines) for d in res.diags)
    s = res.summary
    if "obligations" in s:
        o = s["obligations"]
        tekst += (f"\n\nzobowiązania: {sum(o.values())} (udowodnione {o['proved']}, nieznane {o['unknown']}, "
                  f"obalone {o['refuted']}, indukcyjne-niejawne {o['refuted-inductive']}); "
                  f"przykłady: {s['examples']['passed']} zaliczone, {s['examples']['failed']} niezaliczone; "
                  f"dziury: {s['holes']}")
    bledy = [d.code for d in res.diags if d.severity in ("error", "hole")]
    return {"akceptacja": not bledy, "kody": sorted({d.code for d in res.diags}), "bledy": bledy,
            "podsumowanie": s, "sprawdzenia_dynamiczne": len(res.unproved), "tekst": tekst.strip()}


def bramka_python(z, plik):
    """Wariant PT: uruchamia funkcje test_* z pliku rozwiązania."""
    import traceback
    src = open(plik, encoding="utf-8").read()
    ns = _modul()
    try:
        exec(compile(z.python_preambula() + src, plik, "exec"), ns)
    except Exception:  # noqa: BLE001
        return {"akceptacja": False, "testy": 0, "tekst": traceback.format_exc(limit=3)[-2000:]}
    testy = sorted(k for k, v in ns.items() if k.startswith("test") and callable(v))
    porazki = []
    for t in testy:
        try:
            ns[t]()
        except Exception:  # noqa: BLE001
            porazki.append(f"{t}:\n" + traceback.format_exc(limit=3)[-1500:])
    asercje = src.count("assert ")
    if not testy:
        return {"akceptacja": False, "testy": 0, "asercje": asercje,
                "tekst": "No test functions found (expected functions named test_...)."}
    return {"akceptacja": not porazki, "testy": len(testy), "asercje": asercje, "porazki": len(porazki),
            "tekst": "\n\n".join(porazki) if porazki else f"{len(testy)} tests passed."}


def main():
    tryb, zid, plik = sys.argv[1:4]
    if tryb == "bramka-rdzen":
        out = bramka_rdzen(plik)
    else:
        z = wszystkie()[zid]
        if tryb == "bramka-python":
            out = bramka_python(z, plik)
        elif tryb == "python":
            out = tryb_python(z, plik)
        else:
            out = tryb_rdzen(z, plik)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
