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
  - The text file is streamed character-by-character using Python's internal buffering.
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
import os
import re
from typing import Dict, Tuple, Optional, Iterable

import gdstk



# ----------------------------
# Font parsing and cell build
# ----------------------------

# (Multiglyph composition removed; we now emit one cell per glyph.)

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

def cell_name_from_index(index: int) -> str:
    """Return a monotonically assigned cell name for the given index.

    The means that the first assigned names will be the shortest, so try to assign common names first

    Must be a valid GDS cellname, so see...
    https://chatgpt.com/c/68c438ff-a030-8324-b033-5ae43226e658

    Sequence is Excel-like using uppercase letters only:
    0 -> "A", 1 -> "B", ..., 25 -> "Z", 26 -> "AA", 27 -> "AB", ...

    This guarantees names never start with a digit and remain compact.
    """
    if index < 0:
        raise ValueError(f"cell_name_from_index expects non-negative index, got: {index}")
    name_chars = []
    n = index
    while n >= 0:
        n, rem = divmod(n, 26)
        name_chars.append(chr(ord('A') + rem))
        n -= 1  #  base-26 adjustment
    return ''.join(reversed(name_chars))

def load_font_build_cells(
    font_path: str,
    lib: gdstk.Library,
    pixel_size: float,
    layer: int,
    datatype: int,
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

        # Build a single pixel cell to be referenced by all glyphs
        next_cell_index = 0
        pixel_cell_name = cell_name_from_index(next_cell_index)
        next_cell_index += 1
        pixel_cell = lib.new_cell(pixel_cell_name)
        pixel_rect = gdstk.rectangle(
            (0.0, 0.0), (pixel_size, pixel_size), layer=layer, datatype=datatype
        )
        pixel_cell.add(pixel_rect)

        line_iter = iter(f)
        for line in line_iter:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue  # skip blank and comment lines

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

            # Build cell for this glyph using monotonic naming (A, B, ..., Z, AA, ...)
            safe_name = cell_name_from_index(next_cell_index)
            next_cell_index += 1
            cell = lib.new_cell(safe_name)

            # Create references to the single pixel cell for ON pixels
            refs = []
            for y in range(h_px):
                row = rows[y]
                for x in range(w_px):
                    if row[x] == 'X':
                        x0 = x * step_x
                        y0 = (h_px - 1 - y) * step_y  # origin at bottom-left
                        ref = gdstk.Reference(pixel_cell, origin=(x0, y0))
                        refs.append(ref)

            if refs:
                cell.add(*refs)

            glyph_cells[ch] = cell

    return glyph_cells, (w_px, h_px), advance_x, advance_y


# pass in a string of glyphs and it will create a new cell that has all of the glyphs referenced in it

# (Removed: build_multiglyph_cell and get_multiglyph_cell)


# ----------------------------
# Text streaming and placement
# ----------------------------

def stream_text_to_cells(
    text_path: str,
    lib: gdstk.Library,
    glyph_cells: Dict[str, gdstk.Cell],
    advance_x: float,
    advance_y: float,
    rows_limit: Optional[int],
) -> gdstk.Cell:
    """Create top-level cell containing references for streamed text.

    If an unsupported character is encountered (missing in glyph_cells),
    a ValueError is raised.
    """

    if rows_limit is None:
        print("Processing all rows")
    else:
        print(f"Processing up to {rows_limit} rows")    

    # Create a new cell for the top-level cell. All other cells inside of this.
    # There does not seem to be a typical name for this, so we will go with TOP_CELL
    top = lib.new_cell("TOP_CELL")

    x = 0.0
    y = 0.0

    # Read stream character-by-character (leveraging Python's buffered I/O)
    row = 0
    cell_count = 0
    digit_count = 0
    # We emit one cell per glyph.

    with open(text_path, "r", encoding="utf-8", newline=None) as fin:
        while True:
            ch = fin.read(1)
            if ch == "":
                print("EOF")
                # EOF
                break

            if ch == "\r":
                # ignore CR. Should never happen?
                continue

            if ch == "\n":
                # newline
                # according to chaTGPT, since we opened the file with newline=None, all encodeding should be converted to `\n`
                x = 0.0
                y -= advance_y
                row += 1

                print(
                    f"row={row:,} cell_count={cell_count:,} digit_count={digit_count:,} defined cells={len(glyph_cells)} y-position={y:.3f}"
                )
                if rows_limit is not None and row >= rows_limit:
                    print(f"Reached row limit {rows_limit}, stopping.")
                    return top
            else:
                # no need to put anything in output for whitespace
                if ch == " ":
                    # advance for the space itself
                    x += advance_x
                else:
                    # emit one cell per glyph
                    cell = glyph_cells.get(ch)
                    if cell is None:
                        raise ValueError(f"Missing glyph for character: {ch!r}")
                    top.add(gdstk.Reference(cell, origin=(x, y)))
                    cell_count += 1
                    digit_count += 1
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
    # note that this uses the units specified below

    p.add_argument("--layer", type=int, default=1, help="GDS layer for glyph polygons")
    p.add_argument("--datatype", type=int, default=0, help="GDS datatype for glyph polygons")
    # Always advance by one font height; no --line-advance parameter
    p.add_argument("--rows", type=int, default=None, help="Maximum number of rows (lines) to process")
    p.add_argument(
        "--rows-per-file",
        type=int,
        default=None,
        help="If set, split the output into multiple GDS files with at most this many rows per file to limit memory usage.",
    )
    p.add_argument(
        "--progress-every",
        type=int,
        default=1000,
        help="Print progress every N rows (for chunked mode and single-file mode).",
    )

    p.add_argument("--unit", type=float, default=1e-6, help="Library unit (e.g., micron)")
    p.add_argument("--precision", type=float, default=1e-9, help="Library precision")

    return p.parse_args()


def _stream_chunk_from_open_file(
    fin,
    lib: gdstk.Library,
    glyph_cells: Dict[str, gdstk.Cell],
    advance_x: float,
    advance_y: float,
    rows_limit: Optional[int],
    progress_every: int,
    starting_row: int = 0,
) -> Tuple[gdstk.Cell, int, bool]:
    """Stream from an already-open text file into a new top cell.

    Returns (top_cell, rows_processed, eof_reached).
    """
    top = lib.new_cell("TOP_CELL")

    x = 0.0
    y = -starting_row * advance_y
    row = 0
    cell_count = 0
    digit_count = 0

    while True:
        ch = fin.read(1)
        if ch == "":
            # EOF
            return top, row, True
        if ch == "\r":
            continue
        if ch == "\n":
            x = 0.0
            y -= advance_y
            row += 1
            if progress_every and (row % progress_every == 0):
                print(
                    f"row={row + starting_row:,} cell_count={cell_count:,} digit_count={digit_count:,} defined cells={len(glyph_cells)} y-position={y:.3f}"
                )
            if rows_limit is not None and row >= rows_limit:
                return top, row, False
        else:
            if ch == " ":
                x += advance_x
            else:
                cell = glyph_cells.get(ch)
                if cell is None:
                    raise ValueError(f"Missing glyph for character: {ch!r}")
                top.add(gdstk.Reference(cell, origin=(x, y)))
                cell_count += 1
                digit_count += 1
                x += advance_x

    # Unreachable


def main() -> None:
    args = parse_args()

    part = 1
    total_rows = 0

    with open(args.text, "r", encoding="utf-8", newline=None) as fin:
        while True:
            lib = gdstk.Library(unit=args.unit, precision=args.precision)
            glyph_cells, (w_px, h_px), adv_x, adv_y = load_font_build_cells(
                font_path=args.font,
                lib=lib,
                pixel_size=args.pixel_size,
                layer=args.layer,
                datatype=args.datatype,
            )

            top, rows_done, eof = _stream_chunk_from_open_file(
                fin=fin,
                lib=lib,
                glyph_cells=glyph_cells,
                advance_x=adv_x,
                advance_y=adv_y,
                rows_limit=args.rows_per_file,
                progress_every=args.progress_every,
                starting_row=total_rows,
            )


            if args.rows_per_file is None:

                # if no rows per file, just write to the output file
                out_path = args.out

            else:

                # Determine output filename with part suffix
                base, ext = os.path.splitext(args.out)
                out_path = f"{base}_part{part:03d}{ext or '.gds'}"
                
            print(f"Writing GDS part {part}: {out_path}")
            lib.write_gds(out_path)
            print(f"Wrote GDS part {part}: {out_path}")

            total_rows += rows_done
            part += 1
            if eof:
                break

    print(f"Done. Total rows processed: {total_rows:,}. Parts written: {part-1}.")


if __name__ == "__main__":
    main()
