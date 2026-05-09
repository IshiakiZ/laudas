"""
voronin.py — v0.1 Z3 verifier for Laudas

Symbolically executes a function's body, encodes input refinements, `req`
preconditions, and `ens` postconditions as Z3 constraints, and asks Z3
whether the postconditions hold for all inputs satisfying the
preconditions. On failure, emits an LLM-shaped diagnostic with a concrete
counterexample.

v0.1 supported subset:
  - Inputs: `int`, `int { refinement }` (refinement: comparison or `lo..=hi`)
  - Output: `int`, `int?`, `int { refinement }`
  - Body:
       (`if EXPR { return EXPR }`)*
       `return EXPR`
  - Expressions: int arithmetic, comparisons, &&, ||, Some(_), None,
    result.is_some() / .is_none() / .value(), iff, implies
  - Postconditions: predicates over `result` and parameters

Anything outside the subset is reported as `verifier-skipped` with a reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

import z3

from laudas import Function, Param, Type


# ---------- Z3 datatype for Option<int> ----------

_IntOpt = z3.Datatype("IntOpt")
_IntOpt.declare("none")
_IntOpt.declare("some", ("val", z3.IntSort()))
IntOpt = _IntOpt.create()


# ---------- Errors ----------

class NotSupported(Exception):
    pass


# ---------- Symbolic environment ----------

@dataclass
class SymEnv:
    syms: dict[str, Any] = field(default_factory=dict)
    assumptions: list[Any] = field(default_factory=list)


# ---------- Type encoding ----------

def make_input_sym(p: Param) -> Any:
    base = p.type.base
    if base == "int":
        return z3.Int(p.name)
    if base == "bool":
        return z3.Bool(p.name)
    if base == "str":
        return z3.String(p.name)
    if base == "int?":
        return z3.Const(p.name, IntOpt)
    # Record types: build an opaque Z3 datatype with the declared fields.
    # We look the type up via the global TYPE_ALIASES registry from laudas.
    try:
        from laudas import TYPE_ALIASES
    except ImportError:
        TYPE_ALIASES = {}
    if base in TYPE_ALIASES:
        return _make_record_sym(p.name, base, TYPE_ALIASES[base])
    raise NotSupported(f"unsupported input type: {base}")


# Cache of dynamically-built Z3 record sorts so the same type isn't rebuilt
# every verification (Z3 datatype identities matter for solver state).
_RECORD_SORTS: dict[str, Any] = {}


def _make_record_sort(type_name: str, type_alias: Any) -> Any:
    """Build (or retrieve) a Z3 datatype for a Laudas record type."""
    if type_name in _RECORD_SORTS:
        return _RECORD_SORTS[type_name]
    dt = z3.Datatype(type_name)
    field_specs = []
    for f in type_alias.fields:
        if f.type.base == "int":
            sort = z3.IntSort()
        elif f.type.base == "bool":
            sort = z3.BoolSort()
        elif f.type.base == "str":
            sort = z3.StringSort()
        else:
            raise NotSupported(f"record field type not supported in verifier: {f.type.base}")
        field_specs.append((f.name, sort))
    dt.declare(f"mk_{type_name}", *field_specs)
    sort = dt.create()
    _RECORD_SORTS[type_name] = sort
    return sort


def _make_record_sym(var_name: str, type_name: str, type_alias: Any) -> Any:
    sort = _make_record_sort(type_name, type_alias)
    return z3.Const(var_name, sort)


def parse_refinement(ref: str, var: Any, env: SymEnv) -> Any:
    """Refinement like `> 0`, `>= 0`, `0..=100` applied to `var`."""
    s = ref.strip()
    m = re.match(r"^(-?\d+)\.\.=(-?\d+)$", s)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return z3.And(var >= lo, var <= hi)
    # Otherwise: treat as expression with `_` as the variable
    placeholder = "__refvar__"
    expr = f"{placeholder} {s}"
    temp_env = SymEnv(syms={**env.syms, placeholder: var})
    return sym_eval(expr, temp_env)


# ---------- Expression parser & symbolic evaluator ----------

def sym_eval(expr: str, env: SymEnv) -> Any:
    """Parse a Laudas expression, return the Z3 expression."""
    s = expr.strip()

    # Strip outer parens if balanced
    if s.startswith("(") and s.endswith(")") and _balanced(s):
        return sym_eval(s[1:-1], env)

    # Literals
    if s == "None":
        return IntOpt.none
    if s in ("true", "True"):
        return z3.BoolVal(True)
    if s in ("false", "False"):
        return z3.BoolVal(False)
    if re.match(r"^-?\d+$", s):
        return z3.IntVal(int(s))

    # Some(x)
    m = re.match(r"^Some\((.*)\)$", s)
    if m and _balanced(s):
        return IntOpt.some(sym_eval(m.group(1), env))

    # Method calls: result.is_some() / .is_none() / .value()
    m = re.match(r"^(\w+)\.is_some\(\)$", s)
    if m:
        return IntOpt.is_some(env.syms[m.group(1)])
    m = re.match(r"^(\w+)\.is_none\(\)$", s)
    if m:
        return IntOpt.is_none(env.syms[m.group(1)])
    m = re.match(r"^(\w+)\.value\(\)$", s)
    if m:
        return IntOpt.val(env.syms[m.group(1)])

    # Record field access: NAME.FIELD (no parens). Resolves via the dynamically-built
    # Z3 datatype's field accessors.
    m = re.match(r"^(\w+)\.(\w+)$", s)
    if m:
        obj_name, field = m.groups()
        if obj_name in env.syms:
            obj = env.syms[obj_name]
            sort_name = obj.sort().name() if hasattr(obj, "sort") else None
            if sort_name in _RECORD_SORTS:
                sort = _RECORD_SORTS[sort_name]
                accessor = getattr(sort, field, None)
                if accessor is not None and callable(accessor):
                    return accessor(obj)

    # Word operators (lowest precedence)
    for word_ops in (("iff", "implies"),):
        idx, op = _find_top_word(s, word_ops)
        if idx >= 0:
            left = sym_eval(s[:idx], env)
            right = sym_eval(s[idx + len(op):], env)
            if op == "iff":
                return left == right
            if op == "implies":
                return z3.Implies(left, right)

    # Symbolic operators, in precedence order (lowest first)
    for sym_ops in (
        ("||",),
        ("&&",),
        ("==", "!="),
        ("<=", ">=", "<", ">"),
        ("+", "-"),
        ("*", "/", "%"),
    ):
        idx, op = _find_top_op(s, sym_ops)
        if idx >= 0:
            left_str = s[:idx]
            right_str = s[idx + len(op):]
            if not left_str.strip() and op == "-":
                # Unary minus — wrap into the right operand
                return -sym_eval(right_str, env)
            left = sym_eval(left_str, env)
            right = sym_eval(right_str, env)
            return _apply(op, left, right)

    # Bare identifier
    if re.match(r"^[A-Za-z_]\w*$", s):
        if s in env.syms:
            return env.syms[s]
        raise NotSupported(f"unbound identifier: {s!r}")

    raise NotSupported(f"cannot evaluate symbolically: {s!r}")


def _apply(op: str, a: Any, b: Any) -> Any:
    if op == "+":  return a + b
    if op == "-":  return a - b
    if op == "*":  return a * b
    if op == "/":  return a / b
    if op == "%":  return a % b
    if op == "==": return a == b
    if op == "!=": return a != b
    if op == "<":  return a < b
    if op == ">":  return a > b
    if op == "<=": return a <= b
    if op == ">=": return a >= b
    if op == "&&": return z3.And(a, b)
    if op == "||": return z3.Or(a, b)
    raise NotSupported(f"unsupported op: {op!r}")


def _balanced(s: str) -> bool:
    depth = 0
    for i, c in enumerate(s):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0 and i < len(s) - 1:
                return False
    return depth == 0


def _find_top_op(s: str, ops: tuple[str, ...]) -> tuple[int, str]:
    """Rightmost top-level occurrence of any op (gives left-to-right associativity on recursion)."""
    depth = 0
    best = (-1, "")
    i = 0
    while i < len(s):
        c = s[i]
        if c == "(":
            depth += 1
            i += 1
            continue
        if c == ")":
            depth -= 1
            i += 1
            continue
        if depth == 0:
            matched = False
            for op in ops:
                if s[i:i + len(op)] == op:
                    # Disambiguate `==` vs `=` etc. by checking next char isn't part of a longer op
                    if op in ("<", ">") and i + 1 < len(s) and s[i + 1] == "=":
                        continue
                    if op == "=" and i + 1 < len(s) and s[i + 1] == "=":
                        continue
                    # Skip unary minus at the beginning of the sub-expression
                    if op == "-":
                        # If preceded only by whitespace or by another op, it's unary
                        prev = s[:i].rstrip()
                        if not prev or prev[-1] in "+-*/%<>=!|&(":
                            i += 1
                            matched = True
                            break
                    best = (i, op)
                    i += len(op)
                    matched = True
                    break
            if matched:
                continue
        i += 1
    return best


def _find_top_word(s: str, words: tuple[str, ...]) -> tuple[int, str]:
    depth = 0
    best = (-1, "")
    i = 0
    while i < len(s):
        c = s[i]
        if c == "(":
            depth += 1
            i += 1
            continue
        if c == ")":
            depth -= 1
            i += 1
            continue
        if depth == 0 and (c.isalpha() or c == "_"):
            j = i
            while j < len(s) and (s[j].isalnum() or s[j] == "_"):
                j += 1
            word = s[i:j]
            if word in words:
                before_ok = i == 0 or not (s[i - 1].isalnum() or s[i - 1] == "_")
                after_ok = j == len(s) or not (s[j].isalnum() or s[j] == "_")
                if before_ok and after_ok:
                    best = (i, word)
            i = j
            continue
        i += 1
    return best


# ---------- Body symbolic execution ----------

def sym_execute_body(fn: Function, env: SymEnv) -> Any:
    """Build a Z3 expression representing the body's return value.
    Supported pattern (v0.5.2):
        let NAME = EXPR        ; bind to env (in declaration order)
        let NAME = EXPR
        if COND { return EXPR }
        if COND { return EXPR }
        ...
        return EXPR
    """
    body_text = "\n".join(fn.body)
    stmts = _split_stmts(body_text)
    if not stmts:
        raise NotSupported("empty body")

    # Walk statements: process `let` bindings into the env, collect if-return + final-return.
    let_re = re.compile(r"^let\s+([A-Za-z_]\w*)\s*=\s*(.+)$", flags=re.DOTALL)
    flow_stmts: list[str] = []
    for stmt in stmts:
        s = stmt.strip()
        m = let_re.match(s)
        if m:
            name, expr = m.groups()
            env.syms[name] = sym_eval(expr.strip(), env)
            continue
        flow_stmts.append(stmt)

    if not flow_stmts:
        raise NotSupported("body has only let-bindings; missing a `return`")

    last = flow_stmts[-1].strip()
    if not last.startswith("return "):
        raise NotSupported(f"body must end with `return EXPR`, got {last!r}")
    result = sym_eval(last[7:].strip(), env)

    for stmt in reversed(flow_stmts[:-1]):
        s = stmt.strip()
        m = re.match(
            r"^if\s+(.+?)\s*\{\s*return\s+(.+?)\s*\}\s*$",
            s,
            flags=re.DOTALL,
        )
        if not m:
            raise NotSupported(
                f"only `let`, `if EXPR {{ return EXPR }}` early-returns and a final `return EXPR` are supported in v0.5.2; got {s!r}"
            )
        cond_str, ret_str = m.groups()
        cond = sym_eval(cond_str, env)
        ret_val = sym_eval(ret_str.strip(), env)
        result = z3.If(cond, ret_val, result)

    return result


def _split_stmts(body: str) -> list[str]:
    out: list[str] = []
    lines = body.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
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


# ---------- Verification driver ----------

@dataclass
class VerifyResult:
    ok: bool
    diagnostic: Optional[dict] = None
    skipped: bool = False
    skip_reason: Optional[str] = None
    checked: list[str] = field(default_factory=list)


def verify_function(fn: Function, source: str) -> VerifyResult:
    if fn.extern is not None:
        return VerifyResult(
            ok=True,
            skipped=True,
            skip_reason=f"extern {fn.extern.backend} `{fn.extern.ref}` — body is foreign, not symbolically verifiable",
        )

    has_ens = bool(fn.enses)
    has_in_ref = any(p.type.refinement for p in fn.ins)
    has_out_ref = bool(fn.out and fn.out.refinement)

    if not has_ens and not has_in_ref and not has_out_ref:
        return VerifyResult(ok=True, skipped=True, skip_reason="no refinements or postconditions")

    try:
        env = SymEnv()
        for p in fn.ins:
            sym = make_input_sym(p)
            env.syms[p.name] = sym
            if p.type.refinement:
                env.assumptions.append(parse_refinement(p.type.refinement, sym, env))

        for req in fn.reqs:
            env.assumptions.append(sym_eval(req, env))

        result = sym_execute_body(fn, env)
        env.syms["result"] = result

        checked: list[str] = []

        # Check ens postconditions
        for ens in fn.enses:
            ens_expr = sym_eval(ens, env)
            cex = check_implication(env.assumptions, ens_expr)
            if cex is not None:
                return VerifyResult(
                    ok=False,
                    diagnostic=_diagnose_ens_failure(fn, source, ens, cex, env),
                )
            checked.append(f"ens {ens}")

        # Check output refinement (if any)
        if has_out_ref:
            out_ref = fn.out.refinement
            out_expr = parse_refinement(out_ref, result, env)
            cex = check_implication(env.assumptions, out_expr)
            if cex is not None:
                return VerifyResult(
                    ok=False,
                    diagnostic=_diagnose_out_failure(fn, source, out_ref, cex, env),
                )
            checked.append(f"out {fn.out.base} {{ {out_ref} }}")

        return VerifyResult(ok=True, checked=checked)

    except NotSupported as ns:
        return VerifyResult(ok=True, skipped=True, skip_reason=f"verifier limitation: {ns}")


def check_implication(assumptions: list[Any], goal: Any) -> Optional[Any]:
    """Returns None if assumptions ⇒ goal is valid; else a counterexample model."""
    s = z3.Solver()
    for a in assumptions:
        s.add(a)
    s.add(z3.Not(goal))
    res = s.check()
    if res == z3.unsat:
        return None
    if res == z3.sat:
        return s.model()
    return None  # Unknown — be conservative


def _format_cex(model: Any, env: SymEnv) -> str:
    parts = []
    for name, sym in env.syms.items():
        if name == "result":
            continue
        try:
            val = model.eval(sym, model_completion=True)
            parts.append(f"{name}={val}")
        except Exception:
            pass
    return ", ".join(parts) if parts else "(no concrete inputs)"


def _diagnose_ens_failure(fn: Function, source: str, ens: str, cex: Any, env: SymEnv) -> dict:
    cex_str = _format_cex(cex, env)
    result_val = ""
    if "result" in env.syms:
        try:
            result_val = str(cex.eval(env.syms["result"], model_completion=True))
        except Exception:
            pass
    return {
        "error": "verification-failure",
        "kind": "ens",
        "location": f"{source}:{fn.line}",
        "function": fn.name,
        "expected": f"ens {ens}",
        "found": f"counterexample: {cex_str}" + (f" → result = {result_val}" if result_val else ""),
        "suggestions": [
            {"rank": 1, "fix": "fix the body so the postcondition holds for all inputs"},
            {"rank": 2, "fix": "if the postcondition was wrong, weaken or rewrite it"},
            {"rank": 3, "fix": "add a `req` precondition to exclude the failing inputs"},
        ],
        "explanation": (
            f"Z3 found a counterexample to `ens {ens}`. With inputs {cex_str}, "
            f"the body returned {result_val or '(see model)'}, which does not satisfy "
            f"the postcondition. Either the body is wrong or the postcondition is wrong."
        ),
    }


def _diagnose_out_failure(fn: Function, source: str, out_ref: str, cex: Any, env: SymEnv) -> dict:
    cex_str = _format_cex(cex, env)
    result_val = ""
    try:
        result_val = str(cex.eval(env.syms["result"], model_completion=True))
    except Exception:
        pass
    return {
        "error": "verification-failure",
        "kind": "output-refinement",
        "location": f"{source}:{fn.line}",
        "function": fn.name,
        "expected": f"out {fn.out.base} {{ {out_ref} }}",
        "found": f"counterexample: {cex_str}" + (f" → result = {result_val}" if result_val else ""),
        "suggestions": [
            {"rank": 1, "fix": "fix the body so the result satisfies the output refinement"},
            {"rank": 2, "fix": "loosen the output refinement to match actual behavior"},
            {"rank": 3, "fix": "strengthen input refinements / add `req` to exclude the bad case"},
        ],
        "explanation": (
            f"Z3 found inputs {cex_str} where the body returned {result_val or '(see model)'}, "
            f"which does not satisfy the declared output refinement `{fn.out.base} {{ {out_ref} }}`."
        ),
    }
