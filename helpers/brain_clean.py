import re

# Load, cap counts, and clean control tokens
cleaned_lines = []

with open("brain_file.txt", "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        
        parts = re.split(r"\t+|\s{2,}", line)
        if parts[0].isdigit():
            count = int(parts[0])
            
            # Cap exaggerated counts to a reasonable maximum (e.g., 50)
            capped_count = min(count, 50)
            
            # Skip IRC control codes like ^B
            rest = "\t".join(parts[1:])
            if "^B" in rest or "\x02" in rest:
                continue
                
            cleaned_lines.append(f"{capped_count}\t{rest}\n")

# Write back out to cleaned file
with open("brain_file_clean.txt", "w", encoding="utf-8") as f:
    f.writelines(cleaned_lines)

print("Brain file sanitized and saved to brain_file_clean.txt!")
