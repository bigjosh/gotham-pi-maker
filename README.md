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
6. Finally we turn the grid of digits into a gds. This can take a long time, so we can test with just the first 1500 rows using
    ```
    python .\text_to_gds.py --font .\font4x6.txt --text .\pi-billion-p-grid.txt --out .\pi-billion-p-grid.gds --rows 1500
    ```

    We can then check to make sure it looks OK with KLayout.

    To run the final GDS file, we use this command which will condense every 5 digit sequence of digits into a single cell... 
    ```
    python .\text_to_gds.py --font .\font4x6.txt --text .\pi-billion-p-grid.txt --out .\pi-billion-p-grid.gds --matchlen 5
    ```

   
