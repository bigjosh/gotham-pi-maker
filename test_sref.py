# test if srefs get included in output file automatically. 
import gdstk

# Library and cells
top = gdstk.Cell("TOP")
leaf1 = gdstk.Cell("LEAF1")
leaf2 = gdstk.Cell("LEAF2")
leaf3 = gdstk.Cell("LEAF3")

# Geometry in the leaf cells
leaf1.add(gdstk.rectangle((0, 0), (10, 5)))
leaf2.add(gdstk.rectangle((0, 0), (20, 20)))


branch1 = gdstk.Cell("BRANCH1")
branch1.add(gdstk.Reference(leaf1, origin=(0, 0)))

branch2 = gdstk.Cell("BRANCH2")
branch2.add(gdstk.Reference(leaf1, origin=(0, 0)))
branch2.add(gdstk.Reference(leaf2, origin=(20, 20)))


# References placed in TOP


top.add(gdstk.Reference(branch1, origin=(0, 0)))
top.add(gdstk.Reference(branch2, origin=(15, 0)))

# Write GDS

lib = gdstk.Library()
lib.add(top)
lib.write_gds("example.gds")
