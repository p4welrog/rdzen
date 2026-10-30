# SPDX-License-Identifier: MIT OR Apache-2.0
"""Siła kontraktów zaakceptowanych rozwiązań w Rdzeniu (próbka rozwiązań z przebiegu).

  python3 eval/bench/mutacje.py KATALOG [--proba N] [--ziarno S]

Dla każdego wylosowanego zaakceptowanego i poprawnego rozwiązania R mutuje ciała funkcji (operatory, ±1;
generator z tests/mutate.py — kontrakty, niezmienniki i przykłady pozostają bez zmian) i klasyfikuje mutanty:
  zabity       — rzc check zgłasza błąd (kontrakt, niezmiennik albo przykład wyłapuje zmianę)
  rownowazny   — przechodzi rzc check i wszystkie testy ukryte
  luka         — przechodzi rzc check, a testy ukryte go odrzucają: kontrakt dopuszcza błędne zachowanie
Miara: luka / (zabity + luka) — odsetek błędów wprowadzonych do kodu, których kontrakt modelu nie wyklucza."""
from __future__ import annotations

import json
import os
import random
import sys
import tempfile

TU = os.path.dirname(os.path.abspath(__file__))
KORZEN = os.path.abspath(os.path.join(TU, "..", ".."))
sys.path[:0] = [KORZEN, os.path.join(KORZEN, "eval"), os.path.join(KORZEN, "tests")]

from bench import ocen  # noqa: E402
from mutate import mutants  # noqa: E402
from rdzen.driver import compile_source  # noqa: E402


def mutuj(zid, plik):
    src = open(plik, encoding="utf-8").read()
    st = {"zabity": 0, "rownowazny": 0, "luka": 0}
    luki = []
    for line, desc, m in mutants(src):
        r = compile_source(m, canon=False, cache=False)
        if any(d.severity in ("error", "hole") for d in r.diags):
            st["zabity"] += 1
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".rz", delete=False, encoding="utf-8") as f:
            f.write(m)
        u = ocen.testy_ukryte(zid, f.name)
        os.unlink(f.name)
        if u.get("etap") == "testy" and u.get("liczba_bledow") == 0:
            st["rownowazny"] += 1
        else:
            st["luka"] += 1
            luki.append({"wiersz": line, "zmiana": desc, "bledy": u.get("bledy", [])[:1]})
    return st, luki


def main(argv):
    kat = argv[1]
    n = int(argv[argv.index("--proba") + 1]) if "--proba" in argv else 10
    ziarno = argv[argv.index("--ziarno") + 1] if "--ziarno" in argv else "0"
    rs = [json.loads(w) for w in open(os.path.join(kat, "wyniki.jsonl"), encoding="utf-8")]
    kand = sorted((r for r in rs if r["wariant"] == "R" and r.get("poprawne") and r.get("zaakceptowane")),
                  key=lambda r: r["zadanie"])
    proba = random.Random(ziarno).sample(kand, min(n, len(kand)))
    suma = {"zabity": 0, "rownowazny": 0, "luka": 0}
    wyniki = []
    for r in sorted(proba, key=lambda r: r["zadanie"]):
        st, luki = mutuj(r["zadanie"], os.path.join(kat, r["plik_koncowy"]))
        for k in suma:
            suma[k] += st[k]
        wyniki.append({"zadanie": r["zadanie"], **st, "luki": luki})
        print(f"{r['zadanie']:9} zabite {st['zabity']:3}  równoważne {st['rownowazny']:3}  luki {st['luka']:3}", flush=True)
    nz = suma["zabity"] + suma["luka"]
    wynik = {"proba": len(proba), "ziarno": ziarno, **suma,
             "pct_luk": round(100 * suma["luka"] / nz, 1) if nz else None, "rozwiazania": wyniki}
    json.dump(wynik, open(os.path.join(kat, "mutacje.json"), "w"), ensure_ascii=False, indent=1)
    print(f"razem: zabite {suma['zabity']}, równoważne {suma['rownowazny']}, luki {suma['luka']} "
          f"({wynik['pct_luk']}% błędnych mutantów niewykluczonych przez kontrakt)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
