# SPDX-License-Identifier: MIT OR Apache-2.0
"""Uruchamia przypadki testowe: pierwszy wiersz `// expect: ok` albo `// expect: KOD, KOD`."""
import glob, os, sys, re, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rdzen.driver import compile_source

ok = True
for path in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "cases", "*.rz"))):
    src = open(path, encoding="utf-8").read()
    m = re.match(r"//\s*expect:\s*(.*)", src)
    if not m:
        continue
    want = set() if m.group(1).strip() == "ok" else {c.strip() for c in m.group(1).split(",")}
    t = time.time()
    res = compile_source(src)
    got = {d.code for d in res.diags if d.severity in ("error", "warning")}
    passed = got == want
    ok &= passed
    print(f"{'PASS' if passed else 'FAIL'}  {os.path.basename(path):22} {time.time()-t:5.2f}s  oczekiwano {sorted(want) or 'ok'}, otrzymano {sorted(got) or 'ok'}")
sys.exit(0 if ok else 1)
