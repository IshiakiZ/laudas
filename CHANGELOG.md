# Changelog

All notable changes to Laudas. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
