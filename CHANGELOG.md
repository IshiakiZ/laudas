# Changelog

All notable changes to Laudas. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [v0.5.3] — 2026-05-09 — voronin learns records

### Added — verifier

- **Z3 record types** — voronin now dynamically builds a Z3 datatype for each `type` declaration in the file. Inputs of record type are full Z3 symbolic values, not skipped.
- **Field-access in pre/postconditions** — `req b.width >= 0`, `ens result == p.x + q.x`, etc. The expression parser resolves `obj.field` to the datatype's accessor.
- **`str` inputs** — voronin now accepts `str` as an input type (Z3's String sort).

Functions like `area(b: Box) → int { ens result >= 0 }` (with `req b.width >= 0` and `req b.height >= 0`) now get `ver ✓` instead of `ver · skipped`.

### Demo

[`demo_record_verify.laud`](demo_record_verify.laud) — `area` and `perimeter` both verify `ens result >= 0` for every valid `Box` input.

---

## [v0.5.2] — 2026-05-09 — Volume I scaffolding

### Added — language

- **`use "PATH"`** — multi-file modules. `use` at the top of a `.laud` file recursively loads another file's top-level declarations into the current namespace. Cycle-safe.
- **Bare function calls** — call user-defined Laudas functions across files: `manhattan(a, b)` resolves via the global `FUNCTIONS` registry.
- **`let` bindings inside voronin** — the verifier now symbolically executes `let NAME = EXPR` statements before the if-return chain. Functions like `percentage_v2` (which use `let scaled = part * 100`) now get full Z3 verification (`ver ✓ ens result <= 100`) instead of skipping.
- **`request-body` subcommand** — `laudas request-body FILE.laud` finds functions with empty `do` blocks, asks Claude (via `ANTHROPIC_API_KEY`) to generate a body satisfying the spec, writes the result to `FILE.filled.laud`. Verify with `laudas FILE.filled.laud`. Spec-first inversion.

### Added — Volume I scaffolding

- **`rust/`** — Cargo project skeleton + [PORT_PLAN.md](rust/PORT_PLAN.md) outlining the staged Python → Rust port for v1.0.
- **`synthesis/`** — synthetic-corpus pipeline:
  - [`generate.py`](synthesis/generate.py) — Python → Laudas translator (calls Claude, runs `voronin`, keeps verified outputs)
  - [`corpus/seed/`](synthesis/corpus/seed/) — first 5 hand-written corpus examples
  - [`prompts/translate.md`](synthesis/prompts/translate.md) — versioned prompt template
  - [`README.md`](synthesis/README.md) — workflow, fine-tuning plan, status checklist

### Demo

[`demo_let_verify.laud`](demo_let_verify.laud), [`demo_use_main.laud`](demo_use_main.laud) + [`demo_use_lib.laud`](demo_use_lib.laud), [`demo_specfirst.laud`](demo_specfirst.laud).

---

## [v0.5.1] — 2026-05-09 — module-qualified stdlib

### Added

- **Module-qualified standard library calls** — `text.split(s, ",")`, `arith.min(a, b)`, `ledger.range(n)`, `text.to_json(v)`, `archive.read(path)`, etc. The MODULES table is open for extension; see `laudas.py`.
- **More list methods** — `.at(i)`, `.tail()`, `.take(n)`, `.skip(n)`, `.unique()`, `.sort()`, `.sort_by(fn)`, `.dedupe_by(fn)`, `.reverse()`.
- **More string methods** — `.contains(sub)`, `.starts_with(p)`, `.ends_with(p)`, `.trim()`, `.split(sep)`.
- **Escape-sequence decoding** in string literals — `\"`, `\n`, `\t`, `\r`, `\\`, `\0`.
- **String-aware comma splitter** — commas inside `"..."` no longer split arg lists.

### Demo

[`demo_stdlib.laud`](demo_stdlib.laud) — 7 functions, 14 passing examples, including a CSV-row → record → dedupe → sort → JSON pipeline that exercises records + lambdas + every new module function.

---

## [v0.5] — 2026-05-09 — first public draft

The first version that's plausibly worth showing other people. The language has a verifier, a renderer, lists, lambdas, records, Python interop, and a standalone binary. Volume I (v1.0) is still 6–12 months out, but the shape is real.

### Added

- **Wire format parser** for the slot-based grammar (`fn`, `vis`, `for`, `eff`, `in`, `out`, `ex`, `req`, `ens`, `prose`, `do`, `end`, `extern`).
- **Example runner** — executes `ex` slots and reports mismatches.
- **Z3 verification** (voronin) — symbolically executes function bodies with `(if EXPR { return EXPR })* return EXPR` shape, encodes input refinements + `req` + `ens` as constraints, finds counterexamples on failure.
- **LLM-shaped error format** — every diagnostic emits structured JSON with ranked suggested fixes, plus a plain-English explanation.
- **Display renderer** (`laudas --show`) — wire format → Laudan archive entries (box-drawn, archival framing). Round-trip lossless.
- **List literals + arrow lambdas + method chaining** — `xs.filter(x -> x > 0).map(x -> x * x).sum()`.
- **Type aliases / records** — `type Point { x: int, y: int }`, `Point { x: 3, y: 4 }`, field access via `p.x`.
- **`let` bindings** in function bodies.
- **Python FFI** — `extern python "module.func"` slot gives Laudas day-one access to all of PyPI.
- **`type` declarations render** as their own Laudan archive entries in display mode.
- **Standalone binary** — `dist/laudas.exe` (~18 MB), no Python install required.
- **`pip install -e .`** installs `laudas` as a console script.

### Verifier limits (intentional in v0.5)

- Inputs other than `int` / `int { refinement }` skip with a reason.
- Outputs other than `int` / `int?` / refined int skip.
- Body shapes other than the early-return + final-return pattern skip.
- Records, lists, strings, lambdas, extern functions all skip cleanly with informative reasons.

### Known gaps (planned for v0.5+ / Volume I)

- No multi-file modules / `use` statements.
- No spec-first inversion (empty `do` blocks calling an LLM to generate the body).
- No standard library beyond builtins (`text.parse_csv`, `archive.read/write`, etc.).
- Compiler is Python-hosted; native Rust rewrite is the v1.0 plan.
- No synthetic training corpus or fine-tuned model yet.

---

## [v0.1] — 2026-05-08 — verifier ships

### Added

- **voronin.py** — Z3-backed verifier module, ~350 lines.
- Counterexample-finding — Z3 catches bugs that examples don't (e.g., `safe_div(-1, 0) = Some(0)` violates `result.is_some() iff b != 0`).
- Wire-format parser, example runner, LLM diagnostic format.

---

## [v0.0] — 2026-05-08 — first runnable parser

### Added

- **laudas.py** — single-file parser + interpreter + diagnostic emitter.
- Wire-format slot grammar.
- Demo files (`demo_buggy.laud`, `demo_fixed.laud`) showing the repair-loop end-to-end.
