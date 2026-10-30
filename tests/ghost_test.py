# SPDX-License-Identifier: MIT OR Apache-2.0
"""Kod widmowy nie trafia do kodu wynikowego: kopie stanu czytane wyłącznie przez lematy
i udowodnione asercje oraz `old(..)` użyte tylko w udowodnionych `ensures` nie są emitowane
(ani w C, ani w Pythonie). Z RLIMIT=1 asercje stają się dynamiczne — wtedy kopie muszą zostać."""
import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rdzen.driver import compile_source
from rdzen.emit_c import emit_c
from rdzen.emit_py import emit as emit_py

CASE = os.path.join(os.path.dirname(__file__), "cases", "ghost_copy.rz")


def main():
    src = open(CASE).read()
    ok = True
    # (rlimit, czy `old(out)` ma zostać skopiowane): przy RLIMIT=1 `ensures` jest sprawdzane
    # dynamicznie i potrzebuje kopii; `snapshot` czyta tylko lemat — nie istnieje nigdy.
    for rlimit, want_old in ((1_000_000, False), (1, True)):
        res = compile_source(src, rlimit=rlimit)
        for name, code in (("c", emit_c(res, "ghost_copy.rz")), ("py", emit_py(res, "ghost_copy.rz"))):
            snap = bool(re.search(r"snapshot\w*\s*=", code))
            old = "_old_" in code
            passed = not snap and old == want_old
            print(f"{'PASS' if passed else 'FAIL'}  {name:3} rlimit={rlimit:<8} snapshot={snap} old={old}")
            ok &= passed
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
