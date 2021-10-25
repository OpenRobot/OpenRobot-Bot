import enum

class Enum(enum.Enum):
    def __str__(self) -> str:
        return self.name

class Player(Enum):
    PlayerOne = 1
    PlayerTwo = 2

class Option(Enum):
    ROCK = 0
    PAPER = 1
    SCISSORS = 2

class Winner(Enum):
    PlayerOne = 1
    PlayerTwo = 2
    TIE = 3

class Emoji(Enum):
    ROCK = '\U0001faa8'
    PAPER = '\U0001f4f0'
    SCISSORS = '\U00002702'

    def __str__(self) -> str:
        return self.value