# File size considerations  

We'd like to minimize the size of the output GDS file. 

GDSII supports references so you can include an exoisting cell rather than repeating it.

Defining a cell that is composed of references costs 1ch + 4h (len of name rounded up to next nearest even number) + (1ah * number of included references) + 4h. So really the overhead above just including a reference is ~38 bytes for the first ~1200 instances. 

Including **a reference to an existing cell costs 24 bytes + the length of the cell name rounded up to nearest even number**...

<img width="766" height="606" alt="image" src="https://github.com/user-attachments/assets/12d08ae8-7953-4095-bdec-e35a3e1e660f" />

So we can eg have up to 36^2 = 1296 cells that can be referenced with only 26 bytes, and 36^4 = 1679616 cells that can be referenced in 28 bytes.

* So simplest strategy is to make each digit of the 10 digits be a reference and then our file size will be aprox 26 billion bytes.

One step farther, we can make each of the 100 pairs of digits be a cell and then our file will be helf as big 13 billion bytes.

Take away is that is it worth it to define and then SREF a cell if you will use that cell more than 3 times. 

In 1 billion digits, we would expect even distribution so each 1MM / 3 = ~300M would be defining. Lets round that down to 1,000,000 which is 6 digits, which I think miles emperically landed on 5 digits. We can use 4 byte long names in base 36 even up to 1M cell names. That is actually pretty crazy that every 6 digit long string appears ~10 times in 1 billion digits! :)

We can compress the definitions of these 1 million strings by composing each one out of two 3 digit strings. This will save 26*3 = 78 bytes per definition * 100,000 definitions = ~7MB. I think not worth the extra complexity?

Ok, lets try making a prebuilt cell for each 6 digit long string. Hopefully there will not be a big performance hit on the pythion dictionary at this size. 





