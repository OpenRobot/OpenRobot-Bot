from math import floor, log10


def naturalnumber(value, significant_digits=2, strip_trailing_zeros=True) -> str:
    """
    Adaption of humanize_numbers_fp that will try to print a given number of significant digits, but sometimes more or
    less for easier reading.

    Examples:
    humanize_number(6666666, 2) = 6.7M
    humanize_number(6000000, 2) = 6M
    humanize_number(6000000, 2, strip_trailing_zeros=False) = 6.0M
    humanize_number(.666666, 2) = 0.67
    humanize_number(.0006666, 2) = 670µ
    """
    powers = [10 ** x for x in (12, 9, 6, 3, 0, -3, -6, -9)]
    human_powers = ['T', 'B', 'M', 'K', '', 'm', 'µ', 'n']
    is_negative = False
    suffix = ''

    if not isinstance(value, float):
        value = float(value)
    if value < 0:
        is_negative = True
        value = abs(value)
    if value == 0:
        decimal_places = max(0, significant_digits - 1)
    elif .001 <= value < 1:  # don't humanize these, because 3.0m can be interpreted as 3 million
        decimal_places = max(0, significant_digits - int(floor(log10(value))) - 1)
    else:
        p = next((x for x in powers if value >= x), 10 ** -9)
        i = powers.index(p)
        value = value / p
        before = int(log10(value)) + 1
        decimal_places = max(0, significant_digits - before)
        suffix = human_powers[i]

    return_value = ("%." + str(decimal_places) + "f") % value
    if is_negative:
        return_value = "-" + return_value
    if strip_trailing_zeros and '.' in return_value:
        return_value = return_value.rstrip('0').rstrip('.')

    return return_value + suffix
