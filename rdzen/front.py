# SPDX-License-Identifier: MIT OR Apache-2.0
"""Front-end: parsowanie preludium i programu, kontrola statyczna."""
import os
from .parser import parse
from .check import Checker
from .diag import CompileError

PRELUDE_PATH = os.path.join(os.path.dirname(__file__), "prelude.rz")


def load(src: str):
    """Zwraca (program, checker, diagnostyki). Program None przy błędzie składni."""
    prelude = parse(open(PRELUDE_PATH, encoding="utf-8").read())
    try:
        prog = parse(src)
    except CompileError as e:
        return None, None, [e.diag]
    ch = Checker(prog, prelude)
    diags = ch.run()
    return prog, ch, diags
