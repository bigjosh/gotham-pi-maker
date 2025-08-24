#!/usr/bin/env python3
"""
bitpack_ones.py

Reads an input text file (e.g., pi digits) and writes a binary file where each
bit corresponds to one input byte: 1 if the input byte is ASCII '1' (0x31),
0 otherwise. The output is packed MSB-first within each byte.

Example: input bytes "01234567" -> output bits 01000000 -> output byte 0x40.

This streams the input to support very large files.

Usage:
  python bitpack_ones.py --input pi-billion.txt --output pi-billion.ones.bin

Notes:
- Every input byte is mapped; non-'1' characters (including newlines) become 0 bits.
- Final byte is padded with 0s if the total count of input bytes is not a multiple of 8.
- Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import BinaryIO

ASCII_ONE = 0x31  # ord('1')
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB chunks


def pack_chunk_to_bits(chunk: bytes) -> bytes:
    """Pack a bytes chunk into bit-packed bytes (MSB-first per output byte).

    Each input byte -> 1 bit in output: set if byte == ASCII '1'.
    """
    out = bytearray()
    bit_acc = 0
    bit_count = 0

    for b in chunk:
        bit = 1 if b == ASCII_ONE else 0
        bit_acc = (bit_acc << 1) | bit  # MSB-first within the byte
        bit_count += 1
        if bit_count == 8:
            out.append(bit_acc)
            bit_acc = 0
            bit_count = 0

    # If there are leftover bits, pad the remaining lower bits with 0s
    if bit_count:
        bit_acc = bit_acc << (8 - bit_count)
        out.append(bit_acc)

    return bytes(out)


def stream_pack(input_fp: BinaryIO, output_fp: BinaryIO, chunk_size: int = DEFAULT_CHUNK_SIZE) -> tuple[int, int]:
    """Stream the input, writing packed bits to output.

    Returns a tuple: (input_bytes_processed, output_bytes_written)
    """
    total_in = 0
    total_out = 0

    # For correctness across chunk boundaries, we should carry bit state.
    # Instead of packing each chunk independently (which would pad in the middle),
    # we implement a streaming packer with carry-over.
    bit_acc = 0
    bit_count = 0

    while True:
        chunk = input_fp.read(chunk_size)
        if not chunk:
            break
        total_in += len(chunk)

        for b in chunk:
            bit = 1 if b == ASCII_ONE else 0
            bit_acc = (bit_acc << 1) | bit
            bit_count += 1
            if bit_count == 8:
                output_fp.write(bytes((bit_acc,)))
                total_out += 1
                bit_acc = 0
                bit_count = 0

    if bit_count:
        bit_acc = bit_acc << (8 - bit_count)
        output_fp.write(bytes((bit_acc,)))
        total_out += 1

    return total_in, total_out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pack ASCII '1' positions into a bitmask")
    p.add_argument("--input", "-i", required=True, help="Path to input text file (e.g., pi-billion.txt)")
    p.add_argument(
        "--output",
        "-o",
        required=False,
        help="Path to output binary file (default: <input>.ones.bin)",
    )
    p.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Read buffer size in bytes (default: {DEFAULT_CHUNK_SIZE})",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    in_path = args.input
    out_path = args.output or f"{in_path}.ones.bin"

    # Open files in binary mode
    try:
        with open(in_path, "rb") as fin, open(out_path, "wb") as fout:
            total_in, total_out = stream_pack(fin, fout, chunk_size=args.chunk_size)
    except FileNotFoundError:
        print(f"Input file not found: {in_path}", file=sys.stderr)
        return 1

    # Optional summary to stderr to not pollute binary output users might redirect
    try:
        in_size = os.path.getsize(in_path)
    except OSError:
        in_size = total_in
    print(
        f"Done. Input bytes: {total_in} (file size: {in_size}). Output bytes: {total_out}.",
        file=sys.stderr,
    )
    if total_in % 8:
        print(
            f"Note: last output byte padded with {8 - (total_in % 8)} zero bit(s).",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
