"""
laudas.py — v0 prototype for the Laudas language

A single-file, dependency-free Python implementation of:
  - Wire-format parser (slot-based grammar)
  - Body interpreter (int arithmetic, if/else, return, Option types)
  - Example runner (executes ex slots, reports mismatches)
  - LLM-shaped error format (structured JSON + plain English)

Limitations of v0 (intentional):
  - No Z3 / SMT verification yet — that's v0.1.
  - Body language is a tiny subset: int arithmetic, comparisons,
    if/else with braces, return, Some(...) / None.
  - No method calls, no module-qualified calls, no string concat.
  - Refinement types are parsed but not checked at the boundary
    (Z3 will do that in v0.1).

Usage:
    python laudas.py path/to/file.laud
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

# Force UTF-8 stdout/stderr so unicode (✓ ✗ · ─) renders on Windows cp1252 consoles.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


# ---------- AST ----------

@dataclass
class Type:
    base: str                       # "int", "bool", "int?", "str", ...
    refinement: Optional[str] = None  # e.g., "> 0", "0..=100"


@dataclass
class Param:
    name: str
    type: Type


@dataclass
class TypeAlias:
    """Top-level record/struct type declaration: `type NAME { f1: T1, f2: T2 }`."""
    name: str
    fields: list["Param"]
    line: int = 0


@dataclass
class ExternRef:
    backend: str   # "python" for v0.5; later "js", "c", etc.
    ref: str       # e.g. "math.isqrt"


@dataclass
class Function:
    name: str
    vis: str = ""
    eff: str = ""
    for_iface: Optional[str] = None
    ins: list[Param] = field(default_factory=list)
    out: Optional[Type] = None
    exs: list[str] = field(default_factory=list)
    reqs: list[str] = field(default_factory=list)
    enses: list[str] = field(default_factory=list)
    prose: Optional[str] = None
    body: list[str] = field(default_factory=list)
    extern: Optional[ExternRef] = None
    line: int = 0  # source line for diagnostics


# ---------- Lexer / parser ----------

class ParseError(Exception):
    def __init__(self, msg: str, line: int):
        super().__init__(msg)
        self.msg = msg
        self.line = line


def parse_file(path: str) -> tuple[list[Function], list[TypeAlias]]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    lines = text.split("\n")
    functions: list[Function] = []
    types: list[TypeAlias] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            i += 1
            continue
        if stripped.startswith("module "):
            # ignored in v0
            i += 1
            continue
        if stripped.startswith("fn "):
            fn, i = parse_function(lines, i)
            functions.append(fn)
            continue
        if stripped.startswith("type "):
            ta, i = parse_type_alias(lines, i)
            types.append(ta)
            continue
        raise ParseError(f"unexpected top-level line: {line!r}", i + 1)
    return functions, types


def parse_type_alias(lines: list[str], start: int) -> tuple[TypeAlias, int]:
    # Single-line form: `type NAME { f: T, g: T2 }` (may span lines if braces unbalanced)
    buf = lines[start]
    depth = buf.count("{") - buf.count("}")
    j = start
    while depth > 0 and j + 1 < len(lines):
        j += 1
        buf += "\n" + lines[j]
        depth = buf.count("{") - buf.count("}")
    s = buf.strip()
    m = re.match(r"^type\s+([A-Za-z_]\w*)\s*\{(.*)\}\s*$", s, flags=re.DOTALL)
    if not m:
        raise ParseError(f"malformed type alias: {s!r}", start + 1)
    name = m.group(1)
    fields_str = m.group(2).strip()
    fields: list[Param] = []
    if fields_str:
        for part in split_top_level_commas(fields_str):
            part = part.strip()
            if not part:
                continue
            fields.append(parse_param(part, start + 1))
    return TypeAlias(name=name, fields=fields, line=start + 1), j + 1


def parse_function(lines: list[str], start: int) -> tuple[Function, int]:
    fn_line = lines[start].strip()
    name = fn_line[3:].strip()
    fn = Function(name=name, line=start + 1)
    i = start + 1
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith(";"):
            i += 1
            continue
        if stripped.startswith("vis "):
            fn.vis = stripped[4:].strip()
        elif stripped.startswith("eff "):
            fn.eff = stripped[4:].strip()
        elif stripped.startswith("for "):
            fn.for_iface = stripped[4:].strip()
        elif stripped.startswith("in "):
            fn.ins.append(parse_param(stripped[3:], i + 1))
        elif stripped.startswith("out "):
            fn.out = parse_type(stripped[4:])
        elif stripped.startswith("ex "):
            fn.exs.append(stripped[3:].strip())
        elif stripped.startswith("req "):
            fn.reqs.append(stripped[4:].strip())
        elif stripped.startswith("ens "):
            fn.enses.append(stripped[4:].strip())
        elif stripped.startswith("prose "):
            rest = stripped[6:].strip()
            if rest.startswith('"') and rest.endswith('"'):
                rest = rest[1:-1]
            fn.prose = rest
        elif stripped.startswith("extern "):
            rest = stripped[7:].strip()
            m = re.match(r'^(\w+)\s+"([^"]+)"$', rest)
            if not m:
                raise ParseError(
                    f"malformed extern slot in fn {name!r}: expected `extern BACKEND \"REF\"`, got {stripped!r}",
                    i + 1,
                )
            fn.extern = ExternRef(backend=m.group(1), ref=m.group(2))
        elif stripped == "do":
            i += 1
            while i < len(lines) and lines[i].strip() != "end":
                fn.body.append(lines[i])
                i += 1
            if i >= len(lines):
                raise ParseError(f"function {name!r} missing `end`", fn.line)
            return fn, i + 1
        elif stripped == "end":
            return fn, i + 1
        else:
            raise ParseError(f"unknown slot in fn {name!r}: {stripped!r}", i + 1)
        i += 1
    raise ParseError(f"function {name!r} reached EOF without `end`", fn.line)


def parse_param(s: str, line: int) -> Param:
    if ":" not in s:
        raise ParseError(f"param missing ':': {s!r}", line)
    colon = s.index(":")
    name = s[:colon].strip()
    type_str = s[colon + 1:].strip()
    return Param(name, parse_type(type_str))


def parse_type(s: str) -> Type:
    s = s.strip()
    if "{" in s and "}" in s:
        op = s.index("{")
        cl = s.rindex("}")
        return Type(base=s[:op].strip(), refinement=s[op + 1:cl].strip())
    return Type(base=s)


# ---------- Value model ----------
#
# Internal value representation:
#   int             → Python int
#   bool            → Python bool
#   list<T>         → Python list
#   None (variant)  → ("None",)
#   Some(x)         → ("Some", x)
#   lambda          → LaudasLambda instance
#   error sentinel  → ("error", message)


@dataclass
class LaudasLambda:
    """A first-class function value (closure). Used for `.filter(x -> ...)` etc."""
    param: str
    body: str
    env: dict[str, Any]

    def call(self, arg: Any) -> Any:
        new_env = dict(self.env)
        new_env[self.param] = arg
        return eval_expr(self.body, new_env)


def fmt_value(v: Any) -> str:
    if isinstance(v, tuple):
        if v[0] == "None":
            return "None"
        if v[0] == "Some":
            return f"Some({fmt_value(v[1])})"
        if v[0] == "error":
            return f"<error: {v[1]}>"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "[" + ", ".join(fmt_value(x) for x in v) + "]"
    if isinstance(v, dict):
        type_name = v.get("__type__", "record")
        fields = [f"{k}: {fmt_value(val)}" for k, val in v.items() if not k.startswith("__")]
        return f"{type_name} {{ {', '.join(fields)} }}"
    if isinstance(v, LaudasLambda):
        return f"<lambda {v.param} -> ...>"
    return repr(v)


def parse_value(s: str) -> Any:
    s = s.strip()
    if s == "None":
        return ("None",)
    if s.startswith("Some(") and s.endswith(")"):
        return ("Some", parse_value(s[5:-1]))
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [parse_value(p.strip()) for p in split_top_level_commas(inner)]
    # Record literal: NAME { f: v, g: w }
    m = re.match(r"^([A-Za-z_]\w*)\s*\{(.*)\}\s*$", s, flags=re.DOTALL)
    if m and m.group(1) in TYPE_ALIASES:
        type_name = m.group(1)
        fields_str = m.group(2).strip()
        record: dict[str, Any] = {"__type__": type_name}
        if fields_str:
            for part in split_top_level_commas(fields_str):
                part = part.strip()
                if ":" not in part:
                    continue
                fname, fval = part.split(":", 1)
                record[fname.strip()] = parse_value(fval.strip())
        return record
    try:
        return int(s)
    except ValueError:
        pass
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    return s  # fallthrough — opaque token


def split_top_level_commas(s: str) -> list[str]:
    """Split `s` on commas at top level (outside parens/brackets/braces)."""
    out: list[str] = []
    buf = ""
    depth = 0
    for c in s:
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if c == "," and depth == 0:
            out.append(buf)
            buf = ""
        else:
            buf += c
    if buf.strip():
        out.append(buf)
    return out


# ---------- Method dispatch table ----------

def _list_first(xs: list) -> Any:
    return xs[0] if xs else ("None",)


def _list_last(xs: list) -> Any:
    return xs[-1] if xs else ("None",)


def _list_filter(xs: list, pred: Any) -> Any:
    if not isinstance(pred, LaudasLambda):
        raise RuntimeFail(".filter() needs a lambda, got " + fmt_value(pred))
    return [x for x in xs if pred.call(x)]


def _list_map(xs: list, fn: Any) -> Any:
    if not isinstance(fn, LaudasLambda):
        raise RuntimeFail(".map() needs a lambda, got " + fmt_value(fn))
    return [fn.call(x) for x in xs]


def _list_fold(xs: list, init: Any, fn: Any) -> Any:
    if not isinstance(fn, LaudasLambda):
        raise RuntimeFail(".fold() needs a lambda, got " + fmt_value(fn))
    # 2-arg lambda not supported in v0.5 — restrict fold to a sentinel-pair lambda
    raise RuntimeFail(".fold() needs a 2-arg lambda; not yet supported in v0.5")


# Module-level registry of type aliases, populated by check_file().
# eval_expr consults it to disambiguate `Name { ... }` record literals
# from `if EXPR { ... }` body statements.
TYPE_ALIASES: dict[str, TypeAlias] = {}


METHODS: dict[str, dict[str, Any]] = {
    "list": {
        "length":   lambda xs: len(xs),
        "sum":      lambda xs: sum(xs),
        "min":      lambda xs: min(xs) if xs else ("None",),
        "max":      lambda xs: max(xs) if xs else ("None",),
        "first":    _list_first,
        "last":     _list_last,
        "contains": lambda xs, x: x in xs,
        "filter":   _list_filter,
        "map":      _list_map,
        "fold":     _list_fold,
    },
    "str": {
        "length":   lambda s: len(s),
        "upper":    lambda s: s.upper(),
        "lower":    lambda s: s.lower(),
    },
    "int": {
        "abs":      lambda i: abs(i),
    },
}


def value_type_name(v: Any) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return "list"
    if isinstance(v, tuple) and v and v[0] in ("Some", "None"):
        return "option"
    return "unknown"


def dispatch_method(obj: Any, method: str, args: list[Any]) -> Any:
    t = value_type_name(obj)
    if t not in METHODS or method not in METHODS[t]:
        raise RuntimeFail(f"no method {method!r} on {t} value {fmt_value(obj)}")
    try:
        return METHODS[t][method](obj, *args)
    except TypeError as e:
        raise RuntimeFail(f".{method}() arity mismatch: {e}")


# ---------- Body interpreter ----------
#
# Tiny imperative subset:
#   stmt   ::= "return" expr
#            | "if" expr "{" stmt "}"   (single-statement then-branch)
#            | "if" expr "{" stmt "}" "else" "{" stmt "}"
#   expr   ::= int_literal | ident | expr op expr | "Some" "(" expr ")" | "None"
#            | "(" expr ")"


class RuntimeFail(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def run_body(fn: Function, args: list[Any]) -> Any:
    if len(args) != len(fn.ins):
        raise RuntimeFail(
            f"arity mismatch: {fn.name} expects {len(fn.ins)} args, got {len(args)}"
        )
    if fn.extern is not None:
        return call_foreign(fn, args)
    env: dict[str, Any] = {p.name: a for p, a in zip(fn.ins, args)}
    body_text = "\n".join(fn.body)
    return interp_block(body_text, env)


# ---------- Foreign function interface ----------

def call_foreign(fn: Function, args: list[Any]) -> Any:
    """Invoke an extern-declared function.
    v0.5 supports backend `python`: the ref is a dotted path like `math.isqrt`."""
    backend = fn.extern.backend
    ref = fn.extern.ref
    if backend != "python":
        raise RuntimeFail(f"extern backend {backend!r} not supported in v0.5 (only `python`)")
    parts = ref.split(".")
    if len(parts) < 2:
        raise RuntimeFail(f"extern python ref needs `module.func`, got {ref!r}")
    module_path = ".".join(parts[:-1])
    func_name = parts[-1]
    try:
        import importlib
        module = importlib.import_module(module_path)
        py_func = getattr(module, func_name)
    except (ImportError, AttributeError) as e:
        raise RuntimeFail(f"failed to load extern python ref {ref!r}: {e}")
    py_args = [_laudas_to_python(a) for a in args]
    try:
        py_result = py_func(*py_args)
    except Exception as e:
        raise RuntimeFail(f"extern python call {ref}({', '.join(map(repr, py_args))}) raised: {e}")
    return _python_to_laudas(py_result, fn.out)


def _laudas_to_python(v: Any) -> Any:
    """Convert a Laudas value to a plain Python value for foreign calls."""
    if isinstance(v, tuple) and v:
        if v[0] == "None":
            return None
        if v[0] == "Some":
            return _laudas_to_python(v[1])
    if isinstance(v, list):
        return [_laudas_to_python(x) for x in v]
    return v  # int, bool, str pass through


def _python_to_laudas(v: Any, expected: Optional[Type]) -> Any:
    """Convert a Python return value back to a Laudas value, hinted by the declared output type."""
    if v is None:
        return ("None",)
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return [_python_to_laudas(x, None) for x in v]
    if isinstance(v, float):
        # No float type yet — round-trip via int when sensible, else best-effort string
        if v.is_integer():
            return int(v)
        return v  # let downstream handle as opaque float
    if isinstance(v, tuple):
        return list(v)
    return v


def interp_block(text: str, env: dict[str, Any]) -> Any:
    # Walk top-level statements separated by newlines, respecting `if … { … }`.
    stmts = split_statements(text)
    for s in stmts:
        result = interp_stmt(s, env)
        if result is not _NO_RETURN:
            return result
    return ("None",)  # implicit fallthrough — treat as None


_NO_RETURN = object()  # sentinel: this statement didn't return


def split_statements(text: str) -> list[str]:
    # Each top-level statement is either a single line, or `if … { … }` possibly
    # spanning multiple lines via balanced braces.
    out: list[str] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        # If statement may span lines if braces don't balance on this line.
        if line.startswith("if "):
            buf = line
            depth = buf.count("{") - buf.count("}")
            j = i
            while depth > 0 and j + 1 < len(lines):
                j += 1
                buf += "\n" + lines[j].strip()
                depth = buf.count("{") - buf.count("}")
            out.append(buf)
            i = j + 1
            continue
        out.append(line)
        i += 1
    return out


def interp_stmt(stmt: str, env: dict[str, Any]) -> Any:
    s = stmt.strip()
    if s.startswith("return "):
        return eval_expr(s[7:].strip(), env)
    if s == "return":
        return ("None",)
    if s.startswith("if "):
        return interp_if(s, env)
    if s.startswith("let "):
        m = re.match(r"^let\s+([A-Za-z_]\w*)\s*=\s*(.+)$", s, flags=re.DOTALL)
        if not m:
            return ("error", f"malformed let statement: {s!r}")
        name, expr = m.groups()
        env[name] = eval_expr(expr.strip(), env)
        return _NO_RETURN
    return ("error", f"unsupported statement: {s!r}")


def interp_if(s: str, env: dict[str, Any]) -> Any:
    # Match `if COND { THEN } else { ELSE }` or `if COND { THEN }`
    m = re.match(r"^if\s+(.+?)\s*\{\s*(.+?)\s*\}\s*(?:else\s*\{\s*(.+?)\s*\})?\s*$",
                 s, flags=re.DOTALL)
    if not m:
        return ("error", f"malformed if: {s!r}")
    cond_str, then_str, else_str = m.groups()
    cond_val = eval_expr(cond_str, env)
    if cond_val is True:
        return interp_block(then_str, env)
    if else_str is not None:
        return interp_block(else_str, env)
    return _NO_RETURN


# ---------- Expression evaluator ----------

def eval_expr(expr: str, env: dict[str, Any]) -> Any:
    s = expr.strip()

    # 1. Strip balanced outer parens
    if s.startswith("(") and s.endswith(")") and balanced(s):
        return eval_expr(s[1:-1], env)

    # 2. Lambda: `IDENT -> EXPR` (lowest precedence)
    arrow_idx = find_top_level_substr(s, "->")
    if arrow_idx >= 0:
        lhs = s[:arrow_idx].strip()
        rhs = s[arrow_idx + 2:].strip()
        if re.match(r"^[A-Za-z_]\w*$", lhs):
            return LaudasLambda(param=lhs, body=rhs, env=dict(env))
        # else: fall through (might be a type-annotation arrow somewhere; let parser fail later)

    # 3. Binary operators, lowest precedence first.
    for ops in [
        ("||",), ("&&",),
        ("==", "!="),
        ("<=", ">=", "<", ">"),
        ("+", "-"),
        ("*", "/", "%"),
    ]:
        idx, op = find_binary_op(s, ops)
        if idx >= 0:
            left = eval_expr(s[:idx], env)
            right = eval_expr(s[idx + len(op):], env)
            return apply_op(op, left, right)

    # 4. Postfix method call: PREFIX.METHOD(args)
    pm = try_match_postfix_method(s)
    if pm is not None:
        prefix, method, args_str = pm
        obj = eval_expr(prefix, env)
        args = [eval_expr(a, env) for a in split_top_level_commas(args_str)] if args_str.strip() else []
        return dispatch_method(obj, method, args)

    # 4b. Postfix field access: PREFIX.FIELD (no parens)
    pf = try_match_postfix_field(s)
    if pf is not None:
        prefix, field = pf
        obj = eval_expr(prefix, env)
        if isinstance(obj, dict):
            if field in obj:
                return obj[field]
            raise RuntimeFail(f"no field {field!r} on record (has: {list(k for k in obj if not k.startswith('__'))})")
        raise RuntimeFail(f"cannot access field {field!r} on non-record value {fmt_value(obj)}")

    # 5. List literal: [a, b, c]
    if s.startswith("[") and s.endswith("]") and balanced_brackets(s):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [eval_expr(p, env) for p in split_top_level_commas(inner)]

    # 5b. Record literal: TYPE_NAME { field: value, field: value, ... }
    rl_match = re.match(r"^([A-Za-z_]\w*)\s*\{(.*)\}\s*$", s, flags=re.DOTALL)
    if rl_match:
        type_name = rl_match.group(1)
        fields_str = rl_match.group(2).strip()
        if type_name in TYPE_ALIASES:
            record: dict[str, Any] = {"__type__": type_name}
            if fields_str:
                for part in split_top_level_commas(fields_str):
                    part = part.strip()
                    if ":" not in part:
                        raise RuntimeFail(f"malformed record-literal field: {part!r}")
                    fname, fval = part.split(":", 1)
                    record[fname.strip()] = eval_expr(fval.strip(), env)
            return record

    # 6. Some(EXPR)
    if s.startswith("Some(") and s.endswith(")") and balanced(s):
        return ("Some", eval_expr(s[5:-1], env))

    # 7. None
    if s == "None":
        return ("None",)

    # 8. Booleans
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False

    # 9. Int literal
    if re.match(r"^-?\d+$", s):
        return int(s)

    # 10. String literal
    if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
        return s[1:-1]

    # 11. Bare identifier
    if re.match(r"^[A-Za-z_]\w*$", s):
        if s in env:
            return env[s]
        raise RuntimeFail(f"unbound identifier: {s!r}")

    raise RuntimeFail(f"cannot evaluate: {s!r}")


# ---------- Helpers for the new parser branches ----------

def find_top_level_substr(s: str, sub: str) -> int:
    """Leftmost top-level occurrence of `sub`, or -1."""
    depth = 0
    n = len(s)
    sl = len(sub)
    i = 0
    while i < n:
        c = s[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0 and s[i:i + sl] == sub:
            return i
        i += 1
    return -1


def balanced_brackets(s: str) -> bool:
    depth = 0
    for i, c in enumerate(s):
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0 and i < len(s) - 1:
                return False
    return depth == 0


def try_match_postfix_method(s: str):
    """Match a trailing `.METHOD(args)` postfix. Returns (prefix, method, args_str) or None."""
    s = s.strip()
    if not s.endswith(")"):
        return None
    # Find the `(` matching the trailing `)`.
    open_idx = -1
    depth = 0
    for i in range(len(s) - 1, -1, -1):
        c = s[i]
        if c == ")":
            depth += 1
        elif c == "(":
            depth -= 1
            if depth == 0:
                open_idx = i
                break
    if open_idx <= 0:
        return None
    # Walk back from `(` to find the method name (alphanumeric + _).
    m_start = open_idx
    while m_start > 0 and (s[m_start - 1].isalnum() or s[m_start - 1] == "_"):
        m_start -= 1
    if m_start == open_idx:
        return None  # empty name
    method_name = s[m_start:open_idx]
    # Require a `.` before the method name, and something before the `.`.
    if m_start == 0 or s[m_start - 1] != ".":
        return None
    if m_start - 1 == 0:
        return None
    prefix = s[: m_start - 1]
    args_str = s[open_idx + 1: -1]
    return prefix, method_name, args_str


def try_match_postfix_field(s: str):
    """Match a trailing `.FIELD` postfix (no parens). Returns (prefix, field) or None."""
    s = s.strip()
    if not s or not (s[-1].isalnum() or s[-1] == "_"):
        return None
    # Walk back to find the start of the trailing identifier.
    i = len(s)
    while i > 0 and (s[i - 1].isalnum() or s[i - 1] == "_"):
        i -= 1
    field = s[i:]
    if not re.match(r"^[A-Za-z_]\w*$", field):
        return None
    if i == 0 or s[i - 1] != ".":
        return None
    prefix = s[: i - 1]
    if not prefix:
        return None
    # Prefix must be a balanced expression (no half-open parens/brackets/braces).
    if not balanced(prefix) or not balanced_brackets(prefix) or not balanced_braces(prefix):
        return None
    return prefix, field


def balanced_braces(s: str) -> bool:
    depth = 0
    for c in s:
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def balanced(s: str) -> bool:
    depth = 0
    for i, c in enumerate(s):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0 and i < len(s) - 1:
                return False  # closes before end
    return depth == 0


def find_binary_op(s: str, ops: tuple[str, ...]) -> tuple[int, str]:
    """Return (index, op) of the rightmost top-level occurrence of any op in `ops`,
    or (-1, '') if none. Rightmost gives left-to-right associativity once we recurse.
    Top-level skips inside parens/brackets/braces (so `{x: 1+2}` doesn't match `+`)."""
    depth = 0
    best = (-1, "")
    i = 0
    while i < len(s):
        c = s[i]
        if c in "([{":
            depth += 1
            i += 1
            continue
        if c in ")]}":
            depth -= 1
            i += 1
            continue
        if depth == 0:
            for op in ops:
                if s[i:i + len(op)] == op:
                    # Skip negative-number leading minus: ` -3` at start
                    if op == "-" and (i == 0 or s[i - 1] in "+-*/%<>=!(  "):
                        if i == 0:
                            i += 1
                            continue
                    best = (i, op)
                    i += len(op)
                    break
            else:
                i += 1
                continue
            continue
        i += 1
    return best


def apply_op(op: str, left: Any, right: Any) -> Any:
    if op == "==":
        return values_equal(left, right)
    if op == "!=":
        return not values_equal(left, right)
    if op in ("+", "-", "*", "/", "%", "<", ">", "<=", ">="):
        if not (isinstance(left, int) and isinstance(right, int)):
            raise RuntimeFail(f"op {op} requires int operands, got {fmt_value(left)} and {fmt_value(right)}")
        if op == "/":
            if right == 0:
                raise RuntimeFail("division by zero")
            return left // right
        if op == "%":
            if right == 0:
                raise RuntimeFail("modulo by zero")
            return left % right
        return {
            "+": left + right,
            "-": left - right,
            "*": left * right,
            "<": left < right,
            ">": left > right,
            "<=": left <= right,
            ">=": left >= right,
        }[op]
    raise RuntimeFail(f"unsupported op: {op!r}")


def values_equal(a: Any, b: Any) -> bool:
    if isinstance(a, tuple) and isinstance(b, tuple):
        if a[0] != b[0]:
            return False
        if a[0] == "None":
            return True
        if a[0] == "Some":
            return values_equal(a[1], b[1])
    return a == b


# ---------- Example runner ----------

@dataclass
class ExampleResult:
    raw: str
    ok: bool
    expected: Any = None
    actual: Any = None
    error: Optional[str] = None


def run_example(fn: Function, ex_str: str) -> ExampleResult:
    # Strip trailing comments after `--`
    if "--" in ex_str:
        ex_str = ex_str.split("--", 1)[0].strip()
    if "==" not in ex_str:
        return ExampleResult(raw=ex_str, ok=False, error=f"example missing ==: {ex_str!r}")
    call_str, expected_str = ex_str.split("==", 1)
    call_str = call_str.strip()
    expected_str = expected_str.strip()
    m = re.match(r"^(\w+)\((.*)\)$", call_str)
    if not m:
        return ExampleResult(raw=ex_str, ok=False, error=f"malformed call: {call_str!r}")
    name, args_str = m.groups()
    if name != fn.name:
        return ExampleResult(raw=ex_str, ok=False, error=f"example calls {name!r}, expected {fn.name!r}")
    args = [parse_value(a.strip()) for a in split_top_level_commas(args_str)] if args_str.strip() else []
    expected = parse_value(expected_str)
    try:
        actual = run_body(fn, args)
    except RuntimeFail as rf:
        return ExampleResult(raw=ex_str, ok=False, expected=expected, error=f"runtime: {rf.message}")
    ok = values_equal(actual, expected)
    return ExampleResult(raw=ex_str, ok=ok, expected=expected, actual=actual)


def split_top_level(s: str, sep: str) -> list[str]:
    out: list[str] = []
    depth = 0
    buf = ""
    for c in s:
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if c == sep and depth == 0:
            out.append(buf)
            buf = ""
        else:
            buf += c
    if buf:
        out.append(buf)
    return out


# ---------- Diagnostics ----------

def emit_diagnostic(diag: dict[str, Any]) -> None:
    print("─" * 60)
    print(f"  ERROR  {diag['error']}")
    print(f"  in     {diag['function']}  ({diag['location']})")
    if "expected" in diag:
        print(f"  expected: {diag['expected']}")
    if "found" in diag:
        print(f"  found:    {diag['found']}")
    if "explanation" in diag:
        print(f"  why: {diag['explanation']}")
    if diag.get("suggestions"):
        print("  fixes:")
        for s in diag["suggestions"]:
            print(f"    {s['rank']}. {s['fix']}")
    print()
    print("  --- structured payload (for LLM consumption) ---")
    print(json.dumps(diag, indent=2))
    print("─" * 60)


def diagnose_example_failure(fn: Function, source: str, r: ExampleResult) -> dict[str, Any]:
    if r.error and "runtime:" in r.error:
        return {
            "error": "runtime-panic",
            "location": f"{source}:{fn.line}",
            "function": fn.name,
            "example": r.raw,
            "found": r.error,
            "expected": fmt_value(r.expected) if r.expected is not None else None,
            "suggestions": [
                {"rank": 1, "fix": "guard the failing operation (e.g. `if b == 0 { return None }`)"},
                {"rank": 2, "fix": "tighten an input refinement to forbid the bad input"},
                {"rank": 3, "fix": "change the return type to allow a failure variant"},
            ],
            "explanation": (
                f"While running {r.raw!r}, the body panicked: {r.error}. "
                f"The function did not anticipate this input."
            ),
        }
    return {
        "error": "example-mismatch",
        "location": f"{source}:{fn.line}",
        "function": fn.name,
        "example": r.raw,
        "expected": fmt_value(r.expected),
        "found": fmt_value(r.actual),
        "suggestions": [
            {"rank": 1, "fix": "fix the body so this input produces the expected output"},
            {"rank": 2, "fix": "if the example was wrong, update it to match intended behavior"},
            {"rank": 3, "fix": "split the function — the spec may be conflating two cases"},
        ],
        "explanation": (
            f"Example {r.raw!r} expected {fmt_value(r.expected)} but the body returned "
            f"{fmt_value(r.actual)}. Either the body is wrong or the example is wrong."
        ),
    }


# ---------- Display renderer (mira show) ----------
#
# Wire format → Laudan archive entry. Per display-spec.md:
#   LAUDAS  ▸  vol I  ▸  <name>  [—  answering <T>]
#   <vis> · <eff>
#   ─────────────
#   in    a : int
#         b : int
#   out   int?
#
#   ex    safe_div(10, 2)  →  Some(5)
#   ...
#   ens   result.is_some() iff b ≠ 0
#   ─────────────
#   do
#         <body>
#   ═════════════

# Box / glyph characters
_TOP = "═"
_MID = "─"
_BULLET = "▸"
_ARROW = "→"

# Width of the rendered entry (interior content width — excluding the 2-space inset).
_WIDTH = 56
_LABEL_COL = 8  # label column width (label + 4 spaces of separator)


def _subst_display_ops(s: str, in_body: bool) -> str:
    """Substitute display-format unicode for ASCII operators in slot values.
    Body content is preserved verbatim (so copy-paste yields valid wire)."""
    if in_body:
        return s
    out = s
    out = out.replace("!=", "≠")
    out = out.replace("<=", "≤")
    out = out.replace(">=", "≥")
    return out


def _render_label(label: str, value: str) -> str:
    pad = " " * (_LABEL_COL - len(label))
    return f"  {label}{pad}{value}"


def _render_continuation(value: str) -> str:
    return f"  {' ' * _LABEL_COL}{value}"


def _render_horizontal_rule(char: str = _MID) -> str:
    return "  " + char * _WIDTH


def render_function(fn: Function, volume: str = "I") -> list[str]:
    lines: list[str] = []

    # Top rule
    lines.append("  " + _TOP * _WIDTH)

    # Header
    name_str = fn.name
    if fn.for_iface:
        name_str = f"{fn.name}  —  answering {fn.for_iface}"
    lines.append(f"  LAUDAS  {_BULLET}  vol {volume}  {_BULLET}  {name_str}")

    # Sub-header: vis · eff
    sub_parts = []
    if fn.vis:
        sub_parts.append(fn.vis)
    if fn.eff:
        sub_parts.append(fn.eff)
    if sub_parts:
        lines.append(f"  {' · '.join(sub_parts)}")

    lines.append(_render_horizontal_rule())

    # Inputs
    if fn.ins:
        for i, p in enumerate(fn.ins):
            type_str = p.type.base
            if p.type.refinement:
                type_str = f"{p.type.base} {{ {_subst_display_ops(p.type.refinement, False)} }}"
            value = f"{p.name} : {type_str}"
            lines.append(_render_label("in", value) if i == 0 else _render_continuation(value))

    # Output
    if fn.out:
        out_str = fn.out.base
        if fn.out.refinement:
            out_str = f"{fn.out.base} {{ {_subst_display_ops(fn.out.refinement, False)} }}"
        lines.append(_render_label("out", out_str))

    # Examples
    if fn.exs:
        lines.append("")
        for i, ex in enumerate(fn.exs):
            # Substitute == in ex with → (between input and output)
            display_ex = ex
            if "==" in display_ex:
                # Only substitute the rightmost top-level == (skip inside parens)
                display_ex = _replace_top_level_eq(display_ex)
            display_ex = _subst_display_ops(display_ex, False)
            lines.append(_render_label("ex", display_ex) if i == 0 else _render_continuation(display_ex))

    # Requires
    if fn.reqs:
        lines.append("")
        for i, r in enumerate(fn.reqs):
            v = _subst_display_ops(r, False)
            lines.append(_render_label("req", v) if i == 0 else _render_continuation(v))

    # Ensures
    if fn.enses:
        lines.append("")
        for i, e in enumerate(fn.enses):
            v = _subst_display_ops(e, False)
            lines.append(_render_label("ens", v) if i == 0 else _render_continuation(v))

    # Prose
    if fn.prose:
        lines.append("")
        lines.append(_render_label("note", fn.prose))

    # Body
    lines.append(_render_horizontal_rule())
    lines.append("  do")
    for body_line in fn.body:
        if body_line.strip():
            lines.append(_render_continuation(body_line.strip()))

    # Bottom rule
    lines.append("  " + _TOP * _WIDTH)
    return lines


def render_type_alias(ta: TypeAlias, volume: str = "I") -> list[str]:
    lines: list[str] = []
    lines.append("  " + _TOP * _WIDTH)
    lines.append(f"  LAUDAS  {_BULLET}  vol {volume}  {_BULLET}  type {ta.name}")
    lines.append(_render_horizontal_rule())
    if ta.fields:
        for i, f in enumerate(ta.fields):
            type_str = f.type.base
            if f.type.refinement:
                type_str = f"{f.type.base} {{ {_subst_display_ops(f.type.refinement, False)} }}"
            value = f"{f.name} : {type_str}"
            lines.append(_render_label("field", value) if i == 0 else _render_continuation(value))
    else:
        lines.append(_render_label("field", "(empty record)"))
    lines.append("  " + _TOP * _WIDTH)
    return lines


def _replace_top_level_eq(s: str) -> str:
    """Replace the rightmost top-level `==` with `  →  `."""
    depth = 0
    last_idx = -1
    i = 0
    while i < len(s):
        c = s[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0 and s[i:i+2] == "==":
            last_idx = i
            i += 2
            continue
        i += 1
    if last_idx >= 0:
        return s[:last_idx].rstrip() + "  " + _ARROW + "  " + s[last_idx+2:].lstrip()
    return s


def show_file(path: str) -> int:
    try:
        fns, types = parse_file(path)
    except ParseError as e:
        print(f"parse error at line {e.line}: {e.msg}", file=sys.stderr)
        return 2
    items: list = list(types) + list(fns)
    for i, item in enumerate(items):
        if i > 0:
            print()
        if isinstance(item, TypeAlias):
            for line in render_type_alias(item):
                print(line)
        else:
            for line in render_function(item):
                print(line)
    return 0


# ---------- CLI ----------

def check_file(path: str) -> int:
    try:
        fns, types = parse_file(path)
    except ParseError as e:
        emit_diagnostic({
            "error": "parse-error",
            "location": f"{path}:{e.line}",
            "function": "(file)",
            "found": e.msg,
            "suggestions": [
                {"rank": 1, "fix": "check slot order: fn, vis, for?, eff, in*, out, ex*, req*, ens*, prose?, do, body, end"},
            ],
            "explanation": str(e.msg),
        })
        return 2

    # Try to import the verifier — optional dependency.
    try:
        import voronin
        have_voronin = True
    except ImportError:
        have_voronin = False

    type_count = len(types)
    fn_count = len(fns)
    parts = [f"{fn_count} fn" + ("" if fn_count == 1 else "s")]
    if type_count:
        parts.insert(0, f"{type_count} type" + ("" if type_count == 1 else "s"))
    print(f"  laudas v0.5  ·  parsed {' + '.join(parts)} from {path}")
    if have_voronin:
        print(f"  voronin verifier: enabled (z3)")
    else:
        print(f"  voronin verifier: not available — install z3-solver")
    print()

    # Register type aliases globally so eval_expr can recognize record literals.
    for ta in types:
        TYPE_ALIASES[ta.name] = ta

    failures = 0
    for fn in fns:
        print(f"  fn {fn.name}  [{fn.vis} · {fn.eff}]")

        # ---- examples ----
        ex_failures: list[ExampleResult] = []
        if fn.exs:
            for ex in fn.exs:
                result = run_example(fn, ex)
                if result.ok:
                    print(f"    ex   ✓  {ex}")
                else:
                    print(f"    ex   ✗  {ex}")
                    ex_failures.append(result)
                    failures += 1
        else:
            print("    (no examples)")

        # ---- voronin verification ----
        if have_voronin:
            v = voronin.verify_function(fn, path)
            if v.skipped:
                print(f"    ver  ·  skipped — {v.skip_reason}")
            elif v.ok:
                for c in v.checked:
                    print(f"    ver  ✓  {c}")
            else:
                print(f"    ver  ✗  {v.diagnostic['expected']}")
                failures += 1

        # ---- diagnostics ----
        for r in ex_failures:
            emit_diagnostic(diagnose_example_failure(fn, path, r))
        if have_voronin and not v.skipped and not v.ok:
            emit_diagnostic(v.diagnostic)

        print()

    if failures == 0:
        total_ex = sum(len(f.exs) for f in fns)
        print(f"  all checks passed  ·  {total_ex} example{'' if total_ex==1 else 's'} + verification")
        return 0
    print(f"  {failures} failure{'' if failures==1 else 's'}")
    return 1


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("usage: python laudas.py [--show] FILE.laud", file=sys.stderr)
        return 64
    if args[0] == "--show":
        if len(args) != 2:
            print("usage: python laudas.py --show FILE.laud", file=sys.stderr)
            return 64
        return show_file(args[1])
    if len(args) != 1:
        print("usage: python laudas.py [--show] FILE.laud", file=sys.stderr)
        return 64
    return check_file(args[0])


if __name__ == "__main__":
    sys.exit(main())
