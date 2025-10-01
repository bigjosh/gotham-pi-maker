import gdstk


def main() -> None:
    # Create a GDS library and a top cell
    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    top = gdstk.Cell("TOP")

    # Define the polygon with the specified coordinates
    points = [
        (0, 0),
        (0, 10),
        (10, 10),
        (10, 0),
        (20, 0),
        (20, 10),
        (30, 10),
        (30, 0),
        (0, 0),  # Explicitly close back to the start
    ]

    poly = gdstk.Polygon(points, layer=1, datatype=0)
    top.add(poly)

    # Add top to library and write the GDS file
    lib.add(top)
    out_path = "test_crushed_polys.gds"
    lib.write_gds(out_path)
    print(f"Wrote {out_path} with polygon of {len(poly.points)} points.")

    for p in top.polygons:
        print(f"Polygon has {len(p.points)} points.")   
        print(p.points)


if __name__ == "__main__":
    main()
