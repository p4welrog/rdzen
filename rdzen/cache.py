# SPDX-License-Identifier: MIT OR Apache-2.0
"""Pamięć wyników weryfikacji między uruchomieniami `rzc check` (zalecenie K2 ze studium Huffmana).

Zapamiętywane są wyłącznie jednostki (funkcje, lematy, rekurencyjne `spec fn`), których wszystkie
zobowiązania zostały udowodnione i które nie zawierają dziur. Klucz obejmuje wszystko, od czego
zależą zobowiązania jednostki:
- pełny tekst jednostki;
- tekst wszystkich deklaracji poza ciałami funkcji (typy, aliasy, stałe, `spec fn`) oraz nagłówki
  i kontrakty wszystkich funkcji (wywołania są modularne — ciało wywoływanej funkcji nie wpływa
  na zobowiązania wywołującej);
- silnie spójną składową grafu wywołań jednostki (decyduje o zobowiązaniach `term`);
- wersję kompilatora (skrót plików `rdzen/*.py` i preludium), wersję Z3, `rlimit` i przełączniki
  środowiska wpływające na rozstrzyganie (`RZ_NO_UF`).
Przykłady (`examples`) zależą od ciał wywoływanych funkcji i są zawsze wykonywane ponownie.

Poprawność: zapamiętywany jest tylko wynik „udowodnione”, a dowód (sprzeczność zanegowanego
zobowiązania z hipotezami) nie zależy od tego, które inne funkcje sprawdzano w tym samym
przebiegu. Od tego zależą natomiast nazwy zmiennych pomocniczych, więc dla zobowiązań na granicy
limitu solvera przebieg częściowy (z pamięcią albo `--fn`) może sklasyfikować niedowiedzione
zobowiązanie inaczej niż pełny (np. „obalone” zamiast „nieznane”) albo zgłosić dodatkowy błąd
w funkcji, która już ma błąd. Program poprawny w pełnym przebiegu jest poprawny także w częściowym
i odwrotnie (tests/cache_test.py, porównanie na mutantach `huffman.rz`)."""
from __future__ import annotations
import glob
import hashlib
import json
import os
import z3
from .ast import FnDecl

_HERE = os.path.dirname(os.path.abspath(__file__))


def _compiler_hash():
    h = hashlib.sha256()
    for p in sorted(glob.glob(os.path.join(_HERE, "*.py")) + [os.path.join(_HERE, "prelude.rz")]):
        h.update(os.path.basename(p).encode())
        with open(p, "rb") as fh:
            h.update(fh.read())
    h.update(z3.get_version_string().encode())
    return h.hexdigest()


class VerifCache:
    def __init__(self, src: str, rlimit: int, directory=None):
        self.dir = directory or os.environ.get("RZ_CACHE") or os.path.join(
            os.path.expanduser("~"), ".cache", "rzc")
        os.makedirs(self.dir, exist_ok=True)
        self.lines = src.split("\n")
        self.base = None
        self.rlimit = rlimit
        self.hits = self.misses = 0

    def text(self, line, end_line):
        return "\n".join(self.lines[line - 1:end_line])

    def context(self, ver):
        """Wspólna część klucza: deklaracje poza ciałami funkcji i nagłówki/kontrakty funkcji."""
        if self.base is None:
            h = hashlib.sha256()
            h.update(_compiler_hash().encode())
            h.update(f"rlimit={self.rlimit};uf={os.environ.get('RZ_NO_UF', '')}".encode())
            for it in ver.ch.user_items:
                if isinstance(it, FnDecl):
                    h.update(b"\x00fn\x00" + self.text(it.span.line, it.body.span.line).encode())
                else:
                    h.update(b"\x00it\x00" + self.text(it.span.line, it.span.end_line).encode())
            self.base = h.hexdigest()
        return self.base

    def key(self, ver, name, node):
        h = hashlib.sha256()
        h.update(self.context(ver).encode())
        h.update(name.encode())
        h.update(self.text(node.span.line, node.span.end_line).encode())
        scc = ver.ch.scc.get(name) if isinstance(node, FnDecl) else ver.ch.spec_scc.get(name)
        h.update(",".join(sorted(scc or ())).encode())
        return h.hexdigest()

    def _path(self, key):
        return os.path.join(self.dir, key[:2], key + ".json")

    def get(self, key):
        try:
            with open(self._path(key)) as fh:
                n = json.load(fh)["proved"]
            self.hits += 1
            return n
        except (OSError, ValueError, KeyError):
            self.misses += 1
            return None

    def put(self, key, proved):
        p = self._path(key)
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            tmp = p + f".{os.getpid()}.tmp"
            with open(tmp, "w") as fh:
                json.dump({"proved": proved}, fh)
            os.replace(tmp, p)
        except OSError:
            pass
