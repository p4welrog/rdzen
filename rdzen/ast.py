# SPDX-License-Identifier: MIT OR Apache-2.0
"""Drzewo składni Rdzenia (podzbiór prototypu)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass(frozen=True)
class Span:
    line: int
    col: int
    end_line: int
    end_col: int

    def key(self):
        return (self.line, self.col)


NOSPAN = Span(0, 0, 0, 0)


class Node:
    span: Span
    ty: Any = None          # typ kształtu nadawany przez kontroler


# ---------------- typy ----------------
@dataclass(eq=False)
class TName(Node):
    name: str
    args: list
    span: Span = NOSPAN


@dataclass(eq=False)
class TRefine(Node):
    base: Node
    formula: Node
    span: Span = NOSPAN


# ---------------- deklaracje ----------------
@dataclass(eq=False)
class Param(Node):
    name: str
    type: Node
    inout: bool
    span: Span = NOSPAN


@dataclass(eq=False)
class Example(Node):
    expr: Node
    binders: Optional[list] = None   # [(name, TypeExpr)] dla testu właściwości
    span: Span = NOSPAN


@dataclass(eq=False)
class FnDecl(Node):
    name: str
    tparams: list
    params: list
    ret: Optional[Node]
    requires: list
    ensures: list
    decreases: Optional[Node]
    examples: list
    body: Optional["Block"]
    partial: bool
    pub: bool
    span: Span = NOSPAN
    builtin: bool = False
    lemma: bool = False


@dataclass(eq=False)
class Ctor(Node):
    name: str
    fields: list          # [(name, TypeExpr)]
    span: Span = NOSPAN


@dataclass(eq=False)
class DataDecl(Node):
    name: str
    tparams: list
    ctors: list
    where: Optional[Node]
    span: Span = NOSPAN


@dataclass(eq=False)
class TypeAlias(Node):
    name: str
    tparams: list
    type: Node
    span: Span = NOSPAN


@dataclass(eq=False)
class SpecFn(Node):
    name: str
    tparams: list
    params: list
    body: Node
    span: Span = NOSPAN
    ret: Optional[Node] = None
    decreases: Optional[Node] = None


@dataclass(eq=False)
class ConstDecl(Node):
    name: str
    type: Node
    expr: Node
    span: Span = NOSPAN


@dataclass(eq=False)
class Program(Node):
    items: list
    span: Span = NOSPAN


# ---------------- instrukcje ----------------
@dataclass(eq=False)
class Block(Node):
    stmts: list
    span: Span = NOSPAN


@dataclass(eq=False)
class Let(Node):
    name: str
    type: Optional[Node]
    expr: Node
    mutable: bool
    span: Span = NOSPAN


@dataclass(eq=False)
class Assign(Node):
    name: str
    expr: Node
    span: Span = NOSPAN


@dataclass(eq=False)
class IndexAssign(Node):
    name: str
    index: Node
    expr: Node
    span: Span = NOSPAN


@dataclass(eq=False)
class While(Node):
    cond: Node
    invariants: list
    decreases: Optional[Node]
    body: Block
    span: Span = NOSPAN


@dataclass(eq=False)
class For(Node):
    var: str
    iterable: Node
    invariants: list
    decreases: Optional[Node]
    body: Block
    span: Span = NOSPAN


@dataclass(eq=False)
class Return(Node):
    expr: Optional[Node]
    span: Span = NOSPAN


@dataclass(eq=False)
class Break(Node):
    span: Span = NOSPAN


@dataclass(eq=False)
class Continue(Node):
    span: Span = NOSPAN


@dataclass(eq=False)
class Assert(Node):
    formula: Node
    span: Span = NOSPAN


@dataclass(eq=False)
class ExprStmt(Node):
    expr: Node
    span: Span = NOSPAN


# ---------------- wyrażenia ----------------
@dataclass(eq=False)
class IntLit(Node):
    value: int
    span: Span = NOSPAN


@dataclass(eq=False)
class BoolLit(Node):
    value: bool
    span: Span = NOSPAN


@dataclass(eq=False)
class UnitLit(Node):
    span: Span = NOSPAN


@dataclass(eq=False)
class Name(Node):
    name: str
    span: Span = NOSPAN


@dataclass(eq=False)
class Unary(Node):
    op: str
    expr: Node
    span: Span = NOSPAN


@dataclass(eq=False)
class Binary(Node):
    op: str
    left: Node
    right: Node
    span: Span = NOSPAN


@dataclass(eq=False)
class Arg(Node):
    expr: Optional[Node]
    inout: Optional[str]          # nazwa zmiennej dla &x
    span: Span = NOSPAN


@dataclass(eq=False)
class Call(Node):
    name: str
    args: list
    span: Span = NOSPAN
    callee: Any = None            # rozwiązana deklaracja
    targs: Any = None             # podstawienie typów


@dataclass(eq=False)
class CtorCall(Node):
    name: str
    args: list
    span: Span = NOSPAN


@dataclass(eq=False)
class ArrayLit(Node):
    items: list
    span: Span = NOSPAN


@dataclass(eq=False)
class Index(Node):
    expr: Node
    index: Node
    span: Span = NOSPAN


@dataclass(eq=False)
class Field(Node):
    expr: Node
    name: str
    span: Span = NOSPAN


@dataclass(eq=False)
class If(Node):
    cond: Node
    then: Block
    els: Optional[Node]       # Block | If | None
    span: Span = NOSPAN


@dataclass(eq=False)
class Pattern(Node):
    kind: str                 # 'wild' | 'var' | 'int' | 'bool' | 'ctor'
    name: Optional[str] = None
    value: Any = None
    args: list = field(default_factory=list)
    span: Span = NOSPAN


@dataclass(eq=False)
class Arm(Node):
    pattern: Pattern
    guard: Optional[Node]
    body: Node
    span: Span = NOSPAN


@dataclass(eq=False)
class Match(Node):
    expr: Node
    arms: list
    span: Span = NOSPAN


@dataclass(eq=False)
class BlockExpr(Node):
    block: Block
    span: Span = NOSPAN


@dataclass(eq=False)
class Quant(Node):
    kind: str                 # 'forall' | 'exists'
    var: str
    lo: Node
    hi: Node
    body: Node
    span: Span = NOSPAN


@dataclass(eq=False)
class Old(Node):
    name: str
    span: Span = NOSPAN


@dataclass(eq=False)
class ResultRef(Node):
    span: Span = NOSPAN


@dataclass(eq=False)
class SelfRef(Node):
    span: Span = NOSPAN


@dataclass(eq=False)
class Hole(Node):
    name: str
    span: Span = NOSPAN


def walk(node):
    """Przechodzi po wszystkich węzłach (pre-order)."""
    if isinstance(node, list):
        for n in node:
            yield from walk(n)
        return
    if not isinstance(node, Node):
        if isinstance(node, tuple):
            for n in node:
                yield from walk(n)
        return
    yield node
    for k, v in vars(node).items():
        if k in ("span", "ty", "callee", "targs"):
            continue
        if isinstance(v, (Node, list, tuple)):
            yield from walk(v)
