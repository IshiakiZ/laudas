# Laudas — five-step tutorial

Write your first verified Laudas function, then build up to a real-world pipeline. Each step is a self-contained `.laud` file in this directory. Run any of them with:

```
laudas tutorial/01_hello.laud
```

(Substitute the file you want.)

If you don't have `laudas` installed yet, see the [main README](../README.md#install).

---

## The five steps

| # | File | What you'll learn |
|---|---|---|
| 1 | [`01_hello.laud`](01_hello.laud) | The slot grammar; what `fn`, `vis`, `eff`, `in`, `out`, `do`, `end` mean |
| 2 | [`02_examples.laud`](02_examples.laud) | `ex` slots: examples are tests |
| 3 | [`03_verifier.laud`](03_verifier.laud) | `ens` postconditions: Z3 proves your spec for **every** input |
| 4 | [`04_collections.laud`](04_collections.laud) | Lists, lambdas, method chains, records, field access, `let` bindings |
| 5 | [`05_pipeline.laud`](05_pipeline.laud) | A real pipeline: parse → validate → dedupe → sort → JSON. The compression-target demo. |

---

## Step 1 — Hello, Laudas

Open [`01_hello.laud`](01_hello.laud) and read it top to bottom. The slot grammar is fixed:

```
fn NAME              # function name
vis appearing        # public; the alternative is `disappearing`
eff pure             # no side effects; the alternative is `io`, `panics`, etc.
in PARAM: TYPE       # input parameter (one per line; can have many)
out TYPE             # output type
do                   # body starts here
... statements ...
end                  # function ends
```

Every keyword is a single token in the major LLM tokenizers. Slot order is fixed (the parser rejects out-of-order slots). That's a feature: the LLM never has to guess clause ordering.

Run it:

```
laudas tutorial/01_hello.laud
```

You'll see the function parsed and verified. Verification skips here because there's nothing to verify yet — that comes in step 3.

---

## Step 2 — Examples are tests

[`02_examples.laud`](02_examples.laud) adds `ex` slots: concrete examples that are run as tests when you `laudas` the file.

```
ex add(2, 3) == 5
```

The expected value can be any Laudas literal — `int`, `Some(x)`, `None`, list, record, string. The example runner calls the function and compares.

When examples fail, you get an LLM-shaped diagnostic: structured JSON + plain-English explanation + ranked suggested fixes. See [`../demo_buggy.laud`](../demo_buggy.laud) for the bug-and-repair loop in action.

---

## Step 3 — The verifier

[`03_verifier.laud`](03_verifier.laud) adds an `ens` postcondition. Now Z3 (via voronin) proves the postcondition holds for **every** integer input — not just the examples.

```
ens result.is_some() iff b != 0
```

This is the headline feature. Three examples might all pass, but Z3 tries `a = -1, b = 0`, `a = 999999, b = -7`, and infinitely many more. If the body satisfies the postcondition for *all* of them, you get `ver ✓`. If not, you get a concrete counterexample — a specific input where the body breaks the spec. The model uses that counterexample to fix the body and try again.

---

## Step 4 — Real types

[`04_collections.laud`](04_collections.laud) introduces:

- **Lists** — `[1, 2, 3]`, `xs.length()`, `xs.sum()`, `xs.first()`, `.at(i)`
- **Arrow lambdas** — `x -> x * 2`
- **Method chains** — `xs.filter(p).map(f).sort_by(g)`
- **Records** — `type Point { x: int, y: int }` then `Point { x: 3, y: 4 }`
- **Field access** — `p.x`
- **Let bindings** — `let dx = p.x - q.x`

These are the building blocks for non-trivial programs.

---

## Step 5 — A real pipeline

[`05_pipeline.laud`](05_pipeline.laud) is the compression-target.md demo as actually runnable Laudas. It:

1. Parses a CSV-ish row into a `User` record
2. Filters out invalid rows
3. Dedupes by lowercased email
4. Sorts by (role, name)
5. Serializes to JSON

Roughly 25 lines of Laudas, doing what would be ~70 lines of Python (production code + pytest tests combined). See [`../compression-target.md`](../compression-target.md) for the side-by-side analysis.

---

## What's not in the tutorial yet

- `req` preconditions (covered in [`../demo_let_verify.laud`](../demo_let_verify.laud))
- `prose` slots (LLM-checked natural-language contracts)
- `extern python` (covered in [`../demo_extern.laud`](../demo_extern.laud))
- `use "PATH"` multi-file modules (covered in [`../demo_use_main.laud`](../demo_use_main.laud))
- `laudas request-body` spec-first inversion (covered in [`../demo_specfirst.laud`](../demo_specfirst.laud); requires `ANTHROPIC_API_KEY`)

Once you've worked through the five steps, those demos read naturally.
