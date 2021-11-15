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
        x, y = None, None

        for y in self.board:
            y = 0

            for x in y:
                x = 0

                if x.number == number:
                    return x, y

                x += 1

            y += 1

        return x, y

    def claim(self, number: int):
        x, y = self.get_number_coordinates(self, number)

        self.board[y][x].claimed = True

class Winner:
    def __init__(self, player, win_type):
        self.player: Player = player
        self.win_type: str = win_type