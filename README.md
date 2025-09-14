# gotham-pi-maker
Code to make the billion digits of Pi mask

1. Download the billion digits from here...
    https://stuff.mit.edu/afs/sipb/contrib/pi/
2. convert the leading "3.1" into "3P" with...
    ```
    convert_31_to_3p.py pi-billion.txt -o pi-billion-p.txt
    ```
    
    This makes it so that we have exacty 1 billion digits and they can exactly fit into our nice square. 
5. Run `format_into_grid` to convert the raw digit stream into our nice 40,000 x 25,000 grid with nice gridlines defining blocks of 1 million digits each.
    ```
    format_into_grid.py pi-billion-p.txt >pi-billion-p-grid.txt
    ```
6. Do a test run to turn the grid of digits into a gds. This can take a long time, so we can test with just the first 1500 rows using
    ```
    text_to_gds.py --font .\font4x6.txt --text .\pi-billion-p-grid.txt --out .\pi-billion-p-grid.gds --rows 1500
    ```

    We can then check to make sure it looks OK with KLayout.

7. To run the final GDS file, we use this command which will condense every 6 digit sequence of digits into a single cell for a smaller file size... 
    ```
    text_to_gds.py --font .\font4x6.txt --text .\pi-billion-p-grid.txt --out .\pi-billion-p-grid.gds --prebuilt-digits-len 6 --progress-every 1000    
    ```

## Notes

Cellnames are compacted base36 to save space.

Every row is made into a cell that is composed of the digits in that row. Strings of digits less than the specified prebuilkt digits len size are included as refs.

The program has the ability to split the GDS output into multipule files, each one will be a horizontal stripe of the specified row hight - which apparently is not helpful on the DWL 66+ LaserWriter.
