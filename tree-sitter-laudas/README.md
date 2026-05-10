# tree-sitter-laudas

[Tree-sitter](https://tree-sitter.github.io/tree-sitter/) grammar for the [Laudas](https://github.com/IshiakiZ/laudas) programming language.

## Why tree-sitter

The TextMate grammar in [`../vscode-laudas/`](../vscode-laudas/) is a regex-based approximation. Tree-sitter parses the actual structure, which gives:

- Exact syntax highlighting (no regex false positives)
- Code folding by structural unit
- Indent-aware editing
- Symbol outline (function list in the IDE sidebar)
- Foundation for code-folding, structural search, and refactoring

## Build

```bash
npm install
npx tree-sitter generate    # produces parser.c from grammar.js
npx tree-sitter test         # runs tests if ./test/ exists
```

The generated `parser.c` is what editors load. Tree-sitter has bindings for:

- **Neovim** via `nvim-treesitter` plugin
- **Helix** via languages.toml entry
- **VS Code** via the `vscode-tree-sitter` runtime (still maturing)
- **Emacs** via `treesit` (Emacs 29+)
- **Atom** historically; deprecated

## What the grammar covers

Mirrors `laudas.py`'s `parse_file`:

- Top-level: `use "PATH"`, `type NAME { fields }`, `fn NAME ... do ... end`
- Function slots: `vis`, `for`, `eff`, `in`, `out`, `ex`, `req`, `ens`, `prose`
- Body: `let`, `if { ... } else { ... }`, `return`, expression statements
- Expressions: lambdas (single + multi-arg), binary ops with precedence, method chains, field access, list literals, record literals, function calls, parenthesized
- Atoms: primitive types, refined types (`int { > 0 }`), generic types (`list<T>`), option types (`int?`), strings with escapes, numbers, booleans, identifiers

## What's not yet here

- Tests in `./test/` (corpus + expected parse trees) — would lock in expected output for known inputs
- `bindings/node/` — Node.js bindings for use from JS
- `bindings/rust/` — Rust bindings
- A `queries/highlights.scm` — Tree-sitter highlight queries; tells editors what colors to apply to which captures

## Status

This is a working grammar. To turn it into an installable parser, run `npx tree-sitter generate`. The output (`parser.c`, `bindings/`) are normally checked in for distribution; we don't commit them yet because the language design is still moving.

PRs welcome on [github.com/IshiakiZ/laudas](https://github.com/IshiakiZ/laudas).
