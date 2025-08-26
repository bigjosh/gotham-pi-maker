import argparse
from pathlib import Path
import sys


def convert_file(input_path: Path, output_path: Path) -> None:
    """
    Convert the first three bytes from b"3.1" to b"3P" if present.
    Writes to output_path. Raises ValueError if the file doesn't start with b"3.1".
    Processes in a streaming manner to avoid loading whole file into memory.
    """
    with input_path.open("rb") as fin:
        first3 = fin.read(3)
        if first3 != b"3.1":
            raise ValueError(f"Input file does not start with '3.1': {input_path}")

        # Open output and write replaced header, then copy the rest
        with output_path.open("wb") as fout:
            fout.write(b"3P")  # replacement
            # Copy the remainder of the file in chunks
            while True:
                chunk = fin.read(1024 * 1024)
                if not chunk:
                    break
                fout.write(chunk)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Convert files starting with '3.1' to start with '3P'.")
    parser.add_argument("input", type=Path, help="Path to input file")
    parser.add_argument("-o", "--output", type=Path, help="Path to output file. Defaults to <input>.3p")
    args = parser.parse_args(argv)

    input_path: Path = args.input
    if not input_path.exists() or not input_path.is_file():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 2

    output_path: Path = args.output if args.output else input_path.with_name(input_path.name + ".3p")

    try:
        convert_file(input_path, output_path)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 3

    print(f"Wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
