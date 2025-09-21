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

# --------------------------------------------------
# Stateful GDS cell name generator
# Sequence: A..Z, A0..AZ, B0..BZ, ..., Z0..ZZ, AA0...
# --------------------------------------------------

# 0-9, A-Z
# note that we could have probably included _ here but i dont want to risk it
_GDS_NAME_CHARS = tuple([chr(ord('0') + i) for i in range(10)] + [chr(ord('A') + i) for i in range(26)])

def next_cell_name() -> str:
    """Return the next available GDSII-compatible cell name.

    Order:
      A..Z,A0..AZ,B0..BZ,...,Z0..ZZ,A00..
    """

    # https://chatgpt.com/c/68c5c529-6620-8333-bb79-d6b1c7bff4f4
    # so ugly. how do people live like this.

    if not hasattr(next_cell_name, "value"):
        next_cell_name.value = "A"  # initialize once to "A"

    def increment_gds_name(value: str) -> str:

        # sorry i dont speak python
        begining = value
        end = ""

        while len(begining)>0:

            # simplest case, just increment the last digit if no overflow

            last_char_of_begining = begining[-1]

            if _GDS_NAME_CHARS.index(last_char_of_begining) < len(_GDS_NAME_CHARS) - 1:

                return begining[:-1] + _GDS_NAME_CHARS[_GDS_NAME_CHARS.index(last_char_of_begining) + 1] + end

            else:
                begining = begining[:-1]
                end = '0' + end

        # remeber GDS names must not start with digit. 
        return "A" + end

    next_cell_name.value = increment_gds_name(next_cell_name.value)
    return next_cell_name.value

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
        pixel_cell_name = next_cell_name()

        # print( f"building cell {pixel_cell_name} for pixel")

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

            # Build cell for this glyph using monotonic naming (A..Z, then A0..AZ, B0..BZ, ...)
            safe_name = next_cell_name()
            cell = lib.new_cell(safe_name)

            # print( f"building cell {safe_name} for glyph {ch}") 
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




# Takes a cell that is composed of References to polygons and combines all the polys into a single
# polygon and returns that as a new cell. 

# mostly written by gemini 3.5 pro, which oddly insisted on importing numpi for no reason. 
# when pressed it admitied that this was not only unessisary but also strictly bad, but still insisted
# on doing it. :/

# you must supply the new cell name or will get an exception

def old_merge_references_to_polygon(
    source_cell: gdstk.Cell,
    new_cell_name: str = None
) -> gdstk.Cell:

    """
    Merge polygons from first-level references into a single polygon (no recursion).

    Args:
        source_cell: The input gdstk.Cell containing the references to merge.
        new_cell_name:  name for the newly created cell. 

    Returns:
        A new gdstk.Cell containing the single merged polygon.
    """


    flattened_source_cell = source_cell.copy().flatten()

    # Pull polygons from the referenced cell and transform them
    for poly in flattened_source_cell.polygons:
        polygons_to_merge.append(poly)

    # Boolean union of all polygons
    merged_polygons = gdstk.boolean(polygons_to_merge, [], 'or')

    # Emit the result into a new cell.
    new_cell = gdstk.Cell(new_cell_name)
    new_cell.add(*merged_polygons)
    return new_cell

# gemino 3.5 pro wrote this

def merge_polygons_in_cell(source_cell: gdstk.Cell, new_cell_name: str, precision: float) -> gdstk.Cell:
    """
    Merge all geometry in a cell into polygons by flattening references first,
    then performing a boolean OR. Returns a new cell with the merged polygons.
    """
    # Flatten the cell (including its references) into raw polygons using a temp cell
    tmp = gdstk.Cell("__TMP_FLATTEN__")
    tmp.add(gdstk.Reference(source_cell))
    tmp.flatten()

    merged_cell = gdstk.Cell(new_cell_name)
    if not tmp.polygons:
        return merged_cell

    merged_polygons = gdstk.boolean(list(tmp.polygons), [], "or", precision=precision)
    merged_cell.add(*merged_polygons)
    return merged_cell


# takes a Dict[str, gdstk.Cell] and returns a new Dict[str, gdstk.Cell] where each cell is a merged polygon

def merge_references_to_polygon_dict(
    source_cells: Dict[str, gdstk.Cell],
    precision: float,
) -> Dict[str, gdstk.Cell]:
    # Auto-name each merged cell uniquely if no name provided
    merged: Dict[str, gdstk.Cell] = {}
    for k, v in source_cells.items():
        name = next_cell_name()
        merged[k] = merge_polygons_in_cell(v, name, precision)
    return merged


# -------------------------------------------------------------
# Build map of fixed-length digit strings to composed GDS cells
# -------------------------------------------------------------

def build_digit_string_cells_map(
    lib: gdstk.Library,
    glyph_cells: Dict[str, gdstk.Cell],
    advance_x: float,
    *,
    length: int = 6,
    progress_every: int = 100000,
) -> Dict[str, gdstk.Cell]:
    """Create a dictionary mapping zero-padded digit strings to GDS cells.

    Builds cells for all combinations of decimal digit strings of the given length.
    For length=6, this is 1,000,000 cells for strings '000000'..'999999'. Each cell
    contains references to the existing digit glyph cells positioned horizontally
    at multiples of ``advance_x``.

    Parameters:
      - lib: Target ``gdstk.Library`` in which to create the cells.
      - glyph_cells: Mapping of characters (must include '0'..'9') to glyph cells.
      - advance_x: Horizontal advance between consecutive digits.
      - length: Number of digits per string (default 6).
      - progress_every: Print a progress message every this many cells (default 100k).

    Returns:
      Dict mapping the digit string to its composed ``gdstk.Cell``.

    Notes:
      Creating 1,000,000 cells consumes significant memory and time. Use with care.
    """

    # Ensure required digit glyphs exist
    missing = [d for d in "0123456789" if d not in glyph_cells]
    if missing:
        raise ValueError(f"Missing glyphs for digits: {missing}")

    result: Dict[str, gdstk.Cell] = {}

    max_value = 10 ** length
    for i in range(max_value):
        s = f"{i:0{length}d}"
        # Use global sequence to generate a valid, unique, and short cell name
        cell_name = next_cell_name()

        # print( f"building cell {cell_name} for digit string {s}")
        cell = lib.new_cell(cell_name)

        # Place digit references left-to-right
        xx = 0.0
        for ch in s:
            gcell = glyph_cells[ch]
            cell.add(gdstk.Reference(gcell, origin=(xx, 0.0)))
            xx += advance_x

        result[s] = cell

        if progress_every and ((i + 1) % progress_every == 0):
            print(f"Built {i + 1:,}/{max_value:,} digit-string cells (up to {s})")

    return result


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

    p.add_argument(
        "--prebuilt-digits-len",
        type=int,
        default=2,
        dest="prebuilt_digits_len",
        help=(
            "If set, prebuilds all digit-string cells of this length (builds 10^N cells). "
            "N=6 creates 1,000,000 cells. N=0 creates no prebuilt cells so SREFS directly to glyph cells are used."
        ),
    )

    # Optional flag to use merged glyph cells (single polygon per glyph)
    p.add_argument(
        "--merge",
        action="store_true",
        help="When set, merge each glyph's pixel references into a single polygon before rendering.",
    )

    return p.parse_args()


def _stream_rows_to_writer(
    fin,
    lib: gdstk.Library,
    top: gdstk.Cell,
    glyph_cells: Dict[str, gdstk.Cell],
    advance_x: float,
    advance_y: float,
    combined_cells_map: Dict[str, gdstk.Cell],  # prebuilt digit-string cells
    combined_string_length: int,
    combined_usage_counts: Dict[str, int],
    rows_limit: Optional[int],
    progress_every: int = 1000,
    starting_row: int = 0,
) -> Tuple[int, bool]:
    """Stream text from an open file handle and add one cell per row to the library.

    Returns (rows_processed, eof_reached).

    Each row is emitted as its own cell inside the given library; the given top cell
    receives a reference to the row cell. The whole library (glyphs + rows + top) can
    be written at the end of the part.
    """

    y = -starting_row * advance_y
    row = 0
    cell_count = 0
    digit_count = 0

    # Local helper: build a cell from a glyph string placed at a given y
    # If digit_cells_map is provided (fixed-length strings), greedily match runs
    # of exactly that length to place a single reference for the run.
    def row_to_cell(s: str) -> gdstk.Cell:
        nonlocal cell_count, digit_count
        row_cell = lib.new_cell(next_cell_name())

        xx = 0.0

        while len(s) > 0:

            # Try prebuilt fixed-length digit-string match

            match_key = s[:combined_string_length]
            match_cell = combined_cells_map.get(match_key)

            if match_cell is not None:

                # use the prebuilt combined cell for this run of digits
                row_cell.add(gdstk.Reference(match_cell, origin=(xx,0)))
                cell_count += 1
                digit_count += combined_string_length
                # track usage count for this prebuilt string key
                # we can do this becuase defaultdict(int) will return 0 if the key is not found
                combined_usage_counts[match_key] += 1
            
                xx += advance_x * combined_string_length

                # skip the digits we just added
                s = s[combined_string_length:]

            else:    

                # Fallback: single-character glyph
                ch = s[0]

                if ch == " ":
                    xx += advance_x
                    
                else:
                    gcell = glyph_cells.get(ch)
                    if gcell is None:
                        raise ValueError(f"Missing glyph in font for character: {ch!r}")
                    row_cell.add(gdstk.Reference(gcell, origin=(xx, 0)))
                    cell_count += 1
                    digit_count += 1
                    xx += advance_x

                #skip the char we just added
                s = s[1:]

        return row_cell

    # Process rows one at a time: read line -> build row cell -> reference from top

    for line in fin:
        # With newline=None, universal newlines translates CRLF/CR to '\n'.
        # Trim the trailing newline; keep any other content intact.
        if line.endswith("\n"):
            line = line[:-1]

        # convert the row to a cell. automatically checks for matching combined cells to reference. 
        row_cell = row_to_cell(line)
        # Reference the row cell from the top cell; origin at (0, 0) since y is baked into row cell
        top.add(gdstk.Reference(row_cell, origin=(0, y)))

        # Advance to next row
        y -= advance_y
        row += 1

        # Progress reporting and optional row limit
        if progress_every and (row % progress_every == 0):
            ratio = (digit_count / cell_count) if cell_count else 0.0
            print(
                f"row={row + starting_row:,} cell_count={cell_count:,} digit_count={digit_count:,} compression ratio={ratio:.3f} defined cells={len(glyph_cells)} y-position={y:.3f}"
            )
        if rows_limit is not None and row >= rows_limit:
            # we reached the limit so return so we can start a new file
            return row, False

    # EOF reached naturally
    return row, True

    # Unreachable

# create a diagnostic gds file from a dict of gdstk.Cells

def gds_dump_of_dict(d: Dict[str, gdstk.Cell], unit: float, precision: float, advance_x: float) -> None:

    # Build a diagnostic library where each input cell is flattened into a concrete polygon-only cell.
    lib = gdstk.Library(unit=unit, precision=precision)

    flattened_cells: Dict[str, gdstk.Cell] = {}
    for key, src in d.items():
        # Create a unique name for the flattened clone
        flat_name = f"DUMP_{key}"
        # Some keys may be non-GDS-safe; fallback to generator if needed
        if not flat_name[0].isalpha():
            flat_name = next_cell_name()

        tmp = gdstk.Cell(flat_name)
        tmp.add(gdstk.Reference(src))
        tmp.flatten()
        flattened_cells[key] = tmp
        lib.add(tmp)

    top_cell = gdstk.Cell("TOP_CELL")
    x = 0.0
    for key in flattened_cells:
        v = flattened_cells[key]
        top_cell.add(gdstk.Reference(v, origin=(x, 0.0)))
        x += advance_x

    lib.add(top_cell)
    lib.write_gds("gds_dump_of_dict.gds")
    print("Wrote gds_dump_of_dict.gds")


def main() -> None:
    args = parse_args()

    part = 0
    total_rows = 0

    # Track how many times each prebuilt digit-string key is used across all parts
    # this makes it so we can blindly just increment each value
    from collections import defaultdict
    prebuilt_usage_counts: defaultdict[int] = defaultdict(int)

    if args.rows is not None:
        print(f"Processing max of {args.rows} rows..")

    if args.rows_per_file is not None:
        print(f"Processing max of {args.rows_per_file} rows per file..")
        

    with open(args.text, "r", encoding="utf-8", newline=None) as fin:
        eof = False
        while not eof and (args.rows is None or total_rows < args.rows):
            part += 1

            # New library for this part
            lib = gdstk.Library(unit=args.unit, precision=args.precision)


            # Build glyphs inside this library so row cells can reference them
            glyph_cells, (w_px, h_px), adv_x, adv_y = load_font_build_cells(
                font_path=args.font,
                lib=lib,
                pixel_size=args.pixel_size,
                layer=args.layer,
                datatype=args.datatype,
            )

            # Choose glyph set based on --merge flag
            if args.merge:
                print("Merging glyph cells into single polygons per glyph (first-level references only)..")
                merged_glyph_cells = merge_references_to_polygon_dict(glyph_cells, precision=args.precision)  # Auto-name each merged cell uniquely
                # Ensure merged cells are present in the library so downstream references resolve
                for mc in merged_glyph_cells.values():
                    lib.add(mc)
                active_glyph_cells = merged_glyph_cells
            else:
                active_glyph_cells = glyph_cells

           # gds_dump_of_dict(active_glyph_cells, unit=args.unit, precision=args.precision, advance_x=adv_x)

            print(
                f"Prebuilding digit-string cells of length {args.prebuilt_digits_len} (10^{args.prebuilt_digits_len} cells)..."
            )

            prebuilt_combined_cells_map = build_digit_string_cells_map(
                lib=lib,
                glyph_cells=active_glyph_cells,
                advance_x=adv_x,
                length=args.prebuilt_digits_len,
                progress_every=max(1, args.progress_every),
            )
            print(
                f"Prebuilt {len(prebuilt_combined_cells_map):,} digit-string cells of length {args.prebuilt_digits_len}."
            )

            # Create a top cell that will reference each row cell. TOP seems to be traditional, so we add the underline to avoid
            # collisions with our name generator.
            top = lib.new_cell("TOP_CELL")

            # helper function to find the min of a list of values, but ignore None values, or return None if all args are None
            def _min_or_none(a,b):
                if a is None:
                    return b
                if b is None:
                    return a
                return min(a,b)

            def _sub_or_none(a, b):
                if b is None or a is None:
                    return None
                return a - b

            rows_to_process = _min_or_none( args.rows_per_file , _sub_or_none(args.rows, total_rows)  )

            if rows_to_process is None:
                print("Processing all rows..")
            else:
                print(f"Processing {rows_to_process:,} rows..")

            # Stream rows into row cells and add references to top
            rows_done, eof = _stream_rows_to_writer(
                fin=fin,
                lib=lib,
                top=top,
                glyph_cells=active_glyph_cells,
                advance_x=adv_x,
                advance_y=adv_y,
                combined_cells_map=prebuilt_combined_cells_map,
                combined_string_length=args.prebuilt_digits_len,
                combined_usage_counts=prebuilt_usage_counts,
                #stop processing this file when we have done the max rows in a file, or the max rows overall

                rows_limit = rows_to_process,

                progress_every=args.progress_every,
                starting_row=total_rows,                
            )

            # Decide output path
            if args.rows_per_file is None:
                out_path = args.out
            else:
                base, ext = os.path.splitext(args.out)
                out_path = f"{base}_part{part:03d}{ext or '.gds'}"

            print(f"Writing GDS part {part}: {out_path}")
            lib.write_gds(out_path)
            print(f"Wrote GDS part {part}: {out_path}")

            total_rows += rows_done
 
    print(f"Done. Total rows processed: {total_rows:,}. Part files written: {part}.")

    # Print a brief summary of prebuilt string usage
    if prebuilt_usage_counts:
        total_prebuilt_placements = sum(prebuilt_usage_counts.values())
        nonzero_keys = len(prebuilt_usage_counts)
        print(
            f"Prebuilt string usage: total placements={total_prebuilt_placements:,}, unique keys used={nonzero_keys:,}"
        )
        # Show the top 10 most-used prebuilt strings
        print("Top 10 most used prebuilt strings:")
        top_items = sorted(prebuilt_usage_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
        for idx, (k, v) in enumerate(top_items, 1):
            print(f"  {idx:>2}. {k}: {v:,}")

        print("Top 10 least used prebuilt strings:")
        bottom_items = sorted(prebuilt_usage_counts.items(), key=lambda kv: (kv[1], kv[0]))[:10]
        for idx, (k, v) in enumerate(bottom_items, 1):
            print(f"  {idx:>2}. {k}: {v:,}")  


if __name__ == "__main__":
    main()
