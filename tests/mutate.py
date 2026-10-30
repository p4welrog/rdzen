# SPDX-License-Identifier: MIT OR Apache-2.0
"""Testy mutacyjne: zmienia pojedyncze operatory w ciałach funkcji (nie w kontraktach)
i sprawdza, czy kompilator odrzuca program (błąd) albo przykład/test właściwości go wyłapuje."""
import re, sys, os, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rdzen.driver import compile_source

SWAPS = [(" + 1", " - 1"), (" - 1", " + 1"), (" < ", " <= "), (" <= ", " < "), (" > ", " >= "),
         (" >= ", " > "), (" + ", " - "), ("mid + 1", "mid")]
CONTRACT = re.compile(r"^\s*(requires|ensures|invariant|decreases|spec|examples|forall|//)")

def mutants(src):
    lines = src.split("\n")
    in_ex = False
    for i, l in enumerate(lines):
        if l.strip().startswith("examples"):
            in_ex = True
        if in_ex:
            if l.strip() == "}":
                in_ex = False
            continue
        if CONTRACT.match(l) or l.startswith("spec") or "forall" in l:
            continue
        for a, b in SWAPS:
            start = 0
            while True:
                k = l.find(a, start)
                if k < 0:
                    break
                ml = l[:k] + b + l[k + len(a):]
                yield i + 1, f"{a.strip()} → {b.strip()}", "\n".join(lines[:i] + [ml] + lines[i + 1:])
                start = k + 1

def main(paths):
    total = killed = 0
    for p in sorted(paths):
        src = open(p).read()
        for line, desc, m in mutants(src):
            total += 1
            r = compile_source(m, canon=False)   # mutant nie musi być kanoniczny
            if any(d.severity == "error" for d in r.diags):
                killed += 1
            else:
                print(f"PRZEŻYŁ  {os.path.basename(p)}:{line}  {desc}")
    print(f"mutanty: {total}, zabite: {killed}")


if __name__ == "__main__":
    main(sys.argv[1:])
