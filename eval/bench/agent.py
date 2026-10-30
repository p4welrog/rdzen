# SPDX-License-Identifier: MIT OR Apache-2.0
"""Warianty agentowe: Claude Code w trybie nieinteraktywnym, każde zadanie w świeżym kontenerze.

  AP — agent pisze Pythona; może uruchamiać i testować kod.
  AR — agent pisze Rdzeń ze skillem rdzen-verified-code; ~/rdzen zawiera kompilator BEZ eval/.

Przygotowanie (raz, na komputerze z Dockerem):
  python3 eval/bench/agent.py obraz          — buduje obrazy rz-agent i rz-proxy, sieć rz-wewn, startuje pośrednika
Przebieg:
  ANTHROPIC_API_KEY=… python3 eval/bench/agent.py uruchom --model claude-opus-5-5 [--warianty AP,AR]
        [--zestaw AB] [--zadania ID,…] [--powtorzenia N] [--limit-s 1800] [--budzet-usd 5] [--wyjscie KATALOG]
  python3 eval/bench/raport.py KATALOG

Izolacja: kontener agenta jest tylko w sieci wewnętrznej `rz-wewn` (--internal); na zewnątrz wychodzi
wyłącznie przez pośrednika rz-proxy, który przepuszcza api.anthropic.com (agent/proxy/dozwolone).
HOME agenta jest pusty (bez pamięci, ustawień, CLAUDE.md); w AR montowane są tylko ~/rdzen (kopia bez
eval/ i .git) i skill. Transkrypt (stream-json) jest zapisywany i przeglądany pod kątem prób sięgnięcia
po repozytorium lub sieć (pole `audyt`).

--bez-kontenera uruchamia polecenie agenta bezpośrednio w katalogu roboczym (testy uprzęży z atrapą
agenta: --polecenie-agenta). Taki przebieg NIE jest izolowany i jest oznaczany w meta.json."""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time

TU = os.path.dirname(os.path.abspath(__file__))
KORZEN = os.path.abspath(os.path.join(TU, "..", ".."))
sys.path[:0] = [KORZEN, os.path.join(KORZEN, "eval")]

from bench import ocen, prompty  # noqa: E402
from bench.zadania import wszystkie  # noqa: E402

OBRAZ, PROXY, SIEC = "rz-agent", "rz-proxy", "rz-wewn"
NARZEDZIA = "Bash,Read,Write,Edit,Glob,Grep"
PODEJRZANE = re.compile(r"github\.com|p4welrog|vera-?bench|eval/bench|git clone|curl |wget |pip install(?! z3)",
                        re.I)


def sh(cmd, **kw):
    print("$", " ".join(shlex.quote(c) for c in cmd), flush=True)
    return subprocess.run(cmd, **kw)


# ---------- pakiet kompilatora dla AR (bez eval/) ----------

def pakiet(cel):
    """~/rdzen dla agenta: wszystko, czego używa skill, bez eval/ (wyrocznie i wzorce) i bez historii git."""
    if os.path.exists(cel):
        shutil.rmtree(cel)
    os.makedirs(cel)
    for f in ["rzc", "REFERENCE.md", "SKILL.md", "README.md", "LICENSE-MIT", "LICENSE-APACHE", "LICENSE-CC-BY",
              "LICENSE-0BSD-RUNTIME"]:
        shutil.copy2(os.path.join(KORZEN, f), os.path.join(cel, f))
    ign = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(os.path.join(KORZEN, "rdzen"), os.path.join(cel, "rdzen"), ignore=ign)
    shutil.copytree(os.path.join(KORZEN, "examples"), os.path.join(cel, "examples"), ignore=ign)
    os.makedirs(os.path.join(cel, "tests"))
    shutil.copy2(os.path.join(KORZEN, "tests", "run_tests.py"), os.path.join(cel, "tests", "run_tests.py"))
    shutil.copytree(os.path.join(KORZEN, "tests", "cases"), os.path.join(cel, "tests", "cases"))
    os.makedirs(os.path.join(cel, "docs"))
    shutil.copy2(os.path.join(KORZEN, "docs", "studium-huffman.md"), os.path.join(cel, "docs", "studium-huffman.md"))
    skill = os.path.join(cel + "-skill")
    if os.path.exists(skill):
        shutil.rmtree(skill)
    os.makedirs(skill)
    shutil.copy2(os.path.join(KORZEN, "SKILL.md"), os.path.join(skill, "SKILL.md"))
    for dp, _, fs in os.walk(cel):
        assert "eval" not in os.path.relpath(dp, cel).split(os.sep), dp
    return cel, skill


# ---------- obrazy i sieć ----------

def obraz(_a):
    sh(["docker", "build", "-t", OBRAZ, os.path.join(TU, "agent")], check=True)
    sh(["docker", "build", "-t", PROXY, os.path.join(TU, "agent", "proxy")], check=True)
    if sh(["docker", "network", "inspect", SIEC], capture_output=True).returncode != 0:
        sh(["docker", "network", "create", "--internal", SIEC], check=True)
    sh(["docker", "rm", "-f", PROXY], capture_output=True)
    sh(["docker", "run", "-d", "--name", PROXY, "--restart", "unless-stopped", PROXY], check=True)
    sh(["docker", "network", "connect", SIEC, PROXY], check=True)
    print("gotowe: obraz", OBRAZ, "pośrednik", PROXY, "sieć", SIEC)


# ---------- jedno zadanie ----------

def polecenie_claude(a, prompt):
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose", "--model", a.model,
           "--permission-mode", "bypassPermissions", "--tools", NARZEDZIA, "--no-session-persistence"]
    if a.budzet_usd:
        cmd += ["--max-budget-usd", str(a.budzet_usd)]
    return cmd


def uruchom_agenta(a, z, wariant, praca, pak):
    prompt = prompty.prompt_agenta(z, wariant)
    open(os.path.join(praca, "ZADANIE.md"), "w", encoding="utf-8").write(prompt + "\n")
    if a.bez_kontenera:
        env = dict(os.environ, RZ_PRACA=praca, RZ_ZADANIE=z.id, RZ_WARIANT=wariant)
        cmd = shlex.split(a.polecenie_agenta) if a.polecenie_agenta else polecenie_claude(a, prompt)
        cwd = praca
    else:
        cmd = ["docker", "run", "--rm", "--name", f"rz-agent-{os.getpid()}-{z.id}-{wariant}", "--network", SIEC,
               "-e", "ANTHROPIC_API_KEY", "-e", f"HTTPS_PROXY=http://{PROXY}:8888",
               "-e", f"HTTP_PROXY=http://{PROXY}:8888", "--memory", "4g", "--cpus", "2",
               "-v", f"{praca}:/praca"]
        if wariant == "AR":
            cmd += ["-v", f"{pak[0]}:/home/agent/rdzen:ro",
                    "-v", f"{pak[1]}:/home/agent/.claude/skills/rdzen-verified-code:ro"]
        cmd += [OBRAZ] + polecenie_claude(a, prompt)
        env, cwd = None, None
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=a.limit_s, env=env, cwd=cwd)
        out, err, limit = p.stdout, p.stderr, False
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        err, limit = "", True
        if not a.bez_kontenera:
            subprocess.run(["docker", "rm", "-f", cmd[cmd.index("--name") + 1]], capture_output=True)
    return out, err, limit, round(time.time() - t0, 1)


def przeczytaj_transkrypt(out):
    """stream-json: ostatni obiekt `result` (koszt, tury, tokeny) + audyt wywołań narzędzi."""
    wynik, audyt, narzedzia = {}, [], 0
    for w in out.splitlines():
        try:
            o = json.loads(w)
        except json.JSONDecodeError:
            continue
        if o.get("type") == "result":
            wynik = o
        if o.get("type") == "assistant":
            for c in o.get("message", {}).get("content", []):
                if c.get("type") == "tool_use":
                    narzedzia += 1
                    s = json.dumps(c.get("input", {}), ensure_ascii=False)
                    if PODEJRZANE.search(s):
                        audyt.append(s[:300])
    return wynik, audyt, narzedzia


def jedno(a, z, wariant, kat, pak):
    d = os.path.join(kat, z.id, wariant)
    praca = os.path.join(d, "praca")
    if os.path.exists(praca):
        shutil.rmtree(praca)
    os.makedirs(praca)
    os.chmod(praca, 0o777)                          # użytkownik `agent` w kontenerze
    out, err, limit, czas = uruchom_agenta(a, z, wariant, praca, pak)
    open(os.path.join(d, "transkrypt.jsonl"), "w", encoding="utf-8").write(out)
    if err:
        open(os.path.join(d, "stderr.txt"), "w", encoding="utf-8").write(err[-20000:])
    wynik, audyt, narzedzia = przeczytaj_transkrypt(out)
    u = wynik.get("usage", {})
    log = {"zadanie": z.id, "wariant": wariant, "czas_s": czas, "limit_czasu": limit,
           "iteracje": wynik.get("num_turns", 0), "wywolania_narzedzi": narzedzia,
           "koszt_usd": wynik.get("total_cost_usd"), "blad_agenta": bool(wynik.get("is_error")) or not wynik,
           "tokeny_wej": u.get("input_tokens", 0), "tokeny_wyj": u.get("output_tokens", 0),
           "tokeny_cache_zapis": u.get("cache_creation_input_tokens", 0),
           "tokeny_cache_odczyt": u.get("cache_read_input_tokens", 0), "audyt": audyt, "proby": []}
    plik = os.path.join(praca, "rozwiazanie." + ("rz" if wariant == "AR" else "py"))
    if not os.path.exists(plik):
        log.update(brak_odpowiedzi=True, zaakceptowane=False, poprawne=False, blad_niewykryty=False)
        return log
    if wariant == "AR":
        b = ocen.bramka(z.id, plik)       # ta sama bramka co w R: rzc fmt -w + rzc check
        log["proby"] = [{"n": 1, "bramka": {k: v for k, v in b.items() if k != "tekst"}}]
        log["zaakceptowane"] = bool(b.get("akceptacja"))
    else:
        log["zaakceptowane"] = True       # agent sam zdecydował, że kod jest gotowy
    uk = ocen.testy_ukryte(z.id, plik)
    log["ukryte"] = uk
    log["poprawne"] = uk.get("etap") == "testy" and uk.get("liczba_bledow") == 0
    log["blad_niewykryty"] = log["zaakceptowane"] and not log["poprawne"]
    log["plik_koncowy"] = os.path.relpath(plik, kat)
    return log


def uruchom(a):
    zs = [z for z in wszystkie().values() if z.id[0] in a.zestaw]
    if a.zadania:
        chce = set(a.zadania.split(","))
        zs = [z for z in zs if z.id in chce]
    kat = os.path.abspath(a.wyjscie or os.path.join(TU, "wyniki", f"agent-{a.model}-{time.strftime('%Y%m%d-%H%M%S')}"))
    os.makedirs(kat, exist_ok=True)
    pak = pakiet(os.path.join(kat, "_rdzen"))
    commit = subprocess.run(["git", "-C", TU, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    meta = {"model": a.model, "warianty": a.warianty, "commit": commit, "powtorzenia": a.powtorzenia,
            "izolacja": "brak (--bez-kontenera)" if a.bez_kontenera else f"docker {OBRAZ}, sieć {SIEC}, {PROXY}",
            "limit_s": a.limit_s, "budzet_usd": a.budzet_usd, "narzedzia": NARZEDZIA,
            "start": time.strftime("%Y-%m-%dT%H:%M:%S"), "zadania": [z.id for z in zs]}
    json.dump(meta, open(os.path.join(kat, "meta.json"), "w"), ensure_ascii=False, indent=1)
    for k in range(1, a.powtorzenia + 1):
        pk = kat if a.powtorzenia == 1 else os.path.join(kat, f"powt-{k}")
        os.makedirs(pk, exist_ok=True)
        wyn = os.path.join(pk, "wyniki.jsonl")
        gotowe = set()
        if os.path.exists(wyn):
            gotowe = {(r["zadanie"], r["wariant"]) for r in map(json.loads, open(wyn, encoding="utf-8"))}
        with open(wyn, "a", encoding="utf-8") as out:
            for z in zs:
                for w in a.warianty.split(","):
                    if (z.id, w) in gotowe:
                        continue
                    r = jedno(a, z, w, pk, pak)
                    out.write(json.dumps(r, ensure_ascii=False) + "\n")
                    out.flush()
                    print(f"[{k}/{a.powtorzenia}] {z.id:9} {w}  tury {r['iteracje']}  {r['czas_s']} s  "
                          f"{'zaakc.' if r.get('zaakceptowane') else 'odrzuc.'}  "
                          f"{'POPRAWNE' if r.get('poprawne') else 'błędne'}"
                          f"{'  BŁĄD NIEWYKRYTY' if r.get('blad_niewykryty') else ''}"
                          f"{'  AUDYT: ' + str(len(r['audyt'])) if r.get('audyt') else ''}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("obraz")
    u = sub.add_parser("uruchom")
    u.add_argument("--model", required=True)
    u.add_argument("--warianty", default="AP,AR")
    u.add_argument("--zestaw", default="AB")
    u.add_argument("--zadania", default="")
    u.add_argument("--powtorzenia", type=int, default=1)
    u.add_argument("--limit-s", dest="limit_s", type=int, default=1800)
    u.add_argument("--budzet-usd", dest="budzet_usd", type=float, default=0)
    u.add_argument("--wyjscie", default="")
    u.add_argument("--bez-kontenera", dest="bez_kontenera", action="store_true")
    u.add_argument("--polecenie-agenta", dest="polecenie_agenta", default="",
                   help="tylko z --bez-kontenera: program zamiast claude (dostaje RZ_PRACA, RZ_ZADANIE, RZ_WARIANT)")
    a = ap.parse_args()
    if a.cmd == "obraz":
        obraz(a)
    else:
        if a.polecenie_agenta and not a.bez_kontenera:
            ap.error("--polecenie-agenta wymaga --bez-kontenera")
        uruchom(a)


if __name__ == "__main__":
    main()
