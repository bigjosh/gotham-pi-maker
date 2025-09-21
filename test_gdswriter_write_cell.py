# test how the gdswriter handles shared components

import gdstk

# 1. Create a shared, common component
shared_component = gdstk.Cell("SHARED_COMPONENT")
shared_component.add(gdstk.rectangle((0, 0), (1, 1), layer=1))

# 2. Create two different top-level cells that both use the shared component
A = gdstk.Cell("A")
A.add(gdstk.Reference(shared_component, (0, 0)))

B = gdstk.Cell("B")
B.add(gdstk.Reference(shared_component, (0, 0)))
B.add(gdstk.Reference(shared_component, (10, 10)))

# 3. Write both top-level cells
# The writer will keep track of what it has written.
writer = gdstk.GdsWriter("output_shared.gds")

# writer.write(shared_component)

writer.write(A)
writer.write(B)

TOP = gdstk.Cell("TOP")
TOP.add(gdstk.Reference(A, (0, 0)))
TOP.add(gdstk.Reference(B, (100, 100)))

writer.write(TOP)

writer.close()

print("GDS file 'output_shared.gds' written successfully.")
