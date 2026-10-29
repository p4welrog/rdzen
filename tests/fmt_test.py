# SPDX-License-Identifier: MIT OR Apache-2.0
"""Testy formatera kanonicznego (§2.5).

Dla każdego pliku .rz w repozytorium:
1. fmt zachowuje drzewo składni i komplet komentarzy;
2. fmt jest idempotentny: fmt(fmt(P)) = fmt(P);
3. postać kanoniczna jest jednoznaczna: losowe zmiany wcięć i odstępów między tokenami
   (nie zmieniające ciągu tokenów) dają tę samą postać kanoniczną.
"""
import glob, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rdzen.fmt import check_format, format_source
from rdzen.lexer import lex
from rdzen.diag import CompileError

ROOT = os.path.join(os.path.dirname(__file__), "..")
N = int(os.environ.get("N", 20))


def perturb(src, rng):
    toks = [t for t in lex(src) if not (t.kind == ";" and t.implicit) and t.kind != "EOF"]
    lines = src.split("\n")
    by_line = {}
    for t in toks:
        by_line.setdefault(t.line, []).append(t)
    out = []
    for no, text in enumerate(lines, 1):
        ts = by_line.get(no)
        if not ts:
            out.append(text)
            continue
        # część wiersza od pierwszego tokenu do końca ostatniego; reszta (komentarz) bez zmian
        pieces = [" " * rng.randint(0, 8)]
        for k, t in enumerate(ts):
            a = t.col - 1
            b = ts[k + 1].col - 1 if k + 1 < len(ts) else a + len(t.text)
            tok = text[a:a + len(t.text)]
            gap = text[a + len(t.text):b] if k + 1 < len(ts) else ""
            pieces.append(tok)
            if k + 1 < len(ts):
                pieces.append(gap + " " * rng.randint(0, 2) if gap else rng.choice(["", " "]))
        rest = text[ts[-1].col - 1 + len(ts[-1].text):]
        if rest.strip().startswith("//"):
            rest = " " * rng.randint(1, 6) + rest.strip()
        out.append("".join(pieces) + rest)
    return "\n".join(out)


def glued_ok(src):
    """Odstęp przed `?` zmienia znaczenie (operator vs dziura) — takich plików nie zaburzamy."""
    return "?" not in src


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "**", "*.rz"), recursive=True))
    bad = checked = 0
    rng = random.Random(7)
    for f in files:
        src = open(f, encoding="utf-8").read()
        try:
            out, ok = check_format(src)
        except CompileError:
            continue            # pliki z celowym błędem składni
        checked += 1
        name = os.path.relpath(f, ROOT)
        if not ok:
            print(f"FAIL  {name}: zmienione drzewo lub komentarze"); bad += 1; continue
        if format_source(out) != out:
            print(f"FAIL  {name}: brak idempotencji"); bad += 1; continue
        if glued_ok(src):
            for _ in range(N):
                p = perturb(out, rng)
                try:
                    q = format_source(p)
                except CompileError as e:
                    print(f"FAIL  {name}: zaburzenie nie parsuje się ({e})"); bad += 1; break
                if q != out:
                    print(f"FAIL  {name}: postać kanoniczna zależy od odstępów"); bad += 1
                    open("/tmp/fmt_fail_in.rz", "w").write(p)
                    break
    print(f"plików: {checked}, błędów: {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
