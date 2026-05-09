# Laudas — architecture

How the Python prototype is laid out, and why.

This document is for contributors who want to change the implementation, or for anyone tracking the eventual Rust port (see [`rust/PORT_PLAN.md`](rust/PORT_PLAN.md)). For *what Laudas does* see [`PRD.md`](prd.md). For *how to use it* see the [tutorial](tutorial/) and [PLAYBOOK](PLAYBOOK.md).

---

## The big picture

```
                                     ┌───────────────┐
   ┌───────────────────────┐         │  Z3-solver    │
   │  laudas.py            │  IR     │  (z3-solver   │
   │                       │ ──────▶ │   PyPI pkg,   │
   │  parser, AST,         │         │   native lib) │
   │  interpreter,         │         └───────────────┘
   │  example runner,      │              ▲
   │  display renderer,    │              │
   │  io / text / arith /  │              │ Z3 expressions
   │  archive / ledger     │              │
   │  modules,             │         ┌───────────────┐
   │  Python FFI           │ ──────▶ │  voronin.py   │
   │                       │  AST    │               │
   └───────────────────────┘         │  Z3 sort       │
            │                        │  building,     │
            │ CLI                    │  symbolic exec,│
            ▼                        │  ens checking, │
   ┌───────────────────────┐         │  pretty cex    │
   │  pyproject.toml       │         └───────────────┘
   │  console_script:      │
   │    laudas → laudas:main │
   └───────────────────────┘
```

Two source files do the work: `laudas.py` (~1900 lines) and `voronin.py` (~600 lines). They sit in the project root for prototype simplicity. The Rust port (planned) will split things into proper crates per [`rust/PORT_PLAN.md`](rust/PORT_PLAN.md).

---

## `laudas.py` — the core

Reading order top-to-bottom roughly mirrors the data flow.

| Section | Lines | Purpose |
|---|---|---|
| AST dataclasses | ~50 | `Function`, `TypeAlias`, `Param`, `Type`, `ExternRef` |
| Parser | ~150 | Wire-format slot grammar; recursive `parse_file` for `use` |
| Value model | ~50 | Internal value tagging: `int`, `bool`, `str`, `list`, `dict` (records), `("Some", x)` / `("None",)`, `LaudasLambda` |
| Method dispatch | ~50 | `METHODS["list"]`, `METHODS["str"]`, `METHODS["int"]`, `METHODS["option"]` |
| Module dispatch | ~50 | `MODULES["text"]`, `MODULES["arith"]`, `MODULES["ledger"]`, `MODULES["archive"]`, `MODULES["io"]` |
| Body interpreter | ~250 | `interp_block`, `interp_stmt`, `interp_if`, `eval_expr`. Recursive descent with operator precedence; postfix method calls; lambdas |
| Foreign call | ~30 | `call_foreign` — imports the Python module and dispatches |
| Example runner | ~60 | `run_example` parses `ex` slots, calls body, compares |
| LLM-shaped errors | ~80 | Structured JSON + plain English |
| Display renderer | ~150 | `render_function`, `render_type_alias` — Laudan archive entries |
| Spec-first inversion | ~150 | `request_body_file` — call Anthropic API to fill empty `do` blocks |
| `run` subcommand | ~50 | `run_program` — execute `fn main` |
| CLI | ~30 | Subcommand dispatch (`check`, `--show`, `run`, `request-body`) |

### Why one big file (for now)

The Python prototype is the *reference* — the language design is moving, and refactoring across many files for every change is friction. When the language stabilizes (target: post-Volume I), the Rust port becomes the authoritative implementation, organized into proper modules. The Python file stays as the spec-by-implementation.

---

## `voronin.py` — the verifier

Built around **Z3** (Microsoft Research's SMT solver). Each Laudas function gets translated into Z3 constraints; Z3 either proves the postconditions or returns a counterexample.

| Section | Lines | Purpose |
|---|---|---|
| Z3 sort building | ~80 | `make_input_sym`, `_make_record_sort`. Builds a Z3 datatype for each `type` declaration; uses `z3.SeqSort` for `list<T>`; uses our custom `IntOpt` datatype for `int?` |
| `sym_eval` | ~200 | Translates a Laudas expression string into a Z3 expression. Handles literals, identifiers, binary ops with precedence, refinement comparisons, `result.is_some()` etc., field access, string/seq method chains, filter/map over-approximation, `iff`/`implies` |
| `sym_execute_body` | ~50 | Walks `let` bindings, then translates `if-return` early returns + final return into a chain of `z3.If` |
| `verify_function` | ~80 | Top-level entry: builds input symbols, adds refinement and `req` assumptions, runs body, checks each `ens` and the output refinement via `check_implication` |
| Counterexample formatting | ~70 | `_format_z3_value` — pretty-prints Z3 model values as Laudas syntax (e.g. `Box { width: 1, height: -1 }` instead of `Box!val!0`) |

### Why a separate file

`voronin` should be replaceable. Verification approaches change (e.g., a future port to a Rust-native verifier or a different SMT backend) without touching the parser/interpreter. The contract is small: take a `Function` + source path, return `VerifyResult { ok, diagnostic, skipped, skip_reason }`.

### How `__main__` vs. `laudas` module is handled

If you run `python laudas.py FILE.laud` (script mode), the running module is `__main__`. If you run `laudas FILE.laud` (console-script entry-point), it's `laudas`. Voronin needs to read `TYPE_ALIASES` from whichever one populated it. `_get_type_aliases` walks `sys.modules` checking both names. A subtle bug from early development; preserved as a worked example in [`CHANGELOG.md`](CHANGELOG.md) v0.5.7.

---

## Test sweep

[`tests/test_all.py`](tests/test_all.py) runs `python laudas.py FILE` over every `.laud` in:

- `demo_*.laud` at root
- `tutorial/*.laud`
- `examples/*.laud`
- `synthesis/corpus/seed/*.laud`

Plus a `MUST_VERIFY_FILES` list — files that must show at least one `ver ✓` line in output. Catches silent verifier-skip regressions.

CI matrix: 3 OSes × 2 Python versions = 6 jobs per push. See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## The wire/display split

Wire format is what `.laud` files contain on disk and what LLMs see. Slot-based, single-token keywords, no `@`-sigils. Token-optimized. **Source of truth.**

Display format is what `laudas --show` emits. Box-drawn Laudan archive entries. **Pure rendering**: round-trip through `mira show → mira parse` is lossless.

The two coexist; `display-spec.md` is the canonical spec.

---

## What lives where (file tour)

```
.
├── laudas.py               # the toolchain (parser, interp, runner, renderer, FFI, run, request-body)
├── voronin.py              # the verifier (Z3 layer)
├── pyproject.toml          # console_script: `laudas` → laudas:main
├── tests/test_all.py       # full sweep, used by CI
├── .github/
│   ├── workflows/ci.yml    # GH Actions matrix
│   └── ISSUE_TEMPLATE/     # bug, verifier-limit, feature, config
├── tutorial/               # 8 step-by-step .laud files + README
├── examples/               # real CLI tools (csv2json, wc, sort, ...)
├── synthesis/              # synthetic-corpus pipeline (Python → Laudas)
├── rust/                   # Cargo skeleton + PORT_PLAN.md (v1.0 target)
├── docs/index.html         # landing page (GitHub Pages)
└── *.md                    # PRD, README, PLAYBOOK, CHEATSHEET, CHANGELOG, etc.
```

---

## Adding a new feature — quick guide

| What you want to add | Where it goes |
|---|---|
| A new method on `list` / `str` / `int` / `option` | `METHODS[T]` table in `laudas.py` |
| A new module function (`text.X`, `arith.X`, etc.) | `MODULES[M]` table in `laudas.py` |
| A new keyword / slot | Parser in `laudas.py` (`parse_function`, `parse_type_alias`) + AST + interpreter |
| A new operator | `apply_op` + `find_binary_op` precedence table in `laudas.py` |
| A new verifiable type | `make_input_sym` + maybe `_format_z3_value` in `voronin.py` |
| A new verifier pattern | Add a branch to `sym_eval` in `voronin.py`; **always after binary ops** to avoid the precedence bug from v0.5.8 |
| A new CLI subcommand | `main()` in `laudas.py` + a runner function |
| A new example tool | `.laud` file in `examples/`; add to `tests/test_all.py` |
| A new tutorial step | `.laud` file in `tutorial/`; update `tutorial/README.md` |

Always: add a regression test to `tests/test_all.py`. If it's a verifier feature, add to `MUST_VERIFY_FILES`.
