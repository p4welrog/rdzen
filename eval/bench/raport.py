# SPDX-License-Identifier: MIT OR Apache-2.0
"""Zestawienie wyników przebiegu: python3 eval/bench/raport.py KATALOG [--json]
Przy przebiegu z --powtorzenia N: średnia ± odchylenie standardowe po katalogach powt-K.

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


def _pct(a, b):
    return round(100 * a / b, 1) if b else None


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
             "sr_koszt_usd": (round(sum(r.get("koszt_usd") or 0 for r in rs) / n, 3)
                              if any(r.get("koszt_usd") is not None for r in rs) else None),
             "audyt": sum(1 for r in rs if r.get("audyt")) if any("audyt" in r for r in rs) else None,
             "sr_tokeny_wyj": round(sum(r.get("tokeny_wyj", 0) for r in rs) / n),
             "sr_tokeny_wej": round(sum(r.get("tokeny_wej", 0) + r.get("tokeny_cache_zapis", 0) +
                                        r.get("tokeny_cache_odczyt", 0) for r in rs) / n),
             "pct_wej_z_cache": _pct(sum(r.get("tokeny_cache_odczyt", 0) for r in rs),
                                     sum(r.get("tokeny_wej", 0) + r.get("tokeny_cache_zapis", 0) +
                                         r.get("tokeny_cache_odczyt", 0) for r in rs))}
        a = [r for r in rs if r["zadanie"].startswith("A-")]
        if a:
            ok = sum(1 for r in a if r.get("ukryte", {}).get("zrodlowe") and
                     r["ukryte"].get("zrodlowe_zdane") == r["ukryte"]["zrodlowe"])
            m["pass1_verabench_A"] = round(100 * ok / len(a), 1)
        if w in ("R", "AR"):
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


def powtorzenia(kat):
    """Katalogi powt-K przebiegu z --powtorzenia N (albo sam katalog, gdy ich nie ma)."""
    ks = sorted((d for d in os.listdir(kat) if d.startswith("powt-") and
                 os.path.exists(os.path.join(kat, d, "wyniki.jsonl"))), key=lambda d: int(d[5:]))
    return [os.path.join(kat, d) for d in ks] or [kat]


def zbiorczo(zestawienia):
    """Średnia i odchylenie standardowe (próbkowe) miar liczbowych między powtórzeniami."""
    import statistics
    out = {}
    for k in zestawienia[0]:
        m = {}
        for pole, v in zestawienia[0][k].items():
            vals = [z[k][pole] for z in zestawienia if k in z and isinstance(z[k].get(pole), (int, float))]
            if len(vals) != len(zestawienia) or isinstance(v, bool):
                continue
            m[pole] = round(statistics.mean(vals), 2)
            m[pole + "_sd"] = round(statistics.stdev(vals), 2) if len(vals) > 1 else 0.0
        out[k] = m
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
    katalogi = powtorzenia(kat)
    wszystkie = [wczytaj(k) for k in katalogi]
    zest = [zestawienie(w) for w in wszystkie]
    z = zest[0] if len(zest) == 1 else zbiorczo(zest)
    rb = rodzaje_bledow([r for w in wszystkie for r in w])
    if "--json" in argv:
        out = {"powtorzenia": len(zest), "zestawienie": z, "rodzaje_bledow_niewykrytych": rb}
        if len(zest) > 1:
            out["zestawienia_powtorzen"] = zest
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    kol = ["n", "pct_poprawne", "zaakceptowane", "bledy_niewykryte", "pct_niewykryte_zaakceptowanych",
           "odrzucone_poprawne", "sr_iteracje", "sr_czas_s", "sr_tokeny_wej", "pct_wej_z_cache",
           "pass1_verabench_A", "pct_zobowiazan_udowodnionych"]
    if any(m.get("sr_koszt_usd") is not None for m in z.values()):
        kol += ["sr_koszt_usd", "audyt"]
    if len(zest) > 1:
        print(f"powtórzenia: {len(zest)}; wartości: średnia ± odchylenie standardowe")
    print("| wariant/zestaw | " + " | ".join(kol) + " |")
    print("|---" * (len(kol) + 1) + "|")
    for k, m in z.items():
        def kom(c):
            if m.get(c) is None:
                return ""
            sd = m.get(c + "_sd")
            return f"{m[c]} ± {sd}" if sd is not None and c != "n" else str(m[c])
        print(f"| {k} | " + " | ".join(kom(c) for c in kol) + " |")
    print()
    print("rodzaje błędów niewykrytych (wszystkie powtórzenia):", json.dumps(rb, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
