# Laudas — VS Code extension

Syntax highlighting and language configuration for [Laudas](https://github.com/IshiakiZ/laudas) `.laud` files.

## Install

### From source (now)

```bash
cd vscode-laudas
npm install -g @vscode/vsce  # one-time
vsce package                  # produces laudas-0.1.0.vsix
code --install-extension laudas-0.1.0.vsix
```

### From the marketplace (when published)

Search for "Laudas" in VS Code's extension marketplace.

## What you get

- **Syntax highlighting** for the wire format
  - Slot keywords (`fn`, `vis`, `eff`, `in`, `out`, `ex`, `req`, `ens`, `prose`, `do`, `end`, `type`, `use`, `extern`)
  - Visibility values (`appearing`, `disappearing`, `answering`) as constants
  - Effect values (`pure`, `io`, `panics`, `nondet`, `fails`)
  - Variant constructors (`Some`, `None`, `Ok`, `Err`)
  - Type names (TitleCased identifiers + `int`, `bool`, `str`, `list`, `option`, `result`)
  - Booleans, numbers, strings (with `\n` / `\t` / `\"` / `\\` escapes)
  - Comments (`;` to end of line)
  - Operators (`==`, `!=`, `<=`, `>=`, `<`, `>`, `+`, `-`, `*`, `/`, `%`, `&&`, `||`, `->`)

- **Language configuration**
  - Auto-closing pairs for `{}`, `[]`, `()`, `""`
  - Bracket matching
  - Indentation rules: `do` and `{` open a block; `end` and `}` close it
  - Line comment via `Ctrl+/` inserts `;`

## What's not here yet

- **Language Server Protocol integration** — see [`../lsp_server.py`](../lsp_server.py). When wired in, you'll get inline error squiggles from `voronin` and hover docs.
- **Tree-sitter-based parsing** — see [`../tree-sitter-laudas/`](../tree-sitter-laudas/). The TextMate grammar in this extension is a regex-based approximation; tree-sitter would give exact parse-tree-based highlighting.
- **Snippets** — boilerplate templates for `fn`, `type`, `extern python`, etc.

PRs welcome on [github.com/IshiakiZ/laudas](https://github.com/IshiakiZ/laudas).

## Files

```
vscode-laudas/
├── package.json                          extension manifest
├── language-configuration.json           brackets, comments, indentation
├── syntaxes/laudas.tmLanguage.json       TextMate grammar
└── README.md                             this file
```

Apache-2.0.
