import tiktoken, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load tokenizers
enc_cl100k = tiktoken.get_encoding("cl100k_base")  # GPT-4, GPT-3.5
enc_o200k = tiktoken.get_encoding("o200k_base")    # GPT-4o, o1, o3
encs = [("cl100k", enc_cl100k), ("o200k", enc_o200k)]

# Test groups
two_letter = ["fn", "in", "do", "if", "is", "as", "on", "of", "to", "by", "no", "ex", "op"]
three_letter = ["out", "end", "req", "ens", "eff", "vis", "fmt", "has", "get", "let", "var", "the", "all", "any"]
four_letter = ["pure", "read", "when", "then", "else", "none", "some", "with", "this", "that"]
five_letter = ["where", "while", "retry", "panic"]
sigils = ["@", "$", "#", "%", "->", "=>", "==", "!=", "::", "|>", "↦", "→"]
bigrams_at = ["@f", "@i", "@e", "@d", "@x"]
bigrams_other = ["$x", "#f", "%v"]

def show(name, tokens):
    rows = []
    for tok in tokens:
        row = [tok]
        for ename, enc in encs:
            ids = enc.encode(tok)
            row.append(len(ids))
            row.append(repr(ids))
        rows.append(row)
    print(f"\n=== {name} ===")
    print(f"{'token':<10} {'cl100k_n':<10} {'cl100k_ids':<25} {'o200k_n':<10} {'o200k_ids':<25}")
    for r in rows:
        print(f"{r[0]:<10} {r[1]:<10} {r[2]:<25} {r[3]:<10} {r[4]:<25}")

show("2-letter (raw)", two_letter)
show("3-letter (raw)", three_letter)
show("4-letter (raw)", four_letter)
show("5-letter (raw)", five_letter)
show("sigils", sigils)
show("@-bigrams", bigrams_at)
show("other bigrams", bigrams_other)

# Leading-space variants — critical for BPE
print("\n\n========== LEADING SPACE VARIANTS ==========")
ls2 = [" " + w for w in two_letter]
ls3 = [" " + w for w in three_letter]
ls4 = [" " + w for w in four_letter]
ls5 = [" " + w for w in five_letter]
show("2-letter ' word'", ls2)
show("3-letter ' word'", ls3)
show("4-letter ' word'", ls4)
show("5-letter ' word'", ls5)

# Two leading spaces
print("\n\n========== TWO LEADING SPACES ==========")
ts2 = ["  " + w for w in two_letter]
ts3 = ["  " + w for w in three_letter]
show("2-letter '  word'", ts2)
show("3-letter '  word'", ts3)

# Tab-prefixed
print("\n\n========== TAB-PREFIXED ==========")
tp2 = ["\t" + w for w in two_letter]
tp3 = ["\t" + w for w in three_letter]
show("2-letter '\\tword'", tp2)
show("3-letter '\\tword'", tp3)

# Newline + word (start of new line, common in code)
print("\n\n========== NEWLINE + WORD ==========")
nl3 = ["\n" + w for w in three_letter[:8]]
show("3-letter '\\nword'", nl3)
