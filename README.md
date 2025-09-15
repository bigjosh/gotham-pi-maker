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

7. To run the final GDS file, we use this command which will condense every 6 digit sequence of digits into a single cell for a smaller file size, and make pixels be 750nm to fit the whole thing onto a 5.25"x5.25" mask... 
    ```
    text_to_gds.py --font .\font4x6.txt --text .\pi-billion-p-grid.txt --out .\pi-billion-p-grid.gds --prebuilt-digits-len 6 --progress-every 1000
    text_to_gds.py --font .\font4x6.txt --text .\pi-billion-p-grid.txt --out .\pi-billion-p-grid.gds --rows 1500 --prebuilt-digits-len 6 --progress-every 100 --pixel-size 750 --unit 1e-9
    ```

## Notes

Cellnames are compacted base36 to save space.

Every row is made into a cell that is composed of the digits in that row. Strings of digits less than the specified prebuilkt digits len size are included as refs.

The program has the ability to split the GDS output into multipule files, each one will be a horizontal stripe of the specified row hight - which apparently is not helpful on the DWL 66+ LaserWriter.

## Merge

You can merge all the pixel SREFs in each digit into a single polygon with the `--merge` param. Maybe some processing programs will like this better? Do remember that 
there is no way to have a poly with a hole in it in GDS so `0`, '6', '8', and '9' have ugly bridges in them. 

Pixels:

<img width="2198" height="304" alt="image" src="https://github.com/user-attachments/assets/8383be11-151c-4721-aee1-9edc09529e59" />


Merged:

<img width="2200" height="301" alt="image" src="https://github.com/user-attachments/assets/090a346b-dee3-4f8f-afe2-97dc79314e8d" />

## Stats 

At the end of the run, it prints the top used sequneces. Here are the top 10 sequences that are 6 digits long... (remember that our formating can break out sequences, so thius does not hold for Pi in general, only our layout of it). The take away is that the distribution is pretty even, so not point trying to optimize for more common patterns. 

```
Prebuilt string usage: total placements=166,000,000, unique keys used=1,000,000
  741750: 231
  395234: 227
  590848: 227
  948348: 227
  088715: 225
  559253: 225
  541930: 223
  916680: 223
  270071: 222
  767361: 222
```
