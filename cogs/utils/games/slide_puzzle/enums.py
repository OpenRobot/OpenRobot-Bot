import enum

class Enum(enum.Enum):
    def __str__(self) -> str:
        return self.name

class MoveToEnum(Enum):
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3