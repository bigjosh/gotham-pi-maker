#!/usr/bin/env python3
"""
Text-to-GDSII generator using a bitmap font.

- Font file format:
  - First line: WxH, e.g. "4x6"
  - Then for each glyph:
    - One line naming the glyph, either as a literal char in backticks, e.g. `A`,
      or as hex code like 0x41. Whitespace around is ignored.
    - Followed by H lines of bitmap rows using '.' for off and 'X' for on, e.g. "..X.X".

- Efficient generation:
  - All glyphs are prebuilt as separate GDS cells.
  - The text file is streamed chunk-by-chunk; we only read a small buffer at a time.
  - We place references to glyph cells; no per-pixel polygons are duplicated.

Notes and caveats:
- GDSII writers generally serialize the full library at write time; extremely huge
  outputs (e.g., hundreds of millions to billions of characters) will yield enormous
  files and memory usage. This script minimizes duplication via cell references but
  the top-level still holds many references. Consider tiling/wrapping to practical
  sizes via CLI options.

Requires: gdstk (pip install gdstk)
"""

from __future__ import annotations

import argparse
import io
import os
import re
from typing import Dict, Tuple, Optional

import gdstk



# ----------------------------
# Font parsing and cell build
# ----------------------------

def _parse_glyph_key(line: str) -> str:
    """Parse a glyph identifier line.

    Accepts either backticked literal like `A` or hex like 0x41.
    Returns the single-character string.
    """
    s = line.strip()
    if not s:
        raise ValueError("Empty glyph key line")

    # Backticked literal `X`
    m = re.fullmatch(r"`(.+)`", s)
    if m:
        glyph = m.group(1)
        if len(glyph) != 1:
            raise ValueError(f"Glyph literal must be a single character, got: {glyph!r}")
        return glyph

    # Hex code like 0x41
    if s.lower().startswith("0x"):
        try:
            code = int(s, 16)
            return chr(code)
        except Exception as ex:
            raise ValueError(f"Invalid hex glyph code: {s}") from ex

    # Single visible character without backticks (fallback)
    if len(s) == 1:
        return s

    raise ValueError(f"Unrecognized glyph key format: {s}")


def load_font_build_cells(
    font_path: str,
    lib: gdstk.Library,
    pixel_size: float,
    layer: int,
    datatype: int,
    cell_prefix: str = "GLY_",
) -> Tuple[Dict[str, gdstk.Cell], Tuple[int, int], float, float]:
    """Load font file and construct one cell per glyph.

    Returns:
      - dict mapping character -> gdstk.Cell
      - (width_pixels, height_pixels)
      - advance_x (char width step)
      - advance_y (line height step)
    """
    with open(font_path, "r", encoding="utf-8") as f:
        header = f.readline()
        if not header:
            raise ValueError("Font file is empty")
        header = header.strip()
        m = re.fullmatch(r"\s*(\d+)\s*[xX]\s*(\d+)\s*", header)
        if not m:
            raise ValueError(
                f"First line must be WxH like '4x6'; got: {header!r}"
            )
        w_px, h_px = int(m.group(1)), int(m.group(2))

        glyph_cells: Dict[str, gdstk.Cell] = {}

        # Precompute pixel rectangle size and step (no gap)
        step_x = pixel_size
        step_y = pixel_size
        advance_x = w_px * step_x
        advance_y = h_px * step_y

        line_iter = iter(f)
        for line in line_iter:
            line = line.rstrip("\n")
            if not line.strip():
                continue  # skip blank lines

            # Parse glyph identifier line
            ch = _parse_glyph_key(line)

            # Read h_px bitmap rows
            rows = []
            for _ in range(h_px):
                try:
                    row = next(line_iter)
                except StopIteration:
                    raise ValueError(
                        f"Unexpected EOF while reading bitmap for glyph {ch!r}"
                    )
                row = row.rstrip("\n").strip()
                if len(row) != w_px:
                    raise ValueError(
                        f"Row length {len(row)} != width {w_px} for glyph {ch!r}: {row!r}"
                    )
                rows.append(row)

            # Build cell for this glyph
            safe_name = f"{cell_prefix}{ord(ch):02X}"
            cell = lib.new_cell(safe_name)

            # Create rectangles for ON pixels
            polys = []
            for y in range(h_px):
                row = rows[y]
                for x in range(w_px):
                    if row[x] == 'X':
                        x0 = x * step_x
                        y0 = (h_px - 1 - y) * step_y  # origin at bottom-left
                        rect = gdstk.rectangle(
                            (x0, y0), (x0 + pixel_size, y0 + pixel_size),
                            layer=layer, datatype=datatype
                        )
                        polys.append(rect)

            if polys:
                cell.add(*polys)

            glyph_cells[ch] = cell

    return glyph_cells, (w_px, h_px), advance_x, advance_y


# ----------------------------
# Text streaming and placement
# ----------------------------

def stream_text_to_cells(
    text_path: str,
    lib: gdstk.Library,
    glyph_cells: Dict[str, gdstk.Cell],
    top_cell_name: str,
    advance_x: float,
    advance_y: float,
    newline_advance: Optional[float],
    rows_limit: Optional[int],
) -> gdstk.Cell:
    """Create top-level cell containing references for streamed text.

    If an unsupported character is encountered (missing in glyph_cells),
    a ValueError is raised.
    """
    top = lib.new_cell(top_cell_name)

    x = 0.0
    y = 0.0

    # Read stream in buffered chunks
    bufsize = 1 << 20  # 1 MiB
    row=0
    cell_count=0
    with open(text_path, "r", encoding="utf-8", newline="") as fin:
        while True:
            chunk = fin.read(bufsize)
            if not chunk:
                break
            for ch in chunk:
                if ch == '\r':
                    continue

                if ch == '\n':
                    # newline
                    x = 0.0
                    y -= (newline_advance if newline_advance is not None else advance_y)
                    row += 1
                    print(f"row={row:,} glyph_count={cell_count:,}")
                    if rows_limit is not None and row >= rows_limit:
                        return top

                else:

                    # no need to put anything in output for whitespace

                    if (ch != " "):

                        cell = glyph_cells.get(ch)

                        if cell is None:
                            raise ValueError(f"Missing glyph for character: {ch!r}")


                        ref = gdstk.Reference(cell, origin=(x, y))

                        top.add(ref)

                        cell_count += 1

                    x += advance_x

    return top


# ----------------------------
# CLI
# ----------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert a text file to GDSII using a bitmap font.")
    p.add_argument("--font", required=True, help="Path to font file (custom format)")
    p.add_argument("--text", required=True, help="Path to input text file to render")
    p.add_argument("--out", required=True, help="Output GDSII file path (.gds)")

    p.add_argument("--pixel-size", type=float, default=1.0, help="Size of one font pixel")
    p.add_argument("--layer", type=int, default=1, help="GDS layer for glyph polygons")
    p.add_argument("--datatype", type=int, default=0, help="GDS datatype for glyph polygons")
    p.add_argument("--line-advance", type=float, default=None, help="Vertical advance per newline (defaults to glyph height)")
    p.add_argument("--rows", type=int, default=None, help="Maximum number of rows (lines) to process")

    p.add_argument("--top-cell", default="TEXT", help="Name of the top-level cell")
    p.add_argument("--unit", type=float, default=1e-6, help="Library unit (e.g., micron)")
    p.add_argument("--precision", type=float, default=1e-9, help="Library precision")

    return p.parse_args()


def main() -> None:
    args = parse_args()

    lib = gdstk.Library(unit=args.unit, precision=args.precision)

    glyph_cells, (w_px, h_px), adv_x, adv_y = load_font_build_cells(
        font_path=args.font,
        lib=lib,
        pixel_size=args.pixel_size,
        layer=args.layer,
        datatype=args.datatype,
    )

    top = stream_text_to_cells(
        text_path=args.text,
        lib=lib,
        glyph_cells=glyph_cells,
        top_cell_name=args.top_cell,
        advance_x=adv_x,
        advance_y=adv_y,
        newline_advance=args.line_advance,
        rows_limit=args.rows,
    )

    lib.write_gds(args.out)
    print(f"Wrote GDS: {args.out}")


if __name__ == "__main__":
    main()
