class SlidePuzzleException(Exception):
    """The base exception for the Slide Puzzle Game."""


class CannotBeMoved(SlidePuzzleException):
    """That specific number cannot be moved for a specific reason."""

    def __init__(self, num: int):
        self.number = int(num)
        super().__init__("Number %s cannot be moved" % num)


class SwitchAttemptExhausted(SlidePuzzleException):
    """There are no more tries to switch numbers."""

    def __init__(self):
        super().__init__("No more tries are available to switch.")
