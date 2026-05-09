# Prior Art Survey: Programming Languages Designed for LLMs

A scan of what's been built, proposed, and argued about. The headline finding: **the "right" design depends on which of three goals you optimize for — generation success rate, token cost, or verifiability — and the field has not converged.**

---

## 1. Existing proposals and prototypes

There are roughly four buckets of prior art. Most are not "general-purpose programming languages designed for LLMs" — they are DSLs, prompting languages, or research artifacts. True greenfield attempts are rare and recent.

**(a) Prompting / orchestration DSLs (mature, widely used).** These are languages for *humans to drive LLMs*, not for LLMs to write code in. Often conflated with the topic.
- **LMQL** (ETH Zürich) — Python superset with constraint-guided generation. https://lmql.ai/
- **SudoLang** — pseudocode-flavored DSL for *prompting* LLMs in a structured way. Easy to confuse with an LLM-target language; it's the inverse. https://medium.com/javascript-scene/sudolang-a-powerful-pseudocode-programming-language-for-llms-d64d42aa719b
- **DSPy** (Stanford) — "programming, not prompting." Compositional Python that compiles to prompts/weights. The code-as-action paradigm lives here. https://dspy.ai/
- **Guidance / Outlines** — constrained-decoding libraries (grammar/regex/JSON-schema masking).

**(b) Greenfield "LLM-native" languages (early/speculative).**
- **Magpie** — explicitly "optimized for AI generation, not human typing." Uses explicit SSA, two-primitive control flow (`cbr`/`br`), named operations (`i.add { lhs=%a, rhs=%b }`), explicit borrow forms. Trades **~2.3× more tokens per op** for fewer retries. https://magpie-lang.com/
- **GlyphLang** — backend DSL claiming 23% fewer tokens than FastAPI, 57% fewer than Java. https://glyphlang.dev/
- **NanoLang** — prefix-notation, near-zero ambiguity.
- **Marsha**, **PACT** (compiles to Rust). Hobbyist / Show-HN tier.
- Jason Hall's experiment had Gemini and Claude *design* an LLM IR — they iterated through B-IR (unicode opcodes), TBIR (textual), and Loom — and concluded that token minimization alone was insufficient. https://github.com/ImJasonH/ImJasonH/blob/main/articles/llm-programming-language.md

**(c) Mojo — the important distinction.** Mojo (Modular, Chris Lattner) is **AI-first in the sense of "targets ML hardware"** (CPU+GPU via MLIR) and is a Python superset for performance-critical kernels. It is *not* designed to be easier for LLMs to generate. Worth tracking but orthogonal to the question.

**(d) Verification-oriented languages co-evolving with LLMs** — Dafny, Verus, Lean 4, F* — covered in §2.

---

## 2. Academic / research angles

**Token efficiency.** Empirical benchmarks (Rosetta Code over GPT-4 tokenizer, ~19 languages) and the `vibe-coding-lang-bench` repo converge on:
- Python is the practical winner (~130 tokens avg per task; ~1.3× fewer than Rust, ~1.5× on REST APIs).
- Functional/typed languages (Haskell, F#) are surprisingly competitive (~115–118 tokens) thanks to inference.
- APL/J are token-dense but unusable in practice — no training data.
- https://github.com/adriangalilea/vibe-coding-lang-bench

**Formal verification + LLMs ("vericoding").** This is the most rigorous corner of the space. The arXiv 2509.22908 benchmark across Dafny / Verus / Lean shows:
- Off-the-shelf LLM success rates: **Dafny 82%, Verus/Rust 44%, Lean 27%.**
- Pure Dafny verification: **68% → 96% over one year.**
- Natural-language descriptions added to specs barely help.
- Implication: **SMT-automated languages with cheap proof feedback dominate.** Lean's expressivity hurts when the LLM has to discharge proofs itself.
- https://arxiv.org/abs/2509.22908
- https://dafny.org/blog/2025/06/21/dafny-annotator/

**Constrained / structured generation.** Mature tooling: GBNF (llama.cpp), JSON Schema, XGrammar, Outlines, Guidance. Token-mask the decoder so output *cannot* violate a grammar. This is the substrate any LLM-targeted language will sit on.

**Code-as-action / agent frameworks.** DSPy and ReAct-style loops treat code as the action language for tool use.

---

## 3. Design tensions (the real ones)

| Tension | What practitioners say |
|---|---|
| **Training-data dominance vs. theoretical elegance** | The most-cited objection on HN. APL is token-efficient but LLMs can't write it. Even Haskell suffers vs. JS/Python. Any new language has a cold-start problem solvable only by synthetic data + RL. |
| **Token density vs. retry rate** | Magpie's deliberate 2.3× verbosity *increases* per-op tokens but *decreases* retries. Cheap signal beats compactness. |
| **Generation vs. auditability** | If humans can't read it, every error-recovery and security review needs a re-emission. Loom/B-IR experience: pure machine IR was rejected even by the LLMs that designed it. |
| **Spec-heavy vs. pragmatic** | "The ideal language for AI is the one humans keep rejecting" — Lean 4, F\*, Idris 2 score top on theoretical fit, last on adoption. |
| **New language vs. constrained subset** | Strong faction (Willison, several HN commenters): pick a Python/TS subset + a strict linter + constrained decoding. Jason Hall's experiment ended here too. |
| **Static types for verification vs. flexibility** | Types help LLMs *verify themselves* via compiler feedback loops. This advantage compounds with iteration; ergonomic cost is paid once. |
| **Optimize for which loop?** | (a) generation accuracy, (b) execution cost, (c) human audit. Different answers — Magpie picks (a), GlyphLang picks (b), Dafny picks both (a) and verifiability. |

---

## 4. Notable opinions

- **Andrej Karpathy** — has not proposed an LLM-targeted language directly. His "skills" / `CLAUDE.md` work and "vibe coding" coinage focus instead on **structuring context and workflow** around existing languages. Implicit thesis: the bottleneck isn't syntax, it's repo-level affordances.
- **Simon Willison** — pragmatist; emphasizes existing-language scaffolding, not new languages. "Hallucinations in code are the least dangerous form of LLM mistakes" because the compiler catches them — itself a design argument for fast-feedback languages.
- **Padmaraj Kore — "Rethinking Programming Languages for LLMs"** — best short manifesto for the maximalist position (machine-native graph IR, formal verification at every step, plain-text source code "doesn't exist"). https://medium.com/coinmonks/rethinking-programming-languages-for-llms-building-a-machine-native-language-4acd85431381
- **Jason Hall (ImJasonH)** — useful skeptic-turned-empiricist; let LLMs design their own IR and watched them re-invent readable assembly.
- **AkitaOnRails** — clearest articulation of the human-vs-LLM ergonomics tradeoff. https://akitaonrails.com/en/2026/02/09/ai-agents-best-programming-language-for-llms/

---

## Bottom line — the three live design philosophies

1. **Verbosity-for-correctness** (Magpie): explicit SSA, no syntactic sugar, accept 2× tokens for first-try success.
2. **Token-minimal high-level** (GlyphLang, Python-the-default): small surface, rich stdlib, lean on training-data abundance.
3. **Spec-and-verify** (Dafny-style with LLM): SMT does the work; LLM emits spec + program; proof loop replaces unit tests. The Dafny success-rate trajectory (68→96%) is the strongest empirical case in the space.

The under-explored quadrant — and probably the most interesting design space for a greenfield project — is **(3) with the ergonomics of (2)**: a language whose *primary feedback loop is verification, not execution*, but that doesn't require Lean-grade proof skill from the model. That's where the open research is.

The cold-start training-data problem applies to all three; whichever path is chosen, plan for synthetic-data generation as a first-class part of the toolchain.
