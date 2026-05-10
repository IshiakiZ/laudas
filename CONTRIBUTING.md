# Contributing to Laudas

Laudas is pre-alpha and the language design is still moving. The most valuable contributions right now are not pull requests — they're **carefully-written examples that expose limits or wrongness** in the current implementation.

## What helps most, in order

### 1. Bug reports with `.laud` repros

Open an issue with:

- A minimal `.laud` file that demonstrates the problem
- The output you got (`laudas <file>` and/or `laudas --show <file>`)
- The output you expected
- Your platform (Windows / macOS / Linux) and Python version

Bugs that come with a runnable repro get fixed first.

### 2. Examples for the synthetic corpus

The cold-start training-data problem is real (no LLM has been fine-tuned on Laudas yet). Hand-written example programs are gold. If you write a non-trivial `.laud` file that compiles and verifies cleanly, open a PR adding it to `examples/`. Bonus points for adversarial cases (deliberately broken examples to test the verifier's diagnostics).

### 3. Verifier limits

If you write a function that *should* verify but `voronin` reports `verifier limitation: …`, open an issue. The list of unsupported patterns is also the v0.5+ work queue.

### 4. Display-format edge cases

If `laudas --show` produces ugly output for some real-world function shape, open an issue with the wire input and the rendered output. The display spec ([display-spec.md](display-spec.md)) is the source of truth.

## What's not ready for PRs yet

- **Language semantics changes.** The PRD is the spec; semantic changes need an RFC, and the RFC process isn't formalized until post-Volume I.
- **Major refactors.** The Python implementation is the prototype; v1.0 plans a Rust rewrite. Don't refactor the Python version into a different architecture.
- **New keywords / slots.** Same reason — wait for the RFC process.

## Setup

```bash
git clone https://github.com/IshiakiZ/laudas
cd laudas
pip install -e .
laudas demo_fixed.laud   # smoke test
```

Z3 is the only non-pure-Python dependency. It comes from `z3-solver` on PyPI; pip handles it.

## Testing your changes

Before opening a PR, run the demos:

```bash
laudas demo_fixed.laud      # all checks pass
laudas demo_buggy.laud      # 2 failures expected (intentional)
laudas demo_v05.laud        # lists / lambdas / chains
laudas demo_extern.laud     # Python interop
laudas --show examples.laud # renders cleanly
```

If you broke any of those, fix it before submitting. If your change *intentionally* breaks them (e.g., changing a slot name), update the demos in the same PR.

## Code style

- Python implementation: follow PEP 8 within reason. Format with `black` if you have it.
- `.laud` files: slot order is fixed, slot lines have no leading indent, body uses braces for nested control flow.
- Docs: prose first, code examples second, tables for comparisons.

## Code of Conduct

Be kind. Specifically: critique designs and code, not people. Assume good faith. If a thread feels heated, take a day. Anyone who can't manage that doesn't belong here.

## Releasing (maintainers)

To cut a new version:

1. Bump `version` in `pyproject.toml`.
2. Add a changelog entry to `CHANGELOG.md`.
3. Commit + push to main.
4. `gh release create vX.Y.Z ./dist/laudas.exe --title "..." --notes "..."`.
5. Tag-push triggers `.github/workflows/publish.yml` which builds + publishes to PyPI via trusted publishing (no API tokens needed).

First-time PyPI setup:

1. Reserve the `laudas` name at https://pypi.org/manage/account/publishing/
2. Add a "trusted publisher" pointing at the IshiakiZ/laudas repo, environment-free, workflow `publish.yml`.
3. The next tagged push auto-publishes.

To rebuild the standalone binary:

```bash
pyinstaller --onefile --name laudas --hidden-import voronin --hidden-import anthropic --collect-all z3 --clean --noconfirm laudas.py
```

## License

By contributing, you agree your contributions are licensed under [Apache 2.0](LICENSE) (the project's license).

---

*Coriolis stands as the cautionary alternative — verification-as-administrative-violence. Laudas chooses the other path. So do its contributors.*
