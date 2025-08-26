#!/usr/bin/env python3
"""
Text to Image Converter

Converts a text file to an image where each character becomes a pixel.
- Digits 0-9 map to distinct colors
- Whitespace maps to black
- Newlines define image rows
- Optimized for large files (1B+ characters)
"""

import sys
from PIL import Image
import numpy as np
from typing import Dict, Tuple

# Color mapping for digits 0-9 (RGB tuples)
DIGIT_COLORS: Dict[str, Tuple[int, int, int]] = {
    '0': (255, 0, 0),      # Red
    '1': (0, 255, 0),      # Green
    '2': (0, 0, 255),      # Blue
    '3': (255, 255, 0),    # Yellow
    '4': (255, 0, 255),    # Magenta
    '5': (0, 255, 255),    # Cyan
    '6': (255, 128, 0),    # Orange
    '7': (128, 0, 255),    # Purple
    '8': (255, 192, 203),  # Pink
    '9': (128, 128, 128),  # Gray
}

BLACK = (0, 0, 0)  # For whitespace and unknown characters

def char_to_color(char: str) -> Tuple[int, int, int]:
    """Convert a character to its corresponding RGB color."""
    if char in DIGIT_COLORS:
        return DIGIT_COLORS[char]
    else:
        return BLACK  # Whitespace and other characters

def process_text_to_image(input_file: str, output_file: str, chunk_size: int = 1024*1024):
    """
    Convert text file to image with memory-efficient processing.
    
    Args:
        input_file: Path to input text file
        output_file: Path to output image file
        chunk_size: Size of chunks to read at once (default 1MB)
    """
    print(f"Processing {input_file} -> {output_file}")
    
    # First pass: determine image dimensions
    print("First pass: analyzing file structure...")
    max_width = 0
    height = 0
    current_width = 0
    
    with open(input_file, 'r', encoding='utf-8') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
                
            for char in chunk:
                if char == '\n':
                    max_width = max(max_width, current_width)
                    current_width = 0
                    height += 1
                else:
                    current_width += 1
    
    # Handle case where file doesn't end with newline
    if current_width > 0:
        max_width = max(max_width, current_width)
        height += 1
    
    print(f"Image dimensions: {max_width} x {height}")
    
    if max_width == 0 or height == 0:
        print("Error: Invalid file structure")
        return
    
    # Create image array
    print("Creating image array...")
    image_array = np.zeros((height, max_width, 3), dtype=np.uint8)
    
    # Second pass: populate image data
    print("Second pass: converting text to pixels...")
    row = 0
    col = 0
    
    with open(input_file, 'r', encoding='utf-8') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
                
            for char in chunk:
                if char == '\n':
                    row += 1
                    col = 0
                else:
                    if row < height and col < max_width:
                        color = char_to_color(char)
                        image_array[row, col] = color
                    col += 1
    
    # Create and save image
    print("Creating and saving image...")
    image = Image.fromarray(image_array)
    image.save(output_file, 'PNG', optimize=True)
    
    print(f"Image saved as {output_file}")
    print(f"Final dimensions: {image.width} x {image.height}")

def main():
    if len(sys.argv) != 3:
        print("Usage: python text_to_image.py <input_file> <output_file>")
        print("Example: python text_to_image.py pi-billion.txt pi_visualization.png")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    try:
        process_text_to_image(input_file, output_file)
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
