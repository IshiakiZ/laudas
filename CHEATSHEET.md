# Laudas — cheatsheet

Every feature, one line each. Print this and stick it next to your monitor. Or paste it into your LLM's system prompt.

---

## File structure

```laudas
; comments start with semicolon, run to end of line
use "other.laud"                        ; include another .laud file
type Point { x: int, y: int }           ; record type
fn foo ... do ... end                   ; function declaration
```

## Function — full slot grammar

```laudas
fn name                                 ; required: name
vis appearing | disappearing            ; required: visibility
for SomeInterface                       ; optional: trait impl
eff pure | io | panics | nondet | ...   ; required: effect list
in x: int                               ; one per parameter
in y: int { > 0 }                       ; refinement type
out int                                 ; required: return type
out int { 0..=100 }                     ; refined return
ex name(2) == 4                         ; example: examples are tests
req x >= 0                              ; precondition
ens result <= 100                       ; postcondition (Z3-checked)
prose "human-readable contract"         ; LLM-checked prose
do
  return x + y                          ; body
end
```

Slot order is **fixed**. Out-of-order is a parse error.

## Effects

| Effect | What it means |
|---|---|
| `pure` | No side effects. The default for math / data manipulation. |
| `io` | Reads/writes outside world. Required if you call `io.*`, `archive.*`. |
| `panics` | May abort. Stronger than `fails`. |
| `nondet` | Different result for the same input (random, time, etc.). |

Effects are **infectious upward**. If you call `eff io`, your function must declare it.

## Visibility

```laudas
vis appearing                           ; public — exported
vis disappearing                        ; private — module-internal (default)
vis disappearing(version: 2.0)          ; deprecated — sunset target
```

## `extern python "module.func"` — Python FFI

```laudas
fn sqrt
vis appearing
eff pure
in x: int
out int
ex sqrt(9) == 3
extern python "math.isqrt"              ; replaces do/end body
end
```

## `fn main` — runnable programs

```laudas
fn main
vis appearing
eff io
in args: list<str>                      ; optional CLI args
out int                                 ; exit code
do
  io.println("Hello, Laudas!")
  return 0
end
```

Run it: `laudas run file.laud [arg1 arg2 ...]`.

---

## Body language

### Statements

```laudas
let x = expr                            ; bind a value
if cond { return val }                  ; early return
return val                              ; final return
io.println("side effect")               ; expression statement
```

### Expressions

```laudas
42        true        false       "hello"        None
[1, 2, 3]                               ; list literal
Some(x)                                 ; Option Some constructor
Point { x: 0, y: 0 }                    ; record literal
p.x                                     ; field access
xs.length()                             ; method call
xs.filter(x -> x > 0).sum()             ; method chain
(a, b) -> a + b                         ; multi-arg lambda
```

### Operators

```
arithmetic:  + - * / %
compare:     == != < > <= >=
logic:       && ||
ternary:     -- not yet (use if/return)
```

---

## Built-in modules

```laudas
io.println(s)         io.print(s)         io.eprintln(s)
io.read_line()        io.read_stdin()
text.split(s, sep)    text.join(xs, sep)  text.contains(s, sub)
text.upper(s)         text.lower(s)       text.trim(s)
text.length(s)        text.repeat(s, n)   text.replace(s, old, new)
text.parse_csv(s)     text.to_json(v)     text.to_json_pretty(v)
text.to_int(s)        text.from_int(n)
arith.abs(x)          arith.min(a, b)     arith.max(a, b)   arith.pow(a, b)
arith.sum_of(xs)      arith.min_of(xs)    arith.max_of(xs)
ledger.range(n)       ledger.length(xs)
archive.read(path)    archive.write(path, content)
```

## Built-in methods

### List

```laudas
xs.length()    xs.is_empty()  xs.sum()       xs.min()       xs.max()
xs.first()     xs.last()      xs.at(i)
xs.contains(x)
xs.tail()      xs.take(n)     xs.skip(n)
xs.unique()    xs.sort()      xs.reverse()
xs.sort_by(x -> key)          xs.dedupe_by(x -> key)
xs.filter(x -> pred)          xs.map(x -> expr)
xs.fold(init, (acc, x) -> ...)
```

### String

```laudas
s.length()     s.upper()      s.lower()      s.trim()
s.contains(sub)               s.starts_with(p)              s.ends_with(p)
s.split(sep)
```

### Int

```laudas
i.abs()
```

### Option<T>

```laudas
opt.is_some()         opt.is_none()         opt.value()
opt.unwrap_or(default)
```

---

## CLI

```bash
laudas FILE.laud                  ; verify (parse + run examples + Z3)
laudas --show FILE.laud           ; render as Laudan archive entries
laudas run FILE.laud [args...]    ; execute the file's main function
laudas request-body FILE.laud     ; fill empty `do` blocks via Claude (needs ANTHROPIC_API_KEY)
```

---

## What voronin verifies (the Z3 layer)

| Type / pattern | Status |
|---|---|
| `int`, `bool`, `str`, `int?` (Option<int>) inputs | ✓ |
| `record` types with `int`/`bool`/`str` fields | ✓ |
| `list<int>`, `list<bool>`, `list<str>` inputs (Z3 Seq) | ✓ |
| Refinement types: `int { > 0 }`, `int { 0..=100 }` | ✓ |
| `req` preconditions | ✓ |
| `ens` postconditions over int / bool / records / Option | ✓ |
| `iff` and `implies` in postconditions | ✓ |
| `s.length()`, `xs.length()`, chained methods | ✓ |
| `s.contains(sub)`, `xs.contains(x)` in ens | ✓ |
| `xs.filter(...)` / `xs.map(...)` length over-approximation | ✓ |
| Body shape: `(let | if-return)* return` | ✓ |
| Output refinement check | ✓ |
| Counterexample pretty-printed as Laudas syntax | ✓ |
| `.fold(init, fn)` symbolic execution | ✗ (skip with reason) |
| Element-wise reasoning about `.filter` / `.map` | ✗ (skip — only length) |
| `extern python` bodies | ✗ (skip — body is foreign) |

---

## Counterexamples

When voronin can't prove an `ens`, it prints a concrete counterexample:

```
ver  ✗  ens result.is_some() iff b != 0
        counterexample: a=-1, b=0 → result = Some(0)
```

That input wasn't in your `ex` slots — **Z3 found it**. Either fix the body or fix the postcondition.

The same diagnostic also gets emitted as structured JSON (`error`, `expected`, `found`, `suggestions[]`, `explanation`) — designed to be consumed by an LLM.

---

## When in doubt

- Tutorial: `tutorial/01_hello.laud` → `tutorial/06_runnable.laud`
- Examples: [`examples/`](examples/) — eight real CLI tools
- PRD (canonical spec): [`prd.md`](prd.md)
- 5-min playbook: [`PLAYBOOK.md`](PLAYBOOK.md)

*Volume I begins.*
