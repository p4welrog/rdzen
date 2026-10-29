# SPDX-License-Identifier: MIT OR Apache-2.0
"""Diagnostyka Rdzenia (rozdz. 9 specyfikacji): rekord, postać tekstowa i JSON."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import json

from .ast import Span, NOSPAN


@dataclass
class Diagnostic:
    code: str
    severity: str                     # error | warning | info | hole
    span: Span
    message: str
    spec_ref: list = field(default_factory=list)
    expected: Optional[str] = None
    found: Optional[str] = None
    obligation: Optional[dict] = None
    counterexample: Optional[dict] = None
    goal: Optional[dict] = None
    fix: Optional[dict] = None
    notes: list = field(default_factory=list)       # dodatkowe wiersze "= ..."
    related: list = field(default_factory=list)
    label: Optional[str] = None                     # opis pod znacznikiem ^^^

    def sort_key(self):
        return (self.span.line, self.span.col, self.code)

    def to_json(self, file: str) -> dict:
        d = {
            "code": self.code,
            "severity": self.severity,
            "span": {"file": file, "line": self.span.line, "col": self.span.col,
                     "end_line": self.span.end_line, "end_col": self.span.end_col},
            "spec_ref": self.spec_ref,
            "message": self.message,
        }
        for k in ("expected", "found", "obligation", "counterexample", "goal", "fix"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        if self.notes:
            d["notes"] = self.notes
        d["related"] = self.related
        return d


class CompileError(Exception):
    def __init__(self, diag: Diagnostic):
        super().__init__(diag.message)
        self.diag = diag


def err(code, span, message, spec=None, **kw) -> CompileError:
    return CompileError(Diagnostic(code, "error", span, message, spec_ref=spec or [], **kw))


def render_text(d: Diagnostic, file: str, source_lines: list) -> str:
    sev = {"error": "error", "warning": "warning", "info": "info", "hole": "hole"}[d.severity]
    head = f"{sev}[{d.code}]: {d.message}"
    if d.spec_ref:
        ref = "[spec " + ", ".join(d.spec_ref) + "]"
        pad = max(2, 72 - len(head))
        head = head + " " * pad + ref
    out = [head]
    if d.span is not NOSPAN and d.span.line > 0:
        out.append(f"  --> {file}:{d.span.line}:{d.span.col}")
        ln = d.span.line
        if 0 < ln <= len(source_lines):
            src = source_lines[ln - 1].rstrip("\n")
            w = len(str(ln))
            out.append(" " * (w + 1) + " |")
            out.append(f" {ln} | {src}")
            if d.span.end_line == ln and d.span.end_col > d.span.col:
                n = d.span.end_col - d.span.col
            else:
                n = max(1, len(src) - d.span.col + 1)
            marker = " " * (d.span.col - 1) + "^" * n
            if d.label:
                marker += " " + d.label
            out.append(" " * (w + 1) + " | " + marker)
    if d.obligation and not d.label:
        out.append(f"   = zobowiązanie {d.obligation['id']}: {d.obligation['formula']}")
    if d.expected is not None:
        out.append(f"   = oczekiwano: {d.expected}")
    if d.found is not None:
        out.append(f"   = znaleziono: {d.found}")
    if d.counterexample:
        ce = d.counterexample
        cls = {"real": "rzeczywisty", "inductive": "indukcyjny — stan może być nieosiągalny"}[ce["class"]]
        rep = {"confirmed": "odtworzony", "not-reproduced": "nieodtworzony",
               "not-replayable": "bez odtwarzania"}[ce["replay"]]
        out.append(f"   = kontrprzykład ({cls}; {rep}):")
        for k, v in ce["assignment"].items():
            desc = ce.get("descriptions", {}).get(k)
            out.append(f"       {k} = {v}" + (f"      ({desc})" if desc else ""))
        for t in ce.get("trace_text", []):
            out.append(f"       {t}")
    if d.goal:
        g = d.goal
        out.append(f"   = typ:        {g['type']}")
        out.append(f"   = cel:        {g['goal']}")
        if g.get("hypotheses"):
            out.append(f"   = hipotezy:   " + ",  ".join(g["hypotheses"]))
        out.append(f"   = kontekst:   " + ", ".join(f"{c['name']}: {c['type']}" for c in g["context"]))
        if g.get("candidates"):
            first = True
            for c in g["candidates"]:
                txt = c["expr"] + ("" if c["status"] == "satisfies" else f"   (jeśli {c['condition']})")
                out.append(("   = kandydaci:  " if first else "                 ") + txt)
                first = False
    for n in d.notes:
        out.append(f"   = {n}")
    if d.fix:
        conf = {"unique": "jednoznaczna", "suggested": "sugerowana"}[d.fix["confidence"]]
        out.append(f"   = poprawka ({conf}):")
        for pl in d.fix["patch"].rstrip("\n").split("\n"):
            out.append("       " + pl)
    return "\n".join(out)


def dumps_json(diags, file) -> str:
    return json.dumps([d.to_json(file) for d in diags], ensure_ascii=False, indent=2)
