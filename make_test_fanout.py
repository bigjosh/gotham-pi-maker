# Make a fanout for a linear testing strip
# this is a python macro that runs inside of klayout 

# it creates a layout for testing the resistance of the silicon substrate
# to do this, it creates a strip of tiny test areas, and then breaks out those test pads to larger 
# pads that the user can connect to. Because the test areas are so small compared to the pads, the pads
# must be broken out in an arc around the test areas, with traces connecting the pads to the test areas.
# the pads are arranged in a lovely arc shape, with the test areas in the center.

# it uses two layers - contact and metal
# contact is the layer that contacts the silicon substrate. it is (2/0)
# metal is the layer that is the top layer of the metalization

# params  n, radius, contact_size, contact_offset, pad_size, trace width.  
# n is the number of test areas (also the number of pads)
# radius is the radius of lines that connect the test areas to the pads
# contact_size is the edge size of each  contact area square in the contact layer (and also the metal layer)
# contact_offset is the offset between test consecutive areas 
# pad_size is the edge size of each pad in the metal layer
# trace_width is the width of the traces that connect the test areas to the pads

# to use:
# KLayout > Tools > Macro Development > New (Python) > Run

import klayout.db as db
import math

# Parameters
n = 16  # number of test areas (also the number of pads)
contact_pad_size = 2  # edge size of each contact area square
metal_pad_size = 3000  # edge size of each pad in the metal layer
contact_offset = 4  # offset between consecutive test areas (increased for better spacing)
trace_width = 2  # width of the traces that connect the test areas to the pads
radius = 15000  # radius of arc where pads are placed
center = (0.0, 0.0)  # center point of the layout
output_file = "D:\\Github\\gotham-pi-maker\\fanout.gds"

# Create layout and top cell
ly = db.Layout()
top = ly.create_cell("TOP")

# Define layers
contact = ly.layer((2, 0))  # contact layer
metal = ly.layer((3, 0))    # metal layer

# Create linear strip of test areas in the center
test_strip_length = (n - 1) * contact_offset
start_x = -test_strip_length / 2

for i in range(n):
    # Position of each test area along the x-axis
    test_x = start_x + i * contact_offset
    test_y = 0
    
    # Create small contact pad (test area)
    contact_box = db.DBox(
        test_x - contact_pad_size/2, 
        test_y - contact_pad_size/2,
        test_x + contact_pad_size/2, 
        test_y + contact_pad_size/2
    )
    top.shapes(contact).insert(contact_box)
    top.shapes(metal).insert(contact_box)  # metal layer covers contact
    
    # Calculate angle for this pad in the arc (spread over 180 degrees)
    # Reverse the angle so leftmost test area connects to leftmost pad
    angle_deg = 180.0 * (n - 1 - i) / (n - 1) if n > 1 else 0
    angle_rad = math.radians(angle_deg)
    
    # Position of the large metal pad on the arc
    pad_x = center[0] + radius * math.cos(angle_rad)
    pad_y = center[1] + radius * math.sin(angle_rad)
    
    # Create large metal pad
    pad_box = db.DBox(
        pad_x - metal_pad_size/2,
        pad_y - metal_pad_size/2,
        pad_x + metal_pad_size/2,
        pad_y + metal_pad_size/2
    )
    top.shapes(metal).insert(pad_box)
    
    # Create trace connecting test area to pad with smart routing to avoid collisions
    # Strategy: Route vertically first, then along an arc, then radially to pad
    
    # Simple staggered heights: center traces go highest, end traces stay lowest
    center_index = (n - 1) / 2.0
    distance_from_center = abs(i - center_index)
    max_distance = (n - 1) / 2.0
    # Invert so center gets maximum height, ends get minimum
    distance_from_end = max_distance - distance_from_center
    vertical_clearance = 2 * trace_width * distance_from_end
    vertical_end_y = test_y + vertical_clearance
    
    # Create simple two-segment path: vertical up, then directly to pad
    # This avoids the crossing issue from the horizontal alignment step
    trace_path = db.DPath([
        db.DPoint(test_x, test_y),        # Start at test area
        db.DPoint(test_x, vertical_end_y), # Go straight up to staggered height
        db.DPoint(pad_x, pad_y)           # Go directly to pad
    ], trace_width)
    top.shapes(metal).insert(trace_path)

# Write the GDS file
ly.write(output_file)
print(f"Fanout layout written to {output_file}")
print(f"Created {n} test areas with {n} pads connected by traces")