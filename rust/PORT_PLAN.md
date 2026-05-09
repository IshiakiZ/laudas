# Laudas — Rust port plan

The Python prototype (`../laudas.py`, `../voronin.py`) is the reference. This crate is the v1.0 target: a single native binary, no Python dependency, ~10–100× faster for parsing + verification.

## Why port

The Python prototype is for fast iteration during language design (v0–v0.9). Once the language is stable, Python's runtime cost stops being acceptable: large `.laud` projects spend significant time in the parser and the interpreter loop, and distribution requires bundling Python (~18 MB binary today). A native Rust implementation:

- **Drops the binary to ~3–5 MB**, no Python dependency
- **10–100× faster** parsing and example execution
- **Better Z3 throughput** via native bindings (no Python ↔ C boundary cost)
- **Self-hosting path** — eventually `mira` and `voronin` written in Laudas, compiled by an earlier Rust laudas binary

## Staged port (each stage is shippable)

### Stage 1 — Parser
- Wire-format parser only (no semantics)
- Match the Python parser's grammar exactly (slot order, type aliases, use directives)
- Emit a JSON IR matching the Python AST shape
- `laudas-rs parse FILE.laud` → JSON IR
- Validation: parse every `.laud` file in `../examples/` and `../demo_*.laud`, diff against Python output

### Stage 2 — Example runner
- Body interpreter for the v0.5 subset (int, bool, str, list, record, lambda, method dispatch, module-qualified calls)
- Run `ex` slots, report mismatches in the LLM-shaped JSON format
- Validation: produce identical pass/fail counts on all existing demo files

### Stage 3 — Display renderer
- Port `mira show`
- Validation: byte-identical output to the Python renderer for all demos

### Stage 4 — Voronin
- Z3 Rust bindings (the `z3` crate)
- Symbolic execution for the v0.5.2 subset (let, if-return, final-return)
- Validation: same `ver ✓` / `ver ✗` results, same counterexamples

### Stage 5 — Spec-first inversion (`request-body`)
- Anthropic API client (anyhow + reqwest, or the `anthropic` crate when available)
- Same prompt template, same body extraction
- Validation: same generated output for the same prompt + seed

### Stage 6 — Self-hosting
- Once Stages 1–5 ship, the next compiler can be written in Laudas
- Rust crate becomes the bootstrap; subsequent compilers are .laud → bytecode → native via LLVM
- This is the v2.0 target and not in scope for Volume I

## Target dependencies

Bare minimum:
- `z3` — Z3 SMT solver bindings
- `anyhow` — error handling
- `clap` — CLI parsing
- `serde` + `serde_json` — IR serialization, error JSON output

Anthropic API client: either the official Rust SDK when published, or `reqwest` + handwritten request/response types.

## Layout (when port begins)

```
rust/
├── Cargo.toml
├── src/
│   ├── main.rs         CLI entrypoint
│   ├── lib.rs          public API
│   ├── parser/         wire-format parser
│   │   ├── lex.rs
│   │   ├── grammar.rs
│   │   └── ast.rs
│   ├── runtime/        example runner / interpreter
│   │   ├── value.rs
│   │   ├── eval.rs
│   │   ├── methods.rs
│   │   └── modules.rs
│   ├── verifier/       voronin
│   │   ├── encode.rs
│   │   ├── execute.rs
│   │   └── diagnose.rs
│   ├── render/         mira show
│   │   └── archive.rs
│   └── inversion/      request-body
│       └── prompt.rs
└── tests/
    └── parity.rs       diff against Python prototype output
```

## Non-goals for the Rust port

- Adding new language features. The Python prototype is the spec.
- Performance optimization beyond what falls out of native code. We're not chasing benchmarks here, we're getting native distribution.
- API compatibility with the Python implementation as a library. The CLI is the contract.

## Done criteria for stage cutover

The Rust port replaces the Python implementation as the default `laudas` binary when:

1. All five stages ship
2. All `demo_*.laud` files produce byte-identical output (modulo timestamps)
3. The Rust binary is ≤8 MB stripped
4. The Rust binary is ≥10× faster than the Python prototype on a 1000-line `.laud` benchmark
5. `pip install -e .` continues to work (Python implementation kept as the reference / fallback)
