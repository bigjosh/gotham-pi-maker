# Standalone test for next_cell_name sequence
# Reimplements the minimal logic from text_to_gds.py without external deps

from __future__ import annotations

_SUFFIX_CHARS = tuple([chr(ord('0') + i) for i in range(10)] + [chr(ord('A') + i) for i in range(26)])

_NAME_STATE_LEAD = [0]  # starts at 'A'
_NAME_STATE_SUFFIX: int | None = None  # None means no suffix phase yet

def reset_cell_name_sequence(start: str = "A") -> None:
    global _NAME_STATE_LEAD, _NAME_STATE_SUFFIX
    if not start or any((c < 'A' or c > 'Z') for c in start):
        raise ValueError("start must be non-empty and contain only 'A'..'Z'")
    _NAME_STATE_LEAD = [ord(c) - ord('A') for c in start]
    _NAME_STATE_SUFFIX = None

def _lead_to_str(lead: list[int]) -> str:
    return ''.join(chr(ord('A') + i) for i in lead)

def next_cell_name() -> str:
    global _NAME_STATE_LEAD, _NAME_STATE_SUFFIX

    name = _lead_to_str(_NAME_STATE_LEAD)
    if _NAME_STATE_SUFFIX is not None:
        name += _SUFFIX_CHARS[_NAME_STATE_SUFFIX]

    if _NAME_STATE_SUFFIX is None:
        if len(_NAME_STATE_LEAD) == 1 and _NAME_STATE_LEAD[0] < 25:
            _NAME_STATE_LEAD[0] += 1
        else:
            _NAME_STATE_LEAD = [0]  # 'A'
            _NAME_STATE_SUFFIX = 0  # '0'
    else:
        _NAME_STATE_SUFFIX += 1
        if _NAME_STATE_SUFFIX >= len(_SUFFIX_CHARS):
            _NAME_STATE_SUFFIX = 0
            i = len(_NAME_STATE_LEAD) - 1
            carry = True
            while i >= 0 and carry:
                if _NAME_STATE_LEAD[i] < 25:
                    _NAME_STATE_LEAD[i] += 1
                    carry = False
                else:
                    _NAME_STATE_LEAD[i] = 0
                    i -= 1
            if carry:
                _NAME_STATE_LEAD = [0] * (len(_NAME_STATE_LEAD) + 1)

    return name


def main():
    # Test: first 30 names from fresh reset
    reset_cell_name_sequence("A")
    first_30 = [next_cell_name() for _ in range(30)]
    print("First 30:", ', '.join(first_30))

    # Find 'ZZ' and show the next 5 after it
    reset_cell_name_sequence("A")
    last = None
    steps = 0
    while True:
        last = next_cell_name()
        steps += 1
        if last == 'ZZ':
            break
    after = [next_cell_name() for _ in range(5)]
    print(f"Reached ZZ after {steps} steps. Next 5:", ', '.join(after))

    # Show the tail around the transition from Z? to AA0, to confirm behavior
    # We'll back up: regenerate and capture the last 5 before ZZ, ZZ, then next 5
    reset_cell_name_sequence("A")
    seq = []
    while True:
        s = next_cell_name()
        seq.append(s)
        if s == 'ZZ':
            break
    print("Before ZZ:", ', '.join(seq[-5:]))
    print("After ZZ:", ', '.join([next_cell_name() for _ in range(5)]))

    # Demonstrate multi-letter start caveat
    reset_cell_name_sequence("AA")
    demo = [next_cell_name() for _ in range(5)]
    print("From start=AA (caveat demo):", ', '.join(demo))

if __name__ == '__main__':
    main()
