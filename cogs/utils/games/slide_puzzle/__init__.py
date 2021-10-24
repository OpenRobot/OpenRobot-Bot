# Inspired by zootest#9949

import random
import typing
import time

from .error import *
from .data import *
from .enums import *

class SlidePuzzle:
    def __init__(self, **options):
        self.position: typing.List[typing.List[int]] = self.generate_random()

        self.options: typing.Dict[str, str] = options

        self.x: int = options.pop('x', 5)
        self.y: int = options.pop('y', 4)

        self.tries = 0

        self.start_time = None
        self.end_time = None
        self.duration = None

        self.help = 'You must order the numbers from 1-15.\nHere is a graph of it: ' + """```
1 2 3 4
5 6 7 8
9 10 11 12
13 14 15
```For the last button, you should leave it empty."""

    def generate_random(self) -> typing.List[typing.Union[int, None]]:
        position = []

        temp = []

        l = list(range(1, self.x*self.y)) + [None] # None = one empty space

        while len(position) <= 4: # while the generated number of rows are less-than or equals to 4
            if len(temp) >= 5: # If there are 5 or more buttons in a row
                position.append(temp)
                temp = []

            if not l:
                return position

            random_number = random.choice(l)
            l.remove(random_number)

            temp.append(random_number)

        return position

    def get_location(self, item: typing.Union[int, None]) -> Location:
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

    def possible_moves(self) -> typing.List[int]:
        l = []

        none_location = self.get_location(None)

        if none_location.x == 3:
            l.append(
                self.position[none_location.y][2]
            )
        elif none_location.x == 0:
            l.append(
                self.position[none_location.y][1]
            )
        else:
            l.append(
                self.position[none_location.y][none_location.x-1]
            )
            l.append(
                self.position[none_location.y][none_location.x+1]
            )

        if none_location.y == 0:
            l.append(
                self.position[none_location.y+1][none_location.x]
            )
        elif none_location.y == 3:
            l.append(
                self.position[none_location.y-1][none_location.x]
            )
        else:
            l.append(
                self.position[none_location.y-1][none_location.x]
            )
            l.append(
                self.position[none_location.y+1][none_location.x]
            )

        return l

    def can_move(self, number: int) -> bool:
        return int(number) in self.possible_moves()

    def move_to(self, number: int) -> typing.Union[MoveToEnum, None]:
        none_location: Location = self.get_location(None)
        number_location: Location = self.get_location(number)

        if number_location.x == none_location.x:
            if number_location.y == none_location.y+1:
                return MoveToEnum.DOWN
            elif number_location.y == none_location.y-1:
                return MoveToEnum.UP
        
        if number_location.y == none_location.y:
            if number_location.x == none_location.x+1:
                return MoveToEnum.RIGHT
            elif number_location.x == none_location.x-1:
                return MoveToEnum.LEFT
        
        return None

    def move(self, number: int):
        if not self.can_move(number):
            raise CannotBeMoved(number)

        self.tries += 1

        #move_to: typing.Union[MoveToEnum, None] = self.move_to(number) # From number perspective, not None.

        #if not move_to:
            #raise CannotBeMoved(number)

        none_location: Location = self.get_location(None)
        number_location: Location = self.get_location(number)

        self.position[none_location.y][none_location.x] = number
        self.position[number_location.y][number_location.x] = None

        if self.win():
            self.end()

    def win(self) -> bool:
        if self.position[0] == [1, 2, 3, 4, 5] and \
            self.position[1] == [6, 7, 8, 9, 10] and \
                self.position[2] == [11, 12, 13, 14, 15] and \
                    self.position[3] == [16, 17, 18, 19, None]:

            return True
        else:
            return False

    def end(self):
        self.end_time = time.perf_counter()

        self.duration = self.end_time - self.start_time

    def start(self):
        self.start_time = time.perf_counter()