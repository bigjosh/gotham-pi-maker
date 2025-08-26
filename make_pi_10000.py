#!/usr/bin/env python3
"""
Extract the first 10,000 digits from pi-billion.txt and write them
as 100 lines of 100 digits to pi-10000.txt.

Streaming, stops as soon as 10,000 digits are collected.
"""
from __future__ import annotations

import os

def main():
    src = os.path.join(os.path.dirname(__file__), "pi-billion.txt")
    dst = os.path.join(os.path.dirname(__file__), "pi-10000.txt")

    target = 10000
    per_line = 100

    digits = []
    got = 0

    with open(src, "r", encoding="utf-8", newline="") as f:


        for line in f:
            for ch in line:
                digits.append(ch)
                got += 1
                if got >= target:
                    break
            if got >= target:
                break

    if got < target:
        raise SystemExit(f"Only found {got} digits in {src}, need {target}.")

    with open(dst, "w", encoding="utf-8", newline="\n") as out:
        row_index = 0
        for i in range(0, target, per_line):
            # Build one row of 100 digits with a 3-space gap after every 10 digits
            row_parts = []
            for j in range(0, per_line, 10):
                row_parts.append("".join(digits[i + j:i + j + 10]))
                row_parts.append("   ")  # 3-space gap after each block of 10
            out.write("".join(row_parts))
            out.write("\n")
            row_index += 1
            # After every 10 rows, add a vertical blank line
            if row_index % 10 == 0:
                out.write("\n")

    print(f"Wrote {dst} with {target} digits as {target//per_line} lines of {per_line}.")

if __name__ == "__main__":
    main()
