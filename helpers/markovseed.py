#!/usr/bin/env python3
"""
Seed a Markov brain file from a text file.

Usage:
    python3 seed_brain.py input.txt brain_file.txt [--order 2] [--append]

Examples:
    python3 seed_brain.py chatlog.txt brain_file.txt
    python3 seed_brain.py old_logs/*.txt brain_file.txt --append
"""

import argparse
import collections
import glob
import os
import re
import sys

START = "\x02"
END = "\x03"

# Matches IRC status lines like:
#   Nickname  ^`^t 18/09/2026, 00:02
#   Nick1 [HELLO],   ^`^t 18/09/2026, 10:44
# Anything ending in "DD/MM/YYYY, HH:MM" preceded by non-alphanumeric junk.
STATUS_RE = re.compile(
    r"^.+?[^a-zA-Z0-9]+\d{2}/\d{2}/\d{4},?\s+\d{2}:\d{2}\s*$"
)


def tokenize(line):
    """Strip IRC formatting codes and common log prefixes; return word list."""
    # IRC bold/color/etc. codes
    line = re.sub(r"\x02|\x1d|\x1f|\x16|\x0f|\x03\d{0,2}(,\d{1,2})?", "", line)
    line = line.strip()
    if not line:
        return []
    # "<nick> message" or "nick: message" prefixes from chat logs
    line = re.sub(r"^<[^>]+>\s*", "", line)
    line = re.sub(r"^\[?\d{1,2}[:./]\d{2}(?::\d{2})?\]?\s*", "", line)  # timestamps
    line = re.sub(r"^\w{1,32}:\s+", "", line)                            # "nick: msg"
    return line.split()


def learn(chain, words, order, count=1):
    if len(words) < order + 1:
        return
    padded = [START] * order + words + [END]
    for i in range(len(padded) - order):
        key = tuple(padded[i:i + order])
        chain[key][padded[i + order]] += count


def load_existing(chain, path, order):
    """Merge an existing chain dump into the model, if present."""
    if not os.path.exists(path):
        return False
    merged = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            parts = raw.rstrip("\n").split("\t")
            if len(parts) >= 3 and parts[0].isdigit():
                count = int(parts[0])
                words = parts[1].split(" ") + [parts[2]]
                learn(chain, words, order, count)
                merged += 1
    return merged > 0


def main():
    p = argparse.ArgumentParser(description="Build brain_file.txt from text files")
    p.add_argument("inputs", nargs="+", help="input text file(s), globs ok")
    p.add_argument("output", help="brain_file.txt to write")
    p.add_argument("--order", type=int, default=2)
    p.add_argument("--append", action="store_true",
                   help="merge with existing output instead of overwriting")
    args = p.parse_args()

    order = max(1, args.order)
    chain = collections.defaultdict(collections.Counter)

    if args.append and load_existing(chain, args.output, order):
        print(f"[info] merged existing {args.output}")

    files = []
    for pattern in args.inputs:
        matched = glob.glob(pattern)
        files.extend(matched if matched else [pattern])

    lines_read = tokens_learned = skipped_status = 0
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    lines_read += 1
                    if STATUS_RE.match(line):
                        skipped_status += 1
                        continue
                    words = tokenize(line)
                    if len(words) >= order + 1:
                        tokens_learned += len(words)
                        learn(chain, words, order)
        except OSError as exc:
            print(f"[warn] skipping {path}: {exc}", file=sys.stderr)

    tmp = args.output + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for key, counter in chain.items():
            ctx = " ".join(key)
            for word, count in counter.items():
                f.write(f"{count}\t{ctx}\t{word}\n")
    os.replace(tmp, args.output)

    n_keys = len(chain)
    print(f"[done] {lines_read} lines -> {tokens_learned} tokens, "
          f"{n_keys} contexts written to {args.output}")
    if skipped_status:
        print(f"[info] skipped {skipped_status} status lines")


if __name__ == "__main__":
    main()
