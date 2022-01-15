# Inspired by zootest#9949

import random
import time

from .error import *
from .data import *
from .enums import *


class SlidePuzzle:
    def __init__(self, **options):
        self.options: dict[str, str] = options

        self.x: int = options.pop("x", 3)
        self.y: int = options.pop("y", 3)

        self.position: list[list[int]] = self.generate_random()

        self.tries = 0

        self.start_time = None
        self.end_time = None
        self.duration = None

        s = ""
        start = 0

        for y in range(self.y):
            for x in range(start + 1, start + self.x + 1):
                s += f"{x} "

            start += self.x

            s += "\n"

        s = s[:-3]

        self._switch_attempts = SwitchAttempts(self.get_total_attempts(calculate=True))

        self.help = f"""Goal: You must order the numbers from 1-{self.x*self.y}.\nHere is a graph of it: ```
{s}
```For the last button, you should leave it empty.

Switching Numbers:
- You can switch a number with the other.
- You only have `{self._switch_attempts.total}` attempts in total{f' and `{self._switch_attempts.left}` left' if self._switch_attempts.left != self._switch_attempts.total else ''}.
- You can also switch a number with a empty number.
- Format of changing number is `num1-num2` e.g `1-5`. To change a number with a empty number, use `none` e.g `1-none`."""

    def get_total_attempts(self, *, calculate: bool = False) -> int:
        if calculate:
            if self.x == 2 and self.y == 2:
                return 0
            elif self.x == 2 and self.y == 3:
                return 0
            elif self.x == 5 or self.y == 4:
                return 2
            elif 4 in (self.x, self.y):
                return 1
            elif 3 in (self.x, self.y):
                return 1
            else:
                return 2
        else:
            return self._switch_attempts.total

    def generate_random(self) -> list[int | None]:
        position = []

        temp = []

        l = list(range(1, self.x * self.y)) + [None]  # None = one empty space

        while (
            len(position) <= self.y
        ):  # while the generated number of rows are less-than or equals to 4
            if len(temp) >= self.x:  # If there are 4 or more buttons in a row
                position.append(temp)
                temp = []

            if not l:
                return position

            random_number = random.choice(l)
            l.remove(random_number)

            temp.append(random_number)

        return position

    def get_location(self, item: int | None) -> Location:
        location = Location()

        for row in self.position:
            try:
                index = row.index(item)
            except ValueError:
                location.y += 1
                continue
            else:
                location.x = index

                return location

    def possible_moves(self) -> list[int]:
        l = []

        none_location = self.get_location(None)

        if none_location.x == self.x - 1:
            l.append(self.position[none_location.y][self.x - 1 - 1])
        elif none_location.x == 0:
            l.append(self.position[none_location.y][1])
        else:
            l.append(self.position[none_location.y][none_location.x - 1])
            l.append(self.position[none_location.y][none_location.x + 1])

        if none_location.y == 0:
            l.append(self.position[none_location.y + 1][none_location.x])
        elif none_location.y == self.y - 1:
            l.append(self.position[none_location.y - 1][none_location.x])
        else:
            l.append(self.position[none_location.y - 1][none_location.x])
            l.append(self.position[none_location.y + 1][none_location.x])

        return l

    def can_move(self, number: int) -> bool:
        return int(number) in self.possible_moves()

    def move_to(self, number: int) -> MoveToEnum | None:
        none_location: Location = self.get_location(None)
        number_location: Location = self.get_location(number)

        if number_location.x == none_location.x:
            if number_location.y == none_location.y + 1:
                return MoveToEnum.DOWN
            elif number_location.y == none_location.y - 1:
                return MoveToEnum.UP

        if number_location.y == none_location.y:
            if number_location.x == none_location.x + 1:
                return MoveToEnum.RIGHT
            elif number_location.x == none_location.x - 1:
                return MoveToEnum.LEFT

        return None

    def move(self, number: int):
        if not self.can_move(number):
            raise CannotBeMoved(number)

        self.tries += 1

        # move_to: MoveToEnum | None = self.move_to(number) # From number perspective, not None.

        # if not move_to:
        # raise CannotBeMoved(number)

        none_location: Location = self.get_location(None)
        number_location: Location = self.get_location(number)

        self.position[none_location.y][none_location.x] = number
        self.position[number_location.y][number_location.x] = None

        if self.win():
            self.end()

    def win(self) -> bool:
        try:
            l = []

            start = 0

            for position in self.position:
                if position == list(range(start + 1, start + self.x + 1)):
                    l.append(True)
                elif position == list(range(start + 1, start + self.x)) + [None]:
                    l.append(True)
                else:
                    l.append(False)

                start += self.x

            if all(l):
                return True
            else:
                return False
        except:
            pass

    def end(self):
        self.end_time = time.perf_counter()

        self.duration = self.end_time - self.start_time

    def start(self):
        self.start_time = time.perf_counter()

    @property
    def switch_attempts(self):
        return self._switch_attempts

    def switch(self, num1: int | None, num2: int | None):
        if not self._switch_attempts.left:
            raise SwitchAttemptExhausted()

        num1_location: Location = self.get_location(num1)
        num2_location: Location = self.get_location(num2)

        self.position[num1_location.y][num1_location.x] = num2
        self.position[num2_location.y][num2_location.x] = num1

        self._switch_attempts.left -= 1
