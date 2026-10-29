# SPDX-License-Identifier: MIT OR Apache-2.0
"""Lekser Rdzenia z regułą wstawiania średników (§2.1–2.2)."""
from __future__ import annotations
from dataclasses import dataclass
from .ast import Span
from .diag import err

KEYWORDS = set("""actor as assert break const continue data decreases else ensures
examples exists extern false fn for forall if import in inout invariant let match
old partial pub receives recv requires result return self send spawn spec true type
var where while""".split())

# tokeny, po których koniec wiersza wstawia ';'
SEMI_AFTER = {"IDENT", "TIDENT", "HOLE", "INT", "STR", ")", "]", "}",
              "return", "break", "continue", "?", "true", "false", "result", "self"}

PUNCT = ["..", "->", "=>", "==", "!=", "<=", ">=", "&&", "||",
         "(", ")", "{", "}", "[", "]", ",", ":", ";", ".", "=", "<", ">",
         "+", "-", "*", "/", "%", "!", "&", "?"]


@dataclass
class Tok:
    kind: str        # IDENT, TIDENT, HOLE, INT, STR, EOF, słowo kluczowe lub interpunkcja
    text: str
    value: object
    line: int
    col: int
    implicit: bool = False   # średnik wstawiony przez regułę układu

    @property
    def span(self):
        return Span(self.line, self.col, self.line, self.col + max(1, len(self.text)))


def lex(src: str) -> list:
    toks = []
    i, line, col = 0, 1, 1
    n = len(src)

    def last_kind():
        return toks[-1].kind if toks else None

    while i < n:
        c = src[i]
        if c == "\n":
            if last_kind() in SEMI_AFTER:
                toks.append(Tok(";", ";", None, line, col, implicit=True))
            i += 1; line += 1; col = 1
            continue
        if c in " \t\r":
            i += 1; col += 1
            continue
        if src.startswith("//", i):
            while i < n and src[i] != "\n":
                i += 1; col += 1
            continue
        start_col = col
        if c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            word = src[i:j]
            if word in KEYWORDS:
                kind = word
            elif word[0].isupper():
                kind = "TIDENT"
            else:
                kind = "IDENT"
            toks.append(Tok(kind, word, word, line, start_col))
            col += j - i; i = j
            continue
        if c == "?":
            nxt = src[i + 1] if i + 1 < n else ""
            # '?' przyklejony do wyrażenia to operator, w przeciwnym razie '?nazwa' to dziura
            glued = bool(toks) and src[i - 1] not in " \t\n" and toks[-1].kind in ("IDENT", ")", "]")
            if (nxt.islower() or nxt == "_") and not glued:
                j = i + 1
                while j < n and (src[j].isalnum() or src[j] == "_"):
                    j += 1
                toks.append(Tok("HOLE", src[i:j], src[i + 1:j], line, start_col))
                col += j - i; i = j
                continue
        if c.isdigit():
            j = i
            if src.startswith(("0x", "0X"), i):
                j = i + 2
                while j < n and (src[j] in "0123456789abcdefABCDEF_"):
                    j += 1
                text = src[i:j]; val = int(text[2:].replace("_", ""), 16)
            elif src.startswith(("0b", "0B"), i):
                j = i + 2
                while j < n and src[j] in "01_":
                    j += 1
                text = src[i:j]; val = int(text[2:].replace("_", ""), 2)
            else:
                while j < n and (src[j].isdigit() or src[j] == "_"):
                    j += 1
                if j < n and src[j] == "." and j + 1 < n and src[j + 1].isdigit():
                    raise err("E0010", Span(line, start_col, line, start_col + (j - i)),
                              "liczby zmiennoprzecinkowe nie są obsługiwane w prototypie", ["2.1"])
                text = src[i:j]
                if text.endswith("_") or "__" in text:
                    raise err("E0011", Span(line, start_col, line, start_col + len(text)),
                              "separator `_` dozwolony tylko między cyframi", ["2.1"])
                val = int(text.replace("_", ""))
            toks.append(Tok("INT", text, val, line, start_col))
            col += j - i; i = j
            continue
        if c == '"':
            j = i + 1
            while j < n and src[j] != '"':
                if src[j] == "\n":
                    break
                j += 2 if src[j] == "\\" else 1
            if j >= n or src[j] != '"':
                raise err("E0012", Span(line, start_col, line, start_col + 1), "niezamknięty literał napisowy", ["2.1"])
            text = src[i:j + 1]
            toks.append(Tok("STR", text, text[1:-1], line, start_col))
            col += j + 1 - i; i = j + 1
            continue
        for p in PUNCT:
            if src.startswith(p, i):
                toks.append(Tok(p, p, None, line, start_col))
                i += len(p); col += len(p)
                break
        else:
            raise err("E0001", Span(line, col, line, col + 1), f"nieoczekiwany znak `{c}`", ["2.1"])
    if last_kind() in SEMI_AFTER:
        toks.append(Tok(";", ";", None, line, col, implicit=True))
    toks.append(Tok("EOF", "", None, line, col))
    return toks
