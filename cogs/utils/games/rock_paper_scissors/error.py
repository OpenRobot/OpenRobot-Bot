class RockPaperScissorsException(Exception):
    """Base exception for the rock paper scissors game"""

class CannotGetWinner(RockPaperScissorsException):
    """Cannot get the winner due to unexpected things."""