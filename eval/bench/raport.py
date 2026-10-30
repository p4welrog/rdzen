# SPDX-License-Identifier: MIT OR Apache-2.0
"""Zestawienie wyników przebiegu: python3 eval/bench/raport.py KATALOG [--json]

Miary na wariant i zestaw:
  poprawne        — rozwiązania przechodzące wszystkie testy ukryte
  zaakceptowane   — rozwiązania przepuszczone przez bramkę wariantu (P: wszystkie, PT: własne testy, R: rzc check)
  błędy niewykryte — zaakceptowane, a błędne; podawane względem wszystkich zadań i względem zaakceptowanych
  odrzucone poprawne — nie przeszły bramki, choć są poprawne (koszt nadmiernej ostrożności)
  pass@1 VeraBench — tylko zestaw A: przechodzą wszystkie przypadki testowe z VeraBench (porównywalne
                     z opublikowanymi wynikami, z zastrzeżeniami z README)
  iteracje, czas, tokeny — średnie
  R: odsetek zobowiązań udowodnionych statycznie i liczba sprawdzeń dynamicznych w rozwiązaniu końcowym."""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict


def wczytaj(kat):
    return [json.loads(w) for w in open(os.path.join(kat, "wyniki.jsonl"), encoding="utf-8")]


def zestawienie(wiersze):
    grupy = defaultdict(list)
    for r in wiersze:
        for zestaw in (r["zadanie"][0], "razem"):
            grupy[(r["wariant"], zestaw)].append(r)
    out = {}
    for (w, zs), rs in sorted(grupy.items()):
        n = len(rs)
        pop = sum(bool(r.get("poprawne")) for r in rs)
        zaak = sum(bool(r.get("zaakceptowane")) for r in rs)
        niew = sum(bool(r.get("blad_niewykryty")) for r in rs)
        odrz_pop = sum(bool(r.get("poprawne")) and not r.get("zaakceptowane") for r in rs)
        m = {"n": n, "poprawne": pop, "zaakceptowane": zaak, "bledy_niewykryte": niew,
             "odrzucone_poprawne": odrz_pop,
             "pct_poprawne": round(100 * pop / n, 1),
             "pct_niewykryte_wszystkich": round(100 * niew / n, 1),
             "pct_niewykryte_zaakceptowanych": round(100 * niew / zaak, 1) if zaak else None,
             "sr_iteracje": round(sum(r["iteracje"] for r in rs) / n, 2),
             "sr_czas_s": round(sum(r.get("czas_s", 0) for r in rs) / n, 1),
             "sr_tokeny_wyj": round(sum(r.get("tokeny_wyj", 0) for r in rs) / n)}
        a = [r for r in rs if r["zadanie"].startswith("A-")]
        if a:
            ok = sum(1 for r in a if r.get("ukryte", {}).get("zrodlowe") and
                     r["ukryte"].get("zrodlowe_zdane") == r["ukryte"]["zrodlowe"])
            m["pass1_verabench_A"] = round(100 * ok / len(a), 1)
        if w == "R":
            dow = nie = dyn = k = 0
            for r in rs:
                if not r.get("zaakceptowane"):
                    continue
                b = r["proby"][-1]["bramka"]
                o = b.get("podsumowanie", {}).get("obligations")
                if o:
                    k += 1
                    dow += o["proved"]
                    nie += o["unknown"] + o["refuted-inductive"]
                    dyn += b.get("sprawdzenia_dynamiczne", 0)
            m["pct_zobowiazan_udowodnionych"] = round(100 * dow / (dow + nie), 1) if dow + nie else None
            m["sr_sprawdzen_dynamicznych"] = round(dyn / k, 2) if k else None
        out[f"{w}/{zs}"] = m
    return out


def rodzaje_bledow(wiersze):
    """Błędy niewykryte: rodzaj pierwszego błędu z testów ukrytych."""
    c = defaultdict(lambda: defaultdict(int))
    for r in wiersze:
        if r.get("blad_niewykryty"):
            for k in r.get("ukryte", {}).get("rodzaje", ["?"]):
                c[r["wariant"]][k] += 1
    return {w: dict(v) for w, v in c.items()}


def main(argv):
    kat = argv[1]
    w = wczytaj(kat)
    z = zestawienie(w)
    if "--json" in argv:
        print(json.dumps({"zestawienie": z, "rodzaje_bledow_niewykrytych": rodzaje_bledow(w)}, ensure_ascii=False,
                         indent=1))
        return 0
    kol = ["n", "pct_poprawne", "zaakceptowane", "bledy_niewykryte", "pct_niewykryte_zaakceptowanych",
           "odrzucone_poprawne", "sr_iteracje", "sr_czas_s", "pass1_verabench_A", "pct_zobowiazan_udowodnionych"]
    print("| wariant/zestaw | " + " | ".join(kol) + " |")
    print("|---" * (len(kol) + 1) + "|")
    for k, m in z.items():
        print(f"| {k} | " + " | ".join("" if m.get(c) is None else str(m.get(c)) for c in kol) + " |")
    print()
    print("rodzaje błędów niewykrytych:", json.dumps(rodzaje_bledow(w), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
