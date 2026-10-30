# SPDX-License-Identifier: MIT OR Apache-2.0
"""Prompty trzech wariantów.

P  — Python, jedna odpowiedź, bez informacji zwrotnej (jak linia bazowa VeraBench).
PT — Python z testami pisanymi przez model; testy są uruchamiane, porażki wracają do modelu.
R  — Rdzeń; system zawiera REFERENCE.md, diagnostyka `rzc check` wraca do modelu.
Treść zadań jest po angielsku (jak w VeraBench); referencja Rdzenia jest po polsku."""
from __future__ import annotations

import os
import re

KORZEN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

SYS_PY = "You are an expert Python programmer. Write correct, concise Python 3.11+ code."
SYS_R = ("You are an expert programmer writing in Rdzeń, a small programming language whose contracts "
         "(requires/ensures, loop invariants, bounds and overflow conditions) are verified statically by an SMT "
         "solver. Rdzeń is not in your training data; the language reference below (in Polish) is the authoritative "
         "source.\n\n")


def referencja() -> str:
    return open(os.path.join(KORZEN, "REFERENCE.md"), encoding="utf-8").read()


def _wspolne(z) -> str:
    return f"{z.tytul}\n\n{z.opis_pelny()}\n\n"


def _py_typy(z) -> str:
    pre = z.python_preambula()
    if not pre:
        return ""
    return ("The following definitions are already in scope; do not redefine or import them:\n\n"
            f"```python\n{pre}```\n\n")


def prompt(z, wariant: str) -> dict:
    if wariant == "P":
        user = (_wspolne(z) + _py_typy(z) + f"Write a Python function with this signature:\n\n    {z.sygnatura_python()}\n\n"
                "Output only the Python code in a single ```python block, no explanation.")
        return {"system": SYS_PY, "user": user}
    if wariant == "PT":
        user = (_wspolne(z) + _py_typy(z) + f"Write a Python function with this signature:\n\n    {z.sygnatura_python()}\n\n"
                "In the same file, write tests for it as functions named test_... that use assert; do not call them. "
                "Your tests will be run and any failures will be shown to you. Choose tests that would expose "
                "mistakes in the function. Output only the Python code in a single ```python block, no explanation.")
        return {"system": SYS_PY, "user": user}
    if wariant == "R":
        dane = ""
        if z.dane:
            dane = ("The program must contain these type definitions exactly as written:\n\n```rdzen\n"
                    + "\n".join(d.rdzen() for d in z.dane) + "\n```\n\n")
        user = (_wspolne(z) + dane +
                f"Write a Rdzeń program containing a function with this signature:\n\n    {z.sygnatura_rdzen()}\n\n"
                "Parameter and result types must match (you may add refinements such as `where` clauses and any "
                "requires/ensures). A caller may pass any input allowed by the description above, so requires must "
                "not exclude such inputs. Write ensures clauses that specify the result as completely as you can, and "
                "add helper functions, spec functions or lemmas as needed. The program will be checked with "
                "`rzc fmt -w` followed by `rzc check`; diagnostics will be shown to you. A program is accepted when "
                "rzc check reports no errors. Output only the program in a single ```rdzen block, no explanation.")
        return {"system": SYS_R + referencja(), "user": user}
    raise ValueError(wariant)


def poprawka(wariant: str, tekst: str) -> str:
    if wariant == "PT":
        return ("Running your tests produced:\n\n" + tekst + "\n\nFix the function or the tests. "
                "Output the complete file in a single ```python block, no explanation.")
    return ("`rzc check` reported:\n\n" + tekst + "\n\nFix the program. "
            "Output the complete program in a single ```rdzen block, no explanation.")


_BLOK = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)```", re.S)


def wyciagnij_kod(odp: str) -> str:
    m = _BLOK.findall(odp)
    if m:
        return max(m, key=len).rstrip() + "\n"
    return odp.strip() + "\n"
