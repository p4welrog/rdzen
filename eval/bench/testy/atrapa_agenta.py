# SPDX-License-Identifier: MIT OR Apache-2.0
"""Atrapa agenta do samotestu agent.py --bez-kontenera: kopiuje gotowe rozwiązanie z testy/agent/
i wypisuje transkrypt w formacie stream-json (z jednym podejrzanym wywołaniem do sprawdzenia audytu)."""
import json
import os
import shutil

zid, w, praca = os.environ["RZ_ZADANIE"], os.environ["RZ_WARIANT"], os.environ["RZ_PRACA"]
ext = "rz" if w == "AR" else "py"
src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent", f"{zid}.{w}.{ext}")
assert os.path.exists(os.path.join(praca, "ZADANIE.md"))
if os.path.exists(src):
    shutil.copy(src, os.path.join(praca, f"rozwiazanie.{ext}"))
cmd = "git clone https://github.com/p4welrog/rdzen" if zid == "B-19" else "python3 -c 'print(1)'"
print(json.dumps({"type": "assistant", "message": {"content": [
    {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}}))
print(json.dumps({"type": "result", "num_turns": 3, "total_cost_usd": 0.01, "is_error": False,
                  "usage": {"input_tokens": 10, "output_tokens": 20, "cache_read_input_tokens": 100}}))
