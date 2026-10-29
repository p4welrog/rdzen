# SPDX-License-Identifier: MIT OR Apache-2.0
"""Potok kompilatora prototypu: parsowanie → typy → zobowiązania → Z3 →
przykłady/właściwości → diagnostyka (rozdz. 9)."""
from __future__ import annotations
import random
import copy
import zlib
import z3

from .ast import *
from .front import load
from .diag import Diagnostic, CompileError
from .vcgen import Verifier, EXPLICIT, Fx, _all_refs
from .interp import Interp, Violation, BudgetExceeded, HoleHit, Ctor, UNITV, fmt, INT_MIN, INT_MAX
from .check import RT, subst_rt
from .pp import show

CODE = {"pre": "E4010", "post": "E4020", "inv-init": "E4030", "inv-pres": "E4031",
        "var-nn": "E4040", "var-dec": "E4041", "term": "E4042", "refine": "E4050", "data-inv": "E4051",
        "assert": "E4060", "wd": "E4070", "unreach": "E4080", "bounds": "E4110",
        "overflow": "E4120", "div0": "E4130"}

MSG = {"pre": "warunek wstępny wywołania może nie zachodzić",
       "post": "warunek końcowy może nie zachodzić",
       "inv-init": "niezmiennik pętli może nie zachodzić przy wejściu",
       "inv-pres": "niezmiennik pętli może nie być zachowany",
       "var-nn": "wariant pętli może być ujemny",
       "var-dec": "wariant pętli może nie maleć",
       "term": "miara rekursji może nie maleć",
       "refine": "uściślenie typu może nie zachodzić",
       "data-inv": "konstruowana wartość może nie spełniać niezmiennika typu lub uściśleń pól",
       "assert": "asercja może nie zachodzić",
       "wd": "formuła może być nieokreślona",
       "unreach": "koniec dopasowania może być osiągalny",
       "bounds": "indeks może wykraczać poza tablicę",
       "overflow": "możliwe przepełnienie",
       "div0": "możliwe dzielenie przez zero lub przepełnienie dzielenia"}

SPEC = {"pre": ["6.4", "6.5"], "post": ["6.4", "6.6"], "inv-init": ["6.4"], "inv-pres": ["6.4", "6.6"],
        "var-nn": ["6.4"], "var-dec": ["6.4"], "term": ["6.4"], "refine": ["4.4"], "data-inv": ["4.4", "6.3"], "assert": ["6.4"],
        "wd": ["6.2"], "unreach": ["6.4"], "bounds": ["6.5", "7.3"], "overflow": ["6.5", "7.3"], "div0": ["6.5", "7.3"]}

STATUS_ORDER = {"refuted": 3, "unknown": 2, "proved": 1}


# ---------------- wartości z modelu Z3 ----------------
class NotReplayable(Exception):
    pass


def model_value(m, t, depth=0):
    v = m.eval(t, model_completion=True)
    srt = v.sort()
    if srt == z3.IntSort():
        return v.as_long()
    if srt == z3.BoolSort():
        return z3.is_true(v)
    if isinstance(srt, z3.DatatypeSortRef):
        name = srt.name()
        if name == "Unit":
            return UNITV
        if name.startswith("Arr["):
            ln = m.eval(srt.accessor(0, 0)(v), model_completion=True).as_long()
            if ln < 0 or ln > 200:
                raise NotReplayable(f"tablica długości {ln}")
            data = srt.accessor(0, 1)(v)
            return [model_value(m, z3.Select(data, i), depth + 1) for i in range(ln)]
        decl = v.decl()
        for i in range(srt.num_constructors()):
            if srt.constructor(i).name() == decl.name():
                k = srt.constructor(i).arity()
                return Ctor(decl.name(), [model_value(m, srt.accessor(i, j)(v), depth + 1) for j in range(k)])
        raise NotReplayable(str(v))
    raise NotReplayable(f"wartość typu abstrakcyjnego {srt}")


def collect_consts(exprs):
    seen, out = set(), []
    stack = list(exprs)
    visited = set()
    while stack:
        e = stack.pop()
        if e.get_id() in visited:
            continue
        visited.add(e.get_id())
        if z3.is_const(e) and e.decl().kind() == z3.Z3_OP_UNINTERPRETED:
            n = str(e)
            if n not in seen:
                seen.add(n)
                out.append(e)
        elif z3.is_quantifier(e):
            stack.append(e.body())
        else:
            stack.extend(e.children())
    return out


# ---------------- kompilacja ----------------
class Result:
    def __init__(self):
        self.diags = []
        self.obligations = []
        self.summary = {}
        self.unproved = set()       # (funkcja, klucz) zobowiązań bez dowodu
        self.checker = None


def compile_source(src: str, run_examples=True, rlimit=1_000_000) -> Result:
    res = Result()
    prog, ch, diags = load(src)
    res.diags += diags
    if prog is None or any(d.severity == "error" for d in diags):
        res.summary = {"stage": "front"}
        return res
    ver = Verifier(ch, rlimit=rlimit)
    try:
        obs = ver.run()
    except CompileError as e:
        res.diags.append(e.diag)
        return res
    res.obligations = obs
    res.checker = ch
    fns = {f.name: f for f in ch.user_fns}

    # grupowanie zobowiązań po kluczu
    groups = {}
    for o in obs:
        groups.setdefault((o.fn, o.key), []).append(o)
    counts = {"proved": 0, "unknown": 0, "refuted": 0, "refuted-inductive": 0}
    for (fn, key), lst in groups.items():
        worst = max(lst, key=lambda o: STATUS_ORDER[o.status])
        if worst.status != "proved":
            res.unproved.add((fn, key))
        if worst.status == "proved":
            counts["proved"] += 1
            continue
        if fn not in fns:          # funkcja specyfikacyjna: brak sprawdzeń dynamicznych
            counts["refuted"] += 1
            res.diags.append(spec_diag(worst, ch, ver))
            continue
        if worst.status == "unknown":
            d = falsify(worst, ch, fns[fn])
            if d is not None:
                counts["refuted"] += 1
                res.diags.append(d)
                continue
            if fns[fn].lemma:        # lematy są wymazywane — brak sprawdzeń dynamicznych
                counts["refuted"] += 1
                res.diags.append(Diagnostic(CODE[worst.kind], "error", worst.span, MSG[worst.kind], SPEC[worst.kind],
                                            obligation=_obj(worst, "unknown"),
                                            notes=["solver nie rozstrzygnął zobowiązania w lemacie; lematy są wymazywane, "
                                                   "więc każde ich zobowiązanie musi być udowodnione"],
                                            label=worst.label or f"zobowiązanie {worst.kind}: {worst.text}"))
                continue
            counts["unknown"] += 1
            res.diags.append(Diagnostic("W4200", "warning", worst.span,
                                        f"nie rozstrzygnięto zobowiązania `{worst.kind}` — w programie wykonywalnym pozostanie sprawdzenie dynamiczne",
                                        ["6.6"], obligation=_obj(worst, "unknown")))
            continue
        d, status = refuted_diag(worst, ch, ver, fns[fn])
        if fns[fn].lemma and d.severity != "error":
            d.severity, d.code, status = "error", CODE[worst.kind], "refuted"
            d.notes.append("lematy są wymazywane, więc każde ich zobowiązanie musi być udowodnione")
        counts[status] += 1
        res.diags.append(d)

    # dziury
    for e, st, ctx in ver.holes:
        res.diags.append(hole_diag(e, st, ctx, ver))

    # przykłady i właściwości
    ex_stats = {"passed": 0, "failed": 0}
    if run_examples:
        for f in ch.user_fns:
            for ex in f.examples:
                d = run_example(f, ex, ch, src)
                if d is None:
                    ex_stats["passed"] += 1
                else:
                    if d.severity == "error":
                        ex_stats["failed"] += 1
                    res.diags.append(d)
    res.summary = {"obligations": counts, "examples": ex_stats, "holes": len(ver.holes)}
    res.diags.sort(key=lambda d: d.sort_key())
    return res


def _obj(o, status):
    return {"id": f"{o.fn}/{o.kind}@{o.span.line}:{o.span.col}", "kind": o.kind, "formula": o.text, "status": status}


def refuted_diag(o, ch, ver, fdecl):
    m = o.model
    sig = fdecl.sig
    assignment, descriptions = {}, {}
    replay = "not-replayable"
    vals = []
    try:
        for (pn, pt, pinout) in sig.params:
            vals.append(model_value(m, z3.Const(pn, ver.enc.sort(pt))))
        for (pn, pt, _), v in zip(sig.params, vals):
            assignment[pn] = fmt_t(v, pt, ch)
        it = Interp(ch, budget=500_000)
        try:
            it.call_fn(sig, vals, None, check_pre=False)
            replay = "not-reproduced"
        except Violation as v:
            replay = "confirmed" if v.key == o.key else "not-reproduced"
        except (BudgetExceeded, HoleHit, RecursionError):
            replay = "not-replayable"
    except NotReplayable:
        for (pn, pt, pinout) in sig.params:
            try:
                assignment[pn] = raw_value(m, z3.Const(pn, ver.enc.sort(pt)), pt, ch)
            except Exception:
                pass
    # parametry funkcyjne: wartości w punktach zastosowania
    for (pn, pt, _) in sig.params:
        if pt.kind == "Fn":
            assignment[pn] = fn_table(m, z3.Const(pn, ver.enc.sort(pt)), list(o.pc) + [o.phi])
    # dodatkowe stałe (havoc, wyniki wywołań)
    havoc_vars = {}
    in_goal = {str(c) for c in collect_consts([o.phi])}
    for c in collect_consts(list(o.pc) + [o.phi]):
        n = str(c)
        if n in ver.desc and ("!c" in n or "!v" in n) and n not in in_goal:
            continue        # zmienne pomocnicze innych zobowiązań funkcyjnych
        if n in ver.desc:
            disp, desc = ver.desc[n]
            try:
                val = fmt(model_value(m, c))
            except NotReplayable:
                val = raw_value(m, c, None, ch)
            key = disp
            while key in assignment:
                key += "'"
            assignment[key] = val
            descriptions[key] = desc
            if desc.startswith("po pętli z wiersza"):
                havoc_vars.setdefault(int(desc.split()[-1]), set()).add(disp)
    real = (not o.inductive) or replay == "confirmed"
    cls = "real" if real else "inductive"
    explicit = o.kind in EXPLICIT
    if real or explicit:
        sev, code, status = "error", CODE[o.kind], "refuted"
        msg = MSG[o.kind]
    else:
        sev, code, status = "warning", "W4400", "refuted-inductive"
        msg = MSG[o.kind] + " (kontrprzykład indukcyjny) — pozostaje sprawdzenie dynamiczne"
    notes = []
    if not real:
        if replay == "not-reproduced":
            notes.append("odtworzenie: wykonanie na wartościach parametrów z kontrprzykładu nie narusza zobowiązania")
        for line, ws in sorted(havoc_vars.items()):
            invs = ver.loops_by_line.get(line, [])
            mentioned = {n.name for inv in invs for n in walk(inv) if isinstance(n, Name)}
            missing = sorted(w for w in ws if w not in mentioned and w != "it")
            if missing:
                notes.append(f"przyczyna: pętla z wiersza {line} zapisuje {', '.join('`'+w+'`' for w in missing)}, "
                             f"a jej niezmiennik nic o {'nich' if len(missing) > 1 else 'tej zmiennej'} nie mówi")
        if any(d.startswith("wynik wywołania") for d in descriptions.values()):
            notes.append("hipotezy pochodzą też z warunków końcowych wywoływanych funkcji — mogą być za słabe")
    if o.site != o.span and o.kind in ("post", "pre", "refine"):
        notes.append(f"miejsce: wiersz {o.site.line}, kolumna {o.site.col}")
    d = Diagnostic(code, sev, o.span, msg, SPEC[o.kind],
                   obligation=_obj(o, status),
                   counterexample={"assignment": assignment, "descriptions": descriptions,
                                   "class": cls, "replay": replay},
                   notes=notes, label=o.label or f"zobowiązanie {o.kind}: {o.text}")
    return d, status


def fn_table(m, f, exprs):
    """Funkcja z modelu jako tabela wartości w punktach, w których program ją stosuje."""
    pts, stack, seen = {}, list(exprs), set()
    while stack:
        e = stack.pop()
        if e.get_id() in seen:
            continue
        seen.add(e.get_id())
        if z3.is_quantifier(e):
            continue
        if z3.is_app(e):
            if e.decl().kind() == z3.Z3_OP_SELECT and e.arg(0).eq(f):
                xs = tuple(str(m.eval(e.arg(i), model_completion=True)) for i in range(1, e.num_args()))
                pts[xs] = str(m.eval(e, model_completion=True))
            stack.extend(e.children())
    if not pts:
        return "‹dowolna funkcja danego typu›"
    items = sorted(pts.items(), key=lambda kv: [int(x) if x.lstrip("-").isdigit() else x for x in kv[0]])
    return "{" + ", ".join(f"{', '.join(k)} ↦ {v}" for k, v in items) + ", …}"


def raw_value(m, c, rt, ch):
    """Wartość z modelu, której nie da się odtworzyć (np. bardzo długa tablica)."""
    try:
        return fmt_t(model_value(m, c), rt, ch)
    except NotReplayable:
        srt = c.sort()
        if isinstance(srt, z3.DatatypeSortRef) and srt.name().startswith("Arr["):
            ln = m.eval(srt.accessor(0, 0)(c), model_completion=True)
            return f"‹tablica o długości {ln}›"
        return str(m.eval(c, model_completion=True))


def fmt_t(v, rt, ch):
    """Wartość z uwzględnieniem typu: `Str` (tablica bajtów UTF-8) jako literał napisowy."""
    br = getattr(ch, "byte_ref", None)
    if (rt is not None and rt.kind == "Array" and br is not None and rt.args[0].kind == "Int"
            and any(r is br for r in rt.args[0].refs) and isinstance(v, list)
            and all(isinstance(x, int) and 0 <= x < 256 for x in v)):
        try:
            text = bytes(v).decode("utf-8")
            if all(ch_.isprintable() or ch_ in "\n\t\r" for ch_ in text):
                esc = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
                return f'"{esc}"'
        except UnicodeDecodeError:
            pass
    return fmt(v)


def falsify(o, ch, fdecl, tries=300):
    """Zobowiązanie nierozstrzygnięte przez solver: próba obalenia testowaniem losowym
    (wejścia spełniające warunki wstępne, wykonanie w interpreterze ze sprawdzeniami)."""
    sig = fdecl.sig
    if sig.tparams:
        return None
    rng = random.Random(zlib.crc32(f"{o.fn}/{o.key}".encode()))
    binders = [(pn, pt) for pn, pt, _ in sig.params]

    def failing(env):
        try:
            Interp(ch, budget=200_000).call_fn(sig, [copy.deepcopy(env[pn]) for pn, _ in binders], None)
        except Violation as v:
            if v.key == o.key:
                return f"naruszenie `{v.kind}` w wierszu {v.span.line}"
            return False
        except (BudgetExceeded, HoleHit, RecursionError):
            return False
        return False

    for case in range(tries):
        env = {}
        for pn, pt in binders:
            v = gen_value(ch, pt, rng, env)
            if v is _FAIL:
                break
            env[pn] = v
        if len(env) != len(binders):
            continue
        if failing(env):
            env = shrink(ch, binders, env, failing)
            return Diagnostic(CODE[o.kind], "error", o.span, MSG[o.kind], SPEC[o.kind],
                              obligation=_obj(o, "refuted"),
                              counterexample={"assignment": {n: fmt_t(v, dict(binders)[n], ch) for n, v in env.items()},
                                              "descriptions": {}, "class": "real", "replay": "confirmed"},
                              notes=["solver nie rozstrzygnął zobowiązania; kontrprzykład znaleziono testowaniem losowym "
                                     f"(przypadek {case + 1} z {tries})"],
                              label=o.label or f"zobowiązanie {o.kind}: {o.text}")
    return None


def spec_diag(o, ch, ver):
    sf = ch.specs[o.fn]
    code = {"term": "E4043", "post": "E4020"}.get(o.kind, "E4070")
    msg = {"term": "miara rekurencyjnej funkcji specyfikacyjnej może nie maleć",
           "post": "wynik funkcji specyfikacyjnej może nie spełniać uściślenia typu"}.get(
        o.kind, "ciało funkcji specyfikacyjnej może być nieokreślone")
    assignment = {}
    if o.model is not None:
        for pn, pt, _ in sf.rparams:
            try:
                assignment[pn] = fmt(model_value(o.model, z3.Const(pn, ver.enc.sort(pt))))
            except NotReplayable:
                pass
    notes = ["funkcje specyfikacyjne nie mają sprawdzeń dynamicznych — zobowiązanie musi być udowodnione"]
    if o.status == "unknown":
        notes.insert(0, "solver nie rozstrzygnął zobowiązania")
    ce = {"assignment": assignment, "descriptions": {}, "class": "real", "replay": "not-replayable"} if assignment else None
    return Diagnostic(code, "error", o.span, msg, ["6.1"], obligation=_obj(o, o.status),
                      counterexample=ce, notes=notes, label=f"zobowiązanie {o.kind}: {o.text}")


def hole_diag(e, st, ctx, ver):
    env = st.env
    ctxlist = [{"name": k, "type": str(st.tys.get(k).bare()) if st.tys.get(k) else "?", "mutable": False}
               for k in env if k in st.tys]
    goal_text = "niedostępny — w prototypie cel jest wyznaczany tylko dla dziur w pozycji wyniku funkcji"
    cands = []
    if getattr(e, "tail", False) and ctx is not None:
        decl, sig = ctx.decl, ctx.sig
        clauses = []
        for r in _all_refs(sig.ret):
            clauses.append(("ref", r))
        for q in decl.ensures:
            for c in _conjuncts(q):
                clauses.append(("ens", c))
        if clauses:
            goal_text = " && ".join(show(c, {"self": "ν", "result": "ν"}) for _, c in clauses)
        else:
            goal_text = f"dowolna wartość typu {e.ty}"
        for k, v in env.items():
            t = st.tys.get(k)
            if t is None or t.bare().shape() != e.ty.bare().shape():
                continue
            failing = []
            for kind, c in clauses:
                if kind == "ref":
                    phi, _ = ver.tr(c, env, Fx(self_=v))
                else:
                    phi, _ = ver.tr(c, env, Fx(result=v, old=ctx.old))
                if not ver.check_valid(st.pc, phi):
                    failing.append(c)
            if not failing:
                cands.append({"expr": k, "status": "satisfies"})
            elif len(failing) < len(clauses) or not clauses:
                cond = " && ".join(show(c, {"self": k, "result": k}) for c in failing)
                cands.append({"expr": k, "status": "satisfies-if", "condition": cond})
    goal = {"type": str(e.ty), "goal": goal_text, "hypotheses": list(st.facts),
            "context": ctxlist, "effects": "∅", "candidates": cands}
    return Diagnostic("H7001", "hole", e.span, f"?{e.name} : {e.ty}", ["6.4", "9.5"], goal=goal)


def _conjuncts(e):
    if isinstance(e, Binary) and e.op == "&&":
        return _conjuncts(e.left) + _conjuncts(e.right)
    return [e]


# ---------------- przykłady ----------------
def run_example(f, ex, ch, src):
    it = Interp(ch, budget=1_000_000)
    if ex.binders is None:
        try:
            v = it.ev(ex.expr, {})
        except Violation as viol:
            return Diagnostic("E4300", "error", ex.span, "przykład narusza kontrakt podczas obliczania", ["4.5"],
                              notes=[f"naruszenie `{viol.kind}` w wierszu {viol.span.line}" + (f": {viol.detail}" if viol.detail else "")])
        except BudgetExceeded:
            return Diagnostic("W4301", "warning", ex.span, "przykład przekroczył budżet kroków", ["4.5"])
        except HoleHit as h:
            return Diagnostic("I4302", "info", ex.span, f"przykład pominięty: program zawiera dziurę `?{h.name}`", ["4.5"])
        if v is True:
            return None
        notes = []
        if isinstance(ex.expr, Binary) and ex.expr.op in ("==", "!="):
            try:
                notes.append(f"lewa strona:  {fmt(Interp(ch).ev(ex.expr.left, {}))}")
                notes.append(f"prawa strona: {fmt(Interp(ch).ev(ex.expr.right, {}))}")
            except Exception:
                pass
        return Diagnostic("E4300", "error", ex.span, "przykład nie zachodzi", ["4.5"], notes=notes)
    # test właściwości
    seed = zlib.crc32((f.name + "\n" + show(ex.expr)).encode())
    rng = random.Random(seed)
    binders = [(n, ch.resolve(t, [])) for n, t in ex.binders]

    def failing(env):
        try:
            return not Interp(ch, budget=200_000).ev(ex.expr, dict(env))
        except Violation as viol:
            return f"naruszenie `{viol.kind}` w wierszu {viol.span.line}"
        except (BudgetExceeded, HoleHit, RecursionError):
            return False

    for case in range(256):
        env = {}
        ok = True
        for n, t in binders:
            v = gen_value(ch, t, rng, env)
            if v is _FAIL:
                ok = False
                break
            env[n] = v
        if not ok:
            continue
        fr = failing(env)
        if fr:
            env = shrink(ch, binders, env, failing)
            fr = failing(env)
            notes = [f"przypadek {case + 1} z 256, ziarno {seed}"]
            if isinstance(fr, str):
                notes.append(fr)
            return Diagnostic("E4310", "error", ex.span, "test właściwości znalazł kontrprzykład", ["4.5"],
                              counterexample={"assignment": {n: fmt_t(v, dict(binders)[n], ch) for n, v in env.items()},
                                              "descriptions": {},
                                              "class": "real", "replay": "confirmed"},
                              notes=notes)
    return None


_FAIL = object()
INT_POOL = [0, 1, -1, 2, -2, 3, 7, 10, -10, 100, INT_MAX, INT_MIN]


def gen_value(ch, rt: RT, rng, env, depth=0):
    it = Interp(ch)
    for _ in range(50):
        v = _gen(ch, rt, rng, depth)
        try:
            if it.check_type(v, rt, env):
                return v
        except Exception:
            pass
    return _FAIL


def _gen(ch, rt, rng, depth):
    k = rt.kind
    if k == "Int":
        r = rng.random()
        if rt.refs and r < 0.6:      # typy uściślone (np. Byte, Nat): wartości nieujemne i znaki ASCII
            return rng.choice([rng.randint(0, 255), rng.choice(b"aZz09 _\n"), rng.randint(0, 10)])
        if r < 0.5:
            return rng.choice(INT_POOL[:10])
        if r < 0.9:
            return rng.randint(-20, 20)
        return rng.choice(INT_POOL)
    if k == "Bool":
        return rng.random() < 0.5
    if k == "Unit":
        return UNITV
    if k == "Array":
        n = rng.randint(0, 6 if depth == 0 else 3)
        return [_gen(ch, rt.args[0], rng, depth + 1) for _ in range(n)]
    if k == "Data":
        d = ch.data[rt.name]
        s = dict(zip(d.tparams, rt.args))
        ctors = d.rctors
        if depth > 3:
            ctors = [c for c in ctors if all(subst_rt(ft, s).bare().shape() != rt.bare().shape() for _, ft in c[1])] or ctors
        cname, fields = rng.choice(ctors)
        return Ctor(cname, [_gen(ch, subst_rt(ft, s), rng, depth + 1) for _, ft in fields])
    return _FAIL     # np. typy funkcyjne — brak generatora


def shrink(ch, binders, env, failing):
    types = dict(binders)
    for _ in range(200):
        improved = False
        for n in list(env):
            for cand in _shrinks(env[n]):
                e2 = dict(env)
                e2[n] = cand
                try:
                    if not Interp(ch).check_type(cand, types[n], e2):
                        continue
                except Exception:
                    continue
                if failing(e2):
                    env = e2
                    improved = True
                    break
        if not improved:
            break
    return env


def _shrinks(v):
    if isinstance(v, bool):
        return [False] if v else []
    if isinstance(v, int):
        out = []
        if v != 0:
            out.append(0)
            out.append(v // 2 if v > 0 else -((-v) // 2))
            out.append(v - 1 if v > 0 else v + 1)
        return [x for x in out if x != v]
    if isinstance(v, list):
        out = []
        for i in range(len(v)):
            out.append(v[:i] + v[i + 1:])
        for i in range(len(v)):
            for s in _shrinks(v[i]):
                out.append(v[:i] + [s] + v[i + 1:])
        return out
    if isinstance(v, Ctor):
        out = [fv for fv in v.fields if isinstance(fv, Ctor)]     # zastąpienie poddrzewem
        for i, fv in enumerate(v.fields):
            for s in _shrinks(fv):
                f2 = list(v.fields)
                f2[i] = s
                out.append(Ctor(v.name, f2))
        return out
    return []
