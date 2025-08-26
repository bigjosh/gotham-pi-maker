#!/usr/bin/env python3
"""
Text file reader that processes files in chunks of 40,000 characters.
"""

import sys
import os

# We are going to make a grid of digits that is
# 40000 digits wide x 25000 digits high = 1 billion digits

# Define block sizes in digits
# currently a block is 1 million digits 

BLOCK_SIZE_X = 1000  # how many digits wide a block is
BLOCK_SIZE_Y = 1000  # how many digits high a block is

# define how the blocs are layed out on the grid
BLOCK_COUNT_X = 40  # grid is this many blocks wide
BLOCK_COUNT_Y = 25  # grid is this many blocks high

TOTAL_DIGITS = (BLOCK_SIZE_X*BLOCK_SIZE_Y) *(BLOCK_COUNT_X*BLOCK_COUNT_Y)

# Assertion to ensure we always have exactly 1 billion digits
assert TOTAL_DIGITS == 1_000_000_000, f"Grid must contain exactly 1 billion digits, but has {TOTAL_DIGITS}"

BLOCK_H_PADDING = "   "
BLOCK_V_PADDING = "\n"

# here is the bitmap 3x5 (4x6 including padding) for the digits 0-9
# Do note that we turn the ".1" in the inital "3.1" into a single
# char that is 4 pixels wide, otherwise we would only have 999,999,999 digits and that would suck.
# each digit is a GDSII polygon and includes the padding to the right and below

# read in a file of (presumably 1 billion) digits

def process_file(filename, max_rows=None):
    """
    Read a text file in chunks of ROW_SIZE characters, then break each row into blocks.
    
    Args:
        filename (str): Path to the text file to read
        max_rows (int, optional): Maximum number of rows to process. If None, process all rows.
    """
    try:
        with open(filename, 'r', encoding='utf-8') as file:

            row_number = 0

            for block_y in range(BLOCK_COUNT_Y):

                for row_in_block in range(BLOCK_SIZE_Y):

                    for block_x in range(BLOCK_COUNT_X):

                        block_row = file.read(BLOCK_SIZE_X)

                        print(block_row, end='')
                        print(BLOCK_H_PADDING, end='')

                    print("") # every row always ends with a newline.
                    row_number += 1

                    if max_rows and row_number >= max_rows:
                        break
                
                print(BLOCK_V_PADDING, end='')


    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return False
    except IOError as e:
        print(f"Error reading file '{filename}': {e}")
        return False
    except UnicodeDecodeError as e:
        print(f"Error decoding file '{filename}': {e}")
        return False
    
    return True

def main():
    """Main function to handle command line arguments and run the file reader."""
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python file_reader.py <filename> [max_rows]")
        print("Optional max_rows parameter limits the number of rows processed (for testing).")
        sys.exit(1)
    
    filename = sys.argv[1]
    max_rows = None
    
    # Parse optional max_rows argument
    if len(sys.argv) == 3:
        try:
            max_rows = int(sys.argv[2])
            if max_rows <= 0:
                print("Error: max_rows must be a positive integer.")
                sys.exit(1)
        except ValueError:
            print("Error: max_rows must be a valid integer.")
            sys.exit(1)
    
    success = process_file(filename, max_rows)
    
    if success:
        print("File reading completed successfully.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
