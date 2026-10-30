# SPDX-License-Identifier: MIT OR Apache-2.0
"""Przebieg ewaluacji: model × wariant × zadania.

  python3 eval/bench/uruchom.py --model NAZWA --warianty P,PT,R [--zestaw A|B|AB] [--zadania ID,…]
                                [--proby 6] [--wyjscie eval/bench/wyniki/NAZWA_PRZEBIEGU]
                                [--backend anthropic|polecenie|odtworz] [--polecenie "…"] [--odtworz KATALOG]

Backendy modelu:
  anthropic  — Messages API (zmienna ANTHROPIC_API_KEY), bez zależności poza biblioteką standardową
  polecenie  — dowolny program: JSON {"model","system","messages"} na stdin, odpowiedź na stdout
  odtworz    — odpowiedzi z plików KATALOG/ID/WARIANT/N.txt (testy uprzęży, powtórna ocena)

Wynik: KATALOG/wyniki.jsonl (jeden wiersz na zadanie×wariant) oraz pliki prób w KATALOG/ID/WARIANT/.
Model nie widzi testów ukrytych ani wyroczni — dostaje tylko prompt i informację z bramki."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

TU = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(TU, "..", ".."), os.path.join(TU, "..")]

from bench import ocen, prompty  # noqa: E402
from bench.zadania import wszystkie  # noqa: E402


class Model:
    def __init__(self, a):
        self.a = a

    def __call__(self, zid, wariant, n, system, messages):
        b = self.a.backend
        if b == "odtworz":
            p = os.path.join(self.a.odtworz, zid, wariant, f"{n}.txt")
            if not os.path.exists(p):
                return None, {}
            return open(p, encoding="utf-8").read(), {}
        if b == "polecenie":
            wej = json.dumps({"model": self.a.model, "system": system, "messages": messages})
            p = subprocess.run(self.a.polecenie, shell=True, input=wej, capture_output=True, text=True, timeout=1800)
            return p.stdout, {}
        body = json.dumps({"model": self.a.model, "max_tokens": self.a.max_tokens, "system": system,
                           "messages": messages}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
            "content-type": "application/json"})
        for proba in range(5):
            try:
                with urllib.request.urlopen(req, timeout=900) as r:
                    d = json.load(r)
                break
            except Exception:  # noqa: BLE001
                if proba == 4:
                    raise
                time.sleep(10 * (proba + 1))
        tekst = "".join(c.get("text", "") for c in d.get("content", []))
        return tekst, d.get("usage", {})


def jedno(model, z, wariant, katalog, proby):
    pr = prompty.prompt(z, wariant)
    messages = [{"role": "user", "content": pr["user"]}]
    ext = "rz" if wariant == "R" else "py"
    d = os.path.join(katalog, z.id, wariant)
    os.makedirs(d, exist_ok=True)
    log = {"zadanie": z.id, "wariant": wariant, "proby": [], "tokeny_wej": 0, "tokeny_wyj": 0}
    t0 = time.time()
    plik = None
    maks = 1 if wariant == "P" else proby
    for n in range(1, maks + 1):
        tm = time.time()
        odp, usage = model(z.id, wariant, n, pr["system"], messages)
        t_model = time.time() - tm
        if odp is None:
            break
        log["tokeny_wej"] += usage.get("input_tokens", 0)
        log["tokeny_wyj"] += usage.get("output_tokens", 0)
        open(os.path.join(d, f"{n}.txt"), "w", encoding="utf-8").write(odp)
        plik = os.path.join(d, f"{n}.{ext}")
        open(plik, "w", encoding="utf-8").write(prompty.wyciagnij_kod(odp))
        wpis = {"n": n, "czas_modelu_s": round(t_model, 2)}
        if wariant == "P":
            log["proby"].append(wpis)
            break
        b = ocen.bramka(z.id, plik)
        wpis["bramka"] = {k: v for k, v in b.items() if k != "tekst"}
        log["proby"].append(wpis)
        if b.get("akceptacja"):
            break
        messages += [{"role": "assistant", "content": odp},
                     {"role": "user", "content": prompty.poprawka(wariant, b.get("tekst") or b.get("blad", ""))}]
    log["czas_s"] = round(time.time() - t0, 2)
    log["iteracje"] = len(log["proby"])
    if plik is None:
        log["brak_odpowiedzi"] = True
        return log
    u = ocen.testy_ukryte(z.id, plik)
    log["ukryte"] = u
    log["poprawne"] = u.get("etap") == "testy" and u.get("liczba_bledow") == 0
    log["zaakceptowane"] = True if wariant == "P" else bool(log["proby"][-1]["bramka"].get("akceptacja"))
    log["blad_niewykryty"] = log["zaakceptowane"] and not log["poprawne"]
    log["plik_koncowy"] = os.path.relpath(plik, katalog)
    return log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--warianty", default="P,PT,R")
    ap.add_argument("--zestaw", default="AB")
    ap.add_argument("--zadania", default="")
    ap.add_argument("--proby", type=int, default=6)
    ap.add_argument("--max-tokens", dest="max_tokens", type=int, default=16000)
    ap.add_argument("--backend", default="anthropic", choices=["anthropic", "polecenie", "odtworz"])
    ap.add_argument("--polecenie", default="")
    ap.add_argument("--odtworz", default="")
    ap.add_argument("--wyjscie", default="")
    a = ap.parse_args()
    zs = [z for z in wszystkie().values() if z.id[0] in a.zestaw]
    if a.zadania:
        chce = set(a.zadania.split(","))
        zs = [z for z in zs if z.id in chce]
    kat = a.wyjscie or os.path.join(TU, "wyniki", f"{a.model}-{time.strftime('%Y%m%d-%H%M%S')}")
    os.makedirs(kat, exist_ok=True)
    commit = subprocess.run(["git", "-C", TU, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    meta = {"model": a.model, "backend": a.backend, "warianty": a.warianty, "proby": a.proby, "commit": commit,
            "start": time.strftime("%Y-%m-%dT%H:%M:%S"), "zadania": [z.id for z in zs]}
    json.dump(meta, open(os.path.join(kat, "meta.json"), "w"), ensure_ascii=False, indent=1)
    model = Model(a)
    gotowe = set()
    wyn = os.path.join(kat, "wyniki.jsonl")
    if os.path.exists(wyn):                      # wznowienie przerwanego przebiegu
        for w in open(wyn, encoding="utf-8"):
            r = json.loads(w)
            gotowe.add((r["zadanie"], r["wariant"]))
    with open(wyn, "a", encoding="utf-8") as out:
        for z in zs:
            for w in a.warianty.split(","):
                if (z.id, w) in gotowe:
                    continue
                r = jedno(model, z, w, kat, a.proby)
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                out.flush()
                print(f"{z.id:9} {w:2}  iter {r['iteracje']}  "
                      f"{'zaakc.' if r.get('zaakceptowane') else 'odrzuc.'}  "
                      f"{'POPRAWNE' if r.get('poprawne') else 'błędne'}"
                      f"{'  BŁĄD NIEWYKRYTY' if r.get('blad_niewykryty') else ''}", flush=True)


if __name__ == "__main__":
    main()
