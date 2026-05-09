# Laudas Display Format Specification

## 1. Purpose

Wire format (`.laud` on disk) is optimized for LLM tokens. Display format is for humans: rendered by `mira show` (terminal), the IDE plugin, and the documentation site. Display is **never the source of truth** — wire round-trips through `mira parse → mira show → mira parse` losslessly.

```
                           mira show
                       ┌─────────────────┐
       wire format     │                 │     display format
       ───────────▶   │   render only    │   ───────────▶
       (canonical)     │  (no semantics)  │     (humans)
                       └─────────────────┘
                              ▲   │
                              │   │ mira parse
                              └───┘
                          (wire is recovered exactly)
```

## 2. Aesthetic: the Laudan Archive

Each function = one entry from *The Disappearing: A History of Laudas, Volume I*. The visual identity is **archival, manifest-like, deliberate**. Box-drawn separators, fixed-column slot layout, archival framing. A project full of these reads like turning pages of a meticulously-kept history.

The aesthetic is paint, not structure. Removable without harming the language.

## 3. Header line

```
LAUDAS  ▸  vol <N>  ▸  <function-name>
<vis> · <eff>
```

- `<N>` is the project's current major version (Volume number)
- `<vis>` and `<eff>` form a sub-header line below the main title
- If `for <interface>` is present in the wire, the header reads:

```
LAUDAS  ▸  vol <N>  ▸  <function-name>  —  answering <interface>
<vis> · <eff>
```

**Note the keyword change:** wire uses `for`; display uses `answering`. This is the one place the display format renames a keyword for thematic effect (the function "answers" the interface's question).

## 4. Slot rendering

Each slot type renders with a label and a stable column position. Labels are 4 characters wide, followed by 4 spaces, then the value (column 9):

| Wire slot | Display label | Notes |
|---|---|---|
| `fn` | (header) | Used in title, not a body slot |
| `vis` | (header sub-line) | |
| `for` | (header, `— answering <T>`) | Note keyword change |
| `eff` | (header sub-line) | |
| `in` | `in    <name> : <type>` | First param shows `in`; subsequent params align without `in` |
| `out` | `out   <type>` | |
| `ex` | `ex    <example>` | First example shows `ex`; subsequent examples align without `ex` |
| `req` | `req   <precondition>` | |
| `ens` | `ens   <postcondition>` | |
| `prose` | `note  <text>` | Italicized in IDE rendering |
| `do` | `do` | Marks body section |
| body | (indent 8 spaces) | Contents copied verbatim from wire |
| `end` | (closing rule) | Bottom horizontal rule, no `end` text |

## 5. Box drawing characters

| Symbol | Codepoint | Use |
|---|---|---|
| `═` | U+2550 | Top and bottom of entry |
| `─` | U+2500 | Mid-rule between sections |
| `▸` | U+25B8 | Bullet in header |
| `→` | U+2192 | Example arrow (replaces `==`-pattern in `ex` lines) |
| `≠` | U+2260 | Renders `!=` |
| `≤` | U+2264 | Renders `<=` |
| `≥` | U+2265 | Renders `>=` |

For terminals without unicode support, fall back to ASCII (`=`, `-`, `>`, `>`, `!=`, `<=`, `>=`).

## 6. Operator translation

Inside slot values (`ex`, `ens`, `req`, `prose`), the renderer substitutes:

| Wire | Display |
|---|---|
| `!=` | `≠` |
| `<=` | `≤` |
| `>=` | `≥` |
| `->` | `→` (in type signatures) |
| `==` (in `ex` between input and output) | `→` |

Inside the **body block** (between `do` and `end`), no substitution occurs. The body is rendered byte-for-byte from wire so copy-paste produces valid wire.

## 7. Round-trip example

### Wire

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

### Display

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

## 8. Trait-impl example

### Wire

```
fn render
vis appearing
for Display
eff pure
in u: User
out Html
ex render(User { name: "Mira", role: "engineer" }) == "<div>Mira (engineer)</div>"
do
return "<div>" + u.name + " (" + u.role + ")</div>"
end
```

### Display

```
═══════════════════════════════════════════════════════
  LAUDAS  ▸  vol I  ▸  render  —  answering Display
  appearing · pure
  ─────────────────────────────────────────────────────
  in    u : User
  out   Html

  ex    render(User { name: "Mira", role: "engineer" })
        →  "<div>Mira (engineer)</div>"
  ─────────────────────────────────────────────────────
  do
        return "<div>" + u.name + " (" + u.role + ")</div>"
═══════════════════════════════════════════════════════
```

## 9. Bidirectional rule

`mira parse(mira show(wire))` ≡ `wire` for every valid wire program. Display is a pure rendering, never a transformation that loses information. This means:

- Adding a slot to the wire format requires updating the display renderer.
- The display format never invents content not in the wire.
- Round-trip tests are a CI gate on `mira show`.

## 10. Implementation notes (v0)

- Renderer is a single Python function that takes parsed AST → string.
- ANSI color codes optional; default no-color for piping into `less` / files.
- The IDE plugin invokes `mira show` as a subprocess; no separate JS implementation needed in v0.
- Display format must wrap gracefully at terminal widths ≥80 cols. Long examples wrap onto continuation lines aligned to column 9 (the value column).

## 11. Future (post-v1)

- Themed display variants ("communication log" with stardate-style timestamps, "shipping manifest" with cargo metaphor, etc.) — opt-in.
- Color-by-effect: `pure` functions in green, `io` in yellow, `panics` in red.
- Inline visualization of `voronin` counterexamples as concrete input boxes.
- ASCII-only mode for legacy terminals.
