#!/usr/bin/env python3
"""
Text file reader that processes files in chunks of 40,000 characters.
"""

import sys
import os

# Define the row size constant
ROW_SIZE = 40000
BLOCKS_PER_ROW = 10
BLOCK_SIZE = ROW_SIZE // BLOCKS_PER_ROW  # 4000 characters per block

def calculate_block_width(block):
    """
    Calculate the width of a block based on character values.
    '1' has width 2, all other characters have width 4.
    
    Args:
        block (str): The block of text to analyze
        
    Returns:
        int: Total width of the block
    """
    width = 0
    for char in block:
        if char == '1':
            width += 2
        else:
            width += 4
    return width

def read_file_in_rows(filename, max_rows=None):
    """
    Read a text file in chunks of ROW_SIZE characters, then break each row into blocks.
    
    Args:
        filename (str): Path to the text file to read
        max_rows (int, optional): Maximum number of rows to process. If None, process all rows.
    """
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            row_number = 0
            
            while max_rows is None or (row_number < max_rows):
                chunk = file.read(ROW_SIZE)
                
                # If no more data, exit the loop
                if not chunk:
                    break

                print(f"Row {row_number} ({len(chunk)} characters):")
                print("=" * 60)

                # Break the row into blocks
                for block_num in range(BLOCKS_PER_ROW):
                    start_pos = block_num * BLOCK_SIZE
                    end_pos = start_pos + BLOCK_SIZE
                    block = chunk[start_pos:end_pos]
                    
                    # Skip empty blocks (for the last row which might be shorter)
                    if not block:
                        continue
                    
                    # Calculate the width of this block
                    block_width = calculate_block_width(block)
                    
                    print(f"  Block {block_num} ({len(block)} characters, width: {block_width}):")
                print()
                
                row_number += 1
           
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
        print(f"This program reads text files in chunks of {ROW_SIZE} characters.")
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
    
    # Check if file exists
    if not os.path.exists(filename):
        print(f"Error: File '{filename}' does not exist.")
        sys.exit(1)
    
    if max_rows:
        print(f"Reading file '{filename}' in rows of {ROW_SIZE} characters (max {max_rows} rows)...")
    else:
        print(f"Reading file '{filename}' in rows of {ROW_SIZE} characters...")
    print("=" * 60)
    
    success = read_file_in_rows(filename, max_rows)
    
    if success:
        print("File reading completed successfully.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
