#!/usr/bin/env python3
import os
import re
from collections import defaultdict


def parse_brain_line(raw):
    raw = raw.strip()
    if not raw:
        return None

    parts = re.split(r"\t+|\s{2,}", raw)
    if not parts[0].isdigit():
        return None

    count = int(parts[0])
    rest = parts[1:]

    # Ignore control character noise like ^B
    joined_rest = " ".join(rest)
    if "^B" in joined_rest or "\x02" in joined_rest:
        return None

    # Key represents the context + next_word structure
    key = "\t".join(rest)
    return count, key


def repair_brain(bak_path="brain_file.bak", main_path="brain_file.txt", out_path="brain_file_repaired.txt"):
    if not os.path.exists(bak_path):
        print(f"Error: Could not find backup file '{bak_path}'!")
        return

    if not os.path.exists(main_path):
        print(f"Error: Could not find current file '{main_path}'!")
        return

    brain_counts = defaultdict(int)

    # 1. Load clean baseline counts from backup
    bak_entries = 0
    with open(bak_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parsed = parse_brain_line(line)
            if parsed:
                count, key = parsed
                brain_counts[key] = count
                bak_entries += 1

    print(f"Loaded {bak_entries} clean entries from '{bak_path}'.")

    # 2. Add new entries from current brain file (incrementing safely)
    new_entries = 0
    with open(main_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parsed = parse_brain_line(line)
            if parsed:
                count, key = parsed
                # If key was not in backup, it's new learned chatter
                if key not in brain_counts:
                    # Cap initial weight for new chatter so it matches natural scale
                    brain_counts[key] = min(count, 5)
                    new_entries += 1

    print(f"Merged {new_entries} new entries from current '{main_path}'.")

    # 3. Write out repaired brain file
    with open(out_path, "w", encoding="utf-8") as f:
        for key, count in brain_counts.items():
            f.write(f"{count}\t{key}\n")

    print(f"\nRepaired brain written to '{out_path}'.")
    print(f"To use it:")
    print(f"  1. Stop your bot")
    print(f"  2. mv {out_path} {main_path}")
    print(f"  3. Restart your bot")


if __name__ == "__main__":
    repair_brain()
