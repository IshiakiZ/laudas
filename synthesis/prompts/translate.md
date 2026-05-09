# Python → Laudas translation prompt

This is the prompt template `synthesis/generate.py` sends to Claude. Tweak it here, not in the code, so prompt iterations are visible in git history.

The current prompt lives in `generate.py` as `PROMPT_TEMPLATE`. Sync any changes you make here back to that constant. (When the synthesis pipeline matures, we'll load this file directly — for now, it's documentation of intent.)

## Goals

- The translation should be **idiomatic Laudas**, not a 1:1 transliteration.
- Add `ex` slots derived from the Python's docstrings, doctests, or visible call sites.
- Add `ens` postconditions when the Python has `assert` statements or visible invariants.
- Use `eff pure` unless the function does I/O — in which case `eff io` (with `fails: ...` if it raises).
- Prefer module-qualified stdlib (`text.split`, `arith.min`) over `extern python` when both exist.
- Use `extern python "module.func"` only when no Laudas-native equivalent exists.

## Anti-goals

- Don't invent specs the Python doesn't suggest. If the Python is unspecified, leave the spec slots empty (just `do` and `end`).
- Don't use language features outside the v0.5 subset (no closures over multiple args, no early-return outside `if`, no while loops).
- Don't add `prose` slots unless the Python has a meaningful docstring.

## Iteration log

Track prompt-quality iterations here. Each entry should note: what changed, what improved, what regressed.

### v1 — initial (2026-05-09)

Starting prompt. Includes full slot grammar + body language reference + module-qualified stdlib examples. Untested at scale.
