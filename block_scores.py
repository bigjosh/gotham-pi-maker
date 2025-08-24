#!/usr/bin/env python3
"""
block_scores.py

Reads a bit-packed binary file produced by bitpack_ones.py and processes it in
fixed-size bit blocks (default 40,000 bits = 5,000 bytes). For each block, it
computes the score: (ones * 1) + (zeros * 3), where zeros = block_bits - ones,
and prints the score to stdout, one line per block.

Usage:
  python block_scores.py --input pi-billion.ones.bin --blocks 100

Options:
  --input/-i       Path to bit-packed binary input file
  --blocks/-n      Number of blocks to process (required)
  --block-bits     Bits per block (default: 40000). Must be a multiple of 8.
  --chunk-bytes    I/O read chunk size in bytes (default: 4 MiB)

Notes:
- Expects MSB-first packing, but for counting ones this is irrelevant.
- Only full blocks are processed. If the file doesn't contain enough data for
  the requested number of full blocks, processing stops early and a warning is
  printed to stderr.
- Final partial block (if any) is ignored to avoid padding effects.
- Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import BinaryIO

# Fixed block size: 40,000 bits = 5,000 bytes (evenly divisible by 8)
BLOCK_BITS = 40000
BLOCK_BYTES = BLOCK_BITS // 8  # 5000

# Precompute popcount for 0..255.
# POPCOUNT[x] gives the number of set bits (1s) in the 8-bit value x.
# Implemented as a small lookup table stored in a bytes object for compactness.
# We'll access it through a memoryview for fast indexed reads during streaming.
POPCOUNT = bytes([bin(i).count("1") for i in range(256)])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compute per-block scores from bit-packed file (fixed 40,000-bit blocks)")
    p.add_argument("--input", "-i", required=True, help="Path to bit-packed binary input file")
    p.add_argument("--blocks", "-n", type=int, required=True, help="Number of 40,000-bit blocks to process")
    return p.parse_args(argv)


def stream_block_scores(fp: BinaryIO, blocks: int) -> int:
    """Read fixed-size blocks, track the maximum score, and print it once at the end.

    For regular files, read(BLOCK_BYTES) will return a full block unless EOF.
    We stop when a partial read occurs (insufficient data for a full block).
    """
    mv = memoryview(POPCOUNT)

    blocks_done = 0
    max_score = None

    while blocks_done < blocks:
        block = fp.read(BLOCK_BYTES)
        if len(block) < BLOCK_BYTES:
            break
        # Count ones in this block via popcount table
        ones = sum(mv[b] for b in block)
        zeros = BLOCK_BITS - ones
        score = (ones * 2) + (zeros * 4)

        if (max_score is None) or (score > max_score):
            max_score = score
        blocks_done += 1

    if max_score is not None:
        # Print only the maximum score found across processed blocks
        print(max_score)
    else:
        # No full blocks processed
        print("No full blocks processed; cannot compute maximum score.", file=sys.stderr)

    return blocks_done


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    in_path = args.input
    if not os.path.exists(in_path):
        print(f"Input file not found: {in_path}", file=sys.stderr)
        return 1

    if args.blocks <= 0:
        print("--blocks must be a positive integer", file=sys.stderr)
        return 1

    try:
        with open(in_path, "rb") as f:
            done = stream_block_scores(f, args.blocks)
    except OSError as e:
        print(f"Failed to read input: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    if done < args.blocks:
        print(
            f"Warning: requested {args.blocks} block(s) but only processed {done} full block(s) due to insufficient data.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
