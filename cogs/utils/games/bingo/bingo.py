import discord
import typing
import random
from .error import BingoError
from .baseclass import Player, Number, Winner

class Bingo:
    def __init__(self, players: typing.List[discord.Member], *, min: int = 1, max: int = 75):
        self.x = 5
        self.y = 5
        self._players = players

        self.players: typing.List[Player] = []

        self.min: int = min
        self.max: int = max

        self.rolls: typing.List[int] = []

        self._before_check()

        self.generate_players()

    def _before_check(self):
        if self.x % 2 == 0 or self.y % 2 == 0:
            raise BingoError("x and y must be odd")

        if self.x <= 0 or self.y <= 0:
            raise BingoError(self, 'x and y value must be greater than 0')
        elif self.x == 1 and self.y == 1:
            raise BingoError(self, 'x and y value cannot be 1')

    def generate_player(self, member: discord.Member) -> Player:
        board = []

        possible_numbers = list(range(self.min, self.max+1))

        for y in range(self.y):
            board.append([])
            for x in range(self.x):
                choice = random.choice(possible_numbers)
                board[y].append(Number(choice))

                possible_numbers.remove(choice)

        board[int(self.y / 2)][int(self.x / 2)] = None # Free space

        return Player(member, board)

    def generate_players(self):
        for player in self._players:
            self.players.append(self.generate_player(player))

    def winner(self, player: Player = None) -> typing.Union[Winner, bool, None]:
        if player:
            board = player.board

            # Horizontal:
            for y in board:
                horizontal_claimed = [True if x is None else x.claimed for x in y]
                
                if all(horizontal_claimed):
                    return Winner(player, 'horizontal')
            
            # Vertical:
            for x in range(self.x):
                vertical_claimed = []

                for y in board:
                    if y[x] is None:
                        vertical_claimed.append(True)
                    else:
                        vertical_claimed.append(y[x].claimed)

                if all(vertical_claimed):
                    return Winner(player, 'vertical')

            # Diagonal:
            if board[0][0] is True and board[1][1] is True and board[3][3] is True and board[4][4] is True: # board[2][2] is None, so its a free spot and does not need to be checked.
                return Winner(player, 'diagonal-left')
            elif board[0][4] is True and board[1][3] is True and board[3][1] is True and board[4][0] is True:
                return Winner(player, 'diagonal-right')

            return False

        for player in self.players:
            board = player.board

            # Horizontal:
            for y in board:
                horizontal_claimed = [True if x is None else x.claimed for x in y]
                
                if all(horizontal_claimed):
                    return Winner(player, 'horizontal')

            # Vertical:
            for x in range(self.x):
                vertical_claimed = []

                for y in board:
                    if y[x] is None:
                        vertical_claimed.append(True)
                    else:
                        vertical_claimed.append(y[x].claimed)

                if all(vertical_claimed):
                    return Winner(player, 'vertical')

            # Diagonal:
            if board[0][0] is True and board[1][1] is True and board[3][3] is True and board[4][4] is True: # board[2][2] is None, so its a free spot and does not need to be checked.
                return Winner(player, 'diagonal-left')
            elif board[0][4] is True and board[1][3] is True and board[3][1] is True and board[4][0] is True:
                return Winner(player, 'diagonal-right')

        return None

    def get_player(self, member: discord.Member) -> Player:
        for player in self.players:
            if player.member == member:
                return player

    def roll(self) -> int:
        choice = random.randint(self.min, self.max)
        self.rolls.append(choice)
        return choice

    def claim(self, player: Player, number: int):
        if number not in self.rolls:
            raise BingoError(self, '%s is not a valid number that has been rolled.' % number)

        player.claim(number)

    def get_cords(self, player: Player, number: int) -> typing.Tuple[typing.Union[int, None], typing.Union[int, None]]:
        return player.get_number_coordinates(number)