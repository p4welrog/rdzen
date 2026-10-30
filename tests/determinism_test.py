# SPDX-License-Identifier: MIT OR Apache-2.0
"""Weryfikacja nie zależy od PYTHONHASHSEED: identyczne zapytania SMT i identyczny wynik.
Wcześniej nazwy zmiennych związanych zawierały id(węzła) — zależne od rozmieszczenia obiektów
w pamięci — co zmieniało przebieg Z3 i dawało raz `proved`, raz `unknown` dla tego samego pliku."""
import os, sys, subprocess, tempfile, filecmp

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FILES = [os.path.join(ROOT, "examples", f) for f in ("bst.rz", "sort.rz", "hof.rz")]


def run(path, seed, dump):
    env = dict(os.environ, PYTHONHASHSEED=str(seed), RZ_DUMP_ALL=dump)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "rzc"), "check", path, "--json"],
                       env=env, capture_output=True, text=True)
    return r.stdout


def main():
    ok = True
    for path in FILES:
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            o1, o2 = run(path, 1, d1), run(path, 2, d2)
            cmp = filecmp.dircmp(d1, d2)
            same = o1 == o2 and not cmp.diff_files and not cmp.left_only and not cmp.right_only
            print(f"{'PASS' if same else 'FAIL'}  {os.path.basename(path):12} zapytania: {len(os.listdir(d1))}, różne: {len(cmp.diff_files)}")
            ok &= same
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
