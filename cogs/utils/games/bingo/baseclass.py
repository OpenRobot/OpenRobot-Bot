import typing
import discord

class Number:
    def __init__(self, number, claimed=False):
        self.number: typing.Union[int, None] = number
        self.claimed: bool = claimed

class Player:
    def __init__(self, member, board):
        self.member: discord.Member = member
        self.board: typing.List[typing.List[Number]] = board

    def get_number_coordinates(self, number: int):
        x_cords, y_cords = 0, 0

        for y in self.board:
            for x in y:
                if x is not None:
                    if x.number == number:
                        return x_cords, y_cords

                x_cords += 1

            y_cords += 1

        return None, None

    def claim(self, number: int):
        x, y = self.get_number_coordinates(number)

        if x is None or y is None:
            return

        self.board[y][x].claimed = True

class Winner:
    def __init__(self, player, win_type):
        self.player: Player = player
        self.win_type: str = win_type