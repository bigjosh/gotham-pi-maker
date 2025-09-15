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

## Run compression

You can use the `prebuilt-digits-len` param to make pre-built cells for all groups of digits of the specified length. So, if you say `2` then all the two digit strings (eg "00", "01", ... "99") will each be made
into a cell and then any time those two digits appear in teh GDS file, you will get an SREF to the prebuilt group rather than individual digits.

Because the predefined groups themselves take up space, and becuase the more predefined strings you have the longer your names will need to be and names also take up space, 6 ends up being optimal for smallest file size. 

## Merge

You can merge all the pixel SREFs in each digit into a single polygon with the `--merge` param. Maybe some processing programs will like this better? Do remember that 
there is no way to have a poly with a hole in it in GDS so `0`, `6`, `8`, and `9` have ugly bridges in them. 

Pixels:

<img width="2198" height="304" alt="image" src="https://github.com/user-attachments/assets/8383be11-151c-4721-aee1-9edc09529e59" />


Merged:

<img width="2200" height="301" alt="image" src="https://github.com/user-attachments/assets/090a346b-dee3-4f8f-afe2-97dc79314e8d" />

## Stats 

At the end of the run, it prints the top sequneces.  The take away is that the distribution is pretty even, so not point trying to optimize for more common patterns. 

### 6 digit runs
```
Prebuilt string usage: total placements=166,000,000, unique keys used=1,000,000
Top 10 most used prebuilt strings:
   1. 741750: 231
   2. 395234: 227
   3. 590848: 227
   4. 948348: 227
   5. 088715: 225
   6. 559253: 225
   7. 541930: 223
   8. 916680: 223
   9. 270071: 222
  10. 767361: 222
Top 10 least used prebuilt strings:
   1. 957199: 109
   2. 043192: 112
   3. 075991: 112
   4. 142681: 112
   5. 925906: 113
   6. 440540: 114
   7. 464835: 114
   8. 565788: 114
   9. 093682: 115
  10. 166136: 115
```

### 7 digit runs
```
Prebuilt string usage: total placements=142,000,000, unique keys used=9,999,994
Top 10 most used prebuilt strings:
   1. 9148620: 40
   2. 3595453: 37
   3. 3675426: 37
   4. 8099352: 36
   5. 0371216: 35
   6. 0719218: 35
   7. 1548389: 35
   8. 2949619: 35
   9. 2951308: 35
  10. 3694400: 35
Top 10 least used prebuilt strings:
   1. 0108294: 1
   2. 0225603: 1
   3. 0523803: 1
   4. 0696469: 1
   5. 0732319: 1
   6. 0881149: 1
   7. 0911476: 1
   8. 1099558: 1
   9. 1163882: 1
  10. 1175242: 1
```
