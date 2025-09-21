import gdstk

lib = gdstk.Library()

# Create subcells
cell_b = gdstk.Cell("CELL_B")
cell_b.add(gdstk.rectangle((0, 0), (10, 10)))
lib.add(cell_b)

cell_a = gdstk.Cell("CELL_A")
cell_a.add(gdstk.Reference(cell_b, origin=(20, 20)))
lib.add(cell_a)

# Create a single TOP cell that references what you want visible
top = gdstk.Cell("TOP")
top.add(gdstk.Reference(cell_a, origin=(0, 0)))
# Note: cell_b is NOT directly referenced by TOP
lib.add(top)

lib.write_gds("output.gds")
