# gotham-pi-maker
Code to make the billion digits of Pi mask

1. Download the billion digits from here...
    https://stuff.mit.edu/afs/sipb/contrib/pi/
2. Edit the file to change the starting "3.14" into "3P4" and then delete the last char at the end of this file. This makes it so that we have exacty 1 billion digits and they can exactly fit into our nice square. You can edit the giant file with 010Edit
3. Run `format_into_grid` to convert the raw digit stream into our nice 40,000 x 25,000 grid with nice gridlines defining blocks of 1 million digits each.
    ```
    format_into_grid.py pi-billion.txt >pi-billion-grid.txt
    ```
4. You can run `text_to_image` to make the text file into a PNG just to see that it has the right shape.
5. For now, you gotta figutre out how to convert the grid text file int GDSII. Just remeber that the `P` has to be made into a single 4 pixel wide char that has ".1" in it. 
