# Laudas

> *Code that survives the crossing.*

A verification-first programming language designed for AI agents to generate and human-AI pairs to maintain. The compiler talks back to the model in plain English. The verifier (Z3-backed) does the proofs. The wire format is engineered for LLM tokens; the display format is rendered as Laudan archival entries — pages from *Volume I*.

**Status:** pre-alpha (v0.5). Working: parser, example runner, Z3 verification, display renderer, list / lambda / method-chaining, Python FFI. Not yet: type aliases, records, spec-first inversion, multi-file modules.

---

## Hello, Laudas

A function with a spec, three worked examples, and a postcondition the verifier proves over *all* inputs:

```laudas
fn safe_div
vis appearing
eff pure
in a: int
in b: int
out int?
ex safe_div(10, 2) == Some(5)
ex safe_div(7, 2) == Some(3)
ex safe_div(7, 0) == None
ens result.is_some() iff b != 0
do
if b == 0 { return None }
return Some(a / b)
end
```

Run it:

```powershell
laudas safe_div.laud
```

```
fn safe_div  [appearing · pure]
  ex   ✓  safe_div(10, 2) == Some(5)
  ex   ✓  safe_div(7, 2) == Some(3)
  ex   ✓  safe_div(7, 0) == None
  ver  ✓  ens result.is_some() iff b != 0

all checks passed  ·  3 examples + verification
```

The verifier proves the postcondition holds for *every* `int × int` input — not just the three you wrote. That's what `ver ✓` means.

---

## Install

**Option A — pip (developers):**

```powershell
git clone https://github.com/IshiakiZ/laudas
cd laudas
pip install -e .
```

This puts `laudas` on PATH. Works on any system with Python 3.10+.

**Option B — standalone binary (everyone else):**

Download `laudas.exe` from the [Releases page](https://github.com/IshiakiZ/laudas/releases). Drop it in any folder on PATH. No Python required.

---

## Two faces of the same code

**Wire format** (what the LLM sees, what's stored on disk — token-optimized):

```laudas
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

**Display format** (`laudas --show file.laud` — what humans see, rendered as a Laudan archive entry):

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

Round-trip is lossless: `laudas --show` is a pure renderer.

---

## What makes Laudas different

**The verifier is the headline feature.** Every diagnostic emits a structured JSON payload designed for an LLM to consume — error type, location, expected vs. found, **ranked suggested fixes**, plain-English explanation. The model patches against the JSON; humans read the explanation.

**Specs are tests.** The `ex` slot gives you concrete examples (run as tests), `prose` gives you a human-readable contract (LLM-checked), `req` and `ens` give you formal pre/postconditions (Z3-checked). Use whichever layer is natural — you don't have to write proofs.

**Effects in signatures.** `eff pure`, `eff io`, `eff io,panics` — declared on every function. A function that calls an `eff io` function must declare `eff io` itself. No more "pure" functions that secretly hit a database.

**One way to do it.** No macros, no operator overloading, no implicit conversions, no reflection. Removing degrees of freedom shrinks the model's hallucination surface.

**Tokenizer-aware grammar.** Every keyword is a single token in cl100k_base / o200k_base. Slot order is fixed. No `@`-sigils (they cost 2 tokens each). Constrained-decoding-friendly by design.

**Day-one Python interop.** Any pip-installable package works via the `extern python "module.func"` slot:

```laudas
fn isqrt
vis appearing
eff pure
in x: int
out int
ex isqrt(9) == 3
extern python "math.isqrt"
end
```

---

## The book connection

Laudas takes thematic vocabulary from *The Disappearing* and *The Answering* — a sci-fi trilogy in which AI-built rockets carry humanity to an exoplanet called Laudas. The hook *AIs built the rockets that saved humans* mirrors the language's positioning as **AI-built infrastructure for the post-AI computing era**.

- **Laudas** — the destination, the new world. The language name.
- **`appearing` / `disappearing`** — visibility keywords (public / private). From the Disappearing/Appearing arcs.
- **`answering`** — trait/interface implementation (display rendering of the wire `for` keyword). From book two, *The Answering*.
- **`mira`, `voronin`, `osei`** — the three POV characters; the three CLI tools (compiler, verifier, runtime).
- **`coriolis`** — reserved name for a future second-opinion analyzer; the antagonist civilization of book two.
- **Volumes** — major releases. v1.0 will be **Volume I**.

The thematic frame is paint, not structure: removable without harming the language.

---

## Roadmap

| Phase | Status | Highlights |
|---|---|---|
| **v0** | shipped | parser, example runner, LLM error format |
| **v0.1** | shipped | Z3 verification, counterexample-finding, display renderer |
| **v0.5** | partial | lists, lambdas, method chaining, Python FFI |
| v0.5 (rest) | next | type aliases, records, stdlib stubs, spec-first inversion |
| v0.9 | later | synthetic training corpus, fine-tuned model |
| **Volume I (v1.0)** | 9–12 months | public OSS launch, native Rust compiler, docs site |

See [prd.md](prd.md) for the canonical product spec, [research-survey.md](research-survey.md) for prior-art context, [compression-target.md](compression-target.md) for the 5–10× compression story.

---

## Contributing

The project is pre-alpha and the language design is still moving. The fastest way to help right now: open an issue with example code that *should* compile but doesn't, or a postcondition that *should* verify but doesn't.

When the language is stable enough for an RFC process (target: post-Volume I), it'll live in `rfcs/`. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

[Apache 2.0](LICENSE). You can use Laudas in commercial work, fork it, embed it. Please don't trademark "Laudas."

---

*Volume I begins.*
