# Laudas — Product Requirements Document

**Status:** Draft v0.2 (locked design)
**Last updated:** 2026-05-08
**Project location:** `C:\Users\pearc\Documents\AiCodingLng`
**Companion docs:** [research-survey.md](research-survey.md) · [examples.laud](examples.laud) · [display-spec.md](display-spec.md) · [token_results.txt](token_results.txt)

---

## 1. Executive summary

**Laudas** is a verification-first programming language designed for AI agents to generate and human-AI pairs to maintain. Its on-disk source — the **wire format** — is engineered for LLM token efficiency: every keyword is a single tokenizer token, slot-based grammar removes clause-ordering ambiguity, and indentation rules avoid the BPE merge-break that doubles per-line cost. An opt-in **display format** renders the same code as Laudan archival entries, drawing visual identity from *The Disappearing* and *The Answering* — the user's sci-fi novels. The compiler holds a structured conversation with the model: every diagnostic is a teacher's note, not a judge's ruling. The verifier (Z3-backed) does the proofs; the model only writes specs the solver can chew on.

Open-source from day one (Apache 2.0). Major releases are **Volumes** (Volume I = v1.0).

**Tagline:** *"Code that survives the crossing."*

---

## 2. Problem statement

Within a few years, most new code will be authored by AI. Today's languages were optimized for *humans* writing code. They were not optimized for the dominant feedback loop of the next decade: **AI generates, system verifies, AI iterates**.

Python wins for AI generation today because of training-data abundance, not because Python is well-designed for AI generation. The cold-start problem makes any new language worse than Python in the short term — but the structural advantages of a verification-first, token-efficient, LLM-error-shaped language compound with iteration speed, and the gap closes once synthetic data is generated.

The strongest empirical signal in the prior-art survey is Dafny's trajectory: LLM success rate went from **68% to 96% in a single year** because the SMT solver gives the model cheap, mechanical feedback. Laudas bets on that lever, with friendlier syntax and an LLM-targeted error format.

Recent empirical work (arXiv 2508.13666, "Hidden Cost of Readability") shows LLMs tolerate reformatted/minified code with **negligible accuracy loss and 24.5% input-token savings**. Laudas takes this further: instead of post-hoc transformation, the wire format is *designed* for tokens from the start.

---

## 3. Vision & North Star

> **A language where the primary feedback loop is the verifier, not the runtime.** The compiler holds a structured conversation with the model — "you claimed X, but on line 12 with input Y, X doesn't hold; here are three ways to fix it." Code that compiles cleanly under Laudas is *vouched-for*, not just grammatical.

**Three commitments:**

1. **The model never writes proofs.** Z3 does that. The model writes specs (refinement types, pre/post conditions, examples) plausible enough for the solver to confirm.
2. **The compiler is a teacher, not a judge.** Every diagnostic includes ranked suggested fixes, plain-English explanations, and a structured payload designed for an LLM to consume.
3. **One way to do it.** No macros, no operator overloading, no implicit conversions, no reflection. Removing degrees of freedom shrinks the model's hallucination surface.

---

## 4. Target users

**Primary — the AI agent.** Generates, edits, iterates on Laudas code. Needs predictable grammar, errors it can patch without re-reading the whole file, types rich enough to encode behavior but simple enough to skip proof skill, and effects in signatures so it can never accidentally hide an I/O dependency.

**Secondary — the human reviewer.** Reads AI-generated Laudas to ship, review, or audit. Needs readable display format, specs that double as documentation, and a verifier whose passing means *something*.

**Tertiary — the human-AI pair.** The most common workflow today. Human writes the spec, agent writes the implementation, the verifier holds them both honest.

---

## 5. Goals & non-goals

**Goals.** G1: higher first-attempt AI success rate than Python on a comparable benchmark. G2: working v0 in one weekend. G3: open-source release as **Volume I (v1.0)** within 6–12 months. G4: clear "why this and not Dafny" answer — *Laudas is to Dafny what Python is to OCaml.* **G5: 5-10× compression** for typical scripts written spec-first vs equivalent Python (production + tests combined). See [compression-target.md](compression-target.md).

**Non-goals (v1).** Dependent types beyond simple refinements; ownership types; concurrency primitives (single-threaded v1); self-hosting compiler; full package ecosystem; replacing Python or JS for general-purpose use.

---

## 6. The wire format — canonical on-disk representation

Wire format is what `.laud` files contain on disk and what LLMs see. **Flat, slot-based, tokenizer-optimized.**

### 6.1 Why slot-based

- Every function has the **same fixed shape**. The LLM never has to remember clause ordering.
- Adding a feature = adding a slot, not new syntax.
- Each slot is independently grammar-maskable for constrained decoding.
- Reads as a structured document, not a soup of clauses.

### 6.2 Why tokenizer-optimized

We measured (see [token_results.txt](token_results.txt)) with cl100k_base and o200k_base BPE tokenizers. Findings:

- **Every short ASCII English keyword (2–5 letters) is 1 token.** `fn`, `in`, `out`, `do`, `end`, `vis`, `eff`, `ex`, `req`, `ens`, `pure`, `prose`, `appearing`, `disappearing`, `answering` — all single-token.
- **`@<letter>` costs 2 tokens.** Rejected. No `@`-prefixed slot markers; bare-word keywords win.
- **Single-space indent merges with the next word into 1 token; two-space indent breaks the merge.** Wire format uses **no indent on slot lines** (the keyword is the marker).
- `|>` is 2 tokens; `->`, `=>`, `→` are 1. Use ASCII operators.

### 6.3 The slot grammar

Functions are flat sequences of labeled lines in fixed order:

```
fn <name>
vis <appearing | disappearing | disappearing(version: X)>
for <interface>?              ; only if implementing a trait
eff <effect-list>
in <param>: <type>            ; zero or more
out <type>
ex <example>                  ; zero or more, ≥1 recommended
req <precondition>            ; zero or more, optional
ens <postcondition>           ; zero or more, recommended
prose "<text>"                ; zero or one, optional (Layer 1 spec)
do
<body>
end
```

Slot order is **fixed**. The parser rejects out-of-order slots — it's a feature: the LLM's output is constrained, the format is grammar-maskable.

### 6.4 Reserved keywords (all 1-token in cl100k / o200k)

| Slot | Meaning |
|---|---|
| `fn` | Function declaration |
| `vis` | Visibility |
| `for` | Trait/interface implementation target (rendered as `answering` in display) |
| `eff` | Effect list |
| `in` | Input parameter |
| `out` | Output type |
| `ex` | Example (Layer 0 spec) |
| `req` | Precondition |
| `ens` | Postcondition |
| `prose` | Layer 1 prose contract |
| `do` | Body start |
| `end` | Function end |

**Visibility values:** `appearing` (exported), `disappearing` (private), `disappearing(version: X.Y)` (deprecated, sunset target version).

**Common effects:** `pure`, `io`, `panics`, `nondet`. User-defined effects allowed. Multiple: `eff io,panics`.

**Body operators:** `==`, `!=`, `<=`, `>=`, `->`, `&&`, `||`, `+`, `-`, `*`, `/`, `%`. All ASCII, all 1 token.

### 6.5 Wire format example

```
fn safe_div
vis appearing
eff pure
in a: int
in b: int
out int?
ex safe_div(10, 2) == Some(5)
ex safe_div(7, 0) == None
ens result.is_some() iff b != 0
do
if b == 0 { return None }
return Some(a / b)
end
```

Twelve lines, no indent on slot lines; body uses braces for control-flow nesting (also 1-token each).

### 6.6 Spec-first inversion

The `do` … `end` block can be empty. When it is, `mira request-body` invokes an LLM to generate a body, then `voronin` verifies it against the spec. The "source code" can be just specs; bodies are derivable artifacts.

```
fn isort
vis appearing
eff pure
in xs: list<int>
out list<int>
ex isort([3,1,2]) == [1,2,3]
ex isort([]) == []
ens result.length == xs.length
ens result.is_sorted_ascending()
do
end
```

Inverts normal coding. The spec is the artifact; the body is regenerable.

### 6.7 Module structure

Files are flat lists of `fn` blocks. `module <name>` at the top of a file declares the module. **No imports in v1** — every name is fully-qualified (`stdlib.transit.spawn`, `myproj.billing.charge`). Imports are a v2 ergonomic feature; for now, fully-qualified names reduce LLM context-tracking burden. (Justified by Karpathy's implicit thesis from the survey: the bottleneck is repo-level affordances, not syntax.)

### 6.8 Visibility in a project

Items are `disappearing` by default at module boundaries. Mark `appearing` to export. The book theme aligns with the semantics: things that are *appearing* can be seen from elsewhere; things that are *disappearing* are fading from the public surface.

---

## 7. The display format — human-facing rendering

Wire is for tokens. Display is for humans. The renderer (`mira show`) translates wire → display; the parser (`mira parse`) round-trips losslessly. Display is **never stored on disk** in v1.

### 7.1 Aesthetic: the Laudan Archive

Each function renders as an archival entry from *The Disappearing: A History of Laudas, Volume I*. Box-drawn separators, fixed-column slot layout, archival framing. A project full of these reads like flipping through Volume I.

```
═══════════════════════════════════════════════════════
  LAUDAS  ▸  vol I  ▸  safe_div
  appearing · pure
  ─────────────────────────────────────────────────────
  in    a : int
        b : int
  out   int?

  ex    safe_div(10, 2)  →  Some(5)
        safe_div( 7, 0)  →  None

  ens   result.is_some() iff b ≠ 0
  ─────────────────────────────────────────────────────
  do
        if b == 0 { return None }
        return Some(a / b)
═══════════════════════════════════════════════════════
```

The wire format underneath remains brutally efficient; the display is purely a viewer. See [display-spec.md](display-spec.md) for the full rendering algorithm.

### 7.2 Where each format is used

| Wire (canonical) | Display (rendered) |
|---|---|
| `.laud` source files | `mira show <file>` (terminal) |
| `git diff` | IDE plugin (VS Code, JetBrains) |
| LLM context windows | Documentation site |
| Compiler internals | Sharing snippets in docs / chat |

### 7.3 Round-trip guarantee

`mira parse(mira show(wire))` ≡ `wire`. Display is a pure rendering, never an information-losing transformation.

---

## 8. Toolchain architecture

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│   mira   │───▶│ voronin  │───▶│   osei   │
│  parse + │    │  verify  │    │   run    │
│  render  │    │          │    │          │
└──────────┘    └──────────┘    └──────────┘
```

### 8.1 `mira` — compiler & renderer

- `mira parse <file>` — parse + type-check, including refinement types
- `mira show <file>` — render display format from wire
- `mira request-body <file>` — fill empty `do` blocks via LLM
- Emits LLM-shaped diagnostics on parse / type errors
- v0: Python; later: Rust

### 8.2 `voronin` — verifier

- Encodes refinements, pre/post conditions, totality obligations as Z3 constraints
- Returns proof or counterexample
- **Auto-adds counterexamples to the function's `ex` slots on failure** — examples grow with verification iterations; the spec self-improves
- Emits LLM-shaped diagnostics (structured JSON + plain English)
- v0: Python + `z3-solver`

### 8.3 `osei` — runtime

- Tree-walking interpreter for v0
- Effect implementations (I/O, time, randomness)
- v0.5: bytecode VM
- Later: AOT compilation via LLVM or similar

### 8.4 `laudas` — unified entrypoint

`laudas check src/` runs `mira` then `voronin` and emits a unified report. `laudas show` is `mira show`. `laudas synth` is `mira request-body`. Most users never invoke the three binaries separately.

### 8.5 Verification cache

Verification results cached by **function content hash**. If neither body nor signature has changed, skip re-verification. Compounds in CI.

### 8.6 Stateless per-function compilation

Each function compiles in isolation given only its callees' signatures. The LLM editing a function only needs that function plus a manifest of callable signatures in context — not the file, not the project. **Single biggest context-efficiency win in the design.**

---

## 9. Specification system (stratified)

| Layer | Form | Compiler treatment |
|---|---|---|
| 0 | `ex` slots | Executed as tests; concrete behavior visible to LLMs |
| 1 | `prose` slot | LLM-checker confirms body matches prose; warns on mismatch |
| 2 | Refinement types + `req` / `ens` | Checked by `voronin` (Z3) at function boundaries |
| 3 | Full proofs (rare) | Reserved for safety-critical code |

The model writes correctness evidence at whichever layer is natural. Examples + types may be enough; if not, the compiler asks for one more layer.

---

## 10. LLM-shaped error format

Every diagnostic emits both human text and a structured JSON payload:

```json
{
  "error": "refinement-violation",
  "location": "src/billing.laud:42",
  "function": "charge_card",
  "expected": "amount > 0",
  "found": "amount can be 0 when discount equals subtotal",
  "suggestions": [
    {"rank": 1, "fix": "guard with `if amount == 0 { return Refunded }`"},
    {"rank": 2, "fix": "tighten subtotal type to `int { > 0 }`"},
    {"rank": 3, "fix": "change return type to allow zero-charge case"}
  ],
  "explanation": "On the discount-equals-subtotal branch, amount becomes 0, but charge_card's signature requires amount > 0..."
}
```

The model patches against the JSON; humans read the explanation. Fixes are **ranked**, not exhaustive — the model picks the highest-ranked feasible fix.

---

## 11. Standard library v0

Minimal set for the prototype:

- `int`, `bool`, `str`, basic arithmetic
- `option<T>`, `result<T, E>`
- `list<T>` with `map`, `filter`, `fold`
- `print`, `read_line` (in `transit`, demonstrating I/O effect)

Stdlib module names (book-themed naming, all locked):

| Module | Purpose |
|---|---|
| `transit` | Async / futures / message passing |
| `archive` | Persistence / storage |
| `manifest` | Package / module manifest |
| `beacon` | Logging / observability |
| `relay` | Networking |
| `record` | Serialization (the Earth Record) |
| `ledger` | Data structures: list, map, set, queue |
| `arith` | Numeric / math |
| `text` | String handling |

---

## 12. Open-source strategy

**License:** Apache 2.0. Standard for languages, patent grant matters.

**Repo structure (single monorepo):**
```
laudas/
├── README.md, LICENSE, CONTRIBUTING.md, CODE_OF_CONDUCT.md
├── docs/volume-i/   ← documentation as in-universe archive
├── compiler/        ← mira
├── verifier/        ← voronin
├── runtime/         ← osei
├── stdlib/
├── examples/
├── tests/
├── rfcs/            ← written RFC process from day one
└── synthesis/       ← synthetic training data tooling
```

**Governance.** Phase 1: BDFL. Phase 2: written RFC process before third contributor. Phase 3: technical steering committee post-Volume I.

**Trademark.** Register *Laudas* with USPTO (~$300). Cheap insurance; the book/language brand crossover makes this more valuable than usual.

**Day-one artifacts.** README with vision and hello-world; a working `laudas check` on a non-trivial example; CONTRIBUTING, COC, LICENSE; `docs/volume-i/intro.md` (the language's introductory chapter); RFC-0001 (public design rationale); a demo video showing the verification feedback loop.

**Community.** GitHub Discussions on day one. Discord only after traffic justifies it. Project website on GitHub Pages.

---

## 13. Cold-start training data

A new language has near-zero training data, so off-the-shelf LLMs cannot generate it well at first. **Synthetic data generation is part of the toolchain, not a separate concern.**

1. Hand-write ~500 example programs covering the language surface
2. Generate variations via a Claude/GPT pipeline that translates Python/TS programs to Laudas, then verifies they pass `voronin check`
3. Publish the synthetic corpus alongside the language
4. Fine-tune an open Laudas-fluent model and release weights
5. Publish a system prompt + few-shot template for off-the-shelf models

---

## 14. Roadmap

| Phase | Target | Scope |
|---|---|---|
| **v0** | One weekend | Wire-format parser, refinement types on params + return, `ex`-as-tests, Z3 boundary check, LLM error format. One demo program with intentional bug + repair transcript. |
| **v0.1** | 1 month | Effects, `option`/`result`, `list<T>`. Unified `laudas check`. Display renderer (`mira show`). |
| **v0.5** | 3 months | Full v1 stdlib, module system, `osei` interpreter complete, prose-checker pass, spec-first inversion (`mira request-body`), counterexample auto-add. |
| **v0.9** | 6 months | First synthetic corpus, fine-tuned open model release, public alpha. |
| **Volume I (v1.0)** | 9–12 months | Public OSS launch, docs site, marketing, conference talk. |

---

## 15. Success metrics

- **M1.** ≥90% pass rate on Laudas-translated HumanEval (or equivalent) for off-the-shelf Claude/GPT with `voronin check`.
- **M2.** Median ≤2 iterations from "agent submits broken Laudas" to "agent submits passing Laudas" using LLM-shaped errors.
- **M3.** ≥10 outside contributors before Volume I.
- **M4.** Trademark registered. Apache 2.0. RFC process documented.

---

## 16. Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Cold-start training data too thin | High | Synthetic corpus + fine-tuned model as part of OSS release |
| Z3 too slow on real-world programs | Medium | Per-function cache; `assume:` escape hatch; offload to `coriolis` for deep audits |
| Refinement types too hairy on complex code | Medium | Stratified spec system lets users drop to examples-only |
| Wire format too foreign for human reviewers | Medium | Display format softens the experience; IDE renders by default |
| Book-themed naming alienates serious users | Low | Themes are cosmetic and removable |
| "Just use Dafny" objection | Real | Position clearly: Dafny verification + Python feel + LLM-targeted toolchain + token-optimal wire format |
| Trademark dispute with another *Laudas* | Low | Search USPTO and existing software registries before launch; register early |

---

## 17. Thematic philosophy (the Nier note)

*The Answering* asks: **if the thing that made you is gone or changed, and you were made for a purpose that no longer applies, what are you for?**

For Laudas, this is the lens on **legacy code, deprecation, and the `disappearing` modifier**. Code marked `disappearing` is not failing — it has *finished* what it was for. The verifier still proves it correct as long as it lives. Documentation tone treats deprecation as completion, not punishment.

The Earth AI from book one stays an ally: AI is the partner, not the threat. Coriolis stands as the cautionary alternative — verification-as-administrative-violence, the path Laudas explicitly does *not* take.

This is voice, not semantics. But it's the through-line that makes the whole project feel coherent.

---

## 18. Open questions (remaining)

1. **`coriolis` as a tool — what is it?** Reserved name. Strongest candidates: a deep CI-only static analyzer; an adversarial property-based fuzzer; a "deep audit" mode of `voronin` that explores the full state space rather than the nearest counterexample. Decision deferred to v0.5+.
2. **Earth Record format** — should the project's full diagnostic / replay log be a first-class artifact?
3. **Synthesis pipeline scope** — open-source the synthesis tooling, or keep internal until Volume I?

All other prior open questions resolved (locked in §6, §7, §8).

---

*— end of PRD draft v0.2 (locked design)*
