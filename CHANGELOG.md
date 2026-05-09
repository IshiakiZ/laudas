# Changelog

All notable changes to Laudas. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [v0.5.8] — 2026-05-09 — six Unix tools, string-method verification, JSON pretty

### Added — language

- **String-method verification.** Voronin now handles `s.length()`, `s.upper()`, `s.lower()`, and chains thereof in pre/postconditions. `z3.Length()` backs `.length()`; `.upper()`/`.lower()` are modeled as opaque string-to-string Z3 functions, which is enough to prove `result >= 0` for `s.upper().length()` (length is preserved through the function).
- **`text.to_json_pretty(v)`** — same as `to_json` but with 2-space indent.
- **`text.to_int(s)`**, **`text.from_int(n)`** — string ↔ int conversions.
- **`io.read_stdin()`** — read all of stdin as a string. (Already in v0.5.5; mentioned here because the v0.5.7 binary missed it.)

### Added — examples

Three new Unix-style tools join `csv2json`, `wc`, and `sort`:

- **[`examples/head.laud`](examples/head.laud)** — first N lines from stdin, default 10.
- **[`examples/tail.laud`](examples/tail.laud)** — last N lines from stdin.
- **[`examples/uniq.laud`](examples/uniq.laud)** — drop duplicate lines (preserves first occurrence).
- **[`examples/json_pretty.laud`](examples/json_pretty.laud)** — pretty-print JSON via Python FFI + `text.to_json_pretty`.

Six real CLI tools total. They compose: `Get-Content file | laudas run sort.laud | laudas run uniq.laud`.

### Fixed

- **Stdin UTF-8.** `sys.stdin.reconfigure(encoding="utf-8")` so PowerShell-piped UTF-8 BOM bytes decode as `﻿` (one char) instead of three cp1252 chars. Was breaking `json.loads` on otherwise-valid input.
- **Dict round-trip.** `_python_to_laudas` now handles `dict` (was falling through to opaque). JSON objects from `json.loads` come back as proper Laudas records.
- **Binary-op precedence vs. string methods.** The `.length()` suffix-strip in voronin's `sym_eval` is now placed AFTER binary ops, so `result == s.length()` parses as the equality, not as `(result == s).length()`.

---

## [v0.5.7] — 2026-05-09 — fix silent verifier skip, harden tests

### Fixed

- **voronin missed records when laudas ran as a script**. When invoked as `python laudas.py FILE.laud`, the running module is `__main__` while voronin's `from laudas import TYPE_ALIASES` fetched a separately-loaded second copy with stale empty state. Result: record types reported `verifier limitation: unsupported input type: Box` instead of verifying. The console-script entry-point (`laudas FILE.laud`) hid the bug because in that case `laudas` and `__main__` are the same module. Fixed: `voronin._get_type_aliases()` now scans `sys.modules` for both names.

### Added — tests

- **`MUST_VERIFY_FILES` in the sweep** — a list of files that must show at least one `ver ✓` line in the output. Catches silent verifier-skip regressions like the one above. The previous sweep only validated exit codes.

---

## [v0.5.6] — 2026-05-09 — first real CLI tool

### Added — language

- **`io.read_stdin()`** — reads all of stdin as a string. Pairs with `io.println` and the existing list / text / record machinery to make Unix-pipe-style tools possible.

### Added — examples

- **[`examples/csv2json.laud`](examples/csv2json.laud)** — first non-toy CLI tool written in Laudas. Reads CSV text from stdin, drops the header, parses each row into a `Crew` record, emits JSON. ~20 lines. Real working tool, not a demo. Pipe a file in:

  ```
  Get-Content examples/crew.csv | laudas run examples/csv2json.laud
  ```

  Outputs:
  ```json
  [{"name":"Mira","role":"engineer","ship":"Voronin"},{"name":"Dara","role":"captain","ship":"Osei"},{"name":"Cass","role":"navigator","ship":"Telles"}]
  ```

  The `parse_row` function has its own `ex` slots, so verification still runs against it normally with `laudas examples/csv2json.laud` (no piping).

---

## [v0.5.5] — 2026-05-09 — Laudas programs are runnable

Laudas programs are now actually executable from the command line — not just spec-checked. A `fn main` is the entry point; `laudas run FILE.laud [ARGS...]` calls it.

### Added — language

- **`io` module** — `io.println(s)`, `io.print(s)`, `io.eprintln(s)`, `io.read_line()`. The first three return `None` (called for the side effect); read_line returns the trimmed line.
- **Expression-statement support** — body lines can be bare expressions called for their side effects. `io.println("hi")` on its own line works; the result is discarded.

### Added — toolchain

- **`laudas run FILE.laud [ARGS...]`** — execute the file's `main` function. `main` may take zero args, or one `args: list<str>` parameter that receives the CLI arguments. The int return value becomes the process exit code.
- Help text in `laudas --help` updated.

### Demos

- [`demo_hello.laud`](demo_hello.laud) — minimal hello world.
- [`demo_greet.laud`](demo_greet.laud) — personalized greeter that takes names from the command line, validates argc, exits 64 with usage on misuse.

---

## [v0.5.4] — 2026-05-09 — multi-arg lambdas + community plumbing

### Added — language

- **Multi-arg lambdas** — `(a, b) -> a + b`, `(acc, x) -> acc + x`. The single-arg `x -> EXPR` form continues to work.
- **`.fold(init, fn)`** — works now that two-arg callbacks parse cleanly. `xs.fold(0, (acc, x) -> acc + x)`.

### Added — community

- **GitHub Actions CI** (`.github/workflows/ci.yml`) — runs the full test sweep on Linux + macOS + Windows × Python 3.10 + 3.12 on every push/PR.
- **`tests/test_all.py`** — runs `laudas` over every demo / tutorial / corpus seed, asserts expected pass/fail behavior. 19 files covered.
- **Issue templates** — `bug_report.yml`, `verifier_limit.yml`, `feature_request.yml`, plus a `config.yml` that points first-time issuers at the tutorial / PRD / compression analysis.
- **CI badge + license badge** in the README.

### Demo

[`demo_fold.laud`](demo_fold.laud) — sum, product, and string concatenation all via `.fold()` with `(acc, x) -> ...` lambdas.

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
