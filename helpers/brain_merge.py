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

    # Filter out control characters like ^B
    joined_rest = " ".join(rest)
    if "^B" in joined_rest or "\x02" in joined_rest:
        return None

    key = "\t".join(rest)
    return count, key


def merge_brains():
    bak_path = "brain_file.bak"
    tmp_path = "brain_file_tmp.txt"
    main_path = "brain_file.txt"
    out_path = "brain_file_repaired.txt"

    brain_counts = defaultdict(int)

    # Step 1: Load baseline counts from clean backup
    if os.path.exists(bak_path):
        bak_entries = 0
        with open(bak_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                parsed = parse_brain_line(line)
                if parsed:
                    count, key = parsed
                    brain_counts[key] = count
                    bak_entries += 1
        print(f"[1/3] Loaded {bak_entries} baseline entries from '{bak_path}'.")
        
        # Keep track of original keys to safely identify what's genuinely new
        original_keys = set(brain_counts.keys())
    else:
        print(f"Warning: Backup '{bak_path}' not found! Starting with empty baseline.")
        original_keys = set()

    # Step 2: Merge new entries from brain_file_tmp.txt
    if os.path.exists(tmp_path):
        tmp_new = 0
        with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                parsed = parse_brain_line(line)
                if parsed:
                    count, key = parsed
                    if key not in original_keys:
                        # Add new key with capped weight (max 5)
                        brain_counts[key] = min(count, 5)
                        original_keys.add(key)
                        tmp_new += 1
        print(f"[2/3] Merged {tmp_new} new entries from '{tmp_path}'.")
    else:
        print(f"[2/3] '{tmp_path}' not found. Skipping.")

    # Step 3: Merge new entries from current brain_file.txt
    if os.path.exists(main_path):
        main_new = 0
        with open(main_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                parsed = parse_brain_line(line)
                if parsed:
                    count, key = parsed
                    if key not in original_keys:
                        brain_counts[key] = min(count, 5)
                        original_keys.add(key)
                        main_new += 1
        print(f"[3/3] Merged {main_new} new entries from '{main_path}'.")
    else:
        print(f"[3/3] '{main_path}' not found. Skipping.")

    # Step 4: Write merged output
    with open(out_path, "w", encoding="utf-8") as f:
        for key, count in brain_counts.items():
            f.write(f"{count}\t{key}\n")

    print(f"\nSuccessfully combined all sources into '{out_path}'!")


if __name__ == "__main__":
    merge_brains()
