"""
Laudas synthesis — Python → Laudas translation pipeline.

Reads a Python source file, asks Claude to translate it to Laudas, runs
`laudas` to verify the result, and writes the verified Laudas to the
output path. Discards anything that doesn't verify; logs failures.

Requires ANTHROPIC_API_KEY in the environment.

Usage:
    python synthesis/generate.py --input src.py --output corpus/synthetic/out.laud
    python synthesis/generate.py --bulk repo/ --output-dir corpus/synthetic/
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROMPT_TEMPLATE = """You are translating a Python program into Laudas, a verification-first programming language.

Wire-format slot grammar:
- `fn NAME` — function name
- `vis appearing|disappearing` — visibility
- `eff pure|io|panics|nondet|...` — effect list
- `for INTERFACE` — optional, if implementing a trait
- `in NAME: TYPE` — input parameter (one per line)
- `out TYPE` — output type
- `ex EXAMPLE` — concrete example: `funcname(args) == expected`
- `req PRECOND` — precondition
- `ens POSTCOND` — postcondition over `result` and parameters
- `prose "..."` — natural-language contract
- `do` ... body lines ... `end`

Body language:
- Statements: `let NAME = EXPR`, `if EXPR {{ STMT }}`, `return EXPR`
- Expressions: int arithmetic, comparisons, `&&`, `||`, `Some(x)`, `None`, lists `[a, b]`, lambdas `x -> EXPR`, method chains `xs.filter(...).map(...)`
- Module calls: `text.split(s, sep)`, `arith.min(a, b)`, `ledger.range(n)`, `text.to_json(v)`, etc.
- Field access on records: `record.field`
- Records: `type Name {{ f: T, g: T2 }}` then `Name {{ f: ..., g: ... }}`
- Foreign Python: `extern python "module.func"` (use sparingly — only when no Laudas-native equivalent exists)

Translate the following Python program to Laudas. Preserve behavior. Add `ex` examples derived from the Python's docstrings or test cases. Add `ens` postconditions where the Python has assertions or invariants. Use `eff pure` unless the function does I/O.

Output ONLY the Laudas source, no prose, no markdown fences.

Python source:
```python
{python_source}
```"""


def translate_one(python_source: str, model: str = "claude-sonnet-4-5") -> str:
    """Send `python_source` to Claude, return the suggested Laudas source."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic SDK not installed; run `pip install anthropic`")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(python_source=python_source)}],
    )
    text = response.content[0].text

    # Strip markdown fences if Claude added them
    lines = text.split("\n")
    out: list[str] = []
    in_fence = False
    for line in lines:
        s = line.rstrip()
        if s.strip().startswith("```"):
            in_fence = not in_fence
            continue
        out.append(s)
    return "\n".join(out)


def verify(laud_path: Path) -> tuple[bool, str]:
    """Run `laudas FILE.laud` and return (passed, output)."""
    repo_root = Path(__file__).resolve().parent.parent
    laudas_py = repo_root / "laudas.py"
    result = subprocess.run(
        [sys.executable, str(laudas_py), str(laud_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output


def process_one(python_path: Path, output_path: Path, failures_log: Path | None) -> bool:
    print(f"  ▸  {python_path.name}  →  {output_path.name}")
    python_source = python_path.read_text(encoding="utf-8")
    try:
        laudas_source = translate_one(python_source)
    except Exception as e:
        print(f"     ✗ translation failed: {e}")
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(laudas_source, encoding="utf-8")

    passed, log = verify(output_path)
    if passed:
        print(f"     ✓ verified")
        return True

    print(f"     ✗ verification failed — discarding")
    if failures_log is not None:
        with failures_log.open("a", encoding="utf-8") as f:
            f.write(f"\n=== {python_path} → {output_path} ===\n")
            f.write(laudas_source)
            f.write("\n--- verifier output ---\n")
            f.write(log)
            f.write("\n")
    output_path.unlink(missing_ok=True)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="single Python file to translate")
    parser.add_argument("--output", help="output .laud path (used with --input)")
    parser.add_argument("--bulk", help="directory of Python files to translate")
    parser.add_argument("--output-dir", help="output directory (used with --bulk)")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    failures_log = repo_root / "synthesis" / "failures.log"

    if args.input:
        if not args.output:
            print("error: --output required when --input is used", file=sys.stderr)
            return 64
        ok = process_one(Path(args.input), Path(args.output), failures_log)
        return 0 if ok else 1

    if args.bulk:
        if not args.output_dir:
            print("error: --output-dir required when --bulk is used", file=sys.stderr)
            return 64
        in_dir = Path(args.bulk)
        out_dir = Path(args.output_dir)
        py_files = list(in_dir.rglob("*.py"))
        if not py_files:
            print(f"  no .py files under {in_dir}")
            return 0
        print(f"  laudas synthesis  ·  {len(py_files)} python file(s) to translate")
        passed = 0
        for py in py_files:
            rel = py.relative_to(in_dir).with_suffix(".laud")
            if process_one(py, out_dir / rel, failures_log):
                passed += 1
        print()
        print(f"  {passed}/{len(py_files)} verified  ·  see {failures_log.name} for failures")
        return 0 if passed == len(py_files) else 1

    parser.print_help()
    return 64


if __name__ == "__main__":
    sys.exit(main())
