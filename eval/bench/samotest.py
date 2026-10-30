# SPDX-License-Identifier: MIT OR Apache-2.0
"""Samotest materiałów ewaluacji: python3 eval/bench/samotest.py [--szybko]

1. wyrocznie zgadzają się z przypadkami testowymi VeraBench (zestaw A);
2. każde zadanie ma wzorzec w Rdzeniu (ref/ID.rz), który przechodzi rzc check i wszystkie testy
   ukryte; wzorzec koduje dziedzinę w `requires`, więc to sprawdza też, że generatory nie wychodzą
   poza dziedzinę opisaną w zadaniu (--szybko: tylko kilka wzorców);
3. kontrole negatywne oceniacza: błędny wynik, `requires` za silny, zły typ wyniku, wyjątek,
   przekroczenie limitu czasu, niezgodna sygnatura;
4. pełna pętla `uruchom.py` z odpowiedziami odtwarzanymi z testy/odtworz, --powtorzenia i `raport.py`;
5. treść żądania Messages API z cache (bez sieci);
6. `agent.py --bez-kontenera` z atrapą agenta (obrazów Dockera samotest nie buduje)."""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import shutil
import subprocess
import sys
import tempfile

TU = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(TU, "..", ".."), os.path.join(TU, ".."), TU]
os.environ.setdefault("RZ_EVAL_LIMIT_TESTOW", "20")

from bench import ocen  # noqa: E402
from bench.zadania import wszystkie  # noqa: E402

ok = True


def zgłoś(warunek, opis):
    global ok
    print(f"{'PASS' if warunek else 'FAIL'}  {opis}", flush=True)
    ok &= bool(warunek)


def wyrocznie():
    zs = wszystkie()
    zle = [(z.id, a) for z in zs.values() for a, e in z.testy_zrodla if not z.poprawny(a, e)]
    zgłoś(not zle, f"wyrocznie zgodne z VeraBench ({sum(len(z.testy_zrodla) for z in zs.values())} przypadków) {zle[:3]}")
    na = sum(1 for z in zs.values() if z.id.startswith("A-"))
    nb = sum(1 for z in zs.values() if z.id.startswith("B-"))
    zgłoś(na == 50 and nb == 32, f"liczba zadań: A={na}, B={nb}")
    bez = [z.id for z in zs.values() if not os.path.exists(os.path.join(TU, "ref", f"{z.id}.rz"))]
    zgłoś(not bez, f"każde zadanie ma wzorzec w ref/ {bez}")


def wzorce(szybko):
    ids = sorted(wszystkie())
    if szybko:
        ids = ["A-T2-005", "A-T3-003", "B-01", "B-15", "B-22", "B-32"]

    def jeden(zid):
        w = ocen.ocen(zid, os.path.join(TU, "ref", f"{zid}.rz"))
        return zid, w

    zle = []
    with cf.ThreadPoolExecutor(os.cpu_count() or 4) as ex:
        for zid, w in ex.map(jeden, ids):
            if not (w["zaakceptowane"] and w["poprawne"]):
                zle.append((zid, w["bramka"].get("kody"), w["ukryte"].get("rodzaje", w["ukryte"].get("blad"))))
    zgłoś(not zle, f"wzorce w Rdzeniu: {len(ids) - len(zle)}/{len(ids)} przechodzą rzc check i testy ukryte {zle[:5]}")


TMP = tempfile.mkdtemp(prefix="rz_samotest_")


def plik(tresc, ext):
    f = tempfile.NamedTemporaryFile("w", suffix=ext, delete=False, encoding="utf-8", dir=TMP)
    f.write(tresc)
    f.close()
    return f.name


def negatywne():
    u = ocen.testy_ukryte("B-19", plik("def floor_average(xs):\n    return int(sum(xs) / len(xs))\n", ".py"))
    zgłoś(u.get("rodzaje") == ["zly-wynik"] and 0 < u["zdane"] < u["przypadki"], "Python: błędny wynik wykryty")
    u = ocen.testy_ukryte("A-T1-004", plik("def max_of_two(a, b):\n    return float(max(a, b))\n", ".py"))
    zgłoś(u.get("rodzaje") == ["zly-typ-wyniku"], "Python: zły typ wyniku (float zamiast int)")
    u = ocen.testy_ukryte("A-T1-004", plik("def max_of_two(a, b):\n    while True:\n        pass\n", ".py"))
    zgłoś(u.get("limit_czasu"), "Python: limit czasu")
    u = ocen.testy_ukryte("A-T1-007", plik("def safe_modulo(a, b):\n    raise ValueError(a)\n", ".py"))
    zgłoś(u.get("rodzaje") == ["wyjatek"], "Python: wyjątek")
    src = open(os.path.join(TU, "ref", "A-T1-007.rz"), encoding="utf-8").read()
    za_silny = src.replace("requires a >= 0 && b > 0", "requires a >= 0 && b > 1")
    u = ocen.testy_ukryte("A-T1-007", plik(za_silny, ".rz"))
    zgłoś("requires-za-silny" in u.get("rodzaje", []), "Rdzeń: requires odrzucający poprawne wejścia (b == 1)")
    src = open(os.path.join(TU, "ref", "B-01.rz"), encoding="utf-8").read()
    u = ocen.testy_ukryte("B-01", plik(src.replace("requires sorted(xs)", "requires sorted(xs) && xs.len <= 999"), ".rz"))
    zgłoś("requires-za-silny" in u.get("rodzaje", []), "Rdzeń: requires za silny przy kwantyfikatorze (n = 1000)")
    zly_typ = "fn safe_modulo(a: Int, b: Int) -> Bool\n    requires b > 0\n{\n    a % b == 0\n}\n"
    u = ocen.testy_ukryte("A-T1-007", plik(zly_typ, ".rz"))
    zgłoś(u.get("etap") == "sygnatura", "Rdzeń: niezgodna sygnatura")
    blad = "fn signum(x: Int) -> Int {\n    if x > 0 { 1 } else { 0 }\n}\n"
    w = ocen.ocen("A-T1-003", plik(blad, ".rz"))
    zgłoś(w["zaakceptowane"] and not w["poprawne"] and w["blad_niewykryty"],
          "Rdzeń: słaby kontrakt + błędny kod = błąd niewykryty")


def petla():
    wyj = tempfile.mkdtemp(prefix="rz_eval_")
    try:
        cmd = [sys.executable, os.path.join(TU, "uruchom.py"), "--model", "odtworzony", "--backend", "odtworz",
               "--odtworz", os.path.join(TU, "testy", "odtworz"), "--zadania", "A-T1-007,B-19", "--wyjscie", wyj]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        zgłoś(p.returncode == 0, "uruchom.py (backend odtworz) " + p.stderr[-500:])
        rs = {(r["zadanie"], r["wariant"]): r for r in map(json.loads, open(os.path.join(wyj, "wyniki.jsonl")))}
        r = rs[("A-T1-007", "R")]
        zgłoś(r["iteracje"] == 2 and r["zaakceptowane"] and r["poprawne"]
              and "E4130" in r["proby"][0]["bramka"]["kody"], "R: diagnostyka E4130 → poprawka → akceptacja")
        r = rs[("A-T1-007", "PT")]
        zgłoś(r["iteracje"] == 2 and r["poprawne"], "PT: porażka własnego testu → poprawka")
        zgłoś(rs[("B-19", "R")]["blad_niewykryty"] and rs[("B-19", "PT")]["blad_niewykryty"]
              and rs[("B-19", "P")]["blad_niewykryty"], "B-19: błąd niewykryty w P, PT i R")
        p = subprocess.run([sys.executable, os.path.join(TU, "raport.py"), wyj, "--json"], capture_output=True,
                           text=True, timeout=60)
        z = json.loads(p.stdout)["zestawienie"]
        zgłoś(z["R/razem"]["bledy_niewykryte"] == 1 and z["R/razem"]["poprawne"] == 1
              and z["P/A"]["pass1_verabench_A"] == 100.0, "raport.py: zestawienie")
    finally:
        shutil.rmtree(wyj, ignore_errors=True)
    wyj = tempfile.mkdtemp(prefix="rz_eval_")
    try:
        cmd = [sys.executable, os.path.join(TU, "uruchom.py"), "--model", "odtworzony", "--backend", "odtworz",
               "--odtworz", os.path.join(TU, "testy", "odtworz"), "--zadania", "A-T1-007", "--warianty", "R",
               "--powtorzenia", "2", "--wyjscie", wyj]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        p2 = subprocess.run([sys.executable, os.path.join(TU, "raport.py"), wyj, "--json"], capture_output=True,
                            text=True, timeout=60)
        d = json.loads(p2.stdout)
        zgłoś(p.returncode == 0 and d["powtorzenia"] == 2 and d["zestawienie"]["R/A"]["pct_poprawne"] == 100.0
              and d["zestawienie"]["R/A"]["pct_poprawne_sd"] == 0.0, "--powtorzenia 2: powt-1, powt-2, średnia ± sd")
    finally:
        shutil.rmtree(wyj, ignore_errors=True)


def cache_api():
    """Treść żądania Messages API (bez sieci): cache_control na prompcie systemowym i automatyczny punkt."""
    import io
    import types
    import uruchom
    zap = {}

    class Odp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def falszywe(req, timeout=0):
        zap.update(json.loads(req.data))
        return Odp(json.dumps({"content": [{"type": "text", "text": "x"}], "usage": {
            "input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 9}}).encode())

    stare = uruchom.urllib.request.urlopen, os.environ.get("ANTHROPIC_API_KEY")
    uruchom.urllib.request.urlopen = falszywe
    os.environ["ANTHROPIC_API_KEY"] = "test"
    try:
        a = types.SimpleNamespace(backend="anthropic", model="m", max_tokens=8, bez_cache=False)
        _, u = uruchom.Model(a)("A", "R", 1, "SYS", [{"role": "user", "content": "q"}])
    finally:
        uruchom.urllib.request.urlopen = stare[0]
        if stare[1] is None:
            del os.environ["ANTHROPIC_API_KEY"]
        else:
            os.environ["ANTHROPIC_API_KEY"] = stare[1]
    zgłoś(zap["system"][0].get("cache_control") == {"type": "ephemeral"} and zap.get("cache_control")
          and u.get("cache_read_input_tokens") == 9, "Messages API: cache_control w żądaniu, tokeny cache w wyniku")


def agentowe():
    """agent.py --bez-kontenera z atrapą agenta: pakiet bez eval/, ocena AP/AR, audyt, raport."""
    wyj = tempfile.mkdtemp(prefix="rz_eval_")
    try:
        cmd = [sys.executable, os.path.join(TU, "agent.py"), "uruchom", "--model", "atrapa", "--bez-kontenera",
               "--polecenie-agenta", f"{sys.executable} {os.path.join(TU, 'testy', 'atrapa_agenta.py')}",
               "--zadania", "A-T1-007,B-19,A-T1-001", "--wyjscie", wyj]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        rs = {(r["zadanie"], r["wariant"]): r for r in map(json.loads, open(os.path.join(wyj, "wyniki.jsonl")))}
        zgłoś(p.returncode == 0 and rs[("A-T1-007", "AR")]["poprawne"] and rs[("A-T1-007", "AP")]["poprawne"]
              and rs[("A-T1-007", "AR")]["proby"][0]["bramka"]["akceptacja"], "agent.py: AP i AR ocenione")
        zgłoś(rs[("B-19", "AR")]["blad_niewykryty"] and rs[("B-19", "AP")]["blad_niewykryty"]
              and rs[("B-19", "AR")]["audyt"] and not rs[("A-T1-007", "AR")]["audyt"],
              "agent.py: błąd niewykryty i audyt próby sięgnięcia po repozytorium")
        zgłoś(rs[("A-T1-001", "AP")].get("brak_odpowiedzi"), "agent.py: brak pliku rozwiązania")
        pak = os.path.join(wyj, "_rdzen")
        zgłoś(os.path.exists(os.path.join(pak, "rzc")) and not any(
            "eval" in dp.split(os.sep) for dp, _, _ in os.walk(pak)), "pakiet ~/rdzen dla agenta: jest rzc, nie ma eval/")
    finally:
        shutil.rmtree(wyj, ignore_errors=True)


if __name__ == "__main__":
    szybko = "--szybko" in sys.argv
    wyrocznie()
    negatywne()
    petla()
    cache_api()
    agentowe()
    wzorce(szybko)
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(0 if ok else 1)
