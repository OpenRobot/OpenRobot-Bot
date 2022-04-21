from math import floor, log10


def naturalnumber(value: int | float, *, caps: bool=True, significant_digits=1) -> str:
    """
    Makes a number to a human-readable strig.

    Examples:
    naturalnumber(1000) -> "1k"
    naturalnumber(100000) -> "100k"
    naturalnumber(1000000) -> "1m"
    naturalnumber(1000000000) -> "1b"
    naturalnumber(1000000000, caps=True) -> "1B"
    """

    letters = {
        1e3: "k",
        1e6: "m",
        1e9: "b",
        1e12: "t",
    }

    if value < 100:
        return str(value)

    # Get the letter for the value
    letter_items = list(letters.items())

    for i, (num, l) in enumerate(letter_items):
        try:
            if num <= value < letter_items[i + 1][0]:
                letter = l
                digit = num
                break
        except IndexError:
            letter = l
            digit = num
            break

    if caps:
        letter = letter.upper()

    left_over = int(value % digit) # e.g 1574 --> 574
    new_value = int(value // digit) # e.g 2759 --> 2

    new_left_over = int(str(left_over)[:significant_digits])

    if new_left_over == 0 or not new_left_over:
        return f"{new_value}{letter}"

    return f"{new_value}.{new_left_over}{letter}"
