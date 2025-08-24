#!/usr/bin/env python3
"""
density_ones.py

Reads a bit-packed binary file (from bitpack_ones.py) and computes the density
of 1s. The file uses MSB-first packing with zero-padding in the final byte.

Usage examples:
  # If you know the original text file used to create the bin
  python density_ones.py --input pi-billion.ones.bin --original-input pi-billion.txt

  # Or provide the exact count of valid bits (original byte count)
  python density_ones.py --input pi-billion.ones.bin --valid-bits 1000000000

  # Minimal usage (treats all bits in file as valid; OK when no padding)
  python density_ones.py --input pi-billion.ones.bin

Outputs a brief report to stdout. Use --quiet to print only the density value.

Notes:
- Padding bits, if any, are zeros at the LSB side of the final byte in the file.
- When --original-input or --valid-bits is provided, density is computed as
  ones_count / valid_bits. Since padding bits are zeros, no adjustment to the
  ones count is required.
- Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import BinaryIO, Tuple

DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024  # 4 MiB

# Precompute popcount for 0..255
POPCOUNT = bytes([bin(i).count("1") for i in range(256)])


def count_ones_stream(fp: BinaryIO, chunk_size: int = DEFAULT_CHUNK_SIZE) -> Tuple[int, int]:
    """Return (total_bytes_read, ones_count) by streaming through the file."""
    total_bytes = 0
    ones = 0
    mv = memoryview(POPCOUNT)

    while True:
        chunk = fp.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        # Sum popcounts
        # Convert each byte to an index into POPCOUNT; using sum over mv[b]
        ones += sum(mv[b] for b in chunk)

    return total_bytes, ones


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compute density of 1s in bit-packed file")
    p.add_argument("--input", "-i", required=True, help="Path to bit-packed binary file")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--original-input", "-I", help="Path to original input file to infer valid bit count")
    g.add_argument("--valid-bits", "-b", type=int, help="Exact number of valid bits (original bytes)")
    p.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE, help=f"Read chunk size (default {DEFAULT_CHUNK_SIZE})")
    p.add_argument("--quiet", "-q", action="store_true", help="Print only the density as a float")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    in_path = args.input
    if not os.path.exists(in_path):
        print(f"Input file not found: {in_path}", file=sys.stderr)
        return 1

    try:
        with open(in_path, "rb") as f:
            total_bytes, ones = count_ones_stream(f, chunk_size=args.chunk_size)
    except OSError as e:
        print(f"Failed to read input: {e}", file=sys.stderr)
        return 1

    total_bits_in_file = total_bytes * 8

    # Determine valid bits (exclude padding if known)
    valid_bits = total_bits_in_file
    if args.valid_bits is not None:
        valid_bits = args.valid_bits
    elif args.original_input:
        try:
            valid_bits = os.path.getsize(args.original_input)
        except OSError as e:
            print(f"Warning: could not stat original input: {e}. Falling back to total bits in file.", file=sys.stderr)
            valid_bits = total_bits_in_file

    # Clamp to [0, total_bits_in_file]
    if valid_bits < 0:
        valid_bits = 0
    if valid_bits > total_bits_in_file:
        valid_bits = total_bits_in_file

    density = (ones / valid_bits) if valid_bits else 0.0

    if args.quiet:
        print(f"{density:.12g}")
        return 0

    print("Density of 1s in bit-packed file")
    print(f"- File: {in_path}")
    print(f"- Bytes read: {total_bytes}")
    print(f"- Total bits in file: {total_bits_in_file}")
    print(f"- Ones counted: {ones}")
    if valid_bits != total_bits_in_file:
        print(f"- Valid bits (provided): {valid_bits}")
        print("  (Padding bits are zeros; ones count unchanged)")
    print(f"- Density: {density:.12g}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
