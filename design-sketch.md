# Design Sketch — Verification-First Language for LLMs

*Working name: `Verum` (placeholder — Latin "true", fits the verification theme).*

## North star

A language where the **primary feedback loop is the verifier, not the runtime**. The compiler holds a structured conversation with the model: "you claimed X, but on line 12 with input Y, X doesn't hold — here are three ways to fix it." Errors are designed to be *consumed by an LLM*, not stared at by a human.

We trade some Dafny-grade rigor for ergonomics. The model should not need to discharge proofs; the SMT solver does. The model just needs to write code that's **plausibly correct** and **annotated enough for the solver to confirm**.

---

## Five core principles

1. **Specs and code live together, not in separate files.** Function signature carries the contract: refinement types on inputs, post-conditions on outputs, effects declared. No external test files for spec-level properties.

2. **Examples are first-class.** Every function may carry inline `examples:` that are simultaneously documentation, tests, and grounding for the model. The compiler checks them; the model reads them.

3. **Total by default, partial by declaration.** Functions are pure and total unless they explicitly declare otherwise (`effect: io`, `effect: panics`, `effect: nondeterministic`). Effects are part of the type, infectious upward — the model can never accidentally hide an I/O dependency.

4. **Errors are LLM-shaped, not human-shaped.** Every diagnostic is structured (JSON-like), located precisely, and includes 1–3 ranked suggested fixes in plain English. The compiler is a teacher, not a judge.

5. **One way to do it.** No macros, no operator overloading, no implicit conversions, no reflection. Removing degrees of freedom shrinks the model's hallucination surface.

---

## Novel ideas

### Stratified specification

The model writes correctness evidence at whichever layer is natural for the task:

- **Layer 0 — examples**: `safe_div(10, 2) == 5`. Cheap, concrete, often enough.
- **Layer 1 — prose contract**: `"returns None if denominator is zero"`. Becomes documentation; can be lifted into Layer 2 by an annotator pass.
- **Layer 2 — refinement types & pre/post**: formal but lightweight. The SMT solver does the work.
- **Layer 3 — full proofs**: only for safety-critical code. Most code never touches this layer.

The compiler's job is to *propagate* evidence: if you have examples + types, that may be enough to verify a property. If not, it asks for one more layer.

### LLM-targeted error format

Every error is emitted as both human text *and* a structured payload:

```
{
  "error": "refinement-violation",
  "location": "src/billing.vrm:42:8",
  "function": "charge_card",
  "expected": "amount > 0",
  "found": "amount can be 0 when discount equals subtotal (line 38)",
  "suggestions": [
    {"rank": 1, "fix": "guard with `if amount == 0: return Refunded`"},
    {"rank": 2, "fix": "tighten subtotal type to `int { > 0 }`"},
    {"rank": 3, "fix": "change return type to allow zero-charge case"}
  ],
  "explanation": "On the discount-equals-subtotal branch, amount becomes 0, but charge_card's signature requires amount > 0. Either prevent the zero case or expand the contract."
}
```

The model patches against the structured payload; humans read the explanation.

### Effects as types

```
fn read_user(id: UserId) -> User effect: io, fails: NotFound
```

A function that calls `read_user` *must* declare `effect: io` itself unless it catches the failure. The model cannot accidentally write a "pure" function that secretly reads a database. This kills a whole class of agentic-coding bugs.

### Prose checkability

Prose contracts (`"returns None if denominator is zero"`) are not just docs — a separate compiler pass uses an LLM to check whether the implementation matches the prose, and emits a *prose-violation* warning the same way an SMT failure would. Optional, slower, but available.

---

## Syntax sketch

```verum
# Tiny example: safe division with full spec
fn safe_div(a: int, b: int) -> int? {
  effect: pure

  examples:
    safe_div(10, 2)  == Some(5)
    safe_div(7, 2)   == Some(3)
    safe_div(7, 0)   == None
    safe_div(-6, 2)  == Some(-3)

  ensures: result.is_some() iff b != 0

  if b == 0 { return None }
  return Some(a / b)
}
```

```verum
# Refinement type at the boundary
fn percentage(part: int { >= 0 }, whole: int { > 0 }) -> int { 0..=100 } {
  effect: pure

  examples:
    percentage(25, 100) == 25
    percentage(1, 3)    == 33
    percentage(0, 5)    == 0

  ensures: result <= 100

  return (part * 100) / whole
}
```

```verum
# Effect tracking in action
fn cached_fetch(url: Url) -> Bytes effect: io, cache_rw {
  examples:
    # first call hits network, second hits cache (illustrative — runtime checks this)

  if cache.has(url) {
    return cache.get(url)   # cache_rw
  }
  let bytes = http.get(url) # io
  cache.put(url, bytes)     # cache_rw
  return bytes
}

# Compile error if you try to call cached_fetch from a `pure` function:
#
# error: effect-leak
#   location: src/report.vrm:14:18
#   function `summarize` declared effect: pure
#   but calls `cached_fetch` which has effect: io, cache_rw
#   suggestions:
#     1. add `effect: io, cache_rw` to summarize
#     2. accept the bytes as a parameter instead of fetching inside
#     3. memoize the fetch outside summarize and pass result in
```

---

## What we're explicitly NOT doing (yet)

- **Linear/affine types** (Rust-style ownership). Adds power but adds friction; defer.
- **Dependent types** beyond simple refinements. Lean territory; too hard for the model to reason about without help.
- **Concurrency primitives.** v1 is single-threaded. Effects framework should extend cleanly later.
- **A standard library.** v0 needs only `int`, `bool`, `str`, `list`, `option`, `result`, basic arithmetic, basic I/O.
- **Self-hosting.** Compiler will be Python (or Rust) for the foreseeable future.

---

## Open questions to resolve before prototyping

1. **Name.** `Verum`? Something else? (The folder is `AiCodingLng` — placeholder, presumably.)
2. **Surface syntax: braces or indentation?** Braces are easier to parse and harder to mess up; indentation is more Pythonic. Lean toward **braces** for unambiguous parsing.
3. **SMT backend.** Z3 is the obvious choice. Pre-built bindings exist for Python and Rust.
4. **Compiler host language.** **Python** is fastest to prototype and lets us reuse Z3 bindings and integrate LLM-error-formatting trivially. Rust later if we ever care about speed.
5. **What's the "hello world" demo?** Probably a function with a non-trivial refinement, a deliberately broken implementation, and a transcript of the LLM-formatted error message guiding the model to a fix. That's the marketing.

---

## Smallest plausible v0

If we go to prototype, the minimum-interesting-thing is:

- Parser for a tiny subset (functions, ints, bools, if/else, return)
- Refinement types on parameters and return values
- `examples:` block, executed as tests
- Z3 integration to check refinements at function boundaries
- Compiler emits LLM-formatted error JSON on failure

That's a one-weekend toy. If it works, we extend.
