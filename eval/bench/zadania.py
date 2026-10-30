# SPDX-License-Identifier: MIT OR Apache-2.0
"""Definicja zadania ewaluacji, język typów i konwersje wartości.

Wartość neutralna (używana przez wyrocznie, generatory i porównania):
  Int, Nat      → int
  Bool          → bool
  Str           → str (UTF-8)
  Array<T>      → list
  Option<T>     → None albo wartość T
  dane w formie "lista" (Nil/Cons)    → list
  dane w formie "rekord" (1 konstruktor) → tuple pól
  dane w formie "znaczniki"           → ("Konstruktor", pole1, …)
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

# ---------- typy ----------


@dataclass(frozen=True)
class Ty:
    name: str
    args: tuple = ()

    def __str__(self):
        return self.name + (f"<{', '.join(map(str, self.args))}>" if self.args else "")


def parse_ty(s: str) -> Ty:
    s = s.replace(" ", "")
    pos = 0

    def go():
        nonlocal pos
        k = pos
        while pos < len(s) and (s[pos].isalnum() or s[pos] == "_"):
            pos += 1
        name = s[k:pos]
        args = []
        if pos < len(s) and s[pos] == "<":
            pos += 1
            args.append(go())
            while s[pos] == ",":
                pos += 1
                args.append(go())
            assert s[pos] == ">", s
            pos += 1
        return Ty(name, tuple(args))

    t = go()
    assert pos == len(s), s
    return t


@dataclass
class Dane:
    """Typ danych podany w treści zadania: konstruktory z nazwanymi polami."""
    nazwa: str
    konstruktory: list            # [(nazwa, [(pole, typ), …]), …]
    forma: str                    # "lista" | "rekord" | "znaczniki"

    def rdzen(self) -> str:
        cs = []
        for c, fs in self.konstruktory:
            cs.append(c + (f"({', '.join(f'{f}: {t}' for f, t in fs)})" if fs else ""))
        return f"data {self.nazwa} {{ {', '.join(cs)} }}"

    def python(self) -> str:
        out = []
        for c, fs in self.konstruktory:
            out.append("@dataclass(frozen=True)")
            out.append(f"class {c}:")
            if not fs:
                out.append("    pass")
            for f, t in fs:
                out.append(f"    {f}: {py_ann(parse_ty(t), {})}")
        return "\n".join(out)


PY_PRIM = {"Int": "int", "Nat": "int", "Bool": "bool", "Str": "str"}


def py_ann(t: Ty, dane: dict) -> str:
    if t.name in PY_PRIM:
        return PY_PRIM[t.name]
    if t.name == "Array":
        return f"list[{py_ann(t.args[0], dane)}]"
    if t.name == "Option":
        return f"{py_ann(t.args[0], dane)} | None"
    d = dane.get(t.name)
    if d is not None and d.forma == "lista":
        el = dict(d.konstruktory)["Cons"][0][1]
        return f"list[{py_ann(parse_ty(el), dane)}]"
    if d is not None and d.forma == "rekord":
        return "tuple[" + ", ".join(py_ann(parse_ty(ft), dane) for _, ft in d.konstruktory[0][1]) + "]"
    if d is not None:
        return d.nazwa                # alias `Nazwa = K1 | K2 | …` z preambuły
    return f"'{t.name}'"


# ---------- zadanie ----------


@dataclass
class Zadanie:
    id: str
    tytul: str
    opis: str                         # opis neutralny (język naturalny, angielski)
    funkcja: str                      # nazwa funkcji wejściowej
    parametry: list                   # [(nazwa, typ Rdzenia), …]
    wynik: str                        # typ Rdzenia
    wyrocznia: Callable               # wartości neutralne → oczekiwany wynik
    generator: Callable               # random.Random → krotka argumentów (poprawne wejście)
    brzegowe: list                    # lista krotek argumentów
    dziedzina: str = ""               # zdanie o dziedzinie wejść dołączane do opisu
    dane: list = field(default_factory=list)       # [Dane, …]
    sprawdz: Callable | None = None   # (args, wynik) → bool, gdy poprawnych wyników jest wiele
    zrodlo: str = ""                  # np. "VeraBench VB-T3-001"
    testy_zrodla: list = field(default_factory=list)   # [(args, expected)] z VeraBench
    tagi: list = field(default_factory=list)
    n_losowych: int = 200

    # --- pomocnicze ---
    @property
    def dane_map(self):
        return {d.nazwa: d for d in self.dane}

    def opis_pelny(self) -> str:
        return self.opis + (" " + self.dziedzina if self.dziedzina else "")

    def sygnatura_rdzen(self) -> str:
        ps = ", ".join(f"{n}: {t}" for n, t in self.parametry)
        return f"fn {self.funkcja}({ps}) -> {self.wynik}"

    def sygnatura_python(self) -> str:
        dm = self.dane_map
        ps = ", ".join(f"{n}: {py_ann(parse_ty(t), dm)}" for n, t in self.parametry)
        return f"def {self.funkcja}({ps}) -> {py_ann(parse_ty(self.wynik), dm)}"

    def python_preambula(self) -> str:
        """Klasy danych w formie 'znaczniki' dostępne w rozwiązaniu Pythona."""
        zn = [d for d in self.dane if d.forma == "znaczniki"]
        if not zn:
            return ""
        aliasy = "\n".join(f"{d.nazwa} = {' | '.join(c for c, _ in d.konstruktory)}" for d in zn)
        return "from dataclasses import dataclass\n\n" + "\n\n".join(d.python() for d in zn) + "\n\n" + aliasy + "\n"

    def przypadki(self, ziarno: int = 0) -> list:
        """Testy ukryte: brzegowe, ze źródła, potem losowe (deterministyczne)."""
        out, seen = [], set()

        def add(a):
            k = repr(a)
            if k not in seen:
                seen.add(k)
                out.append(tuple(a))

        for a in self.brzegowe:
            add(a)
        for a, _ in self.testy_zrodla:
            add(a)
        rng = random.Random(f"{self.id}/{ziarno}")
        for _ in range(self.n_losowych * 3):
            if len(out) >= len(self.brzegowe) + len(self.testy_zrodla) + self.n_losowych:
                break
            add(self.generator(rng))
        return out

    def poprawny(self, args, wynik) -> bool:
        if self.sprawdz is not None:
            return self.sprawdz(args, wynik)
        return rowne(wynik, self.wyrocznia(*args))


def rowne(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return type(a) is type(b) and len(a) == len(b) and all(rowne(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


# ---------- konwersje: neutralna ↔ moduł Pythona z `rzc emit` ----------


def do_modulu(v, t: Ty, mod, dane: dict):
    n = t.name
    if n in ("Int", "Nat", "Bool"):
        return v
    if n == "Str":
        return list(v.encode("utf-8"))
    if n == "Array":
        return [do_modulu(x, t.args[0], mod, dane) for x in v]
    if n == "Option":
        return mod.None_() if v is None else mod.Some(do_modulu(v, t.args[0], mod, dane))
    d = dane[n]
    if d.forma == "lista":
        el = parse_ty(dict(d.konstruktory)["Cons"][0][1])
        acc = getattr(mod, "Nil")()
        for x in reversed(v):
            acc = getattr(mod, "Cons")(do_modulu(x, el, mod, dane), acc)
        return acc
    if d.forma == "rekord":
        c, fs = d.konstruktory[0]
        return getattr(mod, c)(*[do_modulu(x, parse_ty(ft), mod, dane) for x, (_, ft) in zip(v, fs)])
    c, *pola = v
    fs = dict(d.konstruktory)[c]
    return getattr(mod, c)(*[do_modulu(x, parse_ty(ft), mod, dane) for x, (_, ft) in zip(pola, fs)])


class ZlyWynik(Exception):
    pass


def z_modulu(v, t: Ty, dane: dict):
    n = t.name
    if n in ("Int", "Nat"):
        if type(v) is not int:
            raise ZlyWynik(f"oczekiwano Int, jest {v!r}")
        return v
    if n == "Bool":
        if type(v) is not bool:
            raise ZlyWynik(f"oczekiwano Bool, jest {v!r}")
        return v
    if n == "Str":
        try:
            return bytes(v).decode("utf-8")
        except (UnicodeDecodeError, ValueError, TypeError) as e:
            raise ZlyWynik(f"napis nie jest poprawnym UTF-8: {e}")
    if n == "Array":
        return [z_modulu(x, t.args[0], dane) for x in v]
    cname = type(v).__name__
    if n == "Option":
        if cname == "None_":
            return None
        return z_modulu(v.value, t.args[0], dane)
    d = dane[n]
    if d.forma == "lista":
        el = parse_ty(dict(d.konstruktory)["Cons"][0][1])
        out = []
        while type(v).__name__ == "Cons":
            out.append(z_modulu(getattr(v, v._fields[0]), el, dane))
            v = getattr(v, v._fields[1])
        return out
    fs = dict(d.konstruktory)[cname.rstrip("_")]
    pola = [z_modulu(getattr(v, f), parse_ty(ft), dane) for f, ft in fs]
    if d.forma == "rekord":
        return tuple(pola)
    return (cname.rstrip("_"), *pola)


# ---------- konwersje: neutralna → wartości interpretera (sprawdzanie `requires`) ----------


def do_interp(v, t: Ty, dane: dict):
    from rdzen.interp import Ctor
    n = t.name
    if n in ("Int", "Nat", "Bool"):
        return v
    if n == "Str":
        return list(v.encode("utf-8"))
    if n == "Array":
        return [do_interp(x, t.args[0], dane) for x in v]
    if n == "Option":
        return Ctor("None", []) if v is None else Ctor("Some", [do_interp(v, t.args[0], dane)])
    d = dane[n]
    if d.forma == "lista":
        el = parse_ty(dict(d.konstruktory)["Cons"][0][1])
        acc = Ctor("Nil", [])
        for x in reversed(v):
            acc = Ctor("Cons", [do_interp(x, el, dane), acc])
        return acc
    if d.forma == "rekord":
        c, fs = d.konstruktory[0]
        return Ctor(c, [do_interp(x, parse_ty(ft), dane) for x, (_, ft) in zip(v, fs)])
    c, *pola = v
    fs = dict(d.konstruktory)[c]
    return Ctor(c, [do_interp(x, parse_ty(ft), dane) for x, (_, ft) in zip(pola, fs)])


# ---------- konwersje: neutralna ↔ rozwiązanie w Pythonie ----------


def do_pythona(v, t: Ty, ns: dict, dane: dict):
    n = t.name
    if n in ("Int", "Nat", "Bool", "Str"):
        return v
    if n == "Array":
        return [do_pythona(x, t.args[0], ns, dane) for x in v]
    if n == "Option":
        return None if v is None else do_pythona(v, t.args[0], ns, dane)
    d = dane[n]
    if d.forma == "lista":
        el = parse_ty(dict(d.konstruktory)["Cons"][0][1])
        return [do_pythona(x, el, ns, dane) for x in v]
    if d.forma == "rekord":
        return tuple(do_pythona(x, parse_ty(ft), ns, dane) for x, (_, ft) in zip(v, d.konstruktory[0][1]))
    c, *pola = v
    fs = dict(d.konstruktory)[c]
    return ns[c](*[do_pythona(x, parse_ty(ft), ns, dane) for x, (_, ft) in zip(pola, fs)])


def z_pythona(v, t: Ty, dane: dict):
    n = t.name
    if n in ("Int", "Nat"):
        if type(v) is not int:
            raise ZlyWynik(f"oczekiwano int, jest {v!r}")
        return v
    if n == "Bool":
        if type(v) is not bool:
            raise ZlyWynik(f"oczekiwano bool, jest {v!r}")
        return v
    if n == "Str":
        if type(v) is not str:
            raise ZlyWynik(f"oczekiwano str, jest {v!r}")
        return v
    if n == "Array":
        if not isinstance(v, list):
            raise ZlyWynik(f"oczekiwano list, jest {type(v).__name__}")
        return [z_pythona(x, t.args[0], dane) for x in v]
    if n == "Option":
        return None if v is None else z_pythona(v, t.args[0], dane)
    d = dane[n]
    if d.forma == "lista":
        el = parse_ty(dict(d.konstruktory)["Cons"][0][1])
        if not isinstance(v, list):
            raise ZlyWynik(f"oczekiwano list, jest {type(v).__name__}")
        return [z_pythona(x, el, dane) for x in v]
    if d.forma == "rekord":
        fs = d.konstruktory[0][1]
        if not isinstance(v, tuple) or len(v) != len(fs):
            raise ZlyWynik(f"oczekiwano krotki {len(fs)} pól, jest {v!r}")
        return tuple(z_pythona(x, parse_ty(ft), dane) for x, (_, ft) in zip(v, fs))
    cname = type(v).__name__
    fs = dict(d.konstruktory).get(cname)
    if fs is None:
        raise ZlyWynik(f"nieznany konstruktor {cname}")
    return (cname, *[z_pythona(getattr(v, f), parse_ty(ft), dane) for f, ft in fs])


# ---------- rejestr ----------

ZADANIA: dict[str, Zadanie] = {}


def zadanie(**kw) -> Zadanie:
    z = Zadanie(**kw)
    assert z.id not in ZADANIA, z.id
    ZADANIA[z.id] = z
    return z


def wszystkie() -> dict[str, Zadanie]:
    from . import zestaw_a, zestaw_b  # noqa: F401  (rejestracja)
    return ZADANIA
