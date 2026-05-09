# Laudas — synthesis pipeline

The cold-start training-data problem: no LLM has been fine-tuned on Laudas, so off-the-shelf models can't generate it well from scratch. This directory holds the tooling to **fix that** before Volume I.

The plan is in three parts:

1. **Hand-written seed corpus** — examples in `corpus/` that compile and verify cleanly. The seeds are quality > quantity. Target: ~500 by Volume I.
2. **Synthetic generator** — `generate.py` translates Python programs into Laudas using Claude, then runs `voronin` to confirm the result is correct. Verified outputs go into `corpus/synthetic/`.
3. **Fine-tune a Laudas-fluent open model** — once the corpus is large enough (~10K verified examples), fine-tune an open Llama / Qwen / Mistral checkpoint and publish the weights. People who don't want to call Anthropic for every Laudas edit get an offline option.

## Layout

```
synthesis/
├── README.md           this file
├── generate.py         Python → Laudas translator (calls Claude, verifies via voronin)
├── corpus/
│   ├── seed/           hand-written examples (commit these)
│   └── synthetic/      generated + verified examples (commit these too — they're the dataset)
└── prompts/            prompt templates for Claude
    └── translate.md    Python → Laudas translation prompt
```

## Workflow

### Adding a hand-written seed

1. Write a `.laud` file in `corpus/seed/`. Should be:
   - Self-contained (no `use` of files outside `corpus/`)
   - At least one `ex` per function
   - At least one function with non-trivial `ens` if possible
2. `laudas corpus/seed/your_file.laud` — must show all green
3. Commit it

### Generating synthetic examples (requires `ANTHROPIC_API_KEY`)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python synthesis/generate.py --input some_python_file.py --output corpus/synthetic/some_file.laud
```

The script:
1. Reads the Python source
2. Asks Claude to translate it to Laudas (using `prompts/translate.md`)
3. Runs `laudas` on the result
4. If verification passes, writes to `--output`. Otherwise discards and reports the diagnostic.

Verified outputs go into the dataset. Failures get logged to `synthesis/failures.log` so they can be retried with prompt tweaks.

### Bulk generation

```bash
python synthesis/generate.py --bulk path/to/python/repo --output-dir corpus/synthetic/
```

Walks the directory, translates each `.py` file, keeps verified outputs.

## Fine-tuning (Volume I scope)

Once `corpus/` has ≥10K verified examples:

1. Convert to a fine-tuning JSONL format (input prompt + output Laudas)
2. Fine-tune an open base model — Qwen 2.5 7B is a reasonable starting point
3. Evaluate on a held-out test set:
   - Pass rate of `laudas FILE.filled.laud` after the model fills `do` blocks
   - Match against compression-target.md on a handful of held-out tasks
4. Publish weights on Hugging Face under Apache 2.0

## Status

- [ ] `generate.py` — initial template (this commit)
- [ ] `prompts/translate.md` — initial prompt (this commit)
- [ ] `corpus/seed/` — first 5 hand-written examples (this commit)
- [ ] First batch of synthetic examples
- [ ] 100 verified examples
- [ ] 1K verified examples
- [ ] 10K verified examples
- [ ] First fine-tuned Laudas-fluent model

## Why we keep the dataset in-repo

It's tempting to put a 100K-example corpus in S3 and link to it. Two reasons not to:

1. **Reproducibility.** The dataset is part of the language's specification by example. It should be versioned alongside the spec.
2. **Trust.** If a model is fine-tuned on a corpus, the corpus needs to be auditable. In-repo means anyone can search it for issues, leaks, biases.

When the corpus exceeds ~100 MB, we'll split into a `laudas-corpus` repo as a git submodule. Until then, it stays here.
