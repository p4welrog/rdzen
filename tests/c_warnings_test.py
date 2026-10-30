# SPDX-License-Identifier: MIT OR Apache-2.0
"""Kod C z `rzc emit-c` kompiluje się bez ostrzeżeń `-Wall -Wextra` (w tym bez nieużywanych
funkcji pomocniczych, zmiennych i etykiet) dla każdego weryfikowalnego programu w repozytorium."""
import glob, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rdzen.driver import compile_source
from rdzen.emit_c import emit_c
from rdzen.emit_py import Unsupported

ROOT = os.path.join(os.path.dirname(__file__), "..")
CC = os.environ.get("CC", "gcc")


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "examples", "*.rz")) +
                   glob.glob(os.path.join(ROOT, "tests", "cases", "*.rz")) +
                   glob.glob(os.path.join(ROOT, "eval", "*.rz")))
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        for p in files:
            res = compile_source(open(p, encoding="utf-8").read(), run_examples=False, canon=False)
            if res.checker is None or any(d.severity in ("error", "hole") for d in res.diags):
                continue
            try:
                code = emit_c(res, os.path.basename(p))
            except Unsupported:
                continue
            c = os.path.join(tmp, "m.c")
            open(c, "w").write(code)
            r = subprocess.run([CC, "-std=gnu11", "-O1", "-Wall", "-Wextra", "-c", c, "-o", os.devnull],
                               capture_output=True, text=True)
            warns = [l for l in r.stderr.splitlines() if "warning" in l or "error" in l]
            if r.returncode != 0 or warns:
                bad += 1
                print(f"FAIL  {os.path.basename(p)}: " + (warns[0] if warns else r.stderr[:200]))
            else:
                print(f"PASS  {os.path.basename(p)}  {code.count(chr(10))} wierszy")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
