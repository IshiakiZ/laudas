# Laudas — five-minute playbook

Skim this if you want to evaluate Laudas without reading the [PRD](prd.md). Goal: enough context in 5 minutes to know whether Laudas is worth a deeper look.

---

## The 30-second version

Laudas is a programming language designed for **AI agents to generate and human-AI pairs to maintain**. It treats verification as a first-class part of the inner dev loop — every function carries a spec (examples, pre/post conditions, prose), and a Z3-backed verifier proves the spec holds for *every* input, not just the ones you tested.

The on-disk format is engineered for LLM tokens (every keyword is a single token, slot order is fixed). The display format renders the same code as Laudan archive entries — pages from *Volume I* of the in-universe history of the planet Laudas.

It works today. There's a six-step tutorial, seven CLI tools, a Python FFI, a standalone Windows binary. Pre-alpha; the language design is still moving.

---

## The 60-second proof

Three examples, one postcondition, the verifier finding a bug you didn't test for:

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
if b == 0 { return Some(0) }    ← bug: should be `return None`
return Some(a / b)
end
```

Run `laudas safe_div.laud`:

```
ex   ✓  safe_div(10, 2) == Some(5)
ex   ✓  safe_div(7, 2) == Some(3)
ex   ✗  safe_div(7, 0) == None              ← example mismatch
ver  ✗  ens result.is_some() iff b != 0     ← Z3 found a counterexample
        counterexample: a = -1, b = 0  →  result = some(0)
```

Z3 found `a = -1` — an input you never tested for. **That's the difference between testing and verification.** And every diagnostic is also emitted as structured JSON with ranked suggested fixes — designed to be consumed by an LLM.

---

## The 90-second tour

### Hello world

```laudas
fn answer
vis appearing
eff pure
out int
ex answer() == 42
do
return 42
end
```

`laudas hello.laud` → verifies. Done.

### Real CLI tool

```laudas
fn main
vis appearing
eff io
out int
do
let raw = io.read_stdin()
let lines = text.split(raw, "\n").filter(l -> l.length() > 0)
io.println(text.join(lines.sort(), "\n"))
return 0
end
```

That's `examples/sort.laud` — Unix `sort` in eight lines. Pipe stuff in, sorted lines come out:

```
Get-Content crew.csv | laudas run examples/sort.laud
```

### Python FFI for what's hard

```laudas
fn parse_json
vis appearing
eff pure
in s: str
out str
ex parse_json("[1, 2, 3]") == [1, 2, 3]
extern python "json.loads"
end
```

The body is Python's `json.loads`. Examples still run; voronin skips with a clear reason ("body is foreign").

### Spec-first inversion

```laudas
fn isort
vis appearing
eff pure
in xs: list<int>
out list<int>
ex isort([3, 1, 2]) == [1, 2, 3]
ens result.length == xs.length
ens result.is_sorted_ascending()
do
end
```

Empty `do` block. `laudas request-body isort.laud` calls Claude (via `ANTHROPIC_API_KEY`), fills the body, writes `isort.filled.laud`. Then `laudas isort.filled.laud` verifies the generated body against the spec.

---

## When Laudas is for you

- You're writing code with an LLM in the loop and you wish your tools talked back to the model in a structured way.
- You want to define a function once — spec + tests + docs collapsed into one artifact — and have the verifier prove correctness without writing proofs yourself.
- You're building CLI tools and you want the verified-spec-then-execute model.
- You like the aesthetic of language-as-archive and want code that reads like *Volume I*.

## When Laudas is not for you

- You need a production language right now. This is pre-alpha; APIs change.
- You're doing heavy numeric work or anything performance-critical. Laudas is currently a Python interpreter; native Rust port is on the roadmap.
- You need rich library ecosystems built *for* Laudas. The stdlib is small; you fall back to `extern python` for anything beyond what's listed.
- You're allergic to themed naming. The book vocabulary (`appearing` / `disappearing` / `answering` / Mira / Voronin / Osei) is part of the project's identity. It's removable but not absent.

---

## What to do next

In rough order of "fastest path to is-this-for-me":

1. **5 min:** clone the repo, run `laudas demo_fixed.laud` and `laudas demo_buggy.laud`. See the verifier loop.
2. **15 min:** walk the [tutorial](tutorial/) — six small `.laud` files, each adding one concept.
3. **30 min:** read [examples/](examples/) — seven CLI tools, each ~10–25 lines. Find one similar to something you'd build.
4. **1 hour:** write your own `.laud` file. Use the [PRD](prd.md) and [compression-target.md](compression-target.md) as references.
5. **Open an issue** if you hit something. The [bug template](.github/ISSUE_TEMPLATE/bug_report.yml) and [verifier-limit template](.github/ISSUE_TEMPLATE/verifier_limit.yml) are designed for fast iteration.

---

## What this isn't yet

For honesty:

- The standalone `laudas.exe` is ~46 MB. PyInstaller-bundled Python + Z3 + Anthropic SDK. The native Rust rewrite (planned for v1.0) cuts this to ~3-5 MB.
- The verifier (voronin) handles a v0.5-era subset of body shapes: `let`, `if EXPR { return EXPR }`, `return EXPR`, integer arithmetic, comparisons, &&/||, Option types, refinement types on int/bool/str/record fields, simple string method chains. Anything outside that subset gracefully reports `ver · skipped` with the reason. Each skip is a candidate for the next voronin release.
- No multi-arg Z3 lambdas yet. `.fold((acc, x) -> ...)` works at runtime but voronin can't symbolically execute it.
- No multi-file `use` resolution beyond simple includes (every imported symbol lands in the current namespace).
- No standard library beyond what's listed in [`prd.md`](prd.md) §11 and the `MODULES` table in `laudas.py`.

The list of things-not-yet is the project's roadmap. Volume I (v1.0) will close most of it. See the [PRD](prd.md) §14.

---

*Volume I begins.*
