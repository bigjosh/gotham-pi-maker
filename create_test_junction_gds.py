#!/usr/bin/env python3
"""
Create a GDS file with two layers: 'oxide-etch' and 'metal'.

Cell: 'test-junction'
- oxide-etch layer: 200 um x 200 um square centered at (0, 0)
- metal layer:      100 um x 100 um square centered inside the oxide square

Notes:
- GDS layers are numeric. We map logical names to numbers here:
  * OXIDE_ETCH_LAYER = 2
  * METAL_LAYER      = 3
- Library units are set so that 1 unit = 1 micron (unit=1e-6 m).

Requires: gdstk
Install:  pip install gdstk
"""

import gdstk
import math
# Layer mapping (numeric GDS layers)
METAL_LAYER = 3
OXIDE_ETCH_LAYER = 2
DATATYPE = 0  # Default GDS datatype
# Geometry (micrometers)
OUTER_SIZE_UM = 200.0  # oxide-etch square
INNER_SIZE_UM = 100.0  # metal square, centered inside

# Metal pad and trace parameters (micrometers)
PAD_SIZE_UM = 200.0
TRACE_WIDTH_UM = 100.0
PAD_CLEARANCE_UM = 100.0


def make_test_junction_cell(
    outer_size_um: float,
    inner_size_um: float,
    cell_name: str | None = None,
) -> gdstk.Cell:
    """Create and return a cell that contains a test junction of the given sizes.

    The cell contains two centered squares:
    - oxide-etch layer: outer_size_um x outer_size_um
    - metal layer:      inner_size_um x inner_size_um
    """
    if cell_name is None:
        cell_name = f"test-junction-{int(outer_size_um)}-{int(inner_size_um)}"

    cell = gdstk.Cell(cell_name)

    # Use integer-µm sizes and integer-aligned corners
    outer_int = int(round(outer_size_um))
    # Inner metal should not exceed oxide size when oxide < requested inner
    inner_eff = min(inner_size_um, outer_size_um)
    inner_int = int(round(inner_eff))

    # Oxide-etch: centered about x=0 with integer-aligned corners
    ox_x0 = -(outer_int // 2)
    ox_y0 = -(outer_int // 2)
    oxide_square = gdstk.rectangle(
        (ox_x0, ox_y0), (ox_x0 + outer_int, ox_y0 + outer_int),
        layer=OXIDE_ETCH_LAYER, datatype=DATATYPE,
    )

    # Metal: centered about x=0 with integer-aligned corners
    in_x0 = -(inner_int // 2)
    in_y0 = -(inner_int // 2)
    metal_square = gdstk.rectangle(
        (in_x0, in_y0), (in_x0 + inner_int, in_y0 + inner_int),
        layer=METAL_LAYER, datatype=DATATYPE,
    )

    cell.add(oxide_square)
    cell.add(metal_square)

    return cell


def _logspace_inclusive(start_um: float, stop_um: float, num: int) -> list[int]:
    """Generate num logarithmically spaced INTEGER-µm values between start and stop (inclusive).

    Rounds to nearest integer µm and removes adjacent duplicates created by rounding
    while preserving order. Ensures the first and last entries equal the rounded
    endpoints.
    """
    if num <= 1:
        return [int(round(stop_um))]
    log_start = math.log10(start_um)
    log_stop = math.log10(stop_um)
    step = (log_stop - log_start) / (num - 1)
    vals = [10 ** (log_start + i * step) for i in range(num)]
    q = [int(round(v)) for v in vals]
    # Force exact endpoints after rounding
    q[0] = int(round(start_um))
    q[-1] = int(round(stop_um))
    # Deduplicate adjacent equals while preserving order
    uniq: list[int] = []
    for v in q:
        if not uniq or v != uniq[-1]:
            uniq.append(v)
    return uniq


def make_junction_array(
    oxide_min_um: float = 5.0,
    oxide_max_um: float = 200.0,
    span_min_um: float = 5.0,
    span_max_um: float = 200.0,
    total_width_um: float = 9000.0,
    total_height_um: float = 5000.0,
    clearance_x_um: float = 200.0,
    clearance_y_um: float = 100.0,
    inner_size_um: float = 100.0,
    array_cell_name: str = "test-junction-array",
) -> gdstk.Cell:
    """Create an array of stacked junctions varying oxide size (X) and span (Y).

    - X-axis varies oxide outer size logarithmically from oxide_min_um to oxide_max_um.
    - Y-axis varies span (gap) logarithmically from span_min_um to span_max_um.
    - Ensures at least the requested clearances between devices. Horizontal pitch
      is uniform using worst-case device width. Vertical pitch is computed per-row
      from the actual span for that row so more rows can fit while maintaining the
      specified clearance.
    """
    # Integerized worst-case footprint and pitches
    oxide_max_int = int(round(oxide_max_um))
    span_max_int = int(round(span_max_um))
    pad_size_int = int(round(PAD_SIZE_UM))
    pad_clearance_int = int(round(PAD_CLEARANCE_UM))
    clearance_x_int = int(round(clearance_x_um))
    clearance_y_int = int(round(clearance_y_um))
    total_w_int = int(round(total_width_um))
    total_h_int = int(round(total_height_um))

    width_max = max(pad_size_int, oxide_max_int)
    height_max = 2 * oxide_max_int + span_max_int + 2 * (pad_clearance_int + pad_size_int)

    pitch_x = width_max + clearance_x_int
    # How many columns can we fit (integer arithmetic)?
    ncols = max(1, (total_w_int - width_max) // pitch_x + 1)

    # Build oxide sizes across columns (logarithmic integers)
    oxide_sizes = _logspace_inclusive(oxide_min_um, oxide_max_um, ncols)

    # Build candidate spans (more than we think we need), then place as many rows
    # as will fit with per-row height while maintaining vertical clearance.
    candidate_rows = max(8, (total_h_int // (height_max // 2 + clearance_y_int)))
    spans_all = _logspace_inclusive(span_min_um, span_max_um, candidate_rows)

    # Row height components (worst-case over columns)
    row_base = 2 * oxide_max_int + 2 * (pad_clearance_int + pad_size_int)

    # Cumulative placement from bottom to top within [0, total_h_int]
    row_origins: list[int] = []
    spans_used: list[int] = []
    y_cursor = 0
    for sp in spans_all:
        row_h = row_base + sp
        if y_cursor + row_h > total_h_int:
            break
        # Compute the origin Y so that the row bottom aligns at y_cursor using worst-case outer
        total_h_max = 2 * oxide_max_int + sp
        bottom_offset = - (total_h_max // 2) - pad_clearance_int - pad_size_int
        origin_y = y_cursor - bottom_offset
        row_origins.append(origin_y)
        spans_used.append(sp)
        y_cursor += row_h + clearance_y_int

    array_cell = gdstk.Cell(array_cell_name)

    # Place devices: columns iterate oxide sizes; rows use spans_used and row_origins
    for j, oxide_um in enumerate(oxide_sizes):
        x = (width_max // 2) + j * pitch_x
        for i, sp in enumerate(spans_used):
            y = row_origins[i]
            child_name = f"stack-ox{int(oxide_um)}-sp{int(sp)}"
            child = make_stacked_test_junction_cell(
                outer_size_um=float(oxide_um),
                inner_size_um=float(inner_size_um),
                span_um=float(sp),
                cell_name=child_name,
            )
            array_cell.add(gdstk.Reference(child, (int(x), int(y))))

    return array_cell


def make_stacked_test_junction_cell(
    outer_size_um: float,
    inner_size_um: float,
    span_um: float,
    cell_name: str | None = None,
) -> gdstk.Cell:
    """Create and return a cell with two junctions stacked along +Y/-Y.

    The vertical space between the TOP edge of the bottom oxide square and the
    BOTTOM edge of the top oxide square equals span_um.
    """
    if cell_name is None:
        cell_name = f"test-junction-stack-{int(outer_size_um)}-{int(inner_size_um)}-{int(span_um)}"

    cell = gdstk.Cell(cell_name)

    # Integerized parameters
    outer_int = int(round(outer_size_um))
    inner_eff = min(inner_size_um, outer_int)
    inner_int = int(round(inner_eff))
    span_int = int(round(span_um))
    pad_size_int = int(round(PAD_SIZE_UM))
    trace_w_int = int(round(TRACE_WIDTH_UM))
    pad_clearance_int = int(round(PAD_CLEARANCE_UM))

    # Common X coordinates (centered horizontally on origin)
    ox_x0 = -outer_int // 2
    ox_x1 = ox_x0 + outer_int
    in_x0 = -inner_int // 2
    in_x1 = in_x0 + inner_int
    tr_x0 = -trace_w_int // 2
    tr_x1 = tr_x0 + trace_w_int
    pad_x0 = -pad_size_int // 2
    pad_x1 = pad_x0 + pad_size_int

    # Vertical placement ensuring integer coordinates and exact span
    total_h = 2 * outer_int + span_int
    y_bot0 = - (total_h // 2)                  # bottom oxide bottom
    y_bot1 = y_bot0 + outer_int                # bottom oxide top
    y_top0 = y_bot1 + span_int                 # top oxide bottom
    y_top1 = y_top0 + outer_int                # top oxide top

    # Bottom junction (oxide, inner, pad, trace)
    oxide_bot = gdstk.rectangle((ox_x0, y_bot0), (ox_x1, y_bot1), layer=OXIDE_ETCH_LAYER, datatype=DATATYPE)
    inner_bot_y0 = y_bot0 + (outer_int - inner_int) // 2
    inner_bot_y1 = inner_bot_y0 + inner_int
    metal_bot = gdstk.rectangle((in_x0, inner_bot_y0), (in_x1, inner_bot_y1), layer=METAL_LAYER, datatype=DATATYPE)
    # Bottom pad below with clearance
    pad_bot_top = y_bot0 - pad_clearance_int
    pad_bot = gdstk.rectangle((pad_x0, pad_bot_top - pad_size_int), (pad_x1, pad_bot_top), layer=METAL_LAYER, datatype=DATATYPE)
    # Bottom trace from pad top to inner metal bottom
    trace_bot = gdstk.rectangle((tr_x0, pad_bot_top), (tr_x1, inner_bot_y0), layer=METAL_LAYER, datatype=DATATYPE)

    # Top junction (oxide, inner, pad, trace)
    oxide_top = gdstk.rectangle((ox_x0, y_top0), (ox_x1, y_top1), layer=OXIDE_ETCH_LAYER, datatype=DATATYPE)
    inner_top_y0 = y_top0 + (outer_int - inner_int) // 2
    inner_top_y1 = inner_top_y0 + inner_int
    metal_top = gdstk.rectangle((in_x0, inner_top_y0), (in_x1, inner_top_y1), layer=METAL_LAYER, datatype=DATATYPE)
    # Top pad above with clearance
    pad_top_bottom = y_top1 + pad_clearance_int
    pad_top = gdstk.rectangle((pad_x0, pad_top_bottom), (pad_x1, pad_top_bottom + pad_size_int), layer=METAL_LAYER, datatype=DATATYPE)
    # Top trace from inner metal top to pad bottom
    trace_top = gdstk.rectangle((tr_x0, inner_top_y1), (tr_x1, pad_top_bottom), layer=METAL_LAYER, datatype=DATATYPE)

    cell.add(oxide_bot, metal_bot, pad_bot, trace_bot, oxide_top, metal_top, pad_top, trace_top)

    return cell


def write_gds(cell: gdstk.Cell, filename: str = "test-junction.gds") -> None:
    """Write the provided cell to a GDS file within a library using µm units."""
    # 1 unit = 1 µm, precision = 1 nm
    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    # Ensure all referenced cells are present in the library
    try:
        deps = list(cell.dependencies(True))  # recursive dependencies
    except Exception:
        deps = []
    if deps:
        lib.add(*deps)
    lib.add(cell)
    lib.write_gds(filename)
    print(
        f"Wrote '{filename}' with cell '{cell.name}' (oxide-etch layer={OXIDE_ETCH_LAYER}, metal layer={METAL_LAYER})."
    )


if __name__ == "__main__":
    # Build an array of junctions within 9000 x 5000 µm with ≥200 µm clearance.
    # X varies oxide size [5, 200] (log), Y varies span [5, 200] (log).
    arr = make_junction_array()
    write_gds(arr, "test-junction-array.gds")
