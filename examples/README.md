# Laudas — example tools

Six small CLI tools written in Laudas, ranging from "trivially short" to "I'd actually pipe a file through this." All work the same way: install Laudas, then `laudas run examples/TOOL.laud [ARGS...]`.

These are **real**, not toys. They use real Python under the hood for things Laudas can't do natively (JSON parsing, file I/O), and verify the parts that matter (the parsers, the validators) via voronin.

## The toolkit

| Tool | Lines | What it does | Example |
|---|---|---|---|
| [`csv2json.laud`](csv2json.laud) | 22 | CSV → JSON | `cat crew.csv \| laudas run csv2json.laud` |
| [`wc.laud`](wc.laud) | 21 | lines / words / chars from stdin | `cat file \| laudas run wc.laud` |
| [`sort.laud`](sort.laud) | 8 | alphabetical sort of stdin lines | `cat lines \| laudas run sort.laud` |
| [`head.laud`](head.laud) | 23 | first N lines (default 10) | `cat file \| laudas run head.laud 5` |
| [`tail.laud`](tail.laud) | 23 | last N lines (default 10) | `cat file \| laudas run tail.laud 5` |
| [`uniq.laud`](uniq.laud) | 11 | drop duplicate lines (preserves first) | `cat file \| laudas run uniq.laud` |
| [`json_pretty.laud`](json_pretty.laud) | 22 | indent JSON via Python's json.loads | `echo '{"a":1}' \| laudas run json_pretty.laud` |

## They compose

The same Unix-pipe model:

```powershell
# Get the unique crew roles, sorted
Get-Content crew.csv |
  laudas run examples/csv2json.laud |
  laudas run examples/json_pretty.laud
```

Each tool takes stdin, transforms it, writes stdout. Each does one thing well.

## What's verified vs. just executed

When you run `laudas examples/TOOL.laud` (no `run` subcommand), Laudas only **verifies** the file's spec — it runs `ex` examples on the pure helper functions, checks any `ens` postconditions via Z3, and reports skip-with-reason for anything voronin can't symbolically execute.

When you run `laudas run examples/TOOL.laud`, Laudas **executes** `main`, calling its body with the CLI args.

The two coexist on the same file:

- `csv2json.laud`'s `parse_row` carries `ex` slots → verified
- `csv2json.laud`'s `main` is impure (eff io) → executed only

## Sample data

[`crew.csv`](crew.csv) is the test fixture for `csv2json.laud`. Tiny, three rows, useful for piping into the tools:

```
Get-Content examples/crew.csv | laudas run examples/wc.laud
lines: 4
words: 4
chars: 92
```

## Adding your own

Drop a new `.laud` in this directory. If it has a `fn main`, it's runnable via `laudas run`. If it has functions with `ex` slots, those get verified by `laudas FILE`. If it has `ens` postconditions, Z3 attempts to prove them.

Add the file to `tests/test_all.py` `PASS_FILES` so CI checks it stays green.

If your tool is generally useful, [open a PR](https://github.com/IshiakiZ/laudas/pulls).
