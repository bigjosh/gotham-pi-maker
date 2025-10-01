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
from typing import Dict, Tuple, Optional, List

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
# by not including also means we can use underbar names for other things and not have to worry about it colliding with auto generated names
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
        return "A"

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


def make_pixel_cell( name: str, pixel_size: float, layer: int = 0, datatype: int = 0) -> gdstk.Cell:
    print(f"building pixel cell {name}")
    pixel_cell = gdstk.Cell(name)
    pixel_rect = gdstk.rectangle(
        (0.0, 0.0), (pixel_size, pixel_size), layer=layer, datatype=datatype
    )
    pixel_cell.add(pixel_rect)
    return pixel_cell

# load font from a specified file and return to the caller as a dictionary of glyph names to cells plus some metadata about the font size

def load_font(
    font_path: str,
    pixel_size: float,
    pixel_cell: gdstk.Cell,
    layer: int,
    datatype: int,
    merge: bool,
    precision: float,
) -> Tuple[Dict[str, gdstk.Cell], Tuple[int, int], float, float]:
    """Load font file and construct one cell per glyph, streaming to writer.

    Each glyph is written as soon as it's built, and we keep only a name-only
    placeholder for later SREFs. When ``merge`` is True, we flatten and boolean
    OR the glyph into a polygon-only cell that does not depend on the pixel cell.
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

        # Iterate over glyph definitions
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

            if merge:
                # Build temp glyph using pixel refs, then merge into polygons
                tmp_name = next_cell_name()
                print(f"building temp cell {tmp_name} for glyph {ch} (pre-merge)")
                tmp = gdstk.Cell(tmp_name)
                refs = []
                for yy in range(h_px):
                    r = rows[yy]
                    for xx in range(w_px):
                        if r[xx] == 'X':
                            x0 = xx * step_x
                            y0 = (h_px - 1 - yy) * step_y  # origin at bottom-left
                            refs.append(gdstk.Reference(pixel_cell, origin=(x0, y0)))
                if refs:
                    tmp.add(*refs)

                merged_name = next_cell_name()
                print(f"merging cell {tmp_name} into {merged_name}")
                merged_cell = merge_polygons_in_cell(tmp, merged_name)
                # Ensure merged polygons carry requested layer/datatype
                for poly in merged_cell.polygons:
                    poly.layer = layer
                    poly.datatype = datatype
                glyph_cells[ch] = merged_cell
            else:
                # Non-merge: glyph references pixel cell directly (by name)
                cell_name = next_cell_name()
                print(f"building cell {cell_name} for glyph {ch}")
                cell = gdstk.Cell(cell_name)

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


# gemino 3.5 pro wrote this

def merge_polygons_in_cell(source_cell: gdstk.Cell, new_cell_name: str) -> gdstk.Cell:
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

    merged_polygons = gdstk.boolean(list(tmp.polygons), [], "or")
    merged_cell.add(*merged_polygons)
    return merged_cell

# -------------------------------------------------------------
# Build map of fixed-length digit strings to composed GDS cells
# -------------------------------------------------------------

# retruns a dict that maps digit strings to cell names

def build_digit_string_cells_list(
    glyph_cells: Dict[str, str],
    advance_x: float,
    writer: gdstk.GdsWriter,
    merge: bool = False,
    length: int = 6,
    progress_every: int = 100000,
) -> Dict[str, str]:
    """Create a list of digit-string cells, streaming to writer and returning placeholders.

    Each cell is written immediately and discarded; the returned list holds only
    name-only placeholders for later SREFs.
    """


    # Ensure required digit glyphs exist
    missing = [d for d in "0123456789" if d not in glyph_cells]
    if missing:
        raise ValueError(f"Missing glyphs for digits: {missing}")

    if length <= 0:
        return []

    min_value = 0
    max_value = 10 ** length
    result: Dict[str, str] = {}

    for i in range(min_value, max_value):
        s = f"{i:0{length}d}"
        # Use global sequence to generate a valid, unique, and short cell name
        built_string_cell_name = next_cell_name()

        # print( f"building cell {cell_name} for digit string {s}")
        built_cell = gdstk.Cell(built_string_cell_name)

        # Place digit references left-to-right
        xx = 0.0
        for ch in s:
            gcell = glyph_cells[ch]
            built_cell.add(gdstk.Reference(gcell , origin=(xx, 0.0)))
            xx += advance_x

        if merge:
            # here we make a new cell that has all of the polygons from all of the glyphs merged 
            # we give it the same name as the built cell so that when it gets written to the gds_writer
            # it will use that same name. 
            merged_cell = merge_polygons_in_cell(built_cell, built_string_cell_name)
            result[s] = merged_cell.name
            writer.write(merged_cell)
            del merged_cell
            del built_cell
        else:
            result[s] = built_cell.name
            writer.write(built_cell)
            del built_cell

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

    p.add_argument(
        "--crush",
        action="store_true",
        help="Crush horizontal runs when processing rows (passed to process_row).",
    )

    return p.parse_args()


# here we will run though all of the glyph cells in the input cell and we will decompose them into thier polygons
# and then we will recombine those polys into larger polygons subject to the constraint that each BOUNDARY record
# cna only have a max of 8191 pints (each an XY) and remebering that the resulting poly must be closed so that 
# the end connects back to the begining. 
# To do this, we will take each glyph cell and find the leftmost bottom most point and make that be the "start"
# and then find the right most bottom most point and make that be the "end". we will then check to see if adding the
# current glyph to the current BOUNADARY record would exceed the maximum number of pints (keeping in mind that we also
# need to add the line that goes from the current end back to the orginal start point). if it would we will close the current
# BOUNADARY record by adding a point that goes back to the current begining (which we keep track of) and start a boundary
# where the new start of the current boundary is the start of the glyph we are adding. 


# The GDSII format has a hard limit on the number of vertices a single polygon
# (a BOUNDARY record) can have. This is 8191.
GDSII_MAX_POINTS = 8191

def crush_cell(cell: gdstk.Cell) -> gdstk.Cell:
    """
    Decomposes all geometry in a cell, merges it to create larger polygons,
    and then fractures any resulting polygons that exceed the GDSII vertex limit.

    This function simplifies complex layouts (e.g., from text glyphs) by 
    reducing the total number of polygons, which can significantly decrease 
    file size and improve processing speed in other EDA tools.

    The process is as follows:
    1.  Flattens all polygons from the input cell, grouping them by their layer 
        and datatype.
    2.  For each layer, it performs a boolean "union" (`or`) operation to merge any
        touching or overlapping polygons into single, larger polygons.
    3.  It checks each of these new polygons against the GDSII vertex limit.
    4.  If a polygon is over the limit, it is automatically fractured into 
        smaller, compliant polygons.
    5.  A new cell is returned containing the final, optimized geometry.

    Args:
        cell: The gdstk.Cell object to process.

    Returns:
        A new gdstk.Cell containing the "crushed" and optimized geometry.
    """
    
    # Create a new cell to hold the resulting crushed geometry. Appending a 
    # suffix to the name helps avoid name conflicts in the final GDSII library.
    crushed_cell = gdstk.Cell(f"{cell.name}_crushed")

    # Get all polygons, flattened from any cell references or arrays, and 
    # group them by their layer and datatype specifications.
    polygons = cell.get_polygons()

    print(f"Crushing cell {cell.name} with {len(polygons)} polygons.")

    # Perform the boolean union to merge all polygons on this layer.
    # This is the most robust way to "recombine" polygons, as it correctly
    # handles all edge cases like holes and complex concavities.
    # The result is a list of the new, larger polygons.
    merged_polygons = gdstk.boolean(polygons, [], 'or', layer=polygons[0].layer, datatype=polygons[0].datatype)

    print(f"Merged {len(polygons)} polygons into {len(merged_polygons)} polygons.")
    
    # Now, check each merged polygon and fracture it if it's too large.
    for poly in merged_polygons:
        if len(poly.points) > GDSII_MAX_POINTS:
            # This polygon exceeds the vertex limit. We use the built-in
            # fracture() method to safely chop it into multiple compliant
            # polygons. Using a number slightly less than the max is recommended.
            fractured_polys = poly.fracture(max_points=GDSII_MAX_POINTS - 1, precision=1e-3)
            print(f"Fractured polygon with {len(poly.points)} points into {len(fractured_polys)} polygons.")
            crushed_cell.add(*fractured_polys)
        else:
            print(f"Added polygon with {len(poly.points)} points.")
            # The polygon's point count is within the limit, so we can add it directly.
            crushed_cell.add(poly)

    # Return the new cell containing the optimized geometry.
    return crushed_cell

# read up to rows_limit lines from the input file and write rows to the gds file
# note that this writes each row to the gds file using a  writer so we can limit memory usage 
# adds a SREF to the created row to the top cell, but only uses the row name - the cell itself is deleted after it is written to the writer.
# retruns a bool indicating if the end of the file was reached



def _stream_rows_to_writer(
    fin,
    writer: gdstk.GdsWriter,
    top_cell: gdstk.Cell,
    glyph_cells: Dict[str, str],
    advance_x: float,
    advance_y: float,
    combined_cell_dict: Optional[Dict[str, str]],   
    combined_string_length: int,
    rows_limit: Optional[int],
    progress_every: int = 1000,
    starting_row: int = 0,
    crush: bool = False,
) ->  bool:
    """Stream text from an open file and write each row immediately using GdsWriter.

    Returns (eof_reached).
    """

    y = -starting_row * advance_y
    row = 0
    cell_count = 0
    digit_count = 0


    def process_row_crushed( cell: gdstk.Cell, line: str):
        nonlocal cell_count, digit_count   

        xx = 0

        # first we will build ourselves a dict of all the glyphs preprocessed to start at the leftmost point
        # on the baseline and end at the rightmost point on the baseline.
        

        # this function will deconstruct the passed closed list of points into an open list where
        # a line at y=0 between two points will be broken. 

        def get_poly_points_nobaseline(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:

            # first we fiond the baseline
            baseline = None
            for p in points:
                if baseline is None or p[1] <baseline:
                    baseline = p[1]

            # print(f"Baseline: {baseline}")

            # wrap the point around so we can take a slice to rotate
            # points_with_wrap = points + points
            points_with_wrap = list(points) + list(points)
            
            #print points_with_wrap with indexs
            # for i in range(len(points_with_wrap)):
                # print(f"{i}: {points_with_wrap[i]}")
            
            # find two consecutive points on the baseline, then delete the line between them
            # and make the first point found be the first point in the list via roatation
            # note that this also makes the other point be the last point on the list
            for i in range(len(points) ):    
                if points_with_wrap[i][1] == baseline and points_with_wrap[i + 1][1] == baseline:
                    # print(f" found two consecutive baseline points at {points_with_wrap[i]} and {points_with_wrap[i + 1]}")
                    return points_with_wrap[i+1:i+len(points)+1]

            raise ValueError("No baseline points found")
            

        # we really should not do this every row, but it is so fast not worth worrying about
        # print("Preprocessing glyphs so that they are now lists of points that start and stop on the baseline...")        
        glyph_to_broken_point_list_dict = {}
        for ch in glyph_cells:
            # print(f"{ch}: {len(glyph_cells[ch].polygons)} polygons")
            points = []
            for poly in glyph_cells[ch].polygons:
                # print(f"  {len(poly.points)} points")
                # print(poly.points)
                points.extend(get_poly_points_nobaseline(poly.points))
                # print(f"    {len(points)} points after breaking")
                # print(points)                
            glyph_to_broken_point_list_dict[ch] = points
            # print(f"{ch}: {len(points)} points after breaking")
            # print(points)

        # ok now we have a nice prerpocessed list of borken polys.  

        # for ch in glyph_to_broken_point_list_dict:
        #    print(f"{ch}: {len(glyph_to_broken_point_list_dict[ch])} points")
         
        # grab the layer and datatype from the first polygon  
                     
        layer = 1
        datatype = 0

        # we will keep building up points in are big crushed polygon in here until we are about to 
        # exceed the GDSII points limit of 8191, and then we will create a polygon and add it to the cell
        row_points = []

        MAX_POINTS_PER_POLYGON = 8191

        pos = 0

        def close_polygone():
            nonlocal row_points, cell_count
            if not row_points:
                return
            if row_points[0] != row_points[-1]:
                row_points.append(row_points[0])
            cell.add(gdstk.Polygon(row_points, layer=layer, datatype=datatype))
            cell_count += 1
            row_points = []

        while pos < len(line):
            ch = line[pos]
            if ch == " ":
                xx += advance_x
            else:
                digit_count += 1
                new_points = glyph_to_broken_point_list_dict[ch]

                # move this glyph to the current x position
                new_points = [(x + xx, y) for x, y in new_points]

                # print ch, new_points len, row_points len
                # print(f"Pos {pos} {ch}: {len(new_points)} points, {len(row_points)} points")

                #input("Press any key to continue...")
                
                if (len(row_points) + len(new_points) + 2 ) >= MAX_POINTS_PER_POLYGON or pos == len(line) - 1:
                    # we do not have room for these new points, or we are at the end of this line, so we need to
                    # add a polygone to the cell

                    #print(f"Adding polygone with {len(row_points)} points")

                    # lets close the polygone by connecting the last point to the first point
                    close_polygone()

                row_points += new_points
                xx += advance_x
            pos += 1

        # close any remaining polygones
        if len(row_points) > 0:
            close_polygone()

        return True


    # Local helper: process a glyph string placed at a given y and add them to the provided cell. 
    # If digit_cells_map is provided (fixed-length strings), greedily match runs
    # of exactly that length to place a single reference for the run.
    # the returned cell is "floating", it is not added to the library

    # crush_flag indicates whether to crush each row into a single cell that has one boundard record for Each glyph
    # we do this becuase the Hiedelbuerg docs say it can only handle 100K DEFs or REFs so we will give it only 
    # 25K DEFs (one per row) but oh man those are gonna be some big defs. 

    # a single line is processed and the cells are added to the provided `cell`

    def process_row( cell: gdstk.Cell, line: str):
        nonlocal cell_count, digit_count   

        xx =0

        pos =0

        while pos < len(line):

            # Try prebuilt fixed-length digit-string match
            # note that this will fail in n time if run is 0 so we don't special case it out

            # Disable fixed-length matching when combined_string_length <= 0 to avoid infinite loops.
            match_combined_cell_name = None
            if combined_string_length > 0 and combined_cell_dict is not None and crush is not True:
                if pos + combined_string_length <= len(line):
                    segment = line[pos:pos+combined_string_length]
                    match_combined_cell_name = combined_cell_dict.get(segment)

            if match_combined_cell_name is not None:
                # use the prebuilt combined cell for this run of digits
                # only ref the cell name, maybe this is faster?
                cell.add(gdstk.Reference(match_combined_cell_name, origin=(xx, 0)))
                cell_count += 1
                digit_count += combined_string_length
                xx += advance_x * combined_string_length
                # skip the digits we just added
                pos += combined_string_length
            else:
                # Fallback: single-character glyph
                ch = line[pos]

                if ch == " ":
                    xx += advance_x
                    
                else:
                    gcell = glyph_cells.get(ch)
                    if gcell is None:
                        raise ValueError(f"Missing glyph in font for character: {ch!r}")
                    # print(f"in process_row: for cell {cell.name} adding sref to cell {gcell} for char {ch!r}")
                    # only refernce the cell name, maybe this is faster?
                    # In crush mode we still use references for single chars; row-level crushing is handled elsewhere if needed.
                    cell.add(gdstk.Reference(gcell, origin=(xx, y)))
                    cell_count += 1
                    digit_count += 1
                    xx += advance_x

                #skip the char we just added
                pos += 1

        # if crush:
        #     cell = crush_cell(cell)
            
        #     if cell.polygons:
        #         # Preserve target layer/datatype from existing polygons (all should match Pixel cell's layer/datatype)
        #         polys = list(cell.polygons)
        #         target_layer = polys[0].layer
        #         target_datatype = polys[0].datatype

        #         merged = gdstk.boolean(
        #             polys,
        #             [],
        #             "or",
        #             layer=target_layer,
        #             datatype=target_datatype,
        #             precision=1e-9,
        #             max_points=8191,
        #         )

        #         # Replace existing polygons with merged result
        #         for p in polys:
        #             cell.remove(p)
        #         if merged:
        #             cell.add(*merged)
        return


    row_cell_names = []

    # Process rows one at a time: read line -> build row cell -> reference from top

    for line in fin:
        # With newline=None, universal newlines translates CRLF/CR to '\n'.
        # Trim the trailing newline; keep any other content intact.
        # will also get rid of any extra spaces so that a line with only spaces will be empty
        # and then process_row will skip it
        
        line = line.strip()
        
        # for now every row starts at the lefty edge

        # make a new row cell with the name `ROW` 
        row_cell = gdstk.Cell(f"ROW_{str(row).zfill(8)}")

        # note that we have the row built relative to y=0, we will move it down when we add it to TOP

        if crush:
            process_row_crushed(row_cell, line)
        else:
            process_row(row_cell, line)
        
        writer.write(row_cell)
        top_cell.add(gdstk.Reference(row_cell.name, origin=(0, y)))
        del row_cell

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

    if args.rows is not None:
        print(f"Processing max of {args.rows} rows..")

    if args.rows_per_file is not None:
        print(f"Processing max of {args.rows_per_file} rows per file..")
        
    with open(args.text, "r", encoding="utf-8", newline=None) as fin:
        eof = False
        while not eof and (args.rows is None or total_rows < args.rows):
            part += 1

            # Decide output path for this part
            if args.rows_per_file is None:
                out_path = args.out
            else:
                base, ext = os.path.splitext(args.out)
                out_path = f"{base}_part{part:03d}{ext or '.gds'}"
            # Open GdsWriter and emit glyph + prebuilt combined cells once for this part
            print(f"Writing GDS part {part}: {out_path}")

            writer = gdstk.GdsWriter(outfile=out_path, unit=args.unit, precision=args.precision,max_points=GDSII_MAX_POINTS)

            pixel_cell = make_pixel_cell(
                "PIXEL_CELL",
                args.pixel_size,
                args.layer,
                args.datatype,
            )
            
            # Build glyphs and stream them to the writer
            glyph_cells, (w_px, h_px), adv_x, adv_y = load_font(
                font_path=args.font,
                pixel_size=args.pixel_size,            
                pixel_cell=pixel_cell,
                layer=args.layer,
                datatype=args.datatype,
                merge=args.merge,
                precision=args.precision,
            )

            if not args.merge and not args.crush:
                # we only need  ref to the pixel if we are not merging them
                writer.write(pixel_cell)

    
             # Write glyph cells to the writer since we will need them to be first in the file since they get referenced

            if not args.crush:   
                for v in glyph_cells.values():
                    writer.write(v) 

            # gds_dump_of_dict(glyph_cells, args.unit, args.precision, adv_x)
            # return

            if args.prebuilt_digits_len and args.prebuilt_digits_len > 0:
                print(
                    f"Prebuilding digit-string cells of length {args.prebuilt_digits_len} (10^{args.prebuilt_digits_len} cells)..."
                )

                # build the prebuilt list and also write it to the write so we don't need to keep it in memory
                prebuilt_combined_cells_list = build_digit_string_cells_list(
                    glyph_cells=glyph_cells,
                    advance_x=adv_x,
                    merge=args.merge,
                    writer=writer,
                    length=args.prebuilt_digits_len,
                    progress_every=max(1, args.progress_every),
                )
                print(
                    f"Prebuilt {len(prebuilt_combined_cells_list):,} digit-string cells of length {args.prebuilt_digits_len}."
                )
            else:
                prebuilt_combined_cells_list = None
                print("Skipping prebuilding of digit-string cells (length <= 0).")

            # ok now we will start reading lines from the file and writing them each as a row cell
            # we only need tro keep track of the row names so we can later add them to the TOP cell as SREFs

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

            # Determine how many rows to process in this part. When rows_per_file is None, we will keep
            # a single output file open and stream all rows into it using GdsWriter.
            rows_to_process = _min_or_none( args.rows_per_file , _sub_or_none(args.rows, total_rows)  )

            if rows_to_process is None:
                print("Processing all rows..")
            else:
                print(f"Processing {rows_to_process:,} rows..")


            # Create a top cell that will reference each row cell

            top_cell = gdstk.Cell("TOP_CELL")

            # Stream rows: build row cells and write them immediately via the writer
            rows_done, eof = _stream_rows_to_writer(
                fin=fin,
                writer=writer,
                top_cell=top_cell,
                glyph_cells=glyph_cells,
                advance_x=adv_x,
                advance_y=adv_y,
                crush=args.crush,
                combined_cell_dict=prebuilt_combined_cells_list,
                combined_string_length=args.prebuilt_digits_len,
                rows_limit=rows_to_process,
                progress_every=args.progress_every,
                starting_row=total_rows,
            )


            # Write TOP (after all rows are written) and close writer for this part
            writer.write(top_cell)
            writer.close()
            del top_cell
            print(f"Wrote GDS part {part}: {out_path}")

            total_rows += rows_done
 
    print(f"Done. Total rows processed: {total_rows:,}. Part files written: {part}.")



if __name__ == "__main__":
    main()
