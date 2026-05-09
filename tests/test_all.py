"""
Laudas — full test sweep.

Runs the toolchain (`laudas FILE.laud`) over every demo / tutorial / corpus
seed in the repo. Files that should pass return exit code 0; the
intentionally-broken `demo_buggy.laud` should return non-zero.

Used by .github/workflows/ci.yml. Also runnable locally:

    python tests/test_all.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Force UTF-8 stdout so unicode (✓ ✗) renders on Windows cp1252 consoles.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


REPO = Path(__file__).resolve().parent.parent
LAUDAS = [sys.executable, str(REPO / "laudas.py")]


# Paths relative to REPO that should `laudas FILE` exit 0 on.
PASS_FILES = [
    "demo_fixed.laud",
    "demo_v05.laud",
    "demo_extern.laud",
    "demo_records.laud",
    "demo_stdlib.laud",
    "demo_let_verify.laud",
    "demo_use_main.laud",
    "demo_record_verify.laud",
    "demo_fold.laud",
    "demo_hello.laud",
    "demo_greet.laud",
    "examples/csv2json.laud",
    "examples/wc.laud",
    "examples/sort.laud",
    "examples/json_pretty.laud",
    "demo_string_verify.laud",
    "examples/head.laud",
    "examples/tail.laud",
    "examples/uniq.laud",
    "examples/bars.laud",
    "demo_bool_predicate.laud",
    "demo_list_verify.laud",
    "demo_filter_map_verify.laud",
    "demo_contains_verify.laud",
    "examples/stats.laud",
    "examples/word_freq.laud",
    "examples/grep.laud",
    "examples/cat.laud",
    "examples/calc_rpn.laud",
    "examples/minesweeper.laud",
    "tutorial/07_modules.laud",
    "tutorial/08_ffi.laud",
]

# Intentionally-broken demos that MUST fail (CI flags it as a regression
# if these start passing).
FAIL_FILES = [
    "demo_buggy.laud",
    "demo_cex_format.laud",  # intentionally trips voronin to demo prettified counterexamples
]

# Files where the verifier MUST report at least one `ver ✓` line. Catches
# silent regressions where voronin starts skipping things it used to verify
# (e.g. the __main__-vs-laudas-module TYPE_ALIASES bug fixed in ca62665).
MUST_VERIFY_FILES = [
    "demo_fixed.laud",            # ens result.is_some() iff b != 0
    "demo_let_verify.laud",       # ens result <= 100, with let-bindings
    "demo_record_verify.laud",    # ens result >= 0 over record fields
    "demo_string_verify.laud",    # ens over s.length(), s.upper().length()
    "demo_bool_predicate.laud",   # bool-returning predicates over records
    "demo_list_verify.laud",      # ens over list<T>.length() (Z3 Seq sort)
    "demo_filter_map_verify.laud",# ens over filter/map length-bounds
    "demo_contains_verify.laud",  # ens over .contains() on str + list
    "tutorial/03_verifier.laud",  # the tutorial step that introduces ens
]


def discover() -> tuple[list[str], list[str]]:
    pass_files = list(PASS_FILES)
    pass_files.extend(str(p.relative_to(REPO).as_posix()) for p in (REPO / "tutorial").glob("*.laud"))
    pass_files.extend(str(p.relative_to(REPO).as_posix()) for p in (REPO / "synthesis" / "corpus" / "seed").glob("*.laud"))
    return pass_files, FAIL_FILES


def run(file_rel: str) -> tuple[int, str]:
    result = subprocess.run(
        LAUDAS + [file_rel],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def main() -> int:
    pass_files, fail_files = discover()
    failures: list[str] = []

    print(f"  laudas test sweep  ·  {len(pass_files)} expected-pass + {len(fail_files)} expected-fail")
    print()

    for f in pass_files:
        code, output = run(f)
        if code == 0:
            # If this file is on the must-verify list, also check that
            # at least one `ver ✓` line appears — catches silent skips.
            if f in MUST_VERIFY_FILES and "ver  ✓" not in output:
                print(f"  ✗  {f}  (exit 0 but no `ver ✓` — verifier silently skipped)")
                print("     ---")
                for line in output.splitlines()[-15:]:
                    print(f"     {line}")
                print("     ---")
                failures.append(f"{f} (silent verifier skip)")
            else:
                print(f"  ✓  {f}")
        else:
            print(f"  ✗  {f}  (exit {code})")
            print("     ---")
            for line in output.splitlines()[-15:]:
                print(f"     {line}")
            print("     ---")
            failures.append(f)

    for f in fail_files:
        code, output = run(f)
        if code != 0:
            print(f"  ✓  {f}  (failed as expected, exit {code})")
        else:
            print(f"  ✗  {f}  (expected non-zero exit, got 0)")
            failures.append(f"{f} should have failed")

    print()
    if failures:
        print(f"  {len(failures)} failure(s):")
        for f in failures:
            print(f"    - {f}")
        return 1

    total = len(pass_files) + len(fail_files)
    print(f"  all {total} files behaved as expected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
