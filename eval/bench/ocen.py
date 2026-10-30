# SPDX-License-Identifier: MIT OR Apache-2.0
"""Ocenianie rozwiązań: bramka widoczna dla modelu i testy ukryte.

Użycie:
  python3 eval/bench/ocen.py ID PLIK.(py|rz)          — bramka + testy ukryte, wynik JSON
  python3 eval/bench/ocen.py --bramka ID PLIK.(py|rz) — tylko bramka (to, co widzi model)
Każdy etap działa w osobnym procesie (`python3 -I`) z limitem czasu."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

TU = os.path.dirname(os.path.abspath(__file__))
LIMIT_BRAMKI = int(os.environ.get("RZ_EVAL_LIMIT_BRAMKI", "600"))
LIMIT_TESTOW = int(os.environ.get("RZ_EVAL_LIMIT_TESTOW", "120"))


def _proc(tryb, zid, plik, limit):
    t = time.time()
    try:
        p = subprocess.run([sys.executable, "-I", os.path.join(TU, "_wykonaj.py"), tryb, zid, plik],
                           capture_output=True, text=True, timeout=limit)
    except subprocess.TimeoutExpired:
        return {"etap": tryb, "blad": f"przekroczony limit czasu {limit} s", "limit_czasu": True,
                "czas_s": round(time.time() - t, 2)}
    dt = round(time.time() - t, 2)
    try:
        out = json.loads(p.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        out = {"etap": tryb, "blad": "proces roboczy zakończył się bez wyniku", "stderr": p.stderr[-2000:]}
    out["czas_s"] = dt
    return out


def jezyk(plik):
    return "rdzen" if plik.endswith(".rz") else "python"


def bramka(zid, plik):
    if jezyk(plik) == "rdzen":
        return _proc("bramka-rdzen", zid, plik, LIMIT_BRAMKI)
    return _proc("bramka-python", zid, plik, LIMIT_TESTOW)


def testy_ukryte(zid, plik):
    return _proc(jezyk(plik), zid, plik, LIMIT_TESTOW)


def ocen(zid, plik, z_bramka=True):
    w = {"zadanie": zid, "plik": plik, "jezyk": jezyk(plik)}
    if z_bramka:
        w["bramka"] = bramka(zid, plik)
    w["ukryte"] = testy_ukryte(zid, plik)
    u = w["ukryte"]
    w["poprawne"] = u.get("etap") == "testy" and u.get("liczba_bledow") == 0 and u.get("zdane") == u.get("przypadki")
    if z_bramka:
        w["zaakceptowane"] = bool(w["bramka"].get("akceptacja"))
        w["blad_niewykryty"] = w["zaakceptowane"] and not w["poprawne"]
    return w


def main(argv):
    if argv[1] == "--bramka":
        print(json.dumps(bramka(argv[2], argv[3]), ensure_ascii=False, indent=1))
        return 0
    print(json.dumps(ocen(argv[1], argv[2]), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
