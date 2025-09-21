
so im thinking 10x10 grid with 10 million digits per box? maybe further divid
we want to put 1 billion digits into a plate

160,866 x 160,866 pixels

 52,579 x 19,019  = 1,000,000,001
 52,579 * 4 = 210,316 so too wide for 4 pixel wide font. :/


160,866 / 4 = **40216 columns**  so thats the max digits per row

1000000001 / 40216 = **24865 rows** so thats how many rows we need +1 to round up

24865 * 6 =  149190  ALL GOOD

**40216 columns** * 4 pixels wide = 160864 pixels wide. 

1000000000 / 40000 = 25000

### so we can do 40000 cols x 25000 rows = 1,000,000,000 digits 

we will need to squeeze the decimial point in there, but thats ok becuase we can put it just to the left of the "1" since 1 is only 1 pixel wide.

### the `.1` in 3.1415... is going to be a single 3 pixel wide char. We will call it `P` in the digits file. 

25000 rows * 7 pixels/row = 175000 pixels per row. damn, thats too big we only have 160,866 pixels.

unfortunately we are going to have to go to variable kerning to get this to fit. we can make `1`'s be 1-3 pixels wide to create the padding. the density of 1s turns out to be about 0.10 which in hind sight should be expected. 

so we can make each line slightly too short and then pad about half the 1s to make it right justified. lets make sure the math works.

175000 * 0.92 = 161000
175000 * 0.91  = 159250

so we got very lucky seems like this should almost exactly work out with just 1 out of 10 `1` digits getting an Extra pixel in width

NOTE: We should hard code that any 1 that is first or last on a row should NOT get expanded so everything looks neat. we can easily just pick any other 1 on the row. 

OK just empirically checked and for the first 1 billion digits there are no lines of 40000 digits that have too many 1s. yeay.

also note that we actually get an extra pixel on each row becuase the last digit does not need a spacer after it. doesnt really mater with these numbers but could if things were tight. 

next check if we have room for macro gridlines. lets find the row that has the least padding room (that is, the line with the most 1s on it)...
152,564
160,866
e each of those with thinner grid lines into 10x10 with 100,000 digits in each?

we get at least 160,866 - 152,564 =  **8302** padding pixels per line. 

so maybe thick lines are 800 pixels wide * 9 = 7200
thin lines are 10 pixels wide * 90 = 900

OK, we are going to break the canvas into 40x25 visual blocks so each block is 1 million digits.

that means each block is 1000 x 1000 digits. 

so each block will be :

	160,866 / 40 = ~4000 pixels wide. 4000 * 40 = 160,000 pixels wide at fix width

	160,866 / 25 = ~6434 pixels high. 6434 / 6 = 1072.44 lines. works

double check. 
each block is 1000x1000 digits. 
width: 
each block is 1000 digits * 4 pixels wide per digit 4000 pixels wide per block, 
* 40 blocks per row = 160,000 pixels wide. FITS!

heights:
1000 digits high * 6 pixels per digit high = 6000 pixel high per block. 
* 25 blocks per canvas = 150000 . FITS!

ok, so new updated digit dimensions are:
1000 digits per block * 40 blocks per row = 40000 digits per row.
1000 digits per block * 25 blocks high = 25000 digits per col

## chunking

the laserwriter processor software is chokeng on thise files. we need to break them into chunks of 40,000 digits per chunk.
we want breaks to be on the block boundaries so we can a new chunk every two vertical blocks. this doesnt fit exactly into the 25 blocks high.
so there will be an orphan at the end.

Each block is 1000 rows high, so we will chunk every 2000 rows and then chunk boundary will be on every other block boundary.
We should get 11 files (last one is only 1000 rows). 

here is the commmand:
```
>text_to_gds.py --font .\font4x6.txt --text .\pi-billion-p-grid.txt --out .\pi-billion-p-grid.gdsklayout --rows-per-file 2000
```











